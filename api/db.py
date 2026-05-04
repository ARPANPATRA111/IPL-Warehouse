import json
from collections.abc import Iterable
from functools import lru_cache
from socket import AF_INET, SOCK_STREAM, getaddrinfo
from typing import Any, Optional

import pandas as pd
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool

from config.settings import get_settings


def _resolve_serverless_database_url(database_url: str) -> str:
    settings = get_settings()
    if not settings.is_serverless_runtime():
        return database_url

    parsed_url = make_url(database_url)
    hostname = parsed_url.host
    if (
        not hostname
        or not hostname.endswith(".supabase.co")
        or parsed_url.query.get("hostaddr")
    ):
        return database_url

    try:
        address_info = getaddrinfo(
            hostname, parsed_url.port or 5432, AF_INET, SOCK_STREAM
        )
    except OSError:
        return database_url

    ipv4_host = next((entry[4][0] for entry in address_info if entry[4]), None)
    if not ipv4_host:
        return database_url

    updated_query = dict(parsed_url.query)
    updated_query["hostaddr"] = ipv4_host
    return parsed_url.set(query=updated_query).render_as_string(hide_password=False)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine_kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
    }

    if settings.is_serverless_runtime():
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10

    return create_engine(
        _resolve_serverless_database_url(settings.database_url), **engine_kwargs
    )


def run_query(
    query: str,
    params: Optional[dict[str, Any]] = None,
    expanding: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    statement = text(query)
    for param_name in expanding or []:
        statement = statement.bindparams(bindparam(param_name, expanding=True))

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(statement, params or {})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def run_records(
    query: str,
    params: Optional[dict[str, Any]] = None,
    expanding: Optional[Iterable[str]] = None,
) -> list[dict[str, Any]]:
    df = run_query(query, params=params, expanding=expanding)
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def run_scalar(
    query: str,
    params: Optional[dict[str, Any]] = None,
    expanding: Optional[Iterable[str]] = None,
    default: Any = None,
) -> Any:
    df = run_query(query, params=params, expanding=expanding)
    if df.empty:
        return default
    return df.iloc[0, 0]
