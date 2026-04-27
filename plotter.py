import matplotlib.pyplot as plt
import seaborn as sns
import io
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

LYNCH_COLORS = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel


# ────────────────────────────────────────────────
# Helper added for robustness — detects date column automatically
# ────────────────────────────────────────────────
def get_date_column(df: pd.DataFrame) -> str | None:
    """
    Detect the most appropriate x-axis column for time-series plots.
    V3 FIX: session_day (integer) is checked first and takes priority over calendar dates
    to prevent NaT errors and misaligned cohorts.
    """
    for col in ["session_day", "start_date", "first_session_time", "date", "end_date"]:
        if col in df.columns:
            return col
    return None


def create_plot(data, x, y, title, hue=None, kind="bar", palette="Set1", style=None, markers=True):
    """Legacy matplotlib fallback — kept for ZIP export compatibility."""
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    try:
        if kind == "bar":
            sns.barplot(data=data, x=x, y=y, hue=hue, errorbar=None, palette=palette)
        elif kind == "line":
            sns.lineplot(data=data, x=x, y=y, hue=hue, style=style, markers=markers, palette=palette)
            plt.xticks(rotation=45)
        elif kind == "scatter":
            sns.scatterplot(data=data, x=x, y=y, hue=hue, size=style, alpha=0.7, palette=palette)
        elif kind == "box":
            sns.boxplot(data=data, x=x, y=y, hue=hue, palette=palette)
            sns.stripplot(data=data, x=x, y=y, color='black', alpha=0.3)
    except Exception:
        pass
    plt.title(title)
    plt.tight_layout()
    buf = io.BytesIO()
    try:
        plt.savefig(buf, format="png", dpi=150)
    except Exception as e:
        if "Done" in str(e) or "RendererAgg" in str(e):
            pass  # Expected
    plt.close()
    buf.seek(0)
    return buf


def create_interactive_plot(data, x, y, title, hue=None, kind="line", color_discrete_sequence=LYNCH_COLORS):
    """Core interactive Plotly plot."""
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=f"No data available - {title}")
        return fig

    hover_cols = data.columns.tolist()

    if kind == "line":
        fig = px.line(
            data, x=x, y=y, color=hue, title=title, markers=True,
            hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence
        )
        if x != "session_day":
            fig.update_xaxes(tickangle=45)
    elif kind == "bar":
        fig = px.bar(
            data, x=x, y=y, color=hue, title=title, barmode="group",
            hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence
        )
    elif kind == "scatter":
        fig = px.scatter(
            data, x=x, y=y, color=hue, title=title, opacity=0.7,
            hover_data=hover_cols, marginal_x="box", marginal_y="box",
            color_discrete_sequence=color_discrete_sequence
        )
    elif kind == "box":
        fig = px.box(
            data, x=x, y=y, color=hue, title=title, points="all",
            hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence
        )
    else:
        fig = px.line(
            data, x=x, y=y, title=title,
            hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence
        )

    x_title = "Session Day" if x == "session_day" else x.replace("_", " ").title()
    fig.update_layout(
        template="plotly_white",
        height=600,
        legend_title_text=hue or "",
        xaxis_title=x_title,
        yaxis_title=y.replace("_", " ").title()
    )
    return fig


# ────────────────────────────────────────────────
# Specialized plots
# ────────────────────────────────────────────────

def create_efficiency_trend(daily: pd.DataFrame):
    if daily.empty or "total_active_presses" not in daily.columns:
        return go.Figure().update_layout(title="Efficiency Trend")

    date_col = get_date_column(daily)
    if date_col is None:
        return go.Figure().update_layout(title="Efficiency Trend - No Date Column")

    df = daily.copy()
    df["efficiency"] = df["total_infusions"] / (df["total_active_presses"] + 1)

    return create_interactive_plot(
        df, date_col, "efficiency", "Efficiency Trend (Rewards/Effort)",
        hue="canonical_subject", kind="line"
    )


def create_hourly_heatmap(hr: pd.DataFrame):
    if hr.empty or "infusion_events" not in hr.columns:
        return go.Figure().update_layout(title="Hourly Infusion Heatmap - No Data")

    pivot = hr.groupby(["canonical_subject", "hour"])["infusion_events"].sum().unstack(fill_value=0)

    fig = px.imshow(
        pivot, title="Hourly Infusion Heatmap", aspect="auto",
        color_continuous_scale="Blues",
        labels=dict(x="Hour of Session", y="Subject", color="Infusions")
    )
    fig.update_layout(template="plotly_white", height=500)
    return fig


def create_cumulative_plot(sess: pd.DataFrame):
    if sess.empty:
        return go.Figure().update_layout(title="Cumulative Infusions - No Data")

    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Cumulative Infusions - No Date Column")

    sess = sess.sort_values(date_col).copy()
    sess["cumulative_infusions"] = sess.groupby("canonical_subject")["infusions"].cumsum()

    fig = px.line(
        sess, x=date_col, y="cumulative_infusions", color="canonical_subject",
        title="Cumulative Infusions Over Time", markers=True,
        hover_data=["infusions", "active_presses", "program_name", "gender"],
        color_discrete_sequence=LYNCH_COLORS
    )

    xaxis_cfg = dict(tickangle=45, rangeslider_visible=True)
    if date_col != "session_day":
        xaxis_cfg["tickformat"] = "%Y-%m-%d"

    fig.update_layout(
        xaxis_title="Session Day" if date_col == "session_day" else "Date",
        yaxis_title="Cumulative Infusions",
        template="plotly_white",
        hovermode="x unified",
        xaxis=xaxis_cfg,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def create_discrimination_plot(sess: pd.DataFrame):
    if sess.empty or "active_presses" not in sess.columns:
        return go.Figure().update_layout(title="Active vs Inactive Discrimination - No Data")

    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Discrimination Plot - No Date Column")

    df_melt = sess.melt(
        id_vars=[date_col, "canonical_subject"],
        value_vars=["active_presses", "inactive_presses"],
        var_name="Lever", value_name="Presses"
    )
    df_melt["Lever"] = df_melt["Lever"].str.replace("_presses", "").str.title()

    fig = px.bar(
        df_melt, x=date_col, y="Presses", color="Lever",
        barmode="group", facet_col="canonical_subject", facet_col_wrap=3,
        title="Lever Discrimination per Session"
    )
    
    if date_col == "session_day":
        fig.update_xaxes(title_text="Session Day")
        
    fig.update_layout(template="plotly_white", height=600)
    return fig


def create_pr_breakpoint_plot(sess: pd.DataFrame):
    if sess.empty or "breakpoint" not in sess.columns or sess["breakpoint"].sum() == 0:
        return go.Figure().update_layout(title="Progressive Ratio Breakpoints (No PR Data)")

    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="PR Breakpoint Plot - No Date Column")

    return create_interactive_plot(
        sess, date_col, "breakpoint", "PR Breakpoint Evolution",
        hue="canonical_subject", kind="line"
    )


def create_response_rate_plot(sess: pd.DataFrame):
    if sess.empty or "active_presses" not in sess.columns:
        return go.Figure().update_layout(title="Response Rate (Presses/Hour) - No Data")

    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Response Rate Plot - No Date Column")

    rate = sess.copy()
    rate["response_rate"] = rate["active_presses"] / ((rate["duration_sec"] / 3600) + 1e-6)

    return create_interactive_plot(
        rate, date_col, "response_rate", "Response Rate (Active Presses per Hour)",
        hue="canonical_subject", kind="line"
    )


def create_within_session_plot(active_timestamps, duration=None):
    """Generates a cumulative step-plot for correct responses over 1 session."""
    if not isinstance(active_timestamps, list) or len(active_timestamps) == 0:
        fig = go.Figure()
        fig.update_layout(title="No correct response timepoints (L) available for this session.")
        return fig

    # Y-values represent cumulative correct responses
    y_vals = np.arange(1, len(active_timestamps) + 1)
    
    fig = go.Figure(go.Scatter(
        x=active_timestamps,
        y=y_vals,
        mode='lines+markers',
        line_shape='hv',  # Step-plot
        name='Correct Responses',
        line=dict(color='rgb(31, 119, 180)', width=2)
    ))

    max_time = max(active_timestamps) * 1.05
    if duration and duration > 0:
        max_time = max(max_time, duration)

    fig.update_layout(
        title="Within-Session Timepoint Data: Correct Responses",
        xaxis_title="Time in Session (seconds)",
        yaxis_title="Cumulative Correct Responses",
        xaxis=dict(range=[0, max_time]),
        template="plotly_white",
        hovermode="x unified"
    )
    return fig


def create_mean_sem_trajectory(daily: pd.DataFrame):
    """Cohort average trajectory (Mean ± SEM) with robust integer/date handling."""
    if daily.empty or "total_infusions" not in daily.columns:
        return go.Figure().update_layout(title="No data available for Cohort Average Trajectory")

    date_col = get_date_column(daily)
    if date_col is None:
        return go.Figure().update_layout(title="Cohort Average Trajectory - No Date Column")

    mean_df = daily.groupby(date_col)["total_infusions"].agg(["mean", "sem"]).reset_index()
    mean_df = mean_df.rename(columns={date_col: "x_val"})

    if date_col != "session_day":
        mean_df["x_val"] = pd.to_datetime(mean_df["x_val"], errors="coerce")
        hover_tmpl = "Date: %{x|%Y-%m-%d}<br>Mean Infusions: %{y:.2f}<extra></extra>"
        x_label, tick_fmt = "Date", "%Y-%m-%d"
    else:
        mean_df["x_val"] = mean_df["x_val"].astype(int)
        hover_tmpl = "Session Day: %{x}<br>Mean Infusions: %{y:.2f}<extra></extra>"
        x_label, tick_fmt = "Session Day", None

    x, y = mean_df["x_val"], mean_df["mean"]
    
    fig = go.Figure([
        go.Scatter(
            name="Cohort Mean", x=x, y=y,
            mode="lines+markers", line=dict(color="rgb(31, 119, 180)"),
            marker=dict(size=8), hovertemplate=hover_tmpl
        ),
        go.Scatter(
            name="Upper Bound", x=x, y=y + mean_df["sem"],
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"
        ),
        go.Scatter(
            name="Lower Bound", x=x, y=y - mean_df["sem"],
            mode="lines", line=dict(width=0), fillcolor="rgba(31, 119, 180, 0.2)",
            fill="tonexty", showlegend=False, hoverinfo="skip"
        )
    ])

    xaxis_cfg = dict(tickangle=45, rangeslider_visible=True)
    if tick_fmt:
        xaxis_cfg["tickformat"] = tick_fmt

    fig.update_layout(
        title="Cohort Average Trajectory (Mean ± SEM)",
        xaxis_title=x_label,
        yaxis_title="Infusions (Mean ± SEM)",
        template="plotly_white",
        hovermode="x unified",
        xaxis=xaxis_cfg,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig
