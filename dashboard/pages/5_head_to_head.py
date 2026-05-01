import streamlit as st

st.set_page_config(page_title="Head to Head - IPL", page_icon="🏏", layout="wide")

from dashboard.components.charts import bar_chart, pie_chart
from dashboard.components.filters import season_filter
from dashboard.utils.db import get_teams, run_query

st.title("Head to Head Analysis")
st.markdown("---")


with st.sidebar:
    st.header("Select Teams")
    teams = get_teams()
    team1 = st.selectbox("Team 1", options=teams, key="h2h_team1") if teams else ""
    team2 = st.selectbox("Team 2", options=teams, index=min(1, len(teams) - 1), key="h2h_team2") if teams else ""
    selected_seasons = season_filter(key="h2h_season")

if team1 and team2 and team1 != team2:
    season_clause = ""
    if selected_seasons:
        seasons_str = ",".join(f"'{s}'" for s in selected_seasons)
        season_clause = f"AND fms.season IN ({seasons_str})"


    st.header(f"{team1} vs {team2}")
    h2h_query = f"""
        SELECT
            COUNT(*) as total_matches,
            SUM(CASE WHEN fms.match_winner_key = t1.team_key THEN 1 ELSE 0 END) as team1_wins,
            SUM(CASE WHEN fms.match_winner_key = t2.team_key THEN 1 ELSE 0 END) as team2_wins,
            SUM(CASE WHEN fms.result = 'no result' THEN 1 ELSE 0 END) as no_result
        FROM fact_match_summary fms
        JOIN dim_team t1 ON t1.team_name = :team1
        JOIN dim_team t2 ON t2.team_name = :team2
        WHERE (
            (fms.team1_key = t1.team_key AND fms.team2_key = t2.team_key) OR
            (fms.team1_key = t2.team_key AND fms.team2_key = t1.team_key)
        ) {season_clause}
    """

    try:
        h2h_df = run_query(h2h_query, {"team1": team1, "team2": team2})
        if not h2h_df.empty and h2h_df["total_matches"].iloc[0] > 0:
            row = h2h_df.iloc[0]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Matches", int(row["total_matches"]))
            with col2:
                st.metric(f"{team1} Wins", int(row["team1_wins"]))
            with col3:
                st.metric(f"{team2} Wins", int(row["team2_wins"]))
            with col4:
                st.metric("No Result", int(row["no_result"]))


            import pandas as pd
            pie_data = pd.DataFrame({
                "Team": [team1, team2, "No Result"],
                "Wins": [int(row["team1_wins"]), int(row["team2_wins"]), int(row["no_result"])],
            })
            pie_data = pie_data[pie_data["Wins"] > 0]
            fig = pie_chart(pie_data, "Team", "Wins", "Win Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No head-to-head matches found")
    except Exception as e:
        st.error(f"Error: {e}")


    st.subheader("Season Breakdown")
    season_h2h_query = f"""
        SELECT fms.season,
            COUNT(*) as matches,
            SUM(CASE WHEN fms.match_winner_key = t1.team_key THEN 1 ELSE 0 END) as team1_wins,
            SUM(CASE WHEN fms.match_winner_key = t2.team_key THEN 1 ELSE 0 END) as team2_wins
        FROM fact_match_summary fms
        JOIN dim_team t1 ON t1.team_name = :team1
        JOIN dim_team t2 ON t2.team_name = :team2
        WHERE (
            (fms.team1_key = t1.team_key AND fms.team2_key = t2.team_key) OR
            (fms.team1_key = t2.team_key AND fms.team2_key = t1.team_key)
        ) {season_clause}
        GROUP BY fms.season
        ORDER BY fms.season
    """
    try:
        season_h2h_df = run_query(season_h2h_query, {"team1": team1, "team2": team2})
        if not season_h2h_df.empty:
            st.dataframe(season_h2h_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Error: {e}")


    st.subheader("Top Performers in Matchup")
    perf_query = f"""
        SELECT dp.player_name,
            SUM(fd.runs_batsman) as runs,
            SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as sixes
        FROM fact_deliveries fd
        JOIN dim_player dp ON fd.batsman_key = dp.player_key
        JOIN dim_team t1 ON t1.team_name = :team1
        JOIN dim_team t2 ON t2.team_name = :team2
        WHERE (
            (fd.batting_team_key = t1.team_key AND fd.bowling_team_key = t2.team_key) OR
            (fd.batting_team_key = t2.team_key AND fd.bowling_team_key = t1.team_key)
        ) AND fd.is_wide = FALSE
        GROUP BY dp.player_name
        ORDER BY runs DESC
        LIMIT 10
    """
    try:
        perf_df = run_query(perf_query, {"team1": team1, "team2": team2})
        if not perf_df.empty:
            fig = bar_chart(perf_df, "player_name", "runs", "Top Run Scorers in Matchup")
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Error: {e}")

elif team1 == team2:
    st.warning("Please select two different teams")
else:
    st.info("Select two teams to see head-to-head analysis")
