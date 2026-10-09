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

# set_page_config MUST be the very first Streamlit call.
st.set_page_config(page_title="Lynch Lab MedPC Analyzer", page_icon="🧬", layout="wide")

# ── Module version guard ─────────────────────────────────────────────────────
# app.py v7.0 needs analyzer.py v7.0 and plotter.py v7.0. If only some files are
# pushed, Python raises a bare ImportError and Streamlit Cloud redacts it, which
# makes a partial deploy look like a mystery crash. Name the offending file
# instead.
_MISSING = []
try:
    from parser import MedPCParser
except ImportError:
    _MISSING.append("parser.py")

try:
    import analyzer as _analyzer
    from analyzer import (
        process_sessions, generate_pattern_flags,
        create_daily_summary, report_missing_and_box_room,
        create_segment_summary,
    )
except ImportError as _e:
    _MISSING.append(f"analyzer.py  ({_e})")

try:
    from plotter import (
        create_plot, create_interactive_plot,
        create_cumulative_plot, create_discrimination_plot,
        create_pr_breakpoint_plot, create_efficiency_trend,
        create_response_rate_plot, create_hourly_heatmap,
        create_hourly_line_plot, create_mean_sem_trajectory,
        create_within_session_plot, create_cohort_discrimination_plot,
        create_cohort_hourly_line_plot, create_segment_plot
    )
except ImportError as _e:
    _MISSING.append(f"plotter.py  ({_e})")

try:
    from utils import canonicalize_id
except ImportError:
    _MISSING.append("utils.py")

try:
    from wide_export import parse_id_list, build_wide_workbook
except ImportError as _e:
    _MISSING.append(f"wide_export.py  ({_e})")

try:
    import ui_style
except ImportError as _e:
    _MISSING.append(f"ui_style.py  ({_e})")

try:
    from config import CONFIG_VERSION
except ImportError:
    CONFIG_VERSION = None

if _MISSING or CONFIG_VERSION != "7.3":
    st.title("Deployment is out of sync")
    st.error(
        f"This app expects every module at v{'7.3'}. "
        "The full set is **config.py, analyzer.py, app.py, parser.py, plotter.py, "
        "ui_style.py and wide_export.py** \u2014 push them together in one commit, then reboot "
        "from *Manage app \u2192 Reboot*."
    )
    st.info(
        "**\"No module named X\"** means that file is missing from the repo "
        "entirely \u2014 upload it. Any other import error means that file is "
        "present but still an older version \u2014 re-upload it."
    )
    if _MISSING:
        st.subheader("Modules that failed to import")
        for m in _MISSING:
            st.write(f"- `{m}`")
    if CONFIG_VERSION != "7.3":
        st.subheader("config.py version")
        st.write(f"Found `CONFIG_VERSION = {CONFIG_VERSION!r}`, expected `'7.3'`.")
    st.caption(
        "Streamlit Cloud redacts the real ImportError, so this check reports it directly. "
        "The most common cause is committing app.py without analyzer.py."
    )
    st.stop()
# ─────────────────────────────────────────────────────────────────────────────

def _hr_ok(df_hr) -> bool:
    return df_hr is not None and isinstance(df_hr, pd.DataFrame) and not df_hr.empty


def _short(program: str) -> str:
    """'RAT - FENTANYL FR40 LD' -> 'FENTANYL FR40 LD' for labels; mice stay marked."""
    if program.startswith("RAT - "):
        return program[6:]
    if program.startswith("MOUSE - "):
        return "🐭 " + program[8:]
    return program


# Theme-aware look and background motion (CSS only) - see ui_style.py.
ui_style.inject_global_style()

# ── Login ────────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    try:
        _pw_hash = st.secrets["app_password_hash"]
    except Exception:
        # Running locally without .streamlit/secrets.toml used to raise a raw
        # KeyError the moment a password was typed.
        _pw_hash = None

    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.write("")
        ui_style.hero("Lynch Lab · UVA", "MedPC", "Analyzer",
                      "Lab members only · restricted access")
        if _pw_hash is None:
            st.error(
                "No password is configured for this deployment. Add "
                "`app_password_hash` (a SHA-256 hex digest) to `.streamlit/secrets.toml` "
                "or the Streamlit Cloud secrets."
            )
            st.stop()
        with st.form("login", border=True):
            pw = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            if hashlib.sha256(pw.encode()).hexdigest() == _pw_hash:
                st.session_state.authenticated = True
                st.rerun()
            st.error("Incorrect password")
        st.caption("Forgot the password? Contact the lab manager.")
    st.stop()

if "df_sess" not in st.session_state:
    st.session_state.update({
        "df_sess":        None,
        "df_hr":          None,
        "df_seg":         None,
        "df_unmapped":    None,
        "found_ids":      None,
        "skipped_report": None,
        "analysis_run":   False,
        "exports":        None,
    })


def _build_exports(df_sess, df_hr, df_seg, df_unmap, skipped, id_groups, id_blocks) -> dict:
    """Build the ZIP and the paper-format workbook ONCE per analysis.

    These used to be rebuilt on every Streamlit rerun - every click, every
    subject or session picked - which re-wrote every per-program workbook and
    re-rendered ~5 matplotlib PNGs per program each time.
    """
    stamp = datetime.now()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if skipped:
            skip_buf = io.BytesIO()
            pd.DataFrame(skipped).to_excel(skip_buf, index=False, engine="openpyxl")
            zf.writestr("00_Skipped_Sessions_Log.xlsx", skip_buf.getvalue())

        if df_unmap is not None and not df_unmap.empty:
            unm_buf = io.BytesIO()
            df_unmap.to_excel(unm_buf, index=False, engine="openpyxl")
            zf.writestr("00_Unrecognized_MSNs.xlsx", unm_buf.getvalue())

        for prog in df_sess["program_name"].unique():
            safe  = re.sub(r"[^A-Za-z0-9_]", "_", prog)
            sub_s = df_sess[df_sess["program_name"] == prog]
            sub_h = df_hr[df_hr["program_name"] == prog].copy() if _hr_ok(df_hr) else pd.DataFrame()
            daily = create_daily_summary(sub_s)

            sub_g = (df_seg[df_seg["program_name"] == prog].copy()
                     if _hr_ok(df_seg) else pd.DataFrame())

            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine="openpyxl") as w:
                sub_s.to_excel(w, sheet_name="Sessions", index=False)
                if not sub_h.empty: sub_h.to_excel(w, sheet_name="Hourly", index=False)
                # One row per extinction session / relapse segment.
                if not sub_g.empty:
                    sub_g.to_excel(w, sheet_name="Segments", index=False)
                    create_segment_summary(sub_g).to_excel(w, sheet_name="Segment_Summary", index=False)
                if not daily.empty: daily.to_excel(w, sheet_name="Daily", index=False)
                generate_pattern_flags(sub_s).to_excel(w, sheet_name="Flags", index=False)
            zf.writestr(f"{safe}_Full_Analysis.xlsx", excel_buf.getvalue())

            plot_list = []
            if not daily.empty:
                buf = create_plot(daily, "first_session_time", "total_infusions", f"Daily Infusions - {prog}", "canonical_subject", kind="line")
                if buf: plot_list.append((buf, "01_Daily_Infusions_Line"))
            if not sub_h.empty:
                buf = create_plot(sub_h, "hour", "infusion_events", f"Hourly Infusions - {prog}", "canonical_subject")
                if buf: plot_list.append((buf, "02_Hourly_Infusions"))
                buf = create_plot(sub_h, "hour", "active_events", f"Hourly Active Presses - {prog}", "canonical_subject")
                if buf: plot_list.append((buf, "03_Hourly_Active"))
            if not sub_s.empty:
                buf = create_plot(sub_s, "active_presses", "infusions", f"Efficiency - {prog}", "gender", kind="scatter", style="duration_sec")
                if buf: plot_list.append((buf, "04_Efficiency_Scatter"))
            if not daily.empty and "gender" in daily.columns:
                buf = create_plot(daily, "gender", "total_infusions", f"Infusions by Gender - {prog}", "gender", kind="box")
                if buf: plot_list.append((buf, "05_Infusions_by_Gender_Box"))
            for plt_buf, name in plot_list:
                if plt_buf: zf.writestr(f"Plots/{safe}/{name}.png", plt_buf.getvalue())

        # Paper-format workbook: one sheet per program plus Joined, laid out
        # as ID / Group / numbered session columns with Group x Sex blocks
        # and live Mean/SEM formulas.
        paper_bytes, sheets, paper_error = None, [], None
        try:
            paper_buf = io.BytesIO()
            sheets = build_wide_workbook(df_sess, df_seg, id_groups or {}, id_blocks or {}, paper_buf)
            paper_bytes = paper_buf.getvalue()
            zf.writestr("01_PaperFormat_AllPrograms.xlsx", paper_bytes)
        except Exception as _e:
            paper_error = str(_e)

    return {
        "zip": zip_buffer.getvalue(),
        "zip_name": f"MedPC_{stamp:%Y%m%d_%H%M}.zip",
        "paper": paper_bytes,
        "paper_name": f"MedPC_PaperFormat_{stamp:%Y%m%d_%H%M}.xlsx",
        "sheets": sheets,
        "paper_error": paper_error,
    }


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧬 MedPC Analyzer")
    st.caption(f"Lynch Lab · v{CONFIG_VERSION}")

    st.subheader("1 · Data")
    data_files = st.file_uploader(
        "MedPC data files", accept_multiple_files=True,
        help="Raw MedPC exports: .txt, extensionless (!2025-08-03), or a .zip of them.")
    id_file = st.file_uploader(
        "ID list (optional)", type=["txt"],
        help="Restricts the analysis to these subjects and reports any that are missing.")
    with st.expander("ID list format"):
        st.markdown(
            "One ID per line. Optionally add a Group and a block label:\n\n"
            "`O366M` — no group\n\n"
            "`O366M,Naive` — Group column filled\n\n"
            "`O366M,Saline,Naive` — Group Saline, grouped under the NAIVE banner\n\n"
            "MedPC records carry no group of their own, so the paper-format export "
            "takes it from here."
        )
    with st.expander("Custom MSN mappings"):
        settings_file = st.file_uploader("settings.json", type=["json"],
                                         help="Overrides the built-in MSN patterns and variable mappings.")

    st.subheader("2 · Options")
    with st.expander("Cohort filter"):
        include_mice = st.checkbox("Include Mice (G126 / G126A / G126B)", value=True)
        cohort_options = ["G136A", "G136B", "G138A", "G138B", "G140A", "G140B", "G126", "G126A", "G126B", "All Others"]
        default_cohorts = (["G126", "G126A", "G126B", "G136A", "G136B", "G138A", "G138B", "G140A", "G140B", "All Others"] if include_mice else cohort_options)
        selected_cohorts = st.multiselect("Only include these cohorts", cohort_options, default=default_cohorts)
        if include_mice:
            selected_cohorts = list(set(selected_cohorts) | {"G126", "G126A", "G126B"})

    with st.expander("Flag thresholds"):
        min_active_presses = st.slider("Min active presses (low activity)", 0, 50, 5)
        max_inactive_ratio = st.slider("Max inactive/active ratio", 0.0, 2.0, 0.4, 0.05)
        min_session_min    = st.slider("Min session length (minutes)", 5, 120, 20)
        escalation_pct     = st.slider("Escalation detection threshold (%)", 10, 100, 30)

    with st.expander("Intake estimate"):
        drug_type = st.selectbox("Drug type", ["None", "Cocaine", "Fentanyl", "Nicotine"])
        avg_weight_g = st.number_input("Average subject weight (g)", min_value=100, max_value=600, value=300, step=10)
        conc_mgml = 1.0
        if drug_type == "Cocaine": conc_mgml = st.number_input("Cocaine conc. (mg/ml)", 0.1, 10.0, 1.0, 0.1)
        elif drug_type == "Fentanyl": conc_mgml = st.number_input("Fentanyl conc. (mg/ml)", 0.001, 0.1, 0.01, 0.001, format="%.4f")
        elif drug_type == "Nicotine": conc_mgml = st.number_input("Nicotine conc. (mg/ml)", 0.01, 1.0, 0.2, 0.01)

    st.write("")
    run_clicked = st.button("🚀 Run analysis", type="primary", use_container_width=True,
                            disabled=not data_files,
                            help=None if data_files else "Upload at least one data file first.")

# ── Header ───────────────────────────────────────────────────────────────────
_has_results_hdr = (st.session_state.df_sess is not None and not st.session_state.df_sess.empty)
ui_style.hero(f"Lynch Lab · v{CONFIG_VERSION}", "MedPC", "Analyzer",
              "Parse MedPC exports · per-session and per-segment breakdowns · flags · "
              "paper-ready workbooks", compact=_has_results_hdr)

has_results = (st.session_state.df_sess is not None and not st.session_state.df_sess.empty)

if not has_results and not run_clicked:
    ui_style.steps(
        [("Upload", "Add MedPC data files - or a zip of them - in the sidebar. An ID list is optional."),
         ("Adjust", "Cohort filter, flag thresholds and intake settings live under <i>Options</i>."),
         ("Run", "Press <b>Run analysis</b>. Results, data-quality checks and downloads appear here.")],
        intro=f"{ui_style.greeting()} 👋 &nbsp;Ready when you are.")
    if st.session_state.get("analysis_run") and st.session_state.df_sess is not None:
        st.warning("No data matched your filters / ID list.")

# ── Run ──────────────────────────────────────────────────────────────────────
if run_clicked and data_files:
    custom_patterns = custom_mappings = None
    if settings_file:
        try:
            s = json.load(settings_file)
            custom_patterns = s.get("msn_patterns")
            custom_mappings = s.get("variable_mappings")
        except Exception as e:
            st.warning(f"Settings.json invalid → {e}")

    allowed_canon: set = set()
    id_groups: dict = {}
    id_blocks: dict = {}
    if id_file:
        allowed_canon, id_groups, id_blocks = parse_id_list(id_file, canonicalize_id)

    with st.status("Running analysis…", expanded=True) as run_status:
        parser = MedPCParser()
        all_sessions = []
        prog_bar = st.progress(0.0)
        msg = st.empty()

        for idx, f in enumerate(data_files):
            msg.caption(f"Parsing {f.name} ({idx + 1}/{len(data_files)})")
            try:
                raw_bytes = f.getvalue()
                if raw_bytes[:4] == b"PK\x03\x04":
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                        for inner_name in zf.namelist():
                            if not inner_name.endswith("/"):
                                try:
                                    inner_content = zf.read(inner_name).decode("utf-8", errors="replace")
                                    all_sessions.extend(parser.parse_file(inner_content, f"{f.name}/{inner_name}"))
                                except Exception as ie:
                                    st.warning(f"Error reading {inner_name} inside {f.name}: {ie}")
                else:
                    content = raw_bytes.decode("utf-8", errors="replace")
                    all_sessions.extend(parser.parse_file(content, f.name))
            except Exception as e:
                st.warning(f"Parse error in {f.name}: {e}")
            prog_bar.progress((idx + 1) / len(data_files))

        msg.caption(f"Analysing {len(all_sessions):,} sessions…")
        df_sess, df_hr, found_ids, df_seg, df_unmapped = process_sessions(
            all_sessions, allowed_ids=allowed_canon or None,
            custom_patterns=custom_patterns, custom_mappings=custom_mappings,
            drug_type=drug_type, avg_weight_g=avg_weight_g, conc_mgml=conc_mgml,
        )

        if "All Others" not in selected_cohorts and selected_cohorts:
            cohort_pattern = "|".join(r"(?<![A-Za-z0-9])" + re.escape(c) + r"(?![A-Za-z0-9])" for c in selected_cohorts)
            mask = df_sess["canonical_subject"].str.contains(cohort_pattern, case=False, na=False, regex=True)
            df_sess = df_sess[mask].copy()
            if _hr_ok(df_hr):
                df_hr = df_hr[df_hr["canonical_subject"].isin(df_sess["canonical_subject"])].copy()
            if _hr_ok(df_seg):
                df_seg = df_seg[df_seg["canonical_subject"].isin(df_sess["canonical_subject"])].copy()

        df_sess = generate_pattern_flags(
            df_sess, min_active=min_active_presses, max_inactive_ratio=max_inactive_ratio,
            min_duration_min=min_session_min, escalation_threshold=escalation_pct,
        )

        skipped_report = parser.get_skipped_report()
        exports = None
        if not df_sess.empty:
            msg.caption("Building Excel workbooks and plots for download…")
            exports = _build_exports(df_sess, df_hr, df_seg, df_unmapped, skipped_report,
                                     id_groups, id_blocks)
        run_status.update(label=f"Analysis complete · {len(df_sess):,} sessions",
                          state="complete", expanded=False)

    # Widget selections from a previous dataset may name programs or
    # subjects that no longer exist.
    for k in [k for k in st.session_state if str(k).startswith(("cohort_prog", "subj_prog", "subject_sel", "ts_sel_"))]:
        del st.session_state[k]

    st.session_state.update({
        "df_sess": df_sess, "df_hr": df_hr, "df_seg": df_seg,
        "df_unmapped": df_unmapped, "found_ids": found_ids,
        "seg_problems": _analyzer.LAST_DIAGNOSTICS.get("segment_problems"),
        "n_records_in": _analyzer.LAST_DIAGNOSTICS.get("n_records_in", 0),
        "duplicates_removed": _analyzer.LAST_DIAGNOSTICS.get("duplicates_removed"),
        "reset_remnants": _analyzer.LAST_DIAGNOSTICS.get("reset_remnants"),
        "skipped_report": skipped_report, "allowed_canon": allowed_canon,
        "id_groups": id_groups, "id_blocks": id_blocks, "analysis_run": True,
        "exports": exports,
    })
    st.toast("Analysis complete", icon="✅")
    st.rerun()

# ── Results ──────────────────────────────────────────────────────────────────
if has_results:
    df_sess   = st.session_state.df_sess
    df_hr     = st.session_state.df_hr
    df_seg    = st.session_state.get("df_seg")
    df_unmap  = st.session_state.get("df_unmapped")
    found_ids = st.session_state.found_ids or set()
    skipped   = st.session_state.skipped_report or []
    exports   = st.session_state.get("exports")
    expected_ids = st.session_state.get("allowed_canon") or set()
    missing_ids  = sorted(expected_ids - found_ids)
    n_unmapped   = 0 if df_unmap is None or df_unmap.empty else len(df_unmap)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Subjects", len(found_ids))
    k2.metric("Sessions", f"{len(df_sess):,}")
    k3.metric("Programs", df_sess["program_name"].nunique())
    k4.metric("Skipped blocks", len(skipped))
    k5.metric("Unrecognised MSN", n_unmapped)

    # Problems that change what the numbers mean stay visible on every view.
    # Sessions whose MSN matched no pattern are NOT analysed. v6.3 fell back
    # to the FR20 mapping and labelled them "UNMAPPED", which produced
    # plausible-looking numbers read out of the wrong variables.
    if n_unmapped:
        st.error(
            f"**{n_unmapped} session(s) were not analysed** — no MSN pattern matched. "
            "Add the MSN to DEFAULT_MSN_PATTERNS in config.py, then re-run. "
            "Details under **Data quality**."
        )
    if missing_ids:
        st.warning(f"**{len(missing_ids)} expected subject(s) not found:** {', '.join(missing_ids)}")
    dups = st.session_state.get("duplicates_removed")
    rem = st.session_state.get("reset_remnants")
    n_d = 0 if dups is None else len(dups)
    n_r = 0 if rem is None else len(rem)
    if n_d or n_r:
        st.caption(f"ℹ️ Each session counted once: {n_d} duplicate copies (interim / repeated saves) "
                   f"merged and {n_r} daily-reset remnant records excluded — see **Data quality**.")

    VIEWS = ["📊 Cohort", "🔀 Cross-program", "🐀 Single subject", "🩺 Data quality", "📥 Downloads"]
    # A segmented control renders only the chosen view. st.tabs rendered all of
    # them (80+ charts for a typical upload) on every rerun.
    view = st.segmented_control("View", VIEWS, default=VIEWS[0], key="view",
                                label_visibility="collapsed") or VIEWS[0]

    unique_genders = set(df_sess["gender"].unique())

    # ─── COHORT ──────────────────────────────────────────────────────────────
    if view == VIEWS[0]:
        programs = sorted(df_sess["program_name"].unique())
        p = st.pills("Program", programs, default=programs[0], format_func=_short,
                     key="cohort_prog") or programs[0]

        sub_s = df_sess[df_sess["program_name"] == p].copy()
        sub_h = df_hr[df_hr["program_name"] == p].copy() if _hr_ok(df_hr) else pd.DataFrame()
        sub_g = (df_seg[df_seg["program_name"] == p].copy()
                 if _hr_ok(df_seg) else pd.DataFrame())
        daily = create_daily_summary(sub_s)
        has_both = "Male" in sub_s["gender"].values and "Female" in sub_s["gender"].values

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Subjects", sub_s["canonical_subject"].nunique())
        m2.metric("Sessions", len(sub_s))
        m3.metric("Infusions / session", f"{sub_s['infusions'].mean():.1f}")
        m4.metric("Active / session", f"{sub_s['active_presses'].mean():.1f}")

        if not has_both:
            if "Unknown" in set(sub_s["gender"].unique()):
                st.info("💡 **Sex comparisons hidden.** Sex is read from the last letter of the "
                        "Subject ID (e.g. `123M` / `123F`); some IDs here don't end in M or F.")
            else:
                only = next(iter(set(sub_s["gender"].unique())), "one sex")
                st.caption(f"Only {only.lower()} subjects in this program — sex comparisons hidden.")

        c1, c2 = st.columns(2)
        with c1:
            if not daily.empty:
                st.plotly_chart(
                    create_interactive_plot(
                        daily, "session_day" if "session_day" in daily.columns else "first_session_time", "total_infusions",
                        f"Daily Infusions (Per Subject) — {_short(p)}", "canonical_subject", kind="line"),
                    use_container_width=True, key=f"daily_inf_{p}")
                st.plotly_chart(create_mean_sem_trajectory(daily), use_container_width=True, key=f"mean_sem_{p}")
        with c2:
            if not sub_h.empty:
                st.plotly_chart(create_hourly_line_plot(sub_h, f"Avg Infusions by Hour (Per Subject) — {_short(p)}"), use_container_width=True, key=f"hourly_line_{p}")
                st.plotly_chart(create_hourly_heatmap(sub_h), use_container_width=True, key=f"hourly_heatmap_{p}")

        # ─── EVERY TEST SESSION (extinction / relapse segments) ───
        packs_sessions = any(k in p.upper() for k in ("EXTINCTION", "REINSTATEMENT", "CUE RELAPSE"))
        if not sub_g.empty:
            st.divider()
            st.subheader("Every test session")
            st.caption(
                "An extinction record holds up to nine (2017 program: ten) hourly "
                "extinction sessions plus, if the animal reached it, a reinstatement "
                "test; a cue-relapse record holds four 30-minute segments. Each is "
                "reported as its own row instead of one total."
            )
            st.plotly_chart(create_segment_plot(sub_g), use_container_width=True, key=f"segments_{p}")
            st.dataframe(create_segment_summary(sub_g), hide_index=True, use_container_width=True)
        elif packs_sessions:
            # Never fail silently: this program SHOULD have a
            # per-session breakdown, so say why it doesn't.
            st.divider()
            st.subheader("Every test session")
            st.error("No per-session breakdown was produced for this program.")
            probs = st.session_state.get("seg_problems")
            if probs is not None and not probs.empty:
                mine = probs[probs["program_name"] == p]
                if not mine.empty:
                    st.write("**Why:**")
                    for w in mine["why"].dropna().unique()[:5]:
                        st.write(f"- {w}")
                    st.dataframe(mine, hide_index=True)
            st.caption(
                "The usual cause is that the program wrote its DISKVARS in an "
                "order this build did not expect, so the per-session variables "
                "never reached the parser. The scalar_keys / array_keys columns "
                "in the Sessions table show exactly which letters each record "
                "actually contained."
            )

        # ─── DISCRIMINATION ───
        st.divider()
        st.plotly_chart(create_cohort_discrimination_plot(sub_s), use_container_width=True, key=f"cohort_discrim_{p}")

        # ─── SEX SPLITS ───
        if has_both:
            st.divider()
            st.subheader("Sex comparisons")
            gc1, gc2 = st.columns(2)
            with gc1:
                if not daily.empty:
                    st.plotly_chart(create_mean_sem_trajectory(daily, split_by_gender=True), use_container_width=True, key=f"mean_sem_gen_{p}")
                st.plotly_chart(create_cohort_discrimination_plot(sub_s, split_by_gender=True), use_container_width=True, key=f"cohort_discrim_gen_{p}")
            with gc2:
                if not sub_h.empty:
                    st.plotly_chart(create_cohort_hourly_line_plot(sub_h, split_by_gender=True), use_container_width=True, key=f"cohort_hourly_gen_{p}")

    # ─── CROSS-PROGRAM ───────────────────────────────────────────────────────
    elif view == VIEWS[1]:
        has_both_genders_all = "Male" in unique_genders and "Female" in unique_genders
        st.plotly_chart(create_cumulative_plot(df_sess), use_container_width=True, key="cumulative_all")
        st.plotly_chart(create_cohort_discrimination_plot(df_sess), use_container_width=True, key="cohort_discrim_all")
        if has_both_genders_all:
            st.plotly_chart(create_cohort_discrimination_plot(df_sess, split_by_gender=True), use_container_width=True, key="cohort_discrim_all_gen")

        st.divider()
        st.subheader("Individual discrimination breakdown")
        # One facet per subject; drawing it for every animal at once is slow,
        # so it waits until asked for.
        if st.toggle(f"Show one panel per subject ({df_sess['canonical_subject'].nunique()} subjects)", key="show_indiv_discrim"):
            st.plotly_chart(create_discrimination_plot(df_sess), use_container_width=True, key="discrimination_all")

    # ─── SINGLE SUBJECT ──────────────────────────────────────────────────────
    elif view == VIEWS[2]:
        if not found_ids:
            st.info("No subjects found.")
        else:
            sel = st.selectbox("Subject", sorted(found_ids), key="subject_sel")
            subject_sess = df_sess[df_sess["canonical_subject"] == sel].copy()
            subject_hr   = df_hr[df_hr["canonical_subject"] == sel].copy() if _hr_ok(df_hr) else pd.DataFrame()

            if subject_sess.empty:
                st.warning(f"No sessions found for subject {sel}.")
            else:
                gender_label = subject_sess["gender"].iloc[0]
                programs = sorted(subject_sess["program_name"].unique())
                st.caption(f"{sel} · {gender_label} · {len(subject_sess)} sessions across "
                           f"{len(programs)} program(s)")
                p = st.pills("Program", programs, default=programs[0], format_func=_short,
                             key=f"subj_prog_{sel}") or programs[0]

                prog_sess  = subject_sess[subject_sess["program_name"] == p].copy()
                prog_hr    = subject_hr[subject_hr["program_name"] == p].copy() if not subject_hr.empty else pd.DataFrame()
                prog_daily = create_daily_summary(prog_sess)

                c1, c2, c3 = st.columns(3)
                c1.metric("Sessions",        len(prog_sess))
                c2.metric("Total infusions", int(prog_sess["infusions"].sum()))
                c3.metric("Active presses",  int(prog_sess["active_presses"].sum()))

                if not prog_daily.empty:
                    st.plotly_chart(
                        create_interactive_plot(
                            prog_daily, "first_session_time", "total_infusions",
                            f"Daily Infusions — {_short(p)} ({sel})", hue=None, kind="line"),
                        use_container_width=True, key=f"daily_inf_subj_{sel}_{p}")

                if not prog_hr.empty:
                    h1, h2 = st.columns(2)
                    with h1:
                        st.plotly_chart(create_hourly_line_plot(prog_hr), use_container_width=True, key=f"hourly_line_subj_{sel}_{p}")
                    with h2:
                        st.plotly_chart(create_hourly_heatmap(prog_hr), use_container_width=True, key=f"hourly_heatmap_subj_{sel}_{p}")

                with st.expander("More plots", expanded=False):
                    st.plotly_chart(create_cumulative_plot(prog_sess), use_container_width=True, key=f"cumulative_subj_{sel}_{p}")
                    if "active_presses" in prog_sess.columns:
                        st.plotly_chart(create_discrimination_plot(prog_sess), use_container_width=True, key=f"discrim_subj_{sel}_{p}")
                        st.plotly_chart(create_response_rate_plot(prog_sess), use_container_width=True, key=f"resp_rate_subj_{sel}_{p}")
                    if "breakpoints" in prog_sess.columns and prog_sess["breakpoints"].sum() > 0:
                        st.plotly_chart(create_pr_breakpoint_plot(prog_sess), use_container_width=True, key=f"pr_bp_subj_{sel}_{p}")
                    if not prog_daily.empty and "total_active_presses" in prog_daily.columns:
                        st.plotly_chart(create_efficiency_trend(prog_daily), use_container_width=True, key=f"efficiency_subj_{sel}_{p}")

                st.subheader("Within-session timepoints")
                if ("active_timestamps" in prog_sess.columns and "session_day" in prog_sess.columns):
                    prog_sess = prog_sess.reset_index(drop=True)
                    session_options = {
                        f"Session {row['session_day']} "
                        f"({pd.Timestamp(row['start_date']).date() if pd.notna(row['start_date']) else 'unknown'}) "
                        f"— idx {ridx}": ridx
                        for ridx, row in prog_sess.iterrows()
                    }
                    selected_label = st.selectbox("Session", options=list(session_options.keys()), key=f"ts_sel_{sel}_{p}")
                    if selected_label:
                        ridx             = session_options[selected_label]
                        session_data_row = prog_sess.loc[ridx]
                        timestamps       = session_data_row.get("active_timestamps", [])
                        duration         = session_data_row.get("duration_sec", 0)
                        st.plotly_chart(create_within_session_plot(timestamps, duration), use_container_width=True, key=f"ts_plot_{sel}_{p}")
                else:
                    st.info("Timepoint arrays not available for this program.")

                with st.expander(f"Sessions table — {_short(p)}"):
                    st.dataframe(prog_sess, hide_index=True)
                with st.expander("All programs — quick stats"):
                    st.dataframe(subject_sess[["program_name", "start_date", "end_date", "infusions", "active_presses"]].sort_values("start_date"),
                                 hide_index=True, use_container_width=True)

    # ─── DATA QUALITY ────────────────────────────────────────────────────────
    elif view == VIEWS[3]:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Records read", st.session_state.get("n_records_in", 0))
        d2.metric("Sessions kept", len(df_sess))
        d3.metric("Hourly rows", 0 if not _hr_ok(df_hr) else len(df_hr))
        d4.metric("Segment rows", 0 if not _hr_ok(df_seg) else len(df_seg))

        if n_unmapped:
            st.subheader("Unrecognised MSNs")
            st.dataframe(df_unmap.groupby("raw_msn").size().reset_index(name="sessions"),
                         hide_index=True, use_container_width=True)

        dups = st.session_state.get("duplicates_removed")
        if dups is not None and not dups.empty:
            st.subheader("Duplicate records merged")
            st.caption("The same session (Subject, Start Date/Time, Box, MSN) written more than once. "
                       "The latest-ending copy is kept; an interim save is never larger than the final record.")
            st.dataframe(dups, hide_index=True, use_container_width=True)

        rem = st.session_state.get("reset_remnants")
        if rem is not None and not rem.empty:
            st.subheader("Daily-reset remnants excluded")
            st.caption("Idle records a box writes after its daily reset: same Start and End Date, "
                       "End Time before Start Time, no session of their own. Each one's real session "
                       "is in the data. counts_in_remnant lists any presses made between the reset "
                       "and the program change (DT4 starts a trial at its 12:00 reset).")
            st.dataframe(rem, hide_index=True, use_container_width=True)

        if "active_timestamps_capped" in df_sess.columns and df_sess["active_timestamps_capped"].any():
            capped = df_sess[df_sess["active_timestamps_capped"]]
            st.subheader("Sessions past the 3,200-timestamp limit")
            st.caption("The program stores at most 3,200 press times. Totals are exact; the hourly "
                       "active-press breakdown under-counts the later hours of these sessions.")
            st.dataframe(capped[["canonical_subject", "program_name", "start_date", "active_presses"]],
                         hide_index=True, use_container_width=True)

        if skipped:
            st.subheader("Skipped blocks")
            st.caption("Records the parser could not use — most often a blank Subject or Start Date.")
            st.dataframe(pd.DataFrame(skipped), hide_index=True, use_container_width=True)

        st.subheader("Subject coverage & Box/Room")
        report_missing_and_box_room(expected_ids, found_ids, df_sess)

        st.subheader("Per-program parse summary")
        per_prog = df_sess.groupby("program_name").size().rename("sessions").to_frame()
        if _hr_ok(df_seg):
            per_prog = per_prog.join(
                df_seg.groupby("program_name").size().rename("segment_rows"))
        else:
            per_prog["segment_rows"] = 0
        per_prog["segment_rows"] = per_prog["segment_rows"].fillna(0).astype(int)
        st.dataframe(per_prog.reset_index(), hide_index=True, use_container_width=True)

        probs = st.session_state.get("seg_problems")
        if probs is not None and not probs.empty:
            st.write("**Records that should have had a per-session breakdown but didn't**")
            st.dataframe(probs, hide_index=True)

        if "scalar_keys" in df_sess.columns:
            st.write("**Variable letters present, per program** "
                     "(a mapped variable missing here reads as 0 downstream)")
            st.dataframe(
                df_sess.groupby("program_name")[["scalar_keys", "array_keys"]]
                       .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "")
                       .reset_index(),
                hide_index=True, use_container_width=True)

    # ─── DOWNLOADS ───────────────────────────────────────────────────────────
    elif view == VIEWS[4]:
        if exports is None:
            st.info("Exports are built when the analysis runs — press **Run analysis** again.")
        else:
            dl1, dl2 = st.columns(2)
            with dl1, st.container(key="glass_zip"):
                st.markdown("**📦 Full analysis (ZIP)**")
                st.caption("Per-program workbooks (Sessions, Hourly, Segments, Daily, Flags), "
                           "PNG plots, skipped-session and unrecognised-MSN logs, and the "
                           "paper-format workbook.")
                st.download_button("Download ZIP", exports["zip"], exports["zip_name"],
                                   "application/zip", type="primary", use_container_width=True)
            with dl2, st.container(key="glass_paper"):
                st.markdown("**📄 Paper-format workbook**")
                if exports["paper"] is not None:
                    st.caption(f"ID / Group / per-session columns with Mean & SEM. "
                               f"Sheets: {', '.join(exports['sheets'])}")
                    st.download_button(
                        "Download workbook", exports["paper"], exports["paper_name"],
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)
                else:
                    st.warning(f"Paper-format export unavailable: {exports['paper_error']}")
            if not (st.session_state.get("id_groups") or {}):
                st.info(
                    "The Group column is empty because your ID list has only one column. "
                    "Add `,Group` after each ID to fill it and split the blocks."
                )

    st.divider()
    if st.button("🗑️ Clear results"):
        # Keep the login; drop everything else.
        for k in list(st.session_state):
            if k != "authenticated":
                del st.session_state[k]
        st.rerun()

ui_style.footer(CONFIG_VERSION)
