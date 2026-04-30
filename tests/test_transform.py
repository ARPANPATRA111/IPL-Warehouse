import json
from pathlib import Path

import pytest

from etl.transform import (
    extract_match_info,
    extract_players_from_match,
    parse_single_match,
    transform_deliveries_for_innings,
    transform_match,
)

class TestParseSingleMatch:

    def test_valid_json(self, sample_match_file):
        result = parse_single_match(sample_match_file)
        assert result is not None
        assert "meta" in result
        assert "info" in result
        assert "innings" in result

    def test_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json content")
        result = parse_single_match(bad_file)
        assert result is None

    def test_missing_file(self, tmp_path):
        result = parse_single_match(tmp_path / "nonexistent.json")
        assert result is None

class TestExtractPlayers:

    def test_extracts_registry(self, sample_match_json):
        result = extract_players_from_match(sample_match_json)
        assert "uuid-a-001" in result
        assert result["uuid-a-001"] == "Player A"

    def test_empty_registry(self):
        data = {"info": {}}
        result = extract_players_from_match(data)
        assert result == {}

class TestExtractMatchInfo:

    def test_extracts_all_fields(self, sample_match_json):
        result = extract_match_info(sample_match_json, "9999999")
        assert result["match_id"] == "9999999"
        assert result["season"] == "2023"
        assert result["venue"] == "Wankhede Stadium"
        assert result["city"] == "Mumbai"
        assert result["match_type"] == "T20"
        assert result["balls_per_over"] == 6
        assert result["match_number"] == 1

class TestTransformDeliveries:

    def test_basic_transformation(self, sample_match_json):
        from datetime import date

        innings_data = sample_match_json["innings"][0]
        registry = sample_match_json["info"]["registry"]["people"]

        deliveries = transform_deliveries_for_innings(
            innings_data=innings_data,
            match_id="9999999",
            innings_number=1,
            match_date=date(2023, 4, 1),
            venue="Wankhede Stadium",
            city="Mumbai",
            batting_team="Mumbai Indians",
            bowling_team="Chennai Super Kings",
            is_super_over=False,
            registry=registry,
        )

        assert len(deliveries) == 7

        assert deliveries[0]["runs_batsman"] == 4
        assert deliveries[0]["is_boundary_four"] is True

        assert deliveries[1]["is_wide"] is True
        assert deliveries[1]["is_legal_delivery"] is False

        assert deliveries[2]["runs_batsman"] == 6
        assert deliveries[2]["is_boundary_six"] is True

        assert deliveries[3]["is_wicket"] is True
        assert deliveries[3]["dismissal_type"] == "bowled"
        assert deliveries[3]["dismissed_player"] == "Player B"

    def test_cumulative_tracking(self, sample_match_json):
        from datetime import date

        innings_data = sample_match_json["innings"][0]
        registry = sample_match_json["info"]["registry"]["people"]

        deliveries = transform_deliveries_for_innings(
            innings_data=innings_data,
            match_id="9999999",
            innings_number=1,
            match_date=date(2023, 4, 1),
            venue="Wankhede Stadium",
            city="Mumbai",
            batting_team="Mumbai Indians",
            bowling_team="Chennai Super Kings",
            is_super_over=False,
            registry=registry,
        )


        assert deliveries[0]["cumulative_runs"] == 4

        assert deliveries[1]["cumulative_runs"] == 5

        assert deliveries[2]["cumulative_runs"] == 11

        assert deliveries[3]["cumulative_wickets"] == 1

    def test_legal_ball_counter(self, sample_match_json):
        from datetime import date

        innings_data = sample_match_json["innings"][0]
        registry = sample_match_json["info"]["registry"]["people"]

        deliveries = transform_deliveries_for_innings(
            innings_data=innings_data,
            match_id="9999999",
            innings_number=1,
            match_date=date(2023, 4, 1),
            venue="Wankhede Stadium",
            city="Mumbai",
            batting_team="Mumbai Indians",
            bowling_team="Chennai Super Kings",
            is_super_over=False,
            registry=registry,
        )


        assert deliveries[0]["legal_ball_number"] == 1

        assert deliveries[1]["legal_ball_number"] == 1

        assert deliveries[2]["legal_ball_number"] == 2

class TestTransformMatch:

    def test_full_transformation(self, sample_match_file):
        result = transform_match(sample_match_file)
        assert result is not None
        assert "match" in result
        assert "match_summary" in result
        assert "innings" in result
        assert "deliveries" in result
        assert "players" in result
        assert "team_names" in result
        assert "venue" in result
        assert "date_info" in result

    def test_match_summary_fields(self, sample_match_file):
        result = transform_match(sample_match_file)
        summary = result["match_summary"]
        assert summary["match_id"] == "9999999"
        assert summary["match_winner"] == "Mumbai Indians"
        assert summary["win_type"] == "runs"
        assert summary["win_margin"] == 25
        assert summary["toss_decision"] == "field"
        assert summary["season"] == "2023"

    def test_player_extraction(self, sample_match_file):
        result = transform_match(sample_match_file)
        assert len(result["players"]) == 4
        assert "uuid-a-001" in result["players"]

    def test_team_normalization(self, sample_match_file):
        result = transform_match(sample_match_file)
        assert "Mumbai Indians" in result["team_names"]
        assert "Chennai Super Kings" in result["team_names"]
