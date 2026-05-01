import pandas as pd

from dashboard.utils.db import run_query

def get_overview_metrics() -> dict:
    metrics = {}

    df = run_query("SELECT COUNT(*) as cnt FROM dim_match")
    metrics["total_matches"] = df["cnt"].iloc[0] if not df.empty else 0

    df = run_query("SELECT COUNT(*) as cnt FROM dim_player")
    metrics["total_players"] = df["cnt"].iloc[0] if not df.empty else 0

    df = run_query("SELECT COUNT(*) as cnt FROM dim_team WHERE is_active = TRUE")
    metrics["total_teams"] = df["cnt"].iloc[0] if not df.empty else 0

    df = run_query("SELECT COUNT(*) as cnt FROM fact_deliveries")
    metrics["total_deliveries"] = df["cnt"].iloc[0] if not df.empty else 0

    df = run_query("SELECT COALESCE(SUM(runs_total), 0) as total FROM fact_deliveries")
    metrics["total_runs"] = df["total"].iloc[0] if not df.empty else 0

    df = run_query("SELECT COUNT(*) as cnt FROM fact_deliveries WHERE is_wicket = TRUE")
    metrics["total_wickets"] = df["cnt"].iloc[0] if not df.empty else 0

    df = run_query("SELECT COUNT(*) as cnt FROM fact_deliveries WHERE is_boundary_six = TRUE")
    metrics["total_sixes"] = df["cnt"].iloc[0] if not df.empty else 0

    df = run_query("SELECT COUNT(*) as cnt FROM fact_deliveries WHERE is_boundary_four = TRUE")
    metrics["total_fours"] = df["cnt"].iloc[0] if not df.empty else 0

    return metrics

def get_season_summary(season: str = None) -> pd.DataFrame:
    where = f"WHERE dm.season = '{season}'" if season else ""
    query = f"""
        SELECT dm.season,
            COUNT(DISTINCT fd.match_key) as matches,
            SUM(fd.runs_total) as total_runs,
            SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as wickets,
            SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes,
            ROUND(AVG(fd.runs_total)::numeric, 2) as avg_runs_per_ball
        FROM fact_deliveries fd
        JOIN dim_match dm ON fd.match_key = dm.match_key
        {where}
        GROUP BY dm.season
        ORDER BY dm.season
    """
    return run_query(query)

def get_top_batsmen(season: str = None, limit: int = 10) -> pd.DataFrame:
    where = f"AND dm.season = '{season}'" if season else ""
    query = f"""
        SELECT dp.player_name,
            SUM(fd.runs_batsman) as total_runs,
            COUNT(DISTINCT fd.match_key) as matches,
            SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes,
            ROUND(SUM(fd.runs_batsman)::numeric /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0), 2) * 100 as strike_rate
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.batsman_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE fd.is_wide = FALSE {where}
        GROUP BY dp.player_name
        ORDER BY total_runs DESC
        LIMIT {limit}
    """
    return run_query(query)

def get_top_bowlers(season: str = None, limit: int = 10) -> pd.DataFrame:
    where = f"AND dm.season = '{season}'" if season else ""
    query = f"""
        SELECT dp.player_name,
            SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as wickets,
            COUNT(DISTINCT fd.match_key) as matches,
            ROUND(SUM(fd.runs_total)::numeric /
                NULLIF(SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END), 0), 2) as bowling_avg,
            ROUND(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END)::numeric /
                NULLIF(SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END), 0), 1) as strike_rate,
            ROUND(SUM(fd.runs_total)::numeric * 6 /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0), 2) as economy
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.bowler_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE 1=1 {where}
        GROUP BY dp.player_name
        HAVING SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) > 0
        ORDER BY wickets DESC
        LIMIT {limit}
    """
    return run_query(query)

def get_team_performance(team: str = None) -> pd.DataFrame:
    query = """
        SELECT dt.team_name,
            COUNT(*) as matches_played,
            SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END) as wins,
            COUNT(*) - SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END) as losses,
            ROUND(
                SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END)::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            ) as win_pct
        FROM fact_match_summary fms
        JOIN dim_team dt ON (fms.team1_key = dt.team_key OR fms.team2_key = dt.team_key)
        WHERE fms.result != 'no result'
        GROUP BY dt.team_name, dt.team_key
        ORDER BY win_pct DESC
    """
    df = run_query(query)
    if team and not df.empty:
        df = df[df["team_name"] == team]
    return df
