import streamlit as st

st.set_page_config(page_title="Batting Analysis - IPL", page_icon="🏏", layout="wide")

from dashboard.components.charts import bar_chart, line_chart, scatter_chart
from dashboard.components.filters import player_filter, season_filter
from dashboard.utils.db import run_query

st.title("Batting Analysis")
st.markdown("---")


with st.sidebar:
    st.header("Filters")
    selected_seasons = season_filter(key="bat_season")
    selected_player = player_filter(key="bat_player", label="Batsman")

season_clause = ""
if selected_seasons:
    seasons_str = ",".join(f"'{s}'" for s in selected_seasons)
    season_clause = f"AND dm.season IN ({seasons_str})"


st.header("Batting Leaderboard")
query = f"""
    SELECT dp.player_name,
        SUM(fd.runs_batsman) as total_runs,
        COUNT(DISTINCT fd.match_key) as innings,
        SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) as fours,
        SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes,
        ROUND(SUM(fd.runs_batsman)::numeric * 100 /
            NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0), 2) as strike_rate,
        ROUND(SUM(fd.runs_batsman)::numeric /
            NULLIF(COUNT(DISTINCT fd.match_key), 0), 2) as avg_per_match
    FROM fact_deliveries fd
    JOIN dim_player dp ON fd.batsman_key = dp.player_key
    JOIN dim_match dm ON fd.match_key = dm.match_key
    WHERE fd.is_wide = FALSE {season_clause}
    GROUP BY dp.player_name
    HAVING SUM(fd.runs_batsman) > 100
    ORDER BY total_runs DESC
    LIMIT 25
"""

try:
    df = run_query(query)
    if not df.empty:
        fig = bar_chart(df.head(15), "player_name", "total_runs", "Top Run Scorers")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No data available for selected filters")
except Exception as e:
    st.error(f"Error: {e}")


st.header("Strike Rate vs Total Runs")
try:
    if not df.empty:
        fig = scatter_chart(
            df, "total_runs", "strike_rate",
            "Strike Rate vs Runs (size = sixes)",
            size="sixes",
        )
        st.plotly_chart(fig, use_container_width=True)
except Exception:
    pass


if selected_player:
    st.markdown("---")
    st.header(f"Player Profile: {selected_player}")

    player_query = f"""
        SELECT dm.season,
            SUM(fd.runs_batsman) as runs,
            COUNT(DISTINCT fd.match_key) as matches,
            SUM(CASE WHEN fd.is_boundary_four THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes,
            ROUND(SUM(fd.runs_batsman)::numeric * 100 /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0), 2) as sr
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.batsman_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE dp.player_name = :player AND fd.is_wide = FALSE
        GROUP BY dm.season
        ORDER BY dm.season
    """
    try:
        player_df = run_query(player_query, {"player": selected_player})
        if not player_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = bar_chart(player_df, "season", "runs", f"{selected_player} - Runs per Season")
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = line_chart(player_df, "season", "sr", f"{selected_player} - Strike Rate Trend")
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(player_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error loading player data: {e}")
