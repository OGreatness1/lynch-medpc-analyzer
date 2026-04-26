import matplotlib.pyplot as plt
import seaborn as sns
import io
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

LYNCH_COLORS = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel


def get_date_column(df: pd.DataFrame) -> str | None:
    """
    Detect the most appropriate x-axis column for time-series plots.
    session_day (integer) is checked first and takes priority over
    calendar dates when both are present.
    """
    possible = ["session_day", "start_date", "first_session_time", "date", "end_date"]
    for col in possible:
        if col in df.columns:
            return col
    return None


def _is_integer_day_column(df: pd.DataFrame, col: str) -> bool:
    """Return True when col holds integer session-day numbers (not dates)."""
    try:
        series = df[col].dropna()
        if pd.api.types.is_integer_dtype(series):
            return True
        if pd.api.types.is_float_dtype(series):
            return bool(series.apply(lambda x: x == int(x)).all())
    except Exception:
        pass
    return False


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
            sns.stripplot(data=data, x=x, y=y, color="black", alpha=0.3)
    except Exception:
        pass
    plt.title(title)
    plt.tight_layout()
    buf = io.BytesIO()
    try:
        plt.savefig(buf, format="png", dpi=150)
    except Exception as e:
        if "Done" not in str(e) and "RendererAgg" not in str(e):
            pass
    plt.close()
    buf.seek(0)
    return buf


def create_interactive_plot(
    data, x, y, title, hue=None, kind="line",
    color_discrete_sequence=LYNCH_COLORS
):
    """Core interactive Plotly chart."""
    if data.empty:
        return go.Figure().update_layout(title=f"No data available — {title}")

    hover_cols = data.columns.tolist()

    if kind == "line":
        fig = px.line(
            data, x=x, y=y, color=hue, title=title, markers=True,
            hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence,
        )
        fig.update_xaxes(tickangle=45)
    elif kind == "bar":
        fig = px.bar(
            data, x=x, y=y, color=hue, title=title, barmode="group",
            hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence,
        )
    elif kind == "scatter":
        fig = px.scatter(
            data, x=x, y=y, color=hue, title=title, opacity=0.7,
            hover_data=hover_cols, marginal_x="box", marginal_y="box",
            color_discrete_sequence=color_discrete_sequence,
        )
    elif kind == "box":
        fig = px.box(
            data, x=x, y=y, color=hue, title=title, points="all",
            hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence,
        )
    else:
        fig = px.line(
            data, x=x, y=y, title=title,
            hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence,
        )

    fig.update_layout(
        template="plotly_white",
        height=600,
        legend_title_text=hue or "",
        xaxis_title=x.replace("_", " ").title(),
        yaxis_title=y.replace("_", " ").title(),
    )
    return fig


# ────────────────────────────────────────────────
# Specialised plots
# ────────────────────────────────────────────────

def create_hourly_line_plot(hr: pd.DataFrame, title: str = "Avg Infusions by Hour of Session"):
    """
    Mean infusion events per hour of session, averaged over ALL sessions per
    subject (including sessions where that hour had zero events).

    WHY a dedicated function:
      sub_h has one row per (subject, session, hour) — but only for hours that
      had at least one event (zero-event hours are not stored).  Passing that
      raw to create_interactive_plot draws one line connecting all hours in row
      order across sessions, zigzagging back and forth → cycling appearance.

    WHY .mean() alone is wrong:
      Because we only store active hours, a session where the animal had zero
      infusions in hour 2 contributes NO row for hour 2.  Taking .mean() over
      the rows that DO exist divides by sessions-with-activity, not total
      sessions — making the average artificially inflated.

    Correct approach:
      1. Sum all infusion events per (subject, hour) across the whole cohort.
      2. Divide by the total number of sessions for that subject (including
         sessions with zero events in that hour).
      This gives a true mean that correctly pulls the average down for hours
      where many sessions had zero activity.
    """
    if hr.empty or "infusion_events" not in hr.columns:
        return go.Figure().update_layout(title=f"{title} — No Data")

    # Total sessions per subject (the correct denominator)
    # Use start_date to count unique sessions; fall back to session_day if present
    if "start_date" in hr.columns:
        n_sessions = (
            hr.groupby("canonical_subject")["start_date"]
            .nunique()
            .reset_index(name="n_sessions")
        )
    elif "session_day" in hr.columns:
        n_sessions = (
            hr.groupby("canonical_subject")["session_day"]
            .nunique()
            .reset_index(name="n_sessions")
        )
    else:
        # Last resort: count all rows then divide by max_hour+1
        n_sessions = (
            hr.groupby("canonical_subject")["hour"]
            .nunique()
            .reset_index(name="n_sessions")
        )

    # Sum of infusion events across all sessions for each (subject, hour)
    sum_by_hour = (
        hr.groupby(["canonical_subject", "hour"])["infusion_events"]
        .sum()
        .reset_index(name="total_infusion_events")
    )

    # Merge and divide sum by total sessions → true mean per hour
    agg = sum_by_hour.merge(n_sessions, on="canonical_subject", how="left")
    agg["avg_infusion_events"] = agg["total_infusion_events"] / agg["n_sessions"]
    agg = agg.sort_values(["canonical_subject", "hour"])
    fig = px.line(
        agg, x="hour", y="avg_infusion_events",
        color="canonical_subject", title=title, markers=True,
        hover_data={"total_infusion_events": True, "n_sessions": True},
        color_discrete_sequence=LYNCH_COLORS,
    )
    fig.update_layout(
        template="plotly_white", height=600,
        xaxis_title="Hour of Session",
        yaxis_title="Avg Infusion Events (per session)",
        legend_title_text="Subject",
        xaxis=dict(dtick=1),
    )
    return fig


def create_efficiency_trend(daily: pd.DataFrame):
    if daily.empty or "total_active_presses" not in daily.columns:
        return go.Figure().update_layout(title="Efficiency Trend")

    date_col = get_date_column(daily)
    if date_col is None:
        return go.Figure().update_layout(title="Efficiency Trend — No Date Column")

    df = daily.copy()
    df["efficiency"] = df["total_infusions"] / (df["total_active_presses"] + 1)

    return create_interactive_plot(
        df, date_col, "efficiency",
        "Efficiency Trend (Rewards/Effort)",
        hue="canonical_subject", kind="line",
    )


def create_hourly_heatmap(hr: pd.DataFrame):
    if hr.empty or "infusion_events" not in hr.columns:
        return go.Figure().update_layout(title="Hourly Infusion Heatmap — No Data")

    pivot = hr.groupby(["canonical_subject", "hour"])["infusion_events"].sum().unstack(fill_value=0)

    fig = px.imshow(
        pivot, title="Hourly Infusion Heatmap",
        aspect="auto", color_continuous_scale="Blues",
        labels=dict(x="Hour of Session", y="Subject", color="Infusions"),
    )
    fig.update_layout(template="plotly_white", height=500)
    return fig


def create_cumulative_plot(sess: pd.DataFrame):
    if sess.empty:
        return go.Figure().update_layout(title="Cumulative Infusions — No Data")

    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Cumulative Infusions — No Date Column")

    sess = sess.sort_values(date_col).copy()
    sess["cumulative_infusions"] = sess.groupby("canonical_subject")["infusions"].cumsum()

    fig = px.line(
        sess, x=date_col, y="cumulative_infusions",
        color="canonical_subject",
        title="Cumulative Infusions Over Time", markers=True,
        hover_data=["infusions", "active_presses", "program_name", "gender"],
        color_discrete_sequence=LYNCH_COLORS,
    )

    is_int = _is_integer_day_column(sess, date_col)
    x_label = "Session Day" if is_int else "Date"
    xaxis_cfg = dict(tickangle=45, rangeslider_visible=True)
    if not is_int:
        xaxis_cfg["tickformat"] = "%Y-%m-%d"

    fig.update_layout(
        xaxis_title=x_label, yaxis_title="Cumulative Infusions",
        template="plotly_white", hovermode="x unified",
        xaxis=xaxis_cfg,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def create_discrimination_plot(sess: pd.DataFrame):
    if sess.empty or "active_presses" not in sess.columns:
        return go.Figure().update_layout(title="Active vs Inactive Discrimination — No Data")

    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Discrimination Plot — No Date Column")

    df_melt = sess.melt(
        id_vars=[date_col, "canonical_subject"],
        value_vars=["active_presses", "inactive_presses"],
        var_name="Lever", value_name="Presses",
    )
    df_melt["Lever"] = df_melt["Lever"].str.replace("_presses", "").str.title()

    fig = px.bar(
        df_melt, x=date_col, y="Presses", color="Lever",
        barmode="group", facet_col="canonical_subject", facet_col_wrap=3,
        title="Lever Discrimination per Session",
    )
    fig.update_layout(template="plotly_white", height=600)
    return fig


def create_pr_breakpoint_plot(sess: pd.DataFrame):
    if sess.empty or "breakpoints" not in sess.columns or sess["breakpoints"].sum() == 0:
        return go.Figure().update_layout(title="Progressive Ratio Breakpoints (No PR Data)")

    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="PR Breakpoint Plot — No Date Column")

    return create_interactive_plot(
        sess, date_col, "breakpoints",
        "PR Breakpoint Evolution",
        hue="canonical_subject", kind="line",
    )


def create_response_rate_plot(sess: pd.DataFrame):
    if sess.empty or "active_presses" not in sess.columns:
        return go.Figure().update_layout(title="Response Rate (Presses/Hour) — No Data")

    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Response Rate Plot — No Date Column")

    rate = sess.copy()
    rate["response_rate"] = rate["active_presses"] / ((rate["duration_sec"] / 3600) + 1e-6)

    return create_interactive_plot(
        rate, date_col, "response_rate",
        "Response Rate (Active Presses per Hour)",
        hue="canonical_subject", kind="line",
    )


def create_within_session_plot(active_timestamps, duration=None):
    """Cumulative step-plot of active responses across one session."""
    import numpy as np

    if not isinstance(active_timestamps, list) or len(active_timestamps) == 0:
        return go.Figure().update_layout(title="No active response timepoints available.")

    y_vals = np.arange(1, len(active_timestamps) + 1)

    fig = go.Figure(go.Scatter(
        x=active_timestamps, y=y_vals,
        mode="lines+markers", line_shape="hv",
        name="Active Responses",
        line=dict(color="rgb(31, 119, 180)", width=2),
    ))

    max_time = max(active_timestamps) * 1.05
    if duration and duration > 0:
        max_time = max(max_time, duration)

    fig.update_layout(
        title="Within-Session Timepoint Data: Active Responses",
        xaxis_title="Time in Session (seconds)",
        yaxis_title="Cumulative Active Responses",
        xaxis=dict(range=[0, max_time]),
        template="plotly_white", hovermode="x unified",
    )
    return fig


def create_mean_sem_trajectory(daily: pd.DataFrame):
    """
    Cohort average trajectory (Mean ± SEM) with shaded error band.
    Handles both integer session_day and calendar-date x-axes correctly.
    """
    if daily.empty or "total_infusions" not in daily.columns:
        return go.Figure().update_layout(title="No data — Cohort Average Trajectory")

    date_col = get_date_column(daily)
    if date_col is None:
        return go.Figure().update_layout(title="Cohort Average Trajectory — No Date Column")

    mean_df = (
        daily.groupby(date_col)["total_infusions"]
        .agg(["mean", "sem"])
        .reset_index()
        .rename(columns={date_col: "x_val"})
    )
    mean_df["sem"] = mean_df["sem"].fillna(0)

    # Only attempt datetime conversion when the column is not integer session days.
    # Forcing pd.to_datetime() on integers produces NaT → blank chart.
    use_dates = not _is_integer_day_column(daily, date_col)
    if use_dates:
        mean_df["x_val"] = pd.to_datetime(mean_df["x_val"], errors="coerce")
        mean_df = mean_df.dropna(subset=["x_val"])
        hover_tmpl = "Date: %{x|%Y-%m-%d}<br>Mean Infusions: %{y:.2f}<extra></extra>"
        x_label  = "Date"
        tick_fmt = "%Y-%m-%d"
    else:
        mean_df["x_val"] = mean_df["x_val"].astype(int)
        hover_tmpl = "Session Day: %{x}<br>Mean Infusions: %{y:.2f}<extra></extra>"
        x_label  = "Session Day"
        tick_fmt = None

    if mean_df.empty:
        return go.Figure().update_layout(title="Cohort Average Trajectory — No Valid Data")

    x      = mean_df["x_val"]
    y      = mean_df["mean"]
    y_up   = y + mean_df["sem"]
    y_down = y - mean_df["sem"]

    fig = go.Figure([
        go.Scatter(
            name="Cohort Mean", x=x, y=y,
            mode="lines+markers",
            line=dict(color="rgb(31, 119, 180)"),
            marker=dict(size=8),
            hovertemplate=hover_tmpl,
        ),
        go.Scatter(
            name="Upper Bound", x=x, y=y_up,
            mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ),
        go.Scatter(
            name="Lower Bound", x=x, y=y_down,
            mode="lines", line=dict(width=0),
            fillcolor="rgba(31, 119, 180, 0.2)", fill="tonexty",
            showlegend=False, hoverinfo="skip",
        ),
    ])

    xaxis_cfg = dict(tickangle=45, rangeslider_visible=True)
    if tick_fmt:
        xaxis_cfg["tickformat"] = tick_fmt

    fig.update_layout(
        title="Cohort Average Trajectory (Mean ± SEM)",
        xaxis_title=x_label, yaxis_title="Infusions (Mean ± SEM)",
        template="plotly_white", hovermode="x unified",
        xaxis=xaxis_cfg, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
