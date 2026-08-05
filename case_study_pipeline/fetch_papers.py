#!/usr/bin/env python3
"""
fetch_papers.py — Download source PDFs for a case study using PyPaperBot.

Tries sources in order: Unpaywall (free, open-access) → Anna's Archive API
(if key provided) → SciDB scrape → Sci-Hub.

Downloaded PDFs are saved to data/raw/<CASE_ID>/ and uploaded to the
corresponding Google Drive folder (using drive_folders.json).

Usage:
    # Pass DOIs directly:
    python3 -m case_study_pipeline.fetch_papers \\
        --case-id CS13 \\
        --dois 10.1525/elementa.2021.00036 10.1007/s11069-021-04592-1

    # Or read from a dois.txt file (one DOI per line):
    python3 -m case_study_pipeline.fetch_papers --case-id CS13

    # Skip Drive upload:
    python3 -m case_study_pipeline.fetch_papers --case-id CS13 --no-upload

    # If automated sources fail, open UWaterloo EZproxy in Chrome and wait
    # while you complete WatIAM/Duo and download the PDF:
    python3 -m case_study_pipeline.fetch_papers --case-id CS38 --manual-ezproxy

Options:
    --scihub-mirror     Sci-Hub mirror URL (default: https://sci-hub.se)
    --aa-api-key        Anna's Archive API key (see annas-archive.se/faq#api)
    --no-upload         Skip Drive upload after download
    --manual-ezproxy    Open Chrome for browser-assisted UWaterloo access
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import shutil
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = REPO_ROOT / "data" / "raw" / "_inbox"

# Load .env so UWATERLOO_USER/PASS and GOOGLE credentials are available
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass
PIPELINE_DIR = Path(__file__).resolve().parent
DRIVE_FOLDERS_FILE = PIPELINE_DIR / "drive_folders.json"


def load_drive_folders() -> dict:
    if not DRIVE_FOLDERS_FILE.exists():
        return {}
    return json.loads(DRIVE_FOLDERS_FILE.read_text())


def get_dois_for_case(case_dir: Path, dois_arg: list[str] | None) -> list[str]:
    """Return DOIs from --dois arg, or from data/raw/CSX/dois.txt if it exists."""
    if dois_arg:
        return [d.strip() for d in dois_arg if d.strip()]
    dois_file = case_dir / "dois.txt"
    if dois_file.exists():
        lines = dois_file.read_text().splitlines()
        return [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    return []


def find_case_dir(case_id: str) -> Path | None:
    """Find data/raw/CSxx or data/raw/CSxx-Place_Name style folders."""
    exact = REPO_ROOT / "data" / "raw" / case_id
    if exact.exists():
        return exact

    raw_dir = REPO_ROOT / "data" / "raw"
    for path in raw_dir.iterdir():
        if path.is_dir() and re.match(rf"^{re.escape(case_id)}($|-)", path.name):
            return path
    return None


def fetch_and_download(
    dois: list[str],
    dest_dir: Path,
    scihub_mirror: str,
    aa_api_key: str | None,
) -> list[Path]:
    """
    Run PyPaperBot for each DOI. Downloads go into dest_dir.
    Returns list of PDF paths that were successfully downloaded.
    """
    try:
        from PyPaperBot.Crossref import getPapersInfoFromDOIs
        from PyPaperBot.Downloader import downloadPapers
    except ImportError:
        print(
            "ERROR: PyPaperBot not found. Install it with:\n"
            "  pip3 install bibtexparser crossref-commons undetected-chromedriver\n"
            "  pip3 install -e ~/PyPaperBot/PyPaperBot"
        )
        sys.exit(1)

    dest_dir.mkdir(parents=True, exist_ok=True)

    papers = []
    for doi in dois:
        print(f"\n  Fetching metadata for DOI: {doi}")
        paper = getPapersInfoFromDOIs(doi, restrict=None)
        papers.append(paper)

    before = set(dest_dir.glob("*.pdf"))

    dwn_dir = str(dest_dir) + "/"
    downloadPapers(
        papers,
        dwn_dir,
        num_limit=None,
        SciHub_URL=scihub_mirror,
        SciDB_URL=None,
        AnnasArchive_API_key=aa_api_key,
    )

    after = set(dest_dir.glob("*.pdf"))
    new_pdfs = sorted(after - before)
    return new_pdfs


def safe_pdf_filename(title: str, fallback: str = "downloaded_paper") -> str:
    """Return a filesystem-safe PDF name."""
    stem = re.sub(r"[^\w\-_. ]", "_", title).strip(" ._")
    return f"{stem or fallback}.pdf"


def display_path(path: Path) -> Path:
    """Prefer repo-relative paths in CLI output."""
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def resolve_doi_target_url(doi: str) -> tuple[str, str]:
    """Return a likely publisher PDF/article URL plus title for manual browser access."""
    try:
        import requests

        url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
        resp = requests.get(url, timeout=20, headers={"User-Agent": "rfr-rag-fetch-papers/0.1"})
        if resp.ok:
            msg = resp.json().get("message", {})
            title = (msg.get("title") or [""])[0]
            links = msg.get("link") or []
            for link in links:
                link_url = link.get("URL") or ""
                if "pdf" in link_url.lower():
                    return link_url, title
            if msg.get("URL"):
                return msg["URL"], title
    except Exception as exc:
        print(f"  [Browser] Crossref lookup failed for {doi}: {exc}")

    return f"https://doi.org/{doi}", doi


def to_ezproxy_url(url: str) -> str:
    from .ezproxy import to_ezproxy_url as convert

    return convert(url)


def open_in_chrome(url: str) -> None:
    """Open URL in Google Chrome, falling back to the default browser."""
    try:
        subprocess.run(["open", "-a", "Google Chrome", url], check=True)
    except Exception:
        webbrowser.open(url)


def file_browser_downloads(
    *,
    case_id: str,
    case_dir: Path,
    before_inbox: set[Path],
    dois: list[str],
    titles: dict[str, str],
    no_upload: bool,
) -> list[Path]:
    """Move newly downloaded inbox PDFs into the case folder and optionally upload them."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    after_inbox = set(INBOX_DIR.glob("*.pdf"))
    new_downloads = sorted(after_inbox - before_inbox)

    if not new_downloads:
        print("  [Browser] No new PDFs found in data/raw/_inbox/.")
        return []

    moved: list[Path] = []
    for src in new_downloads:
        if len(new_downloads) == 1 and len(dois) == 1:
            dest_name = safe_pdf_filename(titles.get(dois[0], ""), src.stem)
        else:
            dest_name = src.name

        dest = case_dir / dest_name
        n = 1
        while dest.exists():
            n += 1
            dest = case_dir / f"({n}){dest_name}"
        shutil.move(str(src), str(dest))
        moved.append(dest)
        print(f"  [Browser] Moved {src.name} -> {display_path(dest)}")

    if moved and not no_upload:
        folders = load_drive_folders()
        folder_id = folders.get(case_id)
        if not folder_id:
            print(f"  [Drive] No folder ID found for {case_id} in drive_folders.json — skipping upload.")
        else:
            from .drive_upload import make_uploader, try_upload

            uploader = make_uploader(folder_id=folder_id)
            if uploader:
                for pdf in moved:
                    print(f"  [Drive] Uploading {pdf.name}...")
                    try_upload(uploader, pdf)
            else:
                print("  [Drive] No uploader available — skipping upload.")
    elif no_upload:
        print("  [Drive] Upload skipped (--no-upload).")

    return moved


def browser_ezproxy_flow(case_id: str, case_dir: Path, dois: list[str], no_upload: bool) -> list[Path]:
    """Open failed DOI targets through UWaterloo EZproxy and wait for manual download."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    before_inbox = set(INBOX_DIR.glob("*.pdf"))
    titles: dict[str, str] = {}

    print("\n" + "=" * 60)
    print("  Browser-assisted UWaterloo EZproxy")
    print("  Chrome will open each DOI through EZproxy.")
    print("  Complete WatIAM/Duo if asked, then click Download PDF.")
    print(f"  Save location should be: {INBOX_DIR}")
    print("=" * 60 + "\n")

    for doi in dois:
        target_url, title = resolve_doi_target_url(doi)
        titles[doi] = title
        proxy_url = to_ezproxy_url(target_url)
        print(f"  DOI: {doi}")
        print(f"  Opening: {proxy_url}")
        open_in_chrome(proxy_url)

    input("\nPress Enter after Chrome has finished downloading the PDF(s) into data/raw/_inbox/...")

    return file_browser_downloads(
        case_id=case_id,
        case_dir=case_dir,
        before_inbox=before_inbox,
        dois=dois,
        titles=titles,
        no_upload=no_upload,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Download source PDFs for an RFR case study via PyPaperBot."
    )
    parser.add_argument("--case-id", required=True, help="e.g. CS13")
    parser.add_argument(
        "--dois", nargs="+", metavar="DOI",
        help="One or more DOIs to download. If omitted, reads data/raw/<CASE_ID>/dois.txt",
    )
    parser.add_argument(
        "--scihub-mirror", default="https://sci-hub.se",
        help="Sci-Hub mirror URL (default: https://sci-hub.se)",
    )
    parser.add_argument(
        "--aa-api-key", default=None,
        help="Anna's Archive API key for paywalled papers",
    )
    parser.add_argument(
        "--no-upload", action="store_true",
        help="Skip uploading downloaded PDFs to Google Drive",
    )
    parser.add_argument(
        "--manual-ezproxy",
        action="store_true",
        help="If automated download finds no PDFs, open UWaterloo EZproxy URLs in Chrome and wait for manual download",
    )
    args = parser.parse_args()

    case_id = args.case_id.upper()
    case_dir = find_case_dir(case_id)

    if case_dir is None:
        print(f"ERROR: Case directory not found for {case_id} under {REPO_ROOT / 'data' / 'raw'}")
        sys.exit(1)

    dois = get_dois_for_case(case_dir, args.dois)
    if not dois:
        print(
            f"ERROR: No DOIs provided. Either pass --dois or create:\n"
            f"  {case_dir / 'dois.txt'}  (one DOI per line)"
        )
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  fetch_papers — {case_id}")
    print(f"  DOIs to fetch: {len(dois)}")
    for d in dois:
        print(f"    {d}")
    print(f"  Destination: {case_dir}")
    print(f"{'='*60}\n")

    new_pdfs = fetch_and_download(
        dois=dois,
        dest_dir=case_dir,
        scihub_mirror=args.scihub_mirror,
        aa_api_key=args.aa_api_key,
    )

    print(f"\n{'='*60}")
    if new_pdfs:
        print(f"  Downloaded {len(new_pdfs)} PDF(s):")
        for p in new_pdfs:
            print(f"    {p.name}")
    else:
        print("  No new PDFs downloaded.")
    print(f"{'='*60}\n")

    if not new_pdfs and args.manual_ezproxy:
        browser_pdfs = browser_ezproxy_flow(
            case_id=case_id,
            case_dir=case_dir,
            dois=dois,
            no_upload=args.no_upload,
        )
        new_pdfs.extend(browser_pdfs)

    # Drive upload
    if new_pdfs and not args.no_upload and not args.manual_ezproxy:
        folders = load_drive_folders()
        folder_id = folders.get(case_id)
        if not folder_id:
            print(f"  [Drive] No folder ID found for {case_id} in drive_folders.json — skipping upload.")
        else:
            from .drive_upload import make_uploader, try_upload
            uploader = make_uploader(folder_id=folder_id)
            if uploader:
                for pdf in new_pdfs:
                    print(f"  [Drive] Uploading {pdf.name}...")
                    try_upload(uploader, pdf)
            else:
                print("  [Drive] No uploader available — skipping upload.")
    elif args.no_upload and not args.manual_ezproxy:
        print("  [Drive] Upload skipped (--no-upload).")

    print("\nDone.")


if __name__ == "__main__":
    main()
