"""Regression tests for the all-program audit (v7.3).

Run:  python test_programs.py

Covers record handling shared by every program (duplicate saves, daily-reset
remnants), hourly binning (J-array session hours, zero-filled timestamp
hours), and the per-program mapping fixes (FR presses-during-infusion,
FR23hr, the 2017 discrete-trial INTERMITTENT program, FLUSH pump time,
unsupported programs, the 3,200-timestamp cap).
"""
from parser import ParsedSession
from analyzer import (process_sessions, resolve_program, is_reset_remnant,
                      hourly_from_j_array)
from config import DEFAULT_MSN_PATTERNS
from utils import normalize_msn

fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "  -> " + str(detail)))
    if not cond:
        fails.append(name)


def rec(msn, scalars=None, arrays=None, subj="C412M", sd="01/23/17", st="12:02:52",
        ed="01/24/17", et="11:00:00", box="3"):
    return ParsedSession(
        meta={"Subject": subj, "Start Date": sd, "Start Time": st, "End Date": ed,
              "End Time": et, "Box": box, "MSN": msn},
        scalars={k: float(v) for k, v in (scalars or {}).items()},
        arrays={k: [float(x) for x in v] for k, v in (arrays or {}).items()},
        filename="t", raw_block="")


def jblock(label, R=0, I=0, D=0, A=0, L=0, F=1):
    return [label, R, I, D, A, L, F]


# 1. Daily-reset remnants ------------------------------------------------------
real = rec("FENTANYL 1 SEC FR40 LD ESD", dict(I=40, R=63, A=2), sd="08/05/25", st="12:34:26",
           ed="08/06/25", et="11:00:00")
remnant = rec("FENTANYL 1 SEC FR40 LD ESD", dict(I=0, R=0, A=0), sd="08/06/25", st="12:34:26",
              ed="08/06/25", et="11:55:08")
check("remnant (same date, ends before it starts) is recognised", is_reset_remnant(remnant))
check("real overnight session is not a remnant", not is_reset_remnant(real))
check("ordinary same-day session is not a remnant",
      not is_reset_remnant(rec("x", sd="08/06/25", st="09:00:00", ed="08/06/25", et="10:00:00")))
df, _, _, _, _ = process_sessions([real, remnant])
check("remnant excluded: one session, not a 23 h zero day",
      len(df) == 1 and df.iloc[0]["infusions"] == 40, df[["infusions", "duration_hr"]].to_dict("list"))
check("session_day not pushed out by the remnant", df.iloc[0]["session_day"] == 1)

# 2. J array: session hour = block position ----------------------------------
# start 12:34 -> block 0 is 12:34-13:00 (label 0), then 14, 15 ... 23, 24, 1, 2
j = (jblock(0, R=5, I=4) + jblock(14) + jblock(15, R=2, I=1)
     + sum((jblock(h) for h in range(16, 24)), []) + jblock(24, R=3, I=3)
     + jblock(1, R=1, I=1) + [0.0] * 7 * 5)
rows = hourly_from_j_array(j)
check("J hours run 0..N in session order", [r["hour"] for r in rows] == list(range(len(rows))),
      [r["hour"] for r in rows])
check("clock hour kept (block 0 unlabelled, 24 -> 0)",
      [r["clock_hour"] for r in rows][:3] == [None, 14, 15] and rows[-2]["clock_hour"] == 0)
check("quiet middle hours kept as zero rows, unused tail dropped",
      len(rows) == 13 and rows[3]["infusion_events"] == 0, len(rows))
check("hourly infusions sum to the session total", sum(r["infusion_events"] for r in rows) == 9)

# 3. presses during infusion come from J column 3 (D is not in DISKVARS) --------
fr = rec("FR20", dict(I=6, R=10, A=1), arrays={"J": jblock(13, R=6, I=4, D=2, A=1) + jblock(14, R=4, I=2, D=1)})
dfr, _, _, _, _ = process_sessions([fr])
check("FR presses_during_infusion = sum of J(Q+3) = 3",
      dfr.iloc[0]["presses_during_infusion"] == 3, dfr.iloc[0].get("presses_during_infusion"))
check("FR timeout_presses_per_inf = 3/6", abs(dfr.iloc[0]["timeout_presses_per_inf"] - 0.5) < 1e-3,
      dfr.iloc[0]["timeout_presses_per_inf"])

# 4. Timestamp programs: every session hour, zeros included ------------------
inta = rec("NEW INTERMITTENT ACCESS LD ESD", dict(I=3, R=4, U=1, S=6 * 3600),
           arrays={"O": [100, 200, 5 * 3600 + 10]})
_, hr, _, _, _ = process_sessions([inta])
check("IntA 6 h session -> 6 hourly rows (hours 1-4 are zero)",
      list(hr["hour"]) == [0, 1, 2, 3, 4, 5] and list(hr["infusion_events"]) == [2, 0, 0, 0, 0, 1],
      hr[["hour", "infusion_events"]].to_dict("list"))
_, hr_dt, _, _, _ = process_sessions([rec("DT4FINAL", dict(I=5, R=1))])
check("programs without timestamps get no hourly rows", hr_dt.empty, len(hr_dt))

# 5. Routing ---------------------------------------------------------------------
route = lambda m: resolve_program(normalize_msn(m), DEFAULT_MSN_PATTERNS)
check("exact 'INTERMITTENT' -> 2017 discrete-trial program",
      route("INTERMITTENT") == "RAT - INTERMITTENT (2017 DISCRETE-TRIAL)", route("INTERMITTENT"))
for m in ("INTERMITTENT 24 HR", "NEW INTERMITTENT ACCESS LD ESD", "INTERMITTENT FINAL TEST"):
    check(f"{m!r} still -> RAT - INTERMITTENT ACCESS", route(m) == "RAT - INTERMITTENT ACCESS", route(m))
check("FR23hr -> RAT - FR23HR", route("FR23hr") == "RAT - FR23HR" and route("Box 4 FR23hr") == "RAT - FR23HR")
check("SECOND ORDER FR20 is not read as FR20", route("SECOND ORDER FR20 SOFT CR").startswith("UNSUPPORTED"))
check("FR20 still FR20", route("FR20") == "RAT - FR20")

# 6. 2017 discrete-trial INTERMITTENT: R is the inactive lever -----------------
dti, _, _, _, un = process_sessions([rec("INTERMITTENT", dict(I=38, R=16, Q=47, X=1800))])
check("INTERMITTENT: infusions = I, active = I, inactive = R",
      (dti.iloc[0]["infusions"], dti.iloc[0]["active_presses"], dti.iloc[0]["inactive_presses"]) == (38, 38, 16),
      dti[["infusions", "active_presses", "inactive_presses"]].to_dict("records"))

# 7. FR23hr analysed like FR20 ------------------------------------------------------
f23, _, _, _, _ = process_sessions([rec("FR23hr", dict(I=42, R=63, A=10), arrays={"J": jblock(13, R=63, I=42, A=10)})])
check("FR23hr analysed: I / R / A", (f23.iloc[0]["infusions"], f23.iloc[0]["active_presses"],
                                     f23.iloc[0]["inactive_presses"]) == (42, 63, 10))

# 8. Unsupported programs are reported, not analysed ------------------------------
d_u, _, _, _, un_u = process_sessions([rec("PR 2 LEVER 22 HOUR", dict(I=30, R=38, A=157))])
check("PR 2 LEVER -> unmapped with its reason",
      d_u.empty and len(un_u) == 1 and "PR 2 LEVER" in un_u.iloc[0]["reason"], un_u.to_dict("records"))

# 9. Flush pump time = Y flushes x T seconds -------------------------------------
fl, _, _, _, _ = process_sessions([rec("FLUSH", dict(Y=3, T=5, M=2))])
check("FLUSH pump_time_sec = 3 x 5 = 15", fl.iloc[0]["pump_time_sec"] == 15, fl.iloc[0]["pump_time_sec"])

# 10. 3,200-timestamp cap flagged ----------------------------------------------------
cap = rec("PRCOCAINE", dict(I=24, R=3859, A=1), arrays={"C": list(range(3200)), "W": list(range(24)), "F": [1, 2, 4]})
pc, _, _, _, _ = process_sessions([cap])
check("PR session with R > 3,200 timestamps is flagged", bool(pc.iloc[0]["active_timestamps_capped"]))
ok = rec("PRCOCAINE", dict(I=2, R=3, A=0), arrays={"C": [5, 6, 7], "W": [6, 7], "F": [1, 2]})
po, _, _, _, _ = process_sessions([ok])
check("normal PR session not flagged", not bool(po.iloc[0]["active_timestamps_capped"]))

print()
print(("FAILED: " + ", ".join(fails)) if fails else "ALL TESTS PASSED")
raise SystemExit(1 if fails else 0)
