from typing import Dict, List, Any

# normalize_msn lives in utils.py — import from there to keep a single definition
from utils import normalize_msn

# ============================================================================
# LYNCH LAB MEDPC ANALYZER — CONFIGURATION FILE (v6.1)
# ============================================================================
# Key fixes vs v5.9:
#  - normalize_msn removed here; imported from utils (one definition only)
#  - Mouse mappings restored to correct B-array indexed form:
#      infusions   → "B(2)", active_presses → "B(0)", inactive_presses → "B(1)"
#  - Duplicate dict keys removed (RAT-WITHDRAWAL appeared twice,
#    MOUSE-EXTENDED ACCESS appeared twice — Python silently kept only the last)
#  - map_rat_ext / map_rat_food / map_flush / map_withdrawal gain explicit
#    "infusions": None sentinel so analyzer never falls back to reading array K
#  - map_rat_pr uses "breakpoint" (singular) — matches analyzer lookup key
#  - RAT-CONTINUOUS FENTANYL and RAT-LOCOMOTOR BASELINE mappings restored
#  - ORDER MATTERS: do not reorder DEFAULT_MSN_PATTERNS without review
# ============================================================================

METADATA_KEYS = [
    "start date", "end date", "subject", "msn", "experiment", "group",
    "box", "start time", "end time", "time unit", "room", "cage"
]

# ────────────────────────────────────────────────
# RAT PROGRAM MAPPINGS
# ────────────────────────────────────────────────
map_rat_fr = {
    "infusions": "I",
    "active_presses": "R",
    "inactive_presses": "L",
    "infusion_timestamps": "J",
    "active_timestamps": "K",
    "inactive_timestamps": [],
    "duration": "Z",
    "extra_vars": ["W"],
    "W_value": "W",
    "T_value": "T",
}

map_rat_fent = {
    "infusions": "I",
    "active_presses": "R",
    "inactive_presses": "L",
    "infusion_timestamps": "J",
    "active_timestamps": "K",
    "inactive_timestamps": [],
    "duration": "Z",
    "extra_vars": ["W"],
    "special_processing": "J_ARRAY_HOURLY",
    "W_value": "W",
    "T_value": "T",
}

map_rat_int = {
    "infusions": "I",
    "active_presses": "R",
    "inactive_presses": "L",
    # NOTE: infusion_timestamps intentionally maps to "L" for intermittent
    # access — lever-press timestamps serve as infusion markers in this protocol.
    "infusion_timestamps": "L",
    "active_timestamps": "P",
    "inactive_timestamps": [],
    "duration": "Z",
    "extra_vars": ["U"],
    "W_value": "W",
    "T_value": "T",
}

map_rat_pr = {
    "infusions": "I",
    "active_presses": "R",
    "inactive_presses": "L",
    "infusion_timestamps": "J",
    "active_timestamps": "K",
    "inactive_timestamps": [],
    "duration": "Z",
    "breakpoint": "V",          # singular — analyzer reads mapping.get("breakpoint")
    "W_value": "W",
    "T_value": "T",
}

map_rat_ext = {
    "infusions": None,           # No IV infusions — explicit None prevents K-array fallback
    "active_presses": "R",
    "inactive_presses": "L",
    "active_timestamps": "J",
    "inactive_timestamps": "K",
    "duration": "Z",
    "special_processing": "EXTINCTION_DETAIL",
    "W_value": "W",
    "T_value": "T",
}

map_rat_cue = {
    "infusions": "N",
    "active_presses": "R",
    "inactive_presses": "L",
    "active_timestamps": "J",
    "inactive_timestamps": [],
    "duration": "Z",
    "W_value": "W",
    "T_value": "T",
}

map_rat_food = {
    "infusions": None,           # No IV infusions in food training
    "active_presses": "R",
    "inactive_presses": "L",
    "reinforcers": "I",
    "duration": "Z",
    "W_value": "W",
    "T_value": "T",
}

map_flush = {
    "infusions": None,           # No drug infusions during flush
    "pump_time": "I",
    "duration": "Z",
    "W_value": "W",
    "T_value": "T",
}

map_withdrawal = {
    "infusions": None,           # No infusions during withdrawal
    "duration": "Z",
    "W_value": "W",
    "T_value": "T",
}

map_continuous_fentanyl = {
    "infusions": None,
    "active_presses": "B(0)",
    "inactive_presses": "B(1)",
    "weight": "D",
}

map_locomotor_baseline = {
    "infusions": None,
    "active_presses": "B(0)",
    "inactive_presses": "B(1)",
    "active_timestamps": "L",
    "inactive_timestamps": "R",
    "weight": "A(0)",
}

# ────────────────────────────────────────────────
# MOUSE PROGRAM MAPPINGS
# Mouse data stores counts in the B array:
#   B(0) = active nosepokes, B(1) = inactive nosepokes, B(2) = infusions
# Timestamps are in separate L (active) / R (inactive) / G (infusion) arrays.
# ────────────────────────────────────────────────
map_mouse_fr1 = {
    "infusions": "B(2)",
    "active_presses": "B(0)",
    "inactive_presses": "B(1)",
    "infusion_timestamps": "G",
    "active_timestamps": "L",
    "inactive_timestamps": "R",
    "duration": "S",
    "weight": "A(6)",
    "infusion_time": "A",
    "pr_schedule": "P",
    "z_params": "Z",
    "special_processing": "MOUSE_ADVANCED",
    "W_value": "B",
    "T_value": "B",
}

map_mouse_pr = {
    "infusions": "B(2)",
    "active_presses": "B(0)",
    "inactive_presses": "B(1)",
    "active_timestamps": "L",
    "inactive_timestamps": "R",
    "infusion_timestamps": "G",
    "duration": "S",
    "breakpoint": "A(3)",
    "weight": "A(3)",
    "infusion_time": "A",
    "pr_schedule": "P",
    "z_params": "Z",
    "special_processing": "MOUSE_ADVANCED",
    "W_value": "B",
    "T_value": "B",
}

map_mouse_extended_access = {
    "infusions": "B(2)",
    "active_presses": "B(0)",
    "inactive_presses": "B(1)",
    "infusion_timestamps": "G",
    "active_timestamps": "L",
    "inactive_timestamps": "R",
    "duration": "S",
    "weight": "A(6)",
    "infusion_time": "A",
    "pr_schedule": "P",
    "z_params": "Z",
    "special_processing": "MOUSE_ADVANCED",
    "W_value": "B",
    "T_value": "B",
}

# ────────────────────────────────────────────────
# MSN pattern matching  (program name → list of normalized substrings)
# ORDER MATTERS — more specific patterns must come first.
# Do NOT reorder without careful review.
# ────────────────────────────────────────────────
DEFAULT_MSN_PATTERNS: Dict[str, List[str]] = {

    # === INTERMITTENT ACCESS — first and very specific ===
    "RAT - INTERMITTENT ACCESS": [
        "newintermittentaccessldesd",
        "intermittentaccessldesd",
        "2025newintermittentaccess",
        "3newintermittentaccess",
        "4newintermittentaccess",
        "g136anewintermittentaccess",
        "g136bnewintermittentaccess",
        "shortinta",
        "newintermittentaccessldfoodrestrictesd",
        "intermittentaccess",
        "intaccess",
        "intermittentld",
        "accessldesd",
        "intermittent access ld",
        "new intermittent access",
        "g136a new intermittent",
        "g136b new intermittent",
        "intermittent",
        "ld intermittent",
        "intermittentldesd",
        "new intermittent",
    ],

    # === FENTANYL FR40 LD FOOD RESTRICT — specific before non-food variant ===
    "RAT - FENTANYL FR40 LD FOOD RESTRICT": [
        "fentanyl1secfr40ldfoodrestrictesd",
        "g136afentanyl1secfr40ldfoodrestrictesd",
        "g136bfentanyl1secfr40ldfoodrestrictesd",
        "fentanyl 1 sec fr40 ld food restrict esd",
        "fentanyl1secfr40ld foodrestrictesd",
    ],

    # === FENTANYL FR40 LD (non-food restrict) ===
    "RAT - FENTANYL FR40 LD": [
        "fentanyl1secfr40ldesd",
        "g136afentanyl1secfr40ldesd",
        "g136bfentanyl1secfr40ldesd",
        "fentanyl 1 sec fr40 ld esd",
        "fentanyl1secfr40esd",
        "fentanyl fr40 esd",
    ],

    # === FR FOOD / MAG TRAINING ===
    "RAT - FR FOOD / MAG TRAINING": [
        "2025newfrfoodtrain",
        "frfoodtrain",
        "newfrfoodtrain",
        "g136anewfrfoodtrain",
        "g136bnewfrfoodtrain",
        "g13614bnewfrfoodtrain",
        "frfood",
        "dt4",
        "new frfood train",
    ],

    # === WITHDRAWAL ===
    "RAT - WITHDRAWAL": [
        "withdrawalldesd",
        "g136awithdrawalldesd",
        "g136bwithdrawalldesd",
        "withdrawal ld esd",
        "withdrawal",
        "g136awithdrawal",
        "g136bwithdrawal",
        "withdrawalld",
    ],

    "RAT - CONTINUOUS FENTANYL": ["continuousfentanyl", "continuous fentanyl"],
    "RAT - LOCOMOTOR BASELINE":  ["locomotorbaseline", "locomotor baseline"],
    "RAT - FR20": ["fr20", "g136afr20", "fr20esd", "fr20pdt"],
    "RAT - FR40": ["fr40", "g136afr40"],
    "RAT - PR COCAINE":  ["prcocaine", "prcocaineesd", "g136aprcocaine"],
    "RAT - PR FENTANYL": ["prfent", "g136aprfent", "prfentesd"],

    "RAT - EXTINCTION": [
        "extinct",
        "extinction",
        "extinctmustextby9",
        "g136aextinct",
        "g140aextinct",
        "extinctionreinstatement",
        "2008 v6 to 10 ext plus cue",
        "b boxes extinct must ext by 9",
        "extinct-reinstate",
        "z test extinct",
        "g136aprocaine",
        "g136aboxes",
    ],

    "RAT - REINSTATEMENT": [
        "reinstate",
        "onlyrein",
        "g136aonlyrein",
        "reinstatementg140aboxes2017",
        "extinctionreinstatementg140",
        "g136areinstate",
    ],

    "RAT - CUE RELAPSE 7HR": [
        "g138acuerelapse7hrpreathold",
        "g138a",
        "g136acuerelapse",
        "g140acuerelapse7hr",
        "cuerelapse",
        "g138acuerelapsenohold2025",
        "g140a cue relapse 7hr pretx hold",
        "copy of g140a cue relapse",
        "relapse esd",
    ],

    "RAT - CUE RELAPSE 2HR": [
        "g140acuerelapsefollowing2hr",
        "test cue relapse following 2hr",
        "testcuerelapsefollowing2hr",
        "relapseesd",
    ],

    "RAT - DISCRETE TRIAL": ["dt4final", "g136adt4final"],
    "RAT - FLUSH": ["flush", "g136aflush", "withdrawalmpc"],

    # === MOUSE PROGRAMS ===
    # Extended access listed before FR1/PR to prevent shorter patterns
    # inside those lists from matching extended-access MSN names first.
    "MOUSE - EXTENDED ACCESS": [
        "mouseextendedaccess",
        "mouseextendedaccessv2",
        "mouseextended",
        "mouse extended access",
        "mouseintera",
        "mouseintermittentaccess",
    ],
    "MOUSE - FR1": ["mousefr1", "mouse fr1", "fr1mouse"],
    "MOUSE - PR":  ["mousepr", "mouse pr", "pr mouse"],
}

# ────────────────────────────────────────────────
# Program name → variable mapping
# ────────────────────────────────────────────────
DEFAULT_VARIABLE_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "RAT - INTERMITTENT ACCESS":          map_rat_int,
    "RAT - FR FOOD / MAG TRAINING":       map_rat_food,
    "RAT - FENTANYL FR40 LD":             map_rat_fent,
    "RAT - FENTANYL FR40 LD FOOD RESTRICT": map_rat_fent,
    "RAT - FENTANYL FR40":                map_rat_fent,
    "RAT - CONTINUOUS FENTANYL":          map_continuous_fentanyl,
    "RAT - LOCOMOTOR BASELINE":           map_locomotor_baseline,
    "RAT - FR20":                         map_rat_fr,
    "RAT - FR40":                         map_rat_fr,
    "RAT - PR COCAINE":                   map_rat_pr,
    "RAT - PR FENTANYL":                  map_rat_pr,
    "RAT - EXTINCTION":                   map_rat_ext,
    "RAT - REINSTATEMENT":                map_rat_ext,
    "RAT - CUE RELAPSE 7HR":              map_rat_cue,
    "RAT - CUE RELAPSE 2HR":              map_rat_cue,
    "RAT - DISCRETE TRIAL":               map_rat_fr,
    "RAT - FLUSH":                        map_flush,
    "RAT - WITHDRAWAL":                   map_withdrawal,
    "MOUSE - FR1":                        map_mouse_fr1,
    "MOUSE - PR":                         map_mouse_pr,
    "MOUSE - EXTENDED ACCESS":            map_mouse_extended_access,
}

print("✅ config.py v6.1 loaded — mouse B-array mappings correct, no duplicate keys!")
