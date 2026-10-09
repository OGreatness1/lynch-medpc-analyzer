# v7.3: Accuracy audit of every program

Every mapped program was checked two ways:

* **Against its `.MPC` source.** 287 files, 153 unique. For every variable, each
  statement that writes it was extracted, and every variant (room copies,
  ESD / B-box / pre-2019 versions) was compared.
* **Against real records.** 8,370 records: `G126/1-16/2017` and `2018` from the
  data backup, plus the 2025 files in `MedPC Processing File/New folder`.
  Every count was reconciled with its timestamp array and hourly array.

Regression suites: `python test_extinction.py` (50 checks) and
`python test_programs.py` (26 checks). They build records the way MedPC
writes them. Programs with no `DISKVARS` line write **every** letter, so
unused counters are present as 0, not missing.

## Effect on the real data (v7.2 → v7.3)

| Program | Sessions | Zero-infusion sessions | Infusions / session | Infusions / hour |
|---|---|---|---|---|
| FR20 | 1,656 → 1,316 | 307 → 139 | 13.6 → 13.4 | 0.80 → 0.66 |
| DT4 | 2,290 → 2,151 | 227 → 111 | 47.9 → 50.7 | – |
| Intermittent access | 728 → 661 | 82 → 43 | 161.4 → 175.5 | 14.7 → 8.2 |
| PR cocaine | 774 → 730 | 53 → 21 | 11.2 → 11.6 | 1.18 → 0.53 |
| Fentanyl FR40 LD | 483 → 423 | 62 → 35 | 28.4 → 29.6 | 1.45 → 1.45 |
| Fentanyl FR40 LD food restrict | 162 → 140 | 18 → 5 | 27.0 → 29.2 | 1.35 → 1.34 |
| FR20 PDT | 374 → 297 | 89 → 43 | 13.4 → 15.1 | 0.74 → 0.75 |
| FR food / mag training | 704 → 668 | 74 → 38 | 186.8 → 196.8 | – |
| Extinction (9-session + reinstatement) | 138 → 55 | | reinstatement mean 14.1 → 30.0 | |
| Extinction only (2017) | (pooled above) → 73 | | | |
| FR23hr | not analysed → 7 | | 61.0 | |
| Intermittent (2017 discrete-trial) | not analysed → 2 | | 32.5 | |
| Cue relapse, Reinstatement, Withdrawal, FR20 food restrict | unchanged | | | |

Unrecognised sessions: 259 → 187. Each one now carries the reason it was
not analysed.

---

## 1. Record handling (affects every program)

### 1a. Duplicate saves were counted twice
MedPC often writes the same session into the daily file twice: an interim save
partway through (End Time 11:00 or 11:50 is typical) and the final record.
The app counted both copies. In the 2025 data 70 of 1,655 records were such
copies; in G126 2017–18, 301 were. Because `session_day` is a running count,
each extra copy also moved every later day's number for that animal.

**Now:** records with the same Subject, Start Date, Start Time, Box and MSN are
merged, keeping the copy that ended latest. In all 33 copies whose data
differed, the later copy was ≥ the earlier one on every variable; several
interim copies were all zeros. So nothing is lost. The copies dropped are
listed under **Data quality**.

### 1b. Daily-reset remnants were counted as 23-hour zero-intake sessions
The 24 h programs (FR20, FR20 PDT, Fentanyl FR40, PR, DT4, intermittent
access, FR23hr) flush the day's data around 11:00–12:00, then reset their
counters and run `~STARTDATE:= CURRENTDATE;~`, which leaves the start
**time** unchanged. When the next program is loaded, MedPC writes the idle box
as another record. That record's Start Date is today, its Start Time is the
original start, and it ends before it begins. `calculate_duration` added
24 h to it, producing a 23 h session with no responses. Each of these
also pushed the animal's later session days out by one.

There are 488 such records in the real data. For 487, the real session (same
subject, box and start time, ending that day) is also present; the other
belongs to a TEST box. So no data was lost.

**Now:** any record whose End Date equals its Start Date and whose End Time
is before its Start Time is excluded. These are listed under **Data quality**,
together with any presses they hold. DT4 starts a trial at its 12:00 reset,
so its remnants carry the 1–2 presses made before the program change.

---

## 2. Extinction / reinstatement

### 2a. Phantom reinstatement test on extinction records
v7.2 added a reinstatement row whenever the mapping *named* a reinstatement
variable, which it always does. Animals that never entered the cue phase were
then averaged in as zero-response tests.

An earlier draft of this fix checked whether M/N/O were *present* in the
record. That never works: these programs have no DISKVARS line, so MedPC
writes all 26 letters every time. Checking **M/N/O > 0** would also be wrong:
9 of 54 G126 2018 animals entered the cue phase and made no presses, and
dropping those genuine zeros would inflate the reinstatement mean.

**Now:** the program's own state flag decides. In all 10 nine-session program
variants, E = 1 during extinction, and the only assignments `SET E = 0` (in
S.S.19–22) start the cue phase.

### 2b. Extinction sessions that never ran were reported as zeros
An animal that reinstated after session 6 still carries J/K/L, all 0. These
were reported as "0 presses in sessions 7–9" and pulled down the means for
sessions 7–9 of the extinction curve. On the G126 2017–18 records, session 7
of the 9-session program changed from mean 1.1 (n = 138, pooled with the
2017 extinction-only records) to mean 6.2 (n = 14).

**Now:** sessions are limited to 1..Q, where Q is the number of sessions
started. In 127 real records, no animal has a press in a session numbered
above Q.

### 2c. 2017 extinction-only programs
`EXTINCTION G140 ABOXES 2017` has ten sessions (A…L, **M**), with
`U = A+…+M`, and **no reinstatement phase**: there is no `ADD N`, no `ADD O`
and no cue delivery. `Extinction G126 2017` is routed the same way. Its
.MPC is not in the project, but all 73 records have M = N = O = 0, its cue
test ran the next day as `REINSTATEMENT G126 2017`, and its naming matches the
verified G140 pair. Both now map to `RAT - EXTINCTION ONLY (2017, NO
REINSTATEMENT)` (paper-format prefix `ExtNoRein`). They are no longer read as
9 sessions plus a reinstatement test built from session-10 presses.

### 2d. Inactive presses double-counted across phases
In the 9-session programs S.S.8 (`#R^RLEVER: ADD P`) runs ungated through the
cue phase, while S.S.28 counts the same presses into O. Each session row now
has `inactive_presses_extinction_only` (P − O) and
`inactive_presses_reinstatement` (O); `inactive_presses` keeps raw P. The
paper-format `_Inact` block uses the extinction-only figure.

### 2e. Patterns
`"g136aprocaine"` was removed: it was a typo for PRCOCAINE, a different
program. `"g136aboxes"` was removed because it matched a room label, not a
protocol. The Z TEST pattern typo was also corrected.

---

## 3. Hourly data

### 3a. FR / fentanyl hours were clock hours, not session hours
In the J array, J(Q) holds the **clock** hour at the end of each block. A
12:34 start therefore reads 0, 14, 15 … 23, 24, 1 … 11, and the plots and
heatmaps sorted every overnight session's after-midnight hours before its
first hour. `hour` is now the block position, i.e. hours since session start.
The clock label is kept as `clock_hour`. J column sums match R / I / A on
2,429 of 2,442 FR20 / FR20 PDT / Fentanyl records; the other 13 are empty TEST
boxes.

### 3b. Quiet hours were missing from timestamp-based programs
For intermittent access and PR, v7.2 created hourly rows only for hours that
had an event, so per-hour means averaged over active hours only.
Intermittent-access infusions per hour were 14.7; the correct figure is 8.2.
Every hour of the session now has a row, including zeros. Hourly infusions
sum exactly to session infusions on every session.

### 3c. Presses during infusion were always 0
The FR, PR and fentanyl programs save `DISKVARS = A,C,E,F,I,J,L,R,S,T,V,W`,
which does not include D. As a result `timeout_presses_per_inf` read 0
everywhere. It is now taken from J(Q+3), the same count saved per hour: 6,393
such presses across the 2025 fentanyl sessions.

### 3d. 3,200-press timestamp limit
These programs `DIM C = 3200`. Fifteen real PRCOCAINE sessions exceed it, with
up to 4,365 presses. Totals are unaffected, but those sessions'
hourly active-press breakdown under-counts the later hours. They are flagged
(`active_timestamps_capped`) and listed under **Data quality**. PR keeps its
timestamp-based hourly data: its J array is unreliable (330 of 696 sessions
sum to roughly double the totals, consistent with the manual `#K4` cumulative
snapshot being used).

---

## 4. Program mappings

| Program | Finding | Change |
|---|---|---|
| DT4FINAL (4 variants) | I / R / Q correct; the B-box variant uses input 2 | none |
| FR20, FR20 PDT, FR20 food restrict, Fentanyl FR40 (26 files) | I / R / A / C / W / J correct | 3a, 3c |
| **FR23hr** (6 files, 7 real sessions) | Same layout as FR20 (infusion cap 400); invariants hold 7/7 | was unanalysed → `RAT - FR23HR` |
| PR cocaine / fentanyl / food (9 files) | Breakpoint = F[I−1] is correct; automatic infusions never fired (R ≥ presses required in 756/767) | 3b, 3d |
| New intermittent access (all 2017–2025 cohorts) | I / R / U / S / O correct; S counts session seconds | 3b |
| **`INTERMITTENT`** (exact MSN, 2 real sessions) | Discrete-trial program: R is the **inactive** lever (C538F: I = 38, R = 16) | new exact-match route `RAT - INTERMITTENT (2017 DISCRETE-TRIAL)` |
| Cue relapse (7 variants) | Segment / total / cue variables are correct in all; segment timer doubles | 30-min bins (below) |
| FR food / mag training (13 files) | Only lever 1 is ever counted; R = pellets = presses | none |
| Withdrawal | No levers; only M (minutes) is ever non-zero | none |
| **FLUSH** | There is no I; Y = number of flushes, T = seconds per flush | pump time = Y × T (was always 0) |
| Reinstatement only (ONLY REIN, REINSTATEMENT … 2017) | M / N / O correct | none |
| **SECOND ORDER FR20** | Different schedule, no source; every record is a test box | reported as unsupported (was read as FR20) |
| **PR 2 LEVER (22 HOUR)** | No source; not the PRCOCAINE layout | reported as unsupported, with reason |
| **V6 TO 10 Ext PLUS CUE** | Several revisions under one MSN with different M / N meanings | reported as unsupported, with reason |
| Mouse programs | No mouse .MPC or data in the project | unchanged; still marked unverified |

**Cue-relapse time base.** `ADD C(0), C(T)` with T never set increments C(0)
twice per second. The segment threshold of 3600 is therefore 30 min, as the
headers say ("A: 0-30 ACTIVE RESPONSES"). v7.0 had changed this to 60 min.
Confirmed on 42 G138A records: median Start→End is 9.08 h (7 h hold + 2 h
relapse), and A+D+F+G = R in 42/42.

`resolve_program` now accepts patterns beginning with `=` to match an exact
MSN. This was needed because every intermittent MSN contains
"intermittent".

## 5. Other fixes
* **Individual discrimination plot crashed** with more than about 45
  subjects (Plotly facet spacing). The Advanced tab crashed on the 2025 data.
* **Paper-format workbook**: a program with no infusion variable no longer
  shows a block of all-zero "infusion" columns when it has other data.

## 6. Interface
Measured on the 2025 data: Plotly charts per rerun went from 80 to 6–9, and a
click (switching program, subject or view) went from about 13 s to
0.2–1.1 s.

* Exports (the ZIP and the paper-format workbook) are built once per
  analysis, not on every rerun.
* Only the visible view is drawn. Views use a segmented control; programs
  use pills.
* The sidebar is grouped into *1 · Data* and *2 · Options*, with **Run
  analysis** at the bottom. Summary metrics are cards, and there are
  dedicated **Data quality** and **Downloads** views.
* Light and dark themes are defined; charts follow them instead of
  hard-coding `plotly_white`.
* Chart labels are readable: *Subject*, *Sex*, *Session day*. Tooltips are
  trimmed.
* *Clear results* keeps you signed in. A missing `secrets.toml` now
  produces a clear message instead of a `KeyError`.

## Not changed: open questions
* **Cohort filter.** The filter looks for room codes inside the Subject ID.
  The lab's IDs (`O479M`, `C1264M`) never contain one, so deselecting *All
  Others* removes every subject. A decision is needed on where the room
  should come from: the ID list, the MSN, or the Box number.
* **PR 2 LEVER (136 real sessions) and the V6 extinction programs** need
  their `.MPC` files before they can be mapped.
* **Test boxes** (Subject `0`, `TEST`, `TEST2`, …) are analysed like animals
  unless an ID list is supplied.
* Records with a blank Subject go to the skipped log. In 2025 these include
  Box 10 on 11/07–11/08, a FENTANYL FR40 LD session with real presses.
