import os
import json
from typing import List, Dict
from openai import OpenAI

def mcp_tools_to_openai_tools(mcp_tools):
    """Convert MCP Tool[] -> OpenAI tools[] (function) schema."""
    tools = []
    for t in mcp_tools:
        tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema or {"type": "object", "properties": {}}
            }
        })
    return tools


class OpenAIClient:
    def __init__(self, mcp_session, mcp_tools):
        self.mcp_session = mcp_session
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY")
        )
        self.SYSTEM_PROMPT = "You are a helpful NBA assistant."
        self.tools = mcp_tools_to_openai_tools(mcp_tools) # OpenAI has a specific format for tool definitions, which it provides to its models
    
    async def get_completion(self, messages: List[Dict[str, str]]) -> str:
        """Get OpenAI completion for message history."""
        full_messages = [{"role": "system", "content": self.SYSTEM_PROMPT}] + messages # attach full message history whenever we send a new message
        # the loop below is a tool-calling loop. Basically we just keep calling the API until it's done calling tools. The final response 
        # represents its aggregated knowledge from the tool calls.
        while True:
            try:
                response = self.client.chat.completions.create(
                    model="openai/gpt-5-mini",
                    messages=full_messages,
                    tools=self.tools
                )
            except Exception as e:
                print("OpenRouter error:", repr(e))
                raise
            
            msg = response.choices[0].message
             # note that this is just appending to the internal message loop; we don't touch the database message history here
            full_messages.append(msg.model_dump())
            
            if getattr(msg, "tool_calls", None): # if there are tool calls, send them to the MCP server for execution.
                for call in msg.tool_calls:
                    fn = call.function.name
                    args = json.loads(call.function.arguments or "{}")
                    
                    result = await self.mcp_session.call_tool(fn, args)
                    
                    payload = result.structuredContent or {
                        "result": "\n".join(
                            c.text for c in result.content if getattr(c, "text", None)
                        )
                    }
                    
                    full_messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(payload)
                    })
                
                continue # the tool message has just been appended, and now the AI needs to process it, so we continue 
            
            break # no more tool calls means the AI is done processing
        
        return msg.content
