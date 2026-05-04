CREATE OR REPLACE PROCEDURE refresh_materialized_views()
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_batting_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_bowling_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_team_season_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_venue_stats;
    RAISE NOTICE 'All materialized views refreshed successfully';
END;
$$;

CREATE OR REPLACE FUNCTION get_player_career_summary(p_player_name VARCHAR)
RETURNS TABLE (
    player_name VARCHAR,
    matches INT,
    runs_scored BIGINT,
    balls_faced BIGINT,
    strike_rate DECIMAL,
    fours BIGINT,
    sixes BIGINT,
    wickets_taken BIGINT,
    balls_bowled BIGINT,
    economy DECIMAL
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        bat.player_name::VARCHAR,
        bat.matches::INT,
        bat.total_runs,
        bat.balls_faced,
        bat.strike_rate,
        bat.fours,
        bat.sixes,
        COALESCE(bowl.wickets, 0)::BIGINT,
        COALESCE(bowl.balls_bowled, 0)::BIGINT,
        bowl.economy
    FROM mv_player_batting_stats bat
    LEFT JOIN mv_player_bowling_stats bowl ON bat.player_key = bowl.player_key
    WHERE bat.player_name ILIKE '%' || p_player_name || '%';
END;
$$;

CREATE OR REPLACE FUNCTION get_head_to_head(p_team1 VARCHAR, p_team2 VARCHAR)
RETURNS TABLE (
    team1_name VARCHAR,
    team2_name VARCHAR,
    team1_wins BIGINT,
    team2_wins BIGINT,
    ties BIGINT,
    no_results BIGINT,
    total_matches BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        t1.team_name::VARCHAR AS team1_name,
        t2.team_name::VARCHAR AS team2_name,
        SUM(CASE WHEN fms.match_winner_key = t1.team_key THEN 1 ELSE 0 END) AS team1_wins,
        SUM(CASE WHEN fms.match_winner_key = t2.team_key THEN 1 ELSE 0 END) AS team2_wins,
        SUM(CASE WHEN fms.result = 'tie' THEN 1 ELSE 0 END) AS ties,
        SUM(CASE WHEN fms.result = 'no result' THEN 1 ELSE 0 END) AS no_results,
        COUNT(*)::BIGINT AS total_matches
    FROM fact_match_summary fms
    JOIN dim_team t1 ON t1.team_key IN (fms.team1_key, fms.team2_key)
    JOIN dim_team t2 ON t2.team_key IN (fms.team1_key, fms.team2_key)
    WHERE t1.team_name ILIKE '%' || p_team1 || '%'
        AND t2.team_name ILIKE '%' || p_team2 || '%'
        AND t1.team_key != t2.team_key
    GROUP BY t1.team_name, t2.team_name;
END;
$$;

CREATE OR REPLACE FUNCTION start_etl_run(p_version VARCHAR)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
BEGIN
    INSERT INTO etl_run_log (started_at, status, pipeline_version)
    VALUES (NOW(), 'running', p_version)
    RETURNING run_id INTO v_run_id;

    RETURN v_run_id;
END;
$$;

CREATE OR REPLACE PROCEDURE complete_etl_run(
    p_run_id INT,
    p_status VARCHAR,
    p_files_processed INT,
    p_files_skipped INT,
    p_rows_loaded INT,
    p_error_message TEXT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE etl_run_log
    SET completed_at = NOW(),
        status = p_status,
        files_processed = p_files_processed,
        files_skipped = p_files_skipped,
        rows_loaded = p_rows_loaded,
        error_message = p_error_message
    WHERE run_id = p_run_id;
END;
$$;

CREATE OR REPLACE PROCEDURE log_dq_check(
    p_run_id INT,
    p_check_name VARCHAR,
    p_table_name VARCHAR,
    p_check_type VARCHAR,
    p_records_checked INT,
    p_records_failed INT,
    p_severity VARCHAR,
    p_details TEXT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_pass_rate DECIMAL(5,2);
BEGIN
    IF p_records_checked > 0 THEN
        v_pass_rate := ROUND(((p_records_checked - p_records_failed)::DECIMAL / p_records_checked) * 100, 2);
    ELSE
        v_pass_rate := 100.00;
    END IF;

    INSERT INTO data_quality_log (run_id, check_name, table_name, check_type, records_checked, records_failed, pass_rate, severity, details, checked_at)
    VALUES (p_run_id, p_check_name, p_table_name, p_check_type, p_records_checked, p_records_failed, v_pass_rate, p_severity, p_details, NOW());
END;
$$;

CREATE OR REPLACE PROCEDURE truncate_all_data()
LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE fact_deliveries CASCADE;
    TRUNCATE TABLE fact_match_summary CASCADE;
    TRUNCATE TABLE dim_innings CASCADE;
    TRUNCATE TABLE dim_match CASCADE;
    TRUNCATE TABLE dim_player CASCADE;
    TRUNCATE TABLE dim_team CASCADE;
    TRUNCATE TABLE dim_venue CASCADE;
    TRUNCATE TABLE dim_date CASCADE;
    RAISE NOTICE 'All data tables truncated';
END;
$$;
