from typing import Dict, List, Any
from utils import normalize_msn

# ============================================================================
# LYNCH LAB MEDPC ANALYZER — CONFIGURATION FILE (v7.0)
# ============================================================================
# Changes from v6.3, each verified against the .MPC source and against the
# raw records in "MedPC Processing File/New folder" (1,712 sessions):
#
# 1. DT4FINAL ESD no longer falls into "RAT - FR FOOD / MAG TRAINING".
#    v6.3 listed the bare pattern "dt4" under FR FOOD, which sits above
#    "RAT - DISCRETE TRIAL" in the dict, so all 24 DT4FINAL sessions matched
#    FR FOOD and reported 0 infusions / 3 active presses instead of
#    I infusions / R inactive presses.  "dt4" removed from the FR FOOD list.
#
# 2. RAT - FR FOOD infusions = "R".  v6.3 had infusions=None and put the
#    pellet count only in a "reinforcers" key that analyzer.py never reads,
#    so all 174 FRFOOD sessions reported 0 infusions.  DT4 ESD source:
#        #R^LLEVER: ON ^PELLET; ADD R
#    R is both the reinforcer count and the active-press count under FR1.
#    (The "\R: RIGHT LEVER/ACTIVITY LEVER RESPONSES" comment in the .MPC is
#    stale — the code contradicts it.)
#
# 3. RAT - EXTINCTION active_presses = "U", not "R".
#    EXTINCT MUST EXT BY 9 FOR REINST ESD never increments R during
#    extinction; per-session actives are A,D,F,G,H,I,J,K,L (sessions 1-9) and
#    U is their total.  Verified on the Aug-2026 records: 46+24+4+18 = 92 = U,
#    while R = 0.  v6.3 reported active_presses = 0 for every extinction
#    session.
#
# 4. PR breakpoint = the F ratio array indexed at the last completed infusion,
#    not the scalar "V".  V is the fountain-valve time (default 0.05 s), so
#    v6.3 wrote breakpoints = 0.05 for every PR session and the breakpoint
#    plot drew a flat line at 0.05 instead of reporting "no data".
#    PRFENT ESD source: F = PR schedule array, H = its index, and
#        S.S.9: W(I-1) = G   → W = per-infusion timestamps
#
# 5. FR-family active-press timestamps = "C".  C is the response-time array
#    (len(C) == R, verified on 573/573 well-formed FR/PR records); W is the
#    infusion-time array (len(W) == I).  v6.3 declared no active_timestamps
#    for the FR family, so every hourly row had active_events = 0.
#
# 6. FR20 variants split.  v6.3 pooled plain FR20, FR20 FOOD RESTRICT and
#    FR20PDT (punished discrete trial, 10 s timeout) into one program.
#
# 7. Segment definitions added so multi-session records can be expanded into
#    one row per test session instead of being collapsed to a single total:
#
#    CUE RELAPSE — verified in G136A/G136B/G140A/G140B CUE RELAPSE:
#        S.S.9:  1": ADD C(0), C(T); IF C(T) >= 3600 → Z3; Z7
#                .1": ADD Q            ← Q is the segment counter
#        S.S.10-13: #R1: IF Q = n → ADD A / D / F / G
#        S.S.14-17: #R3: IF Q = n → ADD H / I / J / K
#        Total relapse window V(S) >= 14400 (4 h).
#    The segment timer is 3600 s, so A/D/F/G are 0-60, 60-120, 120-180 and
#    180-240 min.  The "\A: 0-30 ACTIVE RESPONSES" comments in the .MPC are
#    stale — every production variant uses 3600, only the bench TEST variant
#    uses 30 s.  Labelling these as 30-minute bins misreports the time base.
#
#    EXTINCTION — EXTINCT MUST EXT BY 9 FOR REINST ESD:
#        A,D,F,G,H,I,J,K,L = active responses in extinction sessions 1-9
#        P = inactive during extinction, U = total active
#        M = responses during reinstatement, N = cue deliveries, O = inactive
#
# 8. Duration keys unchanged ("S" for intermittent access, "Z" ignored
#    elsewhere) but analyzer.py now uses Start/End DATE as well as time, so
#    multi-day withdrawal holds are no longer truncated to under 24 h.
#
# UNCHANGED AND STILL UNVERIFIED: every MOUSE mapping.  There are no mouse
# .MPC files in the project folder, so those entries are inherited from v6.3
# on trust.  Confirm them before publishing mouse data.
# ============================================================================

METADATA_KEYS = [
    "start date", "end date", "subject", "msn", "experiment", "group",
    "box", "start time", "end time", "time unit", "room", "cage"
]

# ─────────────────────────────────────────────────────────────────────────────
# RAT PROGRAM MAPPINGS
# ─────────────────────────────────────────────────────────────────────────────

map_rat_fr = {
    # FR20 / FR40 base template (Vince Hunt boilerplate)
    "infusions":           "I",
    "active_presses":      "R",
    "inactive_presses":    "A",
    "duration":            "Z",     # Z is a clock array → analyzer falls back to metadata
    "infusion_timestamps": "W",     # S.S.9: W(I-1)=G
    "active_timestamps":   "C",     # response-time array, len(C) == R
    "special_processing":  "J_ARRAY_HOURLY",
    "j_array":             "J",
    "W_value":             "D",
    "T_value":             "F",
}

map_rat_fent = {
    "infusions":           "I",
    "active_presses":      "R",
    "inactive_presses":    "A",
    "duration":            "Z",
    "infusion_timestamps": "W",
    "active_timestamps":   "C",
    "special_processing":  "J_ARRAY_HOURLY",
    "j_array":             "J",
    "j_layout":            ["hour", "active", "infusions", "in_infusion", "inactive", "licks", "ratio"],
    "W_value":             "D",
    "T_value":             "F",
}

map_rat_int = {
    # Intermittent access — R = LLEVER (drug lever), U = RLEVER (inactive)
    # S = elapsed session seconds; Z is the end-of-session clock, not a duration
    "infusions":           "I",
    "active_presses":      "R",
    "inactive_presses":    "U",
    "duration":            "S",
    "infusion_timestamps": "O",     # S.S.15: O(V)=S
    # NOTE: O holds infusion times only.  There is no LLEVER-press time array in
    # this program, so active_timestamps is deliberately left unset — hourly
    # active_events would otherwise be a copy of infusion_events and understate
    # LLEVER responding (136,102 presses vs 100,856 infusions in this dataset).
    "W_value":             "W",
    "T_value":             "Q",
}

map_rat_pr = {
    "infusions":           "I",
    "active_presses":      "R",
    "inactive_presses":    "A",
    "duration":            "Z",
    "infusion_timestamps": "W",
    "active_timestamps":   "C",
    "breakpoint":          "F",
    "breakpoint_mode":     "RATIO_ARRAY_AT_LAST_INFUSION",
    # NOTE: no J_ARRAY_HOURLY here.  The PR programs write J with a different
    # stride than the FR family (J(Q+7) is a sentinel) and the column sums do
    # not reconcile with the R/I/A scalars on any stride from 6 to 9.  Hourly
    # data for PR is therefore built from C (active-press times) and W
    # (infusion times), both of which do reconcile: len(C)==R and len(W)==I.
    "W_value":             "D",
    "T_value":             "F",
}

map_rat_ext = {
    # Extinction with terminal reinstatement test
    "infusions":          "N",     # cue deliveries during the reinstatement test
    "active_presses":     "U",     # total active extinction responses
    "inactive_presses":   "P",
    "duration":           "Z",
    "special_processing": "EXTINCTION_DETAIL",
    "extinction_session_vars":  ["A", "D", "F", "G", "H", "I", "J", "K", "L"],
    "reinstatement_active":     "M",
    "reinstatement_inactive":   "O",
    "reinstatement_cues":       "N",
    "W_value":            "U",
    "T_value":            "Q",
}

map_rat_reinstatement = {
    # ONLY_REIN template — reinstatement test run on its own
    "infusions":          "N",
    "active_presses":     "M",
    "inactive_presses":   "O",
    "duration":           "Z",
    "special_processing": "REINSTATEMENT_DETAIL",
    "reinstatement_active":   "M",
    "reinstatement_inactive": "O",
    "reinstatement_cues":     "N",
    "W_value":            "R",
    "T_value":            "N",
}

map_rat_cue = {
    "infusions":          "N",     # cue/stimulus deliveries, not IV drug
    "active_presses":     "R",
    "inactive_presses":   "M",
    "duration":           "Z",
    "special_processing": "CUE_RELAPSE_SEGMENTS",
    "segment_seconds":    3600,    # S.S.9: IF C(T) >= 3600
    "active_segment_vars":   ["A", "D", "F", "G"],
    "inactive_segment_vars": ["H", "I", "J", "K"],
    "segment_counter":    "Q",
    "W_value":            "U",
    "T_value":            "Q",
}

map_rat_food = {
    # NEW FRFOOD TRAIN / FRFOODTRAIN ESD  (DT4 family, FR1 magazine training)
    #   #R^LLEVER: ON ^PELLET; ADD R   → R is both pellets and active presses
    "infusions":        "R",
    "active_presses":   "R",
    "inactive_presses": None,
    "reinforcers":      "R",
    "duration":         "Z",
    "W_value":          "W",
    "T_value":          "M",
}

map_rat_dt = {
    # DT4FINAL ESD — discrete-trial self-administration
    #   S.S: @T: ... ADD I; SHOW 4, INF, I     → I = infusions
    #        #R3: ADD R                        → R = right/activity lever
    "infusions":        "I",
    "active_presses":   "I",     # one reinforced LLEVER press per delivered trial
    "inactive_presses": "R",
    "duration":         "Z",
    "W_value":          "W",
    "T_value":          "Q",     # trial number
}

map_flush = {
    "infusions":  None,
    "pump_time":  "I",
    "duration":   "Z",
    "W_value":    "W",
    "T_value":    "T",
}

map_withdrawal = {
    # No levers are wired in this program; all behavioural columns are
    # legitimately zero.  M counts elapsed minutes.
    "infusions":        None,
    "active_presses":   None,
    "inactive_presses": None,
    "duration":         "Z",
    "no_behavioural_data": True,
    "W_value":    "W",
    "T_value":    "M",
}

map_continuous_fentanyl = {
    "infusions":           None,
    "active_presses":      "B(0)",
    "inactive_presses":    "B(1)",
    "active_timestamps":   "L",
    "inactive_timestamps": "R",
    "weight":              "W",
}

map_locomotor_baseline = {
    "infusions":           None,
    "active_presses":      "B(0)",
    "inactive_presses":    "B(1)",
    "active_timestamps":   "L",
    "inactive_timestamps": "R",
    "weight":              "A(0)",
}

# ─────────────────────────────────────────────────────────────────────────────
# MOUSE PROGRAM MAPPINGS  — INHERITED FROM v6.3, NOT VERIFIED
# No mouse .MPC files exist in the project folder.  Confirm before publishing.
# ─────────────────────────────────────────────────────────────────────────────

map_mouse_fr1 = {
    "infusions": "B(2)", "active_presses": "B(0)", "inactive_presses": "B(1)",
    "infusion_timestamps": "G", "active_timestamps": "L", "inactive_timestamps": "R",
    "duration": "S", "weight": "A(6)", "infusion_time": "A", "pr_schedule": "P",
    "z_params": "Z", "special_processing": "MOUSE_ADVANCED",
    "W_value": "B", "T_value": "B", "unverified": True,
}

map_mouse_pr = {
    "infusions": "B(2)", "active_presses": "B(0)", "inactive_presses": "B(1)",
    "active_timestamps": "L", "inactive_timestamps": "R", "infusion_timestamps": "G",
    "duration": "S", "breakpoint": "A(3)", "weight": "A(3)", "infusion_time": "A",
    "pr_schedule": "P", "z_params": "Z", "special_processing": "MOUSE_ADVANCED",
    "W_value": "B", "T_value": "B", "unverified": True,
}

map_mouse_extended_access = {
    "infusions": "B(2)", "active_presses": "B(0)", "inactive_presses": "B(1)",
    "infusion_timestamps": "G", "active_timestamps": "L", "inactive_timestamps": "R",
    "duration": "S", "weight": "A(6)", "infusion_time": "A", "pr_schedule": "P",
    "z_params": "Z", "special_processing": "MOUSE_ADVANCED",
    "W_value": "B", "T_value": "B", "unverified": True,
}

# ─────────────────────────────────────────────────────────────────────────────
# MSN pattern matching — ORDER MATTERS.
# analyzer.py takes the FIRST key with a matching pattern, so a program whose
# name contains another program's name must be listed above it.
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_MSN_PATTERNS: Dict[str, List[str]] = {

    "RAT - INTERMITTENT ACCESS": [
        "newintermittentaccessldfoodrestrictesd",
        "newintermittentaccessldesd", "intermittentaccessldesd",
        "2025newintermittentaccess", "3newintermittentaccess", "4newintermittentaccess",
        "g136anewintermittentaccess", "g136bnewintermittentaccess",
        "shortinta", "intermittentaccess", "intaccess", "intermittentld",
        "accessldesd", "intermittentldesd", "intermittent",
    ],

    "RAT - FENTANYL FR40 LD FOOD RESTRICT": [
        "fentanyl1secfr40ldfoodrestrictesd",
        "g136afentanyl1secfr40ldfoodrestrictesd",
        "g136bfentanyl1secfr40ldfoodrestrictesd",
    ],

    "RAT - FENTANYL FR40 LD": [
        "fentanyl1secfr40ldesd", "g136afentanyl1secfr40ldesd",
        "g136bfentanyl1secfr40ldesd", "fentanyl1secfr40esd",
        "fentanyl1secfr40maxesd", "fentanylfr40esd", "fentanyl1secfr40",
    ],

    # DT4FINAL must be matched BEFORE the FR FOOD list — both are DT4-family
    # programs but DT4FINAL is drug self-administration, not food training.
    "RAT - DISCRETE TRIAL (DT4)": ["dt4final", "g136adt4final", "dt4"],

    "RAT - FR FOOD / MAG TRAINING": [
        "frfoodtrainesd", "2025newfrfoodtrain", "frfoodtrain", "newfrfoodtrain",
        "g136anewfrfoodtrain", "g136bnewfrfoodtrain", "g13614bnewfrfoodtrain",
        "frfood",
    ],

    "RAT - WITHDRAWAL": [
        "withdrawalldesd", "withdrawaldlesd", "g136awithdrawalldesd",
        "g136bwithdrawalldesd", "g136awithdrawal", "g136bwithdrawal",
        "withdrawalld", "withdrawal",
    ],

    "RAT - CONTINUOUS FENTANYL": ["continuousfentanyl"],
    "RAT - LOCOMOTOR BASELINE":  ["locomotorbaseline"],

    # FR20 variants kept as separate programs — PDT is a punished discrete-trial
    # schedule and must not be pooled with plain FR20.
    "RAT - FR20 PDT":            ["fr20pdt10secto", "fr20pdt10sectesd", "fr20pdtesd", "fr20pdt"],
    "RAT - FR20 FOOD RESTRICT":  ["fr20foodrestrictesd", "fr20foodrestrict"],
    "RAT - FR20":                ["fr20esd", "g136afr20", "fr20"],
    "RAT - FR40":                ["fr40", "g136afr40"],

    "RAT - PR COCAINE":  ["prcocaineesd", "prcocaine", "g136aprcocaine"],
    "RAT - PR FENTANYL": ["prfentesd", "prfent", "g136aprfent"],
    "RAT - PR FOOD":     ["prfood"],

    "RAT - EXTINCTION": [
        "ztestextinctmustextby9forreinstatedsd",
        "extinctmustextby9forreinsteg140aboxesesd",
        "extinctmustextby9forreinsteg136aboxesesd",
        "bboxesextinctmustextby9forreinstesdesd",
        "extinctmustextby9", "extinctreinstate", "extinct", "extinction",
        "g136aextinct", "g140aextinct", "g136aprocaine", "g136aboxes",
    ],

    "RAT - REINSTATEMENT": [
        "g136aonlyrein", "onlyrein", "reinstatementg140aboxes2017",
        "g136areinstate", "reinstate",
    ],

    "RAT - CUE RELAPSE G138A": [
        "g138acuerelapse7hrpreathold", "g138acuerelapse7hrpretxhold",
        "g138acuerelapsenohold2025", "g138acuerelapse", "g138a",
    ],
    "RAT - CUE RELAPSE G138B": [
        "g138bcuerelapse7hrpretxhold", "g138bcuerelapse7hrpreathold",
        "g138bcuerelapsenohold2025", "g138bcuerelapse", "g138b",
    ],
    "RAT - CUE RELAPSE 2HR": [
        "g140acuerelapsefollowing2hr", "g140bcuerelapsefollowing2hr",
        "testcuerelapsefollowing2hr", "cuerelapsefollowing2hr",
    ],
    "RAT - CUE RELAPSE 7HR": [
        "g136acuerelapse", "g136bcuerelapse", "g140acuerelapse7hr",
        "g140bcuerelapse7hr", "copyofg140acuerelapse", "cuerelapse", "relapseesd",
    ],

    "RAT - FLUSH": ["flushesd", "g136aflush", "flush"],

    "MOUSE - EXTENDED ACCESS": [
        "mouseextendedaccessv2", "mouseextendedaccess", "mouseextended",
        "mouseintera", "mouseintermittentaccess",
    ],
    "MOUSE - FR1": ["mousefr1", "fr1mouse"],
    "MOUSE - PR":  ["mousepr", "prmouse"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Program name → variable mapping
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_VARIABLE_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "RAT - INTERMITTENT ACCESS":            map_rat_int,
    "RAT - FR FOOD / MAG TRAINING":         map_rat_food,
    "RAT - DISCRETE TRIAL (DT4)":           map_rat_dt,
    "RAT - FENTANYL FR40 LD":               map_rat_fent,
    "RAT - FENTANYL FR40 LD FOOD RESTRICT": map_rat_fent,
    "RAT - CONTINUOUS FENTANYL":            map_continuous_fentanyl,
    "RAT - LOCOMOTOR BASELINE":             map_locomotor_baseline,
    "RAT - FR20":                           map_rat_fr,
    "RAT - FR20 PDT":                       map_rat_fr,
    "RAT - FR20 FOOD RESTRICT":             map_rat_fr,
    "RAT - FR40":                           map_rat_fr,
    "RAT - PR COCAINE":                     map_rat_pr,
    "RAT - PR FENTANYL":                    map_rat_pr,
    "RAT - PR FOOD":                        map_rat_pr,
    "RAT - EXTINCTION":                     map_rat_ext,
    "RAT - REINSTATEMENT":                  map_rat_reinstatement,
    "RAT - CUE RELAPSE G138A":              map_rat_cue,
    "RAT - CUE RELAPSE G138B":              map_rat_cue,
    "RAT - CUE RELAPSE 7HR":                map_rat_cue,
    "RAT - CUE RELAPSE 2HR":                map_rat_cue,
    "RAT - FLUSH":                          map_flush,
    "RAT - WITHDRAWAL":                     map_withdrawal,
    "MOUSE - FR1":                          map_mouse_fr1,
    "MOUSE - PR":                           map_mouse_pr,
    "MOUSE - EXTENDED ACCESS":              map_mouse_extended_access,
}
