from datetime import datetime
from threading import Lock, Thread

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.db import run_scalar
from api.queries import (
    get_batting_dashboard,
    get_batting_player_profile,
    get_bowling_dashboard,
    get_bowling_player_profile,
    get_head_to_head,
    get_home_dashboard,
    get_home_leaders,
    get_home_summary,
    get_players,
    get_reference_options,
    get_team_detail,
    get_team_overview,
    get_venue_dashboard,
    warm_analytics_cache,
)
from api.sql_assistant import answer_analytics_question, get_query_engine_context
from config.settings import get_settings

settings = get_settings()
CLOUD_FRONTEND_ORIGIN_REGEX = r"https://([a-z0-9-]+\.)*(netlify\.app|vercel\.app)$"

app = FastAPI(title="IPL Analytics API", version="2.0.0")

_warmup_state: dict[str, object] = {
    "status": "idle",
    "completed_at": None,
    "details": {},
    "error": None,
}
_warmup_lock = Lock()


class AnalyticsQuestionRequest(BaseModel):

    question: str = Field(min_length=5, max_length=500)


def _run_cache_warmup() -> None:
    with _warmup_lock:
        _warmup_state["status"] = "running"
        _warmup_state["error"] = None

    try:
        details = warm_analytics_cache()
        with _warmup_lock:
            _warmup_state["status"] = "ready"
            _warmup_state["completed_at"] = datetime.utcnow()
            _warmup_state["details"] = details
    except Exception as error:
        with _warmup_lock:
            _warmup_state["status"] = "failed"
            _warmup_state["error"] = str(error)


@app.on_event("startup")
def startup_warmup() -> None:
    Thread(target=_run_cache_warmup, daemon=True).start()


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_frontend_origins(),
    allow_origin_regex=CLOUD_FRONTEND_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/readiness")
def readiness() -> dict[str, object]:
    status = "ready"

    try:
        database_ok = bool(run_scalar("SELECT 1", default=0))
        database_check: dict[str, object] = {
            "status": "ok" if database_ok else "failed"
        }
    except Exception as error:
        status = "not_ready"
        database_check = {"status": "failed", "error": str(error)}

    try:
        options = get_reference_options()
        reference_check: dict[str, object] = {
            "status": "ok",
            "seasons": len(options.get("seasons", [])),
            "teams": len(options.get("teams", [])),
            "venues": len(options.get("venues", [])),
        }
    except Exception as error:
        if status == "ready":
            status = "not_ready"
        reference_check = {"status": "failed", "error": str(error)}

    model_check: dict[str, object]
    if settings.groq_api_key:
        model_check = {"status": "ok", "configured": True}
    else:
        if status == "ready":
            status = "degraded"
        model_check = {
            "status": "degraded",
            "configured": False,
            "error": "GROQ_API_KEY is not configured",
        }

    try:
        latest_run = run_scalar(
            "SELECT MAX(completed_at) FROM etl_run_log WHERE status = 'success'",
            default=None,
        )
        latest_file = run_scalar(
            "SELECT MAX(processed_at) FROM etl_file_registry", default=None
        )
        etl_status = "ok" if latest_run or latest_file else "degraded"
        if etl_status != "ok" and status == "ready":
            status = "degraded"
        etl_check: dict[str, object] = {
            "status": etl_status,
            "last_successful_run": latest_run,
            "last_processed_file": latest_file,
        }
    except Exception as error:
        if status == "ready":
            status = "degraded"
        etl_check = {"status": "degraded", "error": str(error)}

    with _warmup_lock:
        cache_check = dict(_warmup_state)

    if cache_check.get("status") == "failed" and status == "ready":
        status = "degraded"

    return {
        "status": status,
        "checks": {
            "database": database_check,
            "reference_data": reference_check,
            "model": model_check,
            "cache_warmup": cache_check,
            "etl_freshness": etl_check,
            "frontend_origins": settings.get_frontend_origins(),
        },
    }


@app.get("/api/reference/options")
def reference_options() -> dict[str, list[str]]:
    return get_reference_options()


@app.get("/api/query-engine/context")
def query_engine_context() -> dict:
    return get_query_engine_context()


@app.post("/api/query-engine")
def query_engine(request: AnalyticsQuestionRequest) -> dict:
    try:
        return answer_analytics_question(request.question)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except requests.HTTPError as error:
        raise HTTPException(status_code=502, detail="Groq request failed") from error


@app.get("/api/players")
def players(search: str = "") -> dict[str, list[str]]:
    return {"items": get_players(search)}


@app.get("/api/home")
def home_dashboard() -> dict:
    return get_home_dashboard()


@app.get("/api/home/summary")
def home_dashboard_summary() -> dict:
    return get_home_summary()


@app.get("/api/home/leaders")
def home_dashboard_leaders() -> dict:
    return get_home_leaders()


@app.get("/api/batting")
def batting_dashboard(seasons: list[str] = Query(default=[])) -> dict:
    return get_batting_dashboard(seasons)


@app.get("/api/batting/profile")
def batting_profile(player: str) -> dict:
    return get_batting_player_profile(player)


@app.get("/api/bowling")
def bowling_dashboard(seasons: list[str] = Query(default=[])) -> dict:
    return get_bowling_dashboard(seasons)


@app.get("/api/bowling/profile")
def bowling_profile(player: str) -> dict:
    return get_bowling_player_profile(player)


@app.get("/api/teams/overview")
def team_overview() -> dict[str, list[dict]]:
    return {"items": get_team_overview()}


@app.get("/api/teams/detail")
def team_detail(team: str, seasons: list[str] = Query(default=[])) -> dict:
    if not team:
        raise HTTPException(status_code=400, detail="team is required")
    return get_team_detail(team, seasons)


@app.get("/api/venues")
def venue_dashboard(
    seasons: list[str] = Query(default=[]),
    venues: list[str] = Query(default=[]),
) -> dict:
    return get_venue_dashboard(seasons, venues)


@app.get("/api/head-to-head")
def head_to_head(
    team1: str,
    team2: str,
    seasons: list[str] = Query(default=[]),
) -> dict:
    if not team1 or not team2:
        raise HTTPException(status_code=400, detail="team1 and team2 are required")
    if team1 == team2:
        raise HTTPException(status_code=400, detail="team1 and team2 must differ")
    return get_head_to_head(team1, team2, seasons)
