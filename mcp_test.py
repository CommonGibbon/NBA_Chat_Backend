from openai import OpenAI  # OpenAI SDK pointed at OpenRouter base_url
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
import asyncio
import os
import json
from dotenv import load_dotenv
import sys
from pathlib import Path

load_dotenv()

def mcp_tools_to_openai_tools(mcp_tools):
    # Convert MCP Tool[] -> OpenAI tools[] (function) schema
    tools = []
    for t in mcp_tools:
        tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema or { "type": "object", "properties": {} }
            }
        })
    return tools

async def run():
    # 1) Start MCP server via stdio
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nba_chat_mcp_server.mcp_server"],  # adjust if needed
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as mcp:
            await mcp.initialize()

            # 2) Discover tools
            tool_list = await mcp.list_tools()
            openai_tools = mcp_tools_to_openai_tools(tool_list.tools)

            # 3) Prepare OpenRouter client
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ["OPENROUTER_API_KEY"],
            )

            messages = [
                {"role": "system", "content": "You are a helpful NBA assistant."},
                {"role": "user", "content": "Show me Steph Curry's season-by-season points per game."},
            ]

            while True:
                # 4) Send chat with tools
                try:
                    resp = client.chat.completions.create(
                        model="openai/gpt-5-mini",  # any model supporting tool calling
                        messages=messages,
                        tools=openai_tools,
                    )
                except Exception as e:
                    # Surface the actual API error so we can iterate if needed
                    print("OpenRouter error:", repr(e))
                    raise
                msg = resp.choices[0].message

                messages.append(msg.model_dump())

                # 5) If tool calls, execute them via MCP and loop
                if getattr(msg, "tool_calls", None):
                    for call in msg.tool_calls:
                        fn = call.function.name
                        args = json.loads(call.function.arguments or "{}")

                        # Call MCP tool
                        result = await mcp.call_tool(fn, args)

                        # Prefer structuredContent if present; else join text content
                        payload = result.structuredContent or {
                            "result": "\n".join(
                                c.text for c in result.content if getattr(c, "text", None)
                            )
                        }

                        # Append tool result
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(payload),
                        })

                    # Continue the loop for model to consume tool results
                    continue

                # 6) No tool_calls => final answer
                break

            print(messages[-1]["content"])


if __name__ == "__main__":
    asyncio.run(run())