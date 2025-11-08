import asyncio
from typing import Dict
from server.openai_client import OpenAIClient
from . import team_form_agent, matchups_agent, injuries_agent, coaching_agent, schedule_agent, writer_agent

async def generate_research(mcp_session, tools, team1: str, team2: str, game_data: str) -> Dict[str, str]:
    """
    Run all research agents in parallel and aggregate their findings.
    Returns a dict mapping research domain to narrative findings.
    """

    # Create a shared lock for MCP tool calls
    shared_lock = asyncio.Lock()

    # Create a client for each research agent
    team_form_client = OpenAIClient(mcp_session, tools, shared_lock, team_form_agent.MODEL, team_form_agent.SYSTEM_PROMPT)
    matchups_client = OpenAIClient(mcp_session, tools, shared_lock, matchups_agent.MODEL, matchups_agent.SYSTEM_PROMPT)
    injuries_client = OpenAIClient(mcp_session, tools, shared_lock, injuries_agent.MODEL, injuries_agent.SYSTEM_PROMPT)
    coaching_client = OpenAIClient(mcp_session, tools, shared_lock, coaching_agent.MODEL, coaching_agent.SYSTEM_PROMPT)
    schedule_client = OpenAIClient(mcp_session, tools, shared_lock, schedule_agent.MODEL, schedule_agent.SYSTEM_PROMPT)

    # Create a research prompt:
    user_message = f"Research the matchup: {team1} vs {team2} on {game_date}."

    # Run all research agents in parallel
    team_form_task = team_form_client.get_completion([{"role": "user", "content": user_message}])
    matchups_task = matchups_client.get_completion([{"role": "user", "content": user_message}])
    injuries_task = injuries_client.get_completion([{"role": "user", "content": user_message}])
    coaching_task = coaching_client.get_completion([{"role": "user", "content": user_message}])
    schedule_task = schedule_client.get_completion([{"role": "user", "content": user_message}])

    # Wait for all to complete
    team_form_findings, matchups_findings, injuries_findings, coaching_findings, schedule_findings = await asyncio.gather(
        team_form_task, matchups_task, injuries_task, coaching_task, schedule_task
    )

    # Aggregate findings by domain
    return {
        "team_form": team_form_findings,
        "matchups": matchups_findings,
        "injuries": injuries_findings,
        "coaching": coaching_findings,
        "schedule": schedule_findings,
    }

async def write_editorial(mcp_session, tools, research_findings: Dict[str, str], team1: str, team2: str, game_date: str) -> str:
    """
    Take aggregated research findings and produce the final editorial report.
    """
    # Create writer client (doesn't need shared lock since it won't use tools)
    writer_client = OpenAIClient(mcp_session, tools, asyncio.Lock(), writer_agent.MODEL, writer_agent.SYSTEM_PROMPT)
    
    # Format research findings for the writer
    research_context = f"""
        MATCHUP: {team1} vs {team2} on {game_date}

        === TEAM FORM & EFFICIENCY RESEARCH ===
        {research_findings['team_form']}

        === KEY PLAYER MATCHUPS RESEARCH ===
        {research_findings['matchups']}

        === INJURIES & AVAILABILITY RESEARCH ===
        {research_findings['injuries']}

        === COACHING & TACTICS RESEARCH ===
        {research_findings['coaching']}

        === SCHEDULE & CONTEXT RESEARCH ===
        {research_findings['schedule']}

        ===

        Using the research above, write your compelling match preview article.
        """
    
    # Generate the editorial
    return await writer_client.get_completion([{"role": "user", "content": research_context}])