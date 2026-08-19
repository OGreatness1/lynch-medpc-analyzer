# lynch-medpc-analyzer — correctness review and v7.0 fixes

Reviewed against the actual MedPC program sources (287 `.MPC` files in
*Personal Projects/MedPC Programs*) and re-run over **1,712 raw session records**
(`MedPC Processing File/New folder`, Aug 2025 – Dec 2025, plus the eight
Aug 2026 files).

Every claim below was verified two ways: by reading the state-machine code in
the `.MPC` that generated the data, and by re-running v6.3 and v7.0 side by side
over the same records.

---

## Summary of what was wrong

| # | Defect | Blast radius in your data |
|---|---|---|
| 1 | `DT4FINAL ESD` misfiled as FR FOOD | 24 sessions, infusions reported as **0** instead of 1,004 |
| 2 | FR FOOD pellet count never reached `infusions` | 174 sessions, **0** instead of 27,718 pellets |
| 3 | Extinction `active_presses` read from `R`, which the program never increments | 4 sessions, **0** instead of 357 |
| 4 | Extinction sessions 1–9 + reinstatement collapsed into one row | 40 test sessions invisible |
| 5 | Cue-relapse hourly segments collapsed into one row | 168 test segments invisible |
| 6 | PR breakpoint read from `V` (fountain-valve time) | every PR session reported breakpoint **0.05** instead of 30 |
| 7 | Duration ignored Start/End **date** | 1,381 multi-day sessions wrapped to < 24 h; a 15-day withdrawal hold reported as 13.8 h |
| 8 | FR/fentanyl/PR hourly `active_events` always 0 | 4,083 hourly rows with a blank active column |
| 9 | Intermittent-access hourly `active_events` was a copy of `infusion_events` | overstated hourly discrimination on 587 sessions |
| 10 | Unrecognised MSNs silently analysed with the FR20 mapping under the label `UNMAPPED` | no wrong rows in *this* dataset, but any new program would produce meaningless numbers with no warning |

---

## The fixes, with the evidence

### 1. `DT4FINAL ESD` was being analysed as food training

`config.py` v6.3 put the bare pattern `"dt4"` in the **`RAT - FR FOOD / MAG
TRAINING`** list, which sits above `RAT - DISCRETE TRIAL` in `DEFAULT_MSN_PATTERNS`.
`resolve_program` takes the first match, so all 24 `DT4FINAL ESD` sessions
matched FR FOOD and were read with `map_rat_food` — which has `infusions: None`.

They are different programs. `DT4FINAL ESD.MPC`:

```
@T: Z7; OFF ^RETRACT; SET L(P)=0; ADD I; SHOW 4, INF, I     ← I = infusions
#R3: ADD R; SHOW 5, RLEVER, R                               ← R = activity lever
```

**v6.3:** 24 sessions → 0 infusions, 1,150 "active presses".
**v7.0:** 24 sessions → 1,004 infusions, 1,004 active, 1,150 **inactive**.

`"dt4"` removed from the FR FOOD list; `RAT - DISCRETE TRIAL (DT4)` moved above
FR FOOD and given its own mapping.

### 2. FR FOOD reported zero reinforcers

v6.3 set `map_rat_food["infusions"] = None` and put the pellet count in a
`"reinforcers"` key — which `analyzer.py` never reads. So every FRFOOD session
reported 0 infusions.

`NEW FRFOOD TRAIN.MPC` (DT4 family, FR1 magazine training):

```
#R^LLEVER: ON ^PELLET; ADD R; SHOW 4, REINF, R
```

`R` is incremented on the lever press *and* delivers the pellet, so under FR1 it
is simultaneously the reinforcer count and the active-press count. (The
`\R: RIGHT LEVER/ACTIVITY LEVER RESPONSES` comment in the header is stale — the
code contradicts it. `I` is declared but never incremented in this program.)

**v6.3:** 174 sessions → 0 infusions.
**v7.0:** 174 sessions → 27,718 pellets.

### 3–4. Extinction: wrong active variable, and every session collapsed

`EXTINCT MUST EXT BY 9 FOR REINST ESD.MPC` runs up to nine ~2 h extinction
sessions in one 24 h record, gated on the session counter `Q`:

```
S.S.: 1": ADD C(0), C(T); IF C(T) >= X       ← X = 7800 s between session starts
      @T: ADD Q; SHOW 3, SESSION#, Q
#R^LLEVER: IF Q = 1 → ADD A; SHOW 5, HR 1, A
#R^LLEVER: IF Q = 2 → ADD D; SHOW 5, HR 2, D
...  Q = 9 → ADD L
#R^RLEVER: ADD P                              ← inactive during extinction
#R1: Z6; ADD N   /   #R1: ADD M   /   #R3: ADD O    ← reinstatement test
```

Two problems:

* v6.3 mapped `active_presses` to **`R`**, which this program never increments.
  On the Aug-2026 records `R = 0` while `U = 92` and `A+F+G+H = 46+24+4+18 = 92`.
  So every extinction session reported **0 active presses**.
* Even with the right total, one row per 24 h record throws away the extinction
  curve — the whole point of the design.

v7.0 maps `active_presses → U` and adds `build_segments()`, which emits one row
per extinction session plus one for the reinstatement test:

```
C1301M  extinction session 1   active=0
C1301M  extinction session 2   active=14
C1301M  extinction session 3   active=0
C1301M  extinction session 4   active=18
C1301M  extinction session 5   active=4
C1301M  extinction session 6-9 active=0
C1301M  reinstatement test     active=9   inactive=2   cues=4
```

### 5. Cue relapse: four hourly segments collapsed into one, and mislabelled

The per-segment counters were never extracted at all. v7.0 emits them — and
note the time base, because the `.MPC` comments are wrong about it:

```
S.S.9:   1": ADD C(0), C(T); SHOW 2, TRIAL=, C(T); IF C(T) >= 3600 → Z3; Z7
         .1": ADD Q; SHOW 3, SESSION#, Q
S.S.10:  #R1: IF Q = 1 → ADD A          S.S.14: #R3: IF Q = 1 → ADD H
S.S.11:  #R1: IF Q = 2 → ADD D          S.S.15: #R3: IF Q = 2 → ADD I
S.S.12:  #R1: IF Q = 3 → ADD F          S.S.16: #R3: IF Q = 3 → ADD J
S.S.13:  #R1: IF Q = 4 → ADD G          S.S.17: #R3: IF Q = 4 → ADD K
         IF V(S) >= 14400                ← 4 h total relapse window
```

The segment timer is **3600 s**, so A/D/F/G are **0–60, 60–120, 120–180 and
180–240 min** — not the "0-30 / 30-60 / 60-90 / 90-120" the header comments
claim. Every production variant (G136A, G136B, G140A, G140B, and the `Copy of`
duplicates) uses 3600; only `TEST CUE RELAPSE FOLLOWING 2HR PRETX HOLD.MPC` uses
30 s, and that is a bench-test file. Reporting these as 30-minute bins halves
the stated time base.

Across your 42 cue-relapse records the recovered within-session time course is:

| segment | active (mean ± SEM) | inactive |
|---|---|---|
| 0–60 min | 89.6 ± 15.4 | 0.86 |
| 60–120 min | 38.1 ± 7.6 | 0.64 |
| 120–180 min | 20.9 ± 5.8 | 0.40 |
| 180–240 min | 19.7 ± 8.4 | 0.64 |

168 rows that did not exist before.

### 6. PR breakpoint was the fountain-valve time

`map_rat_pr["breakpoint"] = "V"`. In `PRFENT ESD.MPC` / `PRCOCAINE ESD.MPC`:

```
\  -V  =  Fountain Valve Time set by User.  Default = .05 sec.
\   F  =  Array that holds the PR schedual
\   H  =  Index used by the F array
   .1": IF Z(3) >= F(H) ...
   SHOW 1,INFLEV,R,3,ACTVTY,A,2,INFS,I,5,PR,F(H),...
```

So the breakpoint is `F[I-1]` — the last ratio completed. v6.3 wrote **0.05**
into `breakpoints` for every PR session, and because `create_pr_breakpoint_plot`
only skips when the column sums to exactly zero, it drew a flat line at 0.05
rather than reporting "no PR data".

**v6.3:** breakpoint = 0.05. **v7.0:** breakpoint = 30.

Verified on the same records: `len(W) == I` and `len(C) == R` on 573/573
well-formed FR/PR records, confirming W = infusion times and C = press times.

### 7. Multi-day sessions were wrapped to under 24 hours

`calculate_duration` fell back to `End Time − Start Time` and added 86,400 s if
negative — using the times only, never the dates. Your withdrawal holds are
multi-day:

```
Subject 0533F   Start Date 08/30/25 11:5x   End Date 09/14/25 11:5x   → 16 days
```

**v6.3:** max duration across all 1,712 sessions = **24.0 h**. 1,381 sessions
have `session_span_days > 1`, and not one of them exceeded 24 h.
**v7.0:** max = **360.2 h**; withdrawal means go from 13.8 h to 92.3 h.

This also silently corrupted `response_rate` (`active_presses / duration_hr`)
and every "short session" flag.

### 8–9. Hourly data

* **FR / fentanyl / PR:** v6.3 declared no `active_timestamps`, so
  `active_events` was 0 in all 4,083 hourly rows. v7.0 uses the 7-column `J`
  block the program documents:

  ```
  J(Q)=H.M, J(Q+1)=R, J(Q+2)=I, J(Q+3)=D, J(Q+4)=A, J(Q+5)=L, J(Q+6)=F
  ```

  Column sums reproduce the `R`/`I`/`A` scalars **exactly on 645/645 fentanyl
  records and 29/29 FR20 records**, so hourly totals now reconcile with session
  totals to the unit.

  PR is the exception: its `J` writes a sentinel at `J(Q+7)` and the columns do
  not reconcile on any stride from 6 to 9, so PR hourly is built from `C` and
  `W` instead. This is called out in `config.py` rather than papered over.

* **Intermittent access:** v6.3 pointed both `infusion_timestamps` and
  `active_timestamps` at `O` and capped both at the infusion count, so
  `active_events` was an exact copy of `infusion_events` — 107,757 of them.
  But `R` (LLEVER presses) is 136,102 against 100,856 infusions, so the hourly
  discrimination was fabricated. This program has no LLEVER time array, so v7.0
  leaves hourly `active_events` empty rather than inventing it.

  This is why the headline hourly `active_events` total drops from 107,757 to
  25,985. The new number is smaller because it is real: 19,021 + 6,154 + 286 +
  137 + 387 = 25,985, matching the session-level active totals exactly.

### 10. Unrecognised MSNs no longer analysed with the wrong mapping

v6.3:

```python
prog    = "UNMAPPED"
mapping = mappings.get("RAT - FR20", {})   # ← fallback
```

A new program would be read for `I`/`R`/`A` regardless of what those letters
mean in it, and land in an `UNMAPPED_Full_Analysis.xlsx` that looks like real
data. v7.0 skips them, returns them in `df_unmapped`, shows a red banner with a
count, and writes `00_Unrecognized_MSNs.xlsx` into the ZIP.

### Also changed

* `RAT - FR20`, `RAT - FR20 FOOD RESTRICT` and `RAT - FR20 PDT` are now separate
  programs. v6.3 pooled all three under `RAT - FR20`; PDT is a punished
  discrete-trial schedule with a 10 s timeout and should not be averaged with
  plain FR20.
* `get_val` no longer silently returns 0 for a letter that is absent — it
  distinguishes "not in this record" from "recorded as zero".
* `RAT - WITHDRAWAL` is marked `no_behavioural_data`. That program wires no
  levers, so its zeros are correct and it is now exempt from the "low activity"
  and "high inactive ratio" flags instead of being flagged on every session.
* New flag `impossible_efficiency_flag` (`infusions > active_presses`), which
  would have caught the intermittent-access lever swap immediately.

---

## Files changed

| File | Change |
|---|---|
| `config.py` | v7.0 — pattern order, DT4 split, FR FOOD infusions, extinction active var, PR breakpoint mode, FR20 split, segment definitions |
| `analyzer.py` | `resolve_program`, `compute_breakpoint`, `hourly_from_j_array`, `build_segments`, `create_segment_summary`, date-aware `calculate_duration`, no UNMAPPED fallback. **`process_sessions` now returns a 5-tuple** |
| `app.py` | unpack 5-tuple, "Unrecognised MSN" metric + banner, `Segments` / `Segment_Summary` sheets, `00_Unrecognized_MSNs.xlsx`, per-program segment figure |
| `plotter.py` | `create_segment_plot` added; nothing removed |
| `parser.py`, `utils.py` | unchanged |

**Breaking change:** `process_sessions` returns
`(df_sessions, df_hourly, found_ids, df_segments, df_unmapped)`.
`app.py` is already updated; any other caller needs the same edit.

---

## Still unverified

Every `MOUSE - *` mapping. There are no mouse `.MPC` files anywhere in the
project folder, so those entries are carried over from v6.3 on trust and are now
tagged `"unverified": True`, surfaced as a `mapping_unverified` column. Confirm
them against the mouse programs before publishing mouse data.

Two things worth a decision rather than a patch:

* `create_daily_summary` groups by `session_day` (a per-program session ordinal),
  not calendar date. When a box emits two records for one day, that day is split
  across two "daily" rows. Left as-is because the plots depend on the current
  behaviour — but the sheet is named "Daily", which invites misreading.
* Subject IDs in the data are inconsistent: `O589F`, `0589F`, `561M`, `F514F`
  and `FS14F` all appear. `canonicalize_id` only fixes a leading `O` before a
  digit, so `561M` and `0561M` remain different animals and `FS14F` / `F514F`
  never merge.
