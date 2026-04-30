import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

@pytest.fixture
def sample_match_json():
    return {
        "meta": {"data_version": "1.1.0", "created": "2023-01-01", "revision": 1},
        "info": {
            "balls_per_over": 6,
            "city": "Mumbai",
            "dates": ["2023-04-01"],
            "event": {"name": "Indian Premier League", "match_number": 1},
            "gender": "male",
            "match_type": "T20",
            "overs": 20,
            "outcome": {"winner": "Mumbai Indians", "by": {"runs": 25}},
            "players": {
                "Mumbai Indians": ["Player A", "Player B"],
                "Chennai Super Kings": ["Player C", "Player D"],
            },
            "registry": {
                "people": {
                    "Player A": "uuid-a-001",
                    "Player B": "uuid-b-002",
                    "Player C": "uuid-c-003",
                    "Player D": "uuid-d-004",
                }
            },
            "season": "2023",
            "teams": ["Mumbai Indians", "Chennai Super Kings"],
            "toss": {"decision": "field", "winner": "Mumbai Indians"},
            "venue": "Wankhede Stadium",
            "player_of_match": ["Player A"],
        },
        "innings": [
            {
                "team": "Mumbai Indians",
                "overs": [
                    {
                        "over": 0,
                        "deliveries": [
                            {
                                "batter": "Player A",
                                "bowler": "Player D",
                                "non_striker": "Player B",
                                "runs": {"batter": 4, "extras": 0, "total": 4},
                            },
                            {
                                "batter": "Player A",
                                "bowler": "Player D",
                                "non_striker": "Player B",
                                "runs": {"batter": 0, "extras": 1, "total": 1},
                                "extras": {"wides": 1},
                            },
                            {
                                "batter": "Player A",
                                "bowler": "Player D",
                                "non_striker": "Player B",
                                "runs": {"batter": 6, "extras": 0, "total": 6},
                            },
                            {
                                "batter": "Player B",
                                "bowler": "Player D",
                                "non_striker": "Player A",
                                "runs": {"batter": 0, "extras": 0, "total": 0},
                                "wickets": [
                                    {
                                        "player_out": "Player B",
                                        "kind": "bowled",
                                        "fielders": [],
                                    }
                                ],
                            },
                            {
                                "batter": "Player A",
                                "bowler": "Player D",
                                "non_striker": "Player B",
                                "runs": {"batter": 1, "extras": 0, "total": 1},
                            },
                            {
                                "batter": "Player B",
                                "bowler": "Player D",
                                "non_striker": "Player A",
                                "runs": {"batter": 2, "extras": 0, "total": 2},
                            },
                            {
                                "batter": "Player A",
                                "bowler": "Player D",
                                "non_striker": "Player B",
                                "runs": {"batter": 0, "extras": 0, "total": 0},
                            },
                        ],
                    }
                ],
            },
            {
                "team": "Chennai Super Kings",
                "overs": [
                    {
                        "over": 0,
                        "deliveries": [
                            {
                                "batter": "Player C",
                                "bowler": "Player A",
                                "non_striker": "Player D",
                                "runs": {"batter": 2, "extras": 0, "total": 2},
                            },
                            {
                                "batter": "Player C",
                                "bowler": "Player A",
                                "non_striker": "Player D",
                                "runs": {"batter": 0, "extras": 0, "total": 0},
                            },
                        ],
                    }
                ],
            },
        ],
    }

@pytest.fixture
def sample_match_file(tmp_path, sample_match_json):
    file_path = tmp_path / "9999999.json"
    with open(file_path, "w") as f:
        json.dump(sample_match_json, f)
    return file_path

@pytest.fixture
def sample_deliveries_df():
    return pd.DataFrame(
        [
            {
                "match_id": "9999999",
                "innings_number": 1,
                "over_number": 0,
                "ball_number": 0,
                "legal_ball_number": 1,
                "batsman": "Player A",
                "bowler": "Player D",
                "runs_batsman": 4,
                "runs_extras": 0,
                "runs_total": 4,
                "is_boundary_four": True,
                "is_boundary_six": False,
                "is_dot_ball": False,
                "is_wicket": False,
                "is_wide": False,
                "is_noball": False,
                "is_legal_delivery": True,
            },
            {
                "match_id": "9999999",
                "innings_number": 1,
                "over_number": 0,
                "ball_number": 1,
                "legal_ball_number": 1,
                "batsman": "Player A",
                "bowler": "Player D",
                "runs_batsman": 0,
                "runs_extras": 1,
                "runs_total": 1,
                "is_boundary_four": False,
                "is_boundary_six": False,
                "is_dot_ball": False,
                "is_wicket": False,
                "is_wide": True,
                "is_noball": False,
                "is_legal_delivery": False,
            },
        ]
    )

@pytest.fixture
def mock_db_connection():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.return_value = (1,)
    cursor.fetchall.return_value = []
    return conn, cursor
