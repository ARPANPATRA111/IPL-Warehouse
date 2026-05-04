import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from config.logging_config import get_logger
from etl.transform_helpers import (
    compute_overs_decimal,
    extract_win_info,
    generate_date_attributes,
    get_franchise_group,
    get_team_short_name,
    normalize_team_name,
    parse_match_date,
    parse_season,
)

logger = get_logger("transform")


@dataclass
class TransformResult:

    df_matches: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_innings: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_deliveries: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_players: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_teams: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_venues: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_dates: pd.DataFrame = field(default_factory=pd.DataFrame)
    files_processed: int = 0
    files_failed: int = 0
    errors: list[str] = field(default_factory=list)


def parse_single_match(file_path: Path) -> Optional[dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to parse {file_path.name}: {e}")
        return None


def extract_players_from_match(data: dict[str, Any]) -> dict[str, str]:
    registry = data.get("info", {}).get("registry", {}).get("people", {})
    return {uuid: name for name, uuid in registry.items()}


def extract_match_info(data: dict[str, Any], match_id: str) -> dict[str, Any]:
    info = data["info"]
    meta = data["meta"]
    season = parse_season(info.get("season", ""))
    match_date = parse_match_date(info["dates"])

    event = info.get("event", {})
    match_number = event.get("match_number")

    return {
        "match_id": match_id,
        "season": season,
        "match_number": match_number,
        "match_type": info.get("match_type", "T20"),
        "gender": info.get("gender", "male"),
        "balls_per_over": info.get("balls_per_over", 6),
        "overs_per_side": info.get("overs", 20),
        "data_version": meta.get("data_version", "1.0.0"),
        "match_date": match_date,
        "city": info.get("city", "Unknown"),
        "venue": info.get("venue", "Unknown"),
        "teams": info.get("teams", []),
        "toss": info.get("toss", {}),
        "outcome": info.get("outcome", {}),
        "player_of_match": info.get("player_of_match", []),
        "players": info.get("players", {}),
        "registry": info.get("registry", {}).get("people", {}),
    }


def transform_deliveries_for_innings(
    innings_data: dict[str, Any],
    match_id: str,
    innings_number: int,
    match_date: date,
    venue: str,
    city: str,
    batting_team: str,
    bowling_team: str,
    is_super_over: bool,
    registry: dict[str, str],
) -> list[dict[str, Any]]:
    deliveries_list: list[dict[str, Any]] = []
    overs_data = innings_data.get("overs", [])

    powerplays = innings_data.get("powerplays", [])
    powerplay_overs: set[int] = set()
    if powerplays:
        for pp in powerplays:
            from_over = int(float(pp.get("from", 0.1)))
            to_over = int(float(pp.get("to", 5.6)))
            powerplay_overs.update(range(from_over, to_over + 1))
    else:

        if not is_super_over:
            powerplay_overs = set(range(0, 6))

    cumulative_runs = 0
    cumulative_wickets = 0
    legal_ball_counter = 0

    for over_data in overs_data:
        over_number = over_data["over"]
        ball_index = 0

        for delivery in over_data["deliveries"]:
            runs = delivery.get("runs", {})
            runs_batsman = runs.get("batter", 0)
            runs_extras = runs.get("extras", 0)
            runs_total = runs.get("total", 0)

            extras_obj = delivery.get("extras", {})
            is_wide = "wides" in extras_obj
            is_noball = "noballs" in extras_obj
            is_legal = not (is_wide or is_noball)

            extras_type: Optional[str] = None
            extras_runs_val = 0
            if extras_obj:
                if is_wide:
                    extras_type = "wides"
                    extras_runs_val = extras_obj.get("wides", 0)
                elif is_noball:
                    extras_type = "noballs"
                    extras_runs_val = extras_obj.get("noballs", 0)
                elif "byes" in extras_obj:
                    extras_type = "byes"
                    extras_runs_val = extras_obj.get("byes", 0)
                elif "legbyes" in extras_obj:
                    extras_type = "legbyes"
                    extras_runs_val = extras_obj.get("legbyes", 0)
                elif "penalty" in extras_obj:
                    extras_type = "penalty"
                    extras_runs_val = extras_obj.get("penalty", 0)

            non_boundary = runs.get("non_boundary", False)
            is_boundary_four = runs_batsman == 4 and not non_boundary and not is_wide
            is_boundary_six = runs_batsman == 6 and not non_boundary and not is_wide

            is_dot_ball = runs_total == 0

            if is_legal:
                legal_ball_counter += 1
            current_legal_ball = legal_ball_counter

            cumulative_runs += runs_total

            wickets = delivery.get("wickets", [])
            is_wicket = len(wickets) > 0
            dismissal_type: Optional[str] = None
            dismissed_player: Optional[str] = None
            fielder1: Optional[str] = None
            fielder2: Optional[str] = None

            if is_wicket:
                wicket = wickets[0]
                dismissal_type = wicket.get("kind")
                dismissed_player = wicket.get("player_out")
                fielders = wicket.get("fielders", [])
                if len(fielders) >= 1:
                    fielder1 = fielders[0].get("name")
                if len(fielders) >= 2:
                    fielder2 = fielders[1].get("name")

                if dismissal_type not in ("retired hurt",):
                    cumulative_wickets += 1

            is_powerplay = over_number in powerplay_overs

            delivery_record = {
                "match_id": match_id,
                "match_date": match_date,
                "venue": venue,
                "city": city,
                "batting_team": normalize_team_name(batting_team),
                "bowling_team": normalize_team_name(bowling_team),
                "innings_number": innings_number,
                "over_number": over_number,
                "ball_number": ball_index,
                "legal_ball_number": current_legal_ball,
                "batsman": delivery["batter"],
                "non_striker": delivery["non_striker"],
                "bowler": delivery["bowler"],
                "runs_batsman": runs_batsman,
                "runs_extras": runs_extras,
                "runs_total": runs_total,
                "is_boundary_four": is_boundary_four,
                "is_boundary_six": is_boundary_six,
                "is_dot_ball": is_dot_ball,
                "extras_type": extras_type,
                "extras_runs": extras_runs_val,
                "is_wicket": is_wicket,
                "dismissal_type": dismissal_type,
                "dismissed_player": dismissed_player,
                "fielder1": fielder1,
                "fielder2": fielder2,
                "is_wide": is_wide,
                "is_noball": is_noball,
                "is_legal_delivery": is_legal,
                "is_super_over": is_super_over,
                "is_powerplay": is_powerplay,
                "cumulative_runs": cumulative_runs,
                "cumulative_wickets": cumulative_wickets,
            }

            deliveries_list.append(delivery_record)
            ball_index += 1

            if len(wickets) > 1:
                for extra_wicket in wickets[1:]:
                    extra_dismissal_type = extra_wicket.get("kind")
                    if extra_dismissal_type not in ("retired hurt",):
                        cumulative_wickets += 1
                    logger.debug(
                        f"Multiple wickets on same ball: {match_id} "
                        f"inn={innings_number} over={over_number} ball={ball_index}"
                    )

    return deliveries_list


def transform_match(file_path: Path) -> Optional[dict[str, Any]]:
    data = parse_single_match(file_path)
    if data is None:
        return None

    match_id = file_path.stem
    info = data["info"]
    registry = info.get("registry", {}).get("people", {})
    name_to_id = {name: uuid for name, uuid in registry.items()}

    match_info = extract_match_info(data, match_id)
    match_date = match_info["match_date"]
    season = match_info["season"]
    venue = match_info["venue"]
    city = match_info["city"]
    teams = match_info["teams"]

    normalized_teams = [normalize_team_name(t) for t in teams]

    outcome = match_info["outcome"]
    winner, win_type, win_margin, is_dls, result = extract_win_info(outcome)
    if winner:
        winner = normalize_team_name(winner)

    toss = match_info["toss"]
    toss_winner = normalize_team_name(toss.get("winner", teams[0]))
    toss_decision = toss.get("decision", "bat")

    pom_list = match_info["player_of_match"]
    player_of_match = pom_list[0] if pom_list else None

    innings_records: list[dict[str, Any]] = []
    all_deliveries: list[dict[str, Any]] = []

    innings_data_list = data.get("innings", [])
    for idx, innings_data in enumerate(innings_data_list):
        innings_number = idx + 1
        batting_team = normalize_team_name(innings_data.get("team", ""))
        bowling_team = [t for t in normalized_teams if t != batting_team]
        bowling_team_name = (
            bowling_team[0]
            if bowling_team
            else normalized_teams[1] if len(normalized_teams) > 1 else ""
        )

        is_super_over = innings_data.get("super_over", False)
        target = innings_data.get("target", {})

        deliveries = transform_deliveries_for_innings(
            innings_data=innings_data,
            match_id=match_id,
            innings_number=innings_number,
            match_date=match_date,
            venue=venue,
            city=city,
            batting_team=batting_team,
            bowling_team=bowling_team_name,
            is_super_over=is_super_over,
            registry=registry,
        )

        total_runs = sum(d["runs_total"] for d in deliveries)
        total_wickets = (
            max(d["cumulative_wickets"] for d in deliveries) if deliveries else 0
        )
        legal_balls = sum(1 for d in deliveries if d["is_legal_delivery"])
        total_overs = compute_overs_decimal(legal_balls)
        total_extras = sum(d["runs_extras"] for d in deliveries)

        innings_record = {
            "match_id": match_id,
            "innings_number": innings_number,
            "batting_team": batting_team,
            "bowling_team": bowling_team_name,
            "total_runs": total_runs,
            "total_wickets": total_wickets,
            "total_overs": total_overs,
            "total_extras": total_extras,
            "is_super_over": is_super_over,
            "target_runs": target.get("runs"),
            "target_overs": target.get("overs"),
            "has_dls": is_dls,
            "is_forfeited": innings_data.get("forfeited", False),
        }
        innings_records.append(innings_record)
        all_deliveries.extend(deliveries)

    team1_innings = [
        i
        for i in innings_records
        if i["innings_number"] == 1 and not i["is_super_over"]
    ]
    team2_innings = [
        i
        for i in innings_records
        if i["innings_number"] == 2 and not i["is_super_over"]
    ]

    team1_score = team1_innings[0]["total_runs"] if team1_innings else None
    team1_wickets = team1_innings[0]["total_wickets"] if team1_innings else None
    team1_overs = team1_innings[0]["total_overs"] if team1_innings else None
    team2_score = team2_innings[0]["total_runs"] if team2_innings else None
    team2_wickets = team2_innings[0]["total_wickets"] if team2_innings else None
    team2_overs = team2_innings[0]["total_overs"] if team2_innings else None

    total_fours = sum(1 for d in all_deliveries if d["is_boundary_four"])
    total_sixes = sum(1 for d in all_deliveries if d["is_boundary_six"])
    total_extras_match = sum(d["runs_extras"] for d in all_deliveries)

    eliminator_winner: Optional[str] = None
    if result == "tie" and "eliminator" in outcome:
        eliminator_winner = normalize_team_name(outcome["eliminator"])

    match_summary = {
        "match_id": match_id,
        "match_date": match_date,
        "venue": venue,
        "city": city,
        "team1": normalized_teams[0] if normalized_teams else "",
        "team2": normalized_teams[1] if len(normalized_teams) > 1 else "",
        "toss_winner": toss_winner,
        "toss_decision": toss_decision,
        "match_winner": winner,
        "win_type": win_type,
        "win_margin": win_margin,
        "is_dls": is_dls,
        "result": result,
        "eliminator_winner": eliminator_winner,
        "player_of_match": player_of_match,
        "team1_score": team1_score,
        "team1_wickets": team1_wickets,
        "team1_overs": team1_overs,
        "team2_score": team2_score,
        "team2_wickets": team2_wickets,
        "team2_overs": team2_overs,
        "total_fours": total_fours,
        "total_sixes": total_sixes,
        "total_extras": total_extras_match,
        "season": season,
        "match_number": match_info["match_number"],
    }

    player_entries: dict[str, dict[str, Any]] = {}
    for player_name, player_id in name_to_id.items():
        player_entries[player_id] = {
            "player_id": player_id,
            "player_name": player_name,
            "match_date": match_date,
        }

    date_info = generate_date_attributes(match_date, season)

    venue_info = {
        "venue_name": venue,
        "city": city if city != "Unknown" else None,
    }

    return {
        "match": match_info,
        "match_summary": match_summary,
        "innings": innings_records,
        "deliveries": all_deliveries,
        "players": player_entries,
        "team_names": normalized_teams,
        "venue": venue_info,
        "date_info": date_info,
    }


def run_transform(valid_files: list[Path]) -> TransformResult:
    logger.info(f"Starting transformation of {len(valid_files)} files")

    all_matches: list[dict] = []
    all_match_summaries: list[dict] = []
    all_innings: list[dict] = []
    all_deliveries: list[dict] = []
    all_players: dict[str, dict] = {}
    all_teams: set[str] = set()
    all_venues: dict[str, dict] = {}
    all_dates: dict[str, dict] = {}
    files_processed = 0
    files_failed = 0
    errors: list[str] = []

    for file_path in valid_files:
        try:
            result = transform_match(file_path)
            if result is None:
                files_failed += 1
                errors.append(f"Failed to transform: {file_path.name}")
                continue

            all_matches.append(
                {
                    "match_id": result["match"]["match_id"],
                    "season": result["match"]["season"],
                    "match_number": result["match"]["match_number"],
                    "match_type": result["match"]["match_type"],
                    "gender": result["match"]["gender"],
                    "balls_per_over": result["match"]["balls_per_over"],
                    "overs_per_side": result["match"]["overs_per_side"],
                    "data_version": result["match"]["data_version"],
                }
            )

            all_match_summaries.append(result["match_summary"])
            all_innings.extend(result["innings"])
            all_deliveries.extend(result["deliveries"])

            for pid, pinfo in result["players"].items():
                if pid in all_players:
                    existing = all_players[pid]
                    if pinfo["match_date"] > existing.get(
                        "last_match_date", pinfo["match_date"]
                    ):
                        existing["player_name"] = pinfo["player_name"]
                        existing["last_match_date"] = pinfo["match_date"]
                    if pinfo["match_date"] < existing.get(
                        "first_match_date", pinfo["match_date"]
                    ):
                        existing["first_match_date"] = pinfo["match_date"]
                    existing["total_matches"] = existing.get("total_matches", 0) + 1
                else:
                    all_players[pid] = {
                        "player_id": pid,
                        "player_name": pinfo["player_name"],
                        "first_match_date": pinfo["match_date"],
                        "last_match_date": pinfo["match_date"],
                        "total_matches": 1,
                    }

            for team in result["team_names"]:
                all_teams.add(team)

            v = result["venue"]
            venue_key_str = f"{v['venue_name']}|{v.get('city', '')}"
            if venue_key_str not in all_venues:
                all_venues[venue_key_str] = v

            d = result["date_info"]
            date_str = str(d["full_date"])
            if date_str not in all_dates:
                all_dates[date_str] = d

            files_processed += 1

        except Exception as e:
            files_failed += 1
            errors.append(f"Error in {file_path.name}: {str(e)}")
            logger.error(f"Transform failed for {file_path.name}: {e}")

    df_matches = pd.DataFrame(all_matches) if all_matches else pd.DataFrame()
    df_match_summaries = (
        pd.DataFrame(all_match_summaries) if all_match_summaries else pd.DataFrame()
    )
    df_innings = pd.DataFrame(all_innings) if all_innings else pd.DataFrame()
    df_deliveries = pd.DataFrame(all_deliveries) if all_deliveries else pd.DataFrame()
    df_players = (
        pd.DataFrame(list(all_players.values())) if all_players else pd.DataFrame()
    )

    teams_data = []
    for team in sorted(all_teams):
        teams_data.append(
            {
                "team_name": team,
                "team_short_name": get_team_short_name(team),
                "franchise_group": get_franchise_group(team),
                "is_active": True,
            }
        )
    df_teams = pd.DataFrame(teams_data) if teams_data else pd.DataFrame()

    df_venues = (
        pd.DataFrame(list(all_venues.values())) if all_venues else pd.DataFrame()
    )

    df_dates = pd.DataFrame(list(all_dates.values())) if all_dates else pd.DataFrame()

    logger.info(
        f"Transformation complete: {files_processed} processed, {files_failed} failed. "
        f"Deliveries: {len(df_deliveries)}, Players: {len(df_players)}, "
        f"Teams: {len(df_teams)}, Venues: {len(df_venues)}"
    )

    result = TransformResult(
        df_matches=df_matches,
        df_innings=df_innings,
        df_deliveries=df_deliveries,
        df_players=df_players,
        df_teams=df_teams,
        df_venues=df_venues,
        df_dates=df_dates,
        files_processed=files_processed,
        files_failed=files_failed,
        errors=errors,
    )

    result.df_match_summaries = df_match_summaries

    return result
