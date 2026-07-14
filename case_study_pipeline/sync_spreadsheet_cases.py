"""
sync_spreadsheet_cases.py — Create Drive folders and local case study dirs for
entries in the Ajibade et al. 2022 spreadsheet not already covered by CS1-CS20.

Reads the "Full data_Clean" sheet from:
  https://docs.google.com/spreadsheets/d/1PGvxXlBUP-DFTuaYKhO5xSesHnPGhMlM

Compares Village/City + Country against existing RFR - CS* folders in Drive.
Creates new CS## folders (Drive + local data/raw/ + case_meta.json) for
entries not yet covered.

Usage:
    python3 -m case_study_pipeline.sync_spreadsheet_cases           # dry-run
    python3 -m case_study_pipeline.sync_spreadsheet_cases --execute # create folders

Flags:
    --execute        Actually create folders (default is dry-run only)
    --start-cs NUM   Override starting CS number (default: next after highest existing)
    --skip-drive     Skip Drive folder creation, only create local dirs
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = Path(__file__).resolve().parent
DRIVE_FOLDERS_FILE = PIPELINE_DIR / "drive_folders.json"
DATA_RAW = REPO_ROOT / "data" / "raw"

SPREADSHEET_ID = "1PGvxXlBUP-DFTuaYKhO5xSesHnPGhMlM"
SHEET_GID = "1698438069"          # Full data_Clean tab
PARENT_FOLDER_ID = "1SEYkC05ICecWn6EleREn6GZaw2CKEWZZ"

# Rows where the city cell contains citation text rather than a place name
_JUNK_PATTERNS = [
    re.compile(r"^\s*pp\.\s*\d+"),
    re.compile(r"Environmental resettlement", re.I),
    re.compile(r"Village\s*/\s*City", re.I),   # header repeat
]

# ---------------------------------------------------------------------------
# Drive helpers (reuse existing auth)
# ---------------------------------------------------------------------------

def _get_service():
    from .onboard_case_study import get_drive_service
    matches = list(REPO_ROOT.glob("client_secret*.json"))
    if not matches:
        print("  [Drive] No client_secret*.json found — use --skip-drive to skip Drive creation.")
        return None
    token_file = Path.home() / ".rfr-drive-token.json"
    return get_drive_service(matches[0], token_file)


def _fetch_sheet_csv(service) -> str:
    """Download the Full data_Clean sheet as CSV using the Drive-authorized HTTP session."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        f"/export?format=csv&gid={SHEET_GID}"
    )
    http = service._http
    response, content = http.request(url)
    if response.status != 200:
        raise RuntimeError(f"Failed to fetch spreadsheet CSV: HTTP {response.status}")
    return content.decode("utf-8-sig")   # strip BOM if present


def _list_existing_cs_folders(service) -> dict[str, dict]:
    """Return {folder_title: {id, title}} for all RFR - CS* folders in the parent."""
    result = {}
    page_token = None
    while True:
        params = dict(
            q=f"'{PARENT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder'",
            fields="nextPageToken, files(id, name)",
            pageSize=100,
        )
        if page_token:
            params["pageToken"] = page_token
        resp = service.files().list(**params).execute()
        for f in resp.get("files", []):
            if re.match(r"RFR\s*-\s*CS\d+", f["name"], re.I):
                result[f["name"]] = {"id": f["id"], "title": f["name"]}
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return result


def _create_drive_folder(service, folder_name: str) -> str:
    meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [PARENT_FOLDER_ID],
    }
    f = service.files().create(body=meta, fields="id,name").execute()
    return f["id"]


# ---------------------------------------------------------------------------
# Spreadsheet parsing
# ---------------------------------------------------------------------------

def _is_junk(city: str) -> bool:
    if not city or city.strip() in ("", "N/A", "Village/ City"):
        return True
    return any(p.search(city) for p in _JUNK_PATTERNS)


def _parse_sheet(csv_text: str) -> list[dict]:
    """Return list of {city, province, country} dicts from the sheet."""
    reader = csv.reader(io.StringIO(csv_text))
    headers = None
    rows = []
    for raw in reader:
        if headers is None:
            headers = [h.strip().lower() for h in raw]
            continue
        if len(raw) < 3:
            continue
        city_idx     = next((i for i, h in enumerate(headers) if "village" in h or "city" in h), None)
        province_idx = next((i for i, h in enumerate(headers) if "province" in h or "state" in h), None)
        country_idx  = next((i for i, h in enumerate(headers) if "country" in h), None)
        if city_idx is None or country_idx is None:
            continue
        city     = re.sub(r'\s+', ' ', raw[city_idx]).strip()    if city_idx < len(raw) else ""
        province = re.sub(r'\s+', ' ', raw[province_idx]).strip() if province_idx is not None and province_idx < len(raw) else ""
        country  = re.sub(r'\s+', ' ', raw[country_idx]).strip() if country_idx < len(raw) else ""
        if not country:
            continue
        rows.append({"city": city, "province": province, "country": country})
    return rows


def _deduplicate(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        key = (r["city"].lower(), r["country"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Matching against existing CS folders
# ---------------------------------------------------------------------------

def _normalise(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Normalise country name variants
    s = s.replace("united states", "us").replace("united kingdom", "uk").replace("england", "uk")
    return s


def _already_covered(row: dict, existing_titles: list[str]) -> bool:
    """Return True if this city+country is already represented in a CS folder title."""
    city    = _normalise(row["city"])
    country = _normalise(row["country"])
    for title in existing_titles:
        t = _normalise(title)
        city_words = [w for w in city.split() if len(w) > 2]
        if city_words and country and all(w in t for w in city_words) and country[:4] in t:
            return True
    return False


# ---------------------------------------------------------------------------
# Folder/dir creation helpers
# ---------------------------------------------------------------------------

def _next_cs_number(existing_titles: list[str], override: int | None) -> int:
    if override:
        return override
    nums = []
    for t in existing_titles:
        m = re.search(r"CS(\d+)", t, re.I)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=20) + 1


def _make_folder_name(cs_num: int, city: str, province: str, country: str) -> str:
    """RFR - CS## City, Province, Country"""
    parts = [p for p in [city if city != "N/A" else "", province, country] if p]
    location = ", ".join(parts)
    return f"RFR - CS{cs_num} {location}"


def _load_drive_folders() -> dict:
    if DRIVE_FOLDERS_FILE.exists():
        return json.loads(DRIVE_FOLDERS_FILE.read_text())
    return {"_comment": "Maps case study IDs to Google Drive folder IDs.",
            "_parent_folder_id": PARENT_FOLDER_ID}


def _save_drive_folders(data: dict) -> None:
    DRIVE_FOLDERS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def _create_local_dirs(cs_id: str, city: str, province: str, country: str) -> None:
    case_dir = DATA_RAW / cs_id
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "pipeline_output").mkdir(exist_ok=True)
    meta_path = case_dir / "case_meta.json"
    if not meta_path.exists():
        location = f"{city}, {province}" if province and province != "N/A" else city
        meta_path.write_text(json.dumps({
            "case_id": cs_id,
            "name": city if city != "N/A" else location,
            "location": location,
            "country": country,
        }, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Create Drive + local dirs for spreadsheet case studies not yet in CS1-CS20."
    )
    parser.add_argument("--execute", action="store_true",
                        help="Actually create folders (default: dry-run only)")
    parser.add_argument("--start-cs", type=int, default=None, metavar="NUM",
                        help="Override starting CS number")
    parser.add_argument("--skip-drive", action="store_true",
                        help="Skip Drive folder creation, local dirs only")
    parser.add_argument("--csv", metavar="PATH",
                        help="Path to a locally-downloaded CSV of the Full data_Clean sheet "
                             "(fallback if Drive auth is broken). "
                             "In Google Sheets: File → Download → CSV.")
    args = parser.parse_args(argv)

    dry_run = not args.execute
    if dry_run:
        print("DRY RUN — pass --execute to actually create folders.\n")

    # --- Auth & data --------------------------------------------------------
    service = None
    if not args.skip_drive:
        service = _get_service()
        if service is None:
            print("Could not get Drive service. Use --skip-drive to create local dirs only.")
            sys.exit(1)

    print("Fetching spreadsheet data...")
    if args.csv:
        csv_text = Path(args.csv).read_text(encoding="utf-8-sig")
        print(f"  Using local CSV: {args.csv}")
    elif service:
        csv_text = _fetch_sheet_csv(service)
    else:
        print("  No CSV source available. Pass --csv <path> or fix Drive auth.")
        sys.exit(1)

    rows = _parse_sheet(csv_text)
    rows = [r for r in rows if not _is_junk(r["city"])]
    rows = _deduplicate(rows)
    print(f"  {len(rows)} unique location rows after filtering.\n")

    print("Fetching existing CS folders from Drive...")
    existing = _list_existing_cs_folders(service) if service else {}
    existing_titles = list(existing.keys())
    print(f"  {len(existing_titles)} existing CS folders found.\n")

    # --- Compare & plan -----------------------------------------------------
    to_create = []
    covered = []
    for row in rows:
        if _already_covered(row, existing_titles):
            covered.append(row)
        else:
            to_create.append(row)

    print(f"Already covered by existing folders: {len(covered)}")
    print(f"New folders to create:               {len(to_create)}\n")

    if not to_create:
        print("Nothing to do — all spreadsheet entries are already covered.")
        return

    next_cs = _next_cs_number(existing_titles, args.start_cs)
    drive_data = _load_drive_folders()

    print(f"{'CS ID':<8} {'Drive folder name':<65} {'Status'}")
    print("-" * 90)

    for i, row in enumerate(to_create):
        cs_num  = next_cs + i
        cs_id   = f"CS{cs_num}"
        folder_name = _make_folder_name(cs_num, row["city"], row["province"], row["country"])

        if dry_run:
            print(f"{cs_id:<8} {folder_name:<65} [dry-run]")
            continue

        # Create Drive folder
        folder_id = ""
        if service and not args.skip_drive:
            try:
                folder_id = _create_drive_folder(service, folder_name)
                drive_data[cs_id] = folder_id
                status = f"Drive ✓ ({folder_id[:20]}...)"
            except Exception as e:
                status = f"Drive FAILED: {e}"
        else:
            status = "Drive skipped"

        # Create local dirs
        _create_local_dirs(cs_id, row["city"], row["province"], row["country"])
        status += " | Local ✓"

        print(f"{cs_id:<8} {folder_name:<65} {status}")

    if not dry_run:
        _save_drive_folders(drive_data)
        print(f"\ndrive_folders.json updated ({len(drive_data) - 2} entries).")
        print(f"Local dirs created under data/raw/.")
        print(f"\nNext steps:")
        print(f"  Download papers:  bash download_all_papers.sh")
        print(f"  Run pipeline:     python3 -m case_study_pipeline.run_case_study --case-folder data/raw/CS<NN>")
    else:
        print(f"\nRun with --execute to create {len(to_create)} folders.")


if __name__ == "__main__":
    main()
