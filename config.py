from typing import Dict, List, Any

# Import single canonical normalize_msn from utils (removes duplicate definition)
from utils import normalize_msn

# ============================================================================
# LYNCH LAB MEDPC ANALYZER - CONFIGURATION FILE (v6.0 - BUGS FIXED)
# ============================================================================
# Changes from v5.9:
#  - normalize_msn removed here; now imported from utils.py (single source)
#  - map_rat_ext / map_rat_cue gain explicit "infusions": None sentinel so
#    analyzer never falls back to reading array K as a scalar count
#  - map_rat_pr uses "breakpoint" (singular) consistently — matches analyzer
#  - Added clarifying comment on map_rat_int L-array dual use
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
    "W_value": "W",          # timeout / non-reinforced presses
    "T_value": "T",          # trial count or total attempts
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
    "W_value": "W",          # timeout presses during infusion delay
    "T_value": "T",          # often total reinforcer attempts
}

map_rat_int = {
    "infusions": "I",
    "active_presses": "R",
    "inactive_presses": "L",
    # NOTE: infusion_timestamps intentionally maps to "L" for intermittent
    # access protocols where lever-press timestamps serve as infusion markers.
    # The hourly binning in analyzer.py uses this key for infusion events,
    # so be aware this will count L-array presses as infusion timestamps.
    "infusion_timestamps": "L",
    "active_timestamps": "P",
    "inactive_timestamps": [],
    "duration": "Z",
    "extra_vars": ["U"],
    "W_value": "W",          # presses during inter-trial interval
    "T_value": "T",          # number of lever extensions / trials
}

map_rat_pr = {
    "infusions": "I",
    "active_presses": "R",
    "inactive_presses": "L",
    "infusion_timestamps": "J",
    "active_timestamps": "K",
    "inactive_timestamps": [],
    "duration": "Z",
    "breakpoint": "V",       # singular — must match analyzer.py mapping.get("breakpoint")
    "W_value": "W",          # timeout presses or side responses
    "T_value": "T",          # total lever presses or attempts
}

map_rat_ext = {
    "infusions": None,       # Extinction has no infusions — explicit None prevents K-array fallback
    "active_presses": "R",
    "inactive_presses": "L",
    "active_timestamps": "J",
    "inactive_timestamps": "K",
    "duration": "Z",
    "special_processing": "EXTINCTION_DETAIL",
    "W_value": "W",          # responses during extinction timeout
    "T_value": "T",          # extinction trials or cue presentations
}

map_rat_cue = {
    "infusions": "N",
    "active_presses": "R",
    "inactive_presses": "L",
    "active_timestamps": "J",
    "inactive_timestamps": [],
    "duration": "Z",
    "W_value": "W",          # cue-induced responses
    "T_value": "T",          # cue presentations or trials
}

map_rat_food = {
    "infusions": None,       # No IV infusions in food training
    "active_presses": "R",
    "inactive_presses": "L",
    "reinforcers": "I",
    "duration": "Z",
    "W_value": "W",          # food magazine entries or side presses
    "T_value": "T",
}

map_flush = {
    "infusions": None,       # No drug infusions during flush
    "pump_time": "I",
    "duration": "Z",
    "W_value": "W",          # any responses during flush
    "T_value": "T",
}

map_withdrawal = {
    "infusions": None,       # No infusions during withdrawal sessions
    "duration": "Z",
    "W_value": "W",          # withdrawal-related responses
    "T_value": "T",
}

map_continuous_fentanyl = {
    "infusions": None,
    "active_presses": "B(0)",
    "inactive_presses": "B(1)",
    "weight": "D"
}

map_locomotor_baseline = {
    "infusions": None,
    "active_presses": "B(0)",      # LLEVER presses
    "inactive_presses": "B(1)",    # RLEVER presses
    "active_timestamps": "L",      # LLEVER Response Array
    "inactive_timestamps": "R",    # RLEVER Response Array
    "weight": "A(0)"               # Weight (grams)
}

# ────────────────────────────────────────────────
# MOUSE PROGRAM MAPPINGS
# ────────────────────────────────────────────────

map_mouse_fr1 = {
    "infusions": "B(2)",
    "active_presses": "B(0)",
    "inactive_presses": "B(1)",
    "infusion_timestamps": "G",
    "active_timestamps": "L",           # All active nosepoke times
    "inactive_timestamps": "R",         # All inactive nosepoke times
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
    "breakpoint": "A",
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
# MSN pattern matching (program name → list of normalized substrings)
# ORDER MATTERS: more specific patterns must come first.
# Do NOT reorder without careful review — intermittent access must remain first.
# ────────────────────────────────────────────────
DEFAULT_MSN_PATTERNS: Dict[str, List[str]] = {
    # === INTERMITTENT ACCESS — FIRST AND VERY SPECIFIC ===
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

    # === FENTANYL FR40 LD FOOD RESTRICT ===
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

    # === WITHDRAWAL (Merged) ===
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
    "RAT - LOCOMOTOR BASELINE": ["locomotorbaseline", "locomotor baseline"],
    "RAT - FR20": ["fr20", "g136afr20", "fr20esd", "fr20pdt"],
    "RAT - FR40": ["fr40", "g136afr40"],
    "RAT - PR COCAINE": ["prcocaine", "prcocaineesd", "g136aprcocaine"],
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
    "MOUSE - FR1": ["mousefr1", "mouse fr1", "fr1mouse"],
    "MOUSE - PR": ["mousepr", "mouse pr", "pr mouse"],
    "MOUSE - EXTENDED ACCESS": [
        "mouseextendedaccess",
        "mouseextended",
        "mouse extended access",
        "mouseextendedaccessv2",
        "mouseintera",
        "mouseintermittentaccess",
    ],
}

# ────────────────────────────────────────────────
# Program name → variable mapping
# ────────────────────────────────────────────────
DEFAULT_VARIABLE_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "RAT - INTERMITTENT ACCESS": map_rat_int,
    "RAT - FR FOOD / MAG TRAINING": map_rat_food,
    "RAT - FENTANYL FR40 LD": map_rat_fent,
    "RAT - FENTANYL FR40 LD FOOD RESTRICT": map_rat_fent,
    "RAT - FENTANYL FR40": map_rat_fent,
    "RAT - CONTINUOUS FENTANYL": map_continuous_fentanyl,
    "RAT - LOCOMOTOR BASELINE": map_locomotor_baseline,
    "RAT - FR20": map_rat_fr,
    "RAT - FR40": map_rat_fr,
    "RAT - PR COCAINE": map_rat_pr,
    "RAT - PR FENTANYL": map_rat_pr,
    "RAT - EXTINCTION": map_rat_ext,
    "RAT - REINSTATEMENT": map_rat_ext,
    "RAT - CUE RELAPSE 7HR": map_rat_cue,
    "RAT - CUE RELAPSE 2HR": map_rat_cue,
    "RAT - DISCRETE TRIAL": map_rat_fr,
    "RAT - FLUSH": map_flush,
    "RAT - WITHDRAWAL": map_withdrawal,
    "MOUSE - FR1": map_mouse_fr1,
    "MOUSE - PR": map_mouse_pr,
    "MOUSE - EXTENDED ACCESS": map_mouse_extended_access,
}

print("✅ config.py v6.0 loaded — normalize_msn unified, breakpoint/infusions sentinels fixed!")
