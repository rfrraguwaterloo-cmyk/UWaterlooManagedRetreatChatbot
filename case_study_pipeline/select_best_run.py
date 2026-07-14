"""
select_best_run.py — Choose the highest-graded pipeline run for a case study.

For each case study, looks at all run_XX/ subdirectories in pipeline_output/,
reads the Check 2 (or Check 1) grade from each, selects the winner, copies its
Ver2.md to the canonical location (pipeline_output/CSX_Ver2.md), and writes
pipeline_output/selected.json.

The canonical Ver2.md is what ingest_pipeline_outputs.py reads into ChromaDB.

Usage:
    python -m case_study_pipeline.select_best_run --case-id CS1
    python -m case_study_pipeline.select_best_run --case-id CS1 CS2 CS13
    python -m case_study_pipeline.select_best_run --all
    python -m case_study_pipeline.select_best_run --all --force
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from .grading import extract_grade

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"

_RUN_DIR_RE = re.compile(r"^run_\d+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_case_ids() -> list[str]:
    return sorted(
        p.name for p in DATA_RAW.iterdir()
        if p.is_dir() and re.match(r"^CS\d+$", p.name)
    )


def _grade_run(run_dir: Path, case_id: str) -> int:
    """Return the numeric Check 2 grade for a run directory (0 if not found)."""
    check2 = next(run_dir.glob(f"{case_id}_Check2_report.md"), None)
    check1 = next(run_dir.glob(f"{case_id}_Check1_report.md"), None)
    report = check2 or check1
    if report:
        grade_str = extract_grade(report.read_text(encoding="utf-8"))
        try:
            return int(grade_str)
        except ValueError:
            return 0
    return 0


def _write_selected(
    pipeline_output: Path,
    case_id: str,
    run_name: str,
    grade: int | str,
    used_check: str,
) -> None:
    data = {
        "case_id": case_id,
        "selected_run": run_name,
        "check2_grade": grade,
        "grade_source": used_check,
        "canonical_ver2": f"{case_id}_Ver2.md",
    }
    out = pipeline_output / "selected.json"
    out.write_text(json.dumps(data, indent=2))
    print(f"    Wrote {out.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def select_for_case(case_id: str, force: bool = False) -> None:
    pipeline_output = DATA_RAW / case_id / "pipeline_output"

    if not pipeline_output.exists():
        print(f"  [{case_id}] No pipeline_output/ — skipping.")
        return

    # --- Case A: no run_XX subdirs at all (flat legacy layout) ----------
    run_dirs = sorted(
        p for p in pipeline_output.iterdir()
        if p.is_dir() and _RUN_DIR_RE.match(p.name)
    )

    if not run_dirs:
        flat_ver2 = pipeline_output / f"{case_id}_Ver2.md"
        if flat_ver2.exists():
            print(f"  [{case_id}] No run_XX/ dirs found; {flat_ver2.name} exists — marking as selected.")
            check2 = pipeline_output / f"{case_id}_Check2_report.md"
            check1 = pipeline_output / f"{case_id}_Check1_report.md"
            report = check2 if check2.exists() else (check1 if check1.exists() else None)
            grade = int(extract_grade(report.read_text(encoding="utf-8"))) if report else "N/A"
            _write_selected(pipeline_output, case_id, "direct", grade, "Check2" if check2.exists() else "Check1")
        else:
            print(f"  [{case_id}] No runs and no Ver2.md found — skipping.")
        return

    # --- Case B: scored run_XX subdirs exist ----------------------------
    scored: list[tuple[int, str, Path]] = []  # (grade, run_name, ver2_path)
    for run_dir in run_dirs:
        ver2 = next(run_dir.glob(f"{case_id}_Ver2.md"), None)
        if not ver2:
            continue
        grade = _grade_run(run_dir, case_id)
        scored.append((grade, run_dir.name, ver2))

    if not scored:
        print(f"  [{case_id}] Run dirs exist but no Ver2.md found in any — skipping.")
        return

    # Highest grade wins; later run name breaks ties (run_02 > run_01)
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    print(f"\n  [{case_id}] Run grades:")
    for grade, run_name, _ in sorted(scored, key=lambda x: x[1]):
        winner_marker = " ← selected" if run_name == scored[0][1] else ""
        print(f"    {run_name}: {grade}/100{winner_marker}")

    best_grade, best_run_name, best_ver2 = scored[0]

    # Copy to canonical location
    canonical = pipeline_output / f"{case_id}_Ver2.md"
    if canonical.exists() and not force:
        ans = input(f"\n  '{canonical.relative_to(REPO_ROOT)}' already exists. Overwrite? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print(f"  Skipped — keeping existing {canonical.name}.")
            return

    shutil.copy2(best_ver2, canonical)
    print(f"    Copied {best_run_name}/{best_ver2.name} → pipeline_output/{canonical.name}")

    # Determine whether we used Check1 or Check2 for the grade
    used = "Check2" if (pipeline_output / best_run_name / f"{case_id}_Check2_report.md").exists() else "Check1"
    _write_selected(pipeline_output, case_id, best_run_name, best_grade, used)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Select the highest-graded pipeline run for one or more case studies."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case-id", nargs="+", metavar="ID",
                       help="Case IDs to process, e.g. CS1 CS2 CS13")
    group.add_argument("--all", action="store_true",
                       help="Process every CSX folder under data/raw/")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing canonical Ver2.md without prompting")
    args = parser.parse_args(argv)

    case_ids = _all_case_ids() if args.all else args.case_id

    print(f"Selecting best run for: {', '.join(case_ids)}\n")
    for case_id in case_ids:
        select_for_case(case_id, force=args.force)

    print("\nDone. Run ingest/ingest_pipeline_outputs.py to push selected Ver2 files into ChromaDB.")


if __name__ == "__main__":
    main()
