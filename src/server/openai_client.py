import anyio
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
    def __init__(self, mcp_sessions, nba_tools, persistent_tools, mcp_lock, model: str, system_prompt: str):
        self.mcp_session = mcp_sessions
        self.mcp_lock = mcp_lock
        self.model = model
        self.system_prompt = system_prompt
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            timeout=90.0
        )

        # since we have multiple mcp sessions, we need to map each tool to its respective session. This way, when the ai
        # selects a tool, we can determine which mcp session to run it through.
        self.tool_to_session = {}
        for tool in nba_tools:
            self.tool_to_session[tool.name] = "nba"
        for tool in persistent_tools:
            self.tool_to_session[tool.name] = "perplexity"

        self.persistent_tools_openai = mcp_tools_to_openai_tools(persistent_tools)
        # we bin tools by category as a lazy-loading/hierarchical loading mechanism. This will reduce context bloat.
        self.nba_tools_by_category = {}
        for tool in nba_tools:
            categories = tool.meta.get("category", []) if hasattr(tool, "meta") and tool.meta else []
            for cat in categories:
                if cat not in ToolCategory:
                    continue # skip minor categories; we're just using the major sorting categories for now 
                if cat not in self.nba_tools_by_category:
                    self.nba_tools_by_category[cat] = []
                self.nba_tools_by_category[cat].append(tool)
        # convert tools to openai's specific formatting
        for category, tools in self.nba_tools_by_category.items():
            self.nba_tools_by_category[category] = mcp_tools_to_openai_tools(tools)

    def get_tool_subset(self, categories: List[str]):
        seen = set()
        new_tools = []
        for category in categories:
            for tool in self.nba_tools_by_category[category]:
                if tool["function"]["name"] not in seen:
                    new_tools.append(tool)
                    seen.add(tool["function"]["name"])
        return new_tools
    
    async def get_completion(self, messages: List[Dict[str, str]]) -> str:
        """Get OpenAI completion for message history."""
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages # attach full message history whenever we send a new message
        current_tools = self.nba_tools_by_category["base"] + self.persistent_tools_openai # the LLM starts off with access to just the basic tools
        # the loop below is a tool-calling loop. Basically we just keep calling the API until it's done calling tools. The final response 
        # represents its aggregated knowledge from the tool calls.
        while True:
            try:
                response = await anyio.to_thread.run_sync(
                    lambda: self.client.chat.completions.create(
                        model=self.model,
                        messages=full_messages,
                        tools=current_tools
                    )
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
                    
                    async with self.mcp_lock:
                        session_name = self.tool_to_session[fn]
                        session = self.mcp_session[session_name]
                        result = await session.call_tool(fn, args)

                    payload = result.structuredContent or {
                            "result": "\n".join(
                                c.text for c in result.content if getattr(c, "text", None)
                            )
                        }
                    # we treat get_tools_by_category uniquely. Rather than returning a message to the LLM, we just updated the 
                    # set of current_tools we're supplying to the LLM. 
                    if fn == "get_tools_by_category": 
                        categories = json.loads(json.dumps(payload)).get("result", [])
                        current_tools = self.get_tool_subset(categories) + self.persistent_tools_openai
                        full_messages.append({"role": "tool", "tool_call_id": call.id, "content": "Updated tool set."})
                    else: # its a normal tool call, just append the result to the full_message 
                        full_messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(payload)})
                
                continue # the tool message has just been appended, and now the AI needs to process it, so we continue 
            
            break # no more tool calls means the AI is done processing
        
        return msg.content
