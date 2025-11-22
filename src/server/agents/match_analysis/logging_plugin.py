from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from google.genai import types
import os
import datetime
import json
from typing import Any, Optional

class NodeLoggingPlugin(BasePlugin):
    """
    Logs all agent activity (prompts, tool calls, stream events) to a node-specific file.
    """
    def __init__(self, log_path: str):
        super().__init__(name="node_logger")
        self.log_path = log_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self._log("--- Node Execution Started ---")

    def _log(self, event_type: str, data: Any = ""):
        timestamp = datetime.datetime.now().isoformat()
        entry = f"[{timestamp}] [{event_type}]\n{str(data)}\n{'-'*40}\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    async def before_model_callback(self, *, callback_context: CallbackContext, llm_request: LlmRequest) -> None:
        # Log the exact prompt sent to the model
        prompt_text = "\n".join([  
            p.text   
            for content in llm_request.contents   
            for p in content.parts   
            if p.text  
        ])
        self._log(f"{callback_context.agent_name}_PROMPT", prompt_text)

    async def on_event_callback(self, *, invocation_context, event) -> Optional[Any]:
        # Log streaming content as it arrives
        if event.content and event.content.parts:
            text = "".join([p.text for p in event.content.parts if p.text])
            if text:
                self._log(f"{invocation_context.agent.name}_RESPONSE", text)
        return event

    async def before_tool_callback(self, *, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext) -> None:
        self._log(f"TOOL_CALL: {tool.name}", json.dumps(tool_args, indent=2))

    async def after_tool_callback(self, *, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext, result: Any) -> None:
        self._log(f"TOOL_RESULT: {tool.name}", str(result))

    async def on_model_error_callback(self, *, callback_context: CallbackContext, llm_request: LlmRequest, error: Exception) -> None:
         self._log("ERROR", str(error))