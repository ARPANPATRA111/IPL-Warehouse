import streamlit as st

st.set_page_config(page_title="Venue Analysis - IPL", page_icon="🏏", layout="wide")

from dashboard.components.charts import bar_chart, heatmap_chart
from dashboard.components.filters import season_filter, venue_filter
from dashboard.utils.db import run_query

st.title("Venue Analysis")
st.markdown("---")


with st.sidebar:
    st.header("Filters")
    selected_seasons = season_filter(key="venue_season")
    selected_venues = venue_filter(key="venue_select")

season_clause = ""
if selected_seasons:
    seasons_str = ",".join(f"'{s}'" for s in selected_seasons)
    season_clause = f"AND dm.season IN ({seasons_str})"

venue_clause = ""
if selected_venues:
    venues_str = ",".join(f"'{v}'" for v in selected_venues)
    venue_clause = f"AND dv.venue_name IN ({venues_str})"


st.header("Venue Statistics")
query = f"""
    SELECT dv.venue_name,
        dv.city,
        COUNT(DISTINCT fd.match_key) as matches,
        ROUND(AVG(fd.runs_total)::numeric * 6 /
            NULLIF(AVG(CASE WHEN fd.is_legal_delivery THEN 1.0 ELSE NULL END), 0), 2) as avg_run_rate,
        SUM(CASE WHEN fd.is_boundary_six THEN 1 ELSE 0 END) as total_sixes,
        SUM(CASE WHEN fd.is_wicket THEN 1 ELSE 0 END) as total_wickets,
        ROUND(SUM(CASE WHEN fd.is_boundary_four OR fd.is_boundary_six THEN 1 ELSE 0 END)::numeric * 100
            / NULLIF(COUNT(*), 0), 2) as boundary_pct
    FROM fact_deliveries fd
    JOIN dim_venue dv ON fd.venue_key = dv.venue_key
    JOIN dim_match dm ON fd.match_key = dm.match_key
    WHERE 1=1 {season_clause} {venue_clause}
    GROUP BY dv.venue_name, dv.city
    HAVING COUNT(DISTINCT fd.match_key) >= 3
    ORDER BY matches DESC
"""

try:
    df = run_query(query)
    if not df.empty:
        fig = bar_chart(df.head(15), "venue_name", "avg_run_rate", "Average Run Rate by Venue")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No venue data available")
except Exception as e:
    st.error(f"Error: {e}")


st.header("Bat First vs Chase Win %")
chase_query = f"""
    SELECT dv.venue_name,
        COUNT(*) as total_matches,
        SUM(CASE WHEN fms.win_type = 'runs' THEN 1 ELSE 0 END) as bat_first_wins,
        SUM(CASE WHEN fms.win_type = 'wickets' THEN 1 ELSE 0 END) as chase_wins,
        ROUND(SUM(CASE WHEN fms.win_type = 'wickets' THEN 1 ELSE 0 END)::numeric * 100
            / NULLIF(COUNT(*), 0), 1) as chase_win_pct
    FROM fact_match_summary fms
    JOIN dim_venue dv ON fms.venue_key = dv.venue_key
    JOIN dim_match dm ON fms.match_key = dm.match_key
    WHERE fms.result = 'normal' {season_clause} {venue_clause}
    GROUP BY dv.venue_name
    HAVING COUNT(*) >= 5
    ORDER BY chase_win_pct DESC
"""

try:
    chase_df = run_query(chase_query)
    if not chase_df.empty:
        fig = bar_chart(chase_df.head(15), "venue_name", "chase_win_pct", "Chase Win % by Venue")
        st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.warning(f"Could not load chase data: {e}")
