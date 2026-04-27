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
        lines = block.splitlines()
        meta: Dict[str, str] = {}
        scalars: Dict[str, float] = {}
        arrays: Dict[str, List[float]] = {}
        i = 0

        # ── 1. Metadata / Header ──────────────────────────────────────────────
        # Read key: value lines until the first scalar or array header line.
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
            # Stop when we reach the scalar/array variable section
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
        # Lines of the form "A:  123.45" or "I:  0"
        # Stop at the first bare array header ("A:" alone on its line).
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
            # blank lines between scalars are fine — skip silently
            i += 1

        # ── 3. Arrays ─────────────────────────────────────────────────────────
        current_var: Optional[str] = None
        current_data: List[float] = []

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
                # Strip the leading row index, e.g. "     0:  " or "  3195:  "
                # Row indices always have a colon; bare session counters do not.
                # Crucially: ONLY strip the pattern "digits-colon-spaces" — this
                # distinguishes "     0:  1234.0" (array row) from a session counter
                # or other stray line.
                clean = re.sub(r"^\d+:\s*", "", line)

                # If stripping left us with an empty string (row index line with
                # no data values), skip it.
                if not clean.strip():
                    i += 1
                    continue

                # Parse each whitespace-separated token as a float.
                # Filter val < 0: the only negative value in MedPC output is
                # the -987.987 end-of-data sentinel.  All real counts and
                # timestamps are non-negative.
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
