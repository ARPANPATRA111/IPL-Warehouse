import streamlit as st

st.set_page_config(page_title="Team Performance - IPL", page_icon="🏏", layout="wide")

from dashboard.components.charts import bar_chart, line_chart, pie_chart
from dashboard.components.filters import season_filter, single_team_filter
from dashboard.components.metrics import get_team_performance
from dashboard.utils.db import run_query

st.title("Team Performance")
st.markdown("---")


with st.sidebar:
    st.header("Filters")
    selected_seasons = season_filter(key="team_season")
    selected_team = single_team_filter(key="team_select")


st.header("Team Win Percentage")
try:
    team_df = get_team_performance()
    if not team_df.empty:
        fig = bar_chart(team_df, "team_name", "win_pct", "Win Percentage by Team")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(team_df, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Error: {e}")


if selected_team:
    st.markdown("---")
    st.header(f"Team Analysis: {selected_team}")

    season_clause = ""
    if selected_seasons:
        seasons_str = ",".join(f"'{s}'" for s in selected_seasons)
        season_clause = f"AND fms.season IN ({seasons_str})"


    query = f"""
        SELECT fms.season,
            COUNT(*) as matches,
            SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END) as wins,
            ROUND(SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END)::numeric
                / NULLIF(COUNT(*), 0) * 100, 1) as win_pct
        FROM fact_match_summary fms
        JOIN dim_team dt ON (fms.team1_key = dt.team_key OR fms.team2_key = dt.team_key)
        WHERE dt.team_name = :team AND fms.result != 'no result' {season_clause}
        GROUP BY fms.season, dt.team_key
        ORDER BY fms.season
    """
    try:
        season_df = run_query(query, {"team": selected_team})
        if not season_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = bar_chart(season_df, "season", "wins", f"{selected_team} - Wins per Season")
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = line_chart(season_df, "season", "win_pct", f"{selected_team} - Win % Trend")
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")


    st.subheader("Toss Analysis")
    toss_query = f"""
        SELECT fms.toss_decision,
            COUNT(*) as times,
            SUM(CASE WHEN fms.match_winner_key = dt.team_key THEN 1 ELSE 0 END) as wins
        FROM fact_match_summary fms
        JOIN dim_team dt ON fms.toss_winner_key = dt.team_key
        WHERE dt.team_name = :team {season_clause}
        GROUP BY fms.toss_decision
    """
    try:
        toss_df = run_query(toss_query, {"team": selected_team})
        if not toss_df.empty:
            fig = pie_chart(toss_df, "toss_decision", "times", "Toss Decisions")
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")
