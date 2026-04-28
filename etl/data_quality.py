from dataclasses import dataclass, field
from typing import Optional

import psycopg2
from psycopg2.extensions import connection as PgConnection

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger("data_quality")

@dataclass
class DQCheckResult:

    check_name: str
    status: str
    records_checked: int
    records_failed: int
    failure_percentage: float
    details: Optional[str] = None

@dataclass
class DQReport:

    checks: list[DQCheckResult] = field(default_factory=list)
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    failures: int = 0
    overall_status: str = "pass"

    def add_check(self, result: DQCheckResult) -> None:
        self.checks.append(result)
        self.total_checks += 1
        if result.status == "pass":
            self.passed += 1
        elif result.status == "warn":
            self.warnings += 1
        elif result.status == "fail":
            self.failures += 1
            self.overall_status = "fail"

def get_connection() -> PgConnection:
    settings = get_settings()
    return psycopg2.connect(settings.database_url)

def log_dq_result(conn: PgConnection, run_id: int, result: DQCheckResult) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data_quality_log
                    (run_id, check_name, status, records_checked,
                     records_failed, failure_percentage, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    result.check_name,
                    result.status,
                    result.records_checked,
                    result.records_failed,
                    result.failure_percentage,
                    result.details,
                ),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to log DQ result for '{result.check_name}': {e}")

def check_null_match_keys(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fact_deliveries WHERE match_key IS NULL")
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM fact_deliveries")
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "fail"
    return DQCheckResult(
        check_name="null_match_keys_in_deliveries",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} deliveries have NULL match_key",
    )

def check_orphan_deliveries(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fact_deliveries fd
            LEFT JOIN dim_match dm ON fd.match_key = dm.match_key
            WHERE dm.match_key IS NULL
        """)
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM fact_deliveries")
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "fail"
    return DQCheckResult(
        check_name="orphan_deliveries",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} deliveries without matching dim_match record",
    )

def check_runs_range(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fact_deliveries
            WHERE runs_batsman < 0 OR runs_batsman > 7
        """)
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM fact_deliveries")
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "warn" if pct < 0.1 else "fail"
    return DQCheckResult(
        check_name="runs_range_check",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} deliveries with runs_batsman outside [0,7]",
    )

def check_overs_per_innings(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT match_key, innings_number, MAX(legal_ball_number) as max_ball
            FROM fact_deliveries
            WHERE is_super_over = FALSE
            GROUP BY match_key, innings_number
            HAVING MAX(legal_ball_number) > 120
        """)
        violations = cur.fetchall()
        failed = len(violations)
        cur.execute("""
            SELECT COUNT(DISTINCT (match_key, innings_number))
            FROM fact_deliveries WHERE is_super_over = FALSE
        """)
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "warn" if pct < 1 else "fail"
    return DQCheckResult(
        check_name="overs_per_innings_check",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} innings exceed 120 legal balls",
    )

def check_wickets_per_innings(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT match_key, innings_number, MAX(cumulative_wickets) as max_wkts
            FROM fact_deliveries
            WHERE is_super_over = FALSE
            GROUP BY match_key, innings_number
            HAVING MAX(cumulative_wickets) > 10
        """)
        violations = cur.fetchall()
        failed = len(violations)
        cur.execute("""
            SELECT COUNT(DISTINCT (match_key, innings_number))
            FROM fact_deliveries WHERE is_super_over = FALSE
        """)
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "fail"
    return DQCheckResult(
        check_name="wickets_per_innings_check",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} innings exceed 10 wickets",
    )

def check_match_summary_completeness(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM dim_match dm
            LEFT JOIN fact_match_summary fms ON dm.match_key = fms.match_key
            WHERE fms.match_key IS NULL
        """)
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM dim_match")
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "warn" if pct < 5 else "fail"
    return DQCheckResult(
        check_name="match_summary_completeness",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} matches without summary record",
    )

def check_duplicate_deliveries(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT match_key, innings_number, over_number, ball_number,
                       COUNT(*) as cnt
                FROM fact_deliveries
                GROUP BY match_key, innings_number, over_number, ball_number
                HAVING COUNT(*) > 1
            ) dups
        """)
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM fact_deliveries")
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "warn"
    return DQCheckResult(
        check_name="duplicate_deliveries",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} duplicate delivery groups",
    )

def check_team_consistency(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT batting_team_key) FROM fact_deliveries
            WHERE batting_team_key NOT IN (SELECT team_key FROM dim_team)
        """)
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT batting_team_key) FROM fact_deliveries")
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "fail"
    return DQCheckResult(
        check_name="team_referential_integrity",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} team keys not in dim_team",
    )

def check_player_consistency(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fact_deliveries
            WHERE batsman_key NOT IN (SELECT player_key FROM dim_player)
        """)
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM fact_deliveries")
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "warn" if pct < 1 else "fail"
    return DQCheckResult(
        check_name="player_referential_integrity",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} batsman_key values not in dim_player",
    )

def check_score_consistency(conn: PgConnection) -> DQCheckResult:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT fms.match_key,
                    fms.team1_score as summary_score,
                    COALESCE(agg.total, 0) as delivery_total
                FROM fact_match_summary fms
                LEFT JOIN (
                    SELECT match_key, SUM(runs_total) as total
                    FROM fact_deliveries
                    WHERE innings_number = 1 AND is_super_over = FALSE
                    GROUP BY match_key
                ) agg ON fms.match_key = agg.match_key
                WHERE fms.team1_score IS NOT NULL
                    AND ABS(fms.team1_score - COALESCE(agg.total, 0)) > 0
            ) mismatches
        """)
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM fact_match_summary WHERE team1_score IS NOT NULL")
        total = cur.fetchone()[0]

    pct = (failed / total * 100) if total > 0 else 0
    status = "pass" if failed == 0 else "warn" if pct < 5 else "fail"
    return DQCheckResult(
        check_name="score_consistency",
        status=status,
        records_checked=total,
        records_failed=failed,
        failure_percentage=pct,
        details=f"{failed} matches with score mismatch between summary and deliveries",
    )

def run_data_quality_checks(run_id: Optional[int] = None) -> DQReport:
    logger.info("Starting data quality checks")
    report = DQReport()

    conn = get_connection()
    try:
        checks = [
            check_null_match_keys,
            check_orphan_deliveries,
            check_runs_range,
            check_overs_per_innings,
            check_wickets_per_innings,
            check_match_summary_completeness,
            check_duplicate_deliveries,
            check_team_consistency,
            check_player_consistency,
            check_score_consistency,
        ]

        for check_fn in checks:
            try:
                result = check_fn(conn)
                report.add_check(result)
                logger.info(
                    f"DQ Check '{result.check_name}': {result.status} "
                    f"({result.records_failed}/{result.records_checked} = {result.failure_percentage:.2f}%)"
                )
                if run_id:
                    log_dq_result(conn, run_id, result)
            except Exception as e:
                logger.error(f"DQ check '{check_fn.__name__}' failed: {e}")
                error_result = DQCheckResult(
                    check_name=check_fn.__name__,
                    status="fail",
                    records_checked=0,
                    records_failed=0,
                    failure_percentage=0,
                    details=f"Check execution error: {str(e)}",
                )
                report.add_check(error_result)

    finally:
        conn.close()

    logger.info(
        f"Data quality complete: {report.passed} passed, "
        f"{report.warnings} warnings, {report.failures} failures"
    )
    return report
