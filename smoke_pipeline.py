"""End-to-end smoke test: run the same calls app.py makes, minus Streamlit.

usage: python smoke_pipeline.py <data_dir> [<data_dir> ...]

Exercises parsing, process_sessions, pattern flags, daily / segment
summaries, every per-program Excel sheet, every matplotlib export, every
plotly figure the UI draws, and the paper-format workbook. Any exception is
recorded with its program and call site instead of stopping the run.
"""
import io
import os
import sys
import traceback
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from parser import MedPCParser
import analyzer
from analyzer import (process_sessions, generate_pattern_flags, create_daily_summary,
                      create_segment_summary)
import plotter as P
from wide_export import build_wide_workbook

problems = []


def run(label, fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:
        problems.append((label, f"{type(e).__name__}: {e}",
                         traceback.format_exc().strip().splitlines()[-3:]))
        return None


parser = MedPCParser()
sessions = []
for d in sys.argv[1:]:
    for dp, _, fns in os.walk(d):
        for fn in fns:
            fp = os.path.join(dp, fn)
            try:
                txt = open(fp, errors="replace").read()
            except Exception:
                continue
            if "Start Date:" not in txt:
                continue
            sessions.extend(parser.parse_file(txt, fn))

print(f"parsed sessions: {len(sessions)}   parser-skipped: {len(parser.skipped_sessions)}")
for f, r, _ in parser.skipped_sessions[:5]:
    print(f"   skipped {f}: {r}")

df_sess, df_hr, found, df_seg, df_un = process_sessions(sessions)
print(f"session rows: {len(df_sess)}  hourly rows: {len(df_hr)}  segment rows: "
      f"{len(df_seg)}  unmapped: {len(df_un)}")
if len(df_un):
    print("   unmapped MSNs:", dict(df_un["raw_msn"].value_counts()))
probs = analyzer.LAST_DIAGNOSTICS.get("segment_problems")
if probs is not None and len(probs):
    print(f"   segment problems: {len(probs)}")

df_sess = run("generate_pattern_flags", generate_pattern_flags, df_sess)
hr_ok = isinstance(df_hr, pd.DataFrame) and not df_hr.empty
seg_ok = isinstance(df_seg, pd.DataFrame) and not df_seg.empty

for prog in df_sess["program_name"].unique():
    sub_s = df_sess[df_sess["program_name"] == prog]
    sub_h = df_hr[df_hr["program_name"] == prog].copy() if hr_ok else pd.DataFrame()
    sub_g = df_seg[df_seg["program_name"] == prog].copy() if seg_ok else pd.DataFrame()
    daily = run(f"{prog}: daily", create_daily_summary, sub_s)
    if daily is None:
        daily = pd.DataFrame()

    buf = io.BytesIO()
    try:
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            sub_s.to_excel(w, sheet_name="Sessions", index=False)
            if not sub_h.empty:
                sub_h.to_excel(w, sheet_name="Hourly", index=False)
            if not sub_g.empty:
                sub_g.to_excel(w, sheet_name="Segments", index=False)
                create_segment_summary(sub_g).to_excel(w, sheet_name="Segment_Summary", index=False)
            if not daily.empty:
                daily.to_excel(w, sheet_name="Daily", index=False)
            generate_pattern_flags(sub_s).to_excel(w, sheet_name="Flags", index=False)
    except Exception as e:
        problems.append((f"{prog}: excel", f"{type(e).__name__}: {e}",
                         traceback.format_exc().strip().splitlines()[-3:]))

    if not daily.empty:
        run(f"{prog}: png daily", P.create_plot, daily, "first_session_time", "total_infusions", "t", "canonical_subject", kind="line")
        run(f"{prog}: png box", P.create_plot, daily, "gender", "total_infusions", "t", "gender", kind="box")
        run(f"{prog}: mean_sem", P.create_mean_sem_trajectory, daily)
        run(f"{prog}: mean_sem gender", P.create_mean_sem_trajectory, daily, split_by_gender=True)
        run(f"{prog}: efficiency_trend", P.create_efficiency_trend, daily)
        run(f"{prog}: interactive", P.create_interactive_plot, daily, "first_session_time", "total_infusions", "t", "canonical_subject")
    if not sub_h.empty:
        run(f"{prog}: png hourly inf", P.create_plot, sub_h, "hour", "infusion_events", "t", "canonical_subject")
        run(f"{prog}: png hourly act", P.create_plot, sub_h, "hour", "active_events", "t", "canonical_subject")
        run(f"{prog}: hourly_line", P.create_hourly_line_plot, sub_h)
        run(f"{prog}: hourly_heatmap", P.create_hourly_heatmap, sub_h)
        run(f"{prog}: cohort_hourly", P.create_cohort_hourly_line_plot, sub_h, split_by_gender=True)
    if not sub_s.empty:
        run(f"{prog}: png scatter", P.create_plot, sub_s, "active_presses", "infusions", "t", "gender", kind="scatter", style="duration_sec")
        run(f"{prog}: cohort_discrim", P.create_cohort_discrimination_plot, sub_s)
        run(f"{prog}: cohort_discrim gender", P.create_cohort_discrimination_plot, sub_s, split_by_gender=True)
        run(f"{prog}: discrim", P.create_discrimination_plot, sub_s)
        run(f"{prog}: response_rate", P.create_response_rate_plot, sub_s)
        run(f"{prog}: pr_breakpoint", P.create_pr_breakpoint_plot, sub_s)
        run(f"{prog}: cumulative", P.create_cumulative_plot, sub_s)
        r0 = sub_s.iloc[0]
        run(f"{prog}: within_session", P.create_within_session_plot,
            r0.get("active_timestamps") or [], r0.get("duration_sec"))
    if not sub_g.empty:
        run(f"{prog}: segment_plot", P.create_segment_plot, sub_g)
        run(f"{prog}: segment_plot gender", P.create_segment_plot, sub_g, split_by_gender=True)

run("all: cumulative", P.create_cumulative_plot, df_sess)
run("all: discrimination", P.create_discrimination_plot, df_sess)
run("paper workbook", build_wide_workbook, df_sess, df_seg, {}, {}, io.BytesIO())

print()
print("programs:", dict(df_sess["program_name"].value_counts()))
print()
if problems:
    print(f"{len(problems)} PROBLEMS")
    for label, msg, tb in problems:
        print(f" - {label}: {msg}")
        for line in tb:
            print("       ", line)
else:
    print("NO ERRORS")
