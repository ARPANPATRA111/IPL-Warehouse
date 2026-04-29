from unittest.mock import patch

import pandas as pd

from api.sql_assistant import GeneratedQuery, _normalize_sql, answer_analytics_question, get_query_engine_context

def test_normalize_sql_quotes_seasons_and_rewrites_boolean_counts():
    sql = (
        "SELECT COUNT(fd.is_boundary_six) AS total_sixes "
        "FROM fact_deliveries fd "
        "JOIN dim_date dd ON fd.date_key = dd.date_key "
        "WHERE dd.season = 2026 AND dd.season IN (2024, 2025)"
    )

    normalized = _normalize_sql(sql)

    assert "SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END)" in normalized
    assert "dd.season = '2026'" in normalized
    assert "dd.season IN ('2024', '2025')" in normalized

def test_normalize_sql_rewrites_reserved_aliases():
    sql = (
        "WITH death_overs AS ( "
        "SELECT fd.bowler_key, SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END) AS total_balls "
        "FROM fact_deliveries fd GROUP BY fd.bowler_key "
        "), bowler_economy AS ( "
        "SELECT dp.player_name, do.total_balls "
        "FROM death_overs do JOIN dim_player dp ON do.bowler_key = dp.player_key "
        ") SELECT * FROM bowler_economy"
    )

    normalized = _normalize_sql(sql)

    assert "FROM death_overs do_alias JOIN dim_player dp ON do_alias.bowler_key = dp.player_key" in normalized
    assert "SELECT dp.player_name, do_alias.total_balls" in normalized

def test_normalize_sql_rewrites_player_name_filters_for_abbreviated_warehouse_names():
    sql = "SELECT dp.player_name FROM dim_player dp WHERE dp.player_name = 'Virat Kohli'"

    normalized = _normalize_sql(sql)

    assert "regexp_replace(lower(dp.player_name), '[^a-z0-9]', '', 'g') = 'viratkohli'" in normalized
    assert "regexp_replace(lower(dp.player_name), '[^a-z0-9]', '', 'g') = 'vkohli'" in normalized

@patch("api.sql_assistant.get_reference_options")
def test_query_engine_context_includes_semantic_schema_groups(mock_get_reference_options):
    mock_get_reference_options.return_value = {
        "seasons": ["2024", "2025"],
        "teams": ["Mumbai Indians", "Chennai Super Kings"],
        "venues": ["Wankhede Stadium"],
    }

    context = get_query_engine_context()

    assert "Warehouse grain map and when to use each table" in context["schema_summary"]
    assert "Source coverage confirmed from the raw IPL JSON corpus" in context["schema_summary"]
    assert "Available seasons: 2024, 2025." in context["schema_summary"]
    assert "Which teams most often win after losing the toss by season?" in context["examples"]

@patch("api.sql_assistant.repair_sql")
@patch("api.sql_assistant.generate_sql")
@patch("api.sql_assistant.run_query")
def test_answer_analytics_question_repairs_failed_sql(mock_run_query, mock_generate_sql, mock_repair_sql):
    mock_generate_sql.return_value = GeneratedQuery(
        title="Initial result",
        explanation="Initial explanation",
        sql="SELECT COUNT(fd.is_boundary_six) AS total_sixes FROM fact_deliveries fd",
    )
    mock_repair_sql.return_value = GeneratedQuery(
        title="Repaired result",
        explanation="Repaired explanation",
        sql="SELECT SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) AS total_sixes FROM fact_deliveries fd",
    )
    mock_run_query.side_effect = [
        Exception("operator does not exist: character varying = integer"),
        pd.DataFrame([{"player_name": "V Kohli", "total_sixes": 12}]),
    ]

    result = answer_analytics_question("Who hit the most sixes in IPL season 2026?")

    assert result["title"] == "Repaired result"
    assert result["row_count"] == 1
    assert result["sql"] == mock_repair_sql.return_value.sql

@patch("api.sql_assistant.generate_sql")
@patch("api.sql_assistant.run_query")
def test_answer_analytics_question_returns_scalar_answer_payload(mock_run_query, mock_generate_sql):
    mock_generate_sql.return_value = GeneratedQuery(
        title="Virat total",
        explanation="Single value answer.",
        sql="SELECT 113 AS highest_score",
    )
    mock_run_query.return_value = pd.DataFrame([{"highest_score": 113}])

    result = answer_analytics_question("What is the highest score for Virat Kohli this season?")

    assert result["answer_mode"] == "scalar"
    assert result["answer_source"] == "warehouse"
    assert "113" in result["answer_text"]
