from . import research_configs, writing_configs, analyst_configs
from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.runners import InMemoryRunner
from google.genai import types
from mcp import StdioServerParameters
import sys
import asyncio
from typing import Dict, List
from dotenv import load_dotenv
import datetime
import inspect
load_dotenv()

user_id = "research_orchestrator" # this is used when running various agents

# This is used by review agents to signal that a loop should exit
def exit_loop() -> Dict[str, str]:  
    """Call this function ONLY when the results are approved, indicating the work is finished and no more changes are needed."""  
    return {"status": "approved", "message": "Work approved. Exiting refinement loop."}

def create_instructions_provider(trigger_key: str, trigger_found_instructions: str, trigger_absent_instructions: str):
    """
    To explain why this function exists, I'll need to explain a few different concepts:
    1. In a loop agent, we can send outselves back to the start of the loop.
    2. If the starting node of the loop received a system prompt, that would be repeated
    3. In order to replace the system prompt with target contents (from the reviewer), we need to know whether target contents are empty
    4. Target contents can be stored in the context of an agent session using output_keys
    """
    def build_conditional_instructions(ctx):
        target = ctx.state.get(trigger_key,"")
        return trigger_found_instructions if len(target) > 0 else trigger_absent_instructions
    return build_conditional_instructions


def get_nba_toolset(tool_filter: List[str] = []):
    nba_toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "nba_mcp_server.mcp_server"],
            ),
        ),
        tool_filter=tool_filter
    )
    return nba_toolset

def call_function(func, team1, team2, game_date):
    """
    We can potentially trigger function calls with preset inputs (team names and game date). 
    So we don't need to hard code these functions here in orchestrator.py, we can instead do some interpretation to
    determine which inputs they need and call accordingly
    """
    # define the parameters we have
    available_params = {"team1": team1, "team2": team2, "game_date": game_date}
    # Get parameter names the function expects
    func_param_names = inspect.signature(func).parameters.keys()
    params_to_pass = {
        name: available_params[name] 
        for name in func_param_names 
        if name in available_params
    }
    # call the function and return the results
    return func(**params_to_pass) 


async def execute_agent(app_name, agent, user_message):
    # create the runner + session
    runner = InMemoryRunner(agent = agent, app_name = app_name)
    session = await runner.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        state = {"critique": ""}
    )

    # execute the defined agentic loop
    results = []
    async for event in runner.run_async(  
        user_id=user_id,  
        session_id=session.id,  
        new_message=user_message  
    ):  
        if event.content and event.content.parts:  
            for part in event.content.parts:  
                if part.text:  
                    results.append((event.author, part.text))
    return results, results[-1][1] 


class ResearchLoop():
    def __init__(self, cfg):
        self.cfg = cfg
        subagents = []

        for idx, action in enumerate(cfg.llm_actions):
            new_agent = Agent(
                name=f"{cfg.name}_action_{idx}",
                model=cfg.model,
                instruction=create_instructions_provider(
                    trigger_key = "critique",
                    trigger_found_instructions="Additional research required: {critique}",
                    trigger_absent_instructions=action.system_prompt
                    ),
                tools=action.tools
            )
            subagents.append(new_agent)
    
        research_critic = Agent(
            name=f"{cfg.name}_research_critic",
            model=research_configs.REVIEW_MODEL,
            instruction=research_configs.REVIEW_SYSTEM_PROMPT,
            output_key="critique",
            tools=[FunctionTool(exit_loop)]
        )
        subagents.append(research_critic)

        loop_agent = LoopAgent(
            name=f"{cfg.name}_research_loop_agent",
            sub_agents=subagents,
            max_iterations=3
        )

        research_organizer = Agent(
            name=f"{cfg.name}_research_organizer",
            model=research_configs.ORGANIZER_MODEL,
            instruction=research_configs.ORGANIZER_SYSTEM_PROMPT,
            output_key="research_results"
        )

        self.root_agent = SequentialAgent(
            name=f"{cfg.name}_research_agent",
            sub_agents=[loop_agent, research_organizer]
        )

    async def run(self, team1: str, team2: str, game_date: str):

        # Call the setup action functions to collect context we'll inject into the context window
        setup_context = []
        for func in self.cfg.setup_actions:
            setup_context.append(call_function(func, team1, team2, game_date)) 
        setup_context = "\n".join(setup_context)    

        # create the user message
        user_text = f"Conduct research for the upcoming game between {team1} and {team2} on {game_date}. Todays date is {datetime.datetime.now().strftime('%m/%d/%Y')}"
        if len(setup_context) > 0:
            user_text += "\nAdditional context: \n" + setup_context
        user_message = types.Content(  
            role='user',  
            parts=[types.Part.from_text(text=user_text)]  
        )  

        self.results, last_message = await execute_agent(f"{self.cfg.name}_research_pipeline", self.root_agent, user_message)

        return last_message # just return the last message


async def generate_research(team1: str, team2: str, game_date: str) -> Dict[str, str]:
    """
    Run all research agents in parallel and aggregate their findings.
    Returns a dict mapping research domain to narrative findings.
    """
    # get LLM results
    research_agents = {cfg.name: ResearchLoop(cfg) for cfg in research_configs.agent_configs}
    res = await asyncio.gather(*[agent.run(team1, team2, game_date) for agent in research_agents.values()])
    agent_results = {agent.cfg.name: result for agent, result in zip(research_agents.values(), res)}
    # get hard-coded function results
    function_results = {cfg.name: call_function(cfg.function, team1, team2, game_date) for cfg in research_configs.function_configs}
    # return the joined agent and function results
    return {**agent_results, **function_results} 

async def write_editorial(research_findings: Dict[str, str], team1: str, team2: str, game_date: str) -> str:
    
    research_findings = await generate_research(team1, team2, game_date)

    critic = Agent(
        name=writing_configs.critic.name,
        model=writing_configs.critic.model,
        instruction=writing_configs.critic.system_prompt,
        output_key="critique"
    )

    ################
    # Analyze match outcome
    match_analyst = Agent(
        name = analyst_configs.match_prediction_analyst.name,
        model = analyst_configs.match_prediction_analyst.model,
        instructions = create_instructions_provider(
            trigger_key = "critique",
            trigger_found_instructions="Additional research required: {critique}",
            trigger_absent_instructions=analyst_configs.match_prediction_analyst.system_prompt
        )
    )

    match_analysis_loop = LoopAgent(
        name=f"match_analysis_loop_agent",
        sub_agents=[match_analyst, critic],
        max_iterations=3
    )

    # The code below hard codes the data we expect to get from the research_findings, but this defeats the 
    # purpose of our config.py files, which are intended to be the flexible one source of truth on what data gets processed
    # by each LLM. I think the the solution to this will involve converting this prompt into a config style as well. 
    user_message_match_analysis = types.Content(  
        role='user',  
        parts=[types.Part.from_text(text=f"""
            You are analyzing the likely outcome of the game between {team1} (your team) and {team2} on {game_date}. Todays date is {datetime.datetime.now().strftime('%m/%d/%Y')}
            You have access to the the following data:  
            Team performance: \n {research_findings['team_performance']}\n\n
            Player performance: \n {research_findings['player_performance']}\n\n
            Player activity status: \n {research_findings['inactive_players']}\n\n
            Match odds according to betting sites: \n {research_findings['odds']}\n\n                                               
            """)]  
    ) 
    ################
    # Fan narrative analyst
    fan_narrative_analyst = Agent(
        name = analyst_configs.fan_narrative_analyst.name,
        model = analyst_configs.fan_narrative_analyst.model,
        instructions = create_instructions_provider(
            trigger_key = "critique",
            trigger_found_instructions="Additional research required: {critique}",
            trigger_absent_instructions=analyst_configs.fan_narrative_analyst.system_prompt
        )
    )

    fan_narrative_loop = LoopAgent(
        name=f"fan_narrative_loop_agent",
        sub_agents=[fan_narrative_analyst, critic],
        max_iterations=3
    )

    user_message_fan_narrative = types.Content(  
        role='user',  
        parts=[types.Part.from_text(text=f"""
            You are analyzing the game between {team1} (your team) and {team2} on {game_date}. Todays date is {datetime.datetime.now().strftime('%m/%d/%Y')}
            You have access to the the following data:  
            Team performance: \n {research_findings['team_performance']}\n\n
            Player performance: \n {research_findings['player_performance']}\n\n
            Player activity status: \n {research_findings['inactive_players']}\n\n                                              
            """)]  
    ) 
    ################
    # Rivalry Analyst
    rivalry_analyst = Agent(
        name = analyst_configs.rivalry_analyst.name,
        model = analyst_configs.rivalry_analyst.model,
        instructions = create_instructions_provider(
            trigger_key = "critique",
            trigger_found_instructions="Additional research required: {critique}",
            trigger_absent_instructions=analyst_configs.rivalry_analyst.system_prompt
        )
    )

    rivalry_loop = LoopAgent(
        name=f"rivalry_loop_agent",
        sub_agents=[rivalry_analyst, critic],
        max_iterations=3
    )

    user_message_rivalry = types.Content(  
        role='user',  
        parts=[types.Part.from_text(text=f"""
            You are analyzing the rivalry between {team1} and {team2} on {game_date}. Todays date is {datetime.datetime.now().strftime('%m/%d/%Y')}
            You have access to the the following data:  
            Rivalry: \n {research_findings['rivalry']}
            """)]  
    ) 

    ################






    # The code below hard codes the data we expect to get from the research_findings, but this defeats the 
    # purpose of our config.py files, which are intended to be the flexible one source of truth on what data gets processed
    # by each LLM. I think the the solution to this will involve converting this prompt into a config style as well. 
    user_message = types.Content(  
        role='user',  
        parts=[types.Part.from_text(text=f"""
            You are analyzing the likely outcome of the game between {team1} (your team) and {team2} on {game_date}. Todays date is {datetime.datetime.now().strftime('%m/%d/%Y')}
            You have access to the the following data:  
            Team performance: \n {research_findings['team_performance']}\n\n
            Player performance: \n {research_findings['player_performance']}\n\n
            Player activity status: \n {research_findings['inactive_players']}\n\n
            Match odds according to betting sites: \n {research_findings['odds']}\n\n                                               
            """)]  
    ) 




    writer = Agent(
        name=writing_configs.writer.name,
        model=writing_configs.writer.model,
        instruction=create_instructions_provider(
            trigger_key = "critique",
            trigger_found_instructions="Additional research required: {critique}",
            trigger_absent_instructions=writing_configs.writer.system_prompt
        )
    )

    

    root_agent = LoopAgent(
        name=f"editorial_loop_agent",
        sub_agents=[writer, critic],
        max_iterations=3
    )

    app_name = f"editorial_loop"
    runner = InMemoryRunner(agent = root_agent, app_name = app_name)
    session = await runner.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        state = {"critique": ""} # initialize critique as empty for the first iteration.
    )

    user_message = types.Content(  
        role='user',  
        parts=[types.Part.from_text(text=f"You are to write an editorial on the upcoming game between {team1} (your team) and {team2} on {game_date}. Todays date is {datetime.datetime.now().strftime('%m/%d/%Y')}")]  
    )  

    results = []
    async for event in runner.run_async(  
        user_id=user_id,  
        session_id=session.id,  
        new_message=user_message  
    ):  
        if event.content and event.content.parts:  
            for part in event.content.parts:  
                if part.text:  
                    results.append((event.author, part.text))
    return results[-1][1] # just return the last message
