"""
Shared helper for reading the score out of an audit report.

Prompt B (the independent-auditor prompt in prompts.py) is required to end
every report with a line in the exact format:

    FINAL GRADE: <number>/100

`extract_grade` pulls that number back out so the pipeline scripts can print
and compare grades across Check 1 / Check 2 runs.
"""

from __future__ import annotations

import re

GRADE_RE = re.compile(r"FINAL GRADE:\s*(\d{1,3})\s*/\s*100", re.IGNORECASE)


def extract_grade(report_text: str) -> str:
    """Return the FINAL GRADE value (e.g. "82") found in `report_text`, or "N/A" if absent."""
    match = GRADE_RE.search(report_text)
    return match.group(1) if match else "N/A"
