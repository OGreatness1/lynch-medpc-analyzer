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
    session_day (integer) is checked first and takes priority over calendar dates.
    """
    for col in ["session_day", "start_date", "first_session_time", "date", "end_date"]:
        if col in df.columns:
            return col
    return None


def _is_integer_day_column(df: pd.DataFrame, col: str) -> bool:
    """Return True when col holds integer session-day numbers."""
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
    """Legacy matplotlib fallback — kept for ZIP export."""
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


def create_interactive_plot(data, x, y, title, hue=None, kind="line",
                             color_discrete_sequence=LYNCH_COLORS):
    if data.empty:
        return go.Figure().update_layout(title=f"No data available — {title}")
    hover_cols = data.columns.tolist()
    if kind == "line":
        fig = px.line(data, x=x, y=y, color=hue, title=title, markers=True,
                      hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence)
        fig.update_xaxes(tickangle=45)
    elif kind == "bar":
        fig = px.bar(data, x=x, y=y, color=hue, title=title, barmode="group",
                     hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence)
    elif kind == "scatter":
        fig = px.scatter(data, x=x, y=y, color=hue, title=title, opacity=0.7,
                         hover_data=hover_cols, marginal_x="box", marginal_y="box",
                         color_discrete_sequence=color_discrete_sequence)
    elif kind == "box":
        fig = px.box(data, x=x, y=y, color=hue, title=title, points="all",
                     hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence)
    else:
        fig = px.line(data, x=x, y=y, title=title,
                      hover_data=hover_cols, color_discrete_sequence=color_discrete_sequence)
    fig.update_layout(template="plotly_white", height=600,
                      legend_title_text=hue or "",
                      xaxis_title=x.replace("_", " ").title(),
                      yaxis_title=y.replace("_", " ").title())
    return fig


def create_hourly_line_plot(hr: pd.DataFrame, title: str = "Avg Infusions by Hour of Session"):
    """Mean infusion events per hour (Per Subject tracking)."""
    if hr.empty or "infusion_events" not in hr.columns:
        return go.Figure().update_layout(title=f"{title} — No Data")

    if "session_day" in hr.columns and "start_date" in hr.columns:
        n_sessions = (
            hr.groupby("canonical_subject")
            .apply(lambda x: x[["start_date", "session_day"]].drop_duplicates().shape[0])
            .reset_index(name="n_sessions")
        )
    elif "start_date" in hr.columns:
        n_sessions = hr.groupby("canonical_subject")["start_date"].nunique().reset_index(name="n_sessions")
    else:
        n_sessions = hr.groupby("canonical_subject").size().reset_index(name="n_sessions")

    sum_by_hour = hr.groupby(["canonical_subject", "hour"])["infusion_events"].sum().reset_index(name="total_infusion_events")
    agg = sum_by_hour.merge(n_sessions, on="canonical_subject", how="left")
    agg["avg_infusion_events"] = agg["total_infusion_events"] / agg["n_sessions"]
    agg = agg.sort_values(["canonical_subject", "hour"])

    fig = px.line(agg, x="hour", y="avg_infusion_events",
                  color="canonical_subject", title=title, markers=True,
                  hover_data={"total_infusion_events": True, "n_sessions": True},
                  color_discrete_sequence=LYNCH_COLORS)
    fig.update_layout(template="plotly_white", height=600,
                      xaxis_title="Hour of Session",
                      yaxis_title="Avg Infusion Events (per session)",
                      legend_title_text="Subject",
                      xaxis=dict(dtick=1))
    return fig


def create_cohort_hourly_line_plot(hr: pd.DataFrame, split_by_gender: bool = False):
    """Cohort average of infusions per hour (Mean ± SEM)."""
    if hr.empty or "infusion_events" not in hr.columns:
        return go.Figure().update_layout(title="Cohort Hourly Averages — No Data")

    date_col = get_date_column(hr) or "start_date"
    if "session_day" in hr.columns and "start_date" in hr.columns:
        n_sess = hr.groupby(["canonical_subject", "gender"]).apply(lambda x: x[["start_date", "session_day"]].drop_duplicates().shape[0]).reset_index(name="n_sessions")
    else:
        n_sess = hr.groupby(["canonical_subject", "gender"])[date_col].nunique().reset_index(name="n_sessions")

    subj_hr = hr.groupby(["canonical_subject", "gender", "hour"])["infusion_events"].sum().reset_index(name="total_inf")
    subj_hr = subj_hr.merge(n_sess, on=["canonical_subject", "gender"])
    subj_hr["subj_avg"] = subj_hr["total_inf"] / subj_hr["n_sessions"]

    grp_cols = ["hour"]
    if split_by_gender and "gender" in subj_hr.columns:
        grp_cols.append("gender")

    cohort_hr = subj_hr.groupby(grp_cols)["subj_avg"].agg(["mean", "sem"]).reset_index()
    cohort_hr["sem"] = cohort_hr["sem"].fillna(0)

    fig = go.Figure()

    if split_by_gender and "gender" in cohort_hr.columns:
        colors = {"Male": "rgb(31, 119, 180)", "Female": "rgb(227, 119, 194)", "Unknown": "rgb(127, 127, 127)"}
        for g, grp in cohort_hr.groupby("gender"):
            c = colors.get(g, "rgb(100,100,100)")
            c_rgba = c.replace("rgb", "rgba").replace(")", ", 0.2)")
            x, y, sem = grp["hour"], grp["mean"], grp["sem"]
            fig.add_trace(go.Scatter(name=f"{g} Mean", x=x, y=y, customdata=sem, mode="lines+markers", line=dict(color=c), hovertemplate="Hour: %{x}<br>Avg: %{y:.2f} ± %{customdata:.2f}"))
            fig.add_trace(go.Scatter(name=f"{g} Upper", x=x, y=y + sem, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(name=f"{g} Lower", x=x, y=y - sem, mode="lines", line=dict(width=0), fillcolor=c_rgba, fill="tonexty", showlegend=False, hoverinfo="skip"))
        title_text = "Cohort Hourly Average by Gender (Mean ± SEM)"
    else:
        x, y, sem = cohort_hr["hour"], cohort_hr["mean"], cohort_hr["sem"]
        c = "rgb(31, 119, 180)"
        c_rgba = "rgba(31, 119, 180, 0.2)"
        fig.add_trace(go.Scatter(name="Cohort Mean", x=x, y=y, customdata=sem, mode="lines+markers", line=dict(color=c), hovertemplate="Hour: %{x}<br>Avg: %{y:.2f} ± %{customdata:.2f}"))
        fig.add_trace(go.Scatter(name="Upper Bound", x=x, y=y + sem, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(name="Lower Bound", x=x, y=y - sem, mode="lines", line=dict(width=0), fillcolor=c_rgba, fill="tonexty", showlegend=False, hoverinfo="skip"))
        title_text = "Cohort Average Infusions by Hour"

    fig.update_layout(title=title_text, xaxis_title="Hour of Session", yaxis_title="Average Infusions",
                      template="plotly_white", hovermode="x unified", xaxis=dict(dtick=1),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def create_hourly_heatmap(hr: pd.DataFrame):
    """Heatmap showing AVERAGE infusion events per hour per subject."""
    if hr.empty or "infusion_events" not in hr.columns:
        return go.Figure().update_layout(title="Hourly Infusion Heatmap — No Data")

    if "session_day" in hr.columns and "start_date" in hr.columns:
        n_sessions = hr.groupby("canonical_subject").apply(lambda x: x[["start_date", "session_day"]].drop_duplicates().shape[0]).reset_index(name="n_sessions")
    elif "start_date" in hr.columns:
        n_sessions = hr.groupby("canonical_subject")["start_date"].nunique().reset_index(name="n_sessions")
    else:
        n_sessions = hr.groupby("canonical_subject").size().reset_index(name="n_sessions")

    sum_pivot = hr.groupby(["canonical_subject", "hour"])["infusion_events"].sum().unstack(fill_value=0)
    n_map = n_sessions.set_index("canonical_subject")["n_sessions"]
    avg_pivot = sum_pivot.div(n_map, axis=0)

    fig = px.imshow(avg_pivot,
                    title="Avg Hourly Infusions per Session",
                    aspect="auto", color_continuous_scale="Blues",
                    labels=dict(x="Hour of Session", y="Subject", color="Avg Infusions / Session"))
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
    is_int = _is_integer_day_column(sess, date_col)
    xaxis_cfg = dict(tickangle=45, rangeslider_visible=True)
    if not is_int:
        xaxis_cfg["tickformat"] = "%Y-%m-%d"
    fig = px.line(sess, x=date_col, y="cumulative_infusions",
                  color="canonical_subject", title="Cumulative Infusions Over Time",
                  markers=True,
                  hover_data=["infusions", "active_presses", "program_name", "gender"],
                  color_discrete_sequence=LYNCH_COLORS)
    fig.update_layout(xaxis_title="Session Day" if is_int else "Date",
                      yaxis_title="Cumulative Infusions",
                      template="plotly_white", hovermode="x unified",
                      xaxis=xaxis_cfg,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def create_cohort_discrimination_plot(sess: pd.DataFrame, split_by_gender: bool = False):
    """Cohort average discrimination plot (Mean ± SEM) per session."""
    if sess.empty or "active_presses" not in sess.columns:
        return go.Figure().update_layout(title="Cohort Discrimination — No Data")
    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Cohort Discrimination — No Date Column")

    grp_cols = [date_col]
    if split_by_gender and "gender" in sess.columns:
        grp_cols.append("gender")

    df_melt = sess.melt(id_vars=grp_cols + ["canonical_subject"],
                        value_vars=["active_presses", "inactive_presses"],
                        var_name="Lever", value_name="Presses")
    df_melt["Lever"] = df_melt["Lever"].str.replace("_presses", "").str.title()

    agg = df_melt.groupby(grp_cols + ["Lever"])["Presses"].agg(["mean", "sem"]).reset_index()
    agg["sem"] = agg["sem"].fillna(0)

    is_int = _is_integer_day_column(sess, date_col)
    if not is_int:
        agg[date_col] = pd.to_datetime(agg[date_col]).dt.strftime("%Y-%m-%d")

    if split_by_gender and "gender" in agg.columns:
        fig = px.bar(agg, x=date_col, y="mean", color="Lever", facet_row="gender",
                     barmode="group", error_y="sem",
                     title="Average Discrimination by Gender",
                     color_discrete_sequence=LYNCH_COLORS)
    else:
        fig = px.bar(agg, x=date_col, y="mean", color="Lever",
                     barmode="group", error_y="sem",
                     title="Cohort Average Discrimination (Mean ± SEM)",
                     color_discrete_sequence=LYNCH_COLORS)

    fig.update_layout(template="plotly_white", height=600 if split_by_gender else 400,
                      xaxis_title="Session Day" if is_int else "Date",
                      yaxis_title="Average Presses")
    # Remove the "gender=" prefix from plotly facets
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


def create_discrimination_plot(sess: pd.DataFrame):
    """Faceted Individual subject discrimination plot."""
    if sess.empty or "active_presses" not in sess.columns:
        return go.Figure().update_layout(title="Active vs Inactive Discrimination — No Data")
    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Discrimination Plot — No Date Column")
    df_melt = sess.melt(id_vars=[date_col, "canonical_subject"],
                        value_vars=["active_presses", "inactive_presses"],
                        var_name="Lever", value_name="Presses")
    df_melt["Lever"] = df_melt["Lever"].str.replace("_presses", "").str.title()
    fig = px.bar(df_melt, x=date_col, y="Presses", color="Lever",
                 barmode="group", facet_col="canonical_subject", facet_col_wrap=3,
                 title="Individual Lever Discrimination per Session")
    fig.update_layout(template="plotly_white", height=600)
    return fig


def create_pr_breakpoint_plot(sess: pd.DataFrame):
    if sess.empty or "breakpoints" not in sess.columns or sess["breakpoints"].sum() == 0:
        return go.Figure().update_layout(title="Progressive Ratio Breakpoints (No PR Data)")
    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="PR Breakpoint Plot — No Date Column")
    return create_interactive_plot(sess, date_col, "breakpoints",
                                   "PR Breakpoint Evolution",
                                   hue="canonical_subject", kind="line")


def create_response_rate_plot(sess: pd.DataFrame):
    if sess.empty or "active_presses" not in sess.columns:
        return go.Figure().update_layout(title="Response Rate (Presses/Hour) — No Data")
    date_col = get_date_column(sess)
    if date_col is None:
        return go.Figure().update_layout(title="Response Rate Plot — No Date Column")
    rate = sess.copy()
    rate["response_rate"] = rate["active_presses"] / ((rate["duration_sec"] / 3600) + 1e-6)
    return create_interactive_plot(rate, date_col, "response_rate",
                                   "Response Rate (Active Presses per Hour)",
                                   hue="canonical_subject", kind="line")


def create_efficiency_trend(daily: pd.DataFrame):
    """Line plot showing Efficiency (Total Infusions / (Total Active Presses + 1))."""
    if daily.empty or "total_active_presses" not in daily.columns:
        return go.Figure().update_layout(title="Efficiency Trend — No Data")
    date_col = get_date_column(daily)
    if date_col is None:
        return go.Figure().update_layout(title="Efficiency Trend — No Date Column")
    df = daily.copy()
    df["efficiency"] = df["total_infusions"] / (df["total_active_presses"] + 1)
    return create_interactive_plot(
        df, x=date_col, y="efficiency", title="Efficiency Trend (Rewards / Effort)",
        hue="canonical_subject", kind="line"
    )


def create_within_session_plot(active_timestamps, duration=None):
    """Cumulative step-plot of active/infusion responses within one session."""
    import numpy as np
    if not isinstance(active_timestamps, list) or len(active_timestamps) == 0:
        return go.Figure().update_layout(title="No active response timepoints available.")
    y_vals = np.arange(1, len(active_timestamps) + 1)
    fig = go.Figure(go.Scatter(x=active_timestamps, y=y_vals,
                               mode="lines+markers", line_shape="hv",
                               name="Active Responses",
                               line=dict(color="rgb(31, 119, 180)", width=2)))
    max_time = max(active_timestamps) * 1.05
    if duration and duration > 0:
        max_time = max(max_time, duration)
    fig.update_layout(title="Within-Session Timepoint Data: Active Responses",
                      xaxis_title="Time in Session (seconds)",
                      yaxis_title="Cumulative Active Responses",
                      xaxis=dict(range=[0, max_time]),
                      template="plotly_white", hovermode="x unified")
    return fig


def create_mean_sem_trajectory(daily: pd.DataFrame, split_by_gender: bool = False):
    """Cohort average trajectory (Mean ± SEM) with optional gender splitting."""
    if daily.empty or "total_infusions" not in daily.columns:
        return go.Figure().update_layout(title="No data — Cohort Average Trajectory")
    date_col = get_date_column(daily)
    if date_col is None:
        return go.Figure().update_layout(title="Cohort Average Trajectory — No Date Column")

    grp_cols = [date_col]
    if split_by_gender and "gender" in daily.columns:
        grp_cols.append("gender")

    mean_df = (
        daily.groupby(grp_cols)["total_infusions"]
        .agg(["mean", "sem"]).reset_index()
        .rename(columns={date_col: "x_val"})
    )
    mean_df["sem"] = mean_df["sem"].fillna(0)

    use_dates = not _is_integer_day_column(daily, date_col)
    if use_dates:
        mean_df["x_val"] = pd.to_datetime(mean_df["x_val"], errors="coerce")
        mean_df = mean_df.dropna(subset=["x_val"])
        hover_tmpl = "Date: %{x|%Y-%m-%d}<br>Mean: %{y:.2f} ± %{customdata:.2f}<extra></extra>"
        x_label, tick_fmt = "Date", "%Y-%m-%d"
    else:
        mean_df["x_val"] = mean_df["x_val"].astype(int)
        hover_tmpl = "Session Day: %{x}<br>Mean: %{y:.2f} ± %{customdata:.2f}<extra></extra>"
        x_label, tick_fmt = "Session Day", None

    if mean_df.empty:
        return go.Figure().update_layout(title="Cohort Average Trajectory — No Valid Data")

    fig = go.Figure()

    if split_by_gender and "gender" in mean_df.columns:
        colors = {"Male": "rgb(31, 119, 180)", "Female": "rgb(227, 119, 194)", "Unknown": "rgb(127, 127, 127)"}
        for g, grp in mean_df.groupby("gender"):
            c = colors.get(g, "rgb(100,100,100)")
            c_rgba = c.replace("rgb", "rgba").replace(")", ", 0.2)")
            x, y, sem = grp["x_val"], grp["mean"], grp["sem"]
            fig.add_trace(go.Scatter(name=f"{g} Mean", x=x, y=y, customdata=sem, mode="lines+markers", line=dict(color=c), hovertemplate=hover_tmpl))
            fig.add_trace(go.Scatter(name=f"{g} Upper", x=x, y=y + sem, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(name=f"{g} Lower", x=x, y=y - sem, mode="lines", line=dict(width=0), fillcolor=c_rgba, fill="tonexty", showlegend=False, hoverinfo="skip"))
        title_text = "Cohort Trajectory by Gender (Mean ± SEM)"
    else:
        x, y, sem = mean_df["x_val"], mean_df["mean"], mean_df["sem"]
        c = "rgb(31, 119, 180)"
        c_rgba = "rgba(31, 119, 180, 0.2)"
        fig.add_trace(go.Scatter(name="Cohort Mean", x=x, y=y, customdata=sem, mode="lines+markers", line=dict(color=c), hovertemplate=hover_tmpl))
        fig.add_trace(go.Scatter(name="Upper Bound", x=x, y=y + sem, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(name="Lower Bound", x=x, y=y - sem, mode="lines", line=dict(width=0), fillcolor=c_rgba, fill="tonexty", showlegend=False, hoverinfo="skip"))
        title_text = "Cohort Average Trajectory (Mean ± SEM)"

    xaxis_cfg = dict(tickangle=45, rangeslider_visible=True)
    if tick_fmt:
        xaxis_cfg["tickformat"] = tick_fmt
    fig.update_layout(title=title_text, xaxis_title=x_label, yaxis_title="Infusions (Mean ± SEM)",
                      template="plotly_white", hovermode="x unified", xaxis=xaxis_cfg,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig
