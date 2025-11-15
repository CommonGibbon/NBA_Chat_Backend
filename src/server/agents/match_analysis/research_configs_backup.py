
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