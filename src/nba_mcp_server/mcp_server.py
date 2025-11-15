from mcp.server.fastmcp import FastMCP
from typing import List, Sequence, Optional
from enum import Enum

from nba_api.stats.endpoints import *
from nba_api.stats.static import players, teams
import datetime

mcp = FastMCP("nba-chat")

class ToolCategory(str, Enum):
    player = "player"
    team = "team"
    league = "league"
    game = "game"
    boxscore = "boxscore"
    draft = "draft"
    franchise = "franchise"
    playoff = "playoff"
    season = "season"
    base = "base"
ALLOWED = {c.value for c in ToolCategory if c != ToolCategory.base} # the llm has no need to ever request "base" tools since they're always included.

@mcp.tool(meta={"category":["base"]})
def get_tools_by_category(categories: List[str]) -> List[str]:
    """
    Request to load tools from specific categories. Multiple categories may be selected.
    Args:
        categories - a list of tool categories to filter on. Categories must be one of the following:
            player - Player-specific statistics and information
            team- Team-specific statistics and information
            league - League-wide statistics and standings
            game- Game-specific data and events
            boxscore- Box score variants for games
            draft- Draft-related data
            franchise - Franchise history and leaders
            playoff - Playoff-specific data
            season - Season schedules and IST standings
    """

    requested = {c.lower().strip() for c in categories}
    invalid = requested - ALLOWED
    if invalid:
        raise ValueError(f"Invalid categories: {sorted(invalid)}. Allowed: {sorted(ALLOWED)}")
    
    result = list(requested | {"base"})
    return sorted(result)

def find_player_id(player_name: str) -> Optional[int]:
    """Helper function to find player ID by name."""
    players_found = players.find_players_by_full_name(player_name)
    if not players_found:
        return None
    return players_found[0]['id']


def find_team_id(team_name: str) -> Optional[int]:
    """Helper function to find team ID by name or abbreviation."""
    all_teams = teams.get_teams()
    for team in all_teams:
        if (team_name.lower() == team['full_name'].lower() or 
            team_name.lower() == team['abbreviation'].lower() or
            team_name.lower() == team['nickname'].lower()):
            return team['id']
    return None


def get_current_season() -> str:
    """Helper function to get current NBA season in format YYYY-YY."""
    today = datetime.date.today()
    year = today.year
    if today.month >= 10:
        return f"{year}-{str(year + 1)[-2:]}"
    else:
        return f"{year - 1}-{str(year)[-2:]}"
    


@mcp.tool(meta = {"category": ['player']})
def get_player_name_from_id(player_id: str) -> str:
    """Get player name from player_id."""
    return commonplayerinfo.CommonPlayerInfo(player_id=player_id).common_player_info.get_data_frame().DISPLAY_FIRST_LAST.values[0]

@mcp.tool(meta={"category": ['team']})
def get_team_name_from_id(team_id: str) -> str:
    """Get team name from team_id."""
    return teamdetails.TeamDetails(team_id=team_id).team_background.get_data_frame().ABBREVIATION.values[0]


@mcp.tool(meta={"category": ['league', 'historical']})
def get_all_time_leaders(
    per_mode: str = "Totals",
    season_type: str = "Regular Season",
    top_x: int = 10,
    stat_categories: Optional[List[str]] = None
) -> str:
    """
    Get all-time statistical leaders across all NBA history.
    Returns leaderboards for specified statistical categories.
    
    Optional Args:
        per_mode: "Totals" or "PerGame".
        season_type: "Regular Season", "Playoffs", or "All Star".
        top_x: Number of leaders to return (default 10).
        stat_categories: List of stat categories to return.
                        Options: "points", "assists", "rebounds", "blocks", "steals", 
                                "turnovers", "field_goals", "field_goal_pct", "threes",
                                "three_pct", "free_throws", "free_throw_pct", 
                                "offensive_rebounds", "defensive_rebounds", "fouls", "games"
                        If None, returns points, assists, and rebounds.
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    # Default to current behavior if no categories specified
    if stat_categories is None:
        stat_categories = ["points", "assists", "rebounds"]
    
    # Map user-friendly names to data object attributes
    category_mapping = {
        "points": ("pts_leaders", "Points"),
        "assists": ("ast_leaders", "Assists"), 
        "rebounds": ("reb_leaders", "Rebounds"),
        "blocks": ("blk_leaders", "Blocks"),
        "steals": ("stl_leaders", "Steals"),
        "turnovers": ("tov_leaders", "Turnovers"),
        "field_goals": ("fgm_leaders", "Field Goals Made"),
        "field_goal_pct": ("fg_pct_leaders", "Field Goal %"),
        "threes": ("fg3m_leaders", "3-Point Field Goals"),
        "three_pct": ("fg3_pct_leaders", "3-Point %"),
        "free_throws": ("ftm_leaders", "Free Throws Made"),
        "free_throw_pct": ("ft_pct_leaders", "Free Throw %"),
        "offensive_rebounds": ("oreb_leaders", "Offensive Rebounds"),
        "defensive_rebounds": ("dreb_leaders", "Defensive Rebounds"),
        "fouls": ("pf_leaders", "Personal Fouls"),
        "games": ("gp_leaders", "Games Played")
    }
    
    # Validate categories
    invalid_categories = [cat for cat in stat_categories if cat not in category_mapping]
    if invalid_categories:
        return f"Invalid stat categories: {', '.join(invalid_categories)}. Valid options: {', '.join(category_mapping.keys())}"
    
    try:
        data = alltimeleadersgrids.AllTimeLeadersGrids(
            league_id="00",
            per_mode_simple=per_mode,
            season_type=season_type,
            topx=top_x
        )
        
        result = f"# All-Time Leaders\n\n"
        result += f"*Per Mode: {per_mode} | Season Type: {season_type}*\n\n"
        
        for category in stat_categories:
            attr_name, display_name = category_mapping[category]
            df = getattr(data, attr_name).get_data_frame()
            result += f"## {display_name}\n"
            result += df.to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving all-time leaders: {str(e)}"


@mcp.tool(meta={"category": ['league', 'statistics']})
def get_assist_leaders(
    season: Optional[str] = None,
    per_mode: str = "Totals",
    player_or_team: str = "Team",
    season_type: str = "Regular Season"
) -> str:
    """
    Get assist leaders for a specific season.
    
    Optional Args:
        season: NBA season (e.g., "2023-24"). If None, uses current season.
        per_mode: "Totals" or "PerGame".
        player_or_team: "Player" or "Team".
        season_type: "Regular Season", "Playoffs", "Pre Season".
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
            
        data = assistleaders.AssistLeaders(
            league_id="00",
            per_mode_simple=per_mode,
            player_or_team=player_or_team,
            season=season,
            season_type_playoffs=season_type
        )
        
        df = data.assist_leaders.get_data_frame()
        return f"# Assist Leaders - {season} ({season_type})\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving assist leaders: {str(e)}"


@mcp.tool(meta={"category": ['league', 'statistics', 'tracking']})
def get_assist_tracker(
    season: Optional[str] = None,
    team_name: Optional[str] = None,
    opponent_team_name: Optional[str] = None,
    season_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    per_mode: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    conference: Optional[str] = None,
    division: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None,
    college: Optional[str] = None,
    country: Optional[str] = None,
    draft_year: Optional[str] = None,
    draft_pick: Optional[str] = None,
    height: Optional[str] = None,
    weight: Optional[str] = None,
    game_scope: Optional[str] = None,
    last_n_games: Optional[int] = None,
    month: Optional[int] = None,
    season_segment: Optional[str] = None,
    po_round: Optional[str] = None
) -> str:
    """
    Returns the total assist count met by the supplied filter criteria.
    Analysts can evaluate performance trends, compare assist production by position or experience level, and identify strategic patterns against 
    specific opponents. 
    
    Args:
        season: NBA season (e.g., "2023-24").
        team_name: Team name or abbreviation.
        opponent_team_name: Opponent team name or abbreviation.
        season_type: "Regular Season", "Playoffs", "All Star", "Pre Season".
        date_from: Start date (YYYY-MM-DD).
        date_to: End date (YYYY-MM-DD).
        per_mode: "Totals" or "PerGame".
        location: "Home" or "Road".
        outcome: "W" or "L".
        conference: "East" or "West".
        division: "Atlantic" | "Central" | "Northwest" | "Pacific" | "Southeast" | "Southwest" | "East" | "West"
        vs_conference: "East" or "West".
        vs_division: "Atlantic" | "Central" | "Northwest" | "Pacific" | "Southeast" | "Southwest" | "East" | "West"
        player_position: "G", "F", "C", "G-F", etc.
        player_experience: "Rookie", "Sophomore", "Veteran".
        starter_bench: "Starters" or "Bench".
        college: College name.
        country: Country name.
        draft_year: Draft year.
        draft_pick: Draft pick.
        height: Height filter.
        weight: Weight filter.
        game_scope: "Yesterday" or "Last 10".
        last_n_games: Number of recent games.
        month: Month number (1-12).
        season_segment: "Post All-Star" or "Pre All-Star".
        po_round: Playoff round.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = None
        if team_name:
            team_id = find_team_id(team_name)
            if team_id is None:
                return f"Team '{team_name}' not found. Check spelling."
        
        opponent_team_id = None
        if opponent_team_name:
            opponent_team_id = find_team_id(opponent_team_name)
            if opponent_team_id is None:
                return f"Opponent team '{opponent_team_name}' not found. Check spelling."
        
        data = assisttracker.AssistTracker(
            season_nullable=season or "",
            team_id_nullable=str(team_id) if team_id else "",
            opponent_team_id_nullable=str(opponent_team_id) if opponent_team_id else "",
            season_type_all_star_nullable=season_type or "",
            date_from_nullable=date_from or "",
            date_to_nullable=date_to or "",
            per_mode_simple_nullable=per_mode or "",
            location_nullable=location or "",
            outcome_nullable=outcome or "",
            conference_nullable=conference or "",
            division_simple_nullable=division or "",
            vs_conference_nullable=vs_conference or "",
            vs_division_nullable=vs_division or "",
            player_position_abbreviation_nullable=player_position or "",
            player_experience_nullable=player_experience or "",
            starter_bench_nullable=starter_bench or "",
            college_nullable=college or "",
            country_nullable=country or "",
            draft_year_nullable=draft_year or "",
            draft_pick_nullable=draft_pick or "",
            height_nullable=height or "",
            weight_nullable=weight or "",
            game_scope_simple_nullable=game_scope or "",
            last_n_games_nullable=last_n_games or "",
            month_nullable=month or "",
            season_segment_nullable=season_segment or "",
            po_round_nullable=po_round or "",
            league_id_nullable=""
        )
        
        df = data.assist_tracker.get_data_frame()
        return f"# Assist Tracker\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving assist tracker data: {str(e)}"

@mcp.tool(meta={"category": ['boxscore', 'game', 'advanced']})
def get_boxscore_advanced_v3(
    game_id: str,
    team_or_player: str = "P"
) -> str:
    """
    Get advanced box score statistics for a specific game aggregated by player or by team. Data returned includes:
    minutes, estimatedOffensiveRating, offensiveRating,
    estimatedDefensiveRating, defensiveRating, estimatedNetRating,
    netRating, assistPercentage, assistToTurnover, assistRatio,
    offensiveReboundPercentage, defensiveReboundPercentage,
    reboundPercentage, turnoverRatio, effectiveFieldGoalPercentage,
    trueShootingPercentage, usagePercentage, estimatedUsagePercentage,
    estimatedPace, pace, pacePer40, possessions, PIE
    
    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    """
    Hidden parameters:
    None of these seem to do anything. I tested all variations I could think of with ints, strings, values, etc. to no effect.
        start_period: Values map to quarter (1-4) or overtime (5-10)
        end_period: Ending period (default 10 covers OT).
        start_range: Range start (default 0).
        end_range: Range end (default 0).
        range_type: Range type (default 0).
    """
    try:
        data = boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=game_id)
        
        result = f"# Advanced Box Score\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        elif team_or_player == "T":
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving advanced box score v3: {str(e)}"

@mcp.tool(meta={"category": ['boxscore', 'game']})
def get_boxscore_defensive_v2(
    game_id: str,
    team_or_player: str = "P"
) -> str:
    """
    Get defensive box score statistics for a specific game aggregated by player or by team. Data returned includes:
    matchupMinutes, partialPossessions, switchesOn, playerPoints, defensiveRebounds,
    matchupAssists, matchupTurnovers, steals, blocks,
    matchupFieldGoalsMade, matchupFieldGoalsAttempted,
    matchupFieldGoalPercentage, matchupThreePointersMade,
    matchupThreePointersAttempted, matchupThreePointerPercentage
    
    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    try:
        data = boxscoredefensivev2.BoxScoreDefensiveV2(game_id=game_id)
        
        result = f"# Defensive Box Score\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        elif team_or_player == "T":
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving defensive box score: {str(e)}"


@mcp.tool(meta={"category": ['boxscore', 'game']})
def get_boxscore_four_factors_v3(
    game_id: str,
    team_or_player: str = "P",
) -> str:
    """
    Get 'Four Factors' box score statistics for a specific game aggregated by player or by team. Data returned includes:
    minutes, effectiveFieldGoalPercentage, freeThrowAttemptRate,
    teamTurnoverPercentage, offensiveReboundPercentage,
    oppEffectiveFieldGoalPercentage, oppFreeThrowAttemptRate,
    oppTeamTurnoverPercentage, oppOffensiveReboundPercentage

    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    """
    Hidden parameters: see get_boxscores_advanced_v3
    """
    try:
        data = boxscorefourfactorsv3.BoxScoreFourFactorsV3(game_id=game_id)
        
        result = f"# Four Factors Box Score V3\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        else:
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving four factors box score v3: {str(e)}"


@mcp.tool(meta={"category": ['boxscore', 'game']})
def get_boxscore_hustle_v2(
    game_id: str,
    team_or_player: str = "P",
) -> str:
    """
    Get hustle statistics box score for a specific game aggregated by player or by team. Data returned includes:
    minutes, points, contestedShots, contestedShots2pt, contestedShots3pt, deflections, chargesDrawn, 
    screenAssists, screenAssistPoints, looseBallsRecoveredOffensive, looseBallsRecoveredDefensive, 
    looseBallsRecoveredTotal, offensiveBoxOuts, defensiveBoxOuts, boxOutPlayerTeamRebounds, boxOutPlayerRebounds, boxOuts
    
    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    try:
        data = boxscorehustlev2.BoxScoreHustleV2(game_id=game_id)
        
        result = f"# Hustle Stats Box Score\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        else:
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving hustle box score: {str(e)}"


@mcp.tool(meta={"category": ['boxscore', 'game']})
def get_boxscore_matchups_v3(game_id: str) -> str:
    """
    Get player matchup data for a specific game (who guarded whom). Data returned includes:
    matchupMinutes, matchupMinutesSort, partialPossessions, percentageDefenderTotalTime, percentageOffensiveTotalTime, 
    percentageTotalTimeBothOn, switchesOn, playerPoints, teamPoints, matchupAssists, matchupPotentialAssists, matchupTurnovers, 
    matchupBlocks, matchupFieldGoalsMade, matchupFieldGoalsAttempted, matchupFieldGoalsPercentage, matchupThreePointersMade, 
    matchupThreePointersAttempted, matchupThreePointersPercentage, helpBlocks, helpFieldGoalsMade, helpFieldGoalsAttempted, 
    helpFieldGoalsPercentage, matchupFreeThrowsMade, matchupFreeThrowsAttempted, shootingFouls

    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). Game IDs can be obtained using the get_league_game_finder tool.
    """
    try:
        data = boxscorematchupsv3.BoxScoreMatchupsV3(game_id=game_id)

        result = f"# Matchups Box Score\n\n"
        result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"

        return result

    except Exception as e:
        return f"Error retrieving matchups box score: {str(e)}"


@mcp.tool(meta={"category": ['boxscore', 'game']})
def get_boxscore_misc_v3(
    game_id: str,
    team_or_player: str = "P",
) -> str:
    """
    Get miscellaneous box score statistics aggregated by player or by team.

    Data returned includes:
    minutes, pointsOffTurnovers, pointsSecondChance, pointsFastBreak, pointsPaint,
    oppPointsOffTurnovers, oppPointsSecondChance, oppPointsFastBreak, oppPointsPaint,
    blocks, blocksAgainst, foulsPersonal, foulsDrawn

    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    try:
        data = boxscoremiscv3.BoxScoreMiscV3(game_id=game_id)
        
        result = f"# Miscellaneous Box Score V3\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        else:
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving misc box score v3: {str(e)}"


@mcp.tool(meta={"category": ['boxscore', 'game', 'tracking']})
def get_boxscore_player_track_v3(
    game_id: str,
    team_or_player: str = "P",
) -> str:
    """
    Get player tracking box score stats (v3 - newer format).

    Data returned includes:
        minutes, speed, distance, reboundChancesOffensive, reboundChancesDefensive, reboundChancesTotal, touches, secondaryAssists, 
        freeThrowAssists, passes, assists, contestedFieldGoalsMade, contestedFieldGoalsAttempted, contestedFieldGoalPercentage, 
        uncontestedFieldGoalsMade, uncontestedFieldGoalsAttempted, uncontestedFieldGoalsPercentage, fieldGoalPercentage, defendedAtRimFieldGoalsMade, 
        defendedAtRimFieldGoalsAttempted, defendedAtRimFieldGoalPercentage

    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    try:
        data = boxscoreplayertrackv3.BoxScorePlayerTrackV3(game_id=game_id)
        
        result = f"# Player Tracking Box Score V3\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        else:
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving player tracking box score v3: {str(e)}"

@mcp.tool(meta={"category": ['boxscore', 'game']})
def get_boxscore_scoring_v3(
    game_id: str,
    team_or_player: str = "P",
) -> str:
    """
    Get scoring-focused box score stats (v3 - newer format).

    Data returned includes:
        MIN, PCT_FGA_2PT, PCT_FGA_3PT, PCT_PTS_2PT, PCT_PTS_2PT_MR, PCT_PTS_3PT, PCT_PTS_FB, PCT_PTS_FT, 
        PCT_PTS_OFF_TOV, PCT_PTS_PAINT, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM

    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    try:
        data = boxscorescoringv3.BoxScoreScoringV3(game_id=game_id)
        
        result = f"# Scoring Box Score V3\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        else:
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving scoring box score v3: {str(e)}"


@mcp.tool(meta={"category": ['boxscore', 'game']})
def get_boxscore_traditional_v3(
    game_id: str,
    team_or_player: str = "P",
) -> str:
    """
    Get traditional box score stats (v3 - newer format).

    Data returned includes:
        minutes, fieldGoalsMade, fieldGoalsAttempted, fieldGoalsPercentage, threePointersMade, threePointersAttempted, threePointersPercentage, 
        freeThrowsMade, freeThrowsAttempted, freeThrowsPercentage, reboundsOffensive, reboundsDefensive, reboundsTotal, assists, steals, blocks, 
        turnovers, foulsPersonal, points, plusMinusPoints

    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    try:
        data = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
        
        result = f"# Traditional Box Score V3\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        else:
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving traditional box score v3: {str(e)}"


@mcp.tool(meta={"category": ['boxscore', 'game']})
def get_boxscore_usage_v3(
    game_id: str,
    team_or_player: str = "P",
) -> str:
    """
    Get usage statistics box score (v3 - newer format).

    Data returned includes:
        minutes, usagePercentage, percentageFieldGoalsMade, percentageFieldGoalsAttempted, percentageThreePointersMade, 
        percentageThreePointersAttempted, percentageFreeThrowsMade, percentageFreeThrowsAttempted, percentageReboundsOffensive, 
        percentageReboundsDefensive, percentageReboundsTotal, percentageAssists, percentageTurnovers, percentageSteals, percentageBlocks, 
        percentageBlocksAllowed, percentagePersonalFouls, percentagePersonalFoulsDrawn, percentagePoints

    Args:
        game_id: 10-digit game ID (e.g., "0021700807"). game_ids can be obtained using the get_league_game_finder tool call
        team_or_player: "P" for player stats, "T" for team stats (default "P").
    """
    try:
        data = boxscoreusagev3.BoxScoreUsageV3(game_id=game_id)
        
        result = f"# Usage Box Score V3\n\n"
        if team_or_player == "P":
            result += "## Player Stats\n"
            result += data.player_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        else:
            result += "## Team Stats\n"
            result += data.team_stats.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving usage box score v3: {str(e)}"


@mcp.tool(meta={"category": ['player', 'league']})
def get_all_players(
    season: Optional[str] = None,
    is_only_current_season: int = 0
) -> str:
    """
    Get list of all NBA players for a specific season.
    
    Args:
        season: NBA season (e.g., "2023-24"). If None, uses current season.
        is_only_current_season: 1 for only current season roster, 0 for all historical.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
            
        data = commonallplayers.CommonAllPlayers(
            is_only_current_season=is_only_current_season,
            league_id="00",
            season=season
        )
        
        df = data.common_all_players.get_data_frame()
        return f"# All Players - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving all players: {str(e)}"


@mcp.tool(meta={"category": ['player']})
def get_player_info(player_name: str) -> str:
    """
    Get detailed information about a specific player. Data includes:
        PERSON_ID, FIRST_NAME, LAST_NAME, DISPLAY_FIRST_LAST,
        DISPLAY_LAST_COMMA_FIRST, DISPLAY_FI_LAST, PLAYER_SLUG,
        BIRTHDATE, SCHOOL, COUNTRY, LAST_AFFILIATION, HEIGHT,
        WEIGHT, SEASON_EXP, JERSEY, POSITION, ROSTERSTATUS,
        GAMES_PLAYED_CURRENT_SEASON_FLAG, TEAM_ID, TEAM_NAME,
        TEAM_ABBREVIATION, TEAM_CODE, TEAM_CITY, PLAYERCODE,
        FROM_YEAR, TO_YEAR, DLEAGUE_FLAG, NBA_FLAG, GAMES_PLAYED_FLAG,
        DRAFT_YEAR, DRAFT_ROUND, DRAFT_NUMBER, GREATEST_75_FLAG
    
    Args:
        player_name: Player's full name (e.g., "LeBron James").
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        player_id = find_player_id(player_name)
        if player_id is None:
            return f"Player '{player_name}' not found. Check the exact name spelling."
        
        data = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            league_id_nullable=""
        )
        
        result = f"# Player Info - {player_name}\n\n"
        result += data.common_player_info.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving player info for {player_name}: {str(e)}"


@mcp.tool(meta={"category": ['playoff']})
def get_playoff_series(
    season: Optional[str] = None
) -> str:
    """
    Get playoff series information for a season. Data returned:
    GAME_ID, HOME_TEAM_ID, VISITOR_TEAM_ID, SERIES_ID, GAME_NUM
    
    Args:
        season: NBA season (e.g., "2023-24"). If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
            
        data = commonplayoffseries.CommonPlayoffSeries(
            league_id="00",
            season=season
        )
        
        df = data.playoff_series.get_data_frame()
        return f"# Playoff Series - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving playoff series: {str(e)}"


@mcp.tool(meta={"category": ['team']})
def get_team_roster(
    team_name: str,
    season: Optional[str] = None
) -> str:
    """
    Get team roster and coach information for a specific season.
    Coach data returned: TEAM_ID, SEASON, COACH_ID, FIRST_NAME, LAST_NAME, COACH_NAME, IS_ASSISTANT, COACH_TYPE, SORT_SEQUENCE
    Team data returned: TeamID, SEASON, LeagueID, PLAYER, PLAYER_SLUG, NUM, POSITION, HEIGHT, WEIGHT, BIRTH_DATE, AGE, EXP, SCHOOL, PLAYER_ID
    
    Args:
        team_name: Team name or abbreviation (e.g., "Lakers" or "LAL").
        season: NBA season (e.g., "2023-24"). If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if team_id is None:
            return f"Team '{team_name}' not found. Check spelling."
        
        if season is None:
            season = get_current_season()
        
        data = commonteamroster.CommonTeamRoster(
            team_id=team_id,
            season=season,
            league_id_nullable=""
        )
        
        result = f"# Team Roster - {team_name} ({season})\n\n"
        result += "## Players\n"
        result += data.common_team_roster.get_data_frame().to_markdown(index=False) + "\n\n"
        result += "## Coaches\n"
        result += data.coaches.get_data_frame().to_markdown(index=False) + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving team roster for {team_name}: {str(e)}"


@mcp.tool(meta={"category": ['player', 'statistics']})
def get_player_stats_by_game(
    player_name: str,
    game_id: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season"
) -> str:
    """
    Get cumulative player stats for specified game
    Data returned: GP, GS, ACTUAL_MINUTES,
       ACTUAL_SECONDS, FG, FGA, FG_PCT, FG3, FG3A, FG3_PCT, FT,
       FTA, FT_PCT, OFF_REB, DEF_REB, TOT_REB, AVG_TOT_REB, AST,
       PF, DQ, STL, TURNOVERS, BLK, PTS, AVG_PTS
    
    Args:
        player_name: Player's full name.
        game_ids: Game ID (e.g., "0021700807).  game_ids can be obtained using the get_league_game_finder tool call
        season: NBA season (e.g., "2023-24"). If None, uses current season.
        season_type: "Regular Season", "Playoffs", "All Star", "Pre Season". Default: "Regular Season"
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        player_id = find_player_id(player_name)
        if player_id is None:
            return f"Player '{player_name}' not found."
        
        if season is None:
            season = get_current_season()
        
        data = cumestatsplayer.CumeStatsPlayer(
            player_id=player_id,
            game_ids=[game_id],
            season=season,
            season_type_all_star=season_type,
            league_id="00"
        )
        df = data.total_player_stats.get_data_frame()
        if not len(df):
            return f"No data found for player '{player_name}' in game {game_id}."
        else:
            result = f"# Player game Stats - {player_name}\n\n"
            result += df.to_markdown(index=False) + "\n\n"
                
            return result
        
    except Exception as e:
        return f"Error retrieving cumulative stats for {player_name}: {str(e)}"

@mcp.tool(meta={"category": ['team', 'statistics']})
def get_cumulative_team_stats(
    team_name: str,
    game_id: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season"
) -> str:
    """
    Get cumulative team stats across specified games. Data returned: 
    CITY, NICKNAME, TEAM_ID, W, L, W_HOME, L_HOME, W_ROAD, L_ROAD, TEAM_TURNOVERS, TEAM_REBOUNDS, GP, GS, ACTUAL_MINUTES, 
    ACTUAL_SECONDS, FG, FGA, FG_PCT, FG3, FG3A, FG3_PCT, FT, FTA, FT_PCT, OFF_REB, DEF_REB, TOT_REB, AST, PF, STL, 
    TOTAL_TURNOVERS, BLK, PTS, AVG_REB, AVG_PTS, DQ
    
    Args:
        team_name: Team name or abbreviation (e.g., "Lakers" or "LAL").
        game_id: Game ID (e.g., "0021700807).  game_ids can be obtained using the get_league_game_finder tool call
        season: season: NBA season (e.g., "2023-24"). If None, uses current season.
        season_type: "Regular Season", "Playoffs", "All Star", "Pre Season". Default: "Regular Season"
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if team_id is None:
            return f"Team '{team_name}' not found."
        
        if season is None:
            season = get_current_season()
        
        data = cumestatsteam.CumeStatsTeam(
            team_id=team_id,
            game_ids=[game_id],
            season=season,
            season_type_all_star=season_type,
            league_id="00"
        )
        df = data.total_team_stats.get_data_frame()
        if not len(df):
            return f"No data found for team '{team_name}' in game {game_id}."
        else:
            result = f"# Team Stats for game - {team_name}\n\n"
            result += df.to_markdown(index=False) + "\n\n"
            
            return result
        
    except Exception as e:
        return f"Error retrieving cumulative team stats for {team_name}: {str(e)}"


@mcp.tool(meta={"category": ['league', 'statistics']})
def get_defense_hub(
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame"
) -> str:
    """
    Get defensive statistics dashboard/hub.
    
    Args:
        season: NBA season. If None, uses current season.
        season_type: "Regular Season", "Playoffs", etc.
        per_mode: "Totals", "PerGame", "Per36".
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = defensehub.DefenseHub(
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode,
            league_id="00"
        )
        
        df = data.defense_hub.get_data_frame()
        return f"# Defense Hub - {season} ({season_type})\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving defense hub: {str(e)}"


@mcp.tool(meta={"category": ['draft']})
def get_draft_board(
    season: Optional[str] = None
) -> str:
    """
    Get NBA draft board for a specific year.
    
    Args:
        season: Draft year (e.g., "2023-24"). If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = draftboard.DraftBoard(
            season=season,
            league_id="00"
        )
        
        df = data.draft_board.get_data_frame()
        return f"# Draft Board - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving draft board: {str(e)}"


@mcp.tool(meta={"category": ['draft', 'combine']})
def get_draft_combine_drill_results(season: Optional[str] = None) -> str:
    """
    Get NBA draft combine drill results (agility, sprint, etc.).
    
    Args:
        season: Draft year. If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = draftcombinedrillresults.DraftCombineDrillResults(
            season_year=season,
            league_id="00"
        )
        
        df = data.results.get_data_frame()
        return f"# Draft Combine Drill Results - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving draft combine drill results: {str(e)}"


@mcp.tool(meta={"category": ['draft', 'combine']})
def get_draft_combine_shooting(season: Optional[str] = None) -> str:
    """
    Get NBA draft combine non-stationary shooting results.
    
    Args:
        season: Draft year. If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = draftcombinenonstationaryshooting.DraftCombineNonStationaryShooting(
            season_year=season,
            league_id="00"
        )
        
        df = data.results.get_data_frame()
        return f"# Draft Combine Shooting - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving draft combine shooting: {str(e)}"


@mcp.tool(meta={"category": ['draft', 'combine']})
def get_draft_combine_measurements(season: Optional[str] = None) -> str:
    """
    Get NBA draft combine player measurements (height, weight, wingspan, etc.).
    
    Args:
        season: Draft year. If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = draftcombineplayeranthro.DraftCombinePlayerAnthro(
            season_year=season,
            league_id="00"
        )
        
        df = data.results.get_data_frame()
        return f"# Draft Combine Measurements - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving draft combine measurements: {str(e)}"


@mcp.tool(meta={"category": ['draft', 'combine']})
def get_draft_combine_spot_shooting(season: Optional[str] = None) -> str:
    """
    Get NBA draft combine spot shooting results.
    
    Args:
        season: Draft year. If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = draftcombinespotshooting.DraftCombineSpotShooting(
            season_year=season,
            league_id="00"
        )
        
        df = data.results.get_data_frame()
        return f"# Draft Combine Spot Shooting - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving draft combine spot shooting: {str(e)}"


@mcp.tool(meta={"category": ['draft', 'combine']})
def get_draft_combine_stats(season: Optional[str] = None) -> str:
    """
    Get NBA draft combine overall statistics.
    
    Args:
        season: Draft year. If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = draftcombinestats.DraftCombineStats(
            season_year=season,
            league_id="00"
        )
        
        df = data.results.get_data_frame()
        return f"# Draft Combine Stats - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving draft combine stats: {str(e)}"


@mcp.tool(meta={"category": ['draft']})
def get_draft_history(
    season: Optional[str] = None
) -> str:
    """
    Get complete NBA draft history for a season.
    
    Args:
        season: Draft year. If None, uses current season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = drafthistory.DraftHistory(
            season=season,
            league_id="00"
        )
        
        df = data.draft_history.get_data_frame()
        return f"# Draft History - {season}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving draft history: {str(e)}"


@mcp.tool(meta={"category": ['other']})
def get_fantasy_widget(
    season: Optional[str] = None,
    season_type: str = "Regular Season"
) -> str:
    """
    Get fantasy basketball widget data.
    
    Args:
        season: NBA season. If None, uses current season.
        season_type: "Regular Season", "Playoffs", etc.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if season is None:
            season = get_current_season()
        
        data = fantasywidget.FantasyWidget(
            season=season,
            season_type_all_star=season_type,
            league_id="00"
        )
        
        df = data.fantasy_widget.get_data_frame()
        return f"# Fantasy Widget - {season} ({season_type})\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving fantasy widget: {str(e)}"


@mcp.tool(meta={"category": ['franchise', 'team', 'historical']})
def get_franchise_history(team_name: str) -> str:
    """
    Get complete franchise history for a team.
    Accepts team name and converts to ID internally.
    
    Args:
        team_name: Team name or abbreviation (e.g., "Lakers" or "LAL")..
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if team_id is None:
            return f"Team '{team_name}' not found."
        
        data = franchisehistory.FranchiseHistory(
            team_id=team_id,
            league_id="00"
        )
        
        df = data.franchise_history.get_data_frame()
        return f"# Franchise History - {team_name}\n\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error retrieving franchise history for {team_name}: {str(e)}"



@mcp.tool(meta={"category": ['franchise', 'team', 'historical']})
def get_franchise_leaders(team_name: str, per_mode: str = "PerGame") -> str:
    """
    Get franchise all-time leaders. Accepts team name.
    
    Args:
        team_name: Team name or abbreviation (e.g., "Lakers" or "LAL").
        per_mode: Per mode.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        data = franchiseleaders.FranchiseLeaders(team_id=team_id, league_id="00", per_mode_simple=per_mode)
        return f"# Franchise Leaders - {team_name}\n\n" + data.franchise_leaders.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['franchise', 'team', 'historical']})
def get_franchise_players(team_name: str, per_mode: str = "PerGame") -> str:
    """
    Get all players in franchise history. Accepts team name.
    
    Args:
        team_name: Team name or abbreviation (e.g., "Lakers" or "LAL").
        per_mode: Per mode.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        data = franchiseplayers.FranchisePlayers(team_id=team_id, league_id="00", per_mode_simple=per_mode)
        return f"# Franchise Players - {team_name}\n\n" + data.franchise_players.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['game']})
def get_game_rotation(game_id: str) -> str:
    """
    Get player rotation data for a game.
    
    Args:
        game_id: Game ID.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        data = gamerotation.GameRotation(game_id=game_id, league_id="00")
        result = f"# Game Rotation - {game_id}\n\n"
        result += "## Home Team\n" + data.home_team.get_data_frame().to_markdown(index=False) + "\n\n"
        result += "## Away Team\n" + data.away_team.get_data_frame().to_markdown(index=False) + "\n\n"
        return result
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league', 'statistics']})
def get_homepage_leaders(
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    player_or_team: str = "Player",
    game_scope: str = "",
    player_scope: str = ""
) -> str:
    """
    Get homepage dashboard leaders.
    
    Args:
        season: Season.
        season_type: Season type.
        player_or_team: Player or team.
        game_scope: Game scope.
        player_scope: Player scope.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if not season:
            season = get_current_season()
        data = homepageleaders.HomePageLeaders(
            season=season, season_type_all_star=season_type, league_id="00",
            player_or_team=player_or_team, game_scope=game_scope, player_scope=player_scope
        )
        return f"# Homepage Leaders - {season}\n\n" + data.home_page_leaders.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['season']})
def get_ist_standings(season: Optional[str] = None, season_type: str = "IST") -> str:
    """
    Get In-Season Tournament standings.
    
    Args:
        season: Season.
        season_type: Season type.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if not season:
            season = get_current_season()
        data = iststandings.ISTStandings(season_year=season, season_type=season_type, league_id="00")
        return f"# IST Standings - {season}\n\n" + data.standings.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league', 'statistics']})
def get_league_leaders(
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    stat_category: str = "PTS",
    scope: str = "S"
) -> str:
    """
    Get league leaders for a stat category.
    
    Args:
        season: Season.
        season_type: Season type.
        per_mode: Per mode.
        stat_category: Stat category.
        scope: Scope.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if not season:
            season = get_current_season()
        data = leagueleaders.LeagueLeaders(
            season=season, season_type_all_star=season_type, per_mode_simple=per_mode,
            stat_category_abbreviation=stat_category, scope=scope, league_id="00"
        )
        return f"# League Leaders - {stat_category} ({season})\n\n" + data.league_leaders.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league', 'player', 'statistics']})
def get_league_dash_player_stats(
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base"
) -> str:
    """
    Get league dashboard player stats with filters.
    
    Args:
        season: Season.
        season_type: Season type.
        per_mode: Per mode.
        measure_type: Measure type.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if not season:
            season = get_current_season()
        data = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season, season_type_all_star=season_type, per_mode_detailed=per_mode,
            measure_type_detailed_defense=measure_type, league_id="00"
        )
        return f"# Player Stats - {season}\n\n" + data.league_dash_player_stats.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league', 'team', 'statistics']})
def get_league_dash_team_stats(
    team_name: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base"
) -> str:
    """
    Get league dashboard team stats.
    Date returned: TEAM_ID, TEAM_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, 
    AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, 
    FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, 
    BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS
    
    Args:
        team_name: Team name or abbreviation (e.g., "Lakers" or "LAL").
        season: Season.
        season_type: Season type.
        per_mode: Per mode.
        measure_type: Measure type.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        if not season:
            season = get_current_season()
        data = leaguedashteamstats.LeagueDashTeamStats(
            season=season, season_type_all_star=season_type, per_mode_detailed=per_mode,
            measure_type_detailed_defense=measure_type, league_id="00"
        )
        return f"# Team Stats - {season}\n\n" + data.league_dash_team_stats.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league', 'game']})
def get_league_game_finder(
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    player_or_team: str = "T",
    team_name: str = None,
    vs_team_name: str = None,
    game_id_only: bool = False
) -> str:
    """
    Find games and game performance stats using specified filters. The stats can be broken down by player or team, but it is not possible to filter by player.
    This can also be used to get game_ids, which are used by other tools
    
    Optional Args:
        season: Which season of play (e.g. "2025-26"). Defaults to current season.
        season_type: One of: "Regular Season", "Pre Season", "Playoffs", "All Star". Defaults to "Regular Season"
        team_name: Name of the team to filter by
        vs_team_name: Name of the opposing team to filter buy.
        player_or_team: P (for player) or T (for team). Useing P gives your player-specific stats breakdowns per game. T gives you team-level stats.
        game_id_only: True or False. If True, we'll only return the game_id column, which reduces the size of the returned payload. Defauts to False
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = None
        if team_name:
            team_id = find_team_id(team_name)
            if team_id is None:
                return f"Team '{team_name}' not found. Check spelling."
            
        vs_team_id = None
        if vs_team_name:
            vs_team_id = find_team_id(vs_team_name)
            if vs_team_id is None:
                return f"Team '{vs_team_name}' not found. Check spelling."
            
        if not season:
            season = get_current_season()
        data = leaguegamefinder.LeagueGameFinder(
            season_nullable=season, season_type_nullable=season_type,
            team_id_nullable=team_id, vs_team_id_nullable=vs_team_id,
            league_id_nullable="", player_or_team_abbreviation=player_or_team
        )
        if not game_id_only:
            return f"# Game Finder Results\n\n" + data.league_game_finder_results.get_data_frame().to_markdown(index=False)
        else:
            df = data.league_game_finder_results.get_data_frame()
            df = df[df.columns[:list(df.columns).index("GAME_ID")+1]] # drop all the stats columns after GAME_ID
            return f"# Game Finder Results\n\n" + df.to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league']})
def get_league_standings(season: Optional[str] = None, season_type: str = "Regular Season") -> str:
    """
    Get league standings.
    
    Args:
        season: Season.
        season_type: Season type.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if not season:
            season = get_current_season()
        data = leaguestandings.LeagueStandings(season=season, season_type=season_type, league_id="00")
        return f"# Standings - {season}\n\n" + data.standings.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['game']})
def get_scoreboard(game_date: str) -> str:
    """
    Get scoreboard for a specific date (format: YYYY-MM-DD or MM/DD/YYYY).
    
    Args:
        game_date: Game date.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        data = scoreboardv2.ScoreboardV2(game_date=game_date, league_id="00")
        result = f"# Scoreboard - {game_date}\n\n"
        result += "## Game Header\n" + data.game_header.get_data_frame().to_markdown(index=False) + "\n\n"
        result += "## Line Score\n" + data.line_score.get_data_frame().to_markdown(index=False) + "\n\n"
        return result
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['game']})
def get_play_by_play(game_id: str, start_period: int = 0, end_period: int = 10) -> str:
    """Get play-by-play data for a game."""
    try:
        data = playbyplayv2.PlayByPlayV2(game_id=game_id, start_period=start_period, end_period=end_period)
        return f"# Play by Play - {game_id}\n\n" + data.play_by_play.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player', 'statistics']})
def get_player_regular_season_stats(player_name: str, season_type: str = "Regular") -> str:
    """
    Get a player's complete regular season statistics broken down by season.
    Use this when the user asks for a player's historical performance in the regular season,
    season-by-season stats, or career data. Requires the player's exact
    full name (first and last name).
    Returns a markdown formatted table.
    
    Required Args:
        player_name: The player's full name (e.g., "LeBron James")
    Optional Args:
        season_type [default: Regular Season]: Any of: "Regular Season", "All Star", "Post Season", "College Season"
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    - per_mode36: Options appear to be Per36, PerGame, and Totals. Totals is derivable so I just defaulted to PerGame
    Other Notes:
    - This also returns season rankings, but only for the regular and post seasons, so I think these could be exposed via a separate funciton. 
    """
    try:
        player_id = find_player_id(player_name)
        if not player_id:
            return f"Player '{player_name}' not found."
        career_stats = playercareerstats.PlayerCareerStats(player_id=player_id, per_mode36="PerGame")
        # only return stats for the desired season type:
        if season_type == "All Star":
            career_stats = career_stats.season_totals_all_star_season
        if season_type == "Post Season":
            career_stats = career_stats.season_totals_post_season
        elif season_type == "College Season":
            career_stats = career_stats.season_totals_college_season
        else: # default to regular sseason
            season_type = "Regular Season" # just in case something illegal was provided
            career_stats = career_stats.season_totals_regular_season

        return f"{player_name} Career Stats for {season_type}\n\n" + career_stats.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player']})
def get_player_awards(player_name: str) -> str:
    """Get player awards and honors. Accepts player name."""
    try:
        player_id = find_player_id(player_name)
        if not player_id:
            return f"Player '{player_name}' not found."
        data = playerawards.PlayerAwards(player_id=player_id)
        return f"# Awards - {player_name}\n\n" + data.player_awards.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player', 'game']})
def get_player_game_log(player_name: str, season: Optional[str] = None, season_type: str = "Regular Season") -> str:
    """Get player game log for a season. Accepts player name."""
    try:
        player_id = find_player_id(player_name)
        if not player_id:
            return f"Player '{player_name}' not found."
        if not season:
            season = get_current_season()
        data = playergamelog.PlayerGameLog(player_id=player_id, season=season, season_type_all_star=season_type)
        return f"# Game Log - {player_name} ({season})\n\n" + data.player_game_log.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player']})
def get_player_profile(player_name: str, per_mode: str = "PerGame") -> str:
    """Get complete player profile. Accepts player name."""
    try:
        player_id = find_player_id(player_name)
        if not player_id:
            return f"Player '{player_name}' not found."
        data = playerprofilev2.PlayerProfileV2(player_id=player_id, per_mode_simple=per_mode)
        result = f"# Player Profile - {player_name}\n\n"
        result += "## Season Totals\n" + data.season_totals_regular_season.get_data_frame().to_markdown(index=False) + "\n\n"
        return result
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player']})
def get_player_vs_player(
    player_name1: str,
    player_name2: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame"
) -> str:
    """Compare two players head-to-head. Accepts player names."""
    try:
        player_id1 = find_player_id(player_name1)
        player_id2 = find_player_id(player_name2)
        if not player_id1:
            return f"Player '{player_name1}' not found."
        if not player_id2:
            return f"Player '{player_name2}' not found."
        if not season:
            season = get_current_season()
        data = playervsplayer.PlayerVsPlayer(
            player_id=player_id1, vs_player_id=player_id2, season=season,
            season_type_all_star=season_type, per_mode_simple=per_mode
        )
        return f"# {player_name1} vs {player_name2} - {season}\n\n" + data.overall.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['playoff']})
def get_playoff_picture(season: Optional[str] = None, season_type: str = "Regular Season") -> str:
    """
    Get current playoff picture/standings.
    
    Args:
        season: Season.
        season_type: Season type.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if not season:
            season = get_current_season()
        data = playoffpicture.PlayoffPicture(season_id=season, league_id="00")
        return f"# Playoff Picture - {season}\n\n" + data.playoff_picture.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player', 'shooting']})
def get_shot_chart(player_name: str, season: Optional[str] = None, season_type: str = "Regular Season") -> str:
    """Get shot chart data for a player. Accepts player name."""
    try:
        player_id = find_player_id(player_name)
        if not player_id:
            return f"Player '{player_name}' not found."
        if not season:
            season = get_current_season()
        data = shotchartdetail.ShotChartDetail(
            player_id=player_id, team_id=0, season_nullable=season,
            season_type_all_star=season_type, context_measure_simple="FGA"
        )
        return f"# Shot Chart - {player_name} ({season})\n\n" + data.shot_chart_detail.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['team']})
def get_team_details(team_name: str) -> str:
    """Get team trivia details and history. Data includes:
        TEAM_ID, ABBREVIATION, NICKNAME, YEARFOUNDED, CITY, ARENA,
        ARENACAPACITY, OWNER, GENERALMANAGER, HEADCOACH,
        DLEAGUEAFFILIATION
    
    Args:
        team_name: Team name.
    
    """
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        data = teamdetails.TeamDetails(team_id=team_id)
        result = f"# Team Details - {team_name}\n\n"
        result += "## Team Background\n" + data.team_background.get_data_frame().to_markdown(index=False) + "\n\n"
        result += "## Team History\n" + data.team_history.get_data_frame().to_markdown(index=False) + "\n\n"
        return result
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool(meta={"category": ['team']})
def get_team_info(team_name: str, season: Optional[str] = None) -> str:
    """
    Get team information. Accepts team name.
    
    Args:
        team_name: Team name.
        season: Season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        if not season:
            season = get_current_season()
        data = teaminfocommon.TeamInfoCommon(team_id=team_id, season_nullable=season, league_id="00")
        result = f"# Team Info - {team_name}\n\n"
        result += "## Team Info\n" + data.team_info_common.get_data_frame().to_markdown(index=False) + "\n\n"
        result += "## Season Ranks\n" + data.team_season_ranks.get_data_frame().to_markdown(index=False) + "\n\n"
        return result
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['team', 'player']})
def get_team_vs_player(
    team_name: str,
    player_name: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame"
) -> str:
    """Get team vs player matchup stats. Accepts team and player names."""
    try:
        team_id = find_team_id(team_name)
        player_id = find_player_id(player_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        if not player_id:
            return f"Player '{player_name}' not found."
        if not season:
            season = get_current_season()
        data = teamvsplayer.TeamVsPlayer(
            team_id=team_id, vs_player_id=player_id, season=season,
            season_type_all_star=season_type, per_mode_simple=per_mode
        )
        return f"# {team_name} vs {player_name} - {season}\n\n" + data.overall.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['game']})
def get_win_probability(game_id: str) -> str:
    """Get win probability play-by-play for a game."""
    try:
        data = winprobabilitypbp.WinProbabilityPBP(game_id=game_id)
        return f"# Win Probability - {game_id}\n\n" + data.win_prob_pbp.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


# Additional comprehensive endpoints with common parameter patterns
@mcp.tool(meta={"category": ['league', 'statistics']})
def get_league_dash_lineups(season: Optional[str] = None, season_type: str = "Regular Season", measure_type: str = "Base") -> str:
    """Get league lineup statistics."""
    try:
        if not season:
            season = get_current_season()
        data = leaguedashlineups.LeagueDashLineups(season=season, season_type_all_star=season_type, measure_type_detailed_defense=measure_type)
        return f"# Lineup Stats - {season}\n\n" + data.league_dash_lineups.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player', 'statistics']})
def get_player_clutch_stats(player_name: str, season: Optional[str] = None, per_mode: str = "PerGame") -> str:
    """Get player clutch performance stats. Accepts player name."""
    try:
        player_id = find_player_id(player_name)
        if not player_id:
            return f"Player '{player_name}' not found."
        if not season:
            season = get_current_season()
        data = playerdashboardbyclutch.PlayerDashboardByClutch(player_id=player_id, season=season, per_mode_detailed=per_mode)
        return f"# Clutch Stats - {player_name} ({season})\n\n" + data.overall_player_dashboard.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player', 'statistics']})
def get_player_shooting_splits(player_name: str, season: Optional[str] = None, per_mode: str = "PerGame") -> str:
    """Get player shooting splits by zone/distance. Accepts player name."""
    try:
        player_id = find_player_id(player_name)
        if not player_id:
            return f"Player '{player_name}' not found."
        if not season:
            season = get_current_season()
        data = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(player_id=player_id, season=season, per_mode_detailed=per_mode)
        return f"# Shooting Splits - {player_name} ({season})\n\n" + data.overall_player_dashboard.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['team', 'statistics']})
def get_team_clutch_stats(team_name: str, season: Optional[str] = None, per_mode: str = "PerGame") -> str:
    """Get team clutch performance stats. Accepts team name."""
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        if not season:
            season = get_current_season()
        data = leaguedashteamclutch.LeagueDashTeamClutch(season=season, season_type_all_star="Regular Season", per_mode_detailed=per_mode)
        df = data.league_dash_team_clutch.get_data_frame()
        team_data = df[df['TEAM_ID'] == team_id] if 'TEAM_ID' in df.columns else df
        return f"# Clutch Stats - {team_name} ({season})\n\n" + team_data.to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['team', 'statistics']})
def get_team_shooting_splits(team_name: str, season: Optional[str] = None, per_mode: str = "PerGame") -> str:
    """Get team shooting splits. Accepts team name."""
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        if not season:
            season = get_current_season()
        data = teamdashboardbyshootingsplits.TeamDashboardByShootingSplits(team_id=team_id, season=season, per_mode_detailed=per_mode)
        return f"# Shooting Splits - {team_name} ({season})\n\n" + data.overall_team_dashboard.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['team', 'statistics']})
def get_team_lineups(team_name: str, season: Optional[str] = None, measure_type: str = "Base") -> str:
    """Get team lineup statistics. Accepts team name."""
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        if not season:
            season = get_current_season()
        data = teamdashlineups.TeamDashLineups(team_id=team_id, season=season, measure_type_detailed_defense=measure_type)
        return f"# Lineups - {team_name} ({season})\n\n" + data.lineups.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['team', 'historical']})
def get_team_historical_leaders(team_name: str) -> str:
    """
    Get team all-time statistical leaders. Accepts team name.
    
    Args:
        team_name: Team name.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        data = teamhistoricalleaders.TeamHistoricalLeaders(team_id=team_id, league_id="00")
        return f"# Historical Leaders - {team_name}\n\n" + data.team_historical_leaders.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['team', 'statistics', 'historical']})
def get_team_year_by_year(team_name: str, per_mode: str = "PerGame") -> str:
    """
    Get team year-by-year stats. Accepts team name.
    
    Args:
        team_name: Team name.
        per_mode: Per mode.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        team_id = find_team_id(team_name)
        if not team_id:
            return f"Team '{team_name}' not found."
        data = teamyearbyyearstats.TeamYearByYearStats(team_id=team_id, league_id="00", per_mode_simple=per_mode)
        return f"# Year by Year - {team_name}\n\n" + data.team_stats.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player']})
def get_player_compare(
    player_names: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame"
) -> str:
    """Compare multiple players (comma-separated names)."""
    try:
        names = [n.strip() for n in player_names.split(',')]
        player_ids = []
        for name in names:
            pid = find_player_id(name)
            if pid:
                player_ids.append(str(pid))
        if not player_ids:
            return "No players found."
        if not season:
            season = get_current_season()
        data = playercompare.PlayerCompare(
            player_id_list=','.join(player_ids), vs_player_id_list='0',
            season=season, season_type_all_star=season_type, per_mode_simple=per_mode
        )
        return f"# Player Comparison - {season}\n\n" + data.overall_compare.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['season']})
def get_schedule(season: Optional[str] = None) -> str:
    """
    Get league schedule.
    
    Args:
        season: Season.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if not season:
            season = get_current_season()
        data = scheduleleaguev2.ScheduleLeagueV2(season=season, league_id="00")
        return f"# Schedule - {season}\n\n" + data.schedule.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


# Additional specialized endpoints
@mcp.tool(meta={"category": ['boxscore', 'game', 'tracking']})
def get_hustle_stats_boxscore(game_id: str) -> str:
    """Get hustle stats for a specific game (alternate endpoint)."""
    try:
        data = hustlestatsboxscore.HustleStatsBoxscore(game_id=game_id)
        return f"# Hustle Stats - {game_id}\n\n" + data.hustle_stats_boxscore.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league', 'player', 'tracking']})
def get_league_hustle_stats_player(season: Optional[str] = None, per_mode: str = "PerGame") -> str:
    """Get league-wide player hustle statistics."""
    try:
        if not season:
            season = get_current_season()
        data = leaguehustlestatsplayer.LeagueHustleStatsPlayer(season=season, per_mode_time=per_mode)
        return f"# Player Hustle Stats - {season}\n\n" + data.hustle_stats_player.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league', 'team', 'tracking']})
def get_league_hustle_stats_team(season: Optional[str] = None, per_mode: str = "PerGame") -> str:
    """Get league-wide team hustle statistics."""
    try:
        if not season:
            season = get_current_season()
        data = leaguehustlestatsteam.LeagueHustleStatsTeam(season=season, per_mode_time=per_mode)
        return f"# Team Hustle Stats - {season}\n\n" + data.hustle_stats_team.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['player', 'advanced']})
def get_player_estimated_metrics(season: Optional[str] = None) -> str:
    """Get player estimated advanced metrics."""
    try:
        if not season:
            season = get_current_season()
        data = playerestimatedmetrics.PlayerEstimatedMetrics(season=season)
        return f"# Player Estimated Metrics - {season}\n\n" + data.player_estimated_metrics.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['team', 'advanced']})
def get_team_estimated_metrics(season: Optional[str] = None) -> str:
    """Get team estimated advanced metrics."""
    try:
        if not season:
            season = get_current_season()
        data = teamestimatedmetrics.TeamEstimatedMetrics(season=season)
        return f"# Team Estimated Metrics - {season}\n\n" + data.team_estimated_metrics.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['advanced', 'statistics']})
def get_synergy_play_types(
    player_name: Optional[str] = None,
    team_name: Optional[str] = None,
    season: Optional[str] = None,
    season_type: str = "Regular Season"
) -> str:
    """Get Synergy play type statistics. Provide either player or team name."""
    try:
        if not season:
            season = get_current_season()
        
        player_id = 0
        team_id = 0
        entity_name = ""
        
        if player_name:
            player_id = find_player_id(player_name)
            if not player_id:
                return f"Player '{player_name}' not found."
            entity_name = player_name
        elif team_name:
            team_id = find_team_id(team_name)
            if not team_id:
                return f"Team '{team_name}' not found."
            entity_name = team_name
        else:
            return "Please provide either player_name or team_name."
        
        data = synergyplaytypes.SynergyPlayTypes(
            player_or_team="P" if player_name else "T",
            season=season, season_type=season_type,
            per_mode="PerGame", type_grouping="offensive"
        )
        return f"# Synergy Play Types - {entity_name} ({season})\n\n" + data.synergy_play_types.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['league', 'statistics']})
def get_matchups_rollup(season: Optional[str] = None, per_mode: str = "PerGame") -> str:
    """
    Get matchup statistics rollup.
    
    Args:
        season: Season.
        per_mode: Per mode.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        if not season:
            season = get_current_season()
        data = matchupsrollup.MatchupsRollup(league_id="00", season=season, per_mode_simple=per_mode)
        return f"# Matchups Rollup - {season}\n\n" + data.matchups.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['game', 'video']})
def get_video_events(game_id: str, game_event_id: Optional[int] = None) -> str:
    """Get video events for a game."""
    try:
        data = videoevents.VideoEvents(game_id=game_id, game_event_id=game_event_id or 0)
        return f"# Video Events - {game_id}\n\n" + data.video_events.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(meta={"category": ['game', 'video']})
def get_video_status(game_date: str) -> str:
    """
    Get video availability status for games on a date.
    
    Args:
        game_date: Game date.
    
    """
    """
    Hidden Parameters:
    - league_id: League ID ("00" for NBA).
    """
    try:
        data = videostatus.VideoStatus(game_date=game_date, league_id="00")
        return f"# Video Status - {game_date}\n\n" + data.video_status.get_data_frame().to_markdown(index=False)
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()

"""
DROPPED ENDPOINTS:
teamgamelog.TeamGameLog - I tried a few variations of this on 11/4/25 and all of them returned empty dataframes
cumestatsteam.CumeStatsTeam - This only returns the date of the game and the game id, no stats


"""