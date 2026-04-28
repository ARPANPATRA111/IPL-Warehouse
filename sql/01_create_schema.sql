DROP TABLE IF EXISTS data_quality_log CASCADE;
DROP TABLE IF EXISTS etl_run_log CASCADE;
DROP TABLE IF EXISTS fact_deliveries CASCADE;
DROP TABLE IF EXISTS fact_match_summary CASCADE;
DROP TABLE IF EXISTS dim_innings CASCADE;
DROP TABLE IF EXISTS dim_match CASCADE;
DROP TABLE IF EXISTS dim_player CASCADE;
DROP TABLE IF EXISTS dim_team CASCADE;
DROP TABLE IF EXISTS dim_venue CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;
DROP TABLE IF EXISTS dim_dismissal_type CASCADE;
DROP TABLE IF EXISTS dim_extras_type CASCADE;

CREATE TABLE dim_date (
    date_key SERIAL PRIMARY KEY,
    full_date DATE UNIQUE NOT NULL,
    day_of_week SMALLINT NOT NULL,
    day_name VARCHAR(10) NOT NULL,
    day_of_month SMALLINT NOT NULL,
    week_of_year SMALLINT NOT NULL,
    month_number SMALLINT NOT NULL,
    month_name VARCHAR(10) NOT NULL,
    quarter SMALLINT NOT NULL,
    year SMALLINT NOT NULL,
    season VARCHAR(10) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_playoff BOOLEAN DEFAULT FALSE,
    phase_of_tournament VARCHAR(20)
);

CREATE TABLE dim_venue (
    venue_key SERIAL PRIMARY KEY,
    venue_name VARCHAR(200) NOT NULL,
    city VARCHAR(100),
    country VARCHAR(50) DEFAULT 'India',
    is_home_ground BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_venue_name_city ON dim_venue(venue_name, COALESCE(city, ''));

CREATE TABLE dim_team (
    team_key SERIAL PRIMARY KEY,
    team_name VARCHAR(100) UNIQUE NOT NULL,
    team_short_name VARCHAR(10),
    is_active BOOLEAN DEFAULT TRUE,
    franchise_group VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE dim_player (
    player_key SERIAL PRIMARY KEY,
    player_id VARCHAR(50) UNIQUE NOT NULL,
    player_name VARCHAR(100) NOT NULL,
    first_match_date DATE,
    last_match_date DATE,
    total_matches INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE dim_match (
    match_key SERIAL PRIMARY KEY,
    match_id VARCHAR(50) UNIQUE NOT NULL,
    season VARCHAR(10) NOT NULL,
    match_number INT,
    match_type VARCHAR(10) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    balls_per_over SMALLINT NOT NULL DEFAULT 6,
    overs_per_side SMALLINT NOT NULL DEFAULT 20,
    data_version VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE dim_innings (
    innings_key SERIAL PRIMARY KEY,
    match_key INT NOT NULL REFERENCES dim_match(match_key),
    innings_number SMALLINT NOT NULL,
    batting_team_key INT NOT NULL REFERENCES dim_team(team_key),
    bowling_team_key INT NOT NULL REFERENCES dim_team(team_key),
    total_runs INT DEFAULT 0,
    total_wickets SMALLINT DEFAULT 0,
    total_overs DECIMAL(4,1),
    total_extras INT DEFAULT 0,
    is_super_over BOOLEAN DEFAULT FALSE,
    target_runs INT,
    target_overs INT,
    has_dls BOOLEAN DEFAULT FALSE,
    is_forfeited BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(match_key, innings_number)
);

CREATE TABLE dim_dismissal_type (
    dismissal_key SERIAL PRIMARY KEY,
    dismissal_type VARCHAR(30) UNIQUE NOT NULL,
    is_bowler_credited BOOLEAN NOT NULL,
    is_fielder_involved BOOLEAN NOT NULL,
    description VARCHAR(200)
);

CREATE TABLE dim_extras_type (
    extras_key SERIAL PRIMARY KEY,
    extras_type VARCHAR(20) UNIQUE NOT NULL,
    is_charged_to_bowler BOOLEAN NOT NULL,
    is_legal_delivery BOOLEAN NOT NULL
);

CREATE TABLE fact_deliveries (
    delivery_id SERIAL PRIMARY KEY,
    match_key INT NOT NULL REFERENCES dim_match(match_key),
    date_key INT NOT NULL REFERENCES dim_date(date_key),
    venue_key INT NOT NULL REFERENCES dim_venue(venue_key),
    batting_team_key INT NOT NULL REFERENCES dim_team(team_key),
    bowling_team_key INT NOT NULL REFERENCES dim_team(team_key),
    batsman_key INT NOT NULL REFERENCES dim_player(player_key),
    non_striker_key INT NOT NULL REFERENCES dim_player(player_key),
    bowler_key INT NOT NULL REFERENCES dim_player(player_key),
    innings_number SMALLINT NOT NULL CHECK (innings_number BETWEEN 1 AND 4),
    over_number SMALLINT NOT NULL,
    ball_number SMALLINT NOT NULL,
    legal_ball_number SMALLINT NOT NULL,
    runs_batsman SMALLINT NOT NULL DEFAULT 0,
    runs_extras SMALLINT NOT NULL DEFAULT 0,
    runs_total SMALLINT NOT NULL DEFAULT 0,
    is_boundary_four BOOLEAN NOT NULL DEFAULT FALSE,
    is_boundary_six BOOLEAN NOT NULL DEFAULT FALSE,
    is_dot_ball BOOLEAN NOT NULL DEFAULT FALSE,
    extras_type VARCHAR(20),
    extras_runs SMALLINT NOT NULL DEFAULT 0,
    is_wicket BOOLEAN NOT NULL DEFAULT FALSE,
    dismissal_type VARCHAR(30),
    dismissed_player_key INT REFERENCES dim_player(player_key),
    fielder1_key INT REFERENCES dim_player(player_key),
    fielder2_key INT REFERENCES dim_player(player_key),
    is_wide BOOLEAN NOT NULL DEFAULT FALSE,
    is_noball BOOLEAN NOT NULL DEFAULT FALSE,
    is_legal_delivery BOOLEAN NOT NULL,
    is_super_over BOOLEAN NOT NULL DEFAULT FALSE,
    is_powerplay BOOLEAN NOT NULL DEFAULT FALSE,
    cumulative_runs INT NOT NULL,
    cumulative_wickets SMALLINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE fact_match_summary (
    match_summary_id SERIAL PRIMARY KEY,
    match_key INT UNIQUE NOT NULL REFERENCES dim_match(match_key),
    date_key INT NOT NULL REFERENCES dim_date(date_key),
    venue_key INT NOT NULL REFERENCES dim_venue(venue_key),
    team1_key INT NOT NULL REFERENCES dim_team(team_key),
    team2_key INT NOT NULL REFERENCES dim_team(team_key),
    toss_winner_key INT NOT NULL REFERENCES dim_team(team_key),
    toss_decision VARCHAR(10) NOT NULL,
    match_winner_key INT REFERENCES dim_team(team_key),
    win_type VARCHAR(10),
    win_margin INT,
    is_dls BOOLEAN NOT NULL DEFAULT FALSE,
    result VARCHAR(20) NOT NULL,
    eliminator_winner_key INT REFERENCES dim_team(team_key),
    player_of_match_key INT REFERENCES dim_player(player_key),
    team1_score INT,
    team1_wickets SMALLINT,
    team1_overs DECIMAL(4,1),
    team2_score INT,
    team2_wickets SMALLINT,
    team2_overs DECIMAL(4,1),
    total_fours INT NOT NULL DEFAULT 0,
    total_sixes INT NOT NULL DEFAULT 0,
    total_extras INT NOT NULL DEFAULT 0,
    season VARCHAR(10) NOT NULL,
    match_number INT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE etl_run_log (
    run_id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    files_processed INT DEFAULT 0,
    files_skipped INT DEFAULT 0,
    rows_loaded INT DEFAULT 0,
    error_message TEXT,
    pipeline_version VARCHAR(20)
);

CREATE TABLE data_quality_log (
    dq_id SERIAL PRIMARY KEY,
    run_id INT REFERENCES etl_run_log(run_id),
    check_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    check_type VARCHAR(30) NOT NULL,
    records_checked INT,
    records_failed INT,
    pass_rate DECIMAL(5,2),
    severity VARCHAR(10) NOT NULL,
    details TEXT,
    checked_at TIMESTAMP DEFAULT NOW()
);
