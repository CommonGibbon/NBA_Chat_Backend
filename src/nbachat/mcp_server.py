from mcp.server.fastmcp import FastMCP

from nba_api.stats.endpoints import playercareerstats
from nba_api.stats.static import players

mcp = FastMCP("nba-chat")

@mcp.tool()
def get_player_season_stats(player_name: str) -> str:
    """
    Get a player's complete career statistics broken down by season.
    Use this when the user asks for a player's historical performance,
    season-by-season stats, or career data. Requires the player's exact
    full name (first and last name).
    Returns a markdown formatted table.
    
    Args:
        player_name: The player's full name (e.g., "LeBron James")
    """
    try:
        players_found = players.find_players_by_full_name(player_name)
        if not players_found:
            return f"Player '{player_name}' not found. Check the exact name spelling."
        
        player_info = players_found[0]
        player_id = player_info['id']
        
        career_stats = playercareerstats.PlayerCareerStats(player_id=player_id).get_data_frames()[0]
        return career_stats.to_markdown(index=False)
    
    except Exception as e:
        return f"Error retrieving stats for {player_name}: {str(e)}"
    
if __name__ == "__main__":
    mcp.run()
