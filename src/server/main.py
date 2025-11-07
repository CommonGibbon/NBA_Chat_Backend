from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Header, Depends
from server.connection_manager import ConnectionManager
from server.db.connection import engine
from server.db.helpers import get_all_chat_ids, get_chat_messages, create_chat, chat_exists, insert_message, get_user_by_api_key, create_match_analysis_report, get_match_analysis_report, get_all_match_analysis_reports, get_chat, get_chats_by_report
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from server.openai_client import OpenAIClient
from server.agents import chat_agent, match_analysis_agent
import sys
from pydantic import BaseModel
from typing import Optional
import asyncio
from datetime import datetime

class ChatRequest(BaseModel):
    chat_id: Optional[str] = None
    message: str
    report_id: Optional[str] = None

class MatchAnalysisRequest(BaseModel):
    team1: str
    team2: str
    game_date: str  # ISO format YYYY-MM-DD

async def get_current_user(x_api_key: str = Header(...)):
    print(f"Received API key: {x_api_key}")
    user = get_user_by_api_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user

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
            mcp_lock = asyncio.Lock()
            chat_client = OpenAIClient(mcp_session, tool_list.tools, mcp_lock, chat_agent.MODEL, chat_agent.SYSTEM_PROMPT)
            print("✓ OpenAI client initialized")
            connection_manager = ConnectionManager()
            print("✓ Connection manager initialized")
            
            app.state.mcp_session = mcp_session
            app.state.chat_client = chat_client
            app.state.connection_manager = connection_manager
            
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

@app.get("/users/me")
def get_me(user: dict = Depends(get_current_user)):
    return user

@app.get("/chats")
def list_chats():
    chat_ids = get_all_chat_ids()
    return {"chat_ids": chat_ids}

@app.get("/chats/{chat_id}/messages")
def get_messages(chat_id: str):
    messages = get_chat_messages(chat_id)
    
    if not messages:
        all_chats = get_all_chat_ids()
        if chat_id not in all_chats:
            raise HTTPException(status_code=404, detail="Chat not found")
    
    return {"chat_id": chat_id, "messages": messages}

@app.websocket("/ws/chats/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    """
    Clients can subscribe to chat_id websockets using this endpoint. We will maintain the connection so long as we receive ping updates from the client.
    """
    await websocket.accept()
    await app.state.connection_manager.connect(chat_id, websocket)

    try:
        # Keep connection alive, send ping periodically
        while True:
            # wait for client messages (we ignore them, just keep connection alive)
            await websocket.receive_text()
    except WebSocketDisconnect:
        await app.state.connection_manager.disconnect(chat_id, websocket)

async def generate_assistant_reply(chat_id: str, chat_client, connection_manager):
    """Background task to generate assistant reply."""
    try:
        # Get chat metadata (includes report_id)
        chat = get_chat(chat_id)

        # Get full message history
        messages = get_chat_messages(chat_id)
        history = [{"role": msg["role"], "content": msg["content"]} for msg in messages] 

        # If chat is linked to a report, prepend report as system context
        if chat and chat['report_id']:
            report = get_match_analysis_report(chat['report_id'])
            if report:
                history = [
                    {"role": "system", "content": f"You're discussing this match analysis:\n\n{report['content']}"},
                    *history
                ]

        # generate a response from the assistant
        assistant_reply = await app.state.chat_client.get_completion(history)

        # insert the assistant message into the chat history
        insert_message(chat_id, "assistant", assistant_reply, None)

        # Get the assistant message we just inserted
        messages = get_chat_messages(chat_id)
        assistant_msg = messages[-1]
        
        # Push message_created event for assistant message
        await connection_manager.send_to_chat(chat_id, {
            "type": "message_created",
            "chat_id": chat_id,
            "message": {
                "role": assistant_msg["role"],
                "content": assistant_msg["content"],
                "id": str(assistant_msg["id"]),
                "created_at": assistant_msg["created_at"].isoformat()
            }
        })
    except Exception as e:
        print(f"Error generating assistant reply for chat {chat_id}: {e}")


@app.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    # when a chat request is made, it might not have a chat_id yet, so we need to create one
    chat_id = request.chat_id
    if not chat_id or not chat_exists(chat_id):
        chat_id = create_chat(report_id=request.report_id)

    # insert the user's message into the chat db
    insert_message(chat_id, "user", request.message, user_id=user["id"])

    # get the user message we just inserted so we can build a payload to send back to the client
    # this may be silly, but for simplicities sake, I'm treating the background as the string one source of truth, which means the 
    # clients don't do anything without the backend's say-so.
    messages = get_chat_messages(chat_id)
    user_msg = messages[-1]

    # Push message_created event for user message
    await app.state.connection_manager.send_to_chat(chat_id, {
        "type": "message_created",
        "chat_id": chat_id,
        "message": {
            "role": user_msg["role"],
            "content": user_msg["content"],
            "id": str(user_msg["id"]),
            "created_at": user_msg["created_at"].isoformat(),
            "username": user["username"]
        }
    })

    # Queue background task for assistant reply, this will send its own update via the connection manager once it completes.
    background_tasks.add_task(generate_assistant_reply, chat_id, app.state.chat_client, app.state.connection_manager)
    return {"chat_id": chat_id, "queued": True}

@app.get("/reports/match-analysis/{report_id}/chats")
def get_report_chats(report_id: str):
    """Get all chats associated with a specific report."""
    chats = get_chats_by_report(report_id)
    return {"report_id": report_id, "chats": chats}

@app.get("/reports/match-analysis")
def list_reports():
    """List all match analysis reports."""
    reports = get_all_match_analysis_reports()
    return {"reports": reports}

@app.get("/reports/match-analysis/{report_id}")
def get_report(report_id: str):
    """Get a specific match analysis report."""
    report = get_match_analysis_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@app.post("/reports/match-analysis")
async def generate_match_analysis(request: MatchAnalysisRequest, background_tasks: BackgroundTasks):
    """Generate a match analysis report for an upcoming game."""
    # Create matchup agent; since this is a one-off request, we don't need to worry about the agent's state
    matchup_client = OpenAIClient(
        app.state.mcp_session,
        (await app.state.mcp_session.list_tools()).tools,
        asyncio.Lock(),
        match_analysis_agent.MODEL,
        match_analysis_agent.SYSTEM_PROMPT
    )
    
    # Generate the report
    initial_message = f"""Your task is to generate a comprehensive matchup analysis for the upcoming game 
                        {request.team1} vs {request.team2} on {request.game_date}. 
                        Todays date is {datetime.now().strftime('%Y-%m-%d')}.
                        """
    report_content = await matchup_client.get_completion([{"role": "user", "content": initial_message}])
    
    # Save to database
    report_id = create_match_analysis_report(
        team1=request.team1,
        team2=request.team2,
        game_date=request.game_date,
        content=report_content
    )
    
    return {"report_id": report_id, "status": "completed"}