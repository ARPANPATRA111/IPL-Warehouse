from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from etl.load import DatabaseLoader, FileRegistryEntry

class TestDatabaseLoader:

    @patch("etl.load.psycopg2.pool.ThreadedConnectionPool")
    def test_get_pool_creates_pool(self, mock_pool_cls):
        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        pool = loader.get_pool()
        mock_pool_cls.assert_called_once()

    @patch("etl.load.psycopg2.pool.ThreadedConnectionPool")
    def test_get_pool_reuses_pool(self, mock_pool_cls):
        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        mock_pool_cls.return_value.closed = False
        pool1 = loader.get_pool()
        pool2 = loader.get_pool()
        assert mock_pool_cls.call_count == 1

    def test_load_dim_dates_empty(self):
        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        result = loader.load_dim_dates(pd.DataFrame())
        assert result == {}

    def test_load_dim_teams_empty(self):
        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        result = loader.load_dim_teams(pd.DataFrame())
        assert result == {}

    def test_load_dim_players_empty(self):
        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        result = loader.load_dim_players(pd.DataFrame())
        assert result == {}

    def test_load_fact_deliveries_empty(self):
        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        result = loader.load_fact_deliveries(
            pd.DataFrame(), {}, {}, {}, {}, {}, {}
        )
        assert result.rows_loaded == 0

    @patch("etl.load.psycopg2.pool.ThreadedConnectionPool")
    @patch("etl.load.psycopg2.extras.execute_values")
    def test_load_dim_matches_converts_nan_to_none(self, mock_execute_values, mock_pool_cls):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool_cls.return_value.getconn.return_value = mock_conn
        mock_pool_cls.return_value.closed = False
        mock_execute_values.return_value = [("12345", 1)]

        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        df = pd.DataFrame([
            {
                "match_id": "12345",
                "season": "2024",
                "match_number": float("nan"),
                "match_type": "T20",
                "gender": "male",
                "balls_per_over": 6,
                "overs_per_side": 20,
                "data_version": "1.0.0",
            }
        ])

        result = loader.load_dim_matches(df)

        values = mock_execute_values.call_args[0][2]
        assert values[0][2] is None
        assert result == {"12345": 1}

    def test_resolve_venue_key_handles_unknown_city(self):
        row = {"venue": "Wankhede Stadium", "city": "Unknown"}
        venue_map = {"Wankhede Stadium|": 7}

        result = DatabaseLoader._resolve_venue_key(row, venue_map)

        assert result == 7

    @patch("etl.load.psycopg2.pool.ThreadedConnectionPool")
    @patch("etl.load.psycopg2.extras.execute_values")
    def test_load_fact_deliveries_commits_successful_matches(self, mock_execute_values, mock_pool_cls):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool_cls.return_value.getconn.return_value = mock_conn
        mock_pool_cls.return_value.closed = False

        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        df = pd.DataFrame([
            {
                "match_id": "m1",
                "match_date": date(2024, 1, 1),
                "venue": "Venue A",
                "city": "Unknown",
                "batting_team": "Team A",
                "bowling_team": "Team B",
                "batsman": "Player A",
                "non_striker": "Player B",
                "bowler": "Player C",
                "dismissed_player": None,
                "fielder1": None,
                "fielder2": None,
                "innings_number": 1,
                "over_number": 0,
                "ball_number": 0,
                "legal_ball_number": 1,
                "runs_batsman": 1,
                "runs_extras": 0,
                "runs_total": 1,
                "is_boundary_four": False,
                "is_boundary_six": False,
                "is_dot_ball": False,
                "extras_type": None,
                "extras_runs": 0,
                "is_wicket": False,
                "dismissal_type": None,
                "is_wide": False,
                "is_noball": False,
                "is_legal_delivery": True,
                "is_super_over": False,
                "is_powerplay": True,
                "cumulative_runs": 1,
                "cumulative_wickets": 0,
            },
            {
                "match_id": "m2",
                "match_date": date(2024, 1, 2),
                "venue": "Venue B",
                "city": "Unknown",
                "batting_team": "Missing Team",
                "bowling_team": "Team B",
                "batsman": "Player A",
                "non_striker": "Player B",
                "bowler": "Player C",
                "dismissed_player": None,
                "fielder1": None,
                "fielder2": None,
                "innings_number": 1,
                "over_number": 0,
                "ball_number": 0,
                "legal_ball_number": 1,
                "runs_batsman": 1,
                "runs_extras": 0,
                "runs_total": 1,
                "is_boundary_four": False,
                "is_boundary_six": False,
                "is_dot_ball": False,
                "extras_type": None,
                "extras_runs": 0,
                "is_wicket": False,
                "dismissal_type": None,
                "is_wide": False,
                "is_noball": False,
                "is_legal_delivery": True,
                "is_super_over": False,
                "is_powerplay": True,
                "cumulative_runs": 1,
                "cumulative_wickets": 0,
            },
        ])

        result = loader.load_fact_deliveries(
            df,
            {"m1": 1, "m2": 2},
            {"2024-01-01": 10, "2024-01-02": 11},
            {"Venue A|": 20, "Venue B|": 21},
            {"Team A": 30, "Team B": 31},
            {"pid-a": 40, "pid-b": 41, "pid-c": 42},
            {"Player A": "pid-a", "Player B": "pid-b", "Player C": "pid-c"},
        )

        assert result.rows_loaded == 1
        assert result.successful_match_ids == {"m1"}
        assert result.failed_match_ids == {"m2"}
        assert mock_execute_values.call_count == 1

    @patch("etl.load.psycopg2.pool.ThreadedConnectionPool")
    @patch("etl.load.psycopg2.extras.execute_values")
    def test_upsert_file_registry_entries(self, mock_execute_values, mock_pool_cls):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool_cls.return_value.getconn.return_value = mock_conn
        mock_pool_cls.return_value.closed = False

        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        loader.upsert_file_registry_entries(
            [FileRegistryEntry(match_id="123", file_name="123.json", file_checksum="abc")],
            run_id=7,
        )

        values = mock_execute_values.call_args[0][2]
        assert values == [("123", "123.json", "abc", None, 7)]

class TestDatabaseLoaderETLLog:

    @patch("etl.load.psycopg2.pool.ThreadedConnectionPool")
    def test_start_etl_run(self, mock_pool_cls):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (42,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool_cls.return_value.getconn.return_value = mock_conn
        mock_pool_cls.return_value.closed = False

        loader = DatabaseLoader(database_url="postgresql://test:test@localhost/test")
        run_id = loader.start_etl_run("1.0.0")
        assert run_id == 42
