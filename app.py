import streamlit as st
import pandas as pd
import re
import io
import zipfile
import json
from datetime import datetime
import warnings
import hashlib

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# set_page_config MUST be the very first Streamlit call — before any other
# st.* call, including those in the auth block below.
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Lynch Lab MedPC Analyzer", page_icon="🧬", layout="wide")

from parser import MedPCParser
from analyzer import (
    process_sessions, generate_pattern_flags,
    create_daily_summary, report_missing_and_box_room,
)
from plotter import (
    create_plot, create_interactive_plot,
    create_cumulative_plot, create_discrimination_plot,
    create_pr_breakpoint_plot, create_efficiency_trend,
    create_response_rate_plot, create_hourly_heatmap,
    create_hourly_line_plot,
    create_mean_sem_trajectory,
    create_within_session_plot,
)
from utils import canonicalize_id

# ─────────────────────────────────────────────────────────────────────────────
# Password protection
# ─────────────────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Lynch Lab MedPC Analyzer – Login")
    st.markdown("Lab members only – restricted access")
    pw = st.text_input("Password", type="password", placeholder="••••••••")
    if pw:
        input_hash = hashlib.sha256(pw.encode()).hexdigest()
        if input_hash == st.secrets["app_password_hash"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
            st.stop()
    else:
        st.info("Please enter the lab password to continue.")
        st.markdown("Forgot password? Contact the lab manager.")
        st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Authenticated — initialise session state
# ─────────────────────────────────────────────────────────────────────────────
if "df_sess" not in st.session_state:
    st.session_state.update({
        "df_sess":        None,
        "df_hr":          None,
        "found_ids":      None,
        "skipped_report": None,
        "analysis_run":   False,
    })

st.title("🧬 Lynch Lab MedPC Analyzer")
st.markdown("**Robust parsing • Custom flags & thresholds • Cohort filtering • Per-program exports**")

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Upload Config (Optional)")
    settings_file = st.file_uploader("settings.json (custom MSN & mappings)", type=["json"])

    st.header("Allowed / Expected IDs")
    id_file = st.file_uploader("ID list (.txt)", type=["txt"])

    st.header("Data Files")
    # No type= restriction — MedPC files are often extensionless.
    # ZIP files are detected by magic bytes, not filename.
    data_files = st.file_uploader(
        "MedPC data files (.txt, .zip, or extensionless)",
        accept_multiple_files=True,
    )

    st.header("Cohort Hard-Filter")
    include_mice = st.checkbox("Include Mice (G126 / G126A / G126B)", value=True)

    cohort_options = [
        "G136A", "G136B", "G140A", "G140B",
        "G126", "G126A", "G126B",
        "All Others",
    ]
    default_cohorts = (
        ["G126", "G126A", "G126B", "G136A", "G136B", "G140A", "G140B", "All Others"]
        if include_mice else cohort_options
    )
    selected_cohorts = st.multiselect(
        "Only include these cohorts", cohort_options, default=default_cohorts
    )
    if include_mice:
        selected_cohorts = list(set(selected_cohorts) | {"G126", "G126A", "G126B"})

    st.header("Custom Flag Thresholds")
    min_active_presses = st.slider("Min active presses (low activity)", 0, 50, 5)
    max_inactive_ratio = st.slider("Max inactive/active ratio", 0.0, 2.0, 0.4, 0.05)
    min_session_min    = st.slider("Min session length (minutes)", 5, 120, 20)
    escalation_pct     = st.slider("Escalation detection threshold (%)", 10, 100, 30)

    st.header("Intake Estimate Settings")
    drug_type = st.selectbox(
        "Drug type for intake estimate", ["None", "Cocaine", "Fentanyl", "Nicotine"],
        help="Selects the correct infusion duration lookup table",
    )
    avg_weight_g = st.number_input(
        "Average subject weight (g)", min_value=100, max_value=600, value=300, step=10,
        help="Used for infusion duration lookup (rounded to nearest 10 g)",
    )

    conc_mgml = 1.0
    if drug_type == "Cocaine":
        conc_mgml = st.number_input(
            "Cocaine concentration (mg/ml)", min_value=0.1, max_value=10.0,
            value=1.0, step=0.1, help="Concentration in syringe — used for mg/kg intake",
        )
    elif drug_type == "Fentanyl":
        conc_mgml = st.number_input(
            "Fentanyl concentration (mg/ml)", min_value=0.001, max_value=0.1,
            value=0.01, step=0.001, format="%.4f",
            help="Concentration in syringe — used for mg/kg intake",
        )
    elif drug_type == "Nicotine":
        conc_mgml = st.number_input(
            "Nicotine concentration (mg/ml)", min_value=0.01, max_value=1.0,
            value=0.2, step=0.01, help="Concentration in syringe — used for mg/kg intake",
        )

    show_debug = st.checkbox("Show skipped sessions & raw debug", False)

# ─────────────────────────────────────────────────────────────────────────────
# Run Analysis
# ─────────────────────────────────────────────────────────────────────────────
if st.button("🚀 Run Analysis", type="primary"):
    if not data_files:
        st.error("Upload at least one data file.")
    else:
        custom_patterns = custom_mappings = None
        if settings_file:
            try:
                s = json.load(settings_file)
                custom_patterns = s.get("msn_patterns")
                custom_mappings = s.get("variable_mappings")
                st.success("Custom MSN patterns & mappings loaded")
            except Exception as e:
                st.warning(f"Settings.json invalid → {e}")

        allowed_raw = set()
        if id_file:
            allowed_raw = {
                line.decode("utf-8", errors="ignore").strip()
                for line in id_file if line.strip()
            }
        allowed_canon = {canonicalize_id(x) for x in allowed_raw if x}

        parser       = MedPCParser()
        all_sessions = []
        prog_bar     = st.progress(0)
        status       = st.empty()

        for i, f in enumerate(data_files):
            status.text(f"Parsing {f.name} ({i + 1}/{len(data_files)})")
            try:
                raw_bytes = f.getvalue()

                # Detect ZIP by magic bytes (PK\x03\x04) — more reliable
                # than checking the filename extension, and works for
                # extensionless or misnamed files.
                if raw_bytes[:4] == b"PK\x03\x04":
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                        for inner_name in zf.namelist():
                            # Parse every file inside the ZIP regardless of
                            # extension — MedPC files often have none.
                            if not inner_name.endswith("/"):
                                try:
                                    inner_content = zf.read(inner_name).decode(
                                        "utf-8", errors="replace"
                                    )
                                    all_sessions.extend(
                                        parser.parse_file(
                                            inner_content, f"{f.name}/{inner_name}"
                                        )
                                    )
                                except Exception as ie:
                                    st.warning(
                                        f"Error reading {inner_name} inside {f.name}: {ie}"
                                    )
                else:
                    content = raw_bytes.decode("utf-8", errors="replace")
                    all_sessions.extend(parser.parse_file(content, f.name))

            except Exception as e:
                st.warning(f"Parse error in {f.name}: {e}")

            prog_bar.progress((i + 1) / len(data_files))

        status.text("Running behavioral analysis…")

        df_sess, df_hr, found_ids = process_sessions(
            all_sessions,
            allowed_ids=allowed_canon or None,
            custom_patterns=custom_patterns,
            custom_mappings=custom_mappings,
            drug_type=drug_type,
            avg_weight_g=avg_weight_g,
            conc_mgml=conc_mgml,
        )

        # ── Cohort hard filter ──────────────────────────────────────────────
        # Use word-boundary anchors so G136A does not match G1364A.
        if "All Others" not in selected_cohorts and selected_cohorts:
            cohort_pattern = "|".join(
                r"(?<![A-Za-z0-9])" + re.escape(c) + r"(?![A-Za-z0-9])"
                for c in selected_cohorts
            )
            mask    = df_sess["canonical_subject"].str.contains(
                cohort_pattern, case=False, na=False, regex=True
            )
            df_sess = df_sess[mask].copy()
            if not df_hr.empty:
                df_hr = df_hr[
                    df_hr["canonical_subject"].isin(df_sess["canonical_subject"])
                ].copy()

        # ── Quality flags ───────────────────────────────────────────────────
        df_sess = generate_pattern_flags(
            df_sess,
            min_active=min_active_presses,
            max_inactive_ratio=max_inactive_ratio,
            min_duration_min=min_session_min,
            escalation_threshold=escalation_pct,
        )

        st.session_state.update({
            "df_sess":        df_sess,
            "df_hr":          df_hr,
            "found_ids":      found_ids,
            "skipped_report": parser.get_skipped_report(),
            "analysis_run":   True,
        })

        # balloons fires once here, before rerun.
        # Placing it after the rerun() would re-trigger on every tab change.
        st.balloons()
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Results Dashboard
# ─────────────────────────────────────────────────────────────────────────────
if (
    "df_sess" in st.session_state
    and st.session_state.df_sess is not None
    and not st.session_state.df_sess.empty
):
    df_sess   = st.session_state.df_sess
    df_hr     = st.session_state.df_hr
    found_ids = st.session_state.found_ids
    skipped   = st.session_state.skipped_report

    if df_sess.empty:
        st.warning("No data matched your filters / ID list.")
    else:
        st.header("Subject Coverage & Box/Room")
        report_missing_and_box_room(set(), found_ids, df_sess)

        col1, col2, col3 = st.columns(3)
        col1.metric("Unique Subjects", len(found_ids))
        col2.metric("Total Sessions",  len(df_sess))
        col3.metric("Skipped Files",   len(skipped), delta_color="inverse")

        if show_debug and skipped:
            st.subheader("Skipped Sessions Log")
            st.dataframe(pd.DataFrame(skipped))

        # ── ZIP Export (entirely in-memory — no disk writes) ───────────────
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

            if skipped:
                skip_buf = io.BytesIO()
                pd.DataFrame(skipped).to_excel(skip_buf, index=False, engine="openpyxl")
                zf.writestr("00_Skipped_Sessions_Log.xlsx", skip_buf.getvalue())

            for prog in df_sess["program_name"].unique():
                safe  = re.sub(r"[^A-Za-z0-9_]", "_", prog)
                sub_s = df_sess[df_sess["program_name"] == prog]
                sub_h = (
                    df_hr[df_hr["program_name"] == prog]
                    if not df_hr.empty else pd.DataFrame()
                )
                daily = create_daily_summary(sub_s)

                excel_buf = io.BytesIO()
                with pd.ExcelWriter(excel_buf, engine="openpyxl") as w:
                    sub_s.to_excel(w, sheet_name="Sessions", index=False)
                    if not sub_h.empty:
                        sub_h.to_excel(w, sheet_name="Hourly", index=False)
                    if not daily.empty:
                        daily.to_excel(w, sheet_name="Daily", index=False)
                    generate_pattern_flags(sub_s).to_excel(w, sheet_name="Flags", index=False)
                zf.writestr(f"{safe}_Full_Analysis.xlsx", excel_buf.getvalue())

                plot_list = []
                if not daily.empty:
                    buf = create_plot(
                        daily, "first_session_time", "total_infusions",
                        f"Daily Infusions - {prog}", "canonical_subject", kind="line",
                    )
                    if buf:
                        plot_list.append((buf, "01_Daily_Infusions_Line"))

                if not sub_h.empty:
                    buf = create_plot(
                        sub_h, "hour", "infusion_events",
                        f"Hourly Infusions - {prog}", "canonical_subject",
                    )
                    if buf:
                        plot_list.append((buf, "02_Hourly_Infusions"))
                    buf = create_plot(
                        sub_h, "hour", "active_events",
                        f"Hourly Active Presses - {prog}", "canonical_subject",
                    )
                    if buf:
                        plot_list.append((buf, "03_Hourly_Active"))

                if not sub_s.empty:
                    buf = create_plot(
                        sub_s, "active_presses", "infusions",
                        f"Efficiency - {prog}", "gender",
                        kind="scatter", style="duration_sec",
                    )
                    if buf:
                        plot_list.append((buf, "04_Efficiency_Scatter"))

                if not daily.empty and "gender" in daily.columns:
                    buf = create_plot(
                        daily, "gender", "total_infusions",
                        f"Infusions by Gender - {prog}", "gender", kind="box",
                    )
                    if buf:
                        plot_list.append((buf, "05_Infusions_by_Gender_Box"))

                for plt_buf, name in plot_list:
                    if plt_buf:
                        zf.writestr(f"Plots/{safe}/{name}.png", plt_buf.getvalue())

        st.download_button(
            "📥 Download ZIP (All Programs + Plots + Logs)",
            zip_buffer.getvalue(),
            f"MedPC_{datetime.now():%Y%m%d_%H%M}.zip",
            "application/zip",
        )
        st.success("Analysis complete!")

        # ── Live Dashboard ─────────────────────────────────────────────────
        st.header("Live Dashboard")
        tab_cohort, tab_advanced, tab_subject = st.tabs(
            ["Cohort View", "Cross-Program", "Single Subject"]
        )

        with tab_cohort:
            programs  = sorted(df_sess["program_name"].unique())
            prog_tabs = st.tabs([f"🧪 {p}" for p in programs])

            for tab_idx, (tab, p) in enumerate(zip(prog_tabs, programs)):
                with tab:
                    sub_s = df_sess[df_sess["program_name"] == p].copy()
                    sub_h = (
                        df_hr[df_hr["program_name"] == p].copy()
                        if not df_hr.empty else pd.DataFrame()
                    )
                    daily = create_daily_summary(sub_s)

                    c1, c2 = st.columns(2)
                    with c1:
                        if not daily.empty:
                            st.plotly_chart(
                                create_interactive_plot(
                                    daily, "first_session_time", "total_infusions",
                                    f"Daily Infusions — {p}", "canonical_subject", kind="line",
                                ),
                                use_container_width=True,
                                key=f"daily_inf_{p}_{tab_idx}",
                            )
                            st.plotly_chart(
                                create_mean_sem_trajectory(daily),
                                use_container_width=True,
                                key=f"mean_sem_{p}_{tab_idx}",
                            )
                    with c2:
                        if not sub_h.empty:
                            # Aggregated line plot — avoids zigzag cycling
                            st.plotly_chart(
                                create_hourly_line_plot(
                                    sub_h, f"Avg Infusions by Hour — {p}",
                                ),
                                use_container_width=True,
                                key=f"hourly_line_{p}_{tab_idx}",
                            )
                            st.plotly_chart(
                                create_hourly_heatmap(sub_h),
                                use_container_width=True,
                                key=f"hourly_heatmap_{p}_{tab_idx}",
                            )

        with tab_advanced:
            st.plotly_chart(
                create_cumulative_plot(df_sess),
                use_container_width=True, key="cumulative_all",
            )
            st.plotly_chart(
                create_discrimination_plot(df_sess),
                use_container_width=True, key="discrimination_all",
            )

        with tab_subject:
            sel = st.selectbox("Select Subject", sorted(found_ids))
            if sel:
                subject_sess = df_sess[df_sess["canonical_subject"] == sel].copy()
                subject_hr   = (
                    df_hr[df_hr["canonical_subject"] == sel].copy()
                    if not df_hr.empty else pd.DataFrame()
                )

                if subject_sess.empty:
                    st.warning(f"No sessions found for subject {sel}.")
                else:
                    gender_label = subject_sess["gender"].iloc[0]
                    st.subheader(f"Overview for {sel} ({gender_label})")

                    programs = sorted(subject_sess["program_name"].unique())
                    prog_tabs = st.tabs([f"🧪 {p}" for p in programs])

                    for tab_idx, (tab, p) in enumerate(zip(prog_tabs, programs)):
                        with tab:
                            prog_sess  = subject_sess[subject_sess["program_name"] == p].copy()
                            prog_hr    = (
                                subject_hr[subject_hr["program_name"] == p].copy()
                                if not subject_hr.empty else pd.DataFrame()
                            )
                            prog_daily = create_daily_summary(prog_sess)

                            col1, col2, col3 = st.columns(3)
                            col1.metric("Sessions",        len(prog_sess))
                            col2.metric("Total Infusions", int(prog_sess["infusions"].sum()))
                            col3.metric("Active Presses",  int(prog_sess["active_presses"].sum()))

                            if not prog_daily.empty:
                                st.plotly_chart(
                                    create_interactive_plot(
                                        prog_daily, "first_session_time", "total_infusions",
                                        f"Daily Infusions — {p} ({sel})",
                                        hue=None, kind="line",
                                    ),
                                    use_container_width=True,
                                    key=f"daily_inf_subj_{sel}_{p}_{tab_idx}",
                                )

                            if not prog_hr.empty:
                                st.plotly_chart(
                                    create_hourly_heatmap(prog_hr),
                                    use_container_width=True,
                                    key=f"hourly_heatmap_subj_{sel}_{p}_{tab_idx}",
                                )

                            st.subheader(f"Additional Plots — {p}")

                            if not prog_sess.empty:
                                st.plotly_chart(
                                    create_cumulative_plot(prog_sess),
                                    use_container_width=True,
                                    key=f"cumulative_subj_{sel}_{p}_{tab_idx}",
                                )

                            if not prog_sess.empty and "active_presses" in prog_sess.columns:
                                st.plotly_chart(
                                    create_discrimination_plot(prog_sess),
                                    use_container_width=True,
                                    key=f"discrim_subj_{sel}_{p}_{tab_idx}",
                                )
                                st.plotly_chart(
                                    create_response_rate_plot(prog_sess),
                                    use_container_width=True,
                                    key=f"resp_rate_subj_{sel}_{p}_{tab_idx}",
                                )

                            if (
                                not prog_sess.empty
                                and "breakpoints" in prog_sess.columns
                                and prog_sess["breakpoints"].sum() > 0
                            ):
                                st.plotly_chart(
                                    create_pr_breakpoint_plot(prog_sess),
                                    use_container_width=True,
                                    key=f"pr_bp_subj_{sel}_{p}_{tab_idx}",
                                )

                            if not prog_daily.empty and "total_active_presses" in prog_daily.columns:
                                st.plotly_chart(
                                    create_efficiency_trend(prog_daily),
                                    use_container_width=True,
                                    key=f"efficiency_subj_{sel}_{p}_{tab_idx}",
                                )

                            # ── Within-Session Timepoint Plot ───────────────
                            st.subheader(f"Within-Session Timepoint Data — {p}")

                            if (
                                "active_timestamps" in prog_sess.columns
                                and "session_day" in prog_sess.columns
                            ):
                                prog_sess = prog_sess.reset_index(drop=True)
                                # Use DataFrame row index as unique key to
                                # avoid collisions when two sessions share a day number
                                session_options = {
                                    f"Session {row['session_day']} "
                                    f"({pd.Timestamp(row['start_date']).date() if pd.notna(row['start_date']) else 'unknown'}) "
                                    f"— idx {idx}": idx
                                    for idx, row in prog_sess.iterrows()
                                }

                                selected_label = st.selectbox(
                                    "Select session to view active response timepoints:",
                                    options=list(session_options.keys()),
                                    key=f"ts_sel_{sel}_{p}_{tab_idx}",
                                )
                                if selected_label:
                                    row_idx          = session_options[selected_label]
                                    session_data_row = prog_sess.loc[row_idx]
                                    timestamps       = session_data_row.get("active_timestamps", [])
                                    duration         = session_data_row.get("duration_sec", 0)
                                    st.plotly_chart(
                                        create_within_session_plot(timestamps, duration),
                                        use_container_width=True,
                                        key=f"ts_plot_{sel}_{p}_{tab_idx}",
                                    )
                            else:
                                st.info(
                                    "Timepoint arrays are not available or mapped for this program."
                                )

                            st.subheader(f"Sessions — {p}")
                            st.dataframe(prog_sess)

                    st.divider()
                    st.subheader("All Programs — Quick Stats")
                    st.dataframe(
                        subject_sess[[
                            "program_name", "start_date", "end_date",
                            "infusions", "active_presses",
                        ]].sort_values("start_date")
                    )

        if st.button("🗑️ Clear & Restart"):
            for k in list(st.session_state):
                del st.session_state[k]
            st.rerun()

else:
    st.info("Upload ID list + data files, then click Run Analysis.")
