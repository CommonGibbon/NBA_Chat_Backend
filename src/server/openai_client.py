import os
import json
from typing import List, Dict
from openai import OpenAI
from nba_mcp_server.mcp_server import ToolCategory

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
        # we bin tools by category as a lazy-loading/hierarchical loading mechanism. This will reduce context bloat.
        self.mcp_tools_by_category = {}
        for tool in mcp_tools:
            categories = tool.meta.get("category", []) if hasattr(tool, "meta") and tool.meta else []
            for cat in categories:
                if cat not in ToolCategory:
                    continue # skip minor categories; we're just using the major sorting categories for now 
                if cat not in self.mcp_tools_by_category:
                    self.mcp_tools_by_category[cat] = []
                self.mcp_tools_by_category[cat].append(tool)
        # convert tools to openai's specific formatting
        for category, tools in self.mcp_tools_by_category.items():
            self.mcp_tools_by_category[category] = mcp_tools_to_openai_tools(tools)

    def get_tool_subset(self, categories: List[str]):
        seen = set()
        new_tools = []
        for category in categories:
            for tool in self.mcp_tools_by_category[category]:
                if tool["function"]["name"] not in seen:
                    new_tools.append(tool)
                    seen.add(tool["function"]["name"])
        return new_tools
    
    async def get_completion(self, messages: List[Dict[str, str]]) -> str:
        """Get OpenAI completion for message history."""
        full_messages = [{"role": "system", "content": self.SYSTEM_PROMPT}] + messages # attach full message history whenever we send a new message
        current_tools = self.mcp_tools_by_category["base"] # the LLM starts off with access to just the basic tools
        # the loop below is a tool-calling loop. Basically we just keep calling the API until it's done calling tools. The final response 
        # represents its aggregated knowledge from the tool calls.
        while True:
            try:
                response = self.client.chat.completions.create(
                    model="openai/gpt-5-mini",
                    messages=full_messages,
                    tools=current_tools
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
                    # we treat get_tools_by_category uniquely. Rather than returning a message to the LLM, we just updated the 
                    # set of current_tools we're supplying to the LLM. 
                    if fn == "get_tools_by_category": 
                        categories = json.loads(json.dumps(payload)).get("result", [])
                        current_tools = self.get_tool_subset(categories)
                    else: # its a normal tool call, just append the result to the full_message 
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
