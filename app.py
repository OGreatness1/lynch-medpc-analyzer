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

from parser import MedPCParser
from analyzer import process_sessions, generate_pattern_flags, create_daily_summary, report_missing_and_box_room
from plotter import (
    create_plot, create_interactive_plot,
    create_cumulative_plot, create_discrimination_plot,
    create_pr_breakpoint_plot, create_efficiency_trend,
    create_response_rate_plot, create_hourly_heatmap,
    create_mean_sem_trajectory,
    create_within_session_plot
)
from utils import canonicalize_id

# ─── V3 FIX: Safe df_hr checker to prevent NoneType crashes ───
def _hr_ok(df_hr) -> bool:
    """Return True only if df_hr is a non-None, non-empty DataFrame."""
    return df_hr is not None and isinstance(df_hr, pd.DataFrame) and not df_hr.empty

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
        st.stop()

st.set_page_config(page_title="Lynch Lab MedPC Analyzer", page_icon="🧬", layout="wide")

if 'df_sess' not in st.session_state:
    st.session_state.update({
        'df_sess': None,
        'df_hr': None,
        'found_ids': None,
        'skipped_report': None,
        'analysis_run': False
    })

st.title("🧬 Lynch Lab MedPC Analyzer (Version 3)")
st.markdown("**Robust parsing • Custom flags & thresholds • Cohort filtering • Per-program exports**")

with st.sidebar:
    st.header("Upload Config (Optional)")
    settings_file = st.file_uploader("settings.json (custom MSN & mappings)", type=["json"])
    st.header("Allowed / Expected IDs")
    id_file = st.file_uploader("ID list (.txt)", type=["txt"])
    st.header("Data Files")
    data_files = st.file_uploader("MedPC .txt / .zip files", accept_multiple_files=True)

    st.header("Cohort Hard-Filter")
    include_mice = st.checkbox("Include Mice (G126 / G126A / G126B)", value=True)
    cohort_options = ["G136A", "G136B", "G140A", "G140B", "G126", "G126A", "G126B", "All Others"]
    default_cohorts = ["G126", "G126A", "G126B", "G136A", "G136B", "G140A", "G140B", "All Others"] if include_mice else cohort_options
    selected_cohorts = st.multiselect("Only include these cohorts", cohort_options, default=default_cohorts)
    if include_mice:
        mouse_cohorts = {"G126", "G126A", "G126B"}
        selected_cohorts = list(set(selected_cohorts) | mouse_cohorts)

    st.header("Custom Flag Thresholds")
    min_active_presses = st.slider("Min active presses (low activity)", 0, 50, 5)
    max_inactive_ratio = st.slider("Max inactive/active ratio", 0.0, 2.0, 0.4, 0.05)
    min_session_min = st.slider("Min session length (minutes)", 5, 120, 20)
    escalation_pct = st.slider("Escalation detection threshold (%)", 10, 100, 30)

    st.header("Intake Estimate Settings")
    drug_type = st.selectbox("Drug type for intake estimate", ["None", "Cocaine", "Fentanyl", "Nicotine"])
    avg_weight_g = st.number_input("Average subject weight (g)", min_value=100, max_value=600, value=300, step=10)
    conc_mgml = 1.0
    if drug_type == "Cocaine":
        conc_mgml = st.number_input("Cocaine concentration (mg/ml)", 0.1, 10.0, 1.0, 0.1)
    elif drug_type == "Fentanyl":
        conc_mgml = st.number_input("Fentanyl concentration (mg/ml)", 0.001, 0.1, 0.01, 0.001, format="%.4f")
    elif drug_type == "Nicotine":
        conc_mgml = st.number_input("Nicotine concentration (mg/ml)", 0.01, 1.0, 0.2, 0.01)

    show_debug = st.checkbox("Show skipped sessions & raw debug", False)

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
            except Exception as e:
                st.warning(f"Settings.json invalid → {e}")

        allowed_raw = set()
        if id_file:
            allowed_raw = {line.decode("utf-8", errors="ignore").strip() for line in id_file if line.strip()}
        allowed_canon = {canonicalize_id(x) for x in allowed_raw if x}

        parser = MedPCParser()
        all_sessions = []
        prog_bar = st.progress(0)
        status = st.empty()

        for i, f in enumerate(data_files):
            status.text(f"Parsing {f.name} ({i+1}/{len(data_files)})")
            try:
                content = f.getvalue().decode("utf-8", errors="replace")
                all_sessions.extend(parser.parse_file(content, f.name))
            except Exception as e:
                st.warning(f"Parse error in {f.name}: {e}")
            prog_bar.progress((i+1)/len(data_files))

        status.text("Running behavioral analysis...")
        df_sess, df_hr, found_ids = process_sessions(
            all_sessions, allowed_ids=allowed_canon or None,
            custom_patterns=custom_patterns, custom_mappings=custom_mappings,
            drug_type=drug_type, avg_weight_g=avg_weight_g, conc_mgml=conc_mgml
        )

        if "All Others" not in selected_cohorts:
            cohort_pattern = '|'.join(selected_cohorts)
            mask = df_sess["canonical_subject"].str.contains(cohort_pattern, case=False, na=False)
            df_sess = df_sess[mask].copy()
            if _hr_ok(df_hr):
                df_hr = df_hr[df_hr["canonical_subject"].isin(df_sess["canonical_subject"])].copy()

        df_sess = generate_pattern_flags(
            df_sess, min_active=min_active_presses, max_inactive_ratio=max_inactive_ratio,
            min_duration_min=min_session_min, escalation_threshold=escalation_pct
        )

        st.session_state.update({
            'df_sess': df_sess, 'df_hr': df_hr, 'found_ids': found_ids,
            'skipped_report': parser.get_skipped_report(), 'analysis_run': True
        })
        st.rerun()

if 'df_sess' in st.session_state and st.session_state.df_sess is not None and not st.session_state.df_sess.empty:
    df_sess = st.session_state.df_sess
    df_hr   = st.session_state.df_hr
    found_ids = st.session_state.found_ids
    skipped  = st.session_state.skipped_report

    if df_sess.empty:
        st.warning("No data matched your filters / ID list.")
    else:
        st.header("Subject Coverage & Box/Room")
        report_missing_and_box_room(set(), found_ids, df_sess)

        col1, col2, col3 = st.columns(3)
        col1.metric("Unique Subjects", len(found_ids))
        col2.metric("Total Sessions", len(df_sess))
        col3.metric("Skipped Files", len(skipped), delta_color="inverse")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            if skipped:
                pd.DataFrame(skipped).to_excel("00_Skipped_Log.xlsx", index=False)
                zf.write("00_Skipped_Log.xlsx")

            for prog in df_sess["program_name"].unique():
                safe = re.sub(r"[^A-Za-z0-9_]", "_", prog)
                sub_s = df_sess[df_sess["program_name"] == prog]
                sub_h = df_hr[df_hr["program_name"] == prog] if _hr_ok(df_hr) else pd.DataFrame()
                daily = create_daily_summary(sub_s)

                excel_buf = io.BytesIO()
                with pd.ExcelWriter(excel_buf, engine="openpyxl") as w:
                    sub_s.to_excel(w, sheet_name="Sessions", index=False)
                    if _hr_ok(sub_h): sub_h.to_excel(w, sheet_name="Hourly", index=False)
                    if not daily.empty: daily.to_excel(w, sheet_name="Daily", index=False)
                    generate_pattern_flags(sub_s).to_excel(w, sheet_name="Flags", index=False)
                zf.writestr(f"{safe}_Full_Analysis.xlsx", excel_buf.getvalue())

                # ───── Matplotlib plots saved to ZIP ─────
                plot_list = []

                if not daily.empty:
                    buf = create_plot(
                        daily, "session_day", "total_infusions",
                        f"Daily Infusions - {prog}", "canonical_subject", kind="line"
                    )
                    if buf:
                        plot_list.append((buf, "01_Daily_Infusions_Line"))

                if _hr_ok(sub_h):
                    buf = create_plot(
                        sub_h, "hour", "infusion_events",
                        f"Hourly Infusions - {prog}", "canonical_subject"
                    )
                    if buf:
                        plot_list.append((buf, "02_Hourly_Infusions"))

                    # ─── RESTORED: Hourly Active Presses Export ───
                    buf = create_plot(
                        sub_h, "hour", "active_events",
                        f"Hourly Active Presses - {prog}", "canonical_subject"
                    )
                    if buf:
                        plot_list.append((buf, "03_Hourly_Active"))
        st.download_button("📥 Download ZIP (All Programs + Plots + Logs)", zip_buffer.getvalue(), f"MedPC_{datetime.now():%Y%m%d_%H%M}.zip", "application/zip")
        st.success("Analysis complete!")

        st.header("Live Dashboard")
        tab_cohort, tab_advanced, tab_subject = st.tabs(["Cohort View", "Cross-Program", "Single Subject"])

        with tab_cohort:
            programs = sorted(df_sess["program_name"].unique())
            prog_tabs = st.tabs([f"🧪 {p}" for p in programs])
            for tab_idx, (tab, p) in enumerate(zip(prog_tabs, programs)):
                with tab:
                    sub_s = df_sess[df_sess["program_name"] == p].copy()
                    sub_h = df_hr[df_hr["program_name"] == p].copy() if _hr_ok(df_hr) else pd.DataFrame()
                    daily = create_daily_summary(sub_s)
                    c1, c2 = st.columns(2)
                    with c1:
                        if not daily.empty:
                            st.plotly_chart(create_interactive_plot(daily, "session_day", "total_infusions", f"Daily Infusions — {p}", "canonical_subject", kind="line"), use_container_width=True, key=f"d_{p}_{tab_idx}")
                            st.plotly_chart(create_mean_sem_trajectory(daily), use_container_width=True, key=f"ms_{p}_{tab_idx}")
                    with c2:
                        if _hr_ok(sub_h):
                            st.plotly_chart(create_interactive_plot(sub_h, "hour", "infusion_events", f"Hourly Infusions — {p}", "canonical_subject", kind="line"), use_container_width=True, key=f"hi_{p}_{tab_idx}")
                            st.plotly_chart(create_hourly_heatmap(sub_h), use_container_width=True, key=f"hm_{p}_{tab_idx}")

        with tab_advanced:
            st.plotly_chart(create_cumulative_plot(df_sess), use_container_width=True, key="c_all")
            st.plotly_chart(create_discrimination_plot(df_sess), use_container_width=True, key="d_all")

        with tab_subject:
            # ─── V3 FIX: Safe handling of found_ids for selectbox ───
            if not found_ids:
                st.info("No subjects found to display.")
            else:
                sel = st.selectbox("Select Subject", sorted(found_ids or set()))
                if sel:
                    subject_sess = df_sess[df_sess["canonical_subject"] == sel].copy()
                    subject_hr = df_hr[df_hr["canonical_subject"] == sel].copy() if _hr_ok(df_hr) else pd.DataFrame()

                    if subject_sess.empty:
                        st.warning(f"No sessions found for subject {sel}.")
                    else:
                        st.subheader(f"Overview for {sel}")
                        programs = sorted(subject_sess["program_name"].unique())
                        prog_tabs = st.tabs([f"🧪 {p}" for p in programs])

                        for tab_idx, (tab, p) in enumerate(zip(prog_tabs, programs)):
                            with tab:
                                prog_sess = subject_sess[subject_sess["program_name"] == p].copy()
                                prog_hr = subject_hr[subject_hr["program_name"] == p].copy() if _hr_ok(subject_hr) else pd.DataFrame()
                                prog_daily = create_daily_summary(prog_sess)

                                col1, col2, col3 = st.columns(3)
                                col1.metric("Sessions", len(prog_sess))
                                col2.metric("Total Infusions", prog_sess["infusions"].sum())
                                col3.metric("Active Presses", prog_sess["active_presses"].sum())

                                if not prog_daily.empty:
                                    st.plotly_chart(create_interactive_plot(prog_daily, "session_day", "total_infusions", f"Daily Infusions — {p}", hue=None, kind="line"), use_container_width=True, key=f"p_d_{sel}_{p}_{tab_idx}")
                                if _hr_ok(prog_hr):
                                    st.plotly_chart(create_hourly_heatmap(prog_hr), use_container_width=True, key=f"p_h_{sel}_{p}_{tab_idx}")

                                if not prog_sess.empty:
                                    st.plotly_chart(create_cumulative_plot(prog_sess), use_container_width=True, key=f"p_c_{sel}_{p}_{tab_idx}")
                                    if "active_presses" in prog_sess.columns:
                                        st.plotly_chart(create_discrimination_plot(prog_sess), use_container_width=True, key=f"p_dis_{sel}_{p}_{tab_idx}")
                                        st.plotly_chart(create_response_rate_plot(prog_sess), use_container_width=True, key=f"p_rr_{sel}_{p}_{tab_idx}")
                                    if "breakpoint" in prog_sess.columns and prog_sess["breakpoint"].sum() > 0:
                                        st.plotly_chart(create_pr_breakpoint_plot(prog_sess), use_container_width=True, key=f"p_pr_{sel}_{p}_{tab_idx}")
                                
                                st.subheader(f"Within-Session Timepoint Data — {p}")
                                if "active_timestamps" in prog_sess.columns and "session_day" in prog_sess.columns:
                                    session_options = prog_sess['session_day'].astype(str) + " (" + prog_sess['start_date'].dt.date.astype(str) + ")"
                                    selected_session = st.selectbox("Select session to view timepoints:", options=session_options, key=f"ts_{sel}_{p}_{tab_idx}")
                                    if selected_session:
                                        sel_day = int(selected_session.split(" ")[0])
                                        session_data_row = prog_sess[prog_sess['session_day'] == sel_day].iloc[0]
                                        fig_ts = create_within_session_plot(session_data_row.get("active_timestamps", []), session_data_row.get("duration_sec", 0))
                                        st.plotly_chart(fig_ts, use_container_width=True, key=f"ts_p_{sel}_{p}_{tab_idx}")
                                else:
                                    st.info("Timepoint arrays not mapped for this program.")

                                st.subheader(f"Sessions — {p}")
                                st.dataframe(prog_sess)
