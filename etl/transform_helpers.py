from datetime import date, datetime
from typing import Optional

from config.logging_config import get_logger

logger = get_logger("transform_helpers")


TEAM_NAME_MAPPING: dict[str, str] = {
    "Delhi Daredevils": "Delhi Capitals",
    "Deccan Chargers": "Sunrisers Hyderabad",
    "Kings XI Punjab": "Punjab Kings",
    "Rising Pune Supergiant": "Rising Pune Supergiants",
    "Rising Pune Supergiants": "Rising Pune Supergiants",
    "Pune Warriors": "Pune Warriors India",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
}


TEAM_SHORT_NAMES: dict[str, str] = {
    "Mumbai Indians": "MI",
    "Chennai Super Kings": "CSK",
    "Royal Challengers Bengaluru": "RCB",
    "Royal Challengers Bangalore": "RCB",
    "Kolkata Knight Riders": "KKR",
    "Delhi Capitals": "DC",
    "Delhi Daredevils": "DC",
    "Punjab Kings": "PBKS",
    "Kings XI Punjab": "PBKS",
    "Rajasthan Royals": "RR",
    "Sunrisers Hyderabad": "SRH",
    "Deccan Chargers": "SRH",
    "Gujarat Titans": "GT",
    "Lucknow Super Giants": "LSG",
    "Rising Pune Supergiants": "RPS",
    "Rising Pune Supergiant": "RPS",
    "Pune Warriors India": "PWI",
    "Pune Warriors": "PWI",
    "Kochi Tuskers Kerala": "KTK",
    "Gujarat Lions": "GL",
}


FRANCHISE_GROUPS: dict[str, str] = {
    "Mumbai Indians": "Mumbai Indians",
    "Chennai Super Kings": "Chennai Super Kings",
    "Royal Challengers Bengaluru": "Royal Challengers",
    "Royal Challengers Bangalore": "Royal Challengers",
    "Kolkata Knight Riders": "Kolkata Knight Riders",
    "Delhi Capitals": "Delhi Franchise",
    "Delhi Daredevils": "Delhi Franchise",
    "Punjab Kings": "Punjab Franchise",
    "Kings XI Punjab": "Punjab Franchise",
    "Rajasthan Royals": "Rajasthan Royals",
    "Sunrisers Hyderabad": "Hyderabad Franchise",
    "Deccan Chargers": "Hyderabad Franchise",
    "Gujarat Titans": "Gujarat Titans",
    "Lucknow Super Giants": "Lucknow Super Giants",
    "Rising Pune Supergiants": "Rising Pune Supergiants",
    "Rising Pune Supergiant": "Rising Pune Supergiants",
    "Pune Warriors India": "Pune Warriors India",
    "Pune Warriors": "Pune Warriors India",
    "Kochi Tuskers Kerala": "Kochi Tuskers Kerala",
    "Gujarat Lions": "Gujarat Lions",
}


def normalize_team_name(team_name: str) -> str:
    return TEAM_NAME_MAPPING.get(team_name, team_name)


def get_team_short_name(team_name: str) -> Optional[str]:
    if team_name in TEAM_SHORT_NAMES:
        return TEAM_SHORT_NAMES[team_name]

    initials = "".join(
        part[0] for part in team_name.split() if part and part[0].isalnum()
    ).upper()
    return initials or team_name[:3].upper()


def get_franchise_group(team_name: str) -> Optional[str]:
    return FRANCHISE_GROUPS.get(team_name)


def parse_season(season_value: object) -> str:
    if season_value is None:
        return ""
    return str(season_value)


def parse_match_date(dates: list[str]) -> date:
    if not dates:
        return date.min
    return datetime.strptime(dates[0], "%Y-%m-%d").date()


def generate_date_attributes(match_date: date, season: str) -> dict:
    return {
        "full_date": match_date,
        "day_of_week": match_date.weekday(),
        "day_name": match_date.strftime("%A"),
        "day_of_month": match_date.day,
        "week_of_year": int(match_date.strftime("%W")),
        "month_number": match_date.month,
        "month_name": match_date.strftime("%B"),
        "quarter": (match_date.month - 1) // 3 + 1,
        "year": match_date.year,
        "season": season,
        "is_weekend": match_date.weekday() >= 5,
        "is_playoff": False,
        "phase_of_tournament": "League",
    }


def determine_phase(
    match_number: Optional[int], total_matches_in_season: int = 74
) -> str:
    if match_number is None:
        return "League"
    if match_number >= total_matches_in_season:
        return "Final"
    elif match_number >= total_matches_in_season - 3:
        return "Playoff"
    return "League"


def compute_overs_decimal(legal_balls: int) -> float:
    complete_overs = legal_balls // 6
    remaining_balls = legal_balls % 6
    return float(f"{complete_overs}.{remaining_balls}")


def extract_win_info(
    outcome: dict,
) -> tuple[Optional[str], Optional[str], Optional[int], bool, str]:
    winner = outcome.get("winner")
    is_dls = "method" in outcome
    result = "normal"

    if winner:
        by = outcome.get("by", {})
        if "runs" in by:
            win_type = "runs"
            win_margin = by["runs"]
        elif "wickets" in by:
            win_type = "wickets"
            win_margin = by["wickets"]
        else:
            win_type = None
            win_margin = None
    else:
        win_type = None
        win_margin = None
        res = outcome.get("result", "")
        if res == "tie":
            result = "tie"
        elif res == "no result":
            result = "no result"
        else:
            result = res if res else "no result"

    return winner, win_type, win_margin, is_dls, result
