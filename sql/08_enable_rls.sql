REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO authenticated;

ALTER TABLE dim_date ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_dim_date ON dim_date;
CREATE POLICY authenticated_read_dim_date ON dim_date FOR SELECT TO authenticated USING (true);

ALTER TABLE dim_venue ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_dim_venue ON dim_venue;
CREATE POLICY authenticated_read_dim_venue ON dim_venue FOR SELECT TO authenticated USING (true);

ALTER TABLE dim_team ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_dim_team ON dim_team;
CREATE POLICY authenticated_read_dim_team ON dim_team FOR SELECT TO authenticated USING (true);

ALTER TABLE dim_player ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_dim_player ON dim_player;
CREATE POLICY authenticated_read_dim_player ON dim_player FOR SELECT TO authenticated USING (true);

ALTER TABLE dim_match ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_dim_match ON dim_match;
CREATE POLICY authenticated_read_dim_match ON dim_match FOR SELECT TO authenticated USING (true);

ALTER TABLE dim_innings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_dim_innings ON dim_innings;
CREATE POLICY authenticated_read_dim_innings ON dim_innings FOR SELECT TO authenticated USING (true);

ALTER TABLE dim_dismissal_type ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_dim_dismissal_type ON dim_dismissal_type;
CREATE POLICY authenticated_read_dim_dismissal_type ON dim_dismissal_type FOR SELECT TO authenticated USING (true);

ALTER TABLE dim_extras_type ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_dim_extras_type ON dim_extras_type;
CREATE POLICY authenticated_read_dim_extras_type ON dim_extras_type FOR SELECT TO authenticated USING (true);

ALTER TABLE fact_deliveries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_fact_deliveries ON fact_deliveries;
CREATE POLICY authenticated_read_fact_deliveries ON fact_deliveries FOR SELECT TO authenticated USING (true);

ALTER TABLE fact_match_summary ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_fact_match_summary ON fact_match_summary;
CREATE POLICY authenticated_read_fact_match_summary ON fact_match_summary FOR SELECT TO authenticated USING (true);

ALTER TABLE etl_run_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_etl_run_log ON etl_run_log;
CREATE POLICY authenticated_read_etl_run_log ON etl_run_log FOR SELECT TO authenticated USING (true);

ALTER TABLE data_quality_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS authenticated_read_data_quality_log ON data_quality_log;
CREATE POLICY authenticated_read_data_quality_log ON data_quality_log FOR SELECT TO authenticated USING (true);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'etl_file_registry'
    ) THEN
        ALTER TABLE etl_file_registry ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS authenticated_read_etl_file_registry ON etl_file_registry;
        CREATE POLICY authenticated_read_etl_file_registry ON etl_file_registry FOR SELECT TO authenticated USING (true);
    END IF;
END $$;