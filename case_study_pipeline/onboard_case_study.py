"""
onboard_case_study.py — Set up a new RFR case study end-to-end.

What this script does:
  1. Creates the local data/raw/CS<NN>/ directory structure
  2. Creates a Google Drive folder "RFR - CS<NN> <Name>" under the RFR parent folder
  3. Saves the new folder ID to case_study_pipeline/drive_folders.json
  4. (Optional) Copies PDFs from an existing Drive folder you point it at into the
     new Drive folder, and downloads them into data/raw/CS<NN>/ too
  5. Prints the filled-in paper discovery prompt (ready to paste into Consensus)

Usage:
  python3 -m case_study_pipeline.onboard_case_study \\
      --cs-num 16 \\
      --name "Fairbourne, Wales" \\
      --country "UK" \\
      --hazard "coastal erosion and flooding" \\
      --stage "pre-retreat" \\
      --actors "Gwynedd Council"

If you've already collected some papers in a Drive folder somewhere (e.g. a
scratch folder from manual searching) and want them copied into the new case
study's Drive folder *and* downloaded locally in one step, add:

  python3 -m case_study_pipeline.onboard_case_study \\
      --cs-num 16 \\
      --name "Fairbourne, Wales" \\
      --country "UK" \\
      --hazard "coastal erosion and flooding" \\
      --stage "pre-retreat" \\
      --source-drive-folder "https://drive.google.com/drive/folders/<existing-folder-id>"

(--source-drive-folder accepts either a full Drive folder URL or a bare folder ID.)

After running:
  - Drop any remaining source PDFs into data/raw/CS<NN>/
  - Run the pipeline:  python3 -m case_study_pipeline.run_case_study --case-folder data/raw/CS<NN>
  - Outputs auto-upload to the correct Drive folder (no extra flags needed)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = Path(__file__).resolve().parent
DRIVE_FOLDERS_FILE = PIPELINE_DIR / "drive_folders.json"
PAPER_DISCOVERY_PROMPT = PIPELINE_DIR / "context" / "paper_discovery_consensus_prompt.md"


# ---------------------------------------------------------------------------
# Drive folder creation
# ---------------------------------------------------------------------------

def get_drive_service(credentials_file: Path, token_file: Path):
    """Authenticate once and return a Drive v3 service object (full read/write scope)."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("  [Drive] Google API libraries not installed.")
        print("  Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
        return None

    SCOPES = ["https://www.googleapis.com/auth/drive"]

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


def create_drive_folder(service, folder_name: str, parent_folder_id: str) -> str:
    """Create a folder in Google Drive and return its ID."""
    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    folder = service.files().create(body=file_metadata, fields="id,name").execute()
    return folder.get("id", "")


def parse_drive_folder_id(value: str) -> str:
    """Accept either a bare Drive folder ID or a full Drive folder URL."""
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", value)
    if match:
        return match.group(1)
    return value.strip()


def copy_pdfs_from_drive_folder(
    service, source_folder_id: str, dest_folder_id: str, local_dest_dir: Path
) -> list[str]:
    """Copy every PDF in source_folder_id into dest_folder_id (a server-side Drive
    copy — file bytes never pass through this machine), and also download a local
    copy of each into local_dest_dir so the pipeline can read them. Skips files
    that already exist locally (by filename)."""
    from googleapiclient.http import MediaIoBaseDownload

    local_dest_dir.mkdir(parents=True, exist_ok=True)

    results = service.files().list(
        q=f"'{source_folder_id}' in parents and mimeType='application/pdf' and trashed=false",
        fields="files(id, name)",
        pageSize=100,
    ).execute()
    files = results.get("files", [])

    if not files:
        print(f"  No PDFs found in source folder {source_folder_id}.")
        return []

    copied = []
    for f in files:
        name = f["name"]
        if not name.endswith(".pdf"):
            name += ".pdf"

        print(f"  {name} ...", end="", flush=True)

        service.files().copy(
            fileId=f["id"],
            body={"parents": [dest_folder_id], "name": name},
        ).execute()
        print(" copied to Drive", end="", flush=True)

        dest_path = local_dest_dir / name
        if dest_path.exists():
            print(" [already local]")
        else:
            request = service.files().get_media(fileId=f["id"])
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            dest_path.write_bytes(buf.getvalue())
            print(f", saved locally ({len(buf.getvalue()):,} bytes)")

        copied.append(name)

    return copied


# ---------------------------------------------------------------------------
# drive_folders.json helpers
# ---------------------------------------------------------------------------

def load_drive_folders() -> dict:
    if DRIVE_FOLDERS_FILE.exists():
        return json.loads(DRIVE_FOLDERS_FILE.read_text())
    return {"_comment": "Maps case study IDs to Google Drive folder IDs.", "_parent_folder_id": ""}


def save_drive_folders(data: dict) -> None:
    DRIVE_FOLDERS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def get_folder_id(case_id: str) -> str | None:
    """Look up a Drive folder ID by case ID (e.g. 'CS12'). Returns None if not found."""
    data = load_drive_folders()
    return data.get(case_id)


# ---------------------------------------------------------------------------
# Paper discovery prompt filler
# ---------------------------------------------------------------------------

def fill_paper_discovery_prompt(cs_num: int, name: str, country: str, hazard: str, stage: str, actors: str) -> str:
    template = PAPER_DISCOVERY_PROMPT.read_text()

    # Replace the CASE PROFILE placeholders
    filled = template.replace("<NN>", str(cs_num))
    filled = filled.replace("<village / city / region>", name)
    filled = filled.replace("<country>, <state/province/district>", country)
    filled = filled.replace(
        "<e.g., riverine flooding / coastal erosion / drought–water scarcity / tidal inundation>",
        hazard,
    )
    filled = filled.replace(
        "<buyout / community resettlement / managed realignment | pre- / during / post->",
        stage,
    )
    filled = filled.replace("<NGO, agency, program>", actors or "unknown")

    # Fill BASE QUERY placeholders
    filled = filled.replace("<place name>", name)
    filled = filled.replace("<country>", country)
    filled = filled.replace("<primary hazard>", hazard)
    filled = filled.replace("<region/district>", country)
    filled = filled.replace("<hazard>", hazard)
    filled = filled.replace("<place>", name)

    return filled


# ---------------------------------------------------------------------------
# Local directory setup
# ---------------------------------------------------------------------------

def create_local_structure(cs_num: int) -> Path:
    case_dir = REPO_ROOT / "data" / "raw" / f"CS{cs_num}"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "pipeline_output").mkdir(exist_ok=True)
    return case_dir


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Onboard a new RFR case study: create Drive folder, local dirs, and paper discovery prompt."
    )
    parser.add_argument("--cs-num", required=True, type=int, help="Case study number, e.g. 16")
    parser.add_argument("--name", required=True, help="Place name, e.g. 'Fairbourne, Wales'")
    parser.add_argument("--country", required=True, help="Country (and region), e.g. 'UK, Wales'")
    parser.add_argument("--hazard", required=True, help="Primary hazard, e.g. 'coastal erosion and flooding'")
    parser.add_argument("--stage", default="unknown", help="MR stage: pre-retreat / during / post-retreat")
    parser.add_argument("--actors", default="", help="Known actors or program name (optional)")
    parser.add_argument(
        "--drive-credentials",
        help="Path to OAuth credentials JSON (defaults to client_secret_*.json in repo root)",
    )
    parser.add_argument(
        "--skip-drive",
        action="store_true",
        help="Skip Drive folder creation (local setup only)",
    )
    parser.add_argument(
        "--source-drive-folder",
        help=(
            "Drive folder ID or URL containing PDFs you've already collected. "
            "They are copied into the new case study's Drive folder and "
            "downloaded into data/raw/CS<NN>/ as well."
        ),
    )
    args = parser.parse_args()

    case_id = f"CS{args.cs_num}"
    folder_name = f"RFR - {case_id} {args.name}"

    print(f"\n{'='*60}")
    print(f"  Onboarding {case_id}: {args.name}")
    print(f"{'='*60}\n")

    # 1. Local directory
    case_dir = create_local_structure(args.cs_num)
    print(f"✓ Local directory: {case_dir}")
    print(f"  Drop source PDFs into: {case_dir}/")

    # 2. Drive folder
    drive_data = load_drive_folders()
    parent_folder_id = drive_data.get("_parent_folder_id", "")
    folder_id = drive_data.get(case_id)  # may already be registered from a prior run

    # We need an authenticated Drive service if we have to create the folder,
    # or if we need to copy PDFs in from a source folder.
    need_service = (not args.skip_drive and not folder_id) or bool(args.source_drive_folder)

    service = None
    if need_service:
        creds_path = None
        if args.drive_credentials:
            creds_path = Path(args.drive_credentials)
        else:
            matches = list(REPO_ROOT.glob("client_secret*.json"))
            if matches:
                creds_path = matches[0]

        if not creds_path or not creds_path.exists():
            print(f"\n⚠ Could not find OAuth credentials file. Pass --drive-credentials <path>.")
        else:
            token_file = Path.home() / ".rfr-drive-token.json"
            service = get_drive_service(creds_path, token_file)

    if args.skip_drive:
        print(f"\n⚠ Skipping Drive folder creation (--skip-drive). Add folder ID manually to drive_folders.json.")
    elif folder_id:
        print(f"\n✓ Drive folder already registered: {folder_id}")
    elif not parent_folder_id or parent_folder_id == "FILL_IN_RFR_PARENT_FOLDER_ID":
        print(f"\n⚠ Parent Drive folder ID not set in drive_folders.json (_parent_folder_id).")
        print(f"  Set it to the ID of the main RFR Drive folder, then re-run.")
        print(f"  (The ID is the last segment of the folder's URL.)")
    elif service:
        print(f"\nCreating Drive folder '{folder_name}'...")
        folder_id = create_drive_folder(service, folder_name, parent_folder_id)
        if folder_id:
            drive_data[case_id] = folder_id
            save_drive_folders(drive_data)
            print(f"✓ Drive folder created: https://drive.google.com/drive/folders/{folder_id}")
            print(f"✓ drive_folders.json updated")
        else:
            print(f"✗ Drive folder creation failed. Add the folder ID manually to drive_folders.json.")
    else:
        print(f"\n⚠ Could not create Drive folder (no credentials available).")

    # 2b. Copy PDFs in from an existing Drive folder, if one was given
    if args.source_drive_folder:
        if not service:
            print(f"\n⚠ --source-drive-folder given but no Drive credentials available — skipping copy.")
        elif not folder_id:
            print(f"\n⚠ --source-drive-folder given but the destination Drive folder isn't set up — skipping copy.")
        else:
            source_id = parse_drive_folder_id(args.source_drive_folder)
            local_dest = REPO_ROOT / "data" / "raw" / case_id
            print(f"\nCopying PDFs from source folder ({source_id}) into '{folder_name}'...")
            copied = copy_pdfs_from_drive_folder(service, source_id, folder_id, local_dest)
            print(f"✓ Copied {len(copied)} PDF(s) into the Drive folder and into {local_dest}/")

    # 3. Write case_meta.json so the ingestion bridge can tag RAG chunks
    import json as _json
    _meta_path = REPO_ROOT / "data" / "raw" / case_id / "case_meta.json"
    _meta_path.write_text(_json.dumps({
        "case_id": case_id,
        "name": args.name,
        "location": args.name,   # user can edit this later for a finer location string
        "country": args.country,
    }, indent=2))
    print(f"✓ case_meta.json written: {_meta_path}")

    # 4. Paper discovery prompt
    prompt_output = REPO_ROOT / "data" / "raw" / f"CS{args.cs_num}" / f"CS{args.cs_num}_paper_discovery_prompt.md"
    filled = fill_paper_discovery_prompt(
        args.cs_num, args.name, args.country, args.hazard, args.stage, args.actors
    )
    prompt_output.write_text(filled)
    print(f"\n✓ Paper discovery prompt saved: {prompt_output}")

    # 4. Print next steps
    print(f"\n{'='*60}")
    print(f"  NEXT STEPS for {case_id}")
    print(f"{'='*60}")
    print(f"1. Open {prompt_output.name} and run the queries in Consensus")
    print(f"2. Drop the source PDFs into:  data/raw/{case_id}/")
    print(f"3. Run the pipeline:")
    print(f"   python3 -m case_study_pipeline.run_case_study --case-folder data/raw/{case_id}")
    print(f"   (Outputs will auto-upload to the '{folder_name}' Drive folder)")
    print()


if __name__ == "__main__":
    main()
