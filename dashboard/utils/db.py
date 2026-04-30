from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import get_settings

@st.cache_resource
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_size=5, max_overflow=10)

def run_query(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return pd.DataFrame(result.fetchall(), columns=result.keys())

@st.cache_data(ttl=300)
def cached_query(query: str, params: Optional[tuple] = None) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        if params:
            result = conn.execute(text(query), dict(enumerate(params)))
        else:
            result = conn.execute(text(query))
        return pd.DataFrame(result.fetchall(), columns=result.keys())

def get_seasons() -> list[str]:
    df = run_query("SELECT DISTINCT season FROM dim_match ORDER BY season DESC")
    return df["season"].tolist() if not df.empty else []

def get_teams() -> list[str]:
    df = run_query("SELECT team_name FROM dim_team WHERE is_active = TRUE ORDER BY team_name")
    return df["team_name"].tolist() if not df.empty else []

def get_players(search: str = "") -> list[str]:
    if search:
        df = run_query(
            "SELECT player_name FROM dim_player WHERE player_name ILIKE :search ORDER BY player_name LIMIT 50",
            {"search": f"%{search}%"},
        )
    else:
        df = run_query("SELECT player_name FROM dim_player ORDER BY total_matches DESC LIMIT 100")
    return df["player_name"].tolist() if not df.empty else []

def get_venues() -> list[str]:
    df = run_query("SELECT venue_name FROM dim_venue ORDER BY venue_name")
    return df["venue_name"].tolist() if not df.empty else []
