import pandas as pd
import numpy as np
from nba_api.stats.endpoints import leaguegamefinder, boxscoretraditionalv3, boxscoreadvancedv3
from nba_mcp_server.mcp_server import get_current_season, find_team_id
from tenacity import retry, stop_after_attempt, wait_exponential

# The code in this file is meant to collect data which will be fed into an LLM process. The principle is,
# rather than letting the LLM figure out how to make the correct sequence of API calls, we'll make them for it (when feasible).
# Define wait parameters for retrying nba API calls
wait_mult = 2
wait_min = 4
wait_max = 30
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=wait_mult, min=wait_min, max=wait_max))
def _get_box_advanced(game_id, team_id, columns, type):
    box_advanced = boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=game_id)
    box_advanced = box_advanced.team_stats.get_data_frame() if type == "T" else box_advanced.player_stats.get_data_frame()
    box_advanced = box_advanced[box_advanced['teamId'] == team_id]
    return box_advanced[columns]

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=wait_mult, min=wait_min, max=wait_max))
def _get_box_traditional(game_id, team_id, columns, type):
    box_traditional = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
    box_traditional = box_traditional.team_stats.get_data_frame() if type == "T" else box_traditional.player_stats.get_data_frame()
    box_traditional = box_traditional[box_traditional['teamId'] == team_id]
    return box_traditional[columns]

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=wait_mult, min=wait_min, max=wait_max))
def _get_game_record(team_id: str):
    #Get all the games in the current season for the designated team
    data = leaguegamefinder.LeagueGameFinder(
            season_nullable=get_current_season(), season_type_nullable="Regular Season",
            team_id_nullable=team_id,
            league_id_nullable="", player_or_team_abbreviation="T"
        )
    game_record = data.league_game_finder_results.get_data_frame()
    
    return game_record

def _get_team_performance_data(team_name):
    team_id = find_team_id(team_name)
    if team_id is None:
        raise ValueError(f"Team {team_name} not found.")
    # pull a record of all the games played by the target team this season
    game_record = _get_game_record(team_id)

    # defined the columns we'll be using from each data source we interact with
    game_record_columns = ["GAME_ID", "GAME_DATE","MATCHUP", "WL", "PTS", "FG_PCT", "FG3_PCT", "REB"]
    box_advanced_columns = ["offensiveRating", "defensiveRating", "netRating", "effectiveFieldGoalPercentage","trueShootingPercentage","pace","assistPercentage", "turnoverRatio"]

    team_data = []
    # for each game pull the target data from the boxscore api calls
    for _,row in game_record.iterrows():
        game_id = row.GAME_ID
        game_record_data = row[game_record_columns].values

        box_advanced = _get_box_advanced(game_id, team_id, box_advanced_columns, "T").values[0]

        team_data.append(np.concat([game_record_data, box_advanced]))

    return pd.DataFrame(team_data, columns = game_record_columns + box_advanced_columns)

def _create_matchup_dataframes(df1, df2, teamname1, teamname2):
    """
    Creates two-row dfs comparing the team performance in the same game
    """
    # Find the intersection of GAME_IDs between the two dataframes
    common_game_ids = pd.Series(list(set(df1['GAME_ID']) & set(df2['GAME_ID'])))

    if common_game_ids.empty:
        return []

    paired_dataframes = []
    for game_id in common_game_ids:
        # Get the row for the current game from each dataframe
        game_df1 = df1[df1['GAME_ID'] == game_id].copy()
        game_df2 = df2[df2['GAME_ID'] == game_id].copy()

        # add the neam name columns
        game_df1['TEAM_NAME'] = teamname1
        game_df2['TEAM_NAME'] = teamname2

        # Concatenate the two rows into a new dataframe
        combined_df = pd.concat([game_df1, game_df2], ignore_index=True)

        # Drop the game_id and matchup columns - the matchup is already known since the two rows in this df represent it. 
        # The game id is not necessary for the same reason.
        combined_df = combined_df.drop(columns=['MATCHUP', 'GAME_ID'])

        paired_dataframes.append(combined_df)

    return paired_dataframes

def get_team_performance(team1: str, team2: str):
    """
    The goal here is to provide a summary of the team's performance in the season so far. 
    Just dropping the tables into the chat for the writer seems like it won't work though, so either we need to pre-process this for narrative,
    or we need to do some other kind of LLM processing to help the writer.
    """
    team1_perf = _get_team_performance_data(team1)
    team2_perf = _get_team_performance_data(team2)
    # this will be provided as input to the LLM, so it needs to be formatted as a string
    output = f"""
        {team1} Performance stats:
        {team1_perf.to_markdown(index=False)}

        {team2} Performance stats:
        {team2_perf.to_markdown(index=False)}
        """

    # Create paired game dataframes (representing direct matchups between the teams)
    paired_dataframes = _create_matchup_dataframes(team1_perf, team2_perf, team1, team2)

    if len(paired_dataframes):
        output += "\nPrevious Matchups this Season:\n"
        for df in paired_dataframes:
            output += df.to_markdown(index=False) + "\n\n"
        

    return output


def _get_player_game_data(game_id: str, team_id: int):
    # we get some data from the advanced box score and some from traditional
    box_advanced_columns = ["playerSlug", "trueShootingPercentage", "usagePercentage", "assistPercentage", "turnoverRatio", "reboundPercentage", "offensiveRating", "defensiveRating", "netRating"]
    box_advanced = _get_box_advanced(game_id, team_id, box_advanced_columns, "P")

    box_traditional_columns = ["playerSlug", "minutes","points","reboundsTotal","assists","steals","blocks","threePointersPercentage","freeThrowsPercentage"]
    box_traditional = _get_box_traditional(game_id, team_id, box_traditional_columns, "P")

    # Merge the two dataframes on 'playerSlug' and return
    return pd.merge(box_advanced, box_traditional, on='playerSlug')

def _get_player_performance(team_name: str):
    "get the player performance stats for all players on a team"
    team_id = find_team_id(team_name)
    if team_id is None:
        raise ValueError(f"Team {team_name} not found.")

    game_record = _get_game_record(team_id)
    game_record = game_record[["GAME_ID","GAME_DATE","MATCHUP","WL"]]
    player_data = {}

    for _, row in game_record.iterrows():
        game_data = _get_player_game_data(row['GAME_ID'], team_id)
        for _, player_row in game_data.iterrows():
            player_slug = player_row['playerSlug']
            
            # Combine game info with player data
            combined_row = {
                **row.to_dict(),
                **player_row.to_dict()
            }
            
            if player_slug not in player_data:
                player_data[player_slug] = []
            player_data[player_slug].append(combined_row)

    # Create separate dataframes for each player
    player_dfs = {slug: pd.DataFrame(data).drop("playerSlug", axis=1) for slug, data in player_data.items()}

    return player_dfs

def get_player_performance(team1: str, team2: str):
    #get the player performance stats for all players on both teams
    team1_perf = _get_player_performance(team1)
    team2_perf = _get_player_performance(team2)

    # this will be provided as input to the LLM, so it needs to be formatted as a string
    output = f"{team1} players: \n"
    output += "\n".join([f"{slug}: {df.to_markdown(index=False)}" for slug, df in team1_perf.items()])
    output += f"\n{team2} players: \n"
    output += "\n".join([f"{slug}: {df.to_markdown(index=False)}" for slug, df in team2_perf.items()])

    return output   



def get_matchup_history(team1: str, team2: str):
    team1_id = find_team_id(team1)
    if team1_id is None:
        raise ValueError(f"Team {team1} not found.")

    team2_id = find_team_id(team2)
    if team2_id is None:
        raise ValueError(f"Team {team2} not found.")
    
    # get match records for each team 
    data = leaguegamefinder.LeagueGameFinder(
        season_type_nullable="Regular Season",
        team_id_nullable=team1_id,
        league_id_nullable="", player_or_team_abbreviation="T"
    )
    team1_record = data.league_game_finder_results.get_data_frame()

    data = leaguegamefinder.LeagueGameFinder(
        season_type_nullable="Regular Season",
        team_id_nullable=team2_id,
        league_id_nullable="", player_or_team_abbreviation="T"
    )
    team2_record = data.league_game_finder_results.get_data_frame()

    # merge the match records to find the matchups 
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=3*365)
    team1_recent = team1_record[pd.to_datetime(team1_record['GAME_DATE']) >= cutoff]
    team2_recent = team2_record[pd.to_datetime(team2_record['GAME_DATE']) >= cutoff]
    matchups = team1_recent[team1_recent['GAME_ID'].isin(team2_recent['GAME_ID'])]
    wins = (matchups['WL'] == 'W').sum()
    losses = (matchups['WL'] == 'L').sum()

    return f"{team1} vs {team2}: {wins} wins, {losses} losses"
