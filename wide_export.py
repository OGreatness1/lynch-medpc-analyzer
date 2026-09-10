"""
wide_export.py — export MedPC results in the Lynch Lab paper layout.

Reproduces the structure of Paper2_Beh_Western_IHC_Luminex.xlsx exactly:

    A          B        C        D ...                          (columns)
 1  <blank>    ID       Group    IntA1 IntA2 ... IntA10 IntA_Mean   ← header, navy fill
 2  <blank>    NAIVE - MALE  (10 s)                                 ← group banner
 3  1          O366M    Naive    <values>
 …
15  <blank>    Mean              =IFERROR(AVERAGE(D3:D14),"")       ← cream fill, bold
16  <blank>    SEM               =IFERROR(STDEV(D3:D14)/SQRT(COUNT(D3:D14)),"")
17  <blank>                                                          ← two blank rows
18  <blank>
19  <blank>    NAIVE - FEMALE  (7 s)   Group  IntA1 …                ← banner repeats header

One sheet per program plus a `Joined` sheet merged on ID, matching the
Joined / Luminex / Beh. / Western / IHC arrangement of the source workbook.

Column naming follows the source file: the primary measure keeps the bare
`<Prog><n>` / `<Prog>_Mean` names (so `IntA1 … IntA10`, `IntA_Mean` are
byte-identical to what you already have), and the secondary measures take a
suffixed block — `IntA_Act1 … IntA_Act10`, `IntA_Act_Mean`, and the same for
`_Inact`. Downstream scripts keyed on the existing infusion column names keep
working.

Mean and SEM are written as live formulas, not baked values, so editing or
deleting an animal's row updates them — same as the source workbook.

GROUP ASSIGNMENT
----------------
MedPC records carry no group: the `Group` and `Experiment` header fields are
"0" in every raw file. Group therefore comes from the ID list, which may now be
one, two or three columns (comma-, tab- or whitespace-separated):

    O366M                 → Group blank, block = sex only
    O366M,Naive           → Group "Naive", block = "NAIVE - MALE"
    O366M,Naive,Cohort1   → Group "Naive", block = "COHORT1 - MALE"

The optional third column is the block label, for when several groups share one
banner. In the source workbook the `NAIVE - MALE` block holds both Naive and
Saline animals; a third column of `Naive` for both reproduces that.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ── styling, lifted from the source workbook ────────────────────────────────
FONT_NAME = "Arial"
FONT_SIZE = 10

HDR_FILL    = PatternFill("solid", start_color="FF305496")
HDR_FONT    = Font(name=FONT_NAME, size=FONT_SIZE, bold=True, color="FFFFFFFF")
BANNER_FILL = PatternFill("solid", start_color="FFD9E1F2")
BANNER_FONT = Font(name=FONT_NAME, size=FONT_SIZE, bold=True, color="FF1F3864")
MEAN_FILL   = PatternFill("solid", start_color="FFFFF2CC")
MEAN_FONT   = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
SEM_FILL    = PatternFill("solid", start_color="FFFFF9E5")
SEM_FONT    = Font(name=FONT_NAME, size=FONT_SIZE, bold=False)
BODY_FONT   = Font(name=FONT_NAME, size=FONT_SIZE)

_thin = Side(style="thin")
BORDER_ALL = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
BORDER_LRB = Border(left=_thin, right=_thin, bottom=_thin)

CENTER = Alignment(horizontal="center")
LEFT   = Alignment(horizontal="left")

BLANK_ROWS_BETWEEN_BLOCKS = 2

# ── program → short column/sheet prefix ─────────────────────────────────────
PROGRAM_SHORT = {
    "RAT - INTERMITTENT ACCESS":            "IntA",
    "RAT - INT ACCESS (FOOD RESTRICT)":     "IntA_FR",
    "RAT - FENTANYL FR40 LD":               "FentFR40",
    "RAT - FENTANYL FR40 LD FOOD RESTRICT": "FentFR40_FR",
    "RAT - FR20":                           "FR20",
    "RAT - FR20 FOOD RESTRICT":             "FR20_FR",
    "RAT - FR20 PDT":                       "FR20PDT",
    "RAT - FR40":                           "FR40",
    "RAT - FR FOOD / MAG TRAINING":         "FRFood",
    "RAT - DISCRETE TRIAL (DT4)":           "DT4",
    "RAT - WITHDRAWAL":                     "With",
    "RAT - EXTINCTION":                     "Ext",
    "RAT - REINSTATEMENT":                  "Reinst",
    "RAT - CUE RELAPSE G138A":              "Cue138A",
    "RAT - CUE RELAPSE G138B":              "Cue138B",
    "RAT - CUE RELAPSE 7HR":                "Cue7hr",
    "RAT - CUE RELAPSE 2HR":                "Cue2hr",
    "RAT - PR FENTANYL":                    "PRFent",
    "RAT - PR COCAINE":                     "PRCoc",
    "RAT - PR FOOD":                        "PRFood",
    "RAT - FLUSH":                          "Flush",
    "RAT - CONTINUOUS FENTANYL":            "ContFent",
    "RAT - LOCOMOTOR BASELINE":             "Loco",
    "MOUSE - FR1":                          "MsFR1",
    "MOUSE - PR":                           "MsPR",
    "MOUSE - EXTENDED ACCESS":              "MsExtA",
}

# Primary measure keeps the bare `<Prog><n>` naming from the source workbook.
SESSION_MEASURES: List[Tuple[str, str]] = [
    ("infusions", ""),          # IntA1 … IntA10, IntA_Mean
    ("active_presses", "_Act"),  # IntA_Act1 … IntA_Act10, IntA_Act_Mean
    ("inactive_presses", "_Inact"),
]


def program_short(program: str) -> str:
    if program in PROGRAM_SHORT:
        return PROGRAM_SHORT[program]
    s = re.sub(r"^(RAT|MOUSE)\s*-\s*", "", str(program))
    s = re.sub(r"[^A-Za-z0-9]+", "", s.title())
    return s[:16] or "Prog"


def safe_sheet_name(name: str, used: set) -> str:
    s = re.sub(r"[\[\]:*?/\\]", "_", str(name))[:31] or "Sheet"
    base, i = s, 2
    while s in used:
        suffix = f"_{i}"
        s = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(s)
    return s


# ── ID list parsing ─────────────────────────────────────────────────────────
def parse_id_list(lines, canonicalize) -> Tuple[set, Dict[str, str], Dict[str, str]]:
    """Parse a 1-, 2- or 3-column ID list.

    Returns (allowed_canonical_ids, id -> group, id -> block_label).
    Accepts comma, tab or whitespace separators. A `#` line is a comment, and a
    first row of ID/Group headers is skipped.
    """
    allowed, groups, blocks = set(), {}, {}
    for raw in lines:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"[,\t]|\s{2,}", line) if p.strip()]
        if len(parts) == 1:
            parts = line.split()
        if not parts:
            continue
        if parts[0].lower() in ("id", "subject", "animal"):
            continue                                    # header row
        cid = canonicalize(parts[0])
        if not cid:
            continue
        allowed.add(cid)
        if len(parts) > 1:
            groups[cid] = parts[1]
        if len(parts) > 2:
            blocks[cid] = parts[2]
    return allowed, groups, blocks


# ── reshaping ───────────────────────────────────────────────────────────────
def _pivot(df: pd.DataFrame, value_col: str, prefix: str) -> pd.DataFrame:
    """One row per subject, one column per session ordinal, plus a _Mean."""
    if df.empty or value_col not in df.columns or "session_day" not in df.columns:
        return pd.DataFrame()
    p = df.pivot_table(index="canonical_subject", columns="session_day",
                       values=value_col, aggfunc="sum")
    if p.empty:
        return pd.DataFrame()
    p = p.reindex(columns=sorted(p.columns))
    p.columns = [f"{prefix}{int(c)}" for c in p.columns]
    p[f"{prefix.rstrip('0123456789')}_Mean"] = p.mean(axis=1, skipna=True)
    return p


def _pivot_segments(seg: pd.DataFrame, short: str) -> pd.DataFrame:
    """Extinction sessions and relapse segments, one column each.

    This is where the multi-session records land in the wide layout — an
    extinction record's nine hourly sessions and its reinstatement test become
    nine numbered columns plus a reinstatement column, rather than one total.
    """
    if seg is None or seg.empty:
        return pd.DataFrame()
    out = []
    for stype, block in seg.groupby("segment_type"):
        tag = {"extinction_session": "ExtSess",
               "relapse_segment": "Seg",
               "reinstatement_test": "Reinst"}.get(stype, re.sub(r"[^A-Za-z0-9]", "", stype.title()))
        for measure, msuffix in (("active_responses", ""),
                                 ("inactive_responses", "_Inact"),
                                 ("cue_deliveries", "_Cue")):
            if measure not in block.columns or not block[measure].notna().any():
                continue
            p = block.pivot_table(index="canonical_subject", columns="segment_index",
                                  values=measure, aggfunc="mean")
            if p.empty:
                continue
            p = p.reindex(columns=sorted(p.columns))
            if stype == "reinstatement_test":
                p.columns = [f"{short}_{tag}{msuffix}" for _ in p.columns]
                p = p.loc[:, ~p.columns.duplicated()]
            else:
                p.columns = [f"{short}_{tag}{msuffix}{int(c)}" for c in p.columns]
                p[f"{short}_{tag}{msuffix}_Mean"] = p.mean(axis=1, skipna=True)
            out.append(p)
    if not out:
        return pd.DataFrame()
    return pd.concat(out, axis=1)


def build_program_table(sess: pd.DataFrame, seg: Optional[pd.DataFrame],
                        program: str) -> pd.DataFrame:
    """Wide table for one program: index = subject, columns = measure blocks."""
    short = program_short(program)
    sub = sess[sess["program_name"] == program]
    parts = []
    for col, suffix in SESSION_MEASURES:
        if col not in sub.columns:
            continue
        if not sub[col].notna().any() or (sub[col].fillna(0) == 0).all():
            # A measure that is legitimately zero for the whole program
            # (withdrawal has no levers) adds a wall of zeros; skip it.
            if col != "infusions":
                continue
        prefix = f"{short}{suffix}" if suffix else short
        p = _pivot(sub, col, prefix)
        if not p.empty:
            parts.append(p)

    if seg is not None and not seg.empty:
        sseg = seg[seg["program_name"] == program]
        p = _pivot_segments(sseg, short)
        if not p.empty:
            parts.append(p)

    if not parts:
        return pd.DataFrame()
    wide = pd.concat(parts, axis=1)
    wide.index.name = "ID"
    return wide


# ── sheet writing ───────────────────────────────────────────────────────────
def _style_header(ws, row: int, ncols: int):
    for c in range(2, ncols + 1):
        cell = ws.cell(row, c)
        cell.font, cell.fill = HDR_FONT, HDR_FILL
        cell.alignment, cell.border = CENTER, BORDER_ALL


def _write_header(ws, row: int, headers: List[str]):
    ws.cell(row, 2, "ID")
    ws.cell(row, 3, "Group")
    for i, h in enumerate(headers):
        ws.cell(row, 4 + i, h)
    _style_header(ws, row, 3 + len(headers))


def write_sheet(ws, wide: pd.DataFrame, meta: pd.DataFrame):
    """Write one program sheet in the paper layout.

    `meta` must have canonical_subject, gender, group, block columns.
    """
    headers = list(wide.columns)
    ncols = 3 + len(headers)
    last_col = get_column_letter(ncols)

    _write_header(ws, 1, headers)
    row = 2
    first_block = True

    meta = meta.copy()
    meta["_sex"] = meta["gender"].fillna("Unknown").str.upper()
    # Sort blocks in the order they first appear, sexes MALE before FEMALE.
    sex_rank = {"MALE": 0, "FEMALE": 1, "UNKNOWN": 2}
    block_order = list(dict.fromkeys(meta["block"].tolist()))

    for block_label in block_order:
        for sex in sorted(meta.loc[meta["block"] == block_label, "_sex"].unique(),
                          key=lambda s: sex_rank.get(s, 3)):
            members = meta[(meta["block"] == block_label) & (meta["_sex"] == sex)]
            members = members.sort_values(["group", "canonical_subject"])
            ids = [i for i in members["canonical_subject"] if i in wide.index]
            if not ids:
                continue

            n = len(ids)
            banner = ws.cell(row, 2, f"{str(block_label).upper()} - {sex}  ({n} s)")
            banner.font, banner.fill = BANNER_FONT, BANNER_FILL
            banner.alignment, banner.border = LEFT, BORDER_ALL
            if not first_block:
                # Later banners repeat the header from column C rightward,
                # exactly as the source workbook does.
                ws.cell(row, 3, "Group")
                for i, h in enumerate(headers):
                    ws.cell(row, 4 + i, h)
            for c in range(3, ncols + 1):
                cell = ws.cell(row, c)
                cell.font, cell.fill = BANNER_FONT, BANNER_FILL
                cell.alignment, cell.border = LEFT, BORDER_ALL
            first_block = False
            row += 1

            data_start = row
            for i, sid in enumerate(ids, start=1):
                idx = ws.cell(row, 1, i)
                idx.font, idx.alignment, idx.border = BODY_FONT, CENTER, BORDER_LRB
                for col, val in ((2, sid),
                                 (3, members.loc[members["canonical_subject"] == sid,
                                                 "group"].iloc[0])):
                    cell = ws.cell(row, col, val if val else None)
                    cell.font, cell.border = BODY_FONT, BORDER_LRB
                vals = wide.loc[sid]
                for j, h in enumerate(headers):
                    v = vals[h]
                    cell = ws.cell(row, 4 + j, None if pd.isna(v) else float(v))
                    cell.font, cell.alignment, cell.border = BODY_FONT, CENTER, BORDER_LRB
                row += 1
            data_end = row - 1

            for label, font, fill, tmpl in (
                ("Mean", MEAN_FONT, MEAN_FILL, '=IFERROR(AVERAGE({c}{a}:{c}{b}),"")'),
                ("SEM",  SEM_FONT,  SEM_FILL,
                 '=IFERROR(STDEV({c}{a}:{c}{b})/SQRT(COUNT({c}{a}:{c}{b})),"")'),
            ):
                cell = ws.cell(row, 2, label)
                cell.font, cell.fill, cell.border = font, fill, BORDER_ALL
                ws.cell(row, 3).fill = fill
                ws.cell(row, 3).border = BORDER_ALL
                for j in range(len(headers)):
                    letter = get_column_letter(4 + j)
                    cell = ws.cell(row, 4 + j,
                                   tmpl.format(c=letter, a=data_start, b=data_end))
                    cell.font, cell.fill, cell.border = font, fill, BORDER_ALL
                row += 1

            row += BLANK_ROWS_BETWEEN_BLOCKS

    ws.freeze_panes = "D2"
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 10
    for j in range(len(headers)):
        letter = get_column_letter(4 + j)
        ws.column_dimensions[letter].width = max(8, min(16, len(headers[j]) + 2))
    return last_col


def build_wide_workbook(df_sess: pd.DataFrame,
                        df_seg: Optional[pd.DataFrame],
                        groups: Dict[str, str],
                        blocks: Dict[str, str],
                        path_or_buffer) -> List[str]:
    """Write the paper-format workbook. Returns the sheet names created."""
    if df_sess is None or df_sess.empty:
        raise ValueError("No session data to export.")

    meta = (df_sess[["canonical_subject", "gender"]]
            .drop_duplicates("canonical_subject")
            .reset_index(drop=True))
    meta["group"] = meta["canonical_subject"].map(groups).fillna("")
    meta["block"] = (meta["canonical_subject"].map(blocks)
                     .fillna(meta["group"])
                     .replace("", "ALL"))

    wb = Workbook()
    wb.remove(wb.active)
    used, joined_parts, created = set(), [], []

    for program in sorted(df_sess["program_name"].unique()):
        wide = build_program_table(df_sess, df_seg, program)
        if wide.empty:
            continue
        name = safe_sheet_name(program_short(program), used)
        ws = wb.create_sheet(name)
        write_sheet(ws, wide, meta)
        created.append(name)
        joined_parts.append(wide)

    if joined_parts:
        joined = pd.concat(joined_parts, axis=1)
        joined = joined.loc[:, ~joined.columns.duplicated()]
        ws = wb.create_sheet("Joined", 0)
        write_sheet(ws, joined, meta)
        created.insert(0, "Joined")

    wb.save(path_or_buffer)
    return created
