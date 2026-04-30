from unittest.mock import MagicMock, patch

import pytest

from etl.pipeline import ETLPipeline

class TestETLPipeline:

    def test_initialization_defaults(self):
        pipeline = ETLPipeline()
        assert pipeline.local_data_dir is None
        assert pipeline.skip_extract is False
        assert pipeline.run_id is None

    def test_initialization_with_local_data(self):
        pipeline = ETLPipeline(local_data_dir="/tmp/data")
        assert pipeline.local_data_dir == "/tmp/data"

    @patch("etl.pipeline.DatabaseLoader")
    @patch("etl.pipeline.run_extract_local")
    @patch("etl.pipeline.run_validate")
    @patch("etl.pipeline.run_transform")
    @patch("etl.pipeline.run_data_quality_checks")
    def test_run_empty_data(
        self, mock_dq, mock_transform, mock_validate, mock_extract, mock_loader_cls
    ):
        mock_loader = MagicMock()
        mock_loader.start_etl_run.return_value = 1
        mock_loader_cls.return_value = mock_loader
        mock_extract.return_value = []

        pipeline = ETLPipeline(local_data_dir="/tmp/empty")
        pipeline.loader = mock_loader
        pipeline.run_id = 1


        result = pipeline._extract()
        assert result == []

    @patch("etl.pipeline.DatabaseLoader")
    def test_setup_schema(self, mock_loader_cls, tmp_path):
        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader


        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "01_create_schema.sql").write_text("CREATE TABLE test;")
        (sql_dir / "02_create_indexes.sql").write_text("CREATE INDEX;")
        (sql_dir / "03_seed_dimensions.sql").write_text("INSERT INTO;")

        pipeline = ETLPipeline()
        pipeline.loader = mock_loader

        with patch("etl.pipeline.Path") as mock_path:
            mock_path.return_value.parent.parent.__truediv__ = lambda s, n: sql_dir

            pass
