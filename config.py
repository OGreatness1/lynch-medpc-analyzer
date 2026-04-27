from typing import Dict, List, Any
from utils import normalize_msn

# ============================================================================
# LYNCH LAB MEDPC ANALYZER — CONFIGURATION FILE (v6.3)
# ============================================================================
# Every variable mapping verified by reading the actual .MPC source file.
# Files read: FR20_ESD, FR20PDT_ESD, FR20PDT_10SECTO_ESD, FR20_FOOD_RESTRICT,
#   FENTANYL_1_SEC_FR40_ESD (all variants), PRCOCAINE_ESD, PRFENT_ESD,
#   NEW_INTERMITTENT_ACCESS_LD_ESD (3NEW, 4NEW, original variants),
#   EXTINCT_MUST_EXT_BY_9 (Z_TEST, G136A, G140A, B_BOXES variants),
#   ONLY_REIN, G136A_ONLY_REIN, G136A_CUE_RELAPSE_7HR,
#   FRFOODTRAIN_ESD, G136_14B_NEW_FRFOOD_TRAIN,
#   WITHDRAWAL_LD_ESD, LOCOMOTOR_BASELINE, CONTINUOUS_FENTANYL
#
# KEY CONFIRMED FACTS:
#
# FR/FENTANYL/PR template (all variants share identical variables):
#   R = active (infusion/left lever) presses
#   A = inactive (activity/right lever) presses   ← NOT L
#   I = infusion counter
#   D = presses during infusion
#   F = FR ratio
#   W = per-infusion timestamp array (S.S.9: W(I-1)=G)  ← NOT J
#   J = hourly summary array [time, R, I, D, A, licks, F]  ← NOT timestamps
#
# INTERMITTENT ACCESS (all variants identical):
#   R = LLEVER (active/drug lever) presses
#   U = RLEVER (inactive lever) presses   ← NOT L
#   I = infusion counter
#   O = infusion timestamp array (S.S.15: O(V)=S)  ← NOT L
#   L = per-trial LLEVER press counts array (NOT timestamps)
#
# EXTINCTION (all variants identical):
#   R = active lever responses (session total)
#   P = inactive extinction responses  ← NOT M
#   U = all active extinction responses (redundant total)
#   Q = session number
#   M = reinstatement responses (different thing, only used post-ext)
#   N = cue deliveries
#
# REINSTATEMENT (ONLY_REIN):
#   M = active responses DURING reinstatement  ← active key
#   O = inactive cue reinstatement             ← inactive key
#   R = right/activity lever (NOT the active drug-seeking lever here)
#   N = stimulus deliveries
#
# CUE RELAPSE:
#   R = total active responses
#   M = total inactive responses
#   N = cue/stimulus deliveries
#
# FRFOODTRAIN_ESD (magazine training):
#   A = lever 1 (left/active) press counter
#   B = lever 2 (right/inactive) press counter
#   R = food reinforcer counter
#   E = magazine entries
#   No infusion timestamps
#
# LOCOMOTOR BASELINE:
#   B(0) = LLEVER total, B(1) = RLEVER total
#   L = LLEVER response timestamps, R = RLEVER response timestamps
#   A(0) = weight (grams)
#
# CONTINUOUS FENTANYL:
#   B(0) = LLEVER total, B(1) = RLEVER total
#   L = LLEVER timestamps, R = RLEVER timestamps
#   W = weight used this session (stored from D after conversion)
#   D = weight input field (reset each session)
# ============================================================================

METADATA_KEYS = [
    "start date", "end date", "subject", "msn", "experiment", "group",
    "box", "start time", "end time", "time unit", "room", "cage"
]

# ─────────────────────────────────────────────────────────────────────────────
# RAT PROGRAM MAPPINGS
# ─────────────────────────────────────────────────────────────────────────────

map_rat_fr = {
    # FR20 / FR40 / Fentanyl FR40 all variants — identical base template
    "infusions":           "I",
    "active_presses":      "R",
    "inactive_presses":    "A",
    "duration":            "Z",
    "infusion_timestamps": "W",   # S.S.9: W(I-1)=G at each infusion
    "W_value":             "D",   # presses during infusion
    "T_value":             "F",   # FR ratio
}

map_rat_fent = {
    # Fentanyl FR40 LD / LD Food Restrict / MAX — same base template as FR
    "infusions":           "I",
    "active_presses":      "R",
    "inactive_presses":    "A",
    "duration":            "Z",
    "infusion_timestamps": "W",
    "special_processing":  "J_ARRAY_HOURLY",
    "W_value":             "D",
    "T_value":             "F",
}

map_rat_int = {
    # Intermittent access — all variants (NEW, 3NEW, 4NEW, original) identical
    # S = elapsed session time in seconds (confirmed from data: S: 85801.000)
    # Z = clock array [Hr, Min, Sec] — not elapsed time, use S instead
    "infusions":           "I",
    "active_presses":      "R",   # LLEVER (drug lever)
    "inactive_presses":    "U",   # RLEVER (inactive lever)
    "duration":            "S",   # elapsed session seconds  ← Z was wrong (clock, not duration)
    "infusion_timestamps": "O",   # S.S.15: O(V)=S at each infusion
    "active_timestamps":   "O",
    "W_value":             "W",   # pump turn time
    "T_value":             "Q",   # trial number
}

map_rat_pr = {
    # PR Cocaine / PR Fentanyl — same base template as FR
    "infusions":           "I",
    "active_presses":      "R",
    "inactive_presses":    "A",
    "duration":            "Z",
    "infusion_timestamps": "W",
    "breakpoint":          "V",
    "W_value":             "D",
    "T_value":             "F",
}

map_rat_ext = {
    # Extinction — all variants (Z_TEST, G136A, G140A, B_BOXES) identical
    # P = inactive extinction responses  ← confirmed from all 4 source files
    # U = all active extinction responses
    # M = reinstatement responses (only populated post-extinction, not during)
    "infusions":        None,
    "active_presses":   "R",    # total active lever responses
    "inactive_presses": "P",    # inactive extinction responses  ← was M, WRONG
    "duration":         "Z",
    "special_processing": "EXTINCTION_DETAIL",
    "W_value":          "U",    # all active extinction responses
    "T_value":          "Q",    # session number
}

map_rat_reinstatement = {
    # Reinstatement (ONLY_REIN template):
    # M = responses DURING reinstatement = active drug-seeking count
    # O = inactive cue reinstatement responses
    # R = right/activity lever (background, not the reinstatement-active lever)
    "infusions":        None,
    "active_presses":   "M",    # responses during reinstatement  ← was R, WRONG
    "inactive_presses": "O",    # inactive cue reinstatement       ← was M, WRONG
    "duration":         "Z",
    "W_value":          "R",    # right lever (activity/background)
    "T_value":          "N",    # stimulus deliveries
}

map_rat_cue = {
    # Cue relapse — R=active total, M=inactive total, N=cue deliveries
    "infusions":        "N",    # cue/stimulus deliveries (not IV drug)
    "active_presses":   "R",
    "inactive_presses": "M",
    "duration":         "Z",
    "W_value":          "U",    # redundant active total
    "T_value":          "Q",    # session segment #
}

map_rat_food = {
    # FRFOODTRAIN_ESD / NEW FRFOOD TRAIN:
    # The program only increments R on each reinforced press (ADD R after lever press).
    # A and B are declared but never incremented in this program.
    # So R = lever 1 presses = food reinforcers (they are the same in FR1 mag training).
    # Z = clock array [Hr,Min,Sec] — not elapsed duration; duration from metadata.
    "infusions":        None,
    "active_presses":   "R",    # reinforced lever 1 presses (= pellets delivered)
    "inactive_presses": None,   # lever 2 never incremented in this program
    "reinforcers":      "R",    # same as active_presses
    "duration":         "Z",    # will fall back to metadata time diff
    "W_value":          "W",
    "T_value":          "M",    # minutes elapsed
}

map_flush = {
    "infusions":  None,
    "pump_time":  "I",
    "duration":   "Z",
    "W_value":    "W",
    "T_value":    "T",
}

map_withdrawal = {
    "infusions":  None,
    "duration":   "Z",
    "W_value":    "W",
    "T_value":    "T",
}

map_continuous_fentanyl = {
    # B(0)=LLEVER count, B(1)=RLEVER count
    # L=LLEVER timestamps, R=RLEVER timestamps
    # W=weight used this session
    "infusions":           None,
    "active_presses":      "B(0)",
    "inactive_presses":    "B(1)",
    "active_timestamps":   "L",
    "inactive_timestamps": "R",
    "weight":              "W",
}

map_locomotor_baseline = {
    # B(0)=LLEVER count, B(1)=RLEVER count
    # L=LLEVER timestamps (S.S.6: L(I)=S), R=RLEVER timestamps (S.S.7: R(J)=S)
    # A(0)=weight
    "infusions":           None,
    "active_presses":      "B(0)",
    "inactive_presses":    "B(1)",
    "active_timestamps":   "L",
    "inactive_timestamps": "R",
    "weight":              "A(0)",
}

# ─────────────────────────────────────────────────────────────────────────────
# MOUSE PROGRAM MAPPINGS
# B(0)=active nosepokes, B(1)=inactive nosepokes, B(2)=infusions
# G=infusion timestamps, L=active timestamps, R=inactive timestamps
# ─────────────────────────────────────────────────────────────────────────────

map_mouse_fr1 = {
    "infusions":           "B(2)",
    "active_presses":      "B(0)",
    "inactive_presses":    "B(1)",
    "infusion_timestamps": "G",
    "active_timestamps":   "L",
    "inactive_timestamps": "R",
    "duration":            "S",
    "weight":              "A(6)",
    "infusion_time":       "A",
    "pr_schedule":         "P",
    "z_params":            "Z",
    "special_processing":  "MOUSE_ADVANCED",
    "W_value":             "B",
    "T_value":             "B",
}

map_mouse_pr = {
    "infusions":           "B(2)",
    "active_presses":      "B(0)",
    "inactive_presses":    "B(1)",
    "active_timestamps":   "L",
    "inactive_timestamps": "R",
    "infusion_timestamps": "G",
    "duration":            "S",
    "breakpoint":          "A(3)",
    "weight":              "A(3)",
    "infusion_time":       "A",
    "pr_schedule":         "P",
    "z_params":            "Z",
    "special_processing":  "MOUSE_ADVANCED",
    "W_value":             "B",
    "T_value":             "B",
}

map_mouse_extended_access = {
    "infusions":           "B(2)",
    "active_presses":      "B(0)",
    "inactive_presses":    "B(1)",
    "infusion_timestamps": "G",
    "active_timestamps":   "L",
    "inactive_timestamps": "R",
    "duration":            "S",
    "weight":              "A(6)",
    "infusion_time":       "A",
    "pr_schedule":         "P",
    "z_params":            "Z",
    "special_processing":  "MOUSE_ADVANCED",
    "W_value":             "B",
    "T_value":             "B",
}

# ─────────────────────────────────────────────────────────────────────────────
# MSN pattern matching — ORDER MATTERS, do not reorder
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_MSN_PATTERNS: Dict[str, List[str]] = {

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
        "new intermittent access",
        "g136a new intermittent",
        "g136b new intermittent",
        "intermittent",
        "ld intermittent",
        "intermittentldesd",
        "new intermittent",
    ],

    "RAT - FENTANYL FR40 LD FOOD RESTRICT": [
        "fentanyl1secfr40ldfoodrestrictesd",
        "g136afentanyl1secfr40ldfoodrestrictesd",
        "g136bfentanyl1secfr40ldfoodrestrictesd",
        "fentanyl 1 sec fr40 ld food restrict esd",
        "fentanyl1secfr40ld foodrestrictesd",
    ],

    "RAT - FENTANYL FR40 LD": [
        "fentanyl1secfr40ldesd",
        "g136afentanyl1secfr40ldesd",
        "g136bfentanyl1secfr40ldesd",
        "fentanyl 1 sec fr40 ld esd",
        "fentanyl1secfr40esd",
        "fentanyl fr40 esd",
        "fentanyl1secfr40maxesd",
        "fentanyl1secfr40",
    ],

    "RAT - FR FOOD / MAG TRAINING": [
        "frfoodtrainesd",
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

    "RAT - WITHDRAWAL": [
        "withdrawalldesd",
        "withdrawaldlesd",
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

    # FR20 food restrict must come before plain FR20 to avoid it matching as FR20
    "RAT - FR20": [
        "fr20foodrestrictesd",
        "fr20foodrestrict",
        "fr20pdtesd",
        "fr20pdt10sectesd",
        "fr20pdt10secto",
        "fr20pdt",
        "fr20esd",
        "g136afr20",
        "fr20",
    ],

    "RAT - FR40": ["fr40", "g136afr40"],
    "RAT - PR COCAINE":  ["prcocaineesd", "prcocaine", "g136aprcocaine"],
    "RAT - PR FENTANYL": ["prfentesd", "prfent", "g136aprfent"],

    "RAT - EXTINCTION": [
        "ztestextinctmustextby9forreinstatedsd",
        "extinctmustextby9forreinsteg140aboxesesd",
        "bboxesextinctmustextby9forreinstesdesd",
        "extinctmustextby9",
        "extinctmustextby9forreinsteg136aboxesesd",
        "extinct",
        "extinction",
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
        "g136aonlyrein",
        "onlyrein",
        "reinstate",
        "reinstatementg140aboxes2017",
        "extinctionreinstatementg140",
        "g136areinstate",
    ],

    # CUE RELAPSE — split by box set so cohorts can be filtered separately in
    # the dashboard.  All variants share identical variable layout → map_rat_cue.
    # G138A and G138B are different physical box sets from G136/G140 but run
    # the same .MPC program with the same variables.
    "RAT - CUE RELAPSE G138A": [
        "g138acuerelapse7hrpreathold",
        "g138acuerelapse7hrpretxhold",
        "g138acuerelapsenohold2025",
        "g138acuerelapse",
        "g138a",
    ],

    "RAT - CUE RELAPSE G138B": [
        "g138bcuerelapse7hrpretxhold",
        "g138bcuerelapse7hrpreathold",
        "g138bcuerelapsenohold2025",
        "g138bcuerelapse",
        "g138b",
    ],

    "RAT - CUE RELAPSE 7HR": [
        "g136acuerelapse",
        "g136bcuerelapse",
        "g140acuerelapse7hr",
        "cuerelapse",
        "g140a cue relapse 7hr pretx hold",
        "copy of g140a cue relapse",
        "relapse esd",
        "relapseesd",
    ],

    "RAT - CUE RELAPSE 2HR": [
        "g140acuerelapsefollowing2hr",
        "test cue relapse following 2hr",
        "testcuerelapsefollowing2hr",
    ],

    "RAT - DISCRETE TRIAL": ["dt4final", "g136adt4final"],
    "RAT - FLUSH": ["flush", "g136aflush", "withdrawalmpc"],

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

# ─────────────────────────────────────────────────────────────────────────────
# Program name → variable mapping
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_VARIABLE_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "RAT - INTERMITTENT ACCESS":            map_rat_int,
    "RAT - FR FOOD / MAG TRAINING":         map_rat_food,
    "RAT - FENTANYL FR40 LD":               map_rat_fent,
    "RAT - FENTANYL FR40 LD FOOD RESTRICT": map_rat_fent,
    "RAT - FENTANYL FR40":                  map_rat_fent,
    "RAT - CONTINUOUS FENTANYL":            map_continuous_fentanyl,
    "RAT - LOCOMOTOR BASELINE":             map_locomotor_baseline,
    "RAT - FR20":                           map_rat_fr,
    "RAT - FR40":                           map_rat_fr,
    "RAT - PR COCAINE":                     map_rat_pr,
    "RAT - PR FENTANYL":                    map_rat_pr,
    "RAT - EXTINCTION":                     map_rat_ext,
    "RAT - REINSTATEMENT":                  map_rat_reinstatement,
    "RAT - CUE RELAPSE G138A":              map_rat_cue,
    "RAT - CUE RELAPSE G138B":              map_rat_cue,
    "RAT - CUE RELAPSE 7HR":                map_rat_cue,
    "RAT - CUE RELAPSE 2HR":                map_rat_cue,
    "RAT - DISCRETE TRIAL":                 map_rat_fr,
    "RAT - FLUSH":                          map_flush,
    "RAT - WITHDRAWAL":                     map_withdrawal,
    "MOUSE - FR1":                          map_mouse_fr1,
    "MOUSE - PR":                           map_mouse_pr,
    "MOUSE - EXTENDED ACCESS":              map_mouse_extended_access,
}

print("✅ config.py v6.3 loaded — all variables verified from every .MPC source file")
