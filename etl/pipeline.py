import sys
import time
from pathlib import Path
from typing import Optional

from config.logging_config import get_logger
from config.settings import get_settings
from etl.data_quality import run_data_quality_checks
from etl.extract import (
    build_tracked_files,
    filter_new_files,
    run_extract,
    run_extract_local,
)
from etl.load import DatabaseLoader, FileRegistryEntry
from etl.transform import TransformResult, run_transform
from etl.validate import run_validate

logger = get_logger("pipeline")


class ETLPipeline:

    def __init__(
        self,
        local_data_dir: Optional[str] = None,
        skip_extract: bool = False,
        full_refresh: bool = False,
    ):
        self.settings = get_settings()
        self.local_data_dir = local_data_dir
        self.skip_extract = skip_extract
        self.full_refresh = full_refresh
        self.loader = DatabaseLoader()
        self.run_id: Optional[int] = None
        self.start_time: float = 0

    def run(self) -> bool:
        self.start_time = time.time()
        logger.info("=" * 60)
        logger.info("IPL Data Warehouse ETL Pipeline - Starting")
        logger.info(f"Version: {self.settings.etl_version}")
        logger.info("=" * 60)

        try:

            self.run_id = self.loader.start_etl_run(self.settings.etl_version)
            logger.info(f"ETL Run ID: {self.run_id}")

            self._ensure_schema()

            json_files = self._extract()
            if not json_files:
                logger.warning("No files to process after extraction")
                self._complete_run("success", 0, 0, 0)
                return True

            tracked_files = self._select_files_for_processing(json_files)
            if not tracked_files:
                logger.info(
                    "No new or changed files detected; skipping transform and load"
                )
                self._complete_run("success", 0, len(json_files), 0)
                return True

            valid_files, invalid_files = self._validate(
                [tracked_file.path for tracked_file in tracked_files]
            )
            if not valid_files:
                logger.warning("No valid files after validation")
                self._complete_run("success", 0, len(invalid_files), 0)
                return True

            tracked_by_match_id = {
                tracked_file.match_id: tracked_file for tracked_file in tracked_files
            }
            valid_tracked_files = [
                tracked_by_match_id[file_path.stem]
                for file_path in valid_files
                if file_path.stem in tracked_by_match_id
            ]

            transform_result = self._transform(valid_files)
            if transform_result.files_processed == 0:
                logger.error("Transform produced no results")
                self._complete_run(
                    "failed", 0, len(tracked_files), 0, "Transform produced no data"
                )
                return False

            rows_loaded, successful_match_ids = self._load(transform_result)
            self._record_processed_files(valid_tracked_files, successful_match_ids)

            dq_report = self._run_quality_checks()

            elapsed = time.time() - self.start_time
            files_processed = len(successful_match_ids)
            files_skipped = len(tracked_files) - files_processed + len(invalid_files)
            self._complete_run(
                "success",
                files_processed,
                files_skipped,
                rows_loaded,
            )

            logger.info("=" * 60)
            logger.info(f"Pipeline completed successfully in {elapsed:.1f}s")
            logger.info(f"Files processed: {files_processed}")
            logger.info(f"Total rows loaded: {rows_loaded}")
            logger.info(f"DQ Status: {dq_report.overall_status}")
            logger.info("=" * 60)
            return True

        except Exception as e:
            elapsed = time.time() - self.start_time
            logger.error(f"Pipeline failed after {elapsed:.1f}s: {e}")
            self._complete_run("failed", 0, 0, 0, str(e))
            return False
        finally:
            self.loader.close()

    def _ensure_schema(self) -> None:
        schema_exists = self.loader.schema_exists()
        if self.full_refresh or not schema_exists:
            self._setup_schema()
        else:
            logger.info(
                "Warehouse schema already exists; skipping destructive schema rebuild"
            )

        self.loader.ensure_file_registry_table()

    def _setup_schema(self) -> None:
        logger.info("Setting up database schema...")
        sql_dir = Path(__file__).parent.parent / "sql"

        schema_files = [
            sql_dir / "01_create_schema.sql",
            sql_dir / "02_create_indexes.sql",
            sql_dir / "03_seed_dimensions.sql",
        ]

        for sql_file in schema_files:
            if sql_file.exists():
                self.loader.execute_schema(str(sql_file))
            else:
                logger.warning(f"Schema file not found: {sql_file}")

        logger.info("Schema setup complete")

    def _select_files_for_processing(self, json_files: list[Path]) -> list:
        tracked_files = build_tracked_files(json_files)
        if self.full_refresh:
            logger.info("Full refresh enabled; processing every extracted file")
            return tracked_files

        processed_files = self.loader.get_processed_file_registry()
        return filter_new_files(tracked_files, processed_files)

    def _extract(self) -> list[Path]:
        logger.info("Starting extraction phase...")

        if self.local_data_dir:
            json_files = run_extract_local(self.local_data_dir)
        elif self.skip_extract:

            data_dir = Path(self.settings.data_dir)
            if data_dir.exists():
                json_files = run_extract_local(str(data_dir))
            else:
                json_files = run_extract()
        else:
            json_files = run_extract()

        logger.info(f"Extraction complete: {len(json_files)} JSON files found")
        return json_files

    def _validate(self, json_files: list[Path]) -> tuple[list[Path], list[Path]]:
        logger.info(f"Starting validation of {len(json_files)} files...")
        valid_files, invalid_files = run_validate(json_files)
        logger.info(
            f"Validation complete: {len(valid_files)} valid, {len(invalid_files)} invalid"
        )
        return valid_files, invalid_files

    def _transform(self, valid_files: list[Path]) -> TransformResult:
        logger.info(f"Starting transformation of {len(valid_files)} files...")
        result = run_transform(valid_files)
        logger.info(
            f"Transform complete: {result.files_processed} processed, "
            f"{result.files_failed} failed"
        )
        return result

    def _load(self, transform_result: TransformResult) -> tuple[int, set[str]]:
        logger.info("Starting load phase...")
        total_rows = 0

        logger.info("Loading dimension tables...")
        date_key_map = self.loader.load_dim_dates(transform_result.df_dates)
        total_rows += len(date_key_map)

        venue_key_map = self.loader.load_dim_venues(transform_result.df_venues)
        total_rows += len(venue_key_map)

        team_key_map = self.loader.load_dim_teams(transform_result.df_teams)
        total_rows += len(team_key_map)

        player_key_map = self.loader.load_dim_players(transform_result.df_players)
        total_rows += len(player_key_map)

        match_key_map = self.loader.load_dim_matches(transform_result.df_matches)
        total_rows += len(match_key_map)

        innings_key_map = self.loader.load_dim_innings(
            transform_result.df_innings, match_key_map, team_key_map
        )
        total_rows += len(innings_key_map)

        player_name_to_id: dict[str, str] = {}
        if not transform_result.df_players.empty:
            for _, row in transform_result.df_players.iterrows():
                player_name_to_id[row["player_name"]] = row["player_id"]

        logger.info("Loading fact tables...")
        match_summaries_df = getattr(transform_result, "df_match_summaries", None)
        if match_summaries_df is not None and not match_summaries_df.empty:
            summary_report = self.loader.load_fact_match_summary(
                match_summaries_df,
                match_key_map,
                date_key_map,
                venue_key_map,
                team_key_map,
                player_key_map,
                player_name_to_id,
            )
            total_rows += summary_report.rows_loaded

        delivery_report = self.loader.load_fact_deliveries(
            transform_result.df_deliveries,
            match_key_map,
            date_key_map,
            venue_key_map,
            team_key_map,
            player_key_map,
            player_name_to_id,
        )
        total_rows += delivery_report.rows_loaded

        logger.info(f"Load complete: {total_rows} total rows loaded")
        return total_rows, delivery_report.successful_match_ids

    def _record_processed_files(
        self, tracked_files: list, successful_match_ids: set[str]
    ) -> None:
        if not successful_match_ids:
            logger.warning("No successful match IDs were recorded during load")
            return

        entries = [
            FileRegistryEntry(
                match_id=tracked_file.match_id,
                file_name=tracked_file.path.name,
                file_checksum=tracked_file.file_checksum,
                source_checksum=tracked_file.file_checksum,
            )
            for tracked_file in tracked_files
            if tracked_file.match_id in successful_match_ids
        ]
        self.loader.upsert_file_registry_entries(entries, run_id=self.run_id)

    def _run_quality_checks(self):
        logger.info("Running data quality checks...")
        report = run_data_quality_checks(run_id=self.run_id)
        return report

    def _complete_run(
        self,
        status: str,
        files_processed: int,
        files_skipped: int,
        rows_loaded: int,
        error_message: Optional[str] = None,
    ) -> None:
        if self.run_id:
            self.loader.complete_etl_run(
                self.run_id,
                status,
                files_processed,
                files_skipped,
                rows_loaded,
                error_message,
            )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="IPL Data Warehouse ETL Pipeline")
    parser.add_argument(
        "--local-data",
        type=str,
        help="Path to local pre-extracted JSON data directory",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Skip download and use existing data directory",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Only create/update schema, don't load data",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Rebuild schema and reload every source file",
    )
    args = parser.parse_args()

    if args.schema_only:
        pipeline = ETLPipeline(full_refresh=True)
        pipeline._setup_schema()
        logger.info("Schema setup complete (no data loaded)")
        sys.exit(0)

    pipeline = ETLPipeline(
        local_data_dir=args.local_data,
        skip_extract=args.skip_extract,
        full_refresh=args.full_refresh,
    )

    success = pipeline.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
