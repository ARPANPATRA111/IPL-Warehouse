SELECT
    p.player_name,
    SUM(fd.runs_batsman) AS total_runs,
    COUNT(DISTINCT CONCAT(fd.match_key, '-', fd.innings_number)) AS innings,
    ROUND(
        SUM(fd.runs_batsman)::DECIMAL /
        NULLIF(COUNT(DISTINCT CONCAT(fd.match_key, '-', fd.innings_number)) -
            (SELECT COUNT(*) FROM fact_deliveries fd2
             WHERE fd2.batsman_key = fd.batsman_key
             AND fd2.is_wicket = TRUE
             AND fd2.dismissed_player_key = fd2.batsman_key
             GROUP BY fd2.batsman_key), 0),
        2
    ) AS batting_average,
    ROUND(
        SUM(fd.runs_batsman)::DECIMAL * 100.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS strike_rate,
    SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) AS fours,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes
FROM fact_deliveries fd
JOIN dim_player p ON fd.batsman_key = p.player_key
GROUP BY p.player_name, fd.batsman_key
ORDER BY total_runs DESC
LIMIT 20;

SELECT
    p.player_name,
    SUM(fd.runs_batsman) AS runs_in_match,
    m.match_id,
    m.season,
    bowl_t.team_name AS opponent,
    CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM fact_deliveries fd2
            WHERE fd2.match_key = fd.match_key
            AND fd2.innings_number = fd.innings_number
            AND fd2.dismissed_player_key = fd.batsman_key
        ) THEN TRUE
        ELSE FALSE
    END AS is_not_out,
    SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) AS balls_faced,
    SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) AS fours,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes
FROM fact_deliveries fd
JOIN dim_player p ON fd.batsman_key = p.player_key
JOIN dim_match m ON fd.match_key = m.match_key
JOIN dim_team bowl_t ON fd.bowling_team_key = bowl_t.team_key
GROUP BY p.player_name, fd.batsman_key, fd.match_key, fd.innings_number, m.match_id, m.season, bowl_t.team_name
ORDER BY runs_in_match DESC
LIMIT 20;

SELECT
    p.player_name,
    SUM(fd.runs_batsman) AS total_runs,
    SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) AS balls_faced,
    ROUND(
        SUM(fd.runs_batsman)::DECIMAL * 100.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS strike_rate,
    ROUND(
        (SUM(CASE WHEN fd.is_boundary_four THEN 4 ELSE 0 END) +
         SUM(CASE WHEN fd.is_boundary_six THEN 6 ELSE 0 END))::DECIMAL * 100.0 /
        NULLIF(SUM(fd.runs_batsman), 0),
        2
    ) AS boundary_percentage
FROM fact_deliveries fd
JOIN dim_player p ON fd.batsman_key = p.player_key
GROUP BY p.player_name
HAVING SUM(fd.runs_batsman) >= 500
ORDER BY strike_rate DESC
LIMIT 20;

SELECT
    d.season,
    p.player_name,
    SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) AS fours,
    SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS sixes,
    SUM(CASE WHEN fd.is_boundary_four OR fd.is_boundary_six THEN 1 ELSE 0 END) AS total_boundaries,
    RANK() OVER (
        PARTITION BY d.season
        ORDER BY SUM(CASE WHEN fd.is_boundary_four OR fd.is_boundary_six THEN 1 ELSE 0 END) DESC
    ) AS season_rank
FROM fact_deliveries fd
JOIN dim_player p ON fd.batsman_key = p.player_key
JOIN dim_date d ON fd.date_key = d.date_key
GROUP BY d.season, p.player_name
ORDER BY d.season DESC, total_boundaries DESC;

WITH batting_order AS (
    SELECT
        fd.match_key,
        fd.innings_number,
        fd.batsman_key,
        ROW_NUMBER() OVER (
            PARTITION BY fd.match_key, fd.innings_number
            ORDER BY fd.over_number, fd.ball_number
        ) AS first_ball_rank
    FROM fact_deliveries fd
    GROUP BY fd.match_key, fd.innings_number, fd.batsman_key, fd.over_number, fd.ball_number
),
positions AS (
    SELECT
        match_key,
        innings_number,
        batsman_key,
        DENSE_RANK() OVER (
            PARTITION BY match_key, innings_number
            ORDER BY MIN(first_ball_rank)
        ) AS batting_position
    FROM batting_order
    GROUP BY match_key, innings_number, batsman_key
)
SELECT
    pos.batting_position,
    ROUND(AVG(innings_runs.runs)::DECIMAL, 2) AS avg_runs,
    COUNT(*) AS innings_count
FROM positions pos
JOIN (
    SELECT
        fd.match_key,
        fd.innings_number,
        fd.batsman_key,
        SUM(fd.runs_batsman) AS runs
    FROM fact_deliveries fd
    GROUP BY fd.match_key, fd.innings_number, fd.batsman_key
) innings_runs ON pos.match_key = innings_runs.match_key
    AND pos.innings_number = innings_runs.innings_number
    AND pos.batsman_key = innings_runs.batsman_key
WHERE pos.batting_position <= 7
GROUP BY pos.batting_position
ORDER BY pos.batting_position;

SELECT
    p.player_name,
    COUNT(*) FILTER (WHERE fd.is_wicket AND fd.dismissal_type NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')) AS wickets,
    COUNT(DISTINCT fd.match_key) AS matches,
    ROUND(
        SUM(fd.runs_total)::DECIMAL /
        NULLIF(COUNT(*) FILTER (WHERE fd.is_wicket AND fd.dismissal_type NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')), 0),
        2
    ) AS bowling_average,
    ROUND(
        SUM(fd.runs_total)::DECIMAL * 6.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS economy,
    ROUND(
        SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END)::DECIMAL /
        NULLIF(COUNT(*) FILTER (WHERE fd.is_wicket AND fd.dismissal_type NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')), 0),
        2
    ) AS strike_rate
FROM fact_deliveries fd
JOIN dim_player p ON fd.bowler_key = p.player_key
GROUP BY p.player_name
HAVING COUNT(*) FILTER (WHERE fd.is_wicket AND fd.dismissal_type NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')) > 0
ORDER BY wickets DESC
LIMIT 20;

SELECT
    p.player_name,
    COUNT(*) FILTER (WHERE fd.is_wicket AND fd.dismissal_type NOT IN ('run out', 'retired hurt', 'retired out')) AS wickets_taken,
    SUM(fd.runs_total) AS runs_conceded,
    ROUND(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END)::DECIMAL / 6, 1) AS overs_bowled,
    m.match_id,
    m.season
FROM fact_deliveries fd
JOIN dim_player p ON fd.bowler_key = p.player_key
JOIN dim_match m ON fd.match_key = m.match_key
GROUP BY p.player_name, fd.match_key, fd.innings_number, m.match_id, m.season
HAVING COUNT(*) FILTER (WHERE fd.is_wicket AND fd.dismissal_type NOT IN ('run out', 'retired hurt', 'retired out')) >= 3
ORDER BY wickets_taken DESC, runs_conceded ASC
LIMIT 20;

SELECT
    p.player_name,
    SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) AS legal_balls_bowled,
    SUM(fd.runs_total) AS runs_conceded,
    ROUND(
        SUM(fd.runs_total)::DECIMAL * 6.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS economy,
    ROUND(
        SUM(CASE WHEN fd.runs_total = 0 THEN 1 ELSE 0 END)::DECIMAL * 100.0 /
        NULLIF(COUNT(*), 0),
        2
    ) AS dot_ball_percentage
FROM fact_deliveries fd
JOIN dim_player p ON fd.bowler_key = p.player_key
GROUP BY p.player_name
HAVING SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) >= 300
ORDER BY economy ASC
LIMIT 20;

SELECT
    p.player_name,
    d.season,
    SUM(CASE WHEN fd.runs_total = 0 THEN 1 ELSE 0 END) AS dot_balls,
    COUNT(*) AS total_balls,
    ROUND(
        SUM(CASE WHEN fd.runs_total = 0 THEN 1 ELSE 0 END)::DECIMAL * 100.0 / COUNT(*),
        2
    ) AS dot_ball_percentage
FROM fact_deliveries fd
JOIN dim_player p ON fd.bowler_key = p.player_key
JOIN dim_date d ON fd.date_key = d.date_key
GROUP BY p.player_name, d.season
ORDER BY dot_balls DESC
LIMIT 30;

SELECT
    fd.dismissal_type,
    COUNT(*) AS total_count,
    ROUND(
        COUNT(*)::DECIMAL * 100.0 / SUM(COUNT(*)) OVER (),
        2
    ) AS percentage
FROM fact_deliveries fd
WHERE fd.is_wicket = TRUE AND fd.dismissal_type IS NOT NULL
GROUP BY fd.dismissal_type
ORDER BY total_count DESC;

SELECT
    t.team_name,
    fms.season,
    COUNT(*) AS matches,
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
GROUP BY t.team_name, fms.season
ORDER BY fms.season DESC, win_percentage DESC;

SELECT
    t1.team_name AS team_a,
    t2.team_name AS team_b,
    SUM(CASE WHEN fms.match_winner_key = fms.team1_key THEN 1 ELSE 0 END) AS team_a_wins,
    SUM(CASE WHEN fms.match_winner_key = fms.team2_key THEN 1 ELSE 0 END) AS team_b_wins,
    SUM(CASE WHEN fms.result = 'tie' THEN 1 ELSE 0 END) AS ties,
    COUNT(*) AS total_matches
FROM fact_match_summary fms
JOIN dim_team t1 ON fms.team1_key = t1.team_key
JOIN dim_team t2 ON fms.team2_key = t2.team_key
GROUP BY t1.team_name, t2.team_name
ORDER BY total_matches DESC;

(
    SELECT
        bat_t.team_name AS batting_team,
        di.total_runs,
        di.total_wickets AS wickets,
        di.total_overs AS overs,
        bowl_t.team_name AS opponent,
        v.venue_name,
        m.season,
        'highest' AS category
    FROM dim_innings di
    JOIN dim_match m ON di.match_key = m.match_key
    JOIN dim_team bat_t ON di.batting_team_key = bat_t.team_key
    JOIN dim_team bowl_t ON di.bowling_team_key = bowl_t.team_key
    JOIN fact_match_summary fms ON fms.match_key = m.match_key
    JOIN dim_venue v ON fms.venue_key = v.venue_key
    WHERE di.is_super_over = FALSE
    ORDER BY di.total_runs DESC
    LIMIT 10
)
UNION ALL
(
    SELECT
        bat_t.team_name AS batting_team,
        di.total_runs,
        di.total_wickets AS wickets,
        di.total_overs AS overs,
        bowl_t.team_name AS opponent,
        v.venue_name,
        m.season,
        'lowest' AS category
    FROM dim_innings di
    JOIN dim_match m ON di.match_key = m.match_key
    JOIN dim_team bat_t ON di.batting_team_key = bat_t.team_key
    JOIN dim_team bowl_t ON di.bowling_team_key = bowl_t.team_key
    JOIN fact_match_summary fms ON fms.match_key = m.match_key
    JOIN dim_venue v ON fms.venue_key = v.venue_key
    WHERE di.is_super_over = FALSE AND di.total_wickets = 10
    ORDER BY di.total_runs ASC
    LIMIT 10
);

WITH team_batting AS (
    SELECT
        fd.batting_team_key,
        d.season,
        SUM(fd.runs_total) AS runs_scored,
        SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END)::DECIMAL / 6 AS overs_faced
    FROM fact_deliveries fd
    JOIN dim_date d ON fd.date_key = d.date_key
    WHERE fd.is_super_over = FALSE
    GROUP BY fd.batting_team_key, d.season
),
team_bowling AS (
    SELECT
        fd.bowling_team_key,
        d.season,
        SUM(fd.runs_total) AS runs_conceded,
        SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END)::DECIMAL / 6 AS overs_bowled
    FROM fact_deliveries fd
    JOIN dim_date d ON fd.date_key = d.date_key
    WHERE fd.is_super_over = FALSE
    GROUP BY fd.bowling_team_key, d.season
)
SELECT
    t.team_name,
    tb.season,
    tb.runs_scored,
    ROUND(tb.overs_faced, 1) AS overs_faced,
    tbl.runs_conceded,
    ROUND(tbl.overs_bowled, 1) AS overs_bowled,
    ROUND(
        (tb.runs_scored / NULLIF(tb.overs_faced, 0)) -
        (tbl.runs_conceded / NULLIF(tbl.overs_bowled, 0)),
        3
    ) AS net_run_rate
FROM team_batting tb
JOIN team_bowling tbl ON tb.batting_team_key = tbl.bowling_team_key AND tb.season = tbl.season
JOIN dim_team t ON tb.batting_team_key = t.team_key
ORDER BY tb.season DESC, net_run_rate DESC;

SELECT
    t.team_name,
    d.season,
    SUM(CASE WHEN fd.over_number BETWEEN 0 AND 5 THEN fd.runs_total ELSE 0 END) AS powerplay_runs,
    SUM(CASE WHEN fd.over_number BETWEEN 6 AND 14 THEN fd.runs_total ELSE 0 END) AS middle_overs_runs,
    SUM(CASE WHEN fd.over_number BETWEEN 15 AND 19 THEN fd.runs_total ELSE 0 END) AS death_overs_runs,
    COUNT(DISTINCT fd.match_key) AS matches
FROM fact_deliveries fd
JOIN dim_team t ON fd.batting_team_key = t.team_key
JOIN dim_date d ON fd.date_key = d.date_key
WHERE fd.is_super_over = FALSE
GROUP BY t.team_name, d.season
ORDER BY d.season DESC, t.team_name;

SELECT
    v.venue_name,
    v.city,
    COUNT(*) AS total_matches,
    SUM(CASE
        WHEN fms.toss_decision = 'bat' AND fms.match_winner_key = fms.toss_winner_key THEN 1
        WHEN fms.toss_decision = 'field' AND fms.match_winner_key IS NOT NULL AND fms.match_winner_key != fms.toss_winner_key THEN 1
        ELSE 0
    END) AS bat_first_wins,
    SUM(CASE
        WHEN fms.toss_decision = 'field' AND fms.match_winner_key = fms.toss_winner_key THEN 1
        WHEN fms.toss_decision = 'bat' AND fms.match_winner_key IS NOT NULL AND fms.match_winner_key != fms.toss_winner_key THEN 1
        ELSE 0
    END) AS field_first_wins,
    ROUND(
        SUM(CASE
            WHEN fms.toss_decision = 'bat' AND fms.match_winner_key = fms.toss_winner_key THEN 1
            WHEN fms.toss_decision = 'field' AND fms.match_winner_key IS NOT NULL AND fms.match_winner_key != fms.toss_winner_key THEN 1
            ELSE 0
        END)::DECIMAL * 100.0 / NULLIF(COUNT(*), 0),
        2
    ) AS bat_first_win_pct
FROM fact_match_summary fms
JOIN dim_venue v ON fms.venue_key = v.venue_key
WHERE fms.result = 'normal'
GROUP BY v.venue_name, v.city
HAVING COUNT(*) >= 5
ORDER BY total_matches DESC;

SELECT
    fms.season,
    COUNT(*) AS total_matches,
    SUM(CASE WHEN fms.match_winner_key = fms.toss_winner_key THEN 1 ELSE 0 END) AS toss_winner_wins_match,
    ROUND(
        SUM(CASE WHEN fms.match_winner_key = fms.toss_winner_key THEN 1 ELSE 0 END)::DECIMAL * 100.0 /
        NULLIF(SUM(CASE WHEN fms.result = 'normal' THEN 1 ELSE 0 END), 0),
        2
    ) AS toss_win_match_win_pct,
    SUM(CASE WHEN fms.toss_decision = 'field' THEN 1 ELSE 0 END) AS chose_to_field,
    ROUND(
        SUM(CASE WHEN fms.toss_decision = 'field' THEN 1 ELSE 0 END)::DECIMAL * 100.0 / COUNT(*),
        2
    ) AS field_choice_pct
FROM fact_match_summary fms
GROUP BY fms.season
ORDER BY fms.season;

SELECT
    v.venue_name,
    v.city,
    ROUND(AVG(fms.team1_score)::DECIMAL, 1) AS avg_first_innings_score,
    ROUND(AVG(fms.team2_score)::DECIMAL, 1) AS avg_second_innings_score,
    COUNT(*) AS matches,
    ROUND((AVG(COALESCE(fms.team1_score, 0)) + AVG(COALESCE(fms.team2_score, 0)))::DECIMAL, 1) AS avg_match_total
FROM fact_match_summary fms
JOIN dim_venue v ON fms.venue_key = v.venue_key
WHERE fms.team1_score IS NOT NULL AND fms.team2_score IS NOT NULL
GROUP BY v.venue_name, v.city
HAVING COUNT(*) >= 5
ORDER BY avg_match_total DESC;

SELECT
    d.season,
    COUNT(DISTINCT fd.match_key) AS total_matches,
    ROUND(
        SUM(fd.runs_total)::DECIMAL / NULLIF(COUNT(DISTINCT fd.match_key), 0) / 2,
        1
    ) AS avg_innings_score,
    ROUND(
        SUM(fd.runs_batsman)::DECIMAL * 100.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS avg_strike_rate,
    ROUND(
        SUM(CASE WHEN fd.is_boundary_four OR fd.is_boundary_six THEN 1 ELSE 0 END)::DECIMAL * 100.0 /
        NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0),
        2
    ) AS boundary_percentage,
    ROUND(
        SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END)::DECIMAL /
        NULLIF(COUNT(DISTINCT fd.match_key), 0),
        1
    ) AS sixes_per_match
FROM fact_deliveries fd
JOIN dim_date d ON fd.date_key = d.date_key
WHERE fd.is_super_over = FALSE
GROUP BY d.season
ORDER BY d.season;

WITH innings_scores AS (
    SELECT
        fd.batsman_key,
        fd.match_key,
        fd.innings_number,
        SUM(fd.runs_batsman) AS innings_runs
    FROM fact_deliveries fd
    GROUP BY fd.batsman_key, fd.match_key, fd.innings_number
)
SELECT
    p.player_name,
    COUNT(*) AS innings,
    ROUND(AVG(is2.innings_runs)::DECIMAL, 2) AS avg_score,
    ROUND(STDDEV(is2.innings_runs)::DECIMAL, 2) AS std_deviation,
    ROUND(
        STDDEV(is2.innings_runs)::DECIMAL * 100.0 / NULLIF(AVG(is2.innings_runs), 0),
        2
    ) AS coefficient_of_variation
FROM innings_scores is2
JOIN dim_player p ON is2.batsman_key = p.player_key
GROUP BY p.player_name
HAVING COUNT(*) >= 30 AND AVG(is2.innings_runs) >= 20
ORDER BY coefficient_of_variation ASC
LIMIT 20;

WITH player_innings AS (
    SELECT
        fd.batsman_key,
        fd.innings_number,
        fd.match_key,
        SUM(fd.runs_batsman) AS runs
    FROM fact_deliveries fd
    WHERE fd.is_super_over = FALSE
    GROUP BY fd.batsman_key, fd.innings_number, fd.match_key
)
SELECT
    p.player_name,
    ROUND(AVG(CASE WHEN pi.innings_number = 1 THEN pi.runs END)::DECIMAL, 2) AS avg_setting,
    ROUND(AVG(CASE WHEN pi.innings_number = 2 THEN pi.runs END)::DECIMAL, 2) AS avg_chasing,
    ROUND(
        AVG(CASE WHEN pi.innings_number = 2 THEN pi.runs END)::DECIMAL -
        AVG(CASE WHEN pi.innings_number = 1 THEN pi.runs END)::DECIMAL,
        2
    ) AS chase_premium,
    COUNT(*) AS total_innings
FROM player_innings pi
JOIN dim_player p ON pi.batsman_key = p.player_key
GROUP BY p.player_name
HAVING COUNT(*) >= 30
    AND COUNT(CASE WHEN pi.innings_number = 1 THEN 1 END) >= 10
    AND COUNT(CASE WHEN pi.innings_number = 2 THEN 1 END) >= 10
ORDER BY chase_premium DESC
LIMIT 20;

WITH phase_stats AS (
    SELECT
        fd.batsman_key,
        CASE
            WHEN fd.over_number BETWEEN 0 AND 5 THEN 'powerplay'
            WHEN fd.over_number BETWEEN 15 AND 19 THEN 'death'
        END AS phase,
        SUM(fd.runs_batsman) AS runs,
        SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) AS balls
    FROM fact_deliveries fd
    WHERE fd.over_number BETWEEN 0 AND 5 OR fd.over_number BETWEEN 15 AND 19
    GROUP BY fd.batsman_key, CASE
            WHEN fd.over_number BETWEEN 0 AND 5 THEN 'powerplay'
            WHEN fd.over_number BETWEEN 15 AND 19 THEN 'death'
        END
)
SELECT
    p.player_name,
    ROUND(
        MAX(CASE WHEN ps.phase = 'powerplay' THEN ps.runs::DECIMAL * 100.0 / NULLIF(ps.balls, 0) END),
        2
    ) AS powerplay_strike_rate,
    MAX(CASE WHEN ps.phase = 'powerplay' THEN ps.balls END) AS powerplay_balls,
    ROUND(
        MAX(CASE WHEN ps.phase = 'death' THEN ps.runs::DECIMAL * 100.0 / NULLIF(ps.balls, 0) END),
        2
    ) AS death_strike_rate,
    MAX(CASE WHEN ps.phase = 'death' THEN ps.balls END) AS death_balls
FROM phase_stats ps
JOIN dim_player p ON ps.batsman_key = p.player_key
GROUP BY p.player_name
HAVING MAX(CASE WHEN ps.phase = 'powerplay' THEN ps.balls END) >= 100
    AND MAX(CASE WHEN ps.phase = 'death' THEN ps.balls END) >= 50
ORDER BY death_strike_rate DESC
LIMIT 20;
