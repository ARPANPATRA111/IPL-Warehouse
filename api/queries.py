import re
from typing import Any

from api.cache import ttl_cache
from api.db import run_query, run_records, run_scalar

PLAYER_NAME_NORMALIZED_SQL = "regexp_replace(lower(player_name), '[^a-z0-9]', '', 'g')"

def _normalize_player_search_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())

def _build_player_search_terms(search: str) -> dict[str, str]:
    stripped_search = search.strip()
    tokens = [token for token in re.findall(r"[a-z0-9]+", stripped_search.lower()) if token]
    normalized_exact = _normalize_player_search_text(stripped_search)
    surname = tokens[-1] if tokens else ""
    initial_surname = ""

    if len(tokens) >= 2:
        initial_surname = "".join(token[0] for token in tokens[:-1]) + surname

    return {
        "contains_search": f"%{stripped_search}%",
        "normalized_exact": normalized_exact,
        "normalized_contains": f"%{normalized_exact}%" if normalized_exact else "",
        "initial_surname": initial_surname,
        "initial_surname_prefix": f"{initial_surname}%" if initial_surname else "",
        "surname_contains": f"%{surname}%" if surname else "",
    }

def resolve_player_name(search: str) -> str | None:
    if not search.strip():
        return None

    matches = get_players(search)
    return matches[0] if matches else None

def _season_clause(seasons: list[str], alias: str) -> tuple[str, dict[str, Any], list[str]]:
    if not seasons:
        return "", {}, []
    return f" AND {alias}.season IN :seasons", {"seasons": seasons}, ["seasons"]

def _venue_clause(venues: list[str], alias: str) -> tuple[str, dict[str, Any], list[str]]:
    if not venues:
        return "", {}, []
    return f" AND {alias}.venue_name IN :venues", {"venues": venues}, ["venues"]

@ttl_cache(max_entries=16)
def get_reference_options() -> dict[str, list[str]]:
    seasons_df = run_query("SELECT DISTINCT season FROM dim_match ORDER BY season DESC")
    teams_df = run_query(
        "SELECT team_name FROM dim_team WHERE is_active = TRUE ORDER BY team_name"
    )
    venues_df = run_query("SELECT venue_name FROM dim_venue ORDER BY venue_name")

    return {
        "seasons": seasons_df["season"].tolist() if not seasons_df.empty else [],
        "teams": teams_df["team_name"].tolist() if not teams_df.empty else [],
        "venues": venues_df["venue_name"].tolist() if not venues_df.empty else [],
    }

def get_players(search: str = "") -> list[str]:
    if search:
        search_terms = _build_player_search_terms(search)
        df = run_query(
            """
            WITH candidates AS (
                SELECT player_name,
                    total_matches,
                    regexp_replace(lower(player_name), '[^a-z0-9]', '', 'g') as normalized_name
                FROM dim_player
            )
            SELECT player_name
            FROM candidates
            WHERE player_name ILIKE :contains_search
                OR (:normalized_exact <> '' AND normalized_name = :normalized_exact)
                OR (:normalized_contains <> '' AND normalized_name LIKE :normalized_contains)
                OR (:initial_surname <> '' AND normalized_name = :initial_surname)
                OR (:initial_surname_prefix <> '' AND normalized_name LIKE :initial_surname_prefix)
                OR (:surname_contains <> '' AND player_name ILIKE :surname_contains)
            ORDER BY
                CASE
                    WHEN :normalized_exact <> '' AND normalized_name = :normalized_exact THEN 0
                    WHEN :initial_surname <> '' AND normalized_name = :initial_surname THEN 1
                    WHEN player_name ILIKE :contains_search THEN 2
                    WHEN :initial_surname_prefix <> '' AND normalized_name LIKE :initial_surname_prefix THEN 3
                    WHEN :surname_contains <> '' AND player_name ILIKE :surname_contains THEN 4
                    ELSE 5
                END,
                total_matches DESC,
                player_name
            LIMIT 50
            """,
            params=search_terms,
        )
    else:
        df = run_query(
            "SELECT player_name FROM dim_player ORDER BY total_matches DESC LIMIT 100"
        )
    return df["player_name"].tolist() if not df.empty else []

@ttl_cache(max_entries=8)
def get_home_dashboard() -> dict[str, Any]:
    metrics = {
        "total_matches": int(run_scalar("SELECT COUNT(*) FROM dim_match", default=0) or 0),
        "total_players": int(run_scalar("SELECT COUNT(*) FROM dim_player", default=0) or 0),
        "total_teams": int(
            run_scalar("SELECT COUNT(*) FROM dim_team WHERE is_active = TRUE", default=0) or 0
        ),
        "total_deliveries": int(run_scalar("SELECT COUNT(*) FROM fact_deliveries", default=0) or 0),
        "total_runs": int(
            run_scalar("SELECT COALESCE(SUM(runs_total), 0) FROM fact_deliveries", default=0) or 0
        ),
        "total_wickets": int(
            run_scalar("SELECT COUNT(*) FROM fact_deliveries WHERE is_wicket = TRUE", default=0) or 0
        ),
        "total_sixes": int(
            run_scalar("SELECT COUNT(*) FROM fact_deliveries WHERE is_boundary_six = TRUE", default=0) or 0
        ),
        "total_fours": int(
            run_scalar("SELECT COUNT(*) FROM fact_deliveries WHERE is_boundary_four = TRUE", default=0) or 0
        ),
    }

    season_summary = run_records(
        """
        SELECT dm.season,
            COUNT(DISTINCT fd.match_key) as matches,
            SUM(fd.runs_total) as total_runs,
            SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as wickets,
            SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes,
            ROUND(AVG(fd.runs_total)::numeric, 2) as avg_runs_per_ball
        FROM fact_deliveries fd
        JOIN dim_match dm ON fd.match_key = dm.match_key
        GROUP BY dm.season
        ORDER BY dm.season
        """
    )

    top_batsmen = run_records(
        """
        SELECT dp.player_name,
            SUM(fd.runs_batsman) as total_runs,
            COUNT(DISTINCT fd.match_key) as matches,
            SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes,
            ROUND(
                SUM(fd.runs_batsman)::numeric /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
                2
            ) * 100 as strike_rate
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.batsman_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE fd.is_wide = FALSE
        GROUP BY dp.player_name
        ORDER BY total_runs DESC
        LIMIT 10
        """
    )

    top_bowlers = run_records(
        """
        SELECT dp.player_name,
            SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as wickets,
            COUNT(DISTINCT fd.match_key) as matches,
            ROUND(
                SUM(fd.runs_total)::numeric /
                NULLIF(SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END), 0),
                2
            ) as bowling_avg,
            ROUND(
                SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END)::numeric /
                NULLIF(SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END), 0),
                1
            ) as strike_rate,
            ROUND(
                SUM(fd.runs_total)::numeric * 6 /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
                2
            ) as economy
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.bowler_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        GROUP BY dp.player_name
        HAVING SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) > 0
        ORDER BY wickets DESC
        LIMIT 10
        """
    )

    return {
        "metrics": metrics,
        "season_summary": season_summary,
        "top_batsmen": top_batsmen,
        "top_bowlers": top_bowlers,
    }

@ttl_cache(max_entries=64)
def get_batting_dashboard(seasons: list[str]) -> dict[str, Any]:
    season_clause, params, expanding = _season_clause(seasons, "dm")
    leaderboard = run_records(
        f"""
        SELECT dp.player_name,
            SUM(fd.runs_batsman) as total_runs,
            COUNT(DISTINCT fd.match_key) as innings,
            SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes,
            ROUND(
                SUM(fd.runs_batsman)::numeric * 100 /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
                2
            ) as strike_rate,
            ROUND(
                SUM(fd.runs_batsman)::numeric /
                NULLIF(COUNT(DISTINCT fd.match_key), 0),
                2
            ) as avg_per_match
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.batsman_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE fd.is_wide = FALSE{season_clause}
        GROUP BY dp.player_name
        HAVING SUM(fd.runs_batsman) > 100
        ORDER BY total_runs DESC
        LIMIT 25
        """,
        params=params,
        expanding=expanding,
    )
    return {"leaderboard": leaderboard}

@ttl_cache(max_entries=128)
def get_batting_player_profile(player: str) -> dict[str, Any]:
    resolved_player = resolve_player_name(player) or player
    return {
        "player_name": resolved_player,
        "seasons": run_records(
        """
        SELECT dm.season,
            SUM(fd.runs_batsman) as runs,
            COUNT(DISTINCT fd.match_key) as matches,
            SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes,
            ROUND(
                SUM(fd.runs_batsman)::numeric * 100 /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
                2
            ) as sr
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.batsman_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE dp.player_name = :player AND fd.is_wide = FALSE
        GROUP BY dm.season
        ORDER BY dm.season
        """,
            params={"player": resolved_player},
        ),
    }

@ttl_cache(max_entries=64)
def get_bowling_dashboard(seasons: list[str]) -> dict[str, Any]:
    season_clause, params, expanding = _season_clause(seasons, "dm")
    leaderboard = run_records(
        f"""
        SELECT dp.player_name,
            SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as wickets,
            COUNT(DISTINCT fd.match_key) as matches,
            ROUND(
                SUM(fd.runs_total)::numeric /
                NULLIF(SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END), 0),
                2
            ) as avg,
            ROUND(
                SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END)::numeric /
                NULLIF(SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END), 0),
                1
            ) as strike_rate,
            ROUND(
                SUM(fd.runs_total)::numeric * 6 /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
                2
            ) as economy,
            SUM(CASE WHEN fd.is_dot_ball THEN 1 ELSE 0 END) as dot_balls
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.bowler_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE 1 = 1{season_clause}
        GROUP BY dp.player_name
        HAVING SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) > 5
        ORDER BY wickets DESC
        LIMIT 25
        """,
        params=params,
        expanding=expanding,
    )
    return {"leaderboard": leaderboard}

@ttl_cache(max_entries=128)
def get_bowling_player_profile(player: str) -> dict[str, Any]:
    resolved_player = resolve_player_name(player) or player
    return {
        "player_name": resolved_player,
        "seasons": run_records(
        """
        SELECT dm.season,
            SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as wickets,
            COUNT(DISTINCT fd.match_key) as matches,
            ROUND(
                SUM(fd.runs_total)::numeric * 6 /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
                2
            ) as economy,
            SUM(CASE WHEN fd.is_dot_ball THEN 1 ELSE 0 END) as dots
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.bowler_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE dp.player_name = :player
        GROUP BY dm.season
        ORDER BY dm.season
        """,
            params={"player": resolved_player},
        ),
    }

@ttl_cache(max_entries=16)
def get_team_overview() -> list[dict[str, Any]]:
    return run_records(
        """
        SELECT dt.team_name,
            COUNT(*) as matches_played,
            SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END) as wins,
            COUNT(*) - SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END) as losses,
            ROUND(
                SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END)::numeric /
                NULLIF(COUNT(*), 0) * 100,
                1
            ) as win_pct
        FROM fact_match_summary fms
        JOIN dim_team dt ON (fms.team1_key = dt.team_key OR fms.team2_key = dt.team_key)
        WHERE fms.result != 'no result'
        GROUP BY dt.team_name, dt.team_key
        ORDER BY win_pct DESC
        """
    )

@ttl_cache(max_entries=64)
def get_team_detail(team: str, seasons: list[str]) -> dict[str, Any]:
    season_clause, params, expanding = _season_clause(seasons, "fms")
    params["team"] = team

    season_performance = run_records(
        f"""
        SELECT fms.season,
            COUNT(*) as matches,
            SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END) as wins,
            ROUND(
                SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END)::numeric /
                NULLIF(COUNT(*), 0) * 100,
                1
            ) as win_pct
        FROM fact_match_summary fms
        JOIN dim_team dt ON (fms.team1_key = dt.team_key OR fms.team2_key = dt.team_key)
        WHERE dt.team_name = :team AND fms.result != 'no result'{season_clause}
        GROUP BY fms.season, dt.team_key
        ORDER BY fms.season
        """,
        params=params,
        expanding=expanding,
    )

    toss_analysis = run_records(
        f"""
        SELECT fms.toss_decision,
            COUNT(*) as times,
            SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END) as wins
        FROM fact_match_summary fms
        JOIN dim_team dt ON fms.toss_winner_key = dt.team_key
        WHERE dt.team_name = :team{season_clause}
        GROUP BY fms.toss_decision
        """,
        params=params,
        expanding=expanding,
    )

    return {
        "season_performance": season_performance,
        "toss_analysis": toss_analysis,
    }

@ttl_cache(max_entries=64)
def get_venue_dashboard(seasons: list[str], venues: list[str]) -> dict[str, Any]:
    season_clause, season_params, season_expanding = _season_clause(seasons, "dm")
    venue_clause, venue_params, venue_expanding = _venue_clause(venues, "dv")
    params = {**season_params, **venue_params}
    expanding = [*season_expanding, *venue_expanding]

    venue_stats = run_records(
        f"""
        SELECT dv.venue_name,
            dv.city,
            COUNT(DISTINCT fd.match_key) as matches,
            ROUND(
                AVG(fd.runs_total)::numeric * 6 /
                NULLIF(AVG(CASE WHEN fd.is_legal_delivery THEN 1.0 ELSE NULL END), 0),
                2
            ) as avg_run_rate,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as total_sixes,
            SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as total_wickets,
            ROUND(
                SUM(CASE WHEN fd.is_boundary_four OR fd.is_boundary_six THEN 1 ELSE 0 END)::numeric * 100 /
                NULLIF(COUNT(*), 0),
                2
            ) as boundary_pct
        FROM fact_deliveries fd
        JOIN dim_venue dv ON fd.venue_key = dv.venue_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE 1 = 1{season_clause}{venue_clause}
        GROUP BY dv.venue_name, dv.city
        HAVING COUNT(DISTINCT fd.match_key) >= 3
        ORDER BY matches DESC
        """,
        params=params,
        expanding=expanding,
    )

    chase_stats = run_records(
        f"""
        SELECT dv.venue_name,
            COUNT(*) as total_matches,
            SUM(CASE WHEN fms.win_type = 'runs' THEN 1 ELSE 0 END) as bat_first_wins,
            SUM(CASE WHEN fms.win_type = 'wickets' THEN 1 ELSE 0 END) as chase_wins,
            ROUND(
                SUM(CASE WHEN fms.win_type = 'wickets' THEN 1 ELSE 0 END)::numeric * 100 /
                NULLIF(COUNT(*), 0),
                1
            ) as chase_win_pct
        FROM fact_match_summary fms
        JOIN dim_venue dv ON fms.venue_key = dv.venue_key
        JOIN dim_match dm ON fms.match_key = dm.match_key
        WHERE fms.result = 'normal'{season_clause}{venue_clause}
        GROUP BY dv.venue_name
        HAVING COUNT(*) >= 5
        ORDER BY chase_win_pct DESC
        """,
        params=params,
        expanding=expanding,
    )

    return {
        "venue_stats": venue_stats,
        "chase_stats": chase_stats,
    }

@ttl_cache(max_entries=64)
def get_head_to_head(team1: str, team2: str, seasons: list[str]) -> dict[str, Any]:
    season_clause, season_params, season_expanding = _season_clause(seasons, "fms")
    params = {**season_params, "team1": team1, "team2": team2}

    overall_rows = run_records(
        f"""
        SELECT
            COUNT(*) as total_matches,
            SUM(CASE WHEN fms.match_winner_key = t1.team_key THEN 1 ELSE 0 END) as team1_wins,
            SUM(CASE WHEN fms.match_winner_key = t2.team_key THEN 1 ELSE 0 END) as team2_wins,
            SUM(CASE WHEN fms.result = 'no result' THEN 1 ELSE 0 END) as no_result
        FROM fact_match_summary fms
        JOIN dim_team t1 ON t1.team_name = :team1
        JOIN dim_team t2 ON t2.team_name = :team2
        WHERE (
            (fms.team1_key = t1.team_key AND fms.team2_key = t2.team_key) OR
            (fms.team1_key = t2.team_key AND fms.team2_key = t1.team_key)
        ){season_clause}
        """,
        params=params,
        expanding=season_expanding,
    )

    season_breakdown = run_records(
        f"""
        SELECT fms.season,
            COUNT(*) as matches,
            SUM(CASE WHEN fms.match_winner_key = t1.team_key THEN 1 ELSE 0 END) as team1_wins,
            SUM(CASE WHEN fms.match_winner_key = t2.team_key THEN 1 ELSE 0 END) as team2_wins
        FROM fact_match_summary fms
        JOIN dim_team t1 ON t1.team_name = :team1
        JOIN dim_team t2 ON t2.team_name = :team2
        WHERE (
            (fms.team1_key = t1.team_key AND fms.team2_key = t2.team_key) OR
            (fms.team1_key = t2.team_key AND fms.team2_key = t1.team_key)
        ){season_clause}
        GROUP BY fms.season
        ORDER BY fms.season
        """,
        params=params,
        expanding=season_expanding,
    )

    performers = run_records(
        """
        SELECT dp.player_name,
            SUM(fd.runs_batsman) as runs,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.batsman_key = dp.player_key
        JOIN dim_team t1 ON t1.team_name = :team1
        JOIN dim_team t2 ON t2.team_name = :team2
        WHERE (
            (fd.batting_team_key = t1.team_key AND fd.bowling_team_key = t2.team_key) OR
            (fd.batting_team_key = t2.team_key AND fd.bowling_team_key = t1.team_key)
        ) AND fd.is_wide = FALSE
        GROUP BY dp.player_name
        ORDER BY runs DESC
        LIMIT 10
        """,
        params={"team1": team1, "team2": team2},
    )

    overall = overall_rows[0] if overall_rows else {
        "total_matches": 0,
        "team1_wins": 0,
        "team2_wins": 0,
        "no_result": 0,
    }

    return {
        "overall": overall,
        "season_breakdown": season_breakdown,
        "performers": performers,
    }

def warm_analytics_cache() -> dict[str, str]:
    warmed: dict[str, str] = {}

    get_reference_options()
    warmed["reference_options"] = "ok"

    get_home_dashboard()
    warmed["home_dashboard"] = "ok"

    get_batting_dashboard([])
    warmed["batting_dashboard"] = "ok"

    get_bowling_dashboard([])
    warmed["bowling_dashboard"] = "ok"

    get_team_overview()
    warmed["team_overview"] = "ok"

    get_venue_dashboard([], [])
    warmed["venue_dashboard"] = "ok"

    return warmed
