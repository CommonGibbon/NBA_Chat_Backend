class agent_config():
    def __init__(self, name, system_prompt, allowed_tools = []):
        self.name = name
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools
