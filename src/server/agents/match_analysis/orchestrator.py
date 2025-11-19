from . import research_configs
from .models import agent_config, function_config
from google.adk.agents import Agent, LoopAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
import asyncio
from typing import Dict, Any, Union
from dotenv import load_dotenv
import datetime
import inspect

load_dotenv()

user_id = "research_orchestrator"

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

def call_function(func, team1, team2, game_date):
    """Dynamically calls a function with the available global context parameters."""
    available_params = {"team1": team1, "team2": team2, "game_date": game_date}
    func_param_names = inspect.signature(func).parameters.keys()
    params_to_pass = {
        name: available_params[name] 
        for name in func_param_names 
        if name in available_params
    }
    return func(**params_to_pass) 

async def execute_agent(app_name, agent, user_message):
    # create the runner + session
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        state={"critique": ""}
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
                    results.append(part.text)
    # return the final state of the output key
    final_session = await runner.session_service.get_session(  
        app_name=app_name,  
        user_id=user_id,  
        session_id=session.id  
    )  
    return final_session.state.get("output")

# --- The Graph Engine ---

class GraphExecutor:
    def __init__(self):
        self.results_cache: Dict[str, Any] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}

    async def resolve(self, node: Union['agent_config', 'function_config'], context: Dict[str, Any]):
        """
        Check if the node has already been resolved and return the result if it has. Otherwise, resolve the node
        """
        # 1. Check Cache (Dedup)
        if node.name in self.results_cache:
            return self.results_cache[node.name]

        # 2. Check if already running (handle diamond dependencies)
        if node.name in self.running_tasks:
            return await self.running_tasks[node.name]

        # 3. Create a task to execute this node
        task = asyncio.create_task(self._execute_node(node, context))
        self.running_tasks[node.name] = task
        
        try:
            result = await task
            self.results_cache[node.name] = result
            return result
        except Exception as e:
            del self.running_tasks[node.name]
            raise e
        
    async def _execute_node(self, node: Union['agent_config', 'function_config'], context: Dict[str, Any]):
        """
        Recursively resolves an agen node and its dependencies or a function node.
        """

        print(f"Executing logic for: {node.name}")

        # Execute the specific logic
        if isinstance(node, function_config):
            return await self._run_function(node, context)
        elif isinstance(node, agent_config):
            print(f"Resolving dependencies for: {node.name}")
        
            # Resolve Dependencies in Parallel
            dep_results_list = await asyncio.gather(
                *[self.resolve(dep, context) for dep in node.depends_on]
            )
        
            # Map results to names for easy access
            dep_results = {
                dep.name: res for dep, res in zip(node.depends_on, dep_results_list)
            }
            return await self._run_agent(node, context, dep_results)
        else:
            raise ValueError(f"Unknown node type: {type(node)}")

    async def _run_function(self, cfg: function_config, context: Dict):
        # Functions currently only use global context
        return call_function(cfg.function, context['team1'], context['team2'], context['game_date'])

    async def _run_agent(self, cfg: agent_config, context: Dict, dep_results: Dict):
        # 1. Determine which critic to use
        if cfg.name == "writer":
            critic_cfg = research_configs.writer_critic_agent
        else:
            critic_cfg = research_configs.research_critic_agent

        # 2. Construct the prompt
        base_prompt = f"Topic: {context['team1']} vs {context['team2']} on {context['game_date']}."
        current_date = datetime.datetime.now().strftime('%m/%d/%Y')

        if dep_results:
            dependency_context_str = "\n\n".join(
                [f"--- Input from {name} ---\n{content}" for name, content in dep_results.items()]
            )
            full_user_prompt = f"{base_prompt}\nToday's Date: {current_date}\n\nCONTEXT:\n{dependency_context_str}"
        else:
            full_user_prompt = f"{base_prompt}\nToday's Date: {current_date}"
        
        user_message = types.Content(role='user', parts=[types.Part.from_text(text=full_user_prompt)])

        # 3. Construct the Loop Agent
        worker_agent = Agent(
            name=cfg.name,
            model=cfg.model,
            instruction=create_instructions_provider(
                trigger_key="critique",
                trigger_found_instructions="Additional work required: {critique}",
                trigger_absent_instructions=cfg.system_prompt
            ),
            output_key="output",
            tools=cfg.tools
        )
        # The Critic
        critic_agent = Agent(
            name=f"{cfg.name}_critic",
            model=critic_cfg.model,
            instruction=f"Task instructions: {cfg.system_prompt}\n Your instructions: {critic_cfg.system_prompt}",
            output_key="critique",
            tools=critic_cfg.tools
        )
        # The Loop
        loop_agent = LoopAgent(
            name=f"{cfg.name}_loop",
            sub_agents=[worker_agent, critic_agent],
            max_iterations=3
        )
        # execute
        return await execute_agent(f"{cfg.name}_pipeline", loop_agent, user_message)

async def write_editorial(team1: str, team2: str, game_date: str) -> str:
    print(f"Starting Editorial Pipeline for {team1} vs {team2}")
    
    # 1. Define Global Context
    context = {"team1": team1, "team2": team2, "game_date": game_date}
    
    # 2. Initialize Executor
    executor = GraphExecutor()
    
    # 3. Run the Root Node (Writer)
    # The executor will automatically trace back and run all dependencies
    final_report = await executor.resolve(research_configs.writer_agent, context)
    
    print("Pipeline Complete.")
    return final_report