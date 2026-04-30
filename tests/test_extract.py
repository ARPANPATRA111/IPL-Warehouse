from etl.extract import build_tracked_files, filter_new_files, list_json_files, run_extract_local

class TestListJsonFiles:

    def test_finds_json_files(self, tmp_path):
        (tmp_path / "match1.json").write_text("{}")
        (tmp_path / "match2.json").write_text("{}")
        (tmp_path / "readme.txt").write_text("not json")

        result = list_json_files(str(tmp_path))
        assert len(result) == 2
        assert all(f.suffix == ".json" for f in result)

    def test_empty_directory(self, tmp_path):
        result = list_json_files(str(tmp_path))
        assert result == []

    def test_nested_not_included(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.json").write_text("{}")
        (tmp_path / "top.json").write_text("{}")

        result = list_json_files(str(tmp_path))
        assert len(result) == 1

class TestFilterNewFiles:

    def test_filters_existing(self, tmp_path):
        f1 = tmp_path / "1001.json"
        f2 = tmp_path / "1002.json"
        f3 = tmp_path / "1003.json"
        f1.write_text("{}")
        f2.write_text("{}")
        f3.write_text("{}")

        all_files = build_tracked_files([f1, f2, f3])
        existing_ids = {
            all_files[0].match_id: all_files[0].file_checksum,
            all_files[1].match_id: all_files[1].file_checksum,
        }

        result = filter_new_files(all_files, existing_ids)
        assert len(result) == 1
        assert result[0].match_id == "1003"

    def test_no_existing(self, tmp_path):
        f1 = tmp_path / "1001.json"
        f1.write_text("{}")

        result = filter_new_files(build_tracked_files([f1]), {})
        assert len(result) == 1

    def test_all_existing(self, tmp_path):
        f1 = tmp_path / "1001.json"
        f1.write_text("{}")

        tracked_files = build_tracked_files([f1])
        result = filter_new_files(
            tracked_files,
            {tracked_files[0].match_id: tracked_files[0].file_checksum},
        )
        assert result == []

    def test_includes_changed_file(self, tmp_path):
        f1 = tmp_path / "1001.json"
        f1.write_text('{"version": 2}')

        tracked_files = build_tracked_files([f1])
        result = filter_new_files(tracked_files, {"1001": "old-checksum"})

        assert len(result) == 1
        assert result[0].match_id == "1001"

class TestRunExtractLocal:

    def test_accepts_string_directory(self, tmp_path):
        (tmp_path / "match1.json").write_text("{}")

        result = run_extract_local(str(tmp_path))

        assert len(result) == 1
        assert result[0].name == "match1.json"
