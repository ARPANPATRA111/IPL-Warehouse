from datetime import date

import pytest

from etl.transform_helpers import (
    compute_overs_decimal,
    extract_win_info,
    generate_date_attributes,
    get_franchise_group,
    get_team_short_name,
    normalize_team_name,
    parse_match_date,
    parse_season,
)

class TestNormalizeTeamName:

    def test_known_mapping(self):
        assert normalize_team_name("Delhi Daredevils") == "Delhi Capitals"
        assert normalize_team_name("Deccan Chargers") == "Deccan Chargers"
        assert normalize_team_name("Royal Challengers Bangalore") == "Royal Challengers Bengaluru"

    def test_current_name_unchanged(self):
        assert normalize_team_name("Mumbai Indians") == "Mumbai Indians"
        assert normalize_team_name("Chennai Super Kings") == "Chennai Super Kings"

    def test_unknown_team(self):
        assert normalize_team_name("Unknown XI") == "Unknown XI"

    def test_case_sensitivity(self):

        assert normalize_team_name("delhi daredevils") == "delhi daredevils"

class TestParseSeason:

    def test_simple_year(self):
        assert parse_season("2023") == "2023"

    def test_integer_season(self):
        assert parse_season(2023) == "2023"

    def test_slash_season(self):
        assert parse_season("2023/24") == "2023/24"

    def test_empty_season(self):
        assert parse_season("") == ""
        assert parse_season(None) == ""

class TestParseMatchDate:

    def test_single_date(self):
        result = parse_match_date(["2023-04-01"])
        assert result == date(2023, 4, 1)

    def test_multi_day_match(self):
        result = parse_match_date(["2023-04-01", "2023-04-02"])
        assert result == date(2023, 4, 1)

    def test_empty_dates(self):
        result = parse_match_date([])
        assert result is not None

class TestComputeOversDecimal:

    def test_full_overs(self):
        assert compute_overs_decimal(6) == 1.0

    def test_partial_over(self):
        assert compute_overs_decimal(7) == 1.1

    def test_20_overs(self):
        assert compute_overs_decimal(120) == 20.0

    def test_zero_balls(self):
        assert compute_overs_decimal(0) == 0.0

class TestExtractWinInfo:

    def test_win_by_runs(self):
        outcome = {"winner": "Mumbai Indians", "by": {"runs": 25}}
        winner, win_type, margin, is_dls, result = extract_win_info(outcome)
        assert winner == "Mumbai Indians"
        assert win_type == "runs"
        assert margin == 25
        assert is_dls is False
        assert result == "normal"

    def test_win_by_wickets(self):
        outcome = {"winner": "CSK", "by": {"wickets": 7}}
        winner, win_type, margin, is_dls, result = extract_win_info(outcome)
        assert winner == "CSK"
        assert win_type == "wickets"
        assert margin == 7

    def test_no_result(self):
        outcome = {"result": "no result"}
        winner, win_type, margin, is_dls, result = extract_win_info(outcome)
        assert winner is None
        assert result == "no result"

    def test_tie(self):
        outcome = {"result": "tie"}
        winner, win_type, margin, is_dls, result = extract_win_info(outcome)
        assert winner is None
        assert result == "tie"

    def test_dls_method(self):
        outcome = {"winner": "MI", "by": {"runs": 10}, "method": "D/L"}
        winner, win_type, margin, is_dls, result = extract_win_info(outcome)
        assert is_dls is True

class TestGenerateDateAttributes:

    def test_basic_attributes(self):
        result = generate_date_attributes(date(2023, 4, 1), "2023")
        assert result["full_date"] == date(2023, 4, 1)
        assert result["year"] == 2023
        assert result["month_number"] == 4
        assert result["month_name"] == "April"
        assert result["day_of_month"] == 1
        assert result["season"] == "2023"
        assert result["quarter"] == 2

    def test_weekend_detection(self):

        result = generate_date_attributes(date(2023, 4, 1), "2023")
        assert result["is_weekend"] is True


        result = generate_date_attributes(date(2023, 4, 3), "2023")
        assert result["is_weekend"] is False

class TestTeamShortNames:

    def test_known_team(self):
        assert get_team_short_name("Mumbai Indians") == "MI"
        assert get_team_short_name("Chennai Super Kings") == "CSK"
        assert get_team_short_name("Deccan Chargers") == "DCH"

    def test_unknown_team(self):
        result = get_team_short_name("Unknown Team XI")
        assert result is not None
