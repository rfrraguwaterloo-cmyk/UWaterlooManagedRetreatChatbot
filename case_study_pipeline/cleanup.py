"""
cleanup.py — Remove local source PDFs and non-selected pipeline runs.

After you have:
  1. Run the pipeline (producing Ver1/Check1/Ver2/Check2 in run_XX/)
  2. Selected the best run with select_best_run.py
  3. Confirmed that Drive holds both the source PDFs and the pipeline outputs

...run this script to free up local disk space. It deletes:
  - Source PDFs (*.pdf directly inside data/raw/CSX/)
  - Non-selected run_XX/ subfolders in pipeline_output/
  - Leaves intact: selected.json, CSX_Ver2.md (canonical), and the winning run_XX/

The canonical CSX_Ver2.md is all that ingest_pipeline_outputs.py needs locally.
Source PDFs remain safely in Google Drive and can be re-downloaded any time.

Usage:
    python -m case_study_pipeline.cleanup --case-id CS1
    python -m case_study_pipeline.cleanup --case-id CS1 CS2 CS13
    python -m case_study_pipeline.cleanup --all
    python -m case_study_pipeline.cleanup --all --dry-run      # preview only
    python -m case_study_pipeline.cleanup --all --force        # skip confirmation
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"

_SOURCE_EXTENSIONS = {".pdf", ".txt", ".md"}
_RUN_DIR_RE = re.compile(r"^run_\d+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_case_ids() -> list[str]:
    return sorted(
        p.name for p in DATA_RAW.iterdir()
        if p.is_dir() and re.match(r"^CS\d+$", p.name)
    )


def _source_pdfs(case_dir: Path) -> list[Path]:
    """Top-level PDFs/txt/md in the case folder (not in subdirs)."""
    return [
        p for p in case_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _SOURCE_EXTENSIONS
    ]


def _non_selected_runs(pipeline_output: Path, selected_run: str | None) -> list[Path]:
    """run_XX dirs that are NOT the selected run."""
    return [
        p for p in pipeline_output.iterdir()
        if p.is_dir() and _RUN_DIR_RE.match(p.name) and p.name != selected_run
    ]


def _read_selected_run(pipeline_output: Path) -> str | None:
    selected_json = pipeline_output / "selected.json"
    if selected_json.exists():
        import json
        data = json.loads(selected_json.read_text())
        return data.get("selected_run")
    return None


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def cleanup_case(case_id: str, dry_run: bool = False, force: bool = False) -> None:
    case_dir = DATA_RAW / case_id
    if not case_dir.exists():
        print(f"  [{case_id}] Folder not found — skipping.")
        return

    pipeline_output = case_dir / "pipeline_output"
    selected_run = _read_selected_run(pipeline_output) if pipeline_output.exists() else None

    # Build deletion lists
    source_files = _source_pdfs(case_dir)
    stale_runs: list[Path] = []
    if pipeline_output.exists():
        stale_runs = _non_selected_runs(pipeline_output, selected_run)

    if not source_files and not stale_runs:
        print(f"  [{case_id}] Nothing to clean up.")
        return

    # Print preview
    print(f"\n  [{case_id}] {'DRY RUN — ' if dry_run else ''}Cleanup plan:")
    if source_files:
        total_mb = sum(f.stat().st_size for f in source_files) / 1_048_576
        print(f"    Source files to delete ({total_mb:.1f} MB total):")
        for f in source_files:
            size_kb = f.stat().st_size / 1024
            print(f"      {f.name}  ({size_kb:.0f} KB)")
    if stale_runs:
        print(f"    Stale run folders to delete:")
        for r in stale_runs:
            size_mb = sum(f.stat().st_size for f in r.rglob("*") if f.is_file()) / 1_048_576
            print(f"      {r.name}/  ({size_mb:.1f} MB)")
    if selected_run:
        print(f"    Keeping: pipeline_output/{selected_run}/  pipeline_output/selected.json  pipeline_output/{case_id}_Ver2.md")

    if dry_run:
        return

    # Confirm unless --force
    if not force:
        if not source_files and not stale_runs:
            return
        print()
        # Check for canonical Ver2 before allowing source deletion
        canonical = pipeline_output / f"{case_id}_Ver2.md" if pipeline_output.exists() else None
        if source_files and (canonical is None or not canonical.exists()):
            print(f"  WARNING: {case_id}_Ver2.md not found in pipeline_output/.")
            print(f"  Run select_best_run.py first, or the source PDFs will be unrecoverable locally.")
            ans = input("  Delete source PDFs anyway? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("  Skipped source deletion.")
                source_files = []

        if source_files or stale_runs:
            ans = input(f"  Proceed with cleanup for {case_id}? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print(f"  Skipped {case_id}.")
                return

    # Delete source files
    for f in source_files:
        f.unlink()
        print(f"    Deleted {f.name}")

    # Delete stale run dirs
    for run_dir in stale_runs:
        shutil.rmtree(run_dir)
        print(f"    Deleted {run_dir.name}/")

    print(f"  [{case_id}] Cleanup complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Delete local source PDFs and non-selected pipeline runs to free disk space."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case-id", nargs="+", metavar="ID",
                       help="Case IDs to clean up, e.g. CS1 CS2")
    group.add_argument("--all", action="store_true",
                       help="Clean up every CSX folder under data/raw/")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be deleted without deleting anything")
    parser.add_argument("--force", action="store_true",
                        help="Skip confirmation prompts")
    args = parser.parse_args(argv)

    case_ids = _all_case_ids() if args.all else args.case_id

    if args.dry_run:
        print("DRY RUN — nothing will be deleted.\n")

    for case_id in case_ids:
        cleanup_case(case_id, dry_run=args.dry_run, force=args.force)

    if not args.dry_run:
        print("\nDone. Source PDFs remain available in Google Drive.")
        print("Re-download any time with: python -m case_study_pipeline.download_drive_papers --case-id <ID>")


if __name__ == "__main__":
    main()
