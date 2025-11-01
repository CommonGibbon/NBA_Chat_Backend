from fastapi import FastAPI, HTTPException
from server.db.connection import engine
from server.db.helpers import get_all_chat_ids, get_chat_messages
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from server.openai_client import OpenAIClient
import sys


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify database connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection verified")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        raise
    
    # Start MCP server and initialize session
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nba_mcp_server.mcp_server"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()
            print("✓ MCP server initialized")
            
            tool_list = await mcp_session.list_tools()
            openai_client = OpenAIClient(mcp_session, tool_list.tools)
            print("✓ OpenAI client initialized")
            
            app.state.mcp_session = mcp_session
            app.state.openai_client = openai_client
            
            yield # server runs here
    
    # MCP cleanup happens automatically when exiting the context managers
    print("✓ MCP server shutdown")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your iOS app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/chats")
def list_chats():
    chat_ids = get_all_chat_ids()
    return {"chats": chat_ids}

@app.get("/chats/{chat_id}/messages")
def get_messages(chat_id: str):
    messages = get_chat_messages(chat_id)
    
    if not messages:
        all_chats = get_all_chat_ids()
        if chat_id not in all_chats:
            raise HTTPException(status_code=404, detail="Chat not found")
    
    return {"chat_id": chat_id, "messages": messages}
