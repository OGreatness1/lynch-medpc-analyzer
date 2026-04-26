import re
import pandas as pd


def canonicalize_id(subject_id: str) -> str:
    """
    Normalizes Subject IDs to prevent 0/O confusion and whitespace issues.
    Handles None and NaN gracefully.
    """
    try:
        if subject_id is None or (isinstance(subject_id, float) and pd.isna(subject_id)):
            return ""
    except Exception:
        pass
    s = str(subject_id).strip().upper()
    if not s:
        return ""
    # Replace leading letter O with zero (common MedPC data-entry error)
    return re.sub(r"^O(?=\d)", "0", s)


def extract_gender(subject_id: str) -> str:
    """Infers gender from the last letter of the subject ID."""
    if not subject_id:
        return "Unknown"
    last = str(subject_id).strip().lower()[-1]
    return "Female" if last == "f" else "Male" if last == "m" else "Unknown"


def normalize_msn(msn: str) -> str:
    """
    Strips all non-alphanumeric characters and lowercases MSN strings
    for reliable pattern matching.
    This is the single canonical implementation — config.py imports from here.
    """
    if msn is None:
        return ""
    try:
        if isinstance(msn, float) and pd.isna(msn):
            return ""
    except Exception:
        pass
    return re.sub(r"[^\w]", "", str(msn)).lower()
