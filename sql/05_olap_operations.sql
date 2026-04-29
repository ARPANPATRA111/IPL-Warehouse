SELECT
    COALESCE(d.season, 'ALL SEASONS') AS season,
    COALESCE(t.team_name, 'ALL TEAMS') AS team,
    SUM(fd.runs_batsman) AS total_runs,
    COUNT(DISTINCT fd.match_key) AS matches,
    ROUND(SUM(fd.runs_batsman)::DECIMAL / NULLIF(COUNT(DISTINCT fd.match_key), 0), 1) AS avg_runs_per_match
FROM fact_deliveries fd
JOIN dim_date d ON fd.date_key = d.date_key
JOIN dim_team t ON fd.batting_team_key = t.team_key
WHERE fd.is_super_over = FALSE
GROUP BY ROLLUP(d.season, t.team_name)
ORDER BY season NULLS LAST, team NULLS LAST;

SELECT
    COALESCE(d.season, 'ALL') AS season,
    COALESCE(p.player_name, 'ALL BOWLERS') AS bowler,
    COALESCE(fd.dismissal_type, 'ALL TYPES') AS dismissal_type,
    COUNT(*) AS wickets
FROM fact_deliveries fd
JOIN dim_date d ON fd.date_key = d.date_key
JOIN dim_player p ON fd.bowler_key = p.player_key
WHERE fd.is_wicket = TRUE
    AND fd.dismissal_type NOT IN ('run out', 'retired hurt', 'retired out')
GROUP BY ROLLUP(d.season, p.player_name, fd.dismissal_type)
ORDER BY season NULLS LAST, bowler NULLS LAST, wickets DESC;

SELECT
    d.season,
    t.team_name,
    SUM(fd.runs_total) AS total_runs,
    COUNT(DISTINCT fd.match_key) AS matches,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes
FROM fact_deliveries fd
JOIN dim_date d ON fd.date_key = d.date_key
JOIN dim_team t ON fd.batting_team_key = t.team_key
WHERE t.team_name = 'Mumbai Indians'
GROUP BY d.season, t.team_name
ORDER BY d.season;

SELECT
    m.match_id,
    d.full_date,
    t.team_name AS opponent,
    SUM(fd.runs_total) AS total_runs,
    MAX(fd.cumulative_wickets) AS wickets_lost,
    SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) AS fours,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes
FROM fact_deliveries fd
JOIN dim_date d ON fd.date_key = d.date_key
JOIN dim_match m ON fd.match_key = m.match_key
JOIN dim_team t ON fd.bowling_team_key = t.team_key
WHERE fd.batting_team_key = (SELECT team_key FROM dim_team WHERE team_name = 'Mumbai Indians')
    AND d.season = '2023'
GROUP BY m.match_id, d.full_date, t.team_name
ORDER BY d.full_date;

SELECT
    fd.innings_number,
    fd.over_number + 1 AS over_display,
    SUM(fd.runs_total) AS runs_in_over,
    SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) AS wickets_in_over,
    SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) AS fours,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes,
    MAX(fd.cumulative_runs) AS cumulative_total
FROM fact_deliveries fd
JOIN dim_match m ON fd.match_key = m.match_key
WHERE m.match_id = '1082591'
    AND fd.innings_number = 1
GROUP BY fd.innings_number, fd.over_number
ORDER BY fd.over_number;

SELECT
    fd.ball_number + 1 AS ball,
    p_bat.player_name AS batsman,
    p_bowl.player_name AS bowler,
    fd.runs_batsman,
    fd.runs_extras,
    fd.runs_total,
    fd.extras_type,
    fd.is_wicket,
    fd.dismissal_type,
    fd.cumulative_runs
FROM fact_deliveries fd
JOIN dim_player p_bat ON fd.batsman_key = p_bat.player_key
JOIN dim_player p_bowl ON fd.bowler_key = p_bowl.player_key
JOIN dim_match m ON fd.match_key = m.match_key
WHERE m.match_id = '1082591'
    AND fd.innings_number = 1
    AND fd.over_number = 0
ORDER BY fd.ball_number;

SELECT
    v.venue_name,
    d.season,
    COUNT(DISTINCT fd.match_key) AS matches_played,
    SUM(fd.runs_total) AS total_runs,
    ROUND(SUM(fd.runs_total)::DECIMAL / NULLIF(COUNT(DISTINCT fd.match_key), 0), 1) AS avg_score,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes
FROM fact_deliveries fd
JOIN dim_team t ON fd.batting_team_key = t.team_key
JOIN dim_venue v ON fd.venue_key = v.venue_key
JOIN dim_date d ON fd.date_key = d.date_key
WHERE t.team_name = 'Mumbai Indians'
    AND fd.is_super_over = FALSE
GROUP BY v.venue_name, d.season
ORDER BY d.season DESC, avg_score DESC;

SELECT
    t.team_name,
    COUNT(DISTINCT fd.match_key) AS matches,
    SUM(fd.runs_total) AS total_runs,
    ROUND(
        SUM(fd.runs_batsman)::DECIMAL * 100.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS strike_rate,
    SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) AS wickets_lost
FROM fact_deliveries fd
JOIN dim_team t ON fd.batting_team_key = t.team_key
JOIN dim_venue v ON fd.venue_key = v.venue_key
WHERE v.venue_name LIKE '%Wankhede%'
    AND fd.is_super_over = FALSE
GROUP BY t.team_name
ORDER BY total_runs DESC;

SELECT
    d.season,
    v.city,
    t.team_name,
    SUM(fd.runs_total) AS powerplay_runs,
    SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) AS powerplay_wickets,
    ROUND(
        SUM(fd.runs_total)::DECIMAL * 6.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS run_rate,
    SUM(CASE WHEN fd.is_boundary_four OR fd.is_boundary_six THEN 1 ELSE 0 END) AS boundaries
FROM fact_deliveries fd
JOIN dim_date d ON fd.date_key = d.date_key
JOIN dim_venue v ON fd.venue_key = v.venue_key
JOIN dim_team t ON fd.batting_team_key = t.team_key
WHERE d.year BETWEEN 2020 AND 2023
    AND v.city IN ('Mumbai', 'Chennai')
    AND fd.over_number BETWEEN 0 AND 5
    AND fd.is_super_over = FALSE
GROUP BY d.season, v.city, t.team_name
ORDER BY d.season, v.city, powerplay_runs DESC;

SELECT
    p.player_name,
    bowl_t.team_name AS bowling_team,
    SUM(fd.runs_batsman) AS death_runs,
    SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) AS balls_faced,
    ROUND(
        SUM(fd.runs_batsman)::DECIMAL * 100.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS death_strike_rate,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes
FROM fact_deliveries fd
JOIN dim_player p ON fd.batsman_key = p.player_key
JOIN dim_team bowl_t ON fd.bowling_team_key = bowl_t.team_key
JOIN dim_date d ON fd.date_key = d.date_key
WHERE fd.over_number BETWEEN 15 AND 19
    AND d.year >= 2020
    AND bowl_t.team_name IN ('Mumbai Indians', 'Chennai Super Kings', 'Royal Challengers Bangalore')
GROUP BY p.player_name, bowl_t.team_name
HAVING SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) >= 20
ORDER BY death_strike_rate DESC
LIMIT 20;

SELECT
    t.team_name,
    SUM(CASE WHEN fms.season = '2017' AND fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins_2017,
    SUM(CASE WHEN fms.season = '2018' AND fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins_2018,
    SUM(CASE WHEN fms.season = '2019' AND fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins_2019,
    SUM(CASE WHEN fms.season = '2020' AND fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins_2020,
    SUM(CASE WHEN fms.season = '2021' AND fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins_2021,
    SUM(CASE WHEN fms.season = '2022' AND fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins_2022,
    SUM(CASE WHEN fms.season = '2023' AND fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins_2023,
    SUM(CASE WHEN fms.season = '2024' AND fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins_2024,
    SUM(CASE WHEN fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS total_wins
FROM fact_match_summary fms
JOIN dim_team t ON t.team_key IN (fms.team1_key, fms.team2_key)
GROUP BY t.team_name
ORDER BY total_wins DESC;

SELECT
    fd.dismissal_type,
    SUM(CASE WHEN d.season = '2020' THEN 1 ELSE 0 END) AS count_2020,
    SUM(CASE WHEN d.season = '2021' THEN 1 ELSE 0 END) AS count_2021,
    SUM(CASE WHEN d.season = '2022' THEN 1 ELSE 0 END) AS count_2022,
    SUM(CASE WHEN d.season = '2023' THEN 1 ELSE 0 END) AS count_2023,
    SUM(CASE WHEN d.season = '2024' THEN 1 ELSE 0 END) AS count_2024,
    COUNT(*) AS total
FROM fact_deliveries fd
JOIN dim_date d ON fd.date_key = d.date_key
WHERE fd.is_wicket = TRUE AND fd.dismissal_type IS NOT NULL
GROUP BY fd.dismissal_type
ORDER BY total DESC;

SELECT
    COALESCE(t.team_name, 'ALL TEAMS') AS team,
    COALESCE(d.season, 'ALL SEASONS') AS season,
    SUM(fd.runs_total) AS total_runs,
    COUNT(DISTINCT fd.match_key) AS matches,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS total_sixes,
    GROUPING(t.team_name) AS is_team_total,
    GROUPING(d.season) AS is_season_total
FROM fact_deliveries fd
JOIN dim_team t ON fd.batting_team_key = t.team_key
JOIN dim_date d ON fd.date_key = d.date_key
WHERE fd.is_super_over = FALSE
GROUP BY GROUPING SETS (
    (t.team_name, d.season),
    (t.team_name),
    (d.season),
    ()
)
ORDER BY is_team_total, is_season_total, team, season;
