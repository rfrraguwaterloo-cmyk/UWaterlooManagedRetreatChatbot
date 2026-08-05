#!/usr/bin/env python3
"""
sort_inbox.py — Move a Chrome-downloaded PDF from data/raw/_inbox/ into the
correct case study folder and upload it to the matching Drive folder.

This is the second half of the EZproxy-assisted download procedure (see
case_study_pipeline/README.md). After Claude drives Chrome to download a
paywalled paper through the UWaterloo proxy, the browser auto-saves it into
data/raw/_inbox/ (per the one-time Chrome download-location setting). This
script files it away.

Usage:
    python3 -m case_study_pipeline.sort_inbox \\
        --filename "s11069-021-04592-1.pdf" \\
        --case-id CS13 \\
        --rename "Pinter_Rees_2021_Natural_Hazards_FULLTEXT.pdf"

    # List what's currently sitting in the inbox, unsorted:
    python3 -m case_study_pipeline.sort_inbox --list

    # Skip the Drive upload:
    python3 -m case_study_pipeline.sort_inbox --filename "..." --case-id CS13 --no-upload
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = Path(__file__).resolve().parent
INBOX_DIR = REPO_ROOT / "data" / "raw" / "_inbox"
DRIVE_FOLDERS_FILE = PIPELINE_DIR / "drive_folders.json"

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from .fetch_papers import find_case_dir


def load_drive_folders() -> dict:
    if not DRIVE_FOLDERS_FILE.exists():
        return {}
    return json.loads(DRIVE_FOLDERS_FILE.read_text())


def main():
    parser = argparse.ArgumentParser(description="File a Chrome-downloaded PDF into its case study folder.")
    parser.add_argument("--filename", help="Exact filename currently sitting in data/raw/_inbox/")
    parser.add_argument("--case-id", help="e.g. CS13")
    parser.add_argument("--rename", default=None, help="Optional new filename (descriptive, e.g. author_year_FULLTEXT.pdf)")
    parser.add_argument("--no-upload", action="store_true", help="Skip Drive upload")
    parser.add_argument("--list", action="store_true", help="List files currently in the inbox and exit")
    args = parser.parse_args()

    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    if args.list:
        files = sorted(INBOX_DIR.glob("*"))
        if not files:
            print("Inbox is empty.")
        else:
            print("Files in data/raw/_inbox/:")
            for f in files:
                print(f"  {f.name}")
        return

    if not args.filename or not args.case_id:
        print("ERROR: --filename and --case-id are required (or use --list).")
        sys.exit(1)

    src = INBOX_DIR / args.filename
    if not src.exists():
        print(f"ERROR: {src} not found. Files currently in inbox:")
        for f in sorted(INBOX_DIR.glob("*")):
            print(f"  {f.name}")
        sys.exit(1)

    case_id = args.case_id.upper()
    dest_dir = find_case_dir(case_id)
    if not dest_dir:
        print(f"ERROR: case directory not found for {case_id} under {REPO_ROOT / 'data' / 'raw'}")
        sys.exit(1)

    dest_name = args.rename if args.rename else args.filename
    dest_path = dest_dir / dest_name

    n = 1
    while dest_path.exists():
        n += 1
        dest_path = dest_dir / f"({n}){dest_name}"

    shutil.move(str(src), str(dest_path))
    print(f"Moved: {src.name} -> {dest_path.relative_to(REPO_ROOT)}")

    if not args.no_upload:
        folders = load_drive_folders()
        folder_id = folders.get(case_id)
        if not folder_id:
            print(f"  [Drive] No folder ID for {case_id} in drive_folders.json — skipping upload.")
        else:
            from .drive_upload import make_uploader, try_upload
            uploader = make_uploader(folder_id=folder_id)
            if uploader:
                print(f"  [Drive] Uploading {dest_path.name}...")
                try_upload(uploader, dest_path)
            else:
                print("  [Drive] No uploader available — skipping upload.")
    else:
        print("  [Drive] Upload skipped (--no-upload).")


if __name__ == "__main__":
    main()
