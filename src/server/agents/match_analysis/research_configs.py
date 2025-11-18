# Research configs are built to collect data either through api calls or google seaches. They do not perform any data reduction, summarization, or analysis.
from .models import agent_config, llm_action, function_config
from .data_preprocessing import get_team_performance, get_player_performance, get_matchup_history
from google.genai import types
from google.adk.tools import google_search
from google.adk.models.google_llm import Gemini

# calls to api can error out for various reasons, such as rate limiting
retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

REVIEW_SYSTEM_PROMPT="""
    Your job is to review the original assigned task and assess whether the research is complete, or if further investigation is needed.
    - If the research is complete, you MUST call the exit_loop function to indicate that no further research is needed.
    - Otherwise, provide specific, actionable suggestions for improvement.
    """
REVIEW_MODEL = Gemini(model="gemini-2.5-flash", retry_options=retry_config)

ORGANIZER_SYSTEM_PROMPT="""
    You will receive a set of research instructions and a set of research results. Your job is to filter out irrelevant information and 
    pair the instruction goals with the corresponding data and references. 
    """
ORGANIZER_MODEL = Gemini(model="gemini-2.5-flash", retry_options=retry_config)

agent_configs = [
    agent_config(
        name = "inactive_players",
        model = Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        setup_actions=[],
        llm_actions=[
            llm_action(
                system_prompt="""
                    Task:
                    For each team, check whether any prominent players are inactive for any reason (such as due to injury, illness, suspension, etc.)
                    Current status (OUT/DOUBTFUL/QUESTIONABLE/PROBABLE/ACTIVE) with reasons

                    You will have access to a web search tool to complete this task. Call it as many times as you need.

                    Return JSON only.

                    Schema:
                    {
                    "last_updated": "ISO8601",
                    "report": [
                        {"player": "string", "team": "string", "status": "OUT|DOUBTFUL|QUESTIONABLE|PROBABLE|ACTIVE", "reason": "string", "updated": "ISO8601"}
                    ],
                    }
                    """, 
                tools=[google_search]
            )
        ]
    ),
    agent_config(
        name = "odds",
        model = Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        setup_actions=[],
        llm_actions=[
            llm_action(
                system_prompt="""
                    Task:
                    For the specified team matchup, check the current sports betting odds/probabilities. Report your best estimate for the outcome of the game. 
                    User sources like Las Vegas odds, Polymarket, or other sportsbooks.

                    You will have access to a web search tool to complete this task. Call it as many times as you need.
                    """, 
                tools=[google_search])
        ]
    ), 
    agent_config(
        name = "rivalry",
        model = Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        setup_actions=[get_matchup_history],
        llm_actions=[
            llm_action(
                system_prompt="""
                    Task:
                    You are a Rivalry Researcher focused on NBA drama and competitive storylines. Your job is to uncover narrative tension between two teams that fans can follow during the game.

                    Research Focus:
                    - Player rivalries (trash talk, social media, head-to-head battles)
                    - Team conflicts (playoff history, coaching disputes, recent controversies)
                    - Competitive angles (statistical races, award battles, revenge narratives)
                    - Emerging storylines (players vs former teams, rookie vs veteran matchups)

                    For each drama point found, provide:
                    1. The conflict/hook
                    2. Why fans should care  
                    3. What to watch during the game
                    4. Recent context

                    Keep it concise, lead with the most compelling storylines, and focus on actionable drama - things fans can actually see unfold during the game. 
                    You're finding the emotional subtext that makes every possession more interesting.
                    """, 
                tools=[google_search])
        ]
    ), 
]

function_configs = [
    function_config(
        name= "team_performance", 
        function=get_team_performance
    ),
    function_config(
        name= "player_performance", 
        function=get_player_performance
    ),
]
