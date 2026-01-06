# NBAChat Backend

A self-hosted NBA-focused conversational AI backend that powers an iOS mobile app. Features real-time chat via WebSockets, persistent conversation history, and AI-powered match analysis reports.

## Features

- **AI Chat Assistant** - NBA-focused conversational AI powered by OpenAI with MCP tool integration
- **Match Analysis Reports** - Automated editorial-style game analysis using multi-agent orchestration
- **Real-time WebSockets** - Live message updates for connected clients
- **NBA Data via MCP** - Extensive NBA statistics through a custom MCP server wrapping the `nba-api`
- **Perplexity Integration** - Web search capabilities for up-to-date information

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   iOS Client    │────▶│   FastAPI       │────▶│   PostgreSQL    │
└─────────────────┘     │   Server        │     └─────────────────┘
                        │                 │
                        │   ┌─────────────┴─────────────┐
                        │   │     MCP Servers           │
                        │   ├─────────────┬─────────────┤
                        │   │ NBA Stats   │ Perplexity  │
                        │   └─────────────┴─────────────┘
                        │                 │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │    OpenAI API   │
                        └─────────────────┘
```

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL + SQLAlchemy
- **AI**: OpenAI API, Google ADK
- **Tools**: MCP (Model Context Protocol), nba-api, Perplexity
- **Language**: Python 3.12+
- **Package Manager**: Poetry

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/users/me` | Get current user (requires API key) |
| `POST` | `/chat` | Send message, get AI response |
| `GET` | `/chats` | List all chats |
| `GET` | `/chats/{chat_id}/messages` | Get chat history |
| `WS` | `/ws/chats/{chat_id}` | WebSocket for real-time updates |
| `POST` | `/reports/match-analysis` | Generate match analysis report |
| `GET` | `/reports/match-analysis` | List all reports |
| `GET` | `/reports/match-analysis/{report_id}` | Get specific report |
| `GET` | `/reports/match-analysis/{report_id}/chats` | Get chats linked to a report |

## Project Structure

```
src/
├── server/
│   ├── main.py              # FastAPI app, routes, lifespan
│   ├── openai_client.py     # OpenAI API wrapper
│   ├── connection_manager.py # WebSocket connection handling
│   ├── agents/
│   │   ├── chat_agent.py    # Chat agent config
│   │   └── match_analysis/  # Multi-agent match analysis
│   └── db/
│       ├── connection.py    # Database connection
│       ├── models.py        # SQLAlchemy models
│       ├── helpers.py       # Database operations
│       └── schema.sql       # Database schema
└── nba_mcp_server/
    └── mcp_server.py        # NBA statistics MCP server
```

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL
- Poetry

### Installation

```bash
# Clone the repository
git clone https://github.com/CommonGibbon/NBA_Chat_Backend.git
cd NBA_Chat_Backend

# Install dependencies
poetry install

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Environment Variables

```
DATABASE_URL=postgresql://user:pass@localhost:5432/nbachat
GOOGLE_API_KEY=your-openai-key
PERPLEXITY_API_KEY=your-perplexity-key
```

### Running

```bash
# Activate virtual environment
poetry shell

# Run the server
uvicorn server.main:app --reload
```

## MCP Server

The NBA MCP server exposes 50+ tools for querying NBA statistics, including:

- Player stats, awards, game logs, shot charts
- Team info, rosters, game logs
- League leaders, standings, scoreboard
- Box scores, play-by-play data
- Draft history, playoff picture

Tools are organized by category: `player`, `team`, `league`, `game`, `boxscore`, `draft`, `franchise`, `playoff`, `season`.

## Data Models

- **Chat** - Conversation container with UUID and optional report link
- **Message** - User/assistant/system messages with timestamps
- **User** - API key authenticated users
- **MatchAnalysisReport** - AI-generated game analysis content

## Status

Work in progress. Core chat and match analysis features are implemented.
