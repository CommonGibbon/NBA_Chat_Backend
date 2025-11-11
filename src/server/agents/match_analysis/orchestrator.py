from . import research_configs, writing_configs
from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.tools import google_search, FunctionTool
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


from google.adk.agents.callback_context import CallbackContext  
from google.adk.models import LlmRequest, LlmResponse  
from typing import Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler('agent_logs.txt', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
  
def log_agent_input(  
    callback_context: CallbackContext,   
    llm_request: LlmRequest  
) -> Optional[LlmResponse]:  
    """Log what's going into the agent."""  
    logger.info(f"\n{'='*80}\n[{callback_context.agent_name}] LLM Request:\n{'='*80}")

    if llm_request.contents:  
        logger.info(f"  Contents ({len(llm_request.contents)} messages):")
        for content in llm_request.contents:  
            role = content.role  
            if content.parts:  
                for part in content.parts:  
                    if part.text:  
                        logger.info(f"    [{role}] {part.text}")
                    elif part.function_call:  
                        logger.info(f"    [{role}] Function call: {part.function_call.name}")
                    elif part.function_response:  
                        logger.info(f"    [{role}] Function response: {part.function_response.name}")
      
    return None
  
def log_agent_output(  
    callback_context: CallbackContext,  
    llm_response: LlmResponse  
) -> Optional[LlmResponse]:  
    """Log what the agent does with the data."""  

    logger.info(f"\n[{callback_context.agent_name}] LLM Response:")
      
    if llm_response.content and llm_response.content.parts:  
        for part in llm_response.content.parts:  
            if part.text:  
                logger.info(f"  Text: {part.text}")
            elif part.function_call:  
                logger.info(f"  Tool Call: {part.function_call.name}")
                logger.info(f"    Args: {part.function_call.args}")

    return None 

class ResearchLoop():
    def __init__(self, cfg):
        self.cfg = cfg
        subagents = []
        if len(cfg.allowed_tools) > 0:
            api_researcher = Agent(
                name=f"{cfg.name}_api_researcher",
                model=research_configs.MODEL,
                instruction=create_instructions_provider(
                    trigger_key = "critique",
                    trigger_found_instructions="Additional research required: {critique}",
                    trigger_absent_instructions=cfg.system_prompt + research_configs.API_SYSTEM_PROMPT
                    ),
                tools=[get_nba_toolset(cfg.allowed_tools)],
                output_key="api_research"
            )
            subagents.append(api_researcher)
        else:
            self.api_researcher = None

        search_researcher = Agent(
            name=f"{cfg.name}_search_researcher",
            model=research_configs.MODEL,
            instruction=create_instructions_provider(
                    trigger_key = "api_research",
                    trigger_found_instructions=research_configs.SEARCH_SYSTEM_PROMPT + "API research results are {api_research}",
                    trigger_absent_instructions=cfg.system_prompt + research_configs.SEARCH_SYSTEM_PROMPT
                    ),
            tools=[google_search],
            output_key="search_research",
            before_model_callback=log_agent_input,  
            after_model_callback=log_agent_output  
        )
        subagents.append(search_researcher)

        research_critic = Agent(
            name=f"{cfg.name}_research_critic",
            model=research_configs.MODEL,
            instruction=create_instructions_provider(
                trigger_key = "api_research",
                trigger_found_instructions=research_configs.REVIEW_SYSTEM_PROMPT + """
                    API research results are: {api_research}
                    Search research results are: {search_research}
                    """,
                trigger_absent_instructions=research_configs.REVIEW_SYSTEM_PROMPT + "Search research results are: {search_research}"
                ),
            output_key="critique",
            tools=[FunctionTool(exit_loop)]
        )
        subagents.append(research_critic)

        loop_agent = LoopAgent(
            name=f"{cfg.name}_research_loop_agent",
            sub_agents=subagents,
            max_iterations=1
        )

        research_organizer = Agent(
            name=f"{cfg.name}_research_organizer",
            model=research_configs.MODEL,
            instruction=research_configs.ORGANIZER_SYSTEM_PROMPT + cfg.system_prompt,
            output_key="research_results"
        )

        self.root_agent = SequentialAgent(
            name=f"{cfg.name}_research_agent",
            sub_agents=[loop_agent, research_organizer]
        )

    async def run(self, user_message):
        app_name = f"{self.cfg.name}_research_pipeline"
        self.runner = InMemoryRunner(agent = self.root_agent, app_name = app_name)
        self.session = await self.runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            state = {"critique": "", "api_research": "", "search_research": ""}
        )

        self.results = []
        async for event in self.runner.run_async(  
            user_id=user_id,  
            session_id=self.session.id,  
            new_message=user_message  
        ):  
            if event.content and event.content.parts:  
                for part in event.content.parts:  
                    if part.text:  
                        self.results.append((event.author, part.text))
        return self.results[-1][1] # just return the last message


async def generate_research(team1: str, team2: str, game_date: str) -> Dict[str, str]:
    """
    Run all research agents in parallel and aggregate their findings.
    Returns a dict mapping research domain to narrative findings.
    """

    user_message = types.Content(  
        role='user',  
        parts=[types.Part.from_text(text=f"Conduct resaerch for the upcoming game between {team1} and {team2} on {game_date}. Todays date is {datetime.datetime.now().strftime('%m/%d/%Y')}")]  
    )  

    research_agents = {cfg.name: ResearchLoop(cfg) for cfg in research_configs.agent_configs}

    res = await asyncio.gather(*[agent.run(user_message) for agent in research_agents.values()])
    return {agent.name: result for agent, result in zip(research_agents.values(), res)}


async def write_editorial(research_findings: Dict[str, str], team1: str, team2: str, game_date: str) -> str:
    """
    Take aggregated research findings and produce the final editorial report.
    """

    writer = Agent(
        name="writer",
        model=writing_configs.MODEL,
        instruction=create_instructions_provider(writing_configs.writer.system_prompt),
        output_key="article_draft"
    )

    critic = Agent(
        name=f"critic",
        model=writing_configs.MODEL,
        instruction=writing_configs.critic.system_prompt,
        output_key="critique"
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
        parts=[types.Part.from_text(text=f"PLACEHOLDER")]  
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
