from __future__ import annotations

import json
import re
from dataclasses import dataclass
from textwrap import dedent
from time import perf_counter
from typing import Any

import requests

from api.db import run_query
from api.queries import get_reference_options, resolve_player_name
from config.settings import get_settings

ALLOWED_TABLES = {
    "dim_date",
    "dim_innings",
    "dim_match",
    "dim_player",
    "dim_team",
    "dim_venue",
    "fact_deliveries",
    "fact_match_summary",
}

FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|call|copy|vacuum|analyze|comment|execute)\b",
    re.IGNORECASE,
)
CTE_PATTERN = re.compile(r"(?:with|,)\s*([a-zA-Z_][\w]*)\s+as\s*\(", re.IGNORECASE)
TABLE_PATTERN = re.compile(
    r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)(?:\s+[a-zA-Z_][\w]*)?", re.IGNORECASE
)
JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
SQL_CODE_BLOCK_PATTERN = re.compile(
    r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE
)
SQL_STATEMENT_PATTERN = re.compile(r"\b(?:with|select)\b[\s\S]*", re.IGNORECASE)
SEASON_LITERAL_PATTERN = re.compile(
    r"(?P<column>\b[a-zA-Z_][\w.]*season\b)\s*(?P<operator>=|!=|<>|>=|<=|>|<)\s*(?P<value>\d{4})\b",
    re.IGNORECASE,
)
SEASON_IN_PATTERN = re.compile(
    r"(?P<column>\b[a-zA-Z_][\w.]*season\b)\s+IN\s*\((?P<values>[^\)]*)\)",
    re.IGNORECASE,
)
BOOLEAN_COUNT_PATTERN = re.compile(
    r"COUNT\(\s*(?P<distinct>DISTINCT\s+)?(?P<expression>(?:[a-zA-Z_][\w]*\.)?(?P<column>is_boundary_four|is_boundary_six|is_dot_ball|is_wicket|is_legal_delivery|is_super_over|is_powerplay))\s*\)",
    re.IGNORECASE,
)
TABLE_ALIAS_PATTERN = re.compile(
    r"\b(?P<keyword>from|join)\s+(?P<table>[a-zA-Z_][\w.]*)(?P<spacing>\s+(?:as\s+)?)?(?P<alias>[a-zA-Z_][\w]*)\b",
    re.IGNORECASE,
)
PLAYER_NAME_FILTER_PATTERN = re.compile(
    r"(?P<column>\b[a-zA-Z_][\w.]*player_name\b)\s*(?P<operator>=|ILIKE|LIKE)\s*'(?P<value>[^']+)'",
    re.IGNORECASE,
)
PLAYER_NAME_CANDIDATE_PATTERN = re.compile(
    r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:'s)?"
)

SQL_CLAUSE_KEYWORDS = {
    "where",
    "group",
    "order",
    "limit",
    "offset",
    "having",
    "union",
    "except",
    "intersect",
    "window",
    "qualify",
    "join",
    "left",
    "right",
    "full",
    "inner",
    "cross",
    "on",
}

RESERVED_ALIAS_REWRITES = {
    "all": "all_alias",
    "any": "any_alias",
    "as": "as_alias",
    "do": "do_alias",
    "end": "end_alias",
    "from": "from_alias",
    "group": "group_alias",
    "join": "join_alias",
    "limit": "limit_alias",
    "not": "not_alias",
    "on": "on_alias",
    "or": "or_alias",
    "order": "order_alias",
    "select": "select_alias",
    "then": "then_alias",
    "to": "to_alias",
    "union": "union_alias",
    "where": "where_alias",
    "with": "with_alias",
}

SCHEMA_CONTEXT = dedent("""
    You are generating SQL for an IPL cricket analytics warehouse in PostgreSQL.

    Source coverage confirmed from the raw IPL JSON corpus:
    - 1,193 match files are present.
    - Every file contains event metadata, toss, outcome, venue, players, registry, season, match type, and officials.
    - Innings almost always contain overs and powerplays, and chase innings usually include target information.
    - Delivery run objects consistently carry batter runs, extras, and total runs; non_boundary appears only rarely.
    - Only use fields that are already materialized into the warehouse tables below. Do not reference raw-only fields like officials.

    Warehouse grain map and when to use each table:
    - fact_deliveries is delivery grain. Use it for batting runs, boundaries, dot balls, wickets, over-phase splits, powerplay analysis, and ball-level bowling metrics.
    - dim_innings is innings grain. Use it for innings totals, targets, super overs, and batting-vs-bowling team context at innings level.
    - fact_match_summary is match grain. Use it for toss, winner, result, win margin, DLS, player of match, and first-versus-second innings totals.
    - dim_date, dim_team, dim_player, dim_venue, and dim_match provide readable filters and labels.

    Core tables:
    - fact_deliveries: one row per delivery. Key columns: match_key, date_key, venue_key, batting_team_key, bowling_team_key, batsman_key, non_striker_key, bowler_key, innings_number, over_number, ball_number, legal_ball_number, runs_batsman, runs_extras, runs_total, is_boundary_four, is_boundary_six, is_dot_ball, extras_type, extras_runs, is_wicket, dismissal_type, dismissed_player_key, is_wide, is_noball, is_legal_delivery, is_super_over, is_powerplay, cumulative_runs, cumulative_wickets.
    - fact_match_summary: one row per match. Key columns: match_key, date_key, venue_key, team1_key, team2_key, toss_winner_key, toss_decision, match_winner_key, win_type, win_margin, is_dls, result, player_of_match_key, team1_score, team1_wickets, team1_overs, team2_score, team2_wickets, team2_overs, total_fours, total_sixes, total_extras, season, match_number.
    - dim_player: player_key, player_id, player_name, total_matches, is_active.
    - dim_team: team_key, team_name, team_short_name, franchise_group, is_active.
    - dim_venue: venue_key, venue_name, city, country.
    - dim_date: date_key, full_date, day_name, month_name, quarter, year, season, is_weekend, phase_of_tournament.
    - dim_match: match_key, match_id, season, match_number, match_type, gender, balls_per_over, overs_per_side.
    - dim_innings: innings_key, match_key, innings_number, batting_team_key, bowling_team_key, total_runs, total_wickets, total_overs, total_extras, is_super_over, target_runs, target_overs.

    Canonical joins:
    - fact_deliveries.batsman_key / bowler_key / dismissed_player_key -> dim_player.player_key
    - fact_deliveries.batting_team_key / bowling_team_key -> dim_team.team_key
    - fact_deliveries.date_key -> dim_date.date_key
    - fact_deliveries.venue_key -> dim_venue.venue_key
    - fact_deliveries.match_key -> dim_match.match_key
    - fact_match_summary.team1_key / team2_key / toss_winner_key / match_winner_key -> dim_team.team_key
    - fact_match_summary.player_of_match_key -> dim_player.player_key
    - fact_match_summary.match_key -> dim_match.match_key when you need match metadata beside match outcomes
    - dim_innings.match_key -> dim_match.match_key and dim_innings.batting_team_key / bowling_team_key -> dim_team.team_key

    Semantic groups and reusable metric recipes:
    - Batting output: SUM(runs_batsman) for runs, SUM(CASE WHEN is_boundary_four THEN 1 ELSE 0 END) for fours, SUM(CASE WHEN is_boundary_six THEN 1 ELSE 0 END) for sixes.
    - Strike rate: 100 * SUM(runs_batsman) / NULLIF(SUM(CASE WHEN is_legal_delivery THEN 1 ELSE 0 END), 0).
    - Bowling wickets credited to bowlers: SUM(CASE WHEN is_wicket AND COALESCE(dismissal_type, '') NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field') THEN 1 ELSE 0 END).
    - Economy rate: 6 * SUM(runs_total) / NULLIF(SUM(CASE WHEN is_legal_delivery THEN 1 ELSE 0 END), 0).
    - Dot-ball pressure: SUM(CASE WHEN is_dot_ball THEN 1 ELSE 0 END) and divide by legal balls for percentage if needed.
    - Chase success usually starts from fact_match_summary and compares team2_score, team1_score, result, and match_winner_key.
    - Powerplay questions use fact_deliveries.is_powerplay. Death overs usually mean over_number >= 16 unless the question says otherwise.
    - First innings / second innings scoring can come from dim_innings or from team1_score and team2_score in fact_match_summary depending on the requested grain.

    Planning rules for complex questions:
    - Choose the correct grain first: delivery, innings, or match. Do not mix grains unless the join is necessary.
    - Prefer fact_match_summary for toss, result, player_of_match, win margin, or winner conversion questions.
    - Prefer fact_deliveries for player scoring, over phases, bowling spells, venue boundary behavior, and partnership-style aggregates.
    - Prefer dim_date for season, year, quarter, weekend, and phase_of_tournament filters.
    - Use CTEs for multi-step logic like toss-winner conversion, defended totals, venue splits, or head-to-head seasonal breakdowns.
    - Prefer joins to dimensions so output columns are human-readable.

    Business rules:
    - Use only read-only SQL.
    - Use PostgreSQL syntax.
    - Prefer season from dim_date or fact_match_summary.season depending on the query.
    - Exclude super overs unless the question explicitly asks for them.
    - legal_ball_number is a sequence within an over, not a countable metric. To count balls, use SUM(CASE WHEN is_legal_delivery THEN 1 ELSE 0 END).
    - For wickets credited to bowlers, exclude dismissal types like 'run out', 'retired hurt', 'retired out', and 'obstructing the field' unless the question asks for all dismissals.
    - Keep result sets compact and presentation-ready.
    """).strip()

QUERY_EXAMPLES = [
    "Show the top 10 batsmen by total runs with strike rate.",
    "Which venues have the highest average first innings score?",
    "Compare Mumbai Indians and Chennai Super Kings head-to-head by season.",
    "Find the bowlers with the best economy rate in death overs.",
    "Show yearly run trends and sixes across IPL seasons.",
    "Who hit the most sixes in IPL season 2024?",
    "Which teams most often win after losing the toss by season?",
    "Show powerplay run rate and wickets lost by team in season 2024.",
    "Which venues have the highest chase success when the target is above 180?",
    "List player of the match leaders for each season with their teams.",
]


@dataclass
class GeneratedQuery:

    title: str
    explanation: str
    sql: str


def get_query_engine_context() -> dict[str, Any]:
    return {
        "schema_summary": f"{SCHEMA_CONTEXT}\n\nLoaded warehouse context:\n{_get_available_filters_summary()}",
        "examples": QUERY_EXAMPLES,
        "row_limit": get_settings().analytics_query_row_limit,
    }


def _get_available_filters_summary() -> str:
    try:
        options = get_reference_options()
    except Exception:
        return "Available warehouse filters could not be loaded at request time."

    seasons = ", ".join(options.get("seasons", [])[:18]) or "unknown"
    teams = ", ".join(options.get("teams", [])[:12]) or "unknown"
    venues = ", ".join(options.get("venues", [])[:10]) or "unknown"
    return (
        f"Available seasons: {seasons}. "
        f"Sample teams: {teams}. "
        f"Sample venues: {venues}."
    )


def _escape_json_control_chars(content: str) -> str:

    repaired: list[str] = []
    in_string = False
    is_escaped = False
    replacements = {
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
        "\b": "\\b",
        "\f": "\\f",
    }

    for char in content:
        if in_string:
            if is_escaped:
                repaired.append(char)
                is_escaped = False
                continue

            if char == "\\":
                repaired.append(char)
                is_escaped = True
                continue

            if char == '"':
                repaired.append(char)
                in_string = False
                continue

            if char in replacements:
                repaired.append(replacements[char])
                continue

            repaired.append(char)
            continue

        if char == '"':
            in_string = True

        repaired.append(char)

    return "".join(repaired)


def _extract_json_payload(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()

    candidates = [content]
    match = JSON_BLOCK_PATTERN.search(content)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired_candidate = _escape_json_control_chars(candidate)
            try:
                return json.loads(repaired_candidate)
            except json.JSONDecodeError:
                continue

    raise ValueError("Groq response did not contain valid JSON")


def _extract_sql_fallback(content: str) -> str | None:

    code_block_match = SQL_CODE_BLOCK_PATTERN.search(content)
    if code_block_match:
        sql_candidate = code_block_match.group(1).strip()
        if sql_candidate:
            return sql_candidate

    statement_match = SQL_STATEMENT_PATTERN.search(content)
    if statement_match:
        return statement_match.group(0).strip()

    return None


def _extract_cte_names(sql: str) -> set[str]:
    return {match.group(1).lower() for match in CTE_PATTERN.finditer(sql)}


def _extract_referenced_tables(sql: str) -> set[str]:
    tables: set[str] = set()
    for match in TABLE_PATTERN.finditer(sql):
        table_name = match.group(1).split(".")[-1].lower()
        tables.add(table_name)
    return tables


def _quote_season_literals(sql: str) -> str:

    def replace_literal(match: re.Match[str]) -> str:
        return f"{match.group('column')} {match.group('operator')} '{match.group('value')}'"

    def replace_in_clause(match: re.Match[str]) -> str:
        values = [value.strip() for value in match.group("values").split(",")]
        if not values or not all(re.fullmatch(r"\d{4}", value) for value in values):
            return match.group(0)
        quoted_values = ", ".join(f"'{value}'" for value in values)
        return f"{match.group('column')} IN ({quoted_values})"

    normalized = SEASON_LITERAL_PATTERN.sub(replace_literal, sql)
    return SEASON_IN_PATTERN.sub(replace_in_clause, normalized)


def _rewrite_boolean_counts(sql: str) -> str:

    def replace_count(match: re.Match[str]) -> str:
        if match.group("distinct"):
            return match.group(0)
        expression = match.group("expression")
        return f"SUM(CASE WHEN {expression} THEN 1 ELSE 0 END)"

    return BOOLEAN_COUNT_PATTERN.sub(replace_count, sql)


def _rewrite_reserved_aliases(sql: str) -> str:
    alias_map: dict[str, str] = {}

    def replace_alias(match: re.Match[str]) -> str:
        alias = match.group("alias")
        alias_lower = alias.lower()
        if alias_lower in SQL_CLAUSE_KEYWORDS:
            return match.group(0)

        replacement = RESERVED_ALIAS_REWRITES.get(alias_lower)
        if not replacement:
            return match.group(0)

        alias_map[alias] = replacement
        spacing = match.group("spacing") or " "
        return f"{match.group('keyword')} {match.group('table')}{spacing}{replacement}"

    normalized = TABLE_ALIAS_PATTERN.sub(replace_alias, sql)
    for original_alias, replacement in alias_map.items():
        normalized = re.sub(
            rf"\b{re.escape(original_alias)}\.", f"{replacement}.", normalized
        )

    return normalized


def _rewrite_player_name_filters(sql: str) -> str:
    def replace_player_name_filter(match: re.Match[str]) -> str:
        raw_value = match.group("value")
        normalized_tokens = re.findall(
            r"[a-z0-9]+", raw_value.replace("%", " ").lower()
        )
        if len(normalized_tokens) < 2:
            return match.group(0)

        normalized_full = "".join(normalized_tokens)
        initial_surname = (
            "".join(token[0] for token in normalized_tokens[:-1])
            + normalized_tokens[-1]
        )
        normalized_column = (
            f"regexp_replace(lower({match.group('column')}), '[^a-z0-9]', '', 'g')"
        )
        expressions = [
            f"{match.group('column')} {match.group('operator')} '{raw_value}'",
            f"{normalized_column} = '{normalized_full}'",
        ]

        if initial_surname and initial_surname != normalized_full:
            expressions.append(f"{normalized_column} = '{initial_surname}'")
            expressions.append(f"{normalized_column} LIKE '{initial_surname}%'")

        return "(" + " OR ".join(expressions) + ")"

    return PLAYER_NAME_FILTER_PATTERN.sub(replace_player_name_filter, sql)


def _format_answer_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return str(value)


def _format_answer_column(column: str) -> str:
    return column.replace("_", " ")


def _build_answer_payload(result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not result_rows:
        return {
            "answer_mode": "text",
            "answer_text": "No matching warehouse rows were found for this question.",
            "answer_source": "warehouse",
        }

    first_row = result_rows[0]
    populated_items = [
        (column, value) for column, value in first_row.items() if value is not None
    ]

    if len(result_rows) == 1 and len(populated_items) == 1:
        column, value = populated_items[0]
        return {
            "answer_mode": "scalar",
            "answer_text": f"{_format_answer_column(column).title()}: {_format_answer_value(value)}",
            "answer_source": "warehouse",
        }

    if len(result_rows) == 1 and len(populated_items) <= 4:
        summary = ", ".join(
            f"{_format_answer_column(column)} {_format_answer_value(value)}"
            for column, value in populated_items
        )
        return {
            "answer_mode": "text",
            "answer_text": summary[0].upper() + summary[1:] if summary else None,
            "answer_source": "warehouse",
        }

    if len(result_rows) <= 3 and len(first_row.keys()) <= 4:
        summary_lines = []
        for row in result_rows:
            summary_lines.append(
                ", ".join(
                    f"{_format_answer_column(column)} {_format_answer_value(value)}"
                    for column, value in row.items()
                    if value is not None
                )
            )

        return {
            "answer_mode": "table",
            "answer_text": " | ".join(summary_lines),
            "answer_source": "warehouse",
        }

    return {
        "answer_mode": "table",
        "answer_text": None,
        "answer_source": "warehouse",
    }


def _get_entity_resolution_summary(question: str) -> str:
    hints: list[str] = []
    seen_candidates: set[str] = set()

    for match in PLAYER_NAME_CANDIDATE_PATTERN.finditer(question):
        candidate = match.group("name")
        candidate_key = candidate.lower()
        if candidate_key in seen_candidates:
            continue

        seen_candidates.add(candidate_key)
        try:
            resolved_player = resolve_player_name(candidate)
        except Exception:
            resolved_player = None

        if resolved_player and resolved_player.lower() != candidate.lower():
            hints.append(
                f'Player hint: "{candidate}" appears as "{resolved_player}" in dim_player.'
            )

    if not hints:
        return "No extra entity hints were resolved."

    return "\n".join(f"- {hint}" for hint in hints)


def _normalize_sql(sql: str) -> str:
    repaired = _quote_season_literals(sql)
    repaired = _rewrite_boolean_counts(repaired)
    repaired = _rewrite_reserved_aliases(repaired)
    repaired = _rewrite_player_name_filters(repaired)
    return repaired


def validate_read_only_sql(sql: str) -> str:
    normalized = sql.strip().rstrip(";")
    if not normalized:
        raise ValueError("Generated SQL is empty")
    if ";" in normalized:
        raise ValueError("Only a single SQL statement is allowed")
    if not re.match(r"^(select|with)\b", normalized, flags=re.IGNORECASE):
        raise ValueError("Only SELECT and WITH queries are allowed")
    if FORBIDDEN_SQL_PATTERN.search(normalized):
        raise ValueError("Generated SQL contains a forbidden write/admin statement")

    cte_names = _extract_cte_names(normalized)
    referenced_tables = _extract_referenced_tables(normalized)
    disallowed_tables = referenced_tables - ALLOWED_TABLES - cte_names
    if disallowed_tables:
        raise ValueError(
            f"Generated SQL referenced unsupported tables: {', '.join(sorted(disallowed_tables))}"
        )

    return normalized


def enforce_result_limit(sql: str) -> str:
    row_limit = get_settings().analytics_query_row_limit
    limit_match = re.search(r"\blimit\s+(\d+)\b", sql, flags=re.IGNORECASE)
    if not limit_match:
        return f"{sql}\nLIMIT {row_limit}"

    requested_limit = int(limit_match.group(1))
    if requested_limit <= row_limit:
        return sql

    return re.sub(
        r"\blimit\s+\d+\b",
        f"LIMIT {row_limit}",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )


def _call_groq(messages: list[dict[str, str]]) -> str:
    settings = get_settings()

    response = requests.post(
        settings.groq_api_url,
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.groq_model,
            "temperature": 0.1,
            "messages": messages,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()
    return payload["choices"][0]["message"]["content"]


def _build_generation_messages(question: str) -> list[dict[str, str]]:
    settings = get_settings()
    return [
        {
            "role": "system",
            "content": (
                "You are a senior analytics engineer. Convert the user's IPL data question "
                "into a single safe PostgreSQL read-only query. Return JSON only with keys "
                "title, explanation, and sql. Never use markdown fences or any prose outside JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Schema context:\n{SCHEMA_CONTEXT}\n\n"
                f"Loaded warehouse context:\n{_get_available_filters_summary()}\n\n"
                f"Entity resolution hints:\n{_get_entity_resolution_summary(question)}\n\n"
                f"Examples:\n- " + "\n- ".join(QUERY_EXAMPLES) + "\n\n"
                f"Question: {question}\n\n"
                "Requirements:\n"
                f"- The query must stay within these tables only: {', '.join(sorted(ALLOWED_TABLES))}.\n"
                "- Use clear aliases and readable column names.\n"
                "- Never use reserved SQL keywords like do, order, or group as table aliases.\n"
                "- Warehouse player_name values often use initials plus surname such as V Kohli, RG Sharma, or MS Dhoni. When a question uses a full player name, use broader matching logic instead of strict exact equality.\n"
                "- Exclude super overs unless the question asks for them.\n"
                "- Season columns are stored as text, so compare season values using quoted strings like '2024'.\n"
                "- To count sixes, fours, wickets, legal balls, or other boolean flags, use SUM(CASE WHEN flag THEN 1 ELSE 0 END), never COUNT(boolean_column).\n"
                f"- Keep the output limited to at most {settings.analytics_query_row_limit} rows.\n"
                "- Prefer joins to dimensions so names are human-readable.\n"
            ),
        },
    ]


def _parse_generated_content(content: str, question: str) -> dict[str, Any]:
    try:
        return _extract_json_payload(content)
    except ValueError:
        fallback_sql = _extract_sql_fallback(content)
        if not fallback_sql:
            raise

        return {
            "title": f"Query result for: {question[:80]}",
            "explanation": "The model returned SQL outside the requested JSON envelope, so the response was normalized by the backend.",
            "sql": fallback_sql,
        }


def generate_sql(question: str) -> GeneratedQuery:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    parsed = _parse_generated_content(
        _call_groq(_build_generation_messages(question)), question
    )
    raw_sql = str(parsed.get("sql", ""))
    sql = enforce_result_limit(validate_read_only_sql(_normalize_sql(raw_sql)))
    title = str(parsed.get("title") or "Ad hoc analytics query")
    explanation = str(
        parsed.get("explanation") or "Generated from the supplied question."
    )
    return GeneratedQuery(title=title, explanation=explanation, sql=sql)


def repair_sql(question: str, failed_sql: str, error_message: str) -> GeneratedQuery:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    parsed = _parse_generated_content(
        _call_groq(
            [
                {
                    "role": "system",
                    "content": (
                        "You are repairing a failed PostgreSQL analytics query. Return JSON only with "
                        "title, explanation, and sql. Fix the SQL so it remains read-only and uses only "
                        "the approved warehouse schema."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Schema context:\n{SCHEMA_CONTEXT}\n\n"
                        f"Loaded warehouse context:\n{_get_available_filters_summary()}\n\n"
                        f"Entity resolution hints:\n{_get_entity_resolution_summary(question)}\n\n"
                        f"Original question: {question}\n\n"
                        f"Failed SQL:\n{failed_sql}\n\n"
                        f"Database error:\n{error_message}\n\n"
                        "Repair requirements:\n"
                        "- Keep the answer faithful to the question.\n"
                        "- Keep the SQL read-only.\n"
                        "- Never use reserved SQL keywords like do, order, or group as table aliases.\n"
                        "- Handle warehouse player_name abbreviations like V Kohli, RG Sharma, and MS Dhoni when the question uses a full first name.\n"
                        "- Quote season literals because season columns are stored as text.\n"
                        "- Use SUM(CASE WHEN flag THEN 1 ELSE 0 END) instead of COUNT(boolean_column).\n"
                        f"- Limit the result to at most {settings.analytics_query_row_limit} rows.\n"
                    ),
                },
            ]
        ),
        question,
    )

    raw_sql = str(parsed.get("sql", ""))
    sql = enforce_result_limit(validate_read_only_sql(_normalize_sql(raw_sql)))
    title = str(parsed.get("title") or "Repaired analytics query")
    explanation = str(
        parsed.get("explanation")
        or "The backend repaired the generated SQL after a database execution error."
    )
    return GeneratedQuery(title=title, explanation=explanation, sql=sql)


def answer_analytics_question(question: str) -> dict[str, Any]:
    current_result = generate_sql(question)
    last_error: Exception | None = None

    for repair_attempt in range(2):
        started_at = perf_counter()
        try:
            result_df = run_query(current_result.sql)
            execution_ms = round((perf_counter() - started_at) * 1000, 2)
            result_rows = result_df.to_dict(orient="records")

            if not result_rows and repair_attempt == 0:
                try:
                    current_result = repair_sql(
                        question,
                        current_result.sql,
                        "Query returned zero rows. Handle abbreviated warehouse player names such as V Kohli or RG Sharma and prefer broader player-name matching.",
                    )
                    continue
                except Exception:
                    pass

            answer_payload = _build_answer_payload(result_rows)

            return {
                "title": current_result.title,
                "explanation": current_result.explanation,
                "sql": current_result.sql,
                "columns": result_df.columns.tolist(),
                "rows": result_rows,
                "row_count": int(len(result_df.index)),
                "execution_ms": execution_ms,
                **answer_payload,
            }
        except Exception as error:
            last_error = error
            if repair_attempt == 0:
                try:
                    current_result = repair_sql(
                        question, current_result.sql, str(error)
                    )
                    continue
                except Exception:
                    pass
            break

    raise ValueError(
        f"Generated SQL could not be executed safely: {last_error}"
    ) from last_error
