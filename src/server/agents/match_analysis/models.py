from typing import List, Any, Callable, Union

class agent_config:
    def __init__(self, 
                 name: str, 
                 model: Any, 
                 system_prompt: str, 
                 tools: List[Any] = None, 
                 depends_on: List[Union['agent_config', 'function_config']] = None):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools if tools is not None else []
        self.depends_on = depends_on if depends_on is not None else []

class function_config():
    def __init__(self, name: str, function: Callable):
        self.name = name
        self.function = function

