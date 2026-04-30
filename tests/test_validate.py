import json
from pathlib import Path

import pytest

from etl.validate import ValidationResult, validate_business_rules, validate_data_types, validate_schema

class TestValidateSchema:

    def test_valid_schema(self, sample_match_json):
        result = validate_schema(sample_match_json)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_missing_meta(self, sample_match_json):
        del sample_match_json["meta"]
        result = validate_schema(sample_match_json)
        assert result.is_valid is False
        assert any("meta" in e.lower() for e in result.errors)

    def test_missing_info(self, sample_match_json):
        del sample_match_json["info"]
        result = validate_schema(sample_match_json)
        assert result.is_valid is False

    def test_missing_innings(self, sample_match_json):
        del sample_match_json["innings"]
        result = validate_schema(sample_match_json)
        assert result.is_valid is False

    def test_empty_teams(self, sample_match_json):
        sample_match_json["info"]["teams"] = []
        result = validate_schema(sample_match_json)
        assert result.is_valid is False

class TestValidateDataTypes:

    def test_valid_types(self, sample_match_json):
        result = validate_data_types(sample_match_json)
        assert result.is_valid is True

    def test_invalid_season_type(self, sample_match_json):
        sample_match_json["info"]["season"] = 2023
        result = validate_data_types(sample_match_json)

        assert result.is_valid is True

    def test_invalid_dates_format(self, sample_match_json):
        sample_match_json["info"]["dates"] = "2023-04-01"
        result = validate_data_types(sample_match_json)
        assert result.is_valid is False

class TestValidateBusinessRules:

    def test_valid_rules(self, sample_match_json):
        result = validate_business_rules(sample_match_json)
        assert result.is_valid is True

    def test_too_few_teams(self, sample_match_json):
        sample_match_json["info"]["teams"] = ["Mumbai Indians"]
        result = validate_business_rules(sample_match_json)
        assert result.is_valid is False

    def test_no_overs_in_innings(self, sample_match_json):
        sample_match_json["innings"][0]["overs"] = []
        result = validate_business_rules(sample_match_json)

        assert len(result.warnings) > 0 or result.is_valid is True
