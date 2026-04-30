from unittest.mock import MagicMock, patch

import pytest

from etl.data_quality import (
    DQCheckResult,
    DQReport,
    check_null_match_keys,
    check_runs_range,
)

class TestDQCheckResult:

    def test_creation(self):
        result = DQCheckResult(
            check_name="test_check",
            status="pass",
            records_checked=100,
            records_failed=0,
            failure_percentage=0.0,
        )
        assert result.check_name == "test_check"
        assert result.status == "pass"
        assert result.failure_percentage == 0.0

class TestDQReport:

    def test_add_passing_check(self):
        report = DQReport()
        result = DQCheckResult("check1", "pass", 100, 0, 0.0)
        report.add_check(result)
        assert report.total_checks == 1
        assert report.passed == 1
        assert report.overall_status == "pass"

    def test_add_failing_check(self):
        report = DQReport()
        result = DQCheckResult("check1", "fail", 100, 50, 50.0)
        report.add_check(result)
        assert report.total_checks == 1
        assert report.failures == 1
        assert report.overall_status == "fail"

    def test_mixed_results(self):
        report = DQReport()
        report.add_check(DQCheckResult("c1", "pass", 100, 0, 0.0))
        report.add_check(DQCheckResult("c2", "warn", 100, 5, 5.0))
        report.add_check(DQCheckResult("c3", "fail", 100, 50, 50.0))
        assert report.total_checks == 3
        assert report.passed == 1
        assert report.warnings == 1
        assert report.failures == 1
        assert report.overall_status == "fail"

class TestCheckFunctions:

    def test_null_match_keys_pass(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(0,), (1000,)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = check_null_match_keys(mock_conn)
        assert result.status == "pass"
        assert result.records_failed == 0

    def test_null_match_keys_fail(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(5,), (1000,)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = check_null_match_keys(mock_conn)
        assert result.status == "fail"
        assert result.records_failed == 5

    def test_runs_range_pass(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(0,), (5000,)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = check_runs_range(mock_conn)
        assert result.status == "pass"
