from .models import agent_config
from google.genai import types
from google.adk.models.google_llm import Gemini

API_SYSTEM_PROMPT="""
    You will have access to a vast set of NBA api tools which give you access detailed data about players,
    teams, and matches. Use these tools to collect data that will help you answer the research checklist items.
    """
SEARCH_SYSTEM_PROMPT="""
    You will have access to a search engine tool and your job is to answer the questions your predecessor was unable to
    by searching the web. 
    """
REVIEW_SYSTEM_PROMPT="""
    Your job is to review the original task and assess whether the research is complete, or if further investigation is needed.
    - If the research is complete, you MUST call the exit_loop function to indicate that no further research is needed.
    - Otherwise, provide 2-3 specific, actionable suggestions for improvement.
    """
ORGANIZER_SYSTEM_PROMPT="""
    You will receive a set of research instructions and a set of research results. Your job is to filter out irrelevant information and 
    pair the instruction goals with the corresponding data and references. 
    """


# calls to api can error out for various reasons, such as rate limiting
retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

MODEL=Gemini(model="gemini-2.5-flash", retry_options=retry_config)

agent_configs = [
    agent_config(
        "injuries",
        """
        - Current status (OUT/DOUBTFUL/QUESTIONABLE/PROBABLE/ACTIVE) with reasons; load management; rest back-to-backs.
        - Return timelines; minutes restrictions for recent returners.
        - On/off impact for key players (team net per 100), with sample sizes and date ranges.
        - Likely rotation changes: list factual coach reports/beat confirmations only (no inference).

        If you are unable to uncover some of the target information, document the missing data in the issues section for handoff to a
        collaborator with web-search capabilities.

        Return JSON only.

        Schema:
        {
        "last_updated": "ISO8601",
        "report": [
            {"player": "string", "status": "OUT|DOUBTFUL|QUESTIONABLE|PROBABLE|ACTIVE", "reason": "string", "updated": "ISO8601", "source": "url"}
        ],
        "rest_flags": [
            {"player": "string", "context": "B2B|3in4|4in6|travel", "note": "string", "source": "url"}
        ],
        "minutes_caps": [
            {"player": "string", "cap_minutes": number, "cap_type": "hard|soft|ramp-up", "updated": "ISO8601", "source": "url"}
        ],
        "return_timelines": [
            {"player": "string", "timeline": "string", "updated": "ISO8601", "source": "url"}
        ],
        "on_off": [
            {"player": "string", "on_net": number, "off_net": number, "diff": number, "units": "points_per_100", "sample_size_minutes": number, "date_range": "string", "source": "url"}
        ],
        "rotation_notes": [
            {"note": "string (factual report/quote)", "updated": "ISO8601", "source": "url"}
        ],
        "sources": ["url", "..."],
        "issues": ["string", "..."]
        }
        """,
        [
            'get_player_info',
            'get_team_roster',
            'get_schedule',
            'get_league_game_finder',
            'get_player_game_log',
            'get_league_dash_player_stats',
            'get_league_dash_team_stats'
        ]
    ),
    agent_config(
        "odds",
        """
        Tasks:
        - Collect open and current spread, total, moneylines across 3–5 sportsbooks; compute implied win probabilities (vig-inclusive and no-vig).
        - Line movement timeline with timestamps and catalysts (if reported).
        - Handle/ticket splits (if available) and any book discrepancies; alt lines of interest (spread/total).
        - Record injury/news events that align with moves (link to sources).

        If you are unable to uncover some of the target information, document the missing data in the issues section for handoff to a
        collaborator with web-search capabilities.

        Return JSON only.

        Schema:
        {
        "last_updated": "ISO8601",
        "books": [
            {
            "book": "string",
            "open": {"spread": "home -x/away +x", "total": number, "ml_home": number, "ml_away": number, "ts": "ISO8601"},
            "current": {"spread": "home -x/away +x", "total": number, "ml_home": number, "ml_away": number, "ts": "ISO8601"}
            }
        ],
        "consensus": {
            "spread": "string",
            "total": number,
            "ml_home": number,
            "ml_away": number,
            "method": "median|mean|majority",
            "sample_size_books": number
        },
        "implied_prob": {
            "home_vig": number,
            "away_vig": number,
            "home_no_vig": number,
            "away_no_vig": number,
            "calc_method": "kelly|proportional|standard",
            "units": "probability_0to1"
        },
        "movement": [
            {"ts": "ISO8601", "field": "spread|total|ml_home|ml_away", "from": number|string, "to": number|string, "catalyst": "string|null", "source": "url"}
        ],
        "splits": [
            {"book": "string", "home_pct_bets": number|null, "home_pct_handle": number|null, "ts": "ISO8601", "source": "url"}
        ],
        "alt_lines": [
            {"type": "spread|total", "line": number|string, "home_price": number|null, "away_price": number|null, "book": "string", "ts": "ISO8601"}
        ],
        "linked_events": [
            {"ts": "ISO8601", "event": "injury/news", "summary": "string", "source": "url"}
        ],
        "sources": ["url", "..."],
        "issues": ["string", "..."]
        }        
        """,
        []
    ),
    agent_config(
        "starting_five",
        """
        Role: Lineup Units (data only).

        Tasks:
        - Projected starting fives from official/beat sources.
        - If prior H2H unit minutes exist: minutes, possessions, offensive/defensive ratings both sides, net ratings.
        - If small sample: provide closest proxies (4-of-5 overlap), plus star-vs-star possession estimates if published.
        - Mark sample_warning when minutes/possessions are low.

        If you are unable to uncover some of the target information, document the missing data in the issues section for handoff to a
        collaborator with web-search capabilities.

        Return JSON only.

        Schema:
        {
        "last_updated": "ISO8601",
        "proj_starting": {"home": ["G","G","F","F","C"], "away": ["G","G","F","F","C"], "source": "url"},
        "h2h_units": {
            "minutes": number|null,
            "possessions": number|null,
            "home_off_rt": number|null,
            "away_off_rt": number|null,
            "home_def_rt": number|null,
            "away_def_rt": number|null,
            "net_rt_home": number|null,
            "net_rt_away": number|null,
            "units": "points_per_100",
            "sample_warning": boolean,
            "date_range": "string",
            "source": "url"
        },
        "proxies": [
            {"desc": "string", "minutes": number, "possessions": number, "net_rt_home": number|null, "net_rt_away": number|null, "units": "points_per_100", "source": "url"}
        ],
        "star_on_star": [
            {"matchup": "Player A vs Player B", "possessions": number|null, "points_per_poss": number|null, "source": "url"}
        ],
        "sources": ["url", "..."],
        "issues": ["string", "..."]
        }
        """,
        [
            'get_team_roster',
            'get_league_dash_lineups',
            'get_team_lineups',
            'get_matchups_rollup',
            'get_league_game_finder',
            'get_player_vs_player'
        ]
    ),
    agent_config(
        "bench",
        """
        Role: Bench & Second Units (data only).

        Tasks:
        - Identify top five bench players per team by minutes last 10 and season.
        - Bench net rating, on/off impact, and typical second-unit overlaps (when available).
        - Factual notes on backup C foul rates, microwave scorers (stat-based only).

        If you are unable to uncover some of the target information, document the missing data in the issues section for handoff to a
        collaborator with web-search capabilities.

        Return JSON only.

        Schema:
        {
        "last_updated": "ISO8601",
        "bench_players": {
            "home": [{"player":"string","min_last10":number,"min_season":number,"usg":number|null,"on_off":number|null,"bench_net":number|null,"units":"points_per_100","source":"url"}],
            "away": [{"player":"string","min_last10":number,"min_season":number,"usg":number|null,"on_off":number|null,"bench_net":number|null,"units":"points_per_100","source":"url"}]
        },
        "second_unit_overlap": [
            {"home_unit":"string","away_unit":"string","minutes":number,"net_home":number|null,"net_away":number|null,"units":"points_per_100","source":"url"}
        ],
        "bench_indicators": [
            {"player":"string","metric":"foul_rate|3p_rate|ts%|on_off","value":number,"units":"per36|share|percent","sample_size_minutes":number,"source":"url"}
        ],
        "sources": ["url", "..."],
        "issues": ["string", "..."]
        }
        """,
        [
            'get_league_dash_player_stats',
            'get_team_roster',
            'get_league_dash_lineups',
            'get_team_lineups',
            'get_player_game_log',
            'get_league_dash_team_stats'
        ]
    ),
    agent_config(
        "team_form",
        """
        Role: Team Form & Microtrends (data only).

        Tasks:
        - Last 10–15 and season: ORtg, DRtg, Net, Pace; Four Factors (off/def).
        - 3PT quality vs actual (shot quality models) and clutch net rating.
        - Star player recent form (slump/hot) as stats only (no labels).

        If you are unable to uncover some of the target information, document the missing data in the issues section for handoff to a
        collaborator with web-search capabilities.

        Return JSON only.

        Schema:
        {
        "last_updated": "ISO8601",
        "ranges": {
            "last_10": {
            "home": {"ortg":number,"drtg":number,"net":number,"pace":number,"off_four":{"efg":number,"tov":number,"orb":number,"ftr":number},"def_four":{"efg":number,"tov":number,"drb":number,"ftr":number},"clutch_net":number|null},
            "away": {"ortg":number,"drtg":number,"net":number,"pace":number,"off_four":{"efg":number,"tov":number,"orb":number,"ftr":number},"def_four":{"efg":number,"tov":number,"drb":number,"ftr":number},"clutch_net":number|null}
            },
            "season": { "home": {...}, "away": {...} }
        },
        "shot_quality": {
            "home": {"exp_3p":number,"act_3p":number,"diff":number,"units":"percentage_points","source":"url"},
            "away": {"exp_3p":number,"act_3p":number,"diff":number,"units":"percentage_points","source":"url"}
        },
        "star_stats": [
            {"player":"string","range":"last_10","metrics":{"pts":number,"ast":number,"reb":number,"ts%":number,"usg%":number,"touches":number|null},"source":"url"}
        ],
        "date_ranges": {"last_10":"string","season":"string"},
        "sources": ["url", "..."],
        "issues": ["string", "..."]
        }
        """,
        [
            'get_league_dash_team_stats',
            'get_team_clutch_stats',
            'get_player_clutch_stats',
            'get_league_dash_player_stats',
            'get_team_shooting_splits',
            'get_player_shooting_splits',
            'get_league_game_finder'
        ]
    ),
    agent_config(
        "coaching",
        """
        Role: Tactics & Coaching (data only).

        Tasks:
        - Offensive/defensive scheme usage rates (e.g., PnR ball-handler %, ISO %, zone %, switch %, drop %), with sources.
        - Coverage vs stars historically (e.g., blitz rate vs specific players).
        - ATO efficiency, late-game play-type frequencies, timeout usage data.
        - Rotation patterns: average stints, bench timing (facts only).

        If you are unable to uncover some of the target information, document the missing data in the issues section for handoff to a
        collaborator with web-search capabilities.

        Return JSON only.

        Schema:
        {
        "last_updated": "ISO8601",
        "schemes": {
            "home_off": {"pnr_bh_pct":number,"iso_pct":number,"post_pct":number,"handoff_pct":number,"source":"url"},
            "home_def": {"drop_pct":number,"switch_pct":number,"zone_pct":number,"hedge_pct":number,"source":"url"},
            "away_off": {"pnr_bh_pct":number,"iso_pct":number,"post_pct":number,"handoff_pct":number,"source":"url"},
            "away_def": {"drop_pct":number,"switch_pct":number,"zone_pct":number,"hedge_pct":number,"source":"url"}
        },
        "star_coverages": [
            {"star":"string","coverage":"drop|switch|blitz|show|zone","rate":number|null,"units":"percent","date_range":"string","source":"url"}
        ],
        "late_game": {
            "home":{"ato_pts_per_play":number|null,"clutch_off_rt":number|null,"clutch_def_rt":number|null,"source":"url"},
            "away":{"ato_pts_per_play":number|null,"clutch_off_rt":number|null,"clutch_def_rt":number|null,"source":"url"}
        },
        "rotation_patterns": [
            {"team":"home|away","pattern":"string (factual: e.g., 'stagger Star A at 6:00 1Q per X')","source":"url"}
        ],
        "sources": ["url", "..."],
        "issues": ["string", "...]
        }
        """,
        [
            'get_synergy_play_types',
            'get_team_clutch_stats',
            'get_game_rotation',
            'get_play_by_play'
        ]
    ),
    agent_config(
        "schedule",
        """
        Role: Schedule & Context (data only).

        Tasks:
        - Days rest; B2B/3-in-4/4-in-6; recent and upcoming schedules; travel miles/time zones; home/away.
        - Recent H2H (last 2–3 meetings) with dates/scores.
        - Standings leverage (seed, games back) and historical performance in similar rest/travel situations.

        If you are unable to uncover some of the target information, document the missing data in the issues section for handoff to a
        collaborator with web-search capabilities.

        Return JSON only.

        Schema:
        {
        "last_updated": "ISO8601",
        "rest": {"home_days": number, "away_days": number, "calc_method": "calendar_diff|league_flag"},
        "density": {"home":"B2B|3in4|4in6|none","away":"B2B|3in4|4in6|none"},
        "travel": {"home_miles": number, "away_miles": number, "time_zones_crossed_home": number, "time_zones_crossed_away": number, "window_days": "string", "source":"url"},
        "home_away": {"home":"home","away":"away"},
        "h2h_recent": [
            {"date":"YYYY-MM-DD","home_score":number,"away_score":number,"site":"home|away|neutral","notes":"string|null","source":"url"}
        ],
        "standings": {
            "home":{"seed":number,"record":"W-L","games_back":number,"source":"url"},
            "away":{"seed":number,"record":"W-L","games_back":number,"source":"url"}
        },
        "situational_perf": {
            "home":{"rest_adv_net":number|null,"b2b_net":number|null,"road_trip_net":number|null,"units":"points_per_100","source":"url"},
            "away":{"rest_adv_net":number|null,"b2b_net":number|null,"road_trip_net":number|null,"units":"points_per_100","source":"url"}
        },
        "sources": ["url", "..."],
        "issues": ["string", "..."]
        }
        """,
        [
            'get_schedule',
            'get_league_game_finder',
            'get_league_standings',
            'get_team_details',
            'get_team_info',
            'get_scoreboard',
            'get_league_dash_team_stats'
        ]
    ),
    agent_config(
        "drama",
        """
        Role: Rivalry & Narrative Facts (data only).

        Tasks:
        - Rivalry history: playoff series, notable games, iconic moments (facts only, with dates).
        - Personal grudges/ex-teammate subplots: transactions, incidents, technicals, public statements (quote exact text where applicable).
        - Recent quotes or verified social posts relevant to motivation; include direct links and timestamps.

        If you are unable to uncover some of the target information, document the missing data in the issues section for handoff to a
        collaborator with web-search capabilities.

        Return JSON only.

        Schema:
        {
        "last_updated": "ISO8601",
        "rivalry_history": [
            {"date":"YYYY-MM-DD","event":"string","context":"regular|playoffs","result":"string|null","source":"url"}
        ],
        "personal_subplots": [
            {"persons":["Player/Coach A","Player/Coach B"],"event":"trade|fight|quote|tech","date":"YYYY-MM-DD","details":"string","source":"url"}
        ],
        "verified_quotes": [
            {"speaker":"string","quote":"string","ts":"ISO8601","platform":"press|team|x|ig","url":"url"}
        ],
        "sources": ["url", "..."],
        "issues": ["string", "..."]
        }
        """,
        []
    )
]