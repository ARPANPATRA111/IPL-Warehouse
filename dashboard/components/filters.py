import streamlit as st

from dashboard.utils.db import get_players, get_seasons, get_teams, get_venues

def season_filter(key: str = "season") -> list[str]:
    seasons = get_seasons()
    return st.multiselect("Season(s)", options=seasons, default=[], key=key)

def team_filter(key: str = "team", label: str = "Team") -> list[str]:
    teams = get_teams()
    return st.multiselect(label, options=teams, default=[], key=key)

def single_team_filter(key: str = "single_team", label: str = "Select Team") -> str:
    teams = get_teams()
    if not teams:
        return ""
    return st.selectbox(label, options=teams, key=key)

def player_filter(key: str = "player", label: str = "Player") -> str:
    search = st.text_input(f"Search {label}", key=f"{key}_search")
    players = get_players(search)
    if not players:
        return ""
    return st.selectbox(label, options=players, key=key)

def venue_filter(key: str = "venue") -> list[str]:
    venues = get_venues()
    return st.multiselect("Venue(s)", options=venues, default=[], key=key)

def build_where_clause(
    seasons: list[str] = None,
    teams: list[str] = None,
    venues: list[str] = None,
    table_alias: str = "",
) -> tuple[str, dict]:
    conditions: list[str] = []
    params: dict = {}
    prefix = f"{table_alias}." if table_alias else ""

    if seasons:
        conditions.append(f"{prefix}season IN :seasons")
        params["seasons"] = tuple(seasons)

    if teams:
        conditions.append(
            f"({prefix}team1_key IN (SELECT team_key FROM dim_team WHERE team_name IN :teams) "
            f"OR {prefix}team2_key IN (SELECT team_key FROM dim_team WHERE team_name IN :teams))"
        )
        params["teams"] = tuple(teams)

    if venues:
        conditions.append(
            f"{prefix}venue_key IN (SELECT venue_key FROM dim_venue WHERE venue_name IN :venues)"
        )
        params["venues"] = tuple(venues)

    where = " AND ".join(conditions) if conditions else "TRUE"
    return where, params
