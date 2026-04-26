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


class MedPCParser:
    def __init__(self):
        self.skipped_sessions: List[Tuple[str, str, str]] = []  # (filename, reason, snippet)

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

    def _extract_session_blocks(self, content: str) -> List[str]:
        """
        Split a multi-session MedPC file into individual session blocks.

        Primary delimiters: \\MPC header, 'Start Date:', or ===== lines.
        Fallback: a blank line immediately before a metadata key line,
        which handles older formats without explicit delimiters.
        """
        blocks = []
        current_lines = []
        lines = content.splitlines()

        METADATA_TRIGGERS = {"start date:", "subject:", "msn:", "experiment:"}

        for line in lines:
            stripped = line.strip()
            stripped_lower = stripped.lower()

            is_delimiter = (
                (stripped.startswith("\\") and "MPC" in stripped.upper())
                or stripped.startswith("Start Date:")
                or re.match(r"={5,}", stripped)
            )

            if is_delimiter:
                if current_lines:
                    block = "\n".join(current_lines).strip()
                    if len(block) > 150 and "Start Date:" in block:
                        blocks.append(block)
                current_lines = [line]
            else:
                # Fallback: blank line followed immediately by a metadata key
                if (
                    current_lines
                    and not current_lines[-1].strip()
                    and any(stripped_lower.startswith(t) for t in METADATA_TRIGGERS)
                    and "Start Date:" in "\n".join(current_lines)
                ):
                    block = "\n".join(current_lines).strip()
                    if len(block) > 150 and "Start Date:" in block:
                        blocks.append(block)
                    current_lines = [line]
                else:
                    current_lines.append(line)

        if current_lines:
            block = "\n".join(current_lines).strip()
            if len(block) > 150 and "Start Date:" in block:
                blocks.append(block)

        return blocks

    def _safe_float(self, s: str) -> Optional[float]:
        """
        Safely parse a string as float.
        Handles integers, decimals, and scientific notation (e.g. 1.5e+03).
        Returns None on failure — never raises.
        """
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    def _parse_single_session(self, block: str, filename: str) -> Optional["ParsedSession"]:
        lines = block.splitlines()
        meta = {}
        scalars = {}
        arrays = {}
        i = 0

        # ── 1. Metadata / Header ──────────────────────────────────────────────
        while i < len(lines) and not re.match(r"^[A-Z]:\s", lines[i].strip()):
            line = lines[i].strip()
            if ":" in line and not line.startswith("\\"):
                key_part, val_part = line.split(":", 1)
                key = key_part.strip()
                val = val_part.strip()
                known_keys = [
                    "Subject", "MSN", "Start Date", "End Date", "Box", "Room",
                    "Experiment", "Group", "Protocol", "File", "Comment"
                ]
                if key in known_keys or key.lower() in {"box", "room", "cage", "experiment", "group"}:
                    meta[key] = val
            i += 1

        # ── 2. Scalars ────────────────────────────────────────────────────────
        while i < len(lines):
            line = lines[i].strip()
            # Match lines like "A: 123.45" or "Z: 0"
            scalar_match = re.match(
                r"^([A-Z]):\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$", line
            )
            if scalar_match:
                var = scalar_match.group(1)
                val = self._safe_float(scalar_match.group(2))
                if val is not None:
                    scalars[var] = val
            elif re.match(r"^[A-Z]:$", line) or line.startswith("\\") or re.match(r"={5,}", line):
                break  # hit an array header or section separator
            elif not line:
                pass   # blank lines are fine between scalars
            i += 1

        # ── 3. Arrays ─────────────────────────────────────────────────────────
        current_var = None
        current_data = []

        while i < len(lines):
            line = lines[i].strip()

            # Array header: a single letter followed by colon on its own line
            m = re.match(r"^([A-Z]):$", line)
            if m:
                if current_var is not None and current_data:
                    arrays[current_var] = current_data
                current_var = m.group(1)
                current_data = []

            elif current_var is not None and line:
                # Strip leading row index (e.g. "     0:  " or "     5:  ")
                clean_line = re.sub(r"^\s*\d+:\s*", "", line)
                # Parse every whitespace-separated token as a float.
                # Filter out negative values — -987.987 is MedPC's end-of-data
                # sentinel written at the end of valid data in fixed-size arrays.
                # No legitimate timestamp or count in any Lynch Lab program is
                # negative, so filtering val < 0 safely removes the sentinel
                # and any other artefacts without discarding real data.
                for token in clean_line.split():
                    val = self._safe_float(token)
                    if val is not None and val >= 0:
                        current_data.append(val)

            i += 1

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
            raw_block=block[:600] + "..." if len(block) > 600 else block
        )

    def get_skipped_report(self) -> List[Dict]:
        return [{"File": f, "Reason": r, "Snippet": s} for f, r, s in self.skipped_sessions]
