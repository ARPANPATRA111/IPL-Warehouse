# 🏏 IPL Cricket Data Warehouse + ETL Pipeline — Production-Grade Master Prompt

> **Context**: This is a final-year academic project that must demonstrate mastery of Data Engineering, Data Warehousing, ETL design, OLAP analytics, and cloud deployment. It must simulate real-world enterprise data engineering practices while remaining fully executable from a single prompt.

---

## 🎯 Project Objective & Scope

Design and implement a **complete, end-to-end Cricket Analytics Data Warehouse system** with a robust ETL pipeline, analytical query layer, interactive dashboard, and cloud deployment — all using IPL (Indian Premier League) match data.

**Data Source:** `https://cricsheet.org/downloads/ipl_json.zip`
**Data Format:** Cricsheet JSON v1.1.0 (each `.json` file = one IPL match)

### What You Must Deliver (Non-Negotiable):

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | **Complete Python ETL pipeline** | Extract → Validate → Transform → Load with full error handling |
| 2 | **Star Schema Data Warehouse** | 8 dimension tables + 2 fact tables in PostgreSQL |
| 3 | **Data Quality Framework** | Validation rules, anomaly detection, quality metrics logging |
| 4 | **20+ Analytical SQL Queries** | With demonstrated OLAP operations (Roll-up, Drill-down, Slice, Dice) |
| 5 | **Interactive Analytics Dashboard** | Streamlit-based web dashboard with charts and filters |
| 6 | **Comprehensive Test Suite** | Unit tests, integration tests, data validation tests |
| 7 | **Docker Containerization** | Dockerfile + docker-compose for local reproducibility |
| 8 | **CI/CD Pipeline** | GitHub Actions workflow for automated testing and deployment |
| 9 | **Cloud Deployment** | Fully deployed on Supabase (DB) + Railway/Render (ETL + Dashboard) |
| 10 | **Production-grade Documentation** | README, architecture diagrams, setup guide, API reference |

⚠️ **CRITICAL RULES:**
- Do NOT leave any pseudo-code, placeholders, or `TODO` comments
- Do NOT skip error handling or edge cases
- Every file must be fully executable as-is
- All imports must be explicit; all dependencies in `requirements.txt`
- Use type hints throughout all Python code
- Follow PEP 8 strictly

---

## 📐 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SYSTEM ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ Cricsheet │───>│   EXTRACT    │───>│  VALIDATE    │              │
│  │ ZIP File  │    │  (Download,  │    │  (Schema,    │              │
│  │ (Source)  │    │   Unzip,     │    │   Data Type, │              │
│  └──────────┘    │   Iterate)   │    │   Business)  │              │
│                  └──────────────┘    └──────┬───────┘              │
│                                             │                       │
│                                             ▼                       │
│                                      ┌──────────────┐              │
│                                      │  TRANSFORM   │              │
│                                      │  (Flatten,   │              │
│                                      │   Normalize, │              │
│                                      │   Enrich,    │              │
│                                      │   SCD Logic) │              │
│                                      └──────┬───────┘              │
│                                             │                       │
│                                             ▼                       │
│                    ┌────────────────────────────────────────┐       │
│                    │            LOAD (PostgreSQL)           │       │
│                    │  ┌────────────────────────────────┐    │       │
│                    │  │     DIMENSION TABLES            │    │       │
│                    │  │  dim_player, dim_team,          │    │       │
│                    │  │  dim_venue, dim_date,           │    │       │
│                    │  │  dim_match, dim_innings,        │    │       │
│                    │  │  dim_dismissal_type,            │    │       │
│                    │  │  dim_extras_type                │    │       │
│                    │  └────────────────────────────────┘    │       │
│                    │  ┌────────────────────────────────┐    │       │
│                    │  │       FACT TABLES               │    │       │
│                    │  │  fact_deliveries (grain: 1 ball)│    │       │
│                    │  │  fact_match_summary (grain: 1   │    │       │
│                    │  │                     match)      │    │       │
│                    │  └────────────────────────────────┘    │       │
│                    │  ┌────────────────────────────────┐    │       │
│                    │  │     METADATA / AUDIT            │    │       │
│                    │  │  etl_run_log, data_quality_log  │    │       │
│                    │  └────────────────────────────────┘    │       │
│                    └────────────────────────────────────────┘       │
│                                             │                       │
│                                             ▼                       │
│                    ┌────────────────────────────────────────┐       │
│                    │        ANALYTICS LAYER                 │       │
│                    │  ┌──────────┐  ┌───────────────────┐  │       │
│                    │  │ SQL OLAP │  │ Streamlit Dashboard│  │       │
│                    │  │ Queries  │  │ (Interactive UI)   │  │       │
│                    │  └──────────┘  └───────────────────┘  │       │
│                    └────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### System Flow (Detailed):

1. **Ingest** → Download `ipl_json.zip` from Cricsheet, extract to `data/raw/`
2. **Validate** → Schema validation per JSON file, reject malformed files with structured error logs
3. **Transform** → Parse the deeply nested JSON, flatten ball-by-ball data, normalize entities (players, teams, venues), derive computed fields (strike rate, economy, etc.)
4. **Load** → Upsert into PostgreSQL star schema: dimensions first (with surrogate keys), then fact tables (with FK references)
5. **Analyze** → Run 20+ OLAP queries demonstrating Roll-up, Drill-down, Slice, Dice, and Pivot operations
6. **Visualize** → Serve an interactive Streamlit dashboard with filterable charts
7. **Deploy** → Containerize with Docker, deploy DB to Supabase, deploy ETL+Dashboard to Railway/Render

---

## 📦 Exact JSON Data Structure (Cricsheet v1.1.0)

> You MUST understand this structure precisely. Do NOT guess or simplify. The JSON has been verified against the official Cricsheet documentation.

Each JSON file represents **one IPL match** and has three top-level sections:

### 1. `meta` Section
```json
{
  "meta": {
    "data_version": "1.1.0",
    "created": "2023-09-15",
    "revision": 1
  }
}
```
- `data_version`: Semantic version of the data format
- `created`: Date the file was created (YYYY-MM-DD)
- `revision`: Integer revision number of this file

### 2. `info` Section (Match Metadata)

This contains ALL match-level information. Every field listed below MUST be extracted:

```json
{
  "info": {
    "balls_per_over": 6,
    "city": "Mumbai",
    "dates": ["2023-04-09"],
    "event": {
      "name": "Indian Premier League",
      "match_number": 15,
      "stage": "Group"        // optional
    },
    "gender": "male",
    "match_type": "T20",
    "match_type_number": 1842,  // optional
    "overs": 20,
    "outcome": {
      "winner": "Mumbai Indians",
      "by": { "runs": 35 },    // OR { "wickets": 7 }
      "method": "D/L"          // optional: "D/L", "VJD", etc.
    },
    // OR for ties/no-results:
    // "outcome": { "result": "tie", "eliminator": "Team Name" }
    // "outcome": { "result": "no result" }
    "player_of_match": ["V Kohli"],
    "players": {
      "Mumbai Indians": ["Player1", "Player2", ... ],  // exactly 11 per team
      "Chennai Super Kings": ["Player1", "Player2", ... ]
    },
    "registry": {
      "people": {
        "V Kohli": "uuid-string-here",  // stable unique ID across all matches
        "MS Dhoni": "uuid-string-here"
        // ... every person mentioned in the file
      }
    },
    "season": "2023",          // can be "2023" or "2023/24"
    "team_type": "club",
    "teams": ["Mumbai Indians", "Chennai Super Kings"],
    "toss": {
      "decision": "bat",       // "bat" or "field"
      "winner": "Mumbai Indians",
      "uncontested": true      // optional boolean
    },
    "venue": "Wankhede Stadium",
    "officials": {             // optional
      "umpires": ["Umpire1", "Umpire2"],
      "tv_umpires": ["Umpire3"],
      "match_referees": ["Referee1"],
      "reserve_umpires": ["Umpire4"]
    },
    "missing": ["player_of_match"],  // optional: lists known missing data
    "supersubs": {                    // optional
      "TeamName": "PlayerName"
    }
  }
}
```

**Critical fields to handle:**
- `dates` is ALWAYS an array (even for single-day matches)
- `season` can be a string like `"2023"` or `"2023/24"` — extract the primary year
- `outcome` has MULTIPLE possible structures (winner+by, result=tie, result=no result, method=D/L)
- `registry.people` provides **stable UUIDs** — USE THESE as the canonical player identifier
- `players` lists the playing XI per team — MUST be cross-referenced with registry
- `officials` is optional and may be missing entirely
- `player_of_match` is an array (can have multiple MoM winners, rare but possible)
- Team names are NOT consistent across seasons (e.g., "Delhi Daredevils" → "Delhi Capitals", "Deccan Chargers" → "Sunrisers Hyderabad", "Rising Pune Supergiant" / "Rising Pune Supergiants", "Kings XI Punjab" → "Punjab Kings")

### 3. `innings` Section (Ball-by-Ball Data)

This is the richest and most complex part. It's an array of innings objects:

```json
{
  "innings": [
    {
      "team": "Mumbai Indians",         // batting team
      "overs": [
        {
          "over": 0,                     // 0-indexed over number
          "deliveries": [
            {
              "batter": "RG Sharma",
              "bowler": "DJ Bravo",
              "non_striker": "QdK",
              "runs": {
                "batter": 4,             // runs credited to batsman
                "extras": 0,             // total extras on this ball
                "total": 4,              // batter + extras
                "non_boundary": true     // optional: if 4/6 was NOT a boundary
              },
              "extras": {               // optional, present only if extras occurred
                "wides": 1,             // possible keys: wides, noballs, byes, legbyes, penalty
                "noballs": 1,
                "byes": 4,
                "legbyes": 2,
                "penalty": 5
              },
              "wickets": [              // optional, present only if wicket fell
                {
                  "player_out": "RG Sharma",
                  "kind": "caught",     // see full list below
                  "fielders": [         // optional, depends on dismissal type
                    { "name": "DJ Bravo" }
                  ]
                }
              ],
              "replacements": {         // optional, very rare
                "match": [{ "in": "Player", "out": "Player", "reason": "concussion_substitute", "team": "Team" }],
                "role": [{ "in": "Player", "out": "Player", "reason": "injury", "role": "bowler" }]
              },
              "review": {               // optional
                "by": "Mumbai Indians",
                "umpire": "Umpire Name",
                "batter": "RG Sharma",
                "decision": "struck down",  // "struck down" or "upheld"
                "umpires_call": 1           // optional
              }
            }
          ]
        }
      ],
      "powerplays": [                   // optional
        { "from": 0.1, "to": 5.6, "type": "mandatory" }
      ],
      "target": {                       // optional, present in 2nd innings
        "overs": 20,
        "runs": 186
      },
      "super_over": true,              // optional boolean
      "penalty_runs": {                 // optional
        "pre": 5,
        "post": 0
      },
      "miscounted_overs": {},           // optional, very rare
      "declared": true,                 // optional boolean (not common in T20)
      "forfeited": true,               // optional boolean (very rare)
      "absent_hurt": ["PlayerName"]     // optional
    }
  ]
}
```

**Complete list of dismissal types (`wickets[].kind`):**
- `bowled`
- `caught`
- `caught and bowled`
- `lbw`
- `stumped`
- `run out`
- `hit wicket`
- `retired hurt`
- `retired out`
- `obstructing the field`
- `handled the ball`
- `timed out`

**Complete list of extras types:**
- `wides`
- `noballs`
- `byes`
- `legbyes`
- `penalty`

**Critical parsing rules:**
- Overs are 0-indexed (over `0` = 1st over, over `19` = 20th over)
- Ball number must be derived from the position in the `deliveries` array (0-indexed within each over)
- A wide or no-ball does NOT count as a legal delivery — the ball number should NOT advance
- Multiple wickets CAN fall on the same delivery (extremely rare, e.g., stumping + retired hurt)
- `fielders` array can have 0, 1, or 2+ entries depending on dismissal type
- `super_over` innings are separate innings objects — must be flagged accordingly
- `replacements` occur BEFORE the delivery they're attached to

---

## 🧱 Data Warehouse Schema Design (Star Schema — STRICT)

You MUST implement the following schema exactly. Use **surrogate keys** (auto-incrementing integers) as primary keys for ALL dimension tables. Use **natural keys** as alternate keys where applicable.

### ⭐ Fact Table 1: `fact_deliveries`

**Grain:** One row per ball bowled (including wides/no-balls as separate rows)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `delivery_id` | SERIAL | PK | Auto-incrementing surrogate key |
| `match_key` | INT | FK → dim_match | Surrogate key reference |
| `date_key` | INT | FK → dim_date | Surrogate key reference |
| `venue_key` | INT | FK → dim_venue | Surrogate key reference |
| `batting_team_key` | INT | FK → dim_team | Team batting |
| `bowling_team_key` | INT | FK → dim_team | Team bowling |
| `batsman_key` | INT | FK → dim_player | Striker |
| `non_striker_key` | INT | FK → dim_player | Non-striker |
| `bowler_key` | INT | FK → dim_player | Bowler |
| `innings_number` | SMALLINT | NOT NULL, CHECK(1-4) | 1st, 2nd, super-over = 3,4 |
| `over_number` | SMALLINT | NOT NULL | 0-indexed as per source |
| `ball_number` | SMALLINT | NOT NULL | Position in deliveries array |
| `legal_ball_number` | SMALLINT | NOT NULL | Ball number excluding wides/no-balls |
| `runs_batsman` | SMALLINT | NOT NULL, DEFAULT 0 | Runs scored by batsman |
| `runs_extras` | SMALLINT | NOT NULL, DEFAULT 0 | Total extras on this delivery |
| `runs_total` | SMALLINT | NOT NULL, DEFAULT 0 | runs_batsman + runs_extras |
| `is_boundary_four` | BOOLEAN | NOT NULL, DEFAULT FALSE | Did batsman hit a 4 (boundary only) |
| `is_boundary_six` | BOOLEAN | NOT NULL, DEFAULT FALSE | Did batsman hit a 6 (boundary only) |
| `is_dot_ball` | BOOLEAN | NOT NULL, DEFAULT FALSE | total_runs = 0? |
| `extras_type` | VARCHAR(20) | NULLABLE | 'wide', 'noball', 'bye', 'legbye', 'penalty', NULL |
| `extras_runs` | SMALLINT | NOT NULL, DEFAULT 0 | Runs from this specific extra |
| `is_wicket` | BOOLEAN | NOT NULL, DEFAULT FALSE | Did a wicket fall? |
| `dismissal_type` | VARCHAR(30) | NULLABLE | From dismissal types list |
| `dismissed_player_key` | INT | FK → dim_player, NULLABLE | Player who got out |
| `fielder1_key` | INT | FK → dim_player, NULLABLE | Primary fielder involved |
| `fielder2_key` | INT | FK → dim_player, NULLABLE | Secondary fielder (run outs) |
| `is_wide` | BOOLEAN | NOT NULL, DEFAULT FALSE | Is this a wide delivery |
| `is_noball` | BOOLEAN | NOT NULL, DEFAULT FALSE | Is this a no-ball delivery |
| `is_legal_delivery` | BOOLEAN | NOT NULL | NOT (is_wide OR is_noball) |
| `is_super_over` | BOOLEAN | NOT NULL, DEFAULT FALSE | Is this in a super over |
| `is_powerplay` | BOOLEAN | NOT NULL, DEFAULT FALSE | Is this delivery in powerplay |
| `cumulative_runs` | INT | NOT NULL | Running total of innings so far |
| `cumulative_wickets` | SMALLINT | NOT NULL | Wickets fallen so far in innings |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | ETL load timestamp |

**Indexes:**
```sql
CREATE INDEX idx_fd_match ON fact_deliveries(match_key);
CREATE INDEX idx_fd_batsman ON fact_deliveries(batsman_key);
CREATE INDEX idx_fd_bowler ON fact_deliveries(bowler_key);
CREATE INDEX idx_fd_date ON fact_deliveries(date_key);
CREATE INDEX idx_fd_team_bat ON fact_deliveries(batting_team_key);
CREATE INDEX idx_fd_venue ON fact_deliveries(venue_key);
CREATE INDEX idx_fd_composite ON fact_deliveries(match_key, innings_number, over_number, ball_number);
```

---

### ⭐ Fact Table 2: `fact_match_summary`

**Grain:** One row per match (pre-aggregated for fast dashboard queries)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `match_summary_id` | SERIAL | PK | Surrogate key |
| `match_key` | INT | FK → dim_match, UNIQUE | One summary per match |
| `date_key` | INT | FK → dim_date | Match date reference |
| `venue_key` | INT | FK → dim_venue | Venue reference |
| `team1_key` | INT | FK → dim_team | First team listed |
| `team2_key` | INT | FK → dim_team | Second team listed |
| `toss_winner_key` | INT | FK → dim_team | Toss winner |
| `toss_decision` | VARCHAR(10) | NOT NULL | 'bat' or 'field' |
| `match_winner_key` | INT | FK → dim_team, NULLABLE | NULL if no result/tie without eliminator |
| `win_type` | VARCHAR(10) | NULLABLE | 'runs', 'wickets', NULL |
| `win_margin` | INT | NULLABLE | Margin of victory |
| `is_dls` | BOOLEAN | NOT NULL, DEFAULT FALSE | Was D/L method applied |
| `result` | VARCHAR(20) | NOT NULL | 'normal', 'tie', 'no result' |
| `eliminator_winner_key` | INT | FK → dim_team, NULLABLE | Super over winner in ties |
| `player_of_match_key` | INT | FK → dim_player, NULLABLE | MoM (first if multiple) |
| `team1_score` | INT | NULLABLE | Total runs scored by team1 |
| `team1_wickets` | SMALLINT | NULLABLE | Wickets lost by team1 |
| `team1_overs` | DECIMAL(4,1) | NULLABLE | Overs faced by team1 |
| `team2_score` | INT | NULLABLE | Total runs scored by team2 |
| `team2_wickets` | SMALLINT | NULLABLE | Wickets lost by team2 |
| `team2_overs` | DECIMAL(4,1) | NULLABLE | Overs faced by team2 |
| `total_fours` | INT | NOT NULL, DEFAULT 0 | Fours in entire match |
| `total_sixes` | INT | NOT NULL, DEFAULT 0 | Sixes in entire match |
| `total_extras` | INT | NOT NULL, DEFAULT 0 | Extras in entire match |
| `season` | VARCHAR(10) | NOT NULL | IPL season year |
| `match_number` | INT | NULLABLE | Match number in season |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | ETL timestamp |

---

### 🔷 Dimension Table 1: `dim_player`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `player_key` | SERIAL | PK | Surrogate key |
| `player_id` | VARCHAR(50) | UNIQUE, NOT NULL | Cricsheet registry UUID |
| `player_name` | VARCHAR(100) | NOT NULL | Most recent name used |
| `first_match_date` | DATE | NULLABLE | Earliest match appearance |
| `last_match_date` | DATE | NULLABLE | Latest match appearance |
| `total_matches` | INT | DEFAULT 0 | Running count of matches |
| `is_active` | BOOLEAN | DEFAULT TRUE | Appeared in last 2 seasons? |
| `created_at` | TIMESTAMP | DEFAULT NOW() | |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | |

> **SCD Type 1**: Player names may vary across matches (e.g., "V Kohli" vs "Virat Kohli"). Use the registry UUID as the canonical identifier. Always update to the most recent name encountered.

---

### 🔷 Dimension Table 2: `dim_team`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `team_key` | SERIAL | PK | Surrogate key |
| `team_name` | VARCHAR(100) | UNIQUE, NOT NULL | Current canonical name |
| `team_short_name` | VARCHAR(10) | NULLABLE | e.g., MI, CSK, RCB |
| `is_active` | BOOLEAN | DEFAULT TRUE | Currently participating in IPL |
| `franchise_group` | VARCHAR(100) | NULLABLE | Groups renamed teams together |
| `created_at` | TIMESTAMP | DEFAULT NOW() | |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | |

> **Team name normalization mapping** (MUST be hardcoded):
> ```python
> TEAM_NAME_MAPPING = {
>     "Delhi Daredevils": "Delhi Capitals",
>     "Deccan Chargers": "Sunrisers Hyderabad",
>     "Kings XI Punjab": "Punjab Kings",
>     "Rising Pune Supergiant": "Rising Pune Supergiants",
>     "Rising Pune Supergiants": "Rising Pune Supergiants",
>     "Pune Warriors": "Pune Warriors India",
> }
> ```

---

### 🔷 Dimension Table 3: `dim_venue`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `venue_key` | SERIAL | PK | Surrogate key |
| `venue_name` | VARCHAR(200) | NOT NULL | Full venue name from source |
| `city` | VARCHAR(100) | NULLABLE | City (from `info.city`) |
| `country` | VARCHAR(50) | DEFAULT 'India' | Derived or hardcoded |
| `is_home_ground` | BOOLEAN | DEFAULT FALSE | Known home ground? |
| `created_at` | TIMESTAMP | DEFAULT NOW() | |

---

### 🔷 Dimension Table 4: `dim_date` (Time Dimension — Role-Playing)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `date_key` | SERIAL | PK | Surrogate key |
| `full_date` | DATE | UNIQUE, NOT NULL | Actual date |
| `day_of_week` | SMALLINT | NOT NULL | 0=Monday, 6=Sunday |
| `day_name` | VARCHAR(10) | NOT NULL | Monday, Tuesday, etc. |
| `day_of_month` | SMALLINT | NOT NULL | 1-31 |
| `week_of_year` | SMALLINT | NOT NULL | 1-53 |
| `month_number` | SMALLINT | NOT NULL | 1-12 |
| `month_name` | VARCHAR(10) | NOT NULL | January, February, etc. |
| `quarter` | SMALLINT | NOT NULL | 1-4 |
| `year` | SMALLINT | NOT NULL | e.g., 2023 |
| `season` | VARCHAR(10) | NOT NULL | IPL season identifier |
| `is_weekend` | BOOLEAN | NOT NULL | Saturday or Sunday |
| `is_playoff` | BOOLEAN | DEFAULT FALSE | Qualifier/Eliminator/Final |
| `phase_of_tournament` | VARCHAR(20) | NULLABLE | 'League', 'Playoff', 'Final' |

---

### 🔷 Dimension Table 5: `dim_match`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `match_key` | SERIAL | PK | Surrogate key |
| `match_id` | VARCHAR(50) | UNIQUE, NOT NULL | Filename without extension |
| `season` | VARCHAR(10) | NOT NULL | IPL season |
| `match_number` | INT | NULLABLE | Match number in season |
| `match_type` | VARCHAR(10) | NOT NULL | 'T20' |
| `gender` | VARCHAR(10) | NOT NULL | 'male' |
| `balls_per_over` | SMALLINT | NOT NULL, DEFAULT 6 | |
| `overs_per_side` | SMALLINT | NOT NULL, DEFAULT 20 | |
| `data_version` | VARCHAR(10) | NOT NULL | Cricsheet data version |
| `created_at` | TIMESTAMP | DEFAULT NOW() | |

---

### 🔷 Dimension Table 6: `dim_innings`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `innings_key` | SERIAL | PK | Surrogate key |
| `match_key` | INT | FK → dim_match | Match reference |
| `innings_number` | SMALLINT | NOT NULL | 1, 2, 3 (super over), etc. |
| `batting_team_key` | INT | FK → dim_team | |
| `bowling_team_key` | INT | FK → dim_team | |
| `total_runs` | INT | DEFAULT 0 | |
| `total_wickets` | SMALLINT | DEFAULT 0 | |
| `total_overs` | DECIMAL(4,1) | NULLABLE | Overs bowled |
| `total_extras` | INT | DEFAULT 0 | |
| `is_super_over` | BOOLEAN | DEFAULT FALSE | |
| `target_runs` | INT | NULLABLE | Target (2nd innings only) |
| `target_overs` | INT | NULLABLE | Target overs |
| `has_dls` | BOOLEAN | DEFAULT FALSE | |
| `is_forfeited` | BOOLEAN | DEFAULT FALSE | |
| `created_at` | TIMESTAMP | DEFAULT NOW() | |

---

### 🔷 Dimension Table 7: `dim_dismissal_type`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `dismissal_key` | SERIAL | PK | Surrogate key |
| `dismissal_type` | VARCHAR(30) | UNIQUE, NOT NULL | e.g., 'caught', 'bowled' |
| `is_bowler_credited` | BOOLEAN | NOT NULL | Does bowler get wicket credit |
| `is_fielder_involved` | BOOLEAN | NOT NULL | Is a fielder involved |
| `description` | VARCHAR(200) | NULLABLE | Human-readable explanation |

Pre-populated data:
```sql
INSERT INTO dim_dismissal_type (dismissal_type, is_bowler_credited, is_fielder_involved, description) VALUES
('bowled', TRUE, FALSE, 'Bowler hits the stumps'),
('caught', TRUE, TRUE, 'Batsman caught by fielder'),
('caught and bowled', TRUE, FALSE, 'Caught by the bowler'),
('lbw', TRUE, FALSE, 'Leg before wicket'),
('stumped', TRUE, TRUE, 'Wicketkeeper disturbs stumps'),
('run out', FALSE, TRUE, 'Batsman run out'),
('hit wicket', TRUE, FALSE, 'Batsman hits own stumps'),
('retired hurt', FALSE, FALSE, 'Batsman retires due to injury'),
('retired out', FALSE, FALSE, 'Batsman retires voluntarily'),
('obstructing the field', FALSE, FALSE, 'Batsman obstructs fielding'),
('handled the ball', FALSE, FALSE, 'Batsman handles ball illegally'),
('timed out', FALSE, FALSE, 'Incoming batsman timed out');
```

---

### 🔷 Dimension Table 8: `dim_extras_type`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `extras_key` | SERIAL | PK | |
| `extras_type` | VARCHAR(20) | UNIQUE, NOT NULL | wide, noball, bye, legbye, penalty |
| `is_charged_to_bowler` | BOOLEAN | NOT NULL | Affects bowler's economy |
| `is_legal_delivery` | BOOLEAN | NOT NULL | Does ball count as legal |

---

### 📋 Metadata Tables

#### `etl_run_log`
| Column | Type | Description |
|--------|------|-------------|
| `run_id` | SERIAL PK | |
| `started_at` | TIMESTAMP | When ETL started |
| `completed_at` | TIMESTAMP | When ETL finished (NULL if failed) |
| `status` | VARCHAR(20) | 'running', 'success', 'failed' |
| `files_processed` | INT | Number of JSON files processed |
| `files_skipped` | INT | Number of files skipped (errors) |
| `rows_loaded` | INT | Total rows inserted into fact tables |
| `error_message` | TEXT | Error details if failed |
| `pipeline_version` | VARCHAR(20) | Version of ETL code |

#### `data_quality_log`
| Column | Type | Description |
|--------|------|-------------|
| `dq_id` | SERIAL PK | |
| `run_id` | INT FK | Reference to ETL run |
| `check_name` | VARCHAR(100) | Name of DQ check |
| `table_name` | VARCHAR(50) | Table checked |
| `check_type` | VARCHAR(30) | 'null_check', 'range_check', 'referential', 'duplicate', 'business_rule' |
| `records_checked` | INT | |
| `records_failed` | INT | |
| `pass_rate` | DECIMAL(5,2) | % of records passing |
| `severity` | VARCHAR(10) | 'critical', 'warning', 'info' |
| `details` | TEXT | Additional details |
| `checked_at` | TIMESTAMP | |

---

## 🐍 Complete Project Structure (MANDATORY)

```
ipl-data-warehouse/
│
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions CI/CD pipeline
│
├── config/
│   ├── __init__.py
│   ├── settings.py                   # Centralized configuration (env vars, DB URLs, paths)
│   └── logging_config.py            # Structured logging configuration
│
├── data/
│   ├── raw/                          # Extracted JSON files (gitignored)
│   └── processed/                    # Intermediate CSVs for debugging (gitignored)
│
├── etl/
│   ├── __init__.py
│   ├── extract.py                    # Download ZIP, extract, iterate files
│   ├── validate.py                   # JSON schema validation + business rule checks
│   ├── transform.py                  # Parse JSON → DataFrames (matches, deliveries, players, etc.)
│   ├── transform_helpers.py          # Team name normalization, date parsing, ID generation
│   ├── load.py                       # Upsert into PostgreSQL (dimensions first, then facts)
│   ├── data_quality.py               # Post-load DQ checks + logging
│   └── pipeline.py                   # Orchestrates full ETL: extract → validate → transform → load → DQ
│
├── sql/
│   ├── 01_create_schema.sql          # All CREATE TABLE statements with constraints
│   ├── 02_create_indexes.sql         # All index creation statements
│   ├── 03_seed_dimensions.sql        # Pre-populate dim_dismissal_type, dim_extras_type
│   ├── 04_analytical_queries.sql     # All 20+ analytical queries
│   ├── 05_olap_operations.sql        # Explicit OLAP demonstrations
│   ├── 06_create_views.sql           # Materialized views for dashboard performance
│   └── 07_stored_procedures.sql      # Stored procedures for common operations
│
├── dashboard/
│   ├── __init__.py
│   ├── app.py                        # Main Streamlit application
│   ├── pages/
│   │   ├── 01_overview.py            # Season overview, key metrics
│   │   ├── 02_batting_analysis.py    # Batting stats, comparisons
│   │   ├── 03_bowling_analysis.py    # Bowling stats, economy, wickets
│   │   ├── 04_team_performance.py    # Team win/loss, NRR, head-to-head
│   │   └── 05_venue_insights.py      # Venue-wise analysis, toss impact
│   ├── components/
│   │   ├── charts.py                 # Reusable Plotly chart functions
│   │   ├── filters.py                # Sidebar filter components
│   │   └── metrics.py                # KPI card components
│   └── utils/
│       └── db.py                     # Database connection for dashboard
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures (sample data, DB connections)
│   ├── test_extract.py               # Tests for extraction logic
│   ├── test_validate.py              # Tests for validation rules
│   ├── test_transform.py             # Tests for transformation logic
│   ├── test_load.py                  # Tests for load operations
│   ├── test_data_quality.py          # Tests for DQ framework
│   ├── test_pipeline.py              # Integration tests for full pipeline
│   └── fixtures/
│       ├── sample_match.json         # A complete sample match JSON for testing
│       ├── malformed_match.json      # Intentionally broken JSON for error tests
│       └── edge_case_match.json      # Match with ties, DLS, super over, etc.
│
├── docker/
│   ├── Dockerfile                    # Multi-stage build for ETL + Dashboard
│   └── docker-compose.yml            # Local dev with PostgreSQL + app
│
├── docs/
│   ├── architecture.md               # Architecture decision records
│   ├── schema_diagram.md             # ER diagram (mermaid syntax)
│   └── deployment_guide.md           # Step-by-step deployment instructions
│
├── .env.example                      # Template for environment variables
├── .gitignore                        # Ignore data/, .env, __pycache__, etc.
├── requirements.txt                  # All Python dependencies with pinned versions
├── Procfile                          # For Railway/Render deployment
├── runtime.txt                       # Python version specification
└── README.md                         # Comprehensive project documentation
```

---

## ⚙️ ETL Pipeline — Detailed Implementation Requirements

### `config/settings.py`

```python
# Must use pydantic-settings or python-dotenv for configuration management
# Required settings:
DATABASE_URL: str          # PostgreSQL connection string
DATA_SOURCE_URL: str       # https://cricsheet.org/downloads/ipl_json.zip
RAW_DATA_DIR: Path         # data/raw/
PROCESSED_DATA_DIR: Path   # data/processed/
BATCH_SIZE: int            # Records per batch insert (default: 1000)
LOG_LEVEL: str             # DEBUG, INFO, WARNING, ERROR
ETL_VERSION: str           # Semantic version of the pipeline
ENABLE_DQ_CHECKS: bool     # Toggle data quality checks
```

### `etl/extract.py` — Extract Layer

**Requirements:**
1. Download ZIP from `DATA_SOURCE_URL` with:
   - Retry logic (3 attempts with exponential backoff)
   - Progress bar using `tqdm`
   - SHA256 checksum comparison to skip re-download if file unchanged
   - Proper timeout handling (connect=10s, read=60s)
2. Extract ZIP to `RAW_DATA_DIR`:
   - Handle corrupted ZIP files gracefully
   - Skip non-JSON files in the archive
   - Log count of extracted files
3. Return a list of `Path` objects pointing to all valid JSON files
4. Support incremental extraction: compare against `etl_run_log` to process only new files

### `etl/validate.py` — Validation Layer

**Requirements:**
1. **Schema validation**: Verify each JSON file has mandatory keys: `meta`, `info`, `innings`
2. **Data type validation**: Ensure `dates` is a list, `teams` has exactly 2 entries, `overs` is within each innings
3. **Business rule validation**:
   - Each match has exactly 2 or 4 innings (including super overs)
   - `balls_per_over` is 6 (for IPL)
   - Teams in `players` dict match teams in `teams` array
   - All player names in `innings` exist in `players` or `registry`
4. **Return structure**: A `ValidationResult` dataclass with:
   - `is_valid: bool`
   - `file_path: Path`
   - `errors: List[str]`
   - `warnings: List[str]`
5. Invalid files should be moved to a `data/rejected/` folder with error logs

### `etl/transform.py` — Transform Layer

**Requirements:**
1. Parse every JSON file and produce these pandas DataFrames:
   - `df_matches`: One row per match
   - `df_innings`: One row per innings
   - `df_deliveries`: One row per ball bowled
   - `df_players`: One row per unique player (deduplicated by registry UUID)
   - `df_teams`: One row per unique team (after normalization)
   - `df_venues`: One row per unique venue + city combination
   - `df_dates`: One row per unique date

2. **Delivery-level transformation** (most complex — be meticulous):
   - Flatten the nested `innings → overs → deliveries` structure
   - Compute `ball_number` from position in the deliveries array
   - Compute `legal_ball_number` (skip wides and no-balls)
   - Determine `is_boundary_four` and `is_boundary_six` (checking `non_boundary` flag)
   - Extract extras type and runs from the `extras` object
   - Extract wicket information including dismissal type, player out, and fielders
   - Handle multiple wickets on same delivery
   - Compute cumulative runs and wickets within each innings
   - Flag powerplay deliveries by cross-referencing `powerplays` data
   - Flag super over deliveries

3. **Team name normalization**: Apply the hardcoded mapping for historical team name changes

4. **Player deduplication**: Use `registry.people` UUIDs as canonical identifiers. When the same UUID appears with different names across matches, keep the most recent name.

5. **Date dimension generation**: Generate all date attributes (day_name, quarter, week, etc.) for every unique match date

6. **Null handling strategy**:
   - `player_of_match`: Can be NULL for some matches → handle gracefully
   - `city`: Can be missing → default to 'Unknown'
   - `officials`: Entirely optional → skip if missing
   - `outcome.method`: Only present for DLS matches → NULL otherwise
   - `extras` on delivery: Only present when extras actually occurred → NULL or 0

### `etl/load.py` — Load Layer

**Requirements:**
1. **Connection management**: Use `psycopg2` with connection pooling (`psycopg2.pool.ThreadedConnectionPool`)
2. **Load order** (strict — referential integrity demands this):
   1. `dim_date`
   2. `dim_venue`
   3. `dim_team`
   4. `dim_player`
   5. `dim_match`
   6. `dim_innings`
   7. `dim_dismissal_type` (pre-seeded, upsert only)
   8. `dim_extras_type` (pre-seeded, upsert only)
   9. `fact_match_summary`
   10. `fact_deliveries`

3. **Upsert strategy**: Use `INSERT ... ON CONFLICT DO UPDATE` for all dimension tables
4. **Batch inserts**: Use `psycopg2.extras.execute_values()` for bulk inserts with configurable batch size
5. **Transaction management**: Each match should be loaded within a single transaction — if any part fails, roll back the entire match
6. **Surrogate key resolution**: After upserting dimensions, fetch back the generated surrogate keys and map them into the fact DataFrames before loading facts
7. **Idempotency**: Re-running the pipeline on the same data MUST NOT create duplicates. Use `match_id` + `innings_number` + `over_number` + `ball_number` as the natural key for deduplication.

### `etl/data_quality.py` — Post-Load Quality Checks

**Requirements:**
Run these checks AFTER loading and log results to `data_quality_log`:

| Check | Table | Type | Severity |
|-------|-------|------|----------|
| No NULL match_keys in facts | fact_deliveries | null_check | critical |
| runs_total = runs_batsman + runs_extras | fact_deliveries | business_rule | critical |
| Every match has a match_summary | fact_match_summary | completeness | critical |
| No orphaned foreign keys | all fact tables | referential | critical |
| Over numbers between 0-19 (IPL) | fact_deliveries | range_check | warning |
| No duplicate deliveries | fact_deliveries | duplicate | critical |
| Total match runs = sum of delivery runs | fact_match_summary | reconciliation | warning |
| Player match count consistency | dim_player | aggregation | info |
| Team names are all normalized | dim_team | business_rule | warning |
| Minimum deliveries per innings >= 1 | fact_deliveries | business_rule | warning |

### `etl/pipeline.py` — Orchestrator

```python
# Must implement this interface:
class ETLPipeline:
    def run(self, full_refresh: bool = False) -> ETLResult:
        """
        Execute the complete ETL pipeline.
        
        Args:
            full_refresh: If True, truncate all tables and reload.
                         If False, only process new/updated files.
        
        Returns:
            ETLResult with stats (files_processed, rows_loaded, duration, errors)
        """
        
    def run_extract(self) -> List[Path]: ...
    def run_validate(self, files: List[Path]) -> Tuple[List[Path], List[Path]]: ...
    def run_transform(self, valid_files: List[Path]) -> TransformResult: ...
    def run_load(self, data: TransformResult) -> LoadResult: ...
    def run_quality_checks(self, run_id: int) -> QualityResult: ...
```

**Pipeline must:**
1. Log start/end to `etl_run_log`
2. Handle partial failures gracefully (process remaining files even if some fail)
3. Support both `--full-refresh` and incremental modes
4. Print a summary report at the end with statistics
5. Use structured logging (JSON format) throughout

---

## 🗄️ Analytical Queries (MINIMUM 20)

All queries go in `sql/04_analytical_queries.sql`. Each must have:
- A descriptive comment header
- The SQL query itself
- Expected output column descriptions

### Category 1: Batting Analysis (5 queries)
1. **Top 20 Run Scorers (All-Time)** — player_name, total_runs, innings, avg, strike_rate, 4s, 6s
2. **Highest Individual Scores** — player_name, runs_in_match, match details, was_not_out
3. **Best Strike Rates** (min 500 runs) — with balls faced and boundary percentage
4. **Most Boundaries (4s + 6s) per Season** — season-wise breakdown with RANK()
5. **Batting Average by Position** (1-7) — inferred from batting order in innings

### Category 2: Bowling Analysis (5 queries)
6. **Top 20 Wicket Takers** — player_name, wickets, matches, avg, economy, strike_rate
7. **Best Bowling Figures in a Match** — player, wickets, runs conceded, overs, match details
8. **Best Economy Rates** (min 300 balls bowled) — with dot ball percentage
9. **Most Dot Balls Bowled** — per season and career
10. **Wickets by Dismissal Type** — breakdown of caught, bowled, lbw, etc. with percentages

### Category 3: Team Analysis (5 queries)
11. **Win/Loss Record per Team per Season** — with win percentage
12. **Head-to-Head Records** — every team pair combination with wins, losses, ties
13. **Highest & Lowest Team Totals** — with opponent and venue details
14. **Net Run Rate Approximation per Season** — (runs scored/overs - runs conceded/overs)
15. **Runs Scored per Over (Phase Analysis)** — powerplay (1-6), middle (7-15), death (16-20)

### Category 4: Venue & Toss Analysis (3 queries)
16. **Venue Win Percentage (Bat First vs Field First)** — per venue
17. **Toss Impact Analysis** — does winning toss correlate with winning match? By season
18. **Highest Scoring Venues** — avg 1st innings score, avg 2nd innings score, top venue for chases

### Category 5: Advanced/Trend Analysis (4 queries)
19. **Season-over-Season Scoring Trends** — avg match total, avg strike rate, boundary % by year
20. **Player Consistency Index** — std deviation of scores, coefficient of variation for top batsmen
21. **Clutch Performance** — batting average in run chases vs setting targets
22. **Powerplay vs Death Over Specialists** — players with highest SR in specific phases

---

## 📊 OLAP Operations (Explicit Demonstrations)

File: `sql/05_olap_operations.sql`

### 1. ROLL-UP (Drill Up)
```sql
-- Roll-up from match → season → all-time for team runs
-- Using ROLLUP clause
SELECT 
    COALESCE(d.season, 'ALL SEASONS') AS season,
    COALESCE(t.team_name, 'ALL TEAMS') AS team,
    SUM(fd.runs_batsman) AS total_runs,
    COUNT(DISTINCT fd.match_key) AS matches
FROM fact_deliveries fd
JOIN dim_date d ON fd.date_key = d.date_key
JOIN dim_team t ON fd.batting_team_key = t.team_key
GROUP BY ROLLUP(d.season, t.team_name)
ORDER BY season, team;
```

### 2. DRILL-DOWN
```sql
-- Drill down from season → match → innings → over → ball for a specific player
-- Hierarchical analysis at multiple granularity levels
```

### 3. SLICE
```sql
-- Slice: Fix one dimension (e.g., team = 'Mumbai Indians'), analyze across others
```

### 4. DICE
```sql
-- Dice: Multiple dimension filters (season 2020-2023, venue in Mumbai/Chennai, powerplay overs)
```

### 5. PIVOT
```sql
-- Pivot: Teams as rows, seasons as columns, values = win count
-- Using CROSSTAB or CASE WHEN
```

---

## 📊 Streamlit Dashboard Requirements

### `dashboard/app.py`

**Tech Stack:**
- Streamlit (latest stable)
- Plotly Express for interactive charts
- pandas for data manipulation
- psycopg2 for DB connection (with `@st.cache_data` for query caching)

**Dashboard Pages:**

#### Page 1: Season Overview (`01_overview.py`)
- **KPI Cards**: Total matches, total runs, total wickets, avg score per match
- **Season selector** dropdown
- **Matches timeline**: Interactive scatter/line chart of matches by date
- **Win distribution**: Pie chart of wins by team (filterable by season)

#### Page 2: Batting Analysis (`02_batting_analysis.py`)
- **Top batsmen table**: Sortable by runs, avg, SR, boundaries
- **Player comparison**: Multi-select to compare up to 4 batsmen
- **Run distribution**: Histogram of individual innings scores
- **Phase analysis**: Bar chart of runs in powerplay vs middle vs death

#### Page 3: Bowling Analysis (`03_bowling_analysis.py`)
- **Top bowlers table**: Sortable by wickets, economy, avg, SR
- **Dismissal type breakdown**: Treemap or sunburst chart
- **Economy rate by over**: Line chart showing avg economy per over (1-20)
- **Dot ball percentage**: Bar chart for top bowlers

#### Page 4: Team Performance (`04_team_performance.py`)
- **Season-wise standings**: Table with W/L/NRR
- **Head-to-head matrix**: Heatmap of team vs team win records
- **Score progression**: Line chart of team totals over a season
- **Win type distribution**: Stacked bar of wins by runs vs wickets

#### Page 5: Venue Insights (`05_venue_insights.py`)
- **Venue statistics**: Avg score, avg wickets, toss decision distribution
- **Bat first vs chase**: Win % comparison per venue
- **Top performers at each venue**: Filterable by venue

**Design Requirements:**
- Dark theme using `st.set_page_config(layout="wide")`
- Custom CSS for professional look
- Loading spinners for DB queries
- Error handling with user-friendly messages
- Mobile-responsive layout

---

## 🧪 Testing Strategy

### Unit Tests (`tests/test_*.py`)

| Test File | What to Test |
|-----------|-------------|
| `test_extract.py` | Download retry logic, ZIP extraction, file listing |
| `test_validate.py` | Schema validation pass/fail, business rule checks, edge cases |
| `test_transform.py` | JSON parsing correctness, team normalization, delivery flattening, null handling |
| `test_load.py` | Upsert behavior, surrogate key resolution, batch insert, idempotency |
| `test_data_quality.py` | Each DQ check individually, logging behavior |

### Integration Test (`tests/test_pipeline.py`)
- Process a single known JSON file end-to-end
- Verify row counts in all tables
- Verify data accuracy against manually calculated values
- Run full DQ suite and assert all pass

### Test Fixtures (`tests/fixtures/`)
- `sample_match.json`: A complete, valid match JSON (copy a real one from the dataset)
- `malformed_match.json`: Missing `innings`, wrong types, etc.
- `edge_case_match.json`: Match with tie, super over, DLS, missing player_of_match, extras on wicket ball

**Framework:** pytest with pytest-cov for coverage reporting (target: >85%)

---

## 🐳 Docker Configuration

### `docker/Dockerfile`
```dockerfile
# Multi-stage build
# Stage 1: Build dependencies
# Stage 2: Runtime with slim Python image
# Install only production dependencies
# Copy ETL + Dashboard code
# Expose port 8501 for Streamlit
# CMD: Run pipeline then start dashboard
```

### `docker/docker-compose.yml`
```yaml
# Services:
#   postgres:
#     image: postgres:16-alpine
#     environment: DB credentials
#     volumes: persistent data
#     healthcheck: pg_isready
#   
#   app:
#     build: context
#     depends_on: postgres (healthy)
#     environment: DATABASE_URL
#     ports: 8501
```

---

## 🚀 Deployment Instructions (CRITICAL)

### Database: Supabase (Free Tier)

1. Create Supabase project at https://supabase.com
2. Get the PostgreSQL connection string from Settings → Database
3. Connection string format: `postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`
4. Run `sql/01_create_schema.sql` through Supabase SQL Editor
5. Run `sql/02_create_indexes.sql`
6. Run `sql/03_seed_dimensions.sql`

### ETL + Dashboard: Railway (Free Tier)

1. Push code to GitHub repository
2. Connect Railway to the GitHub repo
3. Set environment variables:
   - `DATABASE_URL` = Supabase connection string
   - `PYTHON_VERSION` = 3.11
   - `PORT` = 8501
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python -m etl.pipeline --full-refresh && streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0`

### Alternative: Render (Free Tier)

1. Create a new Web Service on Render
2. Connect to GitHub repo
3. Set environment: Python 3
4. Build: `pip install -r requirements.txt`
5. Start: `streamlit run dashboard/app.py --server.port $PORT`
6. Add Cron Job for ETL: separate service running `python -m etl.pipeline` on schedule

### Keeping ETL Updated (Scheduling Options):

**Option A — Railway Cron:**
- Create a separate Railway service for ETL
- Set as Cron Job: `0 6 * * *` (daily at 6 AM UTC)

**Option B — GitHub Actions Schedule:**
```yaml
on:
  schedule:
    - cron: '0 6 * * *'
jobs:
  run-etl:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: python -m etl.pipeline
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

**Option C — In-app scheduler (for single-service deployments):**
```python
# Use APScheduler within the Streamlit app
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(run_pipeline, 'cron', hour=6)
scheduler.start()
```

---

## 🔧 CI/CD Pipeline (`.github/workflows/ci.yml`)

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: test_ipl_dw
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=etl --cov=dashboard --cov-report=xml
        env:
          DATABASE_URL: postgresql://postgres:testpass@localhost:5432/test_ipl_dw
      - uses: codecov/codecov-action@v3

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      # Deploy to Railway/Render via webhook or CLI
```

---

## 📄 README.md Structure (MANDATORY)

The README must include ALL of these sections:

1. **Project Title + Badges** (build status, coverage, Python version)
2. **Project Overview** (1 paragraph)
3. **Architecture Diagram** (Mermaid or ASCII)
4. **Tech Stack** (table format)
5. **Data Source** (with link and format description)
6. **Database Schema** (ER diagram in Mermaid)
7. **ETL Pipeline** (flow diagram + description of each stage)
8. **Setup Instructions**
   - Prerequisites
   - Local setup with Docker
   - Manual setup without Docker
   - Environment variables
9. **Running the ETL**
   - Full refresh: `python -m etl.pipeline --full-refresh`
   - Incremental: `python -m etl.pipeline`
10. **Running the Dashboard**
    - `streamlit run dashboard/app.py`
11. **Running Tests**
    - `pytest tests/ -v`
12. **Deployment Guide** (condensed from docs/deployment_guide.md)
13. **Sample Queries** (top 5 most interesting analytical queries with expected output)
14. **OLAP Operations** (brief explanation with examples)
15. **Project Structure** (tree diagram)
16. **Contributing** (for academic context: how to extend)
17. **License** (MIT)

---

## 📦 `requirements.txt` (Pinned Versions)

```
pandas>=2.1.0
psycopg2-binary>=2.9.9
requests>=2.31.0
tqdm>=4.66.0
python-dotenv>=1.0.0
streamlit>=1.28.0
plotly>=5.18.0
sqlalchemy>=2.0.0
pytest>=7.4.0
pytest-cov>=4.1.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
```

---

## 🧠 Final Instructions to the AI

You are simultaneously acting as:
- **Senior Data Engineer** — Build the ETL pipeline with production-grade error handling, logging, and idempotency
- **Data Warehouse Architect** — Design the star schema with proper dimensional modeling, surrogate keys, and SCD handling
- **Data Analyst** — Write meaningful analytical queries that provide genuine cricket insights
- **Full-Stack Developer** — Build the Streamlit dashboard with professional UX
- **DevOps Engineer** — Configure Docker, CI/CD, and cloud deployment
- **QA Engineer** — Write comprehensive tests with edge case coverage

### Non-Negotiable Quality Standards:
1. ✅ Every Python file must have type hints on ALL function signatures
2. ✅ Every function must have a docstring (Google style)
3. ✅ Every SQL file must have descriptive comments
4. ✅ All errors must be caught, logged, and handled — NEVER crash silently
5. ✅ All database operations must use parameterized queries (SQL injection prevention)
6. ✅ All configuration must come from environment variables (no hardcoded secrets)
7. ✅ All file I/O must use context managers
8. ✅ Use `pathlib.Path` instead of `os.path` for all file operations
9. ✅ Follow PEP 8 naming conventions strictly
10. ✅ Git-ignore all data files, `.env`, and `__pycache__`

### Output Format:
Produce ALL files in the project structure listed above, with complete, executable code. Start with the configuration layer, then schema SQL, then ETL modules (extract → validate → transform → load → pipeline), then dashboard, then tests, then Docker/CI files, then documentation.

**NO placeholders. NO TODOs. NO pseudo-code. NO shortcuts. EVERYTHING must be complete and runnable.**
