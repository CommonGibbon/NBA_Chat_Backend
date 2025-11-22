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
from .logging_plugin import NodeLoggingPlugin
import os
from .log_context import active_log_path, log_to_active_node

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

async def execute_agent(app_name, agent, user_message, log_path: str = None):
    plugins = [NodeLoggingPlugin(log_path)] if log_path else []
    
    # create the runner + session
    runner = InMemoryRunner(agent=agent, app_name=app_name, plugins=plugins)
    session = await runner.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        state={"critique": ""}
    )

    results = [] # I don't need to collect these results, I don't think, but run_async requires that I do.
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
        # Create a unique timestamped folder for this entire run
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_log_dir = f"logs/run_{timestamp}"
        os.makedirs(self.run_log_dir, exist_ok=True)

    def _get_log_path(self, node_name: str) -> str:
        return os.path.join(self.run_log_dir, f"{node_name}.log")

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
        # Log path for this specific node
        log_path = self._get_log_path(node.name)

        # Set the context variable token so we can reset it later
        token = active_log_path.set(log_path)

        try:
            # Initialize the log file
            log_to_active_node(f"\n--- START NODE: {node.name} ---\nContext keys: {list(context.keys())}")
            # Execute the specific logic
            if isinstance(node, function_config):
                try:
                    # When this function runs, any inner function using log_context 
                    # will auto-write to 'log_path'
                    result = await self._run_function(node, context)
                    
                    log_to_active_node(f"\n--- SUCCESS ---\n")
                    return result
                except Exception as e:
                    log_to_active_node(f"\n--- FATAL ERROR ---\n{str(e)}")
                    raise e
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
                return await self._run_agent(node, context, dep_results, log_path)
            else:
                raise ValueError(f"Unknown node type: {type(node)}")
        finally:
            # Reset context var to avoid leaking state between async tasks
            active_log_path.reset(token)

    async def _run_function(self, cfg: function_config, context: Dict):
        # Functions currently only use global context
        return call_function(cfg.function, context['team1'], context['team2'], context['game_date'])

    async def _run_agent(self, cfg: agent_config, context: Dict, dep_results: Dict, log_path: str):
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
            instruction=cfg.system_prompt,
            #create_instructions_provider(
            #    trigger_key="critique",
            #    trigger_found_instructions="Additional work required: {critique}",
            #    trigger_absent_instructions=cfg.system_prompt
            #),
            output_key="output",
            tools=cfg.tools
        )
        # The Critic
        critic_agent = Agent(
            name=f"{cfg.name}_critic",
            model=critic_cfg.model,
            instruction=f"Task instructions: {cfg.system_prompt}\n Your instructions: {critic_cfg.system_prompt}",
            output_key="critique",
            tools=critic_cfg.tools,
            include_contents='none' # the critic agents receive content via the output_key from the worker agents, so there is no need to include the entire chat history.
        )
        # The Loop
        loop_agent = LoopAgent(
            name=f"{cfg.name}_loop",
            sub_agents=[worker_agent, critic_agent],
            max_iterations=3
        )
        # execute
        return await execute_agent(f"{cfg.name}_pipeline", loop_agent, user_message, log_path)

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