import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ParsedSession:
    meta: Dict[str, str]
    scalars: Dict[str, float]
    arrays: Dict[str, List[float]]
    filename: str
    raw_block: str


# Matches a line that is ONLY a bare integer — the MedPC inter-session counter.
# Pattern requires the full string to be digits (plus optional surrounding whitespace).
# Used ONLY for block-splitting, NOT inside array parsing (see note below).
_BARE_INTEGER_RE = re.compile(r"^\d+$")


class MedPCParser:
    def __init__(self):
        self.skipped_sessions: List[Tuple[str, str, str]] = []

    def parse_file(self, content: str, filename: str) -> List["ParsedSession"]:
        """Split file into session blocks and parse each one."""
        session_blocks = self._extract_session_blocks(content)
        parsed = []

        for block in session_blocks:
            try:
                session = self._parse_single_session(block.strip(), filename)
                if session:
                    parsed.append(session)
            except Exception as e:
                short = (block[:180] + "...") if len(block) > 180 else block
                self.skipped_sessions.append((filename, str(e), short.replace("\n", " ")))

        return parsed

    def _is_separator_line(self, line: str) -> bool:
        """
        Return True for lines that are inter-session separators and should be
        dropped entirely before any block is assembled:
          - Blank / whitespace-only lines
          - Bare integer lines  (MedPC session counter, e.g. "    4" or "  153")
          - File: header lines  (e.g. "File: C:\\MED-PC IV\\DATA\\!2026-01-15")

        These appear between sessions in every MedPC export file in the pattern:
            <blank>
            <session counter>
            <blank>
            Start Date: ...
        """
        stripped = line.strip()
        if not stripped:
            return True
        if _BARE_INTEGER_RE.match(stripped):
            return True
        if stripped.lower().startswith("file:") or stripped.lower().startswith("file "):
            return True
        return False

    def _extract_session_blocks(self, content: str) -> List[str]:
        """
        Split a multi-session MedPC export file into individual session blocks.

        'Start Date:' is always the first line of a new session, so it is used
        as the primary delimiter.  Separator lines (blank, session counter,
        File: header) are dropped before blocks are assembled.
        """
        blocks: List[str] = []
        current_lines: List[str] = []

        for line in content.splitlines():
            stripped = line.strip()

            # ── Separator lines — drop completely ────────────────────────────
            if self._is_separator_line(line):
                continue

            # ── Primary delimiter: Start Date: begins a new session ──────────
            if stripped.startswith("Start Date:"):
                if current_lines:
                    block = "\n".join(current_lines).strip()
                    if "Start Date:" in block and len(block) > 50:
                        blocks.append(block)
                current_lines = [line]
                continue

            # ── Secondary delimiters (\\PROG.MPC header, ===== line) ─────────
            if (stripped.startswith("\\") and "MPC" in stripped.upper()) or re.match(r"={5,}", stripped):
                if current_lines:
                    block = "\n".join(current_lines).strip()
                    if "Start Date:" in block and len(block) > 50:
                        blocks.append(block)
                current_lines = []
                continue

            # ── Normal content line ───────────────────────────────────────────
            current_lines.append(line)

        # Flush final block
        if current_lines:
            block = "\n".join(current_lines).strip()
            if "Start Date:" in block and len(block) > 50:
                blocks.append(block)

        return blocks

    def _safe_float(self, s: str) -> Optional[float]:
        """
        Safely parse a string to float.
        Handles integers, decimals, and scientific notation (e.g. 1.5e+03).
        Returns None on failure — never raises.
        """
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    def _parse_single_session(self, block: str, filename: str) -> Optional["ParsedSession"]:
        """Parse one record into metadata, scalars and arrays.

        ORDER-INDEPENDENT (v7.2). The previous version parsed in three fixed
        phases and the scalar phase stopped at the first bare "X:" array header:

            elif re.match(r"^[A-Z]:$", line):
                break   # first array header - stop scalar parsing

        That assumes MedPC always prints every scalar before every array. It
        does so only when DISKVARS happens to be ordered that way. When a
        program declares an array early -- e.g. DISKVARS = A,B,C,I,M,N,O,P,Q,U
        where B is DIM'd -- every scalar after that array is silently dropped,
        so U (extinction total), M/N/O (reinstatement) and Q (session number)
        come back missing and the per-session breakdown collapses to nothing.

        This version makes a single pass and classifies each line on its own
        merits, so scalars and arrays may interleave freely.
        """
        lines = block.splitlines()
        meta: Dict[str, str] = {}
        scalars: Dict[str, float] = {}
        arrays: Dict[str, List[float]] = {}

        KNOWN_META_KEYS = {
            "Subject", "MSN", "Start Date", "End Date", "Box", "Room",
            "Experiment", "Group", "Protocol", "Comment",
            "Start Time", "End Time",
        }
        KNOWN_META_LOWER = {k.lower() for k in KNOWN_META_KEYS} | {
            "box", "room", "cage", "experiment", "group"
        }

        SCALAR_RE = re.compile(r"^([A-Z]):\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$")
        ARRAY_HDR_RE = re.compile(r"^([A-Z]):$")
        ROW_RE = re.compile(r"^\d+:\s*")

        current_var: Optional[str] = None
        current_data: List[float] = []

        def flush():
            nonlocal current_var, current_data
            if current_var is not None:
                # Keep zero-length arrays too: "present but empty" is a real,
                # distinguishable state from "absent".
                arrays[current_var] = current_data
            current_var, current_data = None, []

        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("\\") or re.match(r"={5,}", line):
                flush()
                continue

            m = ARRAY_HDR_RE.match(line)
            if m:
                flush()
                current_var = m.group(1)
                current_data = []
                continue

            m = SCALAR_RE.match(line)
            if m:
                flush()
                val = self._safe_float(m.group(2))
                if val is not None:
                    scalars[m.group(1)] = val
                continue

            if current_var is not None and ROW_RE.match(line):
                clean = ROW_RE.sub("", line)
                for token in clean.split():
                    val = self._safe_float(token)
                    # -987.987 is MedPC's end-of-data sentinel; it is the only
                    # negative value these programs emit.
                    if val is not None and val >= 0:
                        current_data.append(val)
                continue

            if ":" in line and not line.startswith("\\"):
                key_part, val_part = line.split(":", 1)
                key, val = key_part.strip(), val_part.strip()
                if key in KNOWN_META_KEYS or key.lower() in KNOWN_META_LOWER:
                    flush()
                    meta[key] = val
                continue

        flush()

        if not meta.get("Start Date") or not meta.get("Subject"):
            raise ValueError("Missing required metadata (Start Date or Subject)")

        return ParsedSession(
            meta=meta,
            scalars=scalars,
            arrays=arrays,
            filename=filename,
            raw_block=block[:600] + "..." if len(block) > 600 else block,
        )

    def get_skipped_report(self) -> List[Dict]:
        return [{"File": f, "Reason": r, "Snippet": s} for f, r, s in self.skipped_sessions]
