import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str = None,
    orientation: str = "v",
    height: int = 400,
) -> go.Figure:
    fig = px.bar(
        df, x=x, y=y, title=title, color=color,
        orientation=orientation, height=height,
    )
    fig.update_layout(
        xaxis_title=x.replace("_", " ").title(),
        yaxis_title=y.replace("_", " ").title(),
        template="plotly_white",
    )
    return fig

def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str = None,
    height: int = 400,
) -> go.Figure:
    fig = px.line(df, x=x, y=y, title=title, color=color, height=height)
    fig.update_layout(template="plotly_white")
    return fig

def pie_chart(
    df: pd.DataFrame,
    names: str,
    values: str,
    title: str = "",
    height: int = 400,
) -> go.Figure:
    fig = px.pie(df, names=names, values=values, title=title, height=height)
    fig.update_layout(template="plotly_white")
    return fig

def scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str = None,
    size: str = None,
    height: int = 400,
) -> go.Figure:
    fig = px.scatter(df, x=x, y=y, title=title, color=color, size=size, height=height)
    fig.update_layout(template="plotly_white")
    return fig

def heatmap_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    z: str,
    title: str = "",
    height: int = 500,
) -> go.Figure:
    pivot = df.pivot_table(index=y, columns=x, values=z, aggfunc="mean")
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="Blues",
    ))
    fig.update_layout(title=title, height=height, template="plotly_white")
    return fig

def kpi_metric(label: str, value, delta=None, delta_color: str = "normal"):
    import streamlit as st
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)
