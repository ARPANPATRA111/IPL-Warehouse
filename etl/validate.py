import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger("validate")


@dataclass
class ValidationResult:

    is_valid: bool
    file_path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _resolve_validation_path(file_path: Path | None) -> Path:
    return file_path if file_path is not None else Path("<memory>")


def _build_validation_result(
    file_path: Path | None,
    errors: list[str],
    warnings: list[str] | None = None,
) -> ValidationResult:
    return ValidationResult(
        is_valid=len(errors) == 0,
        file_path=_resolve_validation_path(file_path),
        errors=errors,
        warnings=warnings or [],
    )


def _validate_schema_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    required_keys = ["meta", "info", "innings"]
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required top-level key: '{key}'")

    if "meta" in data:
        if "data_version" not in data["meta"]:
            errors.append("Missing 'meta.data_version'")
        if "created" not in data["meta"]:
            errors.append("Missing 'meta.created'")

    if "info" in data:
        info = data["info"]
        required_info = [
            "teams",
            "dates",
            "overs",
            "gender",
            "match_type",
            "toss",
            "outcome",
        ]
        for key in required_info:
            if key not in info:
                errors.append(f"Missing 'info.{key}'")

        teams = info.get("teams")
        if isinstance(teams, list) and len(teams) != 2:
            errors.append(f"'info.teams' must have exactly 2 entries, got {len(teams)}")

    return errors


def validate_schema(
    data: dict[str, Any], file_path: Path | None = None
) -> ValidationResult:
    return _build_validation_result(file_path, _validate_schema_errors(data))


def _validate_data_type_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    info = data.get("info", {})

    dates = info.get("dates")
    if dates is not None and not isinstance(dates, list):
        errors.append(f"'info.dates' must be a list, got {type(dates).__name__}")

    teams = info.get("teams")
    if teams is not None:
        if not isinstance(teams, list):
            errors.append(f"'info.teams' must be a list, got {type(teams).__name__}")

    overs = info.get("overs")
    if overs is not None and not isinstance(overs, int):
        errors.append(f"'info.overs' must be an integer, got {type(overs).__name__}")

    innings = data.get("innings")
    if innings is not None and not isinstance(innings, list):
        errors.append(f"'innings' must be a list, got {type(innings).__name__}")

    toss = info.get("toss")
    if toss is not None and not isinstance(toss, dict):
        errors.append(f"'info.toss' must be a dict, got {type(toss).__name__}")

    return errors


def validate_data_types(
    data: dict[str, Any], file_path: Path | None = None
) -> ValidationResult:
    return _build_validation_result(file_path, _validate_data_type_errors(data))


def _validate_business_rule_results(
    data: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    info = data.get("info", {})
    innings = data.get("innings", [])

    if len(innings) < 1:
        errors.append(f"Match must have at least 1 innings, got {len(innings)}")
    elif len(innings) > 5:
        warnings.append(f"Unusual number of innings: {len(innings)}")

    bpo = info.get("balls_per_over", 6)
    if bpo != 6:
        warnings.append(f"Unexpected balls_per_over: {bpo}")

    teams = info.get("teams", [])
    if teams and len(teams) != 2:
        errors.append(f"Match must list exactly 2 teams, got {len(teams)}")

    players = info.get("players", {})
    if players:
        for team in teams:
            if team not in players:
                warnings.append(f"Team '{team}' not found in 'players' dict")
            elif len(players.get(team, [])) < 11:
                warnings.append(
                    f"Team '{team}' has fewer than 11 players: {len(players.get(team, []))}"
                )

    toss = info.get("toss", {})
    if toss:
        toss_winner = toss.get("winner")
        if toss_winner and toss_winner not in teams:
            errors.append(f"Toss winner '{toss_winner}' not in teams list")
        toss_decision = toss.get("decision")
        if toss_decision and toss_decision not in ("bat", "field"):
            errors.append(f"Invalid toss decision: '{toss_decision}'")

    for i, inn in enumerate(innings):
        if "team" not in inn:
            errors.append(f"Innings {i+1} missing 'team' field")
        if "overs" not in inn:
            errors.append(f"Innings {i+1} missing 'overs' field")
        elif not isinstance(inn["overs"], list):
            errors.append(f"Innings {i+1} 'overs' must be a list")
        elif len(inn["overs"]) == 0:
            warnings.append(f"Innings {i+1} has no overs recorded")

    outcome = info.get("outcome", {})
    if outcome:
        has_winner = "winner" in outcome
        has_result = "result" in outcome
        if not has_winner and not has_result:
            warnings.append("Outcome has neither 'winner' nor 'result'")

    return errors, warnings


def validate_business_rules(
    data: dict[str, Any], file_path: Path | None = None
) -> ValidationResult:
    errors, warnings = _validate_business_rule_results(data)
    return _build_validation_result(file_path, errors, warnings)


def validate_file(file_path: Path) -> ValidationResult:
    all_errors: list[str] = []
    all_warnings: list[str] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return ValidationResult(
            is_valid=False,
            file_path=file_path,
            errors=[f"Invalid JSON: {e}"],
        )
    except OSError as e:
        return ValidationResult(
            is_valid=False,
            file_path=file_path,
            errors=[f"Cannot read file: {e}"],
        )

    schema_errors = _validate_schema_errors(data)
    all_errors.extend(schema_errors)

    if schema_errors:
        return ValidationResult(
            is_valid=False,
            file_path=file_path,
            errors=all_errors,
            warnings=all_warnings,
        )

    type_errors = _validate_data_type_errors(data)
    all_errors.extend(type_errors)

    biz_errors, biz_warnings = _validate_business_rule_results(data)
    all_errors.extend(biz_errors)
    all_warnings.extend(biz_warnings)

    is_valid = len(all_errors) == 0

    if not is_valid:
        logger.warning(f"Validation FAILED for {file_path.name}: {all_errors}")
    elif all_warnings:
        logger.debug(
            f"Validation passed with warnings for {file_path.name}: {all_warnings}"
        )

    return ValidationResult(
        is_valid=is_valid,
        file_path=file_path,
        errors=all_errors,
        warnings=all_warnings,
    )


def reject_file(file_path: Path, errors: list[str]) -> None:
    settings = get_settings()
    rejected_dir = settings.rejected_data_dir
    rejected_dir.mkdir(parents=True, exist_ok=True)

    dest = rejected_dir / file_path.name
    shutil.move(str(file_path), str(dest))

    error_log = rejected_dir / f"{file_path.stem}_errors.txt"
    with open(error_log, "w", encoding="utf-8") as f:
        f.write(f"File: {file_path.name}\n")
        f.write(f"Errors ({len(errors)}):\n")
        for err in errors:
            f.write(f"  - {err}\n")

    logger.info(f"Rejected file moved to: {dest}")


def run_validate(
    files: list[Path], reject_invalid: bool = True
) -> tuple[list[Path], list[Path]]:
    logger.info(f"Starting validation of {len(files)} files")

    valid_files: list[Path] = []
    invalid_files: list[Path] = []

    for file_path in files:
        result = validate_file(file_path)
        if result.is_valid:
            valid_files.append(file_path)
        else:
            invalid_files.append(file_path)
            if reject_invalid:
                reject_file(file_path, result.errors)

    logger.info(
        f"Validation complete: {len(valid_files)} valid, {len(invalid_files)} invalid"
    )
    return valid_files, invalid_files
