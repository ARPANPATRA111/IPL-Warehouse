CREATE INDEX idx_fd_match ON fact_deliveries(match_key);
CREATE INDEX idx_fd_batsman ON fact_deliveries(batsman_key);
CREATE INDEX idx_fd_bowler ON fact_deliveries(bowler_key);
CREATE INDEX idx_fd_date ON fact_deliveries(date_key);
CREATE INDEX idx_fd_team_bat ON fact_deliveries(batting_team_key);
CREATE INDEX idx_fd_team_bowl ON fact_deliveries(bowling_team_key);
CREATE INDEX idx_fd_venue ON fact_deliveries(venue_key);
CREATE INDEX idx_fd_composite ON fact_deliveries(match_key, innings_number, over_number, ball_number);
CREATE INDEX idx_fd_wicket ON fact_deliveries(is_wicket) WHERE is_wicket = TRUE;
CREATE INDEX idx_fd_boundary ON fact_deliveries(is_boundary_four, is_boundary_six);
CREATE INDEX idx_fd_innings ON fact_deliveries(match_key, innings_number);
CREATE INDEX idx_fd_dismissed ON fact_deliveries(dismissed_player_key) WHERE dismissed_player_key IS NOT NULL;

CREATE INDEX idx_fms_date ON fact_match_summary(date_key);
CREATE INDEX idx_fms_venue ON fact_match_summary(venue_key);
CREATE INDEX idx_fms_winner ON fact_match_summary(match_winner_key);
CREATE INDEX idx_fms_season ON fact_match_summary(season);
CREATE INDEX idx_fms_team1 ON fact_match_summary(team1_key);
CREATE INDEX idx_fms_team2 ON fact_match_summary(team2_key);

CREATE INDEX idx_player_name ON dim_player(player_name);
CREATE INDEX idx_player_name_normalized ON dim_player((regexp_replace(lower(player_name), '[^a-z0-9]', '', 'g')));
CREATE INDEX idx_player_active ON dim_player(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_team_active ON dim_team(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_date_year ON dim_date(year);
CREATE INDEX idx_date_season ON dim_date(season);
CREATE INDEX idx_match_season_key ON dim_match(season, match_key);
CREATE INDEX idx_venue_city ON dim_venue(city);

CREATE INDEX idx_etl_status ON etl_run_log(status);
CREATE INDEX idx_dq_run ON data_quality_log(run_id);
CREATE INDEX idx_dq_severity ON data_quality_log(severity);
