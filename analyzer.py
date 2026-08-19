import pandas as pd
from typing import List, Tuple, Optional, Set, Dict, Any
import re
import streamlit as st
from config import DEFAULT_MSN_PATTERNS, DEFAULT_VARIABLE_MAPPINGS
from parser import ParsedSession
from utils import canonicalize_id, extract_gender, normalize_msn

# ─── Pump and drug constants ──────────────────────────────────────────────────
PUMP_RATE_ML_SEC = 0.0172  # ml/sec

AVG_INF_DUR_COCAINE  = 4.0
AVG_INF_DUR_FENTANYL = 1.5
AVG_INF_DUR_NICOTINE = 1.0

COCAINE_1_5MGKG_DUR = {
    100: 1.3, 110: 1.4, 120: 1.5, 130: 1.6, 140: 1.8, 150: 1.9, 160: 2.0, 170: 2.1, 180: 2.3, 190: 2.4,
    200: 2.5, 210: 2.6, 220: 2.8, 230: 2.9, 240: 3.0, 250: 3.1, 260: 3.3, 270: 3.4, 280: 3.5, 290: 3.6,
    300: 3.8, 310: 3.9, 320: 4.0, 330: 4.1, 340: 4.2, 350: 4.4, 360: 4.5, 370: 4.6, 380: 4.7, 390: 4.9,
    400: 5.0, 410: 5.1, 420: 5.2, 430: 5.4, 440: 5.5, 450: 5.6, 460: 5.7, 470: 5.9, 480: 6.0, 490: 6.1,
    500: 6.2, 510: 6.4, 520: 6.5, 530: 6.6, 540: 6.8, 550: 6.9, 560: 7.0, 570: 7.1, 580: 7.3, 590: 7.4,
    600: 7.5, 610: 7.6, 620: 7.8, 630: 7.9, 640: 8.0, 650: 8.1, 660: 8.3, 670: 8.4, 680: 8.5, 690: 8.6,
    700: 8.8, 710: 8.9, 720: 9.0, 730: 9.1, 740: 9.3, 750: 9.4, 760: 9.5, 770: 9.6, 780: 9.8, 790: 9.9,
    800: 10.0, 810: 10.1, 820: 10.3, 830: 10.4, 840: 10.5, 850: 10.6, 860: 10.8, 870: 10.9, 880: 11.0, 890: 11.1,
}

COCAINE_0_5MGKG_DUR = {
    100: 0.4, 110: 0.5, 120: 0.5, 130: 0.5, 140: 0.6, 150: 0.6, 160: 0.7, 170: 0.7, 180: 0.7, 190: 0.8,
    200: 0.8, 210: 0.9, 220: 0.9, 230: 1.0, 240: 1.0, 250: 1.0, 260: 1.1, 270: 1.1, 280: 1.2, 290: 1.2,
    300: 1.2, 310: 1.3, 320: 1.3, 330: 1.4, 340: 1.4, 350: 1.5, 360: 1.5, 370: 1.5, 380: 1.6, 390: 1.6,
    400: 1.7, 410: 1.7, 420: 1.7, 430: 1.8, 440: 1.8, 450: 1.9, 460: 1.9, 470: 2.0, 480: 2.0, 490: 2.0,
    500: 2.1, 510: 2.1, 520: 2.2, 530: 2.2, 540: 2.2, 550: 2.3, 560: 2.3, 570: 2.4, 580: 2.4, 590: 2.5,
    600: 2.5, 610: 2.5, 620: 2.6, 630: 2.6, 640: 2.7, 650: 2.7, 660: 2.7, 670: 2.8, 680: 2.8, 690: 2.9,
    700: 2.9, 710: 3.0, 720: 3.0, 730: 3.0, 740: 3.1, 750: 3.1, 760: 3.2, 770: 3.2, 780: 3.2, 790: 3.3,
    800: 3.3, 810: 3.4, 820: 3.4, 830: 3.4, 840: 3.5, 850: 3.5, 860: 3.6, 870: 3.6, 880: 3.6, 890: 3.7,
}

COCAINE_0_3MGKG_DUR = {
    100: 0.3, 110: 0.3, 120: 0.3, 130: 0.3, 140: 0.4, 150: 0.4, 160: 0.4, 170: 0.4, 180: 0.5, 190: 0.5,
    200: 0.5, 210: 0.5, 220: 0.6, 230: 0.6, 240: 0.6, 250: 0.6, 260: 0.7, 270: 0.7, 280: 0.7, 290: 0.7,
    300: 0.8, 310: 0.8, 320: 0.8, 330: 0.8, 340: 0.9, 350: 0.9, 360: 0.9, 370: 0.9, 380: 1.0, 390: 1.0,
    400: 1.0, 410: 1.0, 420: 1.1, 430: 1.1, 440: 1.1, 450: 1.1, 460: 1.2, 470: 1.2, 480: 1.2, 490: 1.2,
    500: 1.3, 510: 1.3, 520: 1.3, 530: 1.3, 540: 1.4, 550: 1.4, 560: 1.4, 570: 1.4, 580: 1.5, 590: 1.5,
    600: 1.5, 610: 1.5, 620: 1.6, 630: 1.6, 640: 1.6, 650: 1.6, 660: 1.7, 670: 1.7, 680: 1.7, 690: 1.8,
    700: 1.8, 710: 1.8, 720: 1.8, 730: 1.9, 740: 1.9, 750: 1.9, 760: 2.0, 770: 2.0, 780: 2.0, 790: 2.0,
    800: 2.1, 810: 2.1, 820: 2.1, 830: 2.1, 840: 2.2, 850: 2.2, 860: 2.2, 870: 2.2, 880: 2.3, 890: 2.3,
}

NICOTINE_DUR = {
    100: 0.6, 110: 0.7, 120: 0.8, 130: 0.8, 140: 0.9, 150: 0.9, 160: 1.0, 170: 1.1, 180: 1.1, 190: 1.2,
    200: 1.3, 210: 1.3, 220: 1.4, 230: 1.4, 240: 1.5, 250: 1.6, 260: 1.6, 270: 1.7, 280: 1.8, 290: 1.8,
    300: 1.9, 310: 1.9, 320: 2.0, 330: 2.1, 340: 2.1, 350: 2.2, 360: 2.3, 370: 2.3, 380: 2.4, 390: 2.4,
    400: 2.5, 410: 2.6, 420: 2.6, 430: 2.7, 440: 2.7, 450: 2.8, 460: 2.9, 470: 2.9, 480: 3.0, 490: 3.0,
    500: 3.1, 510: 3.2, 520: 3.2, 530: 3.3, 540: 3.3, 550: 3.4, 560: 3.5, 570: 3.5, 580: 3.6, 590: 3.6,
    600: 3.7, 610: 3.8, 620: 3.8, 630: 3.9, 640: 3.9, 650: 4.0, 660: 4.1, 670: 4.1, 680: 4.2, 690: 4.2,
    700: 4.3, 710: 4.4, 720: 4.4, 730: 4.5, 740: 4.5, 750: 4.6, 760: 4.7, 770: 4.7, 780: 4.8, 790: 4.8,
    800: 4.9, 810: 5.0, 820: 5.0, 830: 5.1, 840: 5.1, 850: 5.2, 860: 5.3, 870: 5.3, 880: 5.4, 890: 5.4,
}

FENTANYL_DUR = {
    100: 0.5, 110: 0.5, 120: 0.5, 130: 0.5, 140: 0.5, 150: 0.5, 160: 0.5, 170: 0.5, 180: 0.5, 190: 0.5,
    200: 0.5, 210: 0.5, 220: 0.6, 230: 0.6, 240: 0.6, 250: 0.6, 260: 0.6, 270: 0.6, 280: 0.6, 290: 0.6,
    300: 0.7, 310: 0.7, 320: 0.7, 330: 0.7, 340: 0.7, 350: 0.7, 360: 0.7, 370: 0.7, 380: 0.8, 390: 0.8,
    400: 0.8, 410: 0.8, 420: 0.8, 430: 0.8, 440: 0.8, 450: 0.8, 460: 0.9, 470: 0.9, 480: 0.9, 490: 0.9,
    500: 1.0, 510: 1.0, 520: 1.0, 530: 1.0, 540: 1.0, 550: 1.0, 560: 1.1, 570: 1.1, 580: 1.1, 590: 1.1,
    600: 1.2, 610: 1.2, 620: 1.2, 630: 1.2, 640: 1.2, 650: 1.3, 660: 1.3, 670: 1.3, 680: 1.3, 690: 1.3,
    700: 1.4, 710: 1.4, 720: 1.4, 730: 1.4, 740: 1.4, 750: 1.5, 760: 1.5, 770: 1.5, 780: 1.5, 790: 1.5,
    800: 1.6, 810: 1.6, 820: 1.6, 830: 1.6, 840: 1.6, 850: 1.7, 860: 1.7, 870: 1.7, 880: 1.7, 890: 1.7,
}

DEFAULT_WEIGHT_G = 300.0


# ═════════════════════════════════════════════════════════════════════════════
# v7.0 — corrections.  Each is justified in config.py's header block.
#
#   • Unrecognised MSNs are no longer analysed with the FR20 mapping under the
#     label "UNMAPPED".  They are skipped and returned in df_unmapped so they
#     show up in the UI and the export instead of producing plausible-looking
#     numbers from the wrong variables.
#   • calculate_duration uses Start/End DATE as well as time.  1,381 sessions
#     in the current dataset span more than one calendar day (48 h and 96 h
#     withdrawal holds); v6.3 wrapped every one of them to under 24 h.
#   • PR breakpoint comes from the F ratio array at the last completed
#     infusion, not the scalar V (fountain-valve time, 0.05 s).
#   • Hourly binning: the FR/fentanyl/PR family now uses the 7-column J block
#     (verified to reproduce the R/I/A scalars exactly on all 647 fentanyl
#     records) and C for active-press times, so active_events is no longer 0.
#   • build_segments expands multi-session records — extinction sessions 1-9
#     plus the reinstatement test, and cue-relapse hourly segments — into one
#     row each, so no test session is collapsed into a single total.
# ═════════════════════════════════════════════════════════════════════════════


def _round_weight_to_table(weight_g: float) -> int:
    """Round weight to nearest 10 g, clamped to [100, 890]."""
    return max(100, min(890, round(weight_g / 10) * 10))


def robust_parse_date(date_str: str) -> pd.Timestamp:
    if not date_str or pd.isna(date_str):
        return pd.NaT
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%m-%d-%y", "%m-%d-%Y",
                "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return pd.to_datetime(date_str, format=fmt, errors="raise")
        except Exception:
            continue
    return pd.NaT


def get_val(session: ParsedSession, var_name: Any, default: float = 0.0) -> float:
    """
    Safely retrieve a value from a session as a float.
      None   → default
      []     → default
      "B(2)" → array index lookup
      "I"    → scalar lookup, falling back to the array of the same letter
    """
    if var_name is None:
        return float(default)
    if isinstance(var_name, list):
        if not var_name:
            return float(default)
        var_name = var_name[0]
    var_str = str(var_name)

    m = re.match(r"^([A-Z])\((\d+)\)$", var_str)
    if m:
        arr = session.arrays.get(m.group(1), [])
        idx = int(m.group(2))
        return float(arr[idx]) if len(arr) > idx else float(default)

    if var_str in session.scalars:
        try:
            return float(session.scalars[var_str])
        except (ValueError, TypeError):
            return float(default)
    return float(default)


def _hms_to_seconds(s: str) -> Optional[float]:
    if not s:
        return None
    parts = str(s).strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 3600 + int(parts[1]) * 60
    except (ValueError, IndexError):
        return None
    return None


def calculate_duration(session: ParsedSession, mapping: dict) -> float:
    """
    Session duration in seconds.

    Resolution order:
      1. mapping["duration"] when it is not "Z".  Z is the wall-clock time at
         session end (Z(0)=Hr, Z(1)=Min, Z(2)=Sec), not an elapsed time, and
         for the whole FR/PR family it is not even written to disk.
         "S" (intermittent access elapsed seconds) resolves here.
      2. Legacy explicit-unit keys.
      3. Start Date + Start Time → End Date + End Time.  Using the dates
         matters: withdrawal holds in this dataset run 48 h and 96 h, and a
         time-only difference wraps them into a single day.
      4. Start/End Time only, rolling forward one day if end < start.
      5. 0.0
    """
    dur_key = mapping.get("duration")
    if dur_key and dur_key not in (None, "Z"):
        val = get_val(session, dur_key)
        if val > 0:
            return val

    for key, mult in (("duration_sec", 1), ("duration_min", 60), ("duration_hour", 3600)):
        if key in mapping:
            val = get_val(session, mapping[key]) * mult
            if val > 0:
                return val

    t0 = _hms_to_seconds(session.meta.get("Start Time", ""))
    t1 = _hms_to_seconds(session.meta.get("End Time", ""))
    d0 = robust_parse_date(session.meta.get("Start Date", ""))
    d1 = robust_parse_date(session.meta.get("End Date", ""))

    if t0 is not None and t1 is not None:
        if pd.notna(d0) and pd.notna(d1):
            diff = (d1 - d0).days * 86400 + (t1 - t0)
            # A box that never advanced End Date still rolls past midnight.
            if diff < 0:
                diff += 86400
            if diff > 0:
                return float(diff)
        diff = t1 - t0
        if diff < 0:
            diff += 86400
        if diff > 0:
            return float(diff)

    return 0.0


def resolve_program(norm_msn: str, patterns: Dict[str, List[str]]) -> Optional[str]:
    """First program whose pattern is a substring of the normalised MSN.

    Dict order is the precedence order, so a program whose name contains
    another program's name must be listed above it in config.py.
    """
    for name, pats in patterns.items():
        for pat in pats:
            p = normalize_msn(pat)
            if p and p in norm_msn:
                return name
    return None


def compute_breakpoint(session: ParsedSession, mapping: dict, infusions: float) -> float:
    """
    Progressive-ratio breakpoint = the last ratio the animal completed.

    PRFENT/PRCOCAINE store the PR schedule in array F, indexed by H, so the
    breakpoint after `infusions` completed ratios is F[infusions - 1].
    v6.3 read the scalar V, which is the fountain-valve time (default 0.05 s),
    and wrote 0.05 into every PR row.
    """
    key = mapping.get("breakpoint")
    if not key:
        return 0.0
    if mapping.get("breakpoint_mode") == "RATIO_ARRAY_AT_LAST_INFUSION":
        ratios = session.arrays.get(str(key), [])
        n = int(infusions)
        if n <= 0 or not ratios:
            return 0.0
        return float(ratios[min(n, len(ratios)) - 1])
    return get_val(session, key)


def hourly_from_j_array(j: List[float]) -> List[Dict[str, float]]:
    """
    FR / fentanyl / PR hourly block.  The .MPC documents the layout as

        J(Q)=H.M, J(Q+1)=R, J(Q+2)=I, J(Q+3)=D, J(Q+4)=A, J(Q+5)=L, J(Q+6)=F

    — seven columns per clock hour: hour, active presses, infusions, presses
    during infusion, inactive presses, licks, ratio in effect.  Column sums
    reproduce the R / I / A scalars exactly on all 647 fentanyl records in the
    current dataset, so this is the authoritative within-session breakdown for
    these programs.

    All-zero trailing slots (the array is DIM 170 regardless of session length)
    are dropped so a 6-hour session does not contribute 18 phantom rows.
    """
    rows = []
    for i in range(0, len(j) - 6, 7):
        hour, act, inf, in_inf, inact, licks, ratio = j[i:i + 7]
        if hour == 0 and act == 0 and inf == 0 and inact == 0 and licks == 0:
            continue
        rows.append({
            "hour": int(hour),
            "infusion_events": inf,
            "active_events": act,
            "inactive_events": inact,
            "presses_during_infusion": in_inf,
            "licks": licks,
            "ratio_in_effect": ratio,
        })
    return rows


def build_segments(session: ParsedSession, mapping: dict, prog: str) -> List[Dict[str, Any]]:
    """
    Expand a record that contains several test sessions into one row per
    session.  Without this, an extinction record collapses nine hourly
    extinction sessions plus a reinstatement test into a single total, and a
    cue-relapse record collapses four hourly segments into one.

    Extinction (EXTINCT MUST EXT BY 9 FOR REINST ESD):
        A, D, F, G, H, I, J, K, L = active responses in sessions 1-9
        (S.S.: "#R^LLEVER: IF Q = n → ADD <var>"), U = their total,
        P = inactive during extinction.  The terminal reinstatement test uses
        M (responses), N (cue deliveries) and O (inactive lever).

    Cue relapse (G136A/G136B/G138A/G138B/G140A/G140B CUE RELAPSE):
        Q is the segment counter, incremented every time C(T) reaches 3600 s.
        A, D, F, G hold active responses for segments 1-4 and H, I, J, K the
        matching inactive counts.  The segment timer is 3600 s in every
        production variant, so these are HOURLY bins — the "0-30 min" comments
        in the .MPC headers are stale and describe an earlier revision.
    """
    special = mapping.get("special_processing")
    rows: List[Dict[str, Any]] = []

    if special == "EXTINCTION_DETAIL":
        for idx, letter in enumerate(mapping.get("extinction_session_vars", []), start=1):
            if letter not in session.scalars:
                continue
            rows.append({
                "segment_type":        "extinction_session",
                "segment_index":       idx,
                "segment_label":       f"extinction session {idx}",
                "segment_minutes":     None,
                "active_responses":    get_val(session, letter),
                "inactive_responses":  None,
                "cue_deliveries":      None,
                "source_variable":     letter,
            })
        # Terminal reinstatement test, if this record reached it.
        m_key = mapping.get("reinstatement_active")
        if m_key:
            rows.append({
                "segment_type":       "reinstatement_test",
                "segment_index":      len(rows) + 1,
                "segment_label":      "reinstatement test",
                "segment_minutes":    None,
                "active_responses":   get_val(session, m_key),
                "inactive_responses": get_val(session, mapping.get("reinstatement_inactive")),
                "cue_deliveries":     get_val(session, mapping.get("reinstatement_cues")),
                "source_variable":    m_key,
            })

    elif special == "REINSTATEMENT_DETAIL":
        rows.append({
            "segment_type":       "reinstatement_test",
            "segment_index":      1,
            "segment_label":      "reinstatement test",
            "segment_minutes":    None,
            "active_responses":   get_val(session, mapping.get("reinstatement_active")),
            "inactive_responses": get_val(session, mapping.get("reinstatement_inactive")),
            "cue_deliveries":     get_val(session, mapping.get("reinstatement_cues")),
            "source_variable":    mapping.get("reinstatement_active"),
        })

    elif special == "CUE_RELAPSE_SEGMENTS":
        act_vars = mapping.get("active_segment_vars", [])
        inact_vars = mapping.get("inactive_segment_vars", [])
        width_min = int(mapping.get("segment_seconds", 3600)) // 60
        n_seg = max(len(act_vars), len(inact_vars))
        for idx in range(n_seg):
            a_key = act_vars[idx] if idx < len(act_vars) else None
            i_key = inact_vars[idx] if idx < len(inact_vars) else None
            rows.append({
                "segment_type":       "relapse_segment",
                "segment_index":      idx + 1,
                "segment_label":      f"{idx * width_min}-{(idx + 1) * width_min} min",
                "segment_minutes":    width_min,
                "active_responses":   get_val(session, a_key),
                "inactive_responses": get_val(session, i_key),
                "cue_deliveries":     None,
                "source_variable":    a_key,
            })

    return rows


def process_sessions(
    sessions: List[ParsedSession],
    allowed_ids: Optional[Set[str]] = None,
    custom_patterns: Optional[Dict] = None,
    custom_mappings: Optional[Dict] = None,
    avg_weight_g: float = DEFAULT_WEIGHT_G,
    drug_type: str = "None",
    conc_mgml: float = 1.0,
) -> Tuple[pd.DataFrame, pd.DataFrame, Set[str], pd.DataFrame, pd.DataFrame]:
    """
    Returns (df_sessions, df_hourly, found_ids, df_segments, df_unmapped).

    NOTE: v6.3 returned a 3-tuple.  Callers must be updated to

        df_sess, df_hr, found, df_seg, df_unmapped = process_sessions(...)
    """

    patterns   = custom_patterns or DEFAULT_MSN_PATTERNS
    mappings   = custom_mappings or DEFAULT_VARIABLE_MAPPINGS
    all_rows   = []
    all_hourly = []
    all_segments = []
    unmapped   = []
    found: Set[str] = set()
    weight_key = _round_weight_to_table(avg_weight_g)

    for sess in sessions:
        canon = canonicalize_id(sess.meta.get("Subject", ""))
        if not canon:
            continue
        if allowed_ids and canon not in allowed_ids:
            continue

        gender   = extract_gender(canon)
        raw_msn  = sess.meta.get("MSN", "")
        norm_msn = normalize_msn(raw_msn)
        start_dt = robust_parse_date(sess.meta.get("Start Date", ""))

        prog = resolve_program(norm_msn, patterns)
        if prog is None or prog not in mappings:
            # Do NOT fall back to the FR20 mapping.  Reading I/R/A out of a
            # program that uses those letters for something else produces
            # numbers that look reasonable and are meaningless.
            unmapped.append({
                "canonical_subject": canon,
                "raw_msn":           raw_msn,
                "start_date":        start_dt,
                "file":              sess.filename,
                "reason":            "No MSN pattern matched" if prog is None
                                     else f"No variable mapping for program '{prog}'",
            })
            continue

        mapping = mappings[prog]
        found.add(canon)

        end_dt       = robust_parse_date(sess.meta.get("End Date", ""))
        duration_sec = calculate_duration(sess, mapping)

        if drug_type == "Fentanyl" or "FENTANYL" in prog.upper():
            inf_dur_sec = FENTANYL_DUR.get(weight_key, AVG_INF_DUR_FENTANYL)
        elif drug_type == "Nicotine" or "NICOTINE" in prog.upper():
            inf_dur_sec = NICOTINE_DUR.get(weight_key, AVG_INF_DUR_NICOTINE)
        else:
            inf_dur_sec = COCAINE_1_5MGKG_DUR.get(weight_key, AVG_INF_DUR_COCAINE)

        infusion_count   = get_val(sess, mapping.get("infusions"))
        active_presses   = get_val(sess, mapping.get("active_presses"))
        inactive_presses = get_val(sess, mapping.get("inactive_presses"))
        pump_time_raw    = get_val(sess, mapping.get("pump_time"))
        breakpoint_val   = compute_breakpoint(sess, mapping, infusion_count)

        estimated_volume_ml   = infusion_count * PUMP_RATE_ML_SEC * inf_dur_sec
        estimated_intake_mgkg = (
            infusion_count * conc_mgml * PUMP_RATE_ML_SEC * inf_dur_sec
            / (avg_weight_g / 1000)
        ) if conc_mgml > 0 and avg_weight_g > 0 else 0.0

        row = {
            "canonical_subject":   canon,
            "gender":              gender,
            "program_name":        prog,
            "raw_msn":             raw_msn,
            "start_date":          start_dt,
            "end_date":            end_dt,
            "session_span_days":   (
                (end_dt - start_dt).days + 1
                if pd.notna(end_dt) and pd.notna(start_dt) else 1
            ),
            "overnight_session":   (
                pd.notna(end_dt) and pd.notna(start_dt) and (end_dt > start_dt)
            ),
            "duration_sec":        duration_sec,
            "duration_hr":         round(duration_sec / 3600.0, 3),
            "active_presses":      active_presses,
            "inactive_presses":    inactive_presses,
            "infusions":           infusion_count,
            "pump_time_sec":       pump_time_raw,
            "breakpoints":         breakpoint_val,
            "retrievals":          get_val(sess, mapping.get("retrievals")),
            "responses":           get_val(sess, mapping.get("responses")),
            "W_value":             get_val(sess, mapping.get("W_value", "W")),
            "T_value":             get_val(sess, mapping.get("T_value", "T")),
            "timeout_presses_per_inf": (
                get_val(sess, mapping.get("W_value", "W")) / (infusion_count + 1e-6)
            ),
            "estimated_volume_ml":   estimated_volume_ml,
            "estimated_inf_dur_sec": inf_dur_sec,
            "estimated_intake_mgkg": estimated_intake_mgkg,
            "U_value": get_val(sess, mapping.get("U_value")),
            "V_value": get_val(sess, mapping.get("V_value")),
            "timeout_active":        0,
            "timeout_inactive":      0,
            "post_session_active":   0,
            "post_session_inactive": 0,
            "pr_schedule":           [],
            "session_params":        [],
            "no_behavioural_data":   bool(mapping.get("no_behavioural_data")),
            "mapping_unverified":    bool(mapping.get("unverified")),
            "Box":  sess.meta.get("Box",  ""),
            "Room": sess.meta.get("Room", "") or sess.meta.get("Experiment", ""),
        }

        special = mapping.get("special_processing")

        if special == "MOUSE_ADVANCED":
            b_array = sess.arrays.get("B", [])
            row["timeout_active"]        = b_array[6] if len(b_array) > 6 else 0
            row["timeout_inactive"]      = b_array[7] if len(b_array) > 7 else 0
            row["post_session_active"]   = b_array[8] if len(b_array) > 8 else 0
            row["post_session_inactive"] = b_array[9] if len(b_array) > 9 else 0
            row["active_timestamps"]     = sess.arrays.get(mapping.get("active_timestamps", "L"), [])
            row["inactive_timestamps"]   = sess.arrays.get(mapping.get("inactive_timestamps", "R"), [])
            row["pr_schedule"]           = sess.arrays.get(mapping.get("pr_schedule", "P"), [])
            row["session_params"]        = sess.arrays.get(mapping.get("z_params", "Z"), [])
        else:
            # Real per-event time arrays.  For the FR/PR family C holds the
            # active-press times (len(C) == R) and W the infusion times
            # (len(W) == I); v6.3 stored infusion times under the name
            # "active_timestamps", so the within-session cumulative plot was
            # labelled "Active Responses" but drew infusions.
            act_key = mapping.get("active_timestamps")
            inf_key = mapping.get("infusion_timestamps")
            row["active_timestamps"]   = (
                sess.arrays.get(act_key, [])[:int(active_presses)] if act_key else []
            )
            row["infusion_timestamps"] = (
                sess.arrays.get(inf_key, [])[:int(infusion_count)] if inf_key else []
            )
            row["inactive_timestamps"] = (
                sess.arrays.get(mapping.get("inactive_timestamps"), [])
                if mapping.get("inactive_timestamps") else []
            )
            row["pr_schedule"]    = sess.arrays.get("F", []) if mapping.get("breakpoint") == "F" else []
            row["session_params"] = []

        all_rows.append(row)

        # ── Segment expansion (extinction sessions, relapse segments) ───────
        for seg in build_segments(sess, mapping, prog):
            all_segments.append({
                "canonical_subject": canon,
                "gender":            gender,
                "program_name":      prog,
                "raw_msn":           raw_msn,
                "start_date":        start_dt,
                "Box":               row["Box"],
                "Room":              row["Room"],
                **seg,
            })

        # ── Hourly binning ──────────────────────────────────────────────────
        hourly_rows: List[Dict[str, Any]] = []

        if special == "J_ARRAY_HOURLY":
            j = sess.arrays.get(mapping.get("j_array", "J"), [])
            hourly_rows = hourly_from_j_array(j)
        else:
            ts_inf = row.get("infusion_timestamps") or []
            ts_act = row.get("active_timestamps") or []
            ts_inact = row.get("inactive_timestamps") or []
            hours = set()
            for t in list(ts_inf) + list(ts_act) + list(ts_inact):
                hours.add(int(t // 3600))
            for h in sorted(hours):
                hourly_rows.append({
                    "hour": h,
                    "infusion_events": sum(1 for t in ts_inf if int(t // 3600) == h),
                    "active_events":   sum(1 for t in ts_act if int(t // 3600) == h),
                    "inactive_events": sum(1 for t in ts_inact if int(t // 3600) == h),
                })

        for hr_row in hourly_rows:
            all_hourly.append({
                "canonical_subject": canon,
                "gender":            gender,
                "program_name":      prog,
                "start_date":        start_dt,
                "Box":  row["Box"],
                "Room": row["Room"],
                **hr_row,
            })

    df_sessions  = pd.DataFrame(all_rows)
    df_hourly    = pd.DataFrame(all_hourly)
    df_segments  = pd.DataFrame(all_segments)
    df_unmapped  = pd.DataFrame(unmapped)

    if not df_sessions.empty:
        df_sessions = df_sessions.sort_values(["canonical_subject", "start_date"])
        df_sessions["session_day"] = (
            df_sessions.groupby(["canonical_subject", "program_name"]).cumcount() + 1
        )

        day_map = df_sessions[
            ["canonical_subject", "program_name", "start_date", "session_day"]
        ].drop_duplicates(subset=["canonical_subject", "program_name", "start_date"])

        for df in (df_hourly, df_segments):
            if not df.empty:
                merged = df.merge(
                    day_map, on=["canonical_subject", "program_name", "start_date"], how="left"
                )
                df.drop(df.index, inplace=True)
                for col in merged.columns:
                    df[col] = merged[col].values

    if not df_hourly.empty:
        df_hourly = df_hourly.sort_values(["canonical_subject", "start_date", "hour"])
    if not df_segments.empty:
        df_segments = df_segments.sort_values(
            ["canonical_subject", "start_date", "segment_index"]
        )

    return df_sessions, df_hourly, found, df_segments, df_unmapped


def generate_pattern_flags(
    df: pd.DataFrame,
    min_active: int = 5,
    max_inactive_ratio: float = 0.5,
    min_duration_min: int = 30,
    escalation_threshold: int = 30,
) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()

    # Programs that record no lever data (withdrawal, flush) must not be
    # flagged for "low activity" — zero is the correct answer there.
    behavioural = ~df.get("no_behavioural_data", pd.Series(False, index=df.index)).fillna(False)

    df["low_activity_flag"] = (df["active_presses"] < min_active) & behavioural
    df["high_inactive_ratio_flag"] = (
        (df["inactive_presses"] / (df["active_presses"] + 1)) > max_inactive_ratio
    ) & behavioural
    df["short_session_flag"] = df["duration_sec"] < (min_duration_min * 60)
    df["impossible_efficiency_flag"] = (
        df["infusions"] > df["active_presses"]
    ) & behavioural & (df["active_presses"] > 0)

    df = df.sort_values(["canonical_subject", "start_date"])
    df["prev_infusions"] = df.groupby("canonical_subject")["infusions"].shift(1)
    df["escalation_flag"] = (
        (df["infusions"] > df["prev_infusions"] * (1 + escalation_threshold / 100))
        & df["prev_infusions"].notna()
    )
    df["data_quality_flag"] = (
        df["low_activity_flag"].astype(int)
        + df["high_inactive_ratio_flag"].astype(int)
        + df["short_session_flag"].astype(int)
        + df["escalation_flag"].astype(int)
        + df["impossible_efficiency_flag"].astype(int)
    )
    return df


def create_daily_summary(df_sessions: pd.DataFrame) -> pd.DataFrame:
    if df_sessions.empty:
        return pd.DataFrame()

    df = df_sessions.copy()
    if "start_date" in df.columns:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df = df.dropna(subset=["start_date"])

    if "session_day" not in df.columns:
        df["session_day"] = 1

    group_keys = ["canonical_subject", "gender", "program_name", "session_day"]

    possible_agg = {
        "infusions": "sum", "active_presses": "sum", "inactive_presses": "sum",
        "duration_sec": "sum", "pump_time_sec": "sum", "breakpoints": "max",
        "start_date": "min", "end_date": "max", "Box": "first", "Room": "first",
        "overnight_session": "any", "session_span_days": "max",
        "W_value": "sum", "T_value": "sum", "timeout_presses_per_inf": "mean",
        "timeout_active": "sum", "timeout_inactive": "sum",
        "post_session_active": "sum", "post_session_inactive": "sum",
        "estimated_volume_ml": "sum", "estimated_inf_dur_sec": "mean",
        "estimated_intake_mgkg": "sum",
    }
    agg_dict = {c: f for c, f in possible_agg.items() if c in df.columns and c not in group_keys}

    daily  = df.groupby(group_keys, sort=False).agg(agg_dict).reset_index()
    counts = df.groupby(group_keys, sort=False).size().reset_index(name="session_count")
    daily  = daily.merge(counts, on=group_keys, how="left")

    rename_map = {
        "infusions": "total_infusions", "active_presses": "total_active_presses",
        "inactive_presses": "total_inactive_presses", "duration_sec": "total_duration_sec",
        "start_date": "first_session_time", "end_date": "last_session_time",
        "overnight_session": "had_overnight_session", "session_span_days": "max_session_span_days",
        "W_value": "total_W_value", "T_value": "total_T_value",
        "timeout_presses_per_inf": "avg_timeout_presses_per_inf",
        "timeout_active": "total_timeout_active", "timeout_inactive": "total_timeout_inactive",
        "post_session_active": "total_post_session_active",
        "post_session_inactive": "total_post_session_inactive",
        "estimated_volume_ml": "total_estimated_volume_ml",
        "estimated_inf_dur_sec": "avg_estimated_inf_dur_sec",
        "estimated_intake_mgkg": "total_estimated_intake_mgkg",
    }
    daily = daily.rename(columns={k: v for k, v in rename_map.items() if k in daily.columns})
    return daily.sort_values(["canonical_subject", "program_name", "session_day"])


def create_segment_summary(df_segments: pd.DataFrame) -> pd.DataFrame:
    """Mean ± SEM active responses per segment index, per program.

    This is the table the extinction and cue-relapse figures should be built
    from — one point per test session rather than one point per 24 h record.
    """
    if df_segments is None or df_segments.empty:
        return pd.DataFrame()
    g = (df_segments
         .groupby(["program_name", "segment_type", "segment_index", "segment_label"])
         .agg(n_subjects=("canonical_subject", "nunique"),
              n_records=("canonical_subject", "size"),
              active_mean=("active_responses", "mean"),
              active_sem=("active_responses", "sem"),
              inactive_mean=("inactive_responses", "mean"),
              cue_mean=("cue_deliveries", "mean"))
         .reset_index())
    return g.sort_values(["program_name", "segment_type", "segment_index"])


def add_non_zero_inf_days(df_sessions: pd.DataFrame) -> pd.DataFrame:
    cols = ["canonical_subject", "program_name", "non_zero_inf_days", "total_non_zero_days"]
    if df_sessions.empty or "start_date" not in df_sessions.columns:
        return pd.DataFrame(columns=cols)
    df = df_sessions.copy()
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df = df.dropna(subset=["start_date"])
    df["date"]      = df["start_date"].dt.date
    df["infusions"] = pd.to_numeric(df["infusions"], errors="coerce").fillna(0)

    daily_inf = (df.groupby(["canonical_subject", "program_name", "date"])["infusions"]
                   .sum().reset_index())
    per_program = (daily_inf[daily_inf["infusions"] > 0]
                   .groupby(["canonical_subject", "program_name"]).size()
                   .reset_index(name="non_zero_inf_days"))
    total_days = (daily_inf[daily_inf["infusions"] > 0]
                  .groupby("canonical_subject")["date"].nunique()
                  .reset_index(name="total_non_zero_days"))
    return per_program.merge(total_days, on="canonical_subject", how="left").fillna(
        {"total_non_zero_days": 0}
    )


def report_missing_and_box_room(expected_ids: Set[str], found_set: Set[str], df: pd.DataFrame):
    missing = sorted(expected_ids - found_set)
    if missing:
        st.warning(f"**{len(missing)} expected subject(s) NOT found:**")
        st.write(", ".join(missing) or "(none)")
    elif expected_ids:
        st.success("All expected subjects were found in the data.")

    if "Box" not in df.columns and "Room" not in df.columns:
        return

    st.subheader("Box / Room Distribution")
    summary = (df.groupby(["canonical_subject", "Box", "Room", "program_name"])
                 .size().reset_index(name="session_count"))
    non_zero_df = add_non_zero_inf_days(df)
    summary = summary.merge(non_zero_df, on=["canonical_subject", "program_name"], how="left").fillna(
        {"non_zero_inf_days": 0, "total_non_zero_days": 0})
    summary = summary.sort_values(
        ["total_non_zero_days", "non_zero_inf_days", "session_count"], ascending=False)
    st.dataframe(
        summary.style
        .format({"non_zero_inf_days":   lambda x: f"{int(x)}" if x > 0 else "-",
                 "total_non_zero_days": lambda x: f"{int(x)}" if x > 0 else "-",
                 "session_count":       "{:.0f}"})
        .highlight_max(subset=["session_count"],       color="#d4edda")
        .highlight_max(subset=["non_zero_inf_days"],   color="#fff3cd")
        .highlight_max(subset=["total_non_zero_days"], color="#d4edda")
    )
    st.caption(
        f"Showing {len(summary)} rows • "
        f"Total unique animals: {summary['canonical_subject'].nunique()} • "
        f"Total non-zero infusion days: {summary['total_non_zero_days'].sum():.0f}"
    )
