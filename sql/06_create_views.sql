CREATE MATERIALIZED VIEW IF NOT EXISTS mv_player_batting_stats AS
SELECT
    p.player_key,
    p.player_name,
    p.player_id,
    COUNT(DISTINCT fd.match_key) AS matches,
    COUNT(DISTINCT CONCAT(fd.match_key, '-', fd.innings_number)) AS innings,
    SUM(fd.runs_batsman) AS total_runs,
    SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) AS balls_faced,
    ROUND(
        SUM(fd.runs_batsman)::DECIMAL * 100.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS strike_rate,
    SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) AS fours,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes,
    SUM(CASE WHEN fd.is_dot_ball AND fd.batsman_key = fd.batsman_key THEN 1 ELSE 0 END) AS dot_balls_faced,
    MAX(sub.highest_score) AS highest_score
FROM fact_deliveries fd
JOIN dim_player p ON fd.batsman_key = p.player_key
LEFT JOIN (
    SELECT
        batsman_key,
        MAX(innings_runs) AS highest_score
    FROM (
        SELECT batsman_key, match_key, innings_number, SUM(runs_batsman) AS innings_runs
        FROM fact_deliveries
        GROUP BY batsman_key, match_key, innings_number
    ) t
    GROUP BY batsman_key
) sub ON sub.batsman_key = p.player_key
GROUP BY p.player_key, p.player_name, p.player_id;

CREATE UNIQUE INDEX idx_mv_batting_player ON mv_player_batting_stats(player_key);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_player_bowling_stats AS
SELECT
    p.player_key,
    p.player_name,
    p.player_id,
    COUNT(DISTINCT fd.match_key) AS matches,
    SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) AS balls_bowled,
    SUM(fd.runs_total) AS runs_conceded,
    ROUND(
        SUM(fd.runs_total)::DECIMAL * 6.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS economy,
    COUNT(*) FILTER (WHERE fd.is_wicket AND fd.dismissal_type NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')) AS wickets,
    SUM(CASE WHEN fd.runs_total = 0 THEN 1 ELSE 0 END) AS dot_balls,
    SUM(CASE WHEN fd.is_wide THEN 1 ELSE 0 END) AS wides,
    SUM(CASE WHEN fd.is_noball THEN 1 ELSE 0 END) AS noballs
FROM fact_deliveries fd
JOIN dim_player p ON fd.bowler_key = p.player_key
GROUP BY p.player_key, p.player_name, p.player_id;

CREATE UNIQUE INDEX idx_mv_bowling_player ON mv_player_bowling_stats(player_key);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_team_season_summary AS
SELECT
    t.team_key,
    t.team_name,
    fms.season,
    COUNT(*) AS matches_played,
    SUM(CASE WHEN fms.match_winner_key = t.team_key THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN fms.match_winner_key IS NOT NULL AND fms.match_winner_key != t.team_key THEN 1 ELSE 0 END) AS losses,
    SUM(CASE WHEN fms.result = 'no result' THEN 1 ELSE 0 END) AS no_results,
    ROUND(
        SUM(CASE WHEN fms.match_winner_key = t.team_key THEN 1 ELSE 0 END)::DECIMAL * 100.0 /
        NULLIF(COUNT(*) - SUM(CASE WHEN fms.result = 'no result' THEN 1 ELSE 0 END), 0),
        2
    ) AS win_percentage
FROM fact_match_summary fms
JOIN dim_team t ON t.team_key IN (fms.team1_key, fms.team2_key)
GROUP BY t.team_key, t.team_name, fms.season;

CREATE UNIQUE INDEX idx_mv_team_season ON mv_team_season_summary(team_key, season);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_venue_stats AS
SELECT
    v.venue_key,
    v.venue_name,
    v.city,
    COUNT(*) AS total_matches,
    ROUND(AVG(fms.team1_score)::DECIMAL, 1) AS avg_first_innings_score,
    ROUND(AVG(fms.team2_score)::DECIMAL, 1) AS avg_second_innings_score,
    SUM(CASE WHEN fms.toss_decision = 'bat' THEN 1 ELSE 0 END) AS chose_bat_first,
    SUM(CASE WHEN fms.toss_decision = 'field' THEN 1 ELSE 0 END) AS chose_field_first,
    SUM(fms.total_sixes) AS total_sixes,
    SUM(fms.total_fours) AS total_fours
FROM fact_match_summary fms
JOIN dim_venue v ON fms.venue_key = v.venue_key
GROUP BY v.venue_key, v.venue_name, v.city;

CREATE UNIQUE INDEX idx_mv_venue ON mv_venue_stats(venue_key);
