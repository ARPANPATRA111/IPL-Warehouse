from pathlib import Path
from unittest.mock import MagicMock, patch

from etl.pipeline import ETLPipeline

@patch("etl.pipeline.build_tracked_files")
@patch("etl.pipeline.filter_new_files")
def test_select_files_for_processing_uses_registry(mock_filter_new_files, mock_build_tracked_files):
    tracked_file = MagicMock(match_id="12345")
    mock_build_tracked_files.return_value = [tracked_file]
    mock_filter_new_files.return_value = [tracked_file]

    pipeline = ETLPipeline()
    pipeline.loader = MagicMock()
    pipeline.loader.get_processed_file_registry.return_value = {"12345": "old-checksum"}

    result = pipeline._select_files_for_processing([Path("12345.json")])

    assert result == [tracked_file]
    mock_filter_new_files.assert_called_once_with([tracked_file], {"12345": "old-checksum"})

@patch("etl.pipeline.build_tracked_files")
@patch("etl.pipeline.filter_new_files")
def test_select_files_for_processing_skips_registry_on_full_refresh(mock_filter_new_files, mock_build_tracked_files):
    tracked_file = MagicMock(match_id="12345")
    mock_build_tracked_files.return_value = [tracked_file]

    pipeline = ETLPipeline(full_refresh=True)
    pipeline.loader = MagicMock()

    result = pipeline._select_files_for_processing([Path("12345.json")])

    assert result == [tracked_file]
    mock_filter_new_files.assert_not_called()
