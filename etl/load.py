from dataclasses import dataclass
from typing import Any, Iterator, Optional

import pandas as pd
import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extensions import connection as PgConnection

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger("load")

@dataclass(frozen=True)
class FileRegistryEntry:

    match_id: str
    file_name: str
    file_checksum: str
    source_checksum: Optional[str] = None

@dataclass(frozen=True)
class FactLoadReport:

    rows_loaded: int
    successful_match_ids: set[str]
    failed_match_ids: set[str]

class DatabaseLoader:

    def __init__(self, database_url: Optional[str] = None, batch_size: int = 1000):
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self.batch_size = batch_size or settings.batch_size
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    def get_pool(self) -> psycopg2.pool.ThreadedConnectionPool:
        if self._pool is None or self._pool.closed:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=self.database_url,
            )
        return self._pool

    def get_connection(self) -> PgConnection:
        pool = self.get_pool()
        conn = pool.getconn()
        if getattr(conn, "closed", 0):
            pool.putconn(conn, close=True)
            conn = pool.getconn()
        return conn

    def return_connection(self, conn: PgConnection) -> None:
        if self._pool is None or self._pool.closed:
            return
        self._pool.putconn(conn, close=bool(getattr(conn, "closed", 0)))

    def close(self) -> None:
        if self._pool and not self._pool.closed:
            self._pool.closeall()

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if value is None:
            return None

        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass

        if hasattr(value, "item") and callable(getattr(value, "item")):
            try:
                return value.item()
            except (AttributeError, TypeError, ValueError):
                pass

        return value

    def _iter_records(self, df: pd.DataFrame) -> Iterator[dict[str, Any]]:
        for row in df.to_dict("records"):
            yield {key: self._normalize_value(value) for key, value in row.items()}

    def _execute_values(
        self,
        cur: Any,
        sql: str,
        values: list[tuple[Any, ...]],
        *,
        template: Optional[str] = None,
        fetch: bool = False,
    ) -> list[Any]:
        if not values:
            return []

        result = psycopg2.extras.execute_values(
            cur,
            sql,
            values,
            template=template,
            page_size=self.batch_size,
            fetch=fetch,
        )
        return result or []

    @staticmethod
    def _safe_rollback(conn: PgConnection) -> None:
        if getattr(conn, "closed", 0):
            return
        try:
            conn.rollback()
        except Exception:
            pass

    def execute_schema(self, sql_file_path: str) -> None:
        conn = self.get_connection()
        try:
            with open(sql_file_path, "r", encoding="utf-8") as f:
                sql = f.read()
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            logger.info(f"Executed SQL file: {sql_file_path}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to execute SQL file {sql_file_path}: {e}")
            raise
        finally:
            self.return_connection(conn)

    def schema_exists(self) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'dim_match'
                    )
                    """
                )
                return bool(cur.fetchone()[0])
        finally:
            self.return_connection(conn)

    def ensure_file_registry_table(self) -> None:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                self._create_file_registry_table(cur)
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to ensure file registry table: {e}")
            raise
        finally:
            self.return_connection(conn)

    def reset_file_registry_table(self) -> None:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS etl_file_registry")
                self._create_file_registry_table(cur)
            conn.commit()
            logger.info("Reset file registry table")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to reset file registry table: {e}")
            raise
        finally:
            self.return_connection(conn)

    @staticmethod
    def _create_file_registry_table(cur: psycopg2.extensions.cursor) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS etl_file_registry (
                match_id VARCHAR(50) PRIMARY KEY,
                file_name VARCHAR(255) NOT NULL,
                file_checksum VARCHAR(64) NOT NULL,
                source_checksum VARCHAR(64),
                run_id INT REFERENCES etl_run_log(run_id),
                processed_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )

    def get_processed_file_registry(self) -> dict[str, str]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT match_id, file_checksum FROM etl_file_registry")
                return {match_id: checksum for match_id, checksum in cur.fetchall()}
        except Exception as e:
            logger.warning(f"Could not read processed file registry: {e}")
            return {}
        finally:
            self.return_connection(conn)

    def upsert_file_registry_entries(
        self,
        entries: list[FileRegistryEntry],
        run_id: Optional[int] = None,
    ) -> None:
        if not entries:
            return

        values = [
            (
                entry.match_id,
                entry.file_name,
                entry.file_checksum,
                entry.source_checksum,
                run_id,
            )
            for entry in entries
        ]

        for attempt in range(1, 3):
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    self._execute_values(
                        cur,
                        """
                        INSERT INTO etl_file_registry (
                            match_id, file_name, file_checksum, source_checksum, run_id, processed_at
                        )
                        VALUES %s
                        ON CONFLICT (match_id)
                        DO UPDATE SET
                            file_name = EXCLUDED.file_name,
                            file_checksum = EXCLUDED.file_checksum,
                            source_checksum = EXCLUDED.source_checksum,
                            run_id = EXCLUDED.run_id,
                            processed_at = NOW()
                        """,
                        values,
                        template="(%s, %s, %s, %s, %s, NOW())",
                    )
                conn.commit()
                logger.info(f"Updated file registry for {len(entries)} files")
                return
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                self._safe_rollback(conn)
                logger.warning(
                    f"Retrying file registry update after connection error on attempt {attempt}: {e}"
                )
                self.close()
                if attempt == 2:
                    raise
            except Exception as e:
                self._safe_rollback(conn)
                logger.error(f"Failed to update file registry: {e}")
                raise
            finally:
                self.return_connection(conn)

    @staticmethod
    def _resolve_venue_key(
        row: dict[str, Any],
        venue_key_map: dict[str, int],
    ) -> Optional[int]:
        venue_name = row.get("venue") or row.get("venue_name")
        if not venue_name:
            return None

        city = row.get("city")
        normalized_city = "" if city in (None, "", "Unknown") else city
        exact_key = f"{venue_name}|{normalized_city}"
        if exact_key in venue_key_map:
            return venue_key_map[exact_key]
        return venue_key_map.get(f"{venue_name}|")

    def load_dim_dates(self, df: pd.DataFrame) -> dict[str, int]:
        if df.empty:
            return {}

        conn = self.get_connection()
        mapping: dict[str, int] = {}
        try:
            with conn.cursor() as cur:
                values = [
                    (
                        row["full_date"],
                        row["day_of_week"],
                        row["day_name"],
                        row["day_of_month"],
                        row["week_of_year"],
                        row["month_number"],
                        row["month_name"],
                        row["quarter"],
                        row["year"],
                        row["season"],
                        row["is_weekend"],
                        row.get("is_playoff", False),
                        row.get("phase_of_tournament", "League"),
                    )
                    for row in self._iter_records(df)
                ]
                returned_rows = self._execute_values(
                    cur,
                    """
                    INSERT INTO dim_date (full_date, day_of_week, day_name, day_of_month,
                        week_of_year, month_number, month_name, quarter, year, season,
                        is_weekend, is_playoff, phase_of_tournament)
                    VALUES %s
                    ON CONFLICT (full_date) DO UPDATE SET season = EXCLUDED.season
                    RETURNING full_date, date_key
                    """,
                    values,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    fetch=True,
                )
                mapping = {str(full_date): date_key for full_date, date_key in returned_rows}

            conn.commit()
            logger.info(f"Loaded {len(mapping)} date records")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to load dates: {e}")
            raise
        finally:
            self.return_connection(conn)
        return mapping

    def load_dim_venues(self, df: pd.DataFrame) -> dict[str, int]:
        if df.empty:
            return {}

        conn = self.get_connection()
        mapping: dict[str, int] = {}
        try:
            with conn.cursor() as cur:
                values = [
                    (row["venue_name"], row.get("city"))
                    for row in self._iter_records(df)
                ]
                returned_rows = self._execute_values(
                    cur,
                    """
                    INSERT INTO dim_venue (venue_name, city)
                    VALUES %s
                    ON CONFLICT (venue_name, COALESCE(city, ''))
                    DO UPDATE SET venue_name = EXCLUDED.venue_name
                    RETURNING venue_name, city, venue_key
                    """,
                    values,
                    template="(%s, %s)",
                    fetch=True,
                )
                mapping = {
                    f"{venue_name}|{city or ''}": venue_key
                    for venue_name, city, venue_key in returned_rows
                }

            conn.commit()
            logger.info(f"Loaded {len(mapping)} venue records")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to load venues: {e}")
            raise
        finally:
            self.return_connection(conn)
        return mapping

    def load_dim_teams(self, df: pd.DataFrame) -> dict[str, int]:
        if df.empty:
            return {}

        conn = self.get_connection()
        mapping: dict[str, int] = {}
        try:
            with conn.cursor() as cur:
                values = [
                    (
                        row["team_name"],
                        row.get("team_short_name"),
                        row.get("is_active", True),
                        row.get("franchise_group"),
                    )
                    for row in self._iter_records(df)
                ]
                returned_rows = self._execute_values(
                    cur,
                    """
                    INSERT INTO dim_team (team_name, team_short_name, is_active, franchise_group)
                    VALUES %s
                    ON CONFLICT (team_name)
                    DO UPDATE SET
                        team_short_name = COALESCE(EXCLUDED.team_short_name, dim_team.team_short_name),
                        is_active = EXCLUDED.is_active,
                        franchise_group = COALESCE(EXCLUDED.franchise_group, dim_team.franchise_group),
                        updated_at = NOW()
                    RETURNING team_name, team_key
                    """,
                    values,
                    template="(%s, %s, %s, %s)",
                    fetch=True,
                )
                mapping = {team_name: team_key for team_name, team_key in returned_rows}

            conn.commit()
            logger.info(f"Loaded {len(mapping)} team records")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to load teams: {e}")
            raise
        finally:
            self.return_connection(conn)
        return mapping

    def load_dim_players(self, df: pd.DataFrame) -> dict[str, int]:
        if df.empty:
            return {}

        conn = self.get_connection()
        mapping: dict[str, int] = {}
        try:
            with conn.cursor() as cur:
                values = [
                    (
                        row["player_id"],
                        row["player_name"],
                        row.get("first_match_date"),
                        row.get("last_match_date"),
                        row.get("total_matches", 1),
                    )
                    for row in self._iter_records(df)
                ]
                returned_rows = self._execute_values(
                    cur,
                    """
                    INSERT INTO dim_player (player_id, player_name, first_match_date,
                        last_match_date, total_matches)
                    VALUES %s
                    ON CONFLICT (player_id)
                    DO UPDATE SET
                        player_name = EXCLUDED.player_name,
                        first_match_date = LEAST(dim_player.first_match_date, EXCLUDED.first_match_date),
                        last_match_date = GREATEST(dim_player.last_match_date, EXCLUDED.last_match_date),
                        total_matches = dim_player.total_matches + EXCLUDED.total_matches,
                        updated_at = NOW()
                    RETURNING player_id, player_key
                    """,
                    values,
                    template="(%s, %s, %s, %s, %s)",
                    fetch=True,
                )
                mapping = {player_id: player_key for player_id, player_key in returned_rows}

            conn.commit()
            logger.info(f"Loaded {len(mapping)} player records")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to load players: {e}")
            raise
        finally:
            self.return_connection(conn)
        return mapping

    def load_dim_matches(self, df: pd.DataFrame) -> dict[str, int]:
        if df.empty:
            return {}

        conn = self.get_connection()
        mapping: dict[str, int] = {}
        try:
            with conn.cursor() as cur:
                values = [
                    (
                        row["match_id"],
                        row["season"],
                        row.get("match_number"),
                        row.get("match_type", "T20"),
                        row.get("gender", "male"),
                        row.get("balls_per_over", 6),
                        row.get("overs_per_side", 20),
                        row.get("data_version", "1.0.0"),
                    )
                    for row in self._iter_records(df)
                ]
                returned_rows = self._execute_values(
                    cur,
                    """
                    INSERT INTO dim_match (match_id, season, match_number, match_type,
                        gender, balls_per_over, overs_per_side, data_version)
                    VALUES %s
                    ON CONFLICT (match_id)
                    DO UPDATE SET season = EXCLUDED.season
                    RETURNING match_id, match_key
                    """,
                    values,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s)",
                    fetch=True,
                )
                mapping = {match_id: match_key for match_id, match_key in returned_rows}

            conn.commit()
            logger.info(f"Loaded {len(mapping)} match records")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to load matches: {e}")
            raise
        finally:
            self.return_connection(conn)
        return mapping

    def load_dim_innings(
        self,
        df: pd.DataFrame,
        match_key_map: dict[str, int],
        team_key_map: dict[str, int],
    ) -> dict[str, int]:
        if df.empty:
            return {}

        conn = self.get_connection()
        mapping: dict[str, int] = {}
        try:
            with conn.cursor() as cur:
                reverse_match_key_map = {value: key for key, value in match_key_map.items()}
                values = []
                for row in self._iter_records(df):
                    match_key = match_key_map.get(row["match_id"])
                    bat_key = team_key_map.get(row["batting_team"])
                    bowl_key = team_key_map.get(row["bowling_team"])

                    if not all([match_key, bat_key, bowl_key]):
                        logger.warning(
                            f"Skipping innings: missing key for match={row['match_id']}, "
                            f"bat={row['batting_team']}, bowl={row['bowling_team']}"
                        )
                        continue

                    values.append(
                        (
                            match_key,
                            row["innings_number"],
                            bat_key,
                            bowl_key,
                            row.get("total_runs", 0),
                            row.get("total_wickets", 0),
                            row.get("total_overs"),
                            row.get("total_extras", 0),
                            row.get("is_super_over", False),
                            row.get("target_runs"),
                            row.get("target_overs"),
                            row.get("has_dls", False),
                            row.get("is_forfeited", False),
                        )
                    )

                returned_rows = self._execute_values(
                    cur,
                    """
                    INSERT INTO dim_innings (match_key, innings_number, batting_team_key,
                        bowling_team_key, total_runs, total_wickets, total_overs,
                        total_extras, is_super_over, target_runs, target_overs,
                        has_dls, is_forfeited)
                    VALUES %s
                    ON CONFLICT (match_key, innings_number)
                    DO UPDATE SET total_runs = EXCLUDED.total_runs
                    RETURNING match_key, innings_number, innings_key
                    """,
                    values,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    fetch=True,
                )
                mapping = {
                    f"{reverse_match_key_map[match_key]}|{innings_number}": innings_key
                    for match_key, innings_number, innings_key in returned_rows
                    if match_key in reverse_match_key_map
                }

            conn.commit()
            logger.info(f"Loaded {len(mapping)} innings records")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to load innings: {e}")
            raise
        finally:
            self.return_connection(conn)
        return mapping

    def load_fact_match_summary(
        self,
        df: pd.DataFrame,
        match_key_map: dict[str, int],
        date_key_map: dict[str, int],
        venue_key_map: dict[str, int],
        team_key_map: dict[str, int],
        player_key_map: dict[str, int],
        player_name_to_id: dict[str, str],
        full_refresh: bool = False,
    ) -> FactLoadReport:
        if df.empty:
            return FactLoadReport(0, set(), set())

        conn = self.get_connection()
        rows_loaded = 0
        successful_match_ids: set[str] = set()
        failed_match_ids: set[str] = set()
        try:
            with conn.cursor() as cur:
                if full_refresh:
                    values_list: list[tuple[Any, ...]] = []
                    for row in self._iter_records(df):
                        match_id = row["match_id"]
                        match_key = match_key_map.get(match_id)
                        date_key = date_key_map.get(str(row["match_date"]))
                        venue_key = self._resolve_venue_key(row, venue_key_map)
                        team1_key = team_key_map.get(row["team1"])
                        team2_key = team_key_map.get(row["team2"])
                        toss_winner_key = team_key_map.get(row["toss_winner"])
                        match_winner_key = (
                            team_key_map.get(row["match_winner"])
                            if row.get("match_winner")
                            else None
                        )
                        eliminator_key = (
                            team_key_map.get(row["eliminator_winner"])
                            if row.get("eliminator_winner")
                            else None
                        )

                        pom_key = None
                        pom_name = row.get("player_of_match")
                        if pom_name and pom_name in player_name_to_id:
                            pom_id = player_name_to_id[pom_name]
                            pom_key = player_key_map.get(pom_id)

                        if not all(
                            [
                                match_key,
                                date_key,
                                venue_key,
                                team1_key,
                                team2_key,
                                toss_winner_key,
                            ]
                        ):
                            logger.warning(f"Skipping match summary for {match_id}: missing keys")
                            failed_match_ids.add(match_id)
                            continue

                        values_list.append(
                            (
                                match_key,
                                date_key,
                                venue_key,
                                team1_key,
                                team2_key,
                                toss_winner_key,
                                row["toss_decision"],
                                match_winner_key,
                                row.get("win_type"),
                                row.get("win_margin"),
                                row.get("is_dls", False),
                                row["result"],
                                eliminator_key,
                                pom_key,
                                row.get("team1_score"),
                                row.get("team1_wickets"),
                                row.get("team1_overs"),
                                row.get("team2_score"),
                                row.get("team2_wickets"),
                                row.get("team2_overs"),
                                row.get("total_fours", 0),
                                row.get("total_sixes", 0),
                                row.get("total_extras", 0),
                                row["season"],
                                row.get("match_number"),
                            )
                        )
                        successful_match_ids.add(match_id)

                    if values_list:
                        self._execute_values(
                            cur,
                            """
                            INSERT INTO fact_match_summary (match_key, date_key, venue_key,
                                team1_key, team2_key, toss_winner_key, toss_decision,
                                match_winner_key, win_type, win_margin, is_dls, result,
                                eliminator_winner_key, player_of_match_key,
                                team1_score, team1_wickets, team1_overs,
                                team2_score, team2_wickets, team2_overs,
                                total_fours, total_sixes, total_extras, season, match_number)
                            VALUES %s
                            ON CONFLICT (match_key)
                            DO UPDATE SET
                                team1_score = EXCLUDED.team1_score,
                                team2_score = EXCLUDED.team2_score,
                                total_fours = EXCLUDED.total_fours,
                                total_sixes = EXCLUDED.total_sixes
                            """,
                            values_list,
                            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        )
                        conn.commit()
                        rows_loaded = len(values_list)

                    logger.info(f"Loaded {rows_loaded} match summary records")
                    return FactLoadReport(rows_loaded, successful_match_ids, failed_match_ids)

                for row in self._iter_records(df):
                    match_id = row["match_id"]
                    try:
                        match_key = match_key_map.get(match_id)
                        date_key = date_key_map.get(str(row["match_date"]))
                        venue_key = self._resolve_venue_key(row, venue_key_map)
                        team1_key = team_key_map.get(row["team1"])
                        team2_key = team_key_map.get(row["team2"])
                        toss_winner_key = team_key_map.get(row["toss_winner"])
                        match_winner_key = team_key_map.get(row["match_winner"]) if row.get("match_winner") else None
                        eliminator_key = team_key_map.get(row["eliminator_winner"]) if row.get("eliminator_winner") else None

                        pom_key = None
                        pom_name = row.get("player_of_match")
                        if pom_name and pom_name in player_name_to_id:
                            pom_id = player_name_to_id[pom_name]
                            pom_key = player_key_map.get(pom_id)

                        if not all([match_key, date_key, venue_key, team1_key, team2_key, toss_winner_key]):
                            logger.warning(f"Skipping match summary for {match_id}: missing keys")
                            failed_match_ids.add(match_id)
                            continue

                        cur.execute(
                            """
                            INSERT INTO fact_match_summary (match_key, date_key, venue_key,
                                team1_key, team2_key, toss_winner_key, toss_decision,
                                match_winner_key, win_type, win_margin, is_dls, result,
                                eliminator_winner_key, player_of_match_key,
                                team1_score, team1_wickets, team1_overs,
                                team2_score, team2_wickets, team2_overs,
                                total_fours, total_sixes, total_extras, season, match_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (match_key)
                            DO UPDATE SET
                                team1_score = EXCLUDED.team1_score,
                                team2_score = EXCLUDED.team2_score,
                                total_fours = EXCLUDED.total_fours,
                                total_sixes = EXCLUDED.total_sixes
                            """,
                            (
                                match_key, date_key, venue_key,
                                team1_key, team2_key, toss_winner_key, row["toss_decision"],
                                match_winner_key, row.get("win_type"), row.get("win_margin"),
                                row.get("is_dls", False), row["result"],
                                eliminator_key, pom_key,
                                row.get("team1_score"), row.get("team1_wickets"), row.get("team1_overs"),
                                row.get("team2_score"), row.get("team2_wickets"), row.get("team2_overs"),
                                row.get("total_fours", 0), row.get("total_sixes", 0),
                                row.get("total_extras", 0), row["season"], row.get("match_number"),
                            ),
                        )
                        conn.commit()
                        rows_loaded += 1
                        successful_match_ids.add(match_id)
                    except Exception as match_error:
                        conn.rollback()
                        failed_match_ids.add(match_id)
                        logger.error(f"Failed to load match summary for {match_id}: {match_error}")

            logger.info(f"Loaded {rows_loaded} match summary records")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to load match summaries: {e}")
            raise
        finally:
            self.return_connection(conn)
        return FactLoadReport(rows_loaded, successful_match_ids, failed_match_ids)

    def load_fact_deliveries(
        self,
        df: pd.DataFrame,
        match_key_map: dict[str, int],
        date_key_map: dict[str, int],
        venue_key_map: dict[str, int],
        team_key_map: dict[str, int],
        player_key_map: dict[str, int],
        player_name_to_id: dict[str, str],
        full_refresh: bool = False,
    ) -> FactLoadReport:
        if df.empty:
            return FactLoadReport(0, set(), set())

        conn = self.get_connection()
        rows_loaded = 0
        successful_match_ids: set[str] = set()
        failed_match_ids: set[str] = set()

        def resolve_player_key(name: Optional[str]) -> Optional[int]:
            if not name:
                return None
            pid = player_name_to_id.get(name)
            if pid:
                return player_key_map.get(pid)
            return None

        try:
            with conn.cursor() as cur:
                if full_refresh:
                    pending_values: list[tuple[Any, ...]] = []
                    skipped_rows_by_match: dict[str, int] = {}
                    insert_sql = """
                        INSERT INTO fact_deliveries (
                            match_key, date_key, venue_key,
                            batting_team_key, bowling_team_key,
                            batsman_key, non_striker_key, bowler_key,
                            innings_number, over_number, ball_number,
                            legal_ball_number,
                            runs_batsman, runs_extras, runs_total,
                            is_boundary_four, is_boundary_six, is_dot_ball,
                            extras_type, extras_runs,
                            is_wicket, dismissal_type,
                            dismissed_player_key, fielder1_key, fielder2_key,
                            is_wide, is_noball, is_legal_delivery,
                            is_super_over, is_powerplay,
                            cumulative_runs, cumulative_wickets
                        ) VALUES %s
                    """
                    insert_template = """(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )"""

                    def flush_pending() -> None:
                        if not pending_values:
                            return
                        self._execute_values(
                            cur,
                            insert_sql,
                            pending_values,
                            template=insert_template,
                        )
                        pending_values.clear()

                    for match_id, match_df in df.groupby("match_id", sort=False):
                        match_key = match_key_map.get(match_id)
                        if not match_key:
                            logger.warning(f"Skipping deliveries for {match_id}: missing match key")
                            failed_match_ids.add(match_id)
                            continue

                        loaded_rows_for_match = 0
                        skipped_rows = 0
                        for row in self._iter_records(match_df):
                            date_key = date_key_map.get(str(row["match_date"]))
                            venue_key = self._resolve_venue_key(row, venue_key_map)
                            bat_team_key = team_key_map.get(row["batting_team"])
                            bowl_team_key = team_key_map.get(row["bowling_team"])
                            batsman_key = resolve_player_key(row["batsman"])
                            non_striker_key = resolve_player_key(row["non_striker"])
                            bowler_key = resolve_player_key(row["bowler"])
                            dismissed_key = resolve_player_key(row.get("dismissed_player"))
                            fielder1_key = resolve_player_key(row.get("fielder1"))
                            fielder2_key = resolve_player_key(row.get("fielder2"))

                            if not all(
                                [
                                    match_key,
                                    date_key,
                                    venue_key,
                                    bat_team_key,
                                    bowl_team_key,
                                    batsman_key,
                                    bowler_key,
                                ]
                            ):
                                skipped_rows += 1
                                continue

                            if non_striker_key is None:
                                non_striker_key = batsman_key

                            pending_values.append(
                                (
                                    match_key,
                                    date_key,
                                    venue_key,
                                    bat_team_key,
                                    bowl_team_key,
                                    batsman_key,
                                    non_striker_key,
                                    bowler_key,
                                    row["innings_number"],
                                    row["over_number"],
                                    row["ball_number"],
                                    row["legal_ball_number"],
                                    row["runs_batsman"],
                                    row["runs_extras"],
                                    row["runs_total"],
                                    row["is_boundary_four"],
                                    row["is_boundary_six"],
                                    row["is_dot_ball"],
                                    row.get("extras_type"),
                                    row.get("extras_runs", 0),
                                    row["is_wicket"],
                                    row.get("dismissal_type"),
                                    dismissed_key,
                                    fielder1_key,
                                    fielder2_key,
                                    row["is_wide"],
                                    row["is_noball"],
                                    row["is_legal_delivery"],
                                    row["is_super_over"],
                                    row["is_powerplay"],
                                    row["cumulative_runs"],
                                    row["cumulative_wickets"],
                                )
                            )
                            rows_loaded += 1
                            loaded_rows_for_match += 1

                            if len(pending_values) >= self.batch_size:
                                flush_pending()

                        if loaded_rows_for_match:
                            successful_match_ids.add(match_id)
                        else:
                            failed_match_ids.add(match_id)
                            logger.warning(
                                f"Skipping deliveries for {match_id}: no loadable rows "
                                f"(skipped {skipped_rows} rows due to missing keys)"
                            )

                        if skipped_rows:
                            skipped_rows_by_match[match_id] = skipped_rows

                    flush_pending()
                    conn.commit()

                    for match_id, skipped_rows in skipped_rows_by_match.items():
                        if match_id in successful_match_ids:
                            logger.warning(
                                f"Loaded deliveries for {match_id} with {skipped_rows} rows skipped"
                            )

                    logger.info(f"Loaded {rows_loaded} delivery records")
                    return FactLoadReport(rows_loaded, successful_match_ids, failed_match_ids)

                for match_id, match_df in df.groupby("match_id", sort=False):
                    try:
                        match_key = match_key_map.get(match_id)
                        if not match_key:
                            logger.warning(f"Skipping deliveries for {match_id}: missing match key")
                            failed_match_ids.add(match_id)
                            continue

                        cur.execute(
                            "DELETE FROM fact_deliveries WHERE match_key = %s",
                            (match_key,),
                        )

                        values_list: list[tuple] = []
                        skipped_rows = 0

                        for row in self._iter_records(match_df):
                            date_key = date_key_map.get(str(row["match_date"]))
                            venue_key = self._resolve_venue_key(row, venue_key_map)
                            bat_team_key = team_key_map.get(row["batting_team"])
                            bowl_team_key = team_key_map.get(row["bowling_team"])
                            batsman_key = resolve_player_key(row["batsman"])
                            non_striker_key = resolve_player_key(row["non_striker"])
                            bowler_key = resolve_player_key(row["bowler"])
                            dismissed_key = resolve_player_key(row.get("dismissed_player"))
                            fielder1_key = resolve_player_key(row.get("fielder1"))
                            fielder2_key = resolve_player_key(row.get("fielder2"))

                            if not all([
                                match_key,
                                date_key,
                                venue_key,
                                bat_team_key,
                                bowl_team_key,
                                batsman_key,
                                bowler_key,
                            ]):
                                skipped_rows += 1
                                continue

                            if non_striker_key is None:
                                non_striker_key = batsman_key

                            values_list.append((
                                match_key, date_key, venue_key,
                                bat_team_key, bowl_team_key,
                                batsman_key, non_striker_key, bowler_key,
                                row["innings_number"], row["over_number"], row["ball_number"],
                                row["legal_ball_number"],
                                row["runs_batsman"], row["runs_extras"], row["runs_total"],
                                row["is_boundary_four"], row["is_boundary_six"], row["is_dot_ball"],
                                row.get("extras_type"), row.get("extras_runs", 0),
                                row["is_wicket"], row.get("dismissal_type"),
                                dismissed_key, fielder1_key, fielder2_key,
                                row["is_wide"], row["is_noball"], row["is_legal_delivery"],
                                row["is_super_over"], row["is_powerplay"],
                                row["cumulative_runs"], row["cumulative_wickets"],
                            ))

                        if not values_list:
                            conn.rollback()
                            failed_match_ids.add(match_id)
                            logger.warning(
                                f"Skipping deliveries for {match_id}: no loadable rows "
                                f"(skipped {skipped_rows} rows due to missing keys)"
                            )
                            continue

                        psycopg2.extras.execute_values(
                            cur,
                            """
                            INSERT INTO fact_deliveries (
                                match_key, date_key, venue_key,
                                batting_team_key, bowling_team_key,
                                batsman_key, non_striker_key, bowler_key,
                                innings_number, over_number, ball_number,
                                legal_ball_number,
                                runs_batsman, runs_extras, runs_total,
                                is_boundary_four, is_boundary_six, is_dot_ball,
                                extras_type, extras_runs,
                                is_wicket, dismissal_type,
                                dismissed_player_key, fielder1_key, fielder2_key,
                                is_wide, is_noball, is_legal_delivery,
                                is_super_over, is_powerplay,
                                cumulative_runs, cumulative_wickets
                            ) VALUES %s
                            """,
                            values_list,
                            template="""(
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s
                            )""",
                        )
                        conn.commit()
                        rows_loaded += len(values_list)
                        successful_match_ids.add(match_id)
                        if skipped_rows:
                            logger.warning(
                                f"Loaded deliveries for {match_id} with {skipped_rows} rows skipped"
                            )
                    except Exception as match_error:
                        conn.rollback()
                        failed_match_ids.add(match_id)
                        logger.error(f"Failed to load deliveries for {match_id}: {match_error}")

            logger.info(f"Loaded {rows_loaded} delivery records")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to load deliveries: {e}")
            raise
        finally:
            self.return_connection(conn)
        return FactLoadReport(rows_loaded, successful_match_ids, failed_match_ids)

    def get_existing_match_ids(self) -> set[str]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT match_id FROM dim_match")
                return {row[0] for row in cur.fetchall()}
        except Exception:
            return set()
        finally:
            self.return_connection(conn)

    def start_etl_run(self, version: str) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO etl_run_log (started_at, status, pipeline_version)
                    VALUES (NOW(), 'running', %s)
                    RETURNING run_id
                    """,
                    (version,),
                )
                run_id = cur.fetchone()[0]
            conn.commit()
            return run_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to start ETL run log: {e}")
            raise
        finally:
            self.return_connection(conn)

    def complete_etl_run(
        self,
        run_id: int,
        status: str,
        files_processed: int,
        files_skipped: int,
        rows_loaded: int,
        error_message: Optional[str] = None,
    ) -> None:
        for attempt in range(1, 3):
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE etl_run_log
                        SET completed_at = NOW(), status = %s,
                            files_processed = %s, files_skipped = %s,
                            rows_loaded = %s, error_message = %s
                        WHERE run_id = %s
                        """,
                        (status, files_processed, files_skipped, rows_loaded, error_message, run_id),
                    )
                conn.commit()
                return
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                self._safe_rollback(conn)
                logger.warning(
                    f"Retrying ETL run log completion after connection error on attempt {attempt}: {e}"
                )
                self.close()
            except Exception as e:
                self._safe_rollback(conn)
                logger.error(f"Failed to complete ETL run log: {e}")
                return
            finally:
                self.return_connection(conn)

        logger.error("Failed to complete ETL run log after retrying connection errors")
