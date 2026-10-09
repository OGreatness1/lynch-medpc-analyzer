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

CONFIG_VERSION = "7.3"

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
    # Extinction (9 sessions) with a terminal cue-reinstatement test.
    # Verified against all 31 nine-session .MPC variants in the project folder
    # (EXTINCT MUST EXT BY 9 FOR REINST / FOR REINSTATE G136A|G140A|G140B,
    # B BOXES, Z TEST, EXTINCT-REINSTATE G138A|G140A, g136B EXTINCT-REINSTATE):
    #   S.S.9-17:  #R^LLEVER: IF Q = n -> ADD A/D/F/G/H/I/J/K/L   (n = 1..9)
    #   S.S.18:    #Z7: SET U = (A+D+F+G+H+I+J+K+L)
    #   S.S.8:     #R^RLEVER: ADD P
    #   S.S.25:    #R1: Z6; ADD N      (cue DELIVERIES - not counted during the
    #                                   5 s cue/pump window, so N <= M)
    #   S.S.26:    #R1: ADD M          (every reinstatement active press)
    #   S.S.28:    #R3: ADD O          (reinstatement inactive presses)
    "infusions":          "N",     # cue deliveries during the reinstatement test
    "active_presses":     "U",     # total active extinction responses
    "inactive_presses":   "P",
    "duration":           "Z",
    "special_processing": "EXTINCTION_DETAIL",
    # S.S.8 ("#R^RLEVER: ADD P") is never gated on E, so it keeps counting
    # through the reinstatement test while S.S.28 counts the same presses into
    # O.  P is therefore inactive presses for the WHOLE run, not for extinction
    # alone, and extinction-only inactive = P - O.  analyzer.py derives that as
    # `inactive_presses_extinction_only`.
    "inactive_includes_reinstatement": True,
    # These programs have no DISKVARS line, so MedPC writes EVERY letter A-Z
    # to every record: sessions that never ran (J/K/L for an animal that
    # stopped after session 6) and M/N/O for an animal that never reached the
    # cue phase are all present, as 0.  Presence therefore says nothing.
    #   Q = sessions started (S.S.5 SET Q = 1; S.S.6 ADD Q each 65-min cycle
    #       while E = 1).  On the 127 G126 2017/2018 records no animal has a
    #       press in any session numbered > Q.
    #   E = 1 during extinction; S.S.19-22 "SET E = 0" (the only assignments
    #       in all 10 nine-session variants) start the cue phase.  E stays 1
    #       when S.S.23 ends the run at session 9 without reinstatement.
    # E = 0 with M = N = O = 0 is a genuine zero-response reinstatement test
    # (9 of 54 animals in G126 2018) and must be kept, not dropped.
    "session_count_var":        "Q",
    "reinstatement_flag_var":   "E",
    "reinstatement_flag_value": 0,
    "extinction_session_vars":  ["A", "D", "F", "G", "H", "I", "J", "K", "L"],
    "reinstatement_active":     "M",
    "reinstatement_inactive":   "O",
    "reinstatement_cues":       "N",
    "W_value":            "U",
    "T_value":            "Q",
}

map_rat_ext_2017 = {
    # EXTINCTION G140 ABOXES 2017 - TEN extinction sessions, NO reinstatement.
    # Verified against EXTINCTION G140 ABOXES 2017.MPC (also in MPC/ and
    # OTHER PROGRAMS/; all three copies are byte-identical):
    #   S.S.9-18:  #R^LLEVER: IF Q = n -> ADD A/D/F/G/H/I/J/K/L/M  (n = 1..10)
    #   S.S.19:    #Z7: SET U = (A+D+F+G+H+I+J+K+L+M)
    #   header:    "\M: SESSION 10 ACTIVE RESPONSES"
    # The file contains no Z8/Z9, no cue delivery and no "ADD N" / "ADD O"
    # anywhere, so there is no reinstatement phase.  M MUST NOT be read as
    # reinstatement responding here - that is what map_rat_ext does, and
    # routing this program through map_rat_ext both invents a reinstatement
    # test out of session-10 extinction presses and drops session 10 from the
    # per-session breakdown, so the nine reported sessions no longer sum to U.
    "infusions":          None,
    "active_presses":     "U",
    "inactive_presses":   "P",
    "duration":           "Z",
    "special_processing": "EXTINCTION_DETAIL",
    "extinction_session_vars": ["A", "D", "F", "G", "H", "I", "J", "K", "L", "M"],
    "session_count_var":  "Q",
    # No reinstatement_* keys: this program has no reinstatement phase.
    #
    # "Extinction G126 2017" is routed here too.  Its .MPC is not in the
    # project folder, but all 73 records in G126/1-16/2017 have M = N = O = 0
    # (no cue phase at all), the cue test ran the next day as the separate
    # program "REINSTATEMENT G126 2017", and the naming matches the verified
    # G140 pair.  No G126 record ran past session 8, so M (session 10) is never
    # reported for them - the Q bound drops it.
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
    # S.S.9 reads "1": ADD C(0), C(T) ... IF C(T) >= 3600".  T is never SET in
    # these programs, so T = 0 and "ADD C(0), C(T)" increments C(0) TWICE per
    # second - the header comment "\120 = 1 MIN" says so explicitly.  The
    # threshold 3600 is therefore 1800 real seconds = 30 min, which is what the
    # .MPC headers have always said ("\A: 0-30 ACTIVE RESPONSES", "Z3: RESETS
    # 30 MIN TIMER", "Z7: MARKS ENDS OF EACH 30 MIN SEGMENT").  The same
    # doubling makes B(S) >= 50400 a 7 h hold, matching "7HR PRETX HOLD" in the
    # program name, and V(S) >= 14400 a 2 h relapse window = 4 x 30 min.
    # Confirmed empirically on the 42 G138A CUE RELAPSE records in
    # "MedPC Processing File/New folder": median Start->End = 9.08 h
    # (7 h hold + 2 h relapse), Q ends at 4, and A+D+F+G == R in 42/42.
    # v7.0-7.2 set this to 3600 and labelled the bins "0-60 min" ... "180-240
    # min", overstating the time base by 2x.
    "segment_seconds":    1800,
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
    # FLUSH ESD (all three variants): S.S.9 "SET F=0; ON ^PUMP; ADD Y" - Y is
    # the number of flushes; S.S.8 "SET K = T*1"" - T is the pump time per
    # flush in seconds ("\K: PUMP TIME IN SECONDS").  There is no I in this
    # program, so v7.2's pump_time = "I" always read 0.
    "infusions":  None,
    "pump_time":  None,
    "pump_count": "Y",
    "pump_time_each": "T",
    "duration":   "Z",
    "W_value":    "W",
    "T_value":    "T",
}

map_rat_int_dt2017 = {
    # MSN exactly "INTERMITTENT" (INTERMITTENT.mpc, May 2017): a discrete-
    # trial program on a 30-min intermittent schedule (X = 1800).  Same
    # variable layout as DT4FINAL, NOT as NEW INTERMITTENT ACCESS:
    #   #R1 (lever extended): "OFF ^RETRACT; SET L(P)=0; ADD I"  -> infusions
    #   #R3: "ADD R; SHOW 5, RLEVER, R"                           -> INACTIVE
    # Routed through map_rat_int, R was reported as active presses (real
    # record C538F: I = 38 infusions, R = 16).
    **map_rat_dt,
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

    # A pattern starting with "=" must equal the whole normalised MSN.  Every
    # intermittent MSN contains "intermittent", so this one needs it.
    "RAT - INTERMITTENT (2017 DISCRETE-TRIAL)": ["=intermittent"],

    # Recognised but deliberately NOT analysed (no variable mapping), so they
    # land in the Unrecognised-MSN report with this name as the reason rather
    # than being read through a mapping that does not fit:
    #   SECOND ORDER FR20 - a second-order schedule; no .MPC in the project;
    #       every record in the backup is a test box.  Must sit above
    #       "RAT - FR20" because its MSN contains "fr20".
    #   PR 2 LEVER (22 HOUR) - no .MPC in the project and not the PRCOCAINE
    #       layout: R covers the PR schedule in only 50 of 136 records and
    #       len(C) / len(W) almost never equal R / I.
    #   V6 TO 10 Ext PLUS CUE - several revisions under one MSN with
    #       different meanings of M and N (see CHANGES_v7.3.md).
    "UNSUPPORTED - SECOND ORDER FR20 (no .MPC source)": ["secondorder", "fr20secondorder"],
    "UNSUPPORTED - PR 2 LEVER (no .MPC source)":        ["pr2lever"],
    "UNSUPPORTED - V6 TO 10 EXT PLUS CUE (mixed revisions)": ["v6to10extpluscue"],

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
    # FR23hr (BOX11A_FR23hr, Box 15B FR23hr, FR23hr.MPC): identical variable
    # layout to FR20 (I at Z7, R / A lever counters, C / W time arrays, 7-slot
    # J), infusion cap 400 instead of 20.  On the 7 real 2017 records
    # len(W) == I, len(C) == R and the J columns reconcile, 7/7.
    "RAT - FR23HR":              ["fr23hr"],
    "RAT - FR20 FOOD RESTRICT":  ["fr20foodrestrictesd", "fr20foodrestrict"],
    "RAT - FR20":                ["fr20esd", "g136afr20", "fr20"],
    "RAT - FR40":                ["fr40", "g136afr40"],

    "RAT - PR COCAINE":  ["prcocaineesd", "prcocaine", "g136aprcocaine"],
    "RAT - PR FENTANYL": ["prfentesd", "prfent", "g136aprfent"],
    "RAT - PR FOOD":     ["prfood"],

    # The 2017 ten-session variant must be matched BEFORE "RAT - EXTINCTION":
    # its MSN contains "extinction", and the nine-session mapping misreads its
    # M (session 10 actives) as reinstatement responding.  See map_rat_ext_2017.
    "RAT - EXTINCTION ONLY (2017, NO REINSTATEMENT)": [
        "extinctiong140aboxes2017", "extinctiong140aboxes",
        "extinctiong140boxes2017", "extinctiong1262017",
    ],

    "RAT - EXTINCTION": [
        "ztestextinctmustextby9forreinstesd",
        "extinctmustextby9forreinsteg140aboxesesd",
        "extinctmustextby9forreinsteg136aboxesesd",
        "bboxesextinctmustextby9forreinstesdesd",
        "extinctmustextby9", "extinctreinstate", "extinct", "extinction",
        "g136aextinct", "g140aextinct",
        # REMOVED in 7.3:
        #   "g136aprocaine" - a typo for PRCOCAINE, which is a different
        #     program (map_rat_pr).  Any MSN that really did read "G136A
        #     PROCAINE" was being reported as extinction.
        #   "g136aboxes"    - matched the room/box label rather than the
        #     protocol, so ANY G136A-boxes program whose MSN happened to carry
        #     that string was classified as extinction.
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
    "RAT - FR23HR":                         map_rat_fr,
    "RAT - INTERMITTENT (2017 DISCRETE-TRIAL)": map_rat_int_dt2017,
    "RAT - FR20 FOOD RESTRICT":             map_rat_fr,
    "RAT - FR40":                           map_rat_fr,
    "RAT - PR COCAINE":                     map_rat_pr,
    "RAT - PR FENTANYL":                    map_rat_pr,
    "RAT - PR FOOD":                        map_rat_pr,
    "RAT - EXTINCTION":                     map_rat_ext,
    "RAT - EXTINCTION ONLY (2017, NO REINSTATEMENT)": map_rat_ext_2017,
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
