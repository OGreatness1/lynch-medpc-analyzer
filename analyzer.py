import pandas as pd
from typing import List, Tuple, Optional, Set, Dict, Any
import re
import streamlit as st
from config import DEFAULT_MSN_PATTERNS, DEFAULT_VARIABLE_MAPPINGS
from parser import ParsedSession
from utils import canonicalize_id, extract_gender, normalize_msn

PUMP_RATE_ML_SEC = 0.0172  # (ml/sec)

AVG_INF_DUR_COCAINE = 4.0
AVG_INF_DUR_FENTANYL = 1.5
AVG_INF_DUR_NICOTINE = 1.0

COCAINE_1_5MGKG_DUR = {100: 1.3, 200: 2.5, 300: 3.8, 400: 5.0, 500: 6.2, 600: 7.5, 700: 8.8, 800: 10.0}
COCAINE_0_5MGKG_DUR = {100: 0.4, 200: 0.8, 300: 1.2, 400: 1.7, 500: 2.1, 600: 2.5, 700: 2.9, 800: 3.3}
COCAINE_0_3MGKG_DUR = {100: 0.3, 200: 0.5, 300: 0.8, 400: 1.0, 500: 1.3, 600: 1.5, 700: 1.8, 800: 2.1}
NICOTINE_DUR = {100: 0.6, 200: 1.3, 300: 1.9, 400: 2.5, 500: 3.1, 600: 3.7, 700: 4.3, 800: 4.9}
FENTANYL_DUR = {100: 0.5, 200: 0.5, 300: 0.7, 400: 0.8, 500: 1.0, 600: 1.2, 700: 1.4, 800: 1.6}

DEFAULT_WEIGHT_G = 300.0

def robust_parse_date(date_str: str) -> pd.Timestamp:
    if not date_str or pd.isna(date_str): return pd.NaT
    for fmt in ["%m/%d/%y", "%m/%d/%Y", "%m-%d-%y", "%m-%d-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%Y/%m/%d"]:
        try: return pd.to_datetime(date_str, format=fmt, errors='raise')
        except: continue
    return pd.NaT

def get_val(session: ParsedSession, var_name: Any, default: Any = 0.0) -> float:
    if not var_name: return float(default)
    if isinstance(var_name, list):
        if len(var_name) > 0: var_name = var_name[0]
        else: return float(default)
            
    var_str = str(var_name)
    match = re.match(r"([A-Z])\((\d+)\)", var_str)
    if match:
        arr_key, idx = match.group(1), int(match.group(2))
        if arr_key in session.arrays and len(session.arrays[arr_key]) > idx:
            return float(session.arrays[arr_key][idx])
        return float(default)

    try: return float(session.scalars.get(var_str, default))
    except (ValueError, TypeError): return float(default)

def calculate_duration(session: ParsedSession, mapping: dict) -> float:
    if "duration_sec" in mapping: return get_val(session, mapping["duration_sec"])
    if "duration_min" in mapping: return get_val(session, mapping["duration_min"]) * 60
    if "duration_hour" in mapping: return get_val(session, mapping["duration_hour"]) * 3600
    return 0.0

def process_sessions(
    sessions: List[ParsedSession], allowed_ids: Optional[Set[str]] = None,
    custom_patterns: Optional[Dict] = None, custom_mappings: Optional[Dict] = None,
    avg_weight_g: float = DEFAULT_WEIGHT_G, drug_type: str = "None", conc_mgml: float = 1.0 
) -> Tuple[pd.DataFrame, pd.DataFrame, Set[str]]:
    
    patterns = custom_patterns or DEFAULT_MSN_PATTERNS
    mappings = custom_mappings or DEFAULT_VARIABLE_MAPPINGS
    all_rows, all_hourly, found = [], [], set()

    for sess in sessions:
        subj_raw = sess.meta.get("Subject", "")
        canon = canonicalize_id(subj_raw)
        if not canon or (allowed_ids and canon not in allowed_ids): continue
        found.add(canon)
        gender, raw_msn = extract_gender(canon), sess.meta.get("MSN", "")
        norm_msn, prog, mapping = normalize_msn(raw_msn), "UNMAPPED", mappings.get("RAT - FR20", {}) 

        for name, pats in patterns.items():
            if any(pat in norm_msn for pat in pats):
                prog, mapping = name, mappings.get(name, mapping)
                break
                            
        start_dt, end_dt = robust_parse_date(sess.meta.get("Start Date", "")), robust_parse_date(sess.meta.get("End Date", ""))
        duration_sec = calculate_duration(sess, mapping)

        inf_dur_sec = FENTANYL_DUR.get(int(avg_weight_g), AVG_INF_DUR_FENTANYL) if drug_type == "Fentanyl" or "FENTANYL" in prog.upper() else \
                      NICOTINE_DUR.get(int(avg_weight_g), AVG_INF_DUR_NICOTINE) if drug_type == "Nicotine" or "NICOTINE" in prog.upper() else \
                      COCAINE_1_5MGKG_DUR.get(int(avg_weight_g), AVG_INF_DUR_COCAINE)

        row = {
            "canonical_subject": canon, "gender": gender, "program_name": prog, "raw_msn": raw_msn,
            "start_date": start_dt, "end_date": end_dt,
            "session_span_days": (end_dt - start_dt).days + 1 if pd.notna(end_dt) and pd.notna(start_dt) else 1,
            "overnight_session": pd.notna(end_dt) and pd.notna(start_dt) and (end_dt > start_dt),
            "duration_sec": duration_sec,
            "active_presses": get_val(sess, mapping.get("active_presses", "I")),
            "inactive_presses": get_val(sess, mapping.get("inactive_presses", "J")),
            "infusions": get_val(sess, mapping.get("infusions", "K")),
            "pump_time_sec": get_val(sess, mapping.get("pump_time", "Y")) * get_val(sess, mapping.get("infusions", "K")),
            "breakpoints": get_val(sess, mapping.get("breakpoints", "B")),
            "W_value": get_val(sess, mapping.get("W_value", "W")),
            "timeout_presses_per_inf": get_val(sess, mapping.get("W_value", "W")) / (get_val(sess, mapping.get("infusions", "K")) + 1e-6),
            "estimated_volume_ml": get_val(sess, mapping.get("infusions", "K")) * PUMP_RATE_ML_SEC,
            "estimated_inf_dur_sec": inf_dur_sec,
            "estimated_intake_mgkg": (get_val(sess, mapping.get("infusions", "K")) * conc_mgml * PUMP_RATE_ML_SEC / (avg_weight_g / 1000)) if conc_mgml > 0 else 0.0,
            "Box": sess.meta.get("Box", ""), "Room": sess.meta.get("Room", "") or sess.meta.get("Experiment", ""),
        }

        if mapping.get("special_processing") == "MOUSE_ADVANCED":
            b_array = sess.arrays.get("B", [])
            row["timeout_active"]        = b_array[6] if len(b_array) > 6 else 0
            row["timeout_inactive"]      = b_array[7] if len(b_array) > 7 else 0
            row["active_timestamps"]     = sess.arrays.get(mapping.get("active_timestamps", "L"), [])
            row["inactive_timestamps"]   = sess.arrays.get(mapping.get("inactive_timestamps", "R"), [])
        else:
            row["timeout_active"] = row["timeout_inactive"] = 0
            row["active_timestamps"] = row["inactive_timestamps"] = []

        all_rows.append(row)

        # ─── V3 FIX: HOURLY ARRAY CAPPING (Prevents active_events > infusions) ───
        inf_ts_key = mapping.get("infusion_timestamps", "I")
        act_ts_key = mapping.get("active_timestamps", "R")

        if inf_ts_key in sess.arrays or act_ts_key in sess.arrays:
            ts_inf_raw = sess.arrays.get(inf_ts_key, []) if inf_ts_key else []
            ts_act_raw = sess.arrays.get(act_ts_key, []) if act_ts_key else []
            
            infusion_count = get_val(sess, mapping.get("infusions", "K"))
            ts_inf = ts_inf_raw[:int(infusion_count)] if len(ts_inf_raw) >= int(infusion_count) else ts_inf_raw
            
            # Key V3 Fix: If both map to 'O' (like in intermittent access), cap active to infusion count
            if act_ts_key == inf_ts_key:
                ts_act = ts_act_raw[:int(infusion_count)]
            else:
                ts_act = ts_act_raw
            
            if duration_sec > 0:
                max_h = int(duration_sec // 3600) + 1
                for h in range(max_h + 1):
                    all_hourly.append({
                        "canonical_subject": canon, "gender": gender, "program_name": prog,
                        "start_date": start_dt, "hour": h,
                        "infusion_events": sum(1 for t in ts_inf if int(t // 3600) == h),
                        "active_events": sum(1 for t in ts_act if int(t // 3600) == h),
                        "Box": row["Box"], "Room": row["Room"]
                    })

    df_sessions = pd.DataFrame(all_rows)
    df_hourly   = pd.DataFrame(all_hourly)

    if not df_sessions.empty:
        df_sessions = df_sessions.sort_values(["canonical_subject", "start_date"])
        df_sessions['session_day'] = df_sessions.groupby(['canonical_subject', 'program_name']).cumcount() + 1
    if not df_hourly.empty:
        df_hourly = df_hourly.sort_values(["canonical_subject", "start_date", "hour"])

    return df_sessions, df_hourly, found

def generate_pattern_flags(df: pd.DataFrame, min_active: int = 5, max_inactive_ratio: float = 0.5, min_duration_min: int = 30, escalation_threshold: int = 30) -> pd.DataFrame:
    if df.empty: return df
    df = df.copy()
    df["low_activity_flag"] = df["active_presses"] < min_active
    df["high_inactive_ratio_flag"] = (df["inactive_presses"] / (df["active_presses"] + 1)) > max_inactive_ratio
    df["short_session_flag"] = df["duration_sec"] < (min_duration_min * 60)
    df = df.sort_values(["canonical_subject", "start_date"])
    df["prev_infusions"] = df.groupby("canonical_subject")["infusions"].shift(1)
    df["escalation_flag"] = ((df["infusions"] > df["prev_infusions"] * (1 + escalation_threshold / 100)) & df["prev_infusions"].notna())
    df["data_quality_flag"] = df["low_activity_flag"].astype(int) + df["high_inactive_ratio_flag"].astype(int) + df["short_session_flag"].astype(int) + df["escalation_flag"].astype(int)
    return df

def create_daily_summary(df_sessions: pd.DataFrame) -> pd.DataFrame:
    if df_sessions.empty: return pd.DataFrame()
    df = df_sessions.copy()
    if 'start_date' in df.columns:
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
        df = df.dropna(subset=['start_date'])
        
    if "session_day" not in df.columns: df["session_day"] = 1

    group_keys = ["canonical_subject", "gender", "session_day"]
    possible_agg = {
        "infusions": "sum", "active_presses": "sum", "inactive_presses": "sum", "duration_sec": "sum", "breakpoints": "max",
        "program_name": lambda x: ", ".join(x.unique()), "start_date": "min", "end_date": "max", "Box": "first", "Room": "first",
        "session_span_days": "max", "W_value": "sum", "timeout_presses_per_inf": "mean", "timeout_active": "sum", "timeout_inactive": "sum",
        "estimated_volume_ml": "sum", "estimated_inf_dur_sec": "mean", "estimated_intake_mgkg": "sum",
    }
    agg_dict = {col: func for col, func in possible_agg.items() if col in df.columns}
    daily = df.groupby(group_keys).agg(agg_dict).reset_index()
    rename_map = {
        "infusions": "total_infusions", "active_presses": "total_active_presses", "inactive_presses": "total_inactive_presses",
        "duration_sec": "total_duration_sec", "start_date": "first_session_time", "end_date": "last_session_time",
        "W_value": "total_W_value", "timeout_presses_per_inf": "avg_timeout_presses_per_inf", "timeout_active": "total_timeout_active",
        "estimated_volume_ml": "total_estimated_volume_ml", "estimated_inf_dur_sec": "avg_estimated_inf_dur_sec", "estimated_intake_mgkg": "total_estimated_intake_mgkg",
    }
    daily = daily.rename(columns={k: v for k, v in rename_map.items() if k in daily.columns})
    daily["session_count"] = df.groupby(group_keys).size().values
    return daily.sort_values(["canonical_subject", "session_day"])

def add_non_zero_inf_days(df_sessions: pd.DataFrame) -> pd.DataFrame:
    if df_sessions.empty: return pd.DataFrame(columns=['canonical_subject', 'program_name', 'non_zero_inf_days', 'total_non_zero_days'])
    df = df_sessions.copy()
    if 'start_date' not in df.columns: return pd.DataFrame(columns=['canonical_subject', 'program_name', 'non_zero_inf_days', 'total_non_zero_days'])
    df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
    df = df.dropna(subset=['start_date'])
    df['date'] = df['start_date'].dt.date
    df['infusions'] = pd.to_numeric(df['infusions'], errors='coerce').fillna(0)
    daily_inf = df.groupby(['canonical_subject', 'program_name', 'date'])['infusions'].sum().reset_index()
    per_program = daily_inf[daily_inf['infusions'] > 0].groupby(['canonical_subject', 'program_name']).size().reset_index(name='non_zero_inf_days')
    total_days = daily_inf[daily_inf['infusions'] > 0].groupby('canonical_subject')['date'].nunique().reset_index(name='total_non_zero_days')
    result = per_program.merge(total_days, on='canonical_subject', how='left').fillna({"total_non_zero_days": 0})
    return result

def report_missing_and_box_room(expected_list: Set[str], found_set: Set[str], df: pd.DataFrame):
    missing = sorted(expected_list - found_set) if expected_list else []
    if missing: st.warning(f"**{len(missing)} expected subject(s) NOT found:**\n" + ", ".join(missing))
    elif expected_list: st.success("All expected subjects were found in the data.")

    if "Box" not in df.columns and "Room" not in df.columns: return
    st.subheader("Box / Room Distribution")
    summary = df.groupby(["canonical_subject", "Box", "Room", "program_name"]).size().reset_index(name="session_count")
    summary = summary.merge(add_non_zero_inf_days(df), on=["canonical_subject", "program_name"], how="left").fillna({"non_zero_inf_days": 0, "total_non_zero_days": 0})
    summary = summary.sort_values(["total_non_zero_days", "non_zero_inf_days", "session_count"], ascending=False)
    st.dataframe(summary.style.format({"non_zero_inf_days": lambda x: f"{int(x)}" if x > 0 else "-", "total_non_zero_days": lambda x: f"{int(x)}" if x > 0 else "-", "session_count": "{:.0f}"}).highlight_max(subset=["session_count"], color="#d4edda"))
