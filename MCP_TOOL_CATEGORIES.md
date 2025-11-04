# NBA Stats MCP - Tool Category Summary

All 83 tools have been categorized with metadata tags for hierarchical/lazy loading.

## Categories Used

### Primary Categories
1. **player** (25+ tools) - Player-specific statistics and information
2. **team** (20+ tools) - Team-specific statistics and information
3. **league** (15+ tools) - League-wide statistics and standings
4. **game** (20+ tools) - Game-specific data and events
5. **boxscore** (20 tools) - Box score variants for games
6. **draft** (8 tools) - Draft-related data
7. **franchise** (3 tools) - Franchise history and leaders
8. **playoff** (2 tools) - Playoff-specific data
9. **season** (2 tools) - Season schedules and IST standings

### Secondary/Modifier Categories
10. **statistics** (15+ tools) - Statistical analysis tools
11. **historical** (5+ tools) - Historical/all-time data
12. **tracking** (6+ tools) - Player/team tracking data
13. **advanced** (4+ tools) - Advanced metrics (estimated metrics, synergy)
14. **shooting** (1 tool) - Shooting-specific analysis
15. **combine** (5 tools) - Draft combine specific
16. **video** (2 tools) - Video-related endpoints
17. **other** (1 tool) - Miscellaneous (fantasy widget)

## Multi-Category Tools

Most tools belong to 1-3 categories. Examples:

- **Single category**: `get_team_roster` → `['team']`
- **Two categories**: `get_player_info` → `['player']`, `get_draft_board` → `['draft']`
- **Three categories**: `get_boxscore_advanced_v2` → `['boxscore', 'game', 'advanced']`
- **Four categories**: `get_franchise_history` → `['franchise', 'team', 'historical']`

## Category Breakdown by Primary Type

### Player Tools (25+)
- Pure player: `get_player_info`, `get_player_profile`, `get_player_awards`
- Player + statistics: `get_player_career_stats_full`, `get_player_clutch_stats`, `get_player_shooting_splits`
- Player + game: `get_player_game_log`, `get_cumulative_player_game_stats`
- Player + advanced: `get_player_estimated_metrics`
- Player + league: `get_all_players`

### Team Tools (20+)
- Pure team: `get_team_roster`, `get_team_info`, `get_team_details`
- Team + statistics: `get_team_clutch_stats`, `get_team_shooting_splits`, `get_team_lineups`
- Team + game: `get_team_game_log`, `get_cumulative_team_game_stats`
- Team + historical: `get_team_historical_leaders`, `get_team_year_by_year`
- Team + player: `get_team_vs_player`

### Boxscore Tools (20)
All boxscore tools include `['boxscore', 'game']` plus:
- Traditional: `get_boxscore_traditional_v2/v3`
- Advanced: `get_boxscore_advanced_v2/v3` (adds `'advanced'`)
- Tracking: `get_boxscore_player_track_v2/v3`, `get_boxscore_hustle_v2` (adds `'tracking'`)
- Scoring: `get_boxscore_scoring_v2/v3`
- Usage: `get_boxscore_usage_v2/v3`
- Four Factors: `get_boxscore_four_factors_v2/v3`
- Misc: `get_boxscore_misc_v2/v3`

### League Tools (15+)
- League + statistics: `get_league_leaders`, `get_league_dash_player_stats`, `get_league_dash_team_stats`
- League + game: `get_league_game_finder`
- League + tracking: `get_league_hustle_stats_player`, `get_league_hustle_stats_team`
- League + historical: `get_all_time_leaders`

### Game Tools (10+)
- Pure game: `get_scoreboard`, `get_game_rotation`, `get_play_by_play`
- Game + video: `get_video_events`, `get_video_status`
- Game + boxscore: All 20 boxscore tools
- Game + win probability: `get_win_probability`

### Draft Tools (8)
- Pure draft: `get_draft_board`, `get_draft_history`
- Draft + combine: `get_draft_combine_drill_results`, `get_draft_combine_shooting`, etc. (5 tools)

### Franchise Tools (3)
All franchise tools include `['franchise', 'team', 'historical']`:
- `get_franchise_history`
- `get_franchise_leaders`
- `get_franchise_players`

### Playoff Tools (2)
- `get_playoff_series` → `['playoff']`
- `get_playoff_picture` → `['playoff']`

### Season Tools (2)
- `get_schedule` → `['season']`
- `get_ist_standings` → `['season']`

## Usage for Hierarchical Tool Loading

When implementing a lazy-loading search tool:

1. **Top-level categories** to expose:
   - Player (25+ tools)
   - Team (20+ tools)
   - League (15+ tools)
   - Game (30+ tools including boxscores)
   - Draft (8 tools)
   - Franchise (3 tools)
   - Playoff (2 tools)
   - Season (2 tools)

2. **Refinement categories** for filtering:
   - Add `statistics`, `tracking`, `advanced`, `historical` as filters
   - Allow multi-select for tools in multiple categories

3. **Search strategy**:
   ```python
   # Example: User wants "player statistics"
   # Return tools with category containing both 'player' AND 'statistics'
   matching_tools = [
       'get_player_career_stats_full',
       'get_player_clutch_stats',
       'get_player_shooting_splits',
       # etc.
   ]
   ```

4. **Benefit**: Instead of exposing all 83 tools initially, expose 8-10 category groups, then expand on demand.
