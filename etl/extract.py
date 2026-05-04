import hashlib
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger("extract")


@dataclass(frozen=True)
class TrackedFile:

    path: Path
    match_id: str
    file_checksum: str


def compute_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def download_zip(
    url: str,
    destination: Path,
    timeout_connect: int = 10,
    timeout_read: int = 60,
    max_retries: int = 3,
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    zip_path = destination / "ipl_json.zip"
    checksum_path = destination / "ipl_json.zip.sha256"

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Download attempt {attempt}/{max_retries} from {url}")

            response = requests.get(
                url,
                stream=True,
                timeout=(timeout_connect, timeout_read),
            )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            with open(zip_path, "wb") as f:
                with tqdm(
                    total=total_size,
                    unit="iB",
                    unit_scale=True,
                    desc="Downloading IPL data",
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        size = f.write(chunk)
                        pbar.update(size)

            new_checksum = compute_sha256(zip_path)

            if checksum_path.exists():
                old_checksum = checksum_path.read_text().strip()
                if old_checksum == new_checksum:
                    logger.info(
                        "File unchanged (same checksum), skipping re-extraction"
                    )
                    return zip_path

            checksum_path.write_text(new_checksum)
            logger.info(f"Download complete: {zip_path} ({total_size} bytes)")
            return zip_path

        except requests.exceptions.RequestException as e:
            logger.warning(f"Download attempt {attempt} failed: {e}")
            if attempt < max_retries:
                wait_time = 2**attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(
                    f"Failed to download {url} after {max_retries} attempts: {e}"
                ) from e

    raise RuntimeError(f"Failed to download {url}")


def extract_zip(zip_path: Path, extract_to: Path) -> int:
    extract_to.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad_file = zf.testzip()
            if bad_file is not None:
                logger.warning(f"Corrupted file in archive: {bad_file}")

            json_files = [f for f in zf.namelist() if f.endswith(".json")]
            logger.info(f"Found {len(json_files)} JSON files in archive")

            for file_name in tqdm(json_files, desc="Extracting files"):
                zf.extract(file_name, extract_to)

            return len(json_files)

    except zipfile.BadZipFile as e:
        raise RuntimeError(f"Corrupted ZIP file: {zip_path}") from e


def list_json_files(directory: Path | str) -> list[Path]:
    directory = Path(directory)

    if not directory.exists():
        logger.warning(f"Directory does not exist: {directory}")
        return []

    json_files = sorted(directory.glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files in {directory}")
    return json_files


def build_tracked_files(json_files: list[Path]) -> list[TrackedFile]:
    tracked_files = [
        TrackedFile(
            path=file_path,
            match_id=file_path.stem,
            file_checksum=compute_sha256(file_path),
        )
        for file_path in json_files
    ]
    logger.info(f"Computed checksums for {len(tracked_files)} JSON files")
    return tracked_files


def get_processed_match_ids(
    existing_ids: Optional[set[str]] = None,
) -> set[str]:
    if existing_ids is None:
        return set()
    return existing_ids


def filter_new_files(
    all_files: list[TrackedFile],
    processed_files: dict[str, str],
) -> list[TrackedFile]:
    new_files = [
        tracked_file
        for tracked_file in all_files
        if processed_files.get(tracked_file.match_id) != tracked_file.file_checksum
    ]
    logger.info(
        f"Filtered to {len(new_files)} new or changed files "
        f"(skipped {len(all_files) - len(new_files)} already processed)"
    )
    return new_files


def run_extract(full_refresh: bool = False) -> list[Path]:
    settings = get_settings()
    settings.ensure_directories()

    logger.info("Starting extraction phase")

    zip_path = download_zip(
        url=settings.data_source_url,
        destination=settings.processed_data_dir,
        timeout_connect=settings.download_timeout_connect,
        timeout_read=settings.download_timeout_read,
        max_retries=settings.download_max_retries,
    )

    extract_count = extract_zip(zip_path, settings.raw_data_dir)
    logger.info(f"Extracted {extract_count} files to {settings.raw_data_dir}")

    json_files = list_json_files(settings.raw_data_dir)

    logger.info(f"Extraction complete: {len(json_files)} files available")
    return json_files


def run_extract_local(data_dir: Path | str) -> list[Path]:
    data_dir = Path(data_dir)
    logger.info(f"Using local data directory: {data_dir}")
    json_files = list_json_files(data_dir)
    logger.info(f"Found {len(json_files)} local JSON files")
    return json_files
