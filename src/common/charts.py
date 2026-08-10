from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go

STATUS_COLORS = {"PASS": "#146C3A", "FAIL": "#B3261E", "REVIEW": "#91600A", "N/A": "#5B6472"}
FONT = dict(family="Inter, Segoe UI, sans-serif", color="#333B47", size=12)
GRID_COLOR = "#EDEFF2"


def _base_layout(fig: go.Figure, title: str, height: int = 300) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(family=FONT["family"], size=13, color="#0F1420"), x=0, xanchor="left"),
        font=FONT,
        height=height,
        margin=dict(l=10, r=10, t=42, b=10),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        showlegend=False,
    )
    return fig


_FLAT_COLUMNS = [
    "case_id",
    "created_at",
    "kct",
    "check",
    "status",
    "confidence",
    "note",
    "left_value",
    "right_value",
    "source_left",
    "source_right",
]


def flatten_results(cases_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, case in cases_df.iterrows():
        try:
            results = json.loads(case["results_json"])
        except (TypeError, ValueError):
            continue
        for r in results:
            rows.append(
                {
                    "case_id": case["case_id"],
                    "created_at": case["created_at"],
                    "kct": r.get("kct"),
                    "check": r.get("check"),
                    "status": r.get("status"),
                    "confidence": r.get("confidence"),
                    "note": r.get("note"),
                    "left_value": r.get("left_value"),
                    "right_value": r.get("right_value"),
                    "source_left": r.get("source_left"),
                    "source_right": r.get("source_right"),
                }
            )
    return pd.DataFrame(rows, columns=_FLAT_COLUMNS)


def status_distribution_chart(counts: dict[str, int]) -> go.Figure:
    order = ["PASS", "REVIEW", "FAIL", "N/A"]
    labels = [s for s in order if counts.get(s, 0) > 0]
    values = [counts[s] for s in labels]
    if not values:
        labels, values = ["No data"], [1]
        colors = ["#EEF0F3"]
    else:
        colors = [STATUS_COLORS[s] for s in labels]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.62,
                marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
                textinfo="value",
                textfont=dict(size=12, color="#FFFFFF"),
                sort=False,
            )
        ]
    )
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.1, font=dict(size=10)))
    return _base_layout(fig, "Check Status Distribution", height=280)


def cases_over_time_chart(cases_df: pd.DataFrame) -> go.Figure:
    if cases_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No cases processed yet", showarrow=False, font=dict(color="#98A2B3"))
        return _base_layout(fig, "Cases Processed Over Time")

    df = cases_df.copy()
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    df["flag_label"] = df["flagged"].map({1: "Flagged", 0: "Clear"})
    grouped = df.groupby(["date", "flag_label"]).size().unstack(fill_value=0)
    for col in ("Clear", "Flagged"):
        if col not in grouped.columns:
            grouped[col] = 0

    fig = go.Figure()
    fig.add_bar(x=grouped.index.astype(str), y=grouped["Clear"], name="Clear", marker_color="#146C3A")
    fig.add_bar(x=grouped.index.astype(str), y=grouped["Flagged"], name="Flagged", marker_color="#B3261E")
    fig.update_layout(barmode="stack", showlegend=True, legend=dict(orientation="h", y=-0.2, font=dict(size=10)))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    return _base_layout(fig, "Cases Processed Over Time")


def top_exceptions_chart(flat: pd.DataFrame) -> go.Figure:
    if flat.empty:
        fig = go.Figure()
        fig.add_annotation(text="No cases processed yet", showarrow=False, font=dict(color="#98A2B3"))
        return _base_layout(fig, "Most Frequent Exceptions")

    exceptions = flat[flat["status"].isin(["FAIL", "REVIEW"])]
    if exceptions.empty:
        fig = go.Figure()
        fig.add_annotation(text="No exceptions recorded", showarrow=False, font=dict(color="#98A2B3"))
        return _base_layout(fig, "Most Frequent Exceptions")

    counts = exceptions.groupby(["kct", "status"]).size().unstack(fill_value=0).sort_values(
        by=list(exceptions["status"].unique()), ascending=True
    )
    fig = go.Figure()
    if "FAIL" in counts.columns:
        fig.add_bar(y=counts.index, x=counts["FAIL"], name="Fail", orientation="h", marker_color="#B3261E")
    if "REVIEW" in counts.columns:
        fig.add_bar(y=counts.index, x=counts["REVIEW"], name="Review", orientation="h", marker_color="#91600A")
    fig.update_layout(barmode="stack", showlegend=True, legend=dict(orientation="h", y=-0.15, font=dict(size=10)))
    fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    fig.update_yaxes(showgrid=False)
    return _base_layout(fig, "Most Frequent Exceptions by Control", height=max(220, 40 * len(counts) + 80))


def confidence_histogram(flat: pd.DataFrame) -> go.Figure:
    scored = flat.dropna(subset=["confidence"])
    if scored.empty:
        fig = go.Figure()
        fig.add_annotation(text="No AI-scored checks yet", showarrow=False, font=dict(color="#98A2B3"))
        return _base_layout(fig, "AI Confidence Distribution")

    fig = go.Figure(
        data=[
            go.Histogram(
                x=scored["confidence"],
                xbins=dict(start=0, end=100, size=10),
                marker_color="#2451D6",
                marker_line=dict(color="#FFFFFF", width=1),
            )
        ]
    )
    fig.update_xaxes(title="Confidence %", showgrid=False, range=[0, 100])
    fig.update_yaxes(title="Checks", showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    return _base_layout(fig, "AI Confidence Distribution")
