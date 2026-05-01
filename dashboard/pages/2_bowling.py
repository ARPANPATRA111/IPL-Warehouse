import streamlit as st

st.set_page_config(page_title="Bowling Analysis - IPL", page_icon="🏏", layout="wide")

from dashboard.components.charts import bar_chart, line_chart, scatter_chart
from dashboard.components.filters import player_filter, season_filter
from dashboard.utils.db import run_query

st.title("Bowling Analysis")
st.markdown("---")


with st.sidebar:
    st.header("Filters")
    selected_seasons = season_filter(key="bowl_season")
    selected_player = player_filter(key="bowl_player", label="Bowler")

season_clause = ""
if selected_seasons:
    seasons_str = ",".join(f"'{s}'" for s in selected_seasons)
    season_clause = f"AND dm.season IN ({seasons_str})"


st.header("Bowling Leaderboard")
query = f"""
    SELECT dp.player_name,
        SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as wickets,
        COUNT(DISTINCT fd.match_key) as matches,
        ROUND(SUM(fd.runs_total)::numeric /
            NULLIF(SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END), 0), 2) as avg,
        ROUND(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END)::numeric /
            NULLIF(SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END), 0), 1) as strike_rate,
        ROUND(SUM(fd.runs_total)::numeric * 6 /
            NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0), 2) as economy,
        SUM(CASE WHEN fd.is_dot_ball THEN 1 ELSE 0 END) as dot_balls
    FROM fact_deliveries fd
    JOIN dim_player dp ON fd.bowler_key = dp.player_key
    JOIN dim_match dm ON fd.match_key = dm.match_key
    WHERE 1=1 {season_clause}
    GROUP BY dp.player_name
    HAVING SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) > 5
    ORDER BY wickets DESC
    LIMIT 25
"""

try:
    df = run_query(query)
    if not df.empty:
        fig = bar_chart(df.head(15), "player_name", "wickets", "Top Wicket Takers")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No data for selected filters")
except Exception as e:
    st.error(f"Error: {e}")


st.header("Economy vs Wickets")
try:
    if not df.empty:
        fig = scatter_chart(
            df, "wickets", "economy",
            "Economy Rate vs Wickets (size = dot balls)",
            size="dot_balls",
        )
        st.plotly_chart(fig, use_container_width=True)
except Exception:
    pass


if selected_player:
    st.markdown("---")
    st.header(f"Bowler Profile: {selected_player}")

    bowler_query = f"""
        SELECT dm.season,
            SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as wickets,
            COUNT(DISTINCT fd.match_key) as matches,
            ROUND(SUM(fd.runs_total)::numeric * 6 /
                NULLIF(SUM(CASE WHEN fd.is_legal_delivery THEN 1 ELSE 0 END), 0), 2) as economy,
            SUM(CASE WHEN fd.is_dot_ball THEN 1 ELSE 0 END) as dots
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.bowler_key = dp.player_key
        JOIN dim_match dm ON fd.match_key = dm.match_key
        WHERE dp.player_name = :player
        GROUP BY dm.season
        ORDER BY dm.season
    """
    try:
        bowler_df = run_query(bowler_query, {"player": selected_player})
        if not bowler_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = bar_chart(bowler_df, "season", "wickets", f"{selected_player} - Wickets per Season")
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = line_chart(bowler_df, "season", "economy", f"{selected_player} - Economy Trend")
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(bowler_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error: {e}")
