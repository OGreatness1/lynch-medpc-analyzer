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


# MedPC inter-session separator pattern.
# Between sessions MedPC writes:
#   <blank line>
#   <session counter — a bare integer, possibly with leading whitespace>
#   <blank line>
#   Start Date: ...
#
# The session-counter line looks like "    4" or "  153".
# It must be recognised as a separator / discarded, NOT parsed as array data.
_SESSION_COUNTER_RE = re.compile(r"^\s*\d+\s*$")


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

    def _is_session_separator(self, line: str) -> bool:
        """
        Return True for lines that are part of MedPC's inter-session separator:
          - Blank / whitespace-only lines
          - Lines containing only a bare integer (the session counter)
          - File header lines  (e.g.  'File: C:\\MED-PC IV\\DATA\\!2026-01-15')
        """
        stripped = line.strip()
        if not stripped:
            return True
        if _SESSION_COUNTER_RE.match(stripped):
            return True
        if stripped.lower().startswith("file:") or stripped.lower().startswith("file "):
            return True
        return False

    def _extract_session_blocks(self, content: str) -> List[str]:
        """
        Split a multi-session MedPC export file into individual session blocks.

        MedPC inter-session format (confirmed from real data files):
            <blank>
            <session-counter integer>   ← bare number, not a data line
            <blank>
            Start Date: MM/DD/YY
            ...

        Primary delimiter:  any line that starts with 'Start Date:'
        Secondary delimiter: \\FILENAME.MPC header or ===== separator lines
        All separator/File/counter lines are dropped from the block content.
        """
        blocks = []
        current_lines: List[str] = []

        for line in content.splitlines():
            stripped = line.strip()

            # ── Primary delimiter: Start Date: line ───────────────────────────
            if stripped.startswith("Start Date:"):
                if current_lines:
                    block = "\n".join(current_lines).strip()
                    if "Start Date:" in block and len(block) > 50:
                        blocks.append(block)
                # Begin new block with this line
                current_lines = [line]
                continue

            # ── Secondary delimiters ──────────────────────────────────────────
            if (stripped.startswith("\\") and "MPC" in stripped.upper()) or re.match(r"={5,}", stripped):
                if current_lines:
                    block = "\n".join(current_lines).strip()
                    if "Start Date:" in block and len(block) > 50:
                        blocks.append(block)
                current_lines = []
                continue

            # ── Separator lines: blank, session counter, File: header ─────────
            # Drop these entirely — do not append to current_lines.
            if self._is_session_separator(line):
                continue

            # ── Normal content ────────────────────────────────────────────────
            current_lines.append(line)

        # Flush the last block
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
        lines = block.splitlines()
        meta: Dict[str, str]    = {}
        scalars: Dict[str, float] = {}
        arrays: Dict[str, List[float]] = {}
        i = 0

        # ── 1. Metadata / Header ──────────────────────────────────────────────
        # Read key: value lines until we hit the first scalar or array header.
        # A scalar header looks like "A:  123.45" (letter, colon, space, number).
        # An array header looks like "A:" (letter, colon, end-of-line).
        KNOWN_META_KEYS = {
            "Subject", "MSN", "Start Date", "End Date", "Box", "Room",
            "Experiment", "Group", "Protocol", "Comment",
            "Start Time", "End Time",
        }
        KNOWN_META_LOWER = {k.lower() for k in KNOWN_META_KEYS} | {
            "box", "room", "cage", "experiment", "group"
        }

        while i < len(lines):
            line = lines[i].strip()
            # Stop when we reach the scalar/array section
            if re.match(r"^[A-Z]:\s*-?\d", line) or re.match(r"^[A-Z]:$", line):
                break
            if ":" in line and not line.startswith("\\"):
                key_part, val_part = line.split(":", 1)
                key = key_part.strip()
                val = val_part.strip()
                if key in KNOWN_META_KEYS or key.lower() in KNOWN_META_LOWER:
                    meta[key] = val
            i += 1

        # ── 2. Scalars ────────────────────────────────────────────────────────
        # Lines of the form  "A:  123.45"  or  "I:  0"
        # Stop at the first array header ("A:" alone on a line).
        while i < len(lines):
            line = lines[i].strip()
            scalar_match = re.match(
                r"^([A-Z]):\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$", line
            )
            if scalar_match:
                var = scalar_match.group(1)
                val = self._safe_float(scalar_match.group(2))
                if val is not None:
                    scalars[var] = val
            elif re.match(r"^[A-Z]:$", line):
                break   # first array header — stop scalar parsing
            elif line.startswith("\\") or re.match(r"={5,}", line):
                break
            # blank lines between scalars are fine — just skip
            i += 1

        # ── 3. Arrays ─────────────────────────────────────────────────────────
        current_var: Optional[str] = None
        current_data: List[float]  = []

        while i < len(lines):
            line = lines[i].strip()

            # Array header: single letter + colon on its own line, e.g. "A:"
            m = re.match(r"^([A-Z]):$", line)
            if m:
                if current_var is not None and current_data:
                    arrays[current_var] = current_data
                current_var = m.group(1)
                current_data = []

            elif current_var is not None and line:
                # ── Row-indexed data line, e.g. "     0:  1234.0  5678.0" ────
                # Strip the leading row index (digits followed by colon).
                # A line that is ONLY a row index with no data values produces
                # an empty string after stripping — handled gracefully below.
                clean = re.sub(r"^\d+:\s*", "", line)

                # Safety check: if after stripping we have a lone integer with
                # no decimal or scientific notation, it could be a session
                # counter that slipped through — skip it.
                # (Real data values always appear alongside other numbers on
                # the same row-indexed line.)
                if _SESSION_COUNTER_RE.match(clean):
                    i += 1
                    continue

                # Parse each whitespace-separated token.
                # Filter val < 0: the -987.987 MedPC end-of-data sentinel is
                # the only negative value in these files; no real count or
                # timestamp is ever negative.
                for token in clean.split():
                    val = self._safe_float(token)
                    if val is not None and val >= 0:
                        current_data.append(val)

            i += 1

        # Flush the last array
        if current_var is not None and current_data:
            arrays[current_var] = current_data

        # ── Validation ────────────────────────────────────────────────────────
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
