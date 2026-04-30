import streamlit as st

st.set_page_config(
    page_title="IPL Cricket Analytics",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.components.charts import bar_chart, line_chart, pie_chart
from dashboard.components.metrics import (
    get_overview_metrics,
    get_season_summary,
    get_top_batsmen,
    get_top_bowlers,
)

st.title("IPL Cricket Data Warehouse")
st.markdown("---")


st.header("Overview")
try:
    metrics = get_overview_metrics()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Matches", f"{metrics['total_matches']:,}")
    with col2:
        st.metric("Total Players", f"{metrics['total_players']:,}")
    with col3:
        st.metric("Total Runs", f"{metrics['total_runs']:,}")
    with col4:
        st.metric("Total Wickets", f"{metrics['total_wickets']:,}")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Active Teams", metrics["total_teams"])
    with col6:
        st.metric("Total Deliveries", f"{metrics['total_deliveries']:,}")
    with col7:
        st.metric("Total Sixes", f"{metrics['total_sixes']:,}")
    with col8:
        st.metric("Total Fours", f"{metrics['total_fours']:,}")
except Exception as e:
    st.error(f"Could not load metrics. Ensure database is connected. Error: {e}")
    st.stop()

st.markdown("---")


st.header("Season Trends")
try:
    season_df = get_season_summary()
    if not season_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig = line_chart(season_df, "season", "total_runs", "Total Runs by Season")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = bar_chart(season_df, "season", "sixes", "Sixes per Season")
            st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.warning(f"Could not load season data: {e}")

st.markdown("---")


st.header("Top Performers")
col1, col2 = st.columns(2)
try:
    with col1:
        st.subheader("Top 10 Run Scorers")
        batsmen_df = get_top_batsmen(limit=10)
        if not batsmen_df.empty:
            fig = bar_chart(batsmen_df, "player_name", "total_runs", "Top Run Scorers")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(batsmen_df, use_container_width=True)

    with col2:
        st.subheader("Top 10 Wicket Takers")
        bowlers_df = get_top_bowlers(limit=10)
        if not bowlers_df.empty:
            fig = bar_chart(bowlers_df, "player_name", "wickets", "Top Wicket Takers")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(bowlers_df, use_container_width=True)
except Exception as e:
    st.warning(f"Could not load performer data: {e}")


st.sidebar.title("Navigation")
st.sidebar.markdown("""
- **Home** (current)
- [Batting Analysis](pages/1_batting.py)
- [Bowling Analysis](pages/2_bowling.py)
- [Team Performance](pages/3_teams.py)
- [Venue Analysis](pages/4_venues.py)
- [Head to Head](pages/5_head_to_head.py)
""")

st.sidebar.markdown("---")
st.sidebar.info("IPL Data Warehouse v1.0.0 | Data: Cricsheet.org")
