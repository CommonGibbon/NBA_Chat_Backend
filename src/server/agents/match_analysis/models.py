from typing import List

class agent_config():
    def __init__(self, name, model, setup_actions, llm_actions):
        self.name = name
        self.model = model
        self.setup_actions = setup_actions # function calls which pull target data and feed it into the LLM
        self.llm_actions = llm_actions

class llm_action():
    def __init__(self, system_prompt: str, tools: List[str] = []):
        self.system_prompt = system_prompt
        self.tools = tools

class function_config():
    def __init__(self, name: str, function: callable):
        self.name = name
        self.function = function
