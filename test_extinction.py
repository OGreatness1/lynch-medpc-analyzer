"""Regression tests for extinction / reinstatement reading.

Run:  python test_extinction.py

Records are built the way MedPC writes them for these programs: no DISKVARS
line, so EVERY letter A-Z is present in every record (unused ones as 0). A test
record that simply omits M/N/O does not resemble real data - v7.3's first fix
passed such tests and still failed on all 73 real "Extinction G126 2017"
records.

  9-session family (EXTINCT MUST EXT BY 9 FOR REINST ESD and its sibling
  variants) - A,D,F,G,H,I,J,K,L = sessions 1-9, U = their sum, Q = sessions
  started, E = 1 during extinction / 0 once the cue phase starts, P = inactive
  for the whole run, M = reinstatement presses, N = cue deliveries,
  O = reinstatement inactive.

  2017 extinction-only programs (EXTINCTION G140 ABOXES 2017, Extinction G126
  2017) - A..M = sessions 1-10, U = their sum, Q = sessions started, no cue
  phase.
"""
import string

from parser import ParsedSession
from analyzer import build_segments, process_sessions, resolve_program
from config import (DEFAULT_MSN_PATTERNS, map_rat_ext, map_rat_ext_2017,
                    map_rat_cue, map_rat_reinstatement)
from utils import normalize_msn

META = {"Subject": "012F", "Start Date": "08/03/25", "End Date": "08/03/25",
        "Start Time": "09:00:00", "End Time": "19:00:00", "Box": "1"}

EXT = "RAT - EXTINCTION"
EXT17 = "RAT - EXTINCTION ONLY (2017, NO REINSTATEMENT)"
REIN = "RAT - REINSTATEMENT"
ALL_LETTERS = [c for c in string.ascii_uppercase if c not in "BCVYZ"]  # those are arrays


def rec(msn, scalars):
    """A record as MedPC writes it: every scalar letter present, default 0."""
    s = {k: 0.0 for k in ALL_LETTERS}
    s.update({k: float(v) for k, v in scalars.items()})
    return ParsedSession(meta=dict(META, MSN=msn), scalars=s,
                         arrays={}, filename="t", raw_block="")


def types(segs):
    return [s["segment_type"] for s in segs]


def ext_sessions(segs):
    return [s["active_responses"] for s in segs if s["segment_type"] == "extinction_session"]


fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "  -> " + str(detail)))
    if not cond:
        fails.append(name)


# 1. MSN routing -------------------------------------------------------------
routes = {
    "EXTINCT MUST EXT BY 9 FOR REINST ESD": EXT,
    "EXTINCT MUST EXT BY 9 FOR REINSTATE G136A BOXES ESD": EXT,
    "EXTINCT MUST EXT BY 9 FOR REINSTATE G140 A BOXES ESD": EXT,
    "EXTINCT MUST EXT BY 9 FOR REINSTATE G140 B BOXES ESD": EXT,
    "B BOXES EXTINCT MUST EXT BY 9 FOR REINST ESD": EXT,
    "Z TEST EXTINCT MUST EXT BY 9 FOR REINST ESD": EXT,
    "EXTINCT-REINSTATE G140 A BOXES ESD": EXT,
    "EXTINCT-REINSTATE G138 A BOXES ESD": EXT,
    "EXTINCT-REINSTATE G126 2018": EXT,
    "G136B EXTINCT MUST EXT BY 9 FOR REINST ESD": EXT,
    "g136B EXTINCT-REINSTATE  ESD": EXT,
    "EXTINCTION G140 ABOXES 2017": EXT17,
    "Extinction G126 2017": EXT17,
    "ONLY REIN": REIN,
    "G136A ONLY REIN": REIN,
    "REINSTATEMENT G140 ABOXES 2017": REIN,
    "REINSTATEMENT G126 2017": REIN,
}
for msn, want in routes.items():
    got = resolve_program(normalize_msn(msn), DEFAULT_MSN_PATTERNS)
    check(f"route {msn!r}", got == want, f"got {got!r}, want {want!r}")

for msn in ("G136A PRCOCAINE ESD", "G136A FR20 ESD", "G136A FLUSH ESD",
            "G136A PRFENT ESD"):
    got = resolve_program(normalize_msn(msn), DEFAULT_MSN_PATTERNS)
    check(f"{msn!r} is not classified as extinction",
          got is not None and "EXTINCTION" not in got, f"got {got!r}")

# 2. Reinstatement row follows the E flag, not presence ----------------------
#    Animal ran 6 sessions; session 6 had < 15 presses, so the program started
#    the cue phase (E = 0).
ran6 = dict(A=46, D=24, F=4, G=18, H=9, I=7, Q=6, P=12)
ran6["U"] = sum(ran6[k] for k in "ADFGHI")

reinst = rec("EXTINCT MUST EXT BY 9 FOR REINST ESD", dict(ran6, E=0, M=31, N=22, O=5, P=17))
segs_r = build_segments(reinst, map_rat_ext, EXT)
check("E = 0 with presses -> exactly one reinstatement row",
      types(segs_r).count("reinstatement_test") == 1, types(segs_r))
row = [s for s in segs_r if s["segment_type"] == "reinstatement_test"][0]
check("  ...reading M / O / N correctly",
      (row["active_responses"], row["inactive_responses"], row["cue_deliveries"])
      == (31, 5, 22), row)

zero = rec("EXTINCT MUST EXT BY 9 FOR REINST ESD", dict(ran6, E=0))
segs_z = build_segments(zero, map_rat_ext, EXT)
zrow = [s for s in segs_z if s["segment_type"] == "reinstatement_test"]
check("E = 0 with M = N = O = 0 -> KEPT as a real zero-response test",
      len(zrow) == 1 and zrow[0]["active_responses"] == 0, types(segs_z))

# Program ended without the cue phase (S.S.23 at session 9, or stopped early):
# E stays 1, M/N/O are present but 0.
ran9 = dict(A=60, D=50, F=40, G=35, H=30, I=25, J=22, K=20, L=18, Q=9, E=1, P=9)
ran9["U"] = sum(ran9[k] for k in "ADFGHIJKL")
no_reinst = rec("EXTINCT MUST EXT BY 9 FOR REINST ESD", ran9)
segs_n = build_segments(no_reinst, map_rat_ext, EXT)
check("E = 1 (never reached cue phase) -> NO reinstatement row, despite M/N/O present",
      "reinstatement_test" not in types(segs_n), types(segs_n))
check("  ...and all 9 sessions reported", len(ext_sessions(segs_n)) == 9, len(segs_n))

# Without a flag variable the fallback needs a non-zero count.
noflag = dict(map_rat_ext, reinstatement_flag_var=None)
check("fallback (no flag var): zeros -> no row",
      "reinstatement_test" not in types(build_segments(zero, noflag, EXT)))
check("fallback (no flag var): N > 0 -> row",
      "reinstatement_test" in types(build_segments(
          rec("x", dict(ran6, E=1, N=3)), noflag, EXT)))

# 3. Sessions bounded by Q ---------------------------------------------------
acts = ext_sessions(segs_r)
check("Q = 6 -> sessions 7-9 (present as 0) are NOT reported", len(acts) == 6, acts)
check("  ...and the 6 reported sessions sum to U", sum(acts) == ran6["U"], (sum(acts), ran6["U"]))

noq = dict(map_rat_ext, session_count_var=None)
check("(control) without the Q bound the 0-filled sessions 7-9 reappear",
      len(ext_sessions(build_segments(reinst, noq, EXT))) == 9)

# 4. Extinction-only 2017 programs -------------------------------------------
e17 = dict(A=50, D=30, F=20, G=15, H=12, I=10, J=8, K=6, L=4, M=3, P=9, Q=10, E=0)
e17["U"] = sum(e17[k] for k in "ADFGHIJKLM")
s17 = rec("EXTINCTION G140 ABOXES 2017", e17)
segs17 = build_segments(s17, map_rat_ext_2017, EXT17)
a17 = ext_sessions(segs17)
check("2017: Q = 10 -> 10 extinction sessions", len(a17) == 10, len(a17))
check("2017: NO reinstatement test (E = 0 here means 'session end')",
      "reinstatement_test" not in types(segs17), types(segs17))
check("2017: sessions sum to U incl. session 10 = M", sum(a17) == e17["U"], (sum(a17), e17["U"]))

# G126 2017 shape: stopped after 6 sessions, M = N = O = 0, E = 0
g126 = dict(A=1, G=7, Q=6, P=1, E=0)
g126["U"] = 8
sg = build_segments(rec("Extinction G126 2017", g126), map_rat_ext_2017, EXT17)
check("G126 2017 record: 6 sessions, no reinstatement row",
      len(ext_sessions(sg)) == 6 and "reinstatement_test" not in types(sg), types(sg))
bad = build_segments(rec("Extinction G126 2017", g126), map_rat_ext, EXT)
check("(control) the 9-session mapping WOULD invent a reinstatement test for it",
      "reinstatement_test" in types(bad))

# 5. P double-count correction -----------------------------------------------
df, _, _, _, _ = process_sessions([reinst])
r = df.iloc[0]
check("inactive_presses still reports raw P", r["inactive_presses"] == 17, r["inactive_presses"])
check("extinction-only inactive = P - O", r["inactive_presses_extinction_only"] == 12,
      r["inactive_presses_extinction_only"])
check("reinstatement inactive = O", r["inactive_presses_reinstatement"] == 5,
      r["inactive_presses_reinstatement"])
df2, _, _, _, _ = process_sessions([no_reinst])
check("no-reinstatement record: extinction-only inactive == P",
      df2.iloc[0]["inactive_presses_extinction_only"] == 9)

# 6. End to end ----------------------------------------------------------------
df3, _, _, seg3, un3 = process_sessions([s17])
check("2017 record is mapped, not dropped", len(df3) == 1 and len(un3) == 0, (len(df3), len(un3)))
check("2017 active_presses == U", df3.iloc[0]["active_presses"] == e17["U"])
check("2017 end-to-end: 10 segments, no reinstatement",
      len(seg3) == 10 and "reinstatement_test" not in list(seg3["segment_type"]),
      list(seg3["segment_type"]))

# 7. Standalone reinstatement (ONLY REIN / REINSTATEMENT ... 2017) -----------
onlyr = rec("ONLY REIN", dict(M=40, N=30, O=6))
rs = build_segments(onlyr, map_rat_reinstatement, REIN)
check("ONLY REIN yields one reinstatement row with M / O / N",
      len(rs) == 1 and (rs[0]["active_responses"], rs[0]["inactive_responses"],
                        rs[0]["cue_deliveries"]) == (40, 6, 30), rs)

# 8. Cue relapse 30-minute bins (separate program, side fix) -----------------
cue = rec("G138A CUE RELAPSE 7HR PRETX HOLD",
          dict(A=19, G=1, H=2, R=20, M=2, N=17, Q=4))
labels = [s["segment_label"] for s in build_segments(cue, map_rat_cue, "cue")]
check("cue relapse bins are 30 min wide",
      labels == ["0-30 min", "30-60 min", "60-90 min", "90-120 min"], labels)

# 9. Duplicate session records (all programs) --------------------------------
from analyzer import deduplicate_sessions


def at(msn, scalars, start="11:56:05", end_date="08/07/25", end="11:43:05", subj="O525F", box="10"):
    s = rec(msn, scalars)
    s.meta.update({"Subject": subj, "Start Date": "08/06/25", "Start Time": start,
                   "End Date": end_date, "End Time": end, "Box": box})
    return s


FENT = "FENTANYL 1 SEC FR40 LD ESD"
interim = at(FENT, dict(I=22, R=27, A=28), end="11:00:00")
final = at(FENT, dict(I=26, R=32, A=29), end="11:43:05")
kept, report = deduplicate_sessions([final, interim])   # final listed first on purpose
check("interim + final save -> one record, the later-ending one",
      len(kept) == 1 and kept[0].scalars["I"] == 26, [k.scalars["I"] for k in kept])
check("  ...and the dropped copy is reported", len(report) == 1 and "interim" in report.iloc[0]["copy"])

kept2, rep2 = deduplicate_sessions([final, at(FENT, dict(I=26, R=32, A=29))])
check("two identical copies -> one record, reported as identical",
      len(kept2) == 1 and rep2.iloc[0]["copy"] == "identical")

other_box = at(FENT, dict(I=5), box="11")
other_time = at(FENT, dict(I=5), start="12:00:00")
kept3, _ = deduplicate_sessions([final, other_box, other_time])
check("different Box or Start Time are different sessions (all kept)", len(kept3) == 3)

df_d, _, _, _, _ = process_sessions([interim, final])
check("process_sessions counts the session once, with the final numbers",
      len(df_d) == 1 and df_d.iloc[0]["infusions"] == 26, df_d["infusions"].tolist())

print()
print(("FAILED: " + ", ".join(fails)) if fails else "ALL TESTS PASSED")
raise SystemExit(1 if fails else 0)
