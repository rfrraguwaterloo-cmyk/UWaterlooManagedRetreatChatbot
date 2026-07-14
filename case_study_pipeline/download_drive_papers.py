"""
download_drive_papers.py — Download source papers from a Drive folder to a local directory.

Usage:
  python3 -m case_study_pipeline.download_drive_papers --case-id CS13
  python3 -m case_study_pipeline.download_drive_papers --case-id CS14
  python3 -m case_study_pipeline.download_drive_papers --case-id CS13 CS14

Downloads all PDFs from the Drive folder for each case study into data/raw/<CS>/.
Skips files that already exist locally (by filename).
Uses the OAuth credentials already configured in .env / client_secret*.json.
"""

from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

# Pipeline-generated PDFs uploaded back to the Drive folder — skip these so
# they are not downloaded into data/raw/CSX/ and mistakenly treated as source
# documents by extract_source_documents().
_PIPELINE_OUTPUT_RE = re.compile(
    r"^CS\d+_(Ver\d+|Check\d+_report)\.pdf$", re.IGNORECASE
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = Path(__file__).resolve().parent
DRIVE_FOLDERS_FILE = PIPELINE_DIR / "drive_folders.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def build_service(credentials_file: Path, token_file: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def download_folder(service, folder_id: str, dest_dir: Path) -> list[str]:
    from googleapiclient.http import MediaIoBaseDownload

    folder_id = folder_id.strip()  # stray whitespace/newlines silently break the Drive query match
    dest_dir.mkdir(parents=True, exist_ok=True)
    results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
        fields="files(id, name)",
        pageSize=100,
    ).execute()

    files = results.get("files", [])
    downloaded = []
    skipped = []

    if not files:
        # Nothing matched the PDF filter. Don't fail silently -- check whether the
        # folder is genuinely empty for this account, or whether it has files that
        # just didn't match (wrong mimeType, trashed, etc.), which usually means
        # the authenticated Google account can't see what you expect it to see.
        raw = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType)",
            pageSize=100,
        ).execute().get("files", [])
        if not raw:
            print(
                "  No files at all are visible in this folder for the signed-in "
                "Google account. If you expected files here, the account that "
                "completed the OAuth login is probably not the one that owns/can "
                "see this folder -- delete ~/.rfr-drive-token.json and re-run to "
                "force a fresh login, then pick the right account."
            )
        else:
            print(f"  Folder has {len(raw)} file(s), but none matched mimeType='application/pdf':")
            for r in raw:
                print(f"    - {r['name']}  ({r['mimeType']})")
        return downloaded

    for f in files:
        name = f["name"]
        if not name.endswith(".pdf"):
            name += ".pdf"
        # Skip pipeline-generated outputs (Ver1, Ver2, Check reports) that were
        # uploaded back to the Drive folder — they must not land in data/raw/CSX/
        # where extract_source_documents() would pick them up as source material.
        if _PIPELINE_OUTPUT_RE.match(name):
            print(f"  Skipping pipeline output: {name}")
            continue
        dest = dest_dir / name
        if dest.exists():
            skipped.append(name)
            continue
        print(f"  Downloading: {name} ...", end="", flush=True)
        request = service.files().get_media(fileId=f["id"])
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        dest.write_bytes(buf.getvalue())
        print(f" {len(buf.getvalue()):,} bytes")
        downloaded.append(name)

    if skipped:
        print(f"  Skipped (already local): {', '.join(skipped)}")
    return downloaded


def main():
    parser = argparse.ArgumentParser(description="Download source PDFs from Drive to local case study folders.")
    parser.add_argument("--case-id", nargs="+", required=True, help="Case IDs to download, e.g. CS13 CS14")
    parser.add_argument("--drive-credentials", help="Path to OAuth credentials JSON (auto-detected if omitted)")
    args = parser.parse_args()

    # Find credentials
    creds_path = None
    if args.drive_credentials:
        creds_path = Path(args.drive_credentials)
    else:
        matches = list(REPO_ROOT.glob("client_secret*.json"))
        if matches:
            creds_path = matches[0]
    if not creds_path or not creds_path.exists():
        print("ERROR: Could not find OAuth credentials. Pass --drive-credentials <path>.")
        return

    token_file = Path.home() / ".rfr-drive-token.json"

    # Load folder map
    folder_map = json.loads(DRIVE_FOLDERS_FILE.read_text())

    print("Authenticating with Google Drive...")
    service = build_service(creds_path, token_file)
    try:
        about = service.about().get(fields="user").execute()
        print(f"  Signed in as: {about['user'].get('emailAddress', '?')}")
    except Exception as exc:
        print(f"  (Could not confirm signed-in account: {exc})")

    for case_id in args.case_id:
        folder_id = folder_map.get(case_id)
        if not folder_id:
            print(f"\n[{case_id}] No Drive folder ID in drive_folders.json — skipping.")
            continue
        dest_dir = REPO_ROOT / "data" / "raw" / case_id
        print(f"\n[{case_id}] Downloading from Drive folder {folder_id} -> {dest_dir}/")
        downloaded = download_folder(service, folder_id, dest_dir)
        print(f"  Done: {len(downloaded)} new file(s) downloaded.")


if __name__ == "__main__":
    main()
