"""
ingest_pipeline_outputs.py — Convert selected Ver2.md files into RAG JSON chunks.

Reads every data/raw/CSX/pipeline_output/CSX_Ver2.md (the canonical file written
by select_best_run.py), splits it into one chunk per questionnaire section, and
writes data/extracted/CSX.json in the format that embed_and_index.py expects.

Run this BEFORE embed_and_index.py whenever you add or update case studies.

Usage:
    python ingest/ingest_pipeline_outputs.py
    python ingest/ingest_pipeline_outputs.py --case-id CS1 CS12 CS13
    python ingest/ingest_pipeline_outputs.py --all          # default
    python ingest/ingest_pipeline_outputs.py --all --force  # overwrite existing JSON

The script is idempotent: re-running it for a case study overwrites its
data/extracted/CSX.json, so the embedding store can reflect the latest selected Ver2.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
EXTRACTED_DIR = REPO_ROOT / "data" / "extracted"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingest.source_links import load_source_links
from ingest.geo_metadata import geographic_metadata

# ---------------------------------------------------------------------------
# Section name → retrieval section key
# The keys match the field names used in CS1_IDJC.json so all chunks are
# queryable with the same metadata filters.
# ---------------------------------------------------------------------------
SECTION_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"case\s+study\s+overview", re.I),                    "overview"),
    # CS12-style: the intro block lives under "Case Study Questionnaire"
    (re.compile(r"case\s+study\s+questionnaire", re.I),               "overview"),
    (re.compile(r"general\s+information", re.I),                      "general_information"),
    (re.compile(r"institutional\s+environment", re.I),                "institutional_environment"),
    (re.compile(r"planning\s+processes", re.I),                       "planning_processes"),
    (re.compile(r"community\s+engagement", re.I),                     "community_engagement"),
    (re.compile(r"socio.cultural\s+considerations", re.I),            "socio_cultural_considerations"),
    (re.compile(r"cross.cutting\s+themes", re.I),                     "cross_cutting_themes"),
    (re.compile(r"additional\s+notes\s+and\s+lessons", re.I),         "additional_notes"),
    (re.compile(r"fields\s+with\s+limited\s+or\s+no\s+evidence", re.I), "evidence_gaps"),
]
SKIP_SECTION_PATTERNS = [
    re.compile(r"pre[-\s]*(flight|writing).*audit", re.I),
]

# Split ONLY on ## section headings, not ### question headings.
# This gives one chunk per broad section (~9 chunks per case study), keeping
# all individual question answers together in their section body.
_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_case_meta(case_id: str) -> dict:
    case_folder = _find_case_folder(case_id)
    if case_folder:
        meta_path = case_folder / "case_meta.json"
        if meta_path.exists():
            return json.loads(meta_path.read_text())
    # Graceful fallback — ingestion still works, just with minimal metadata
    return {"case_id": case_id, "name": case_id, "location": "Unknown", "country": "Unknown"}


def _resolve_section_key(heading: str) -> str:
    for pattern, key in SECTION_MAP:
        if pattern.search(heading):
            return key
    # Unknown heading → slugify it
    return re.sub(r"\W+", "_", heading.strip().lower()).strip("_")


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Split markdown text at ## / ### headings.
    Returns a list of (heading, body_text) pairs.
    The preamble before the first heading is discarded (usually just the title).
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [("document", text.strip())]

    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((heading, body))

    return sections


MIN_BODY_CHARS = 150  # Skip chunks with too little actual content


def _build_chunks(case_id: str, meta: dict, ver2_text: str) -> list[dict]:
    sections = _split_into_sections(ver2_text)
    source_links = load_source_links(case_id)
    geo = geographic_metadata(meta.get("location", ""), meta.get("country", ""))
    chunks = []
    idx = 0
    for heading, body in sections:
        if any(pattern.search(heading) for pattern in SKIP_SECTION_PATTERNS):
            continue
        # Skip near-empty sections (just a title with no real content)
        if len(body.strip()) < MIN_BODY_CHARS:
            continue
        section_key = _resolve_section_key(heading)
        # Prefix the body with case info so every chunk is self-contained
        full_text = (
            f"Case study: {meta.get('name', case_id)} "
            f"({meta.get('location', '')}, {meta.get('country', '')})\n"
            f"Section: {heading}\n\n"
            f"{body}"
        )
        chunks.append({
            "case_id": case_id,
            "chunk_index": idx,
            "section": section_key,
            "location": meta.get("location", ""),
            "country": meta.get("country", ""),
            **geo,
            "source": f"Pipeline Ver2 — {meta.get('name', case_id)}",
            "source_links": source_links,
            "text": full_text,
        })
        idx += 1
    return chunks


def _all_case_ids() -> list[str]:
    """Return sorted list of case IDs (e.g. 'CS1', 'CS24') from folder names like CS24-Queens_NY_USA."""
    ids = []
    for p in DATA_RAW.iterdir():
        if p.is_dir():
            m = re.match(r"^(CS\d+)", p.name)
            if m:
                ids.append(m.group(1))
    return sorted(set(ids), key=lambda x: int(x[2:]))


def _find_case_folder(case_id: str) -> Path | None:
    """Find the data/raw folder for a case ID, handles both CS24 and CS24-Queens_NY_USA styles."""
    for p in DATA_RAW.iterdir():
        if p.is_dir() and re.match(rf"^{re.escape(case_id)}($|-)", p.name):
            return p
    return None


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def ingest_case(case_id: str, force: bool = False) -> bool:
    case_folder = _find_case_folder(case_id)
    if case_folder is None:
        print(f"  [{case_id}] No folder found in data/raw/. Skipping.")
        return False

    ver2_path = case_folder / "pipeline_output" / f"{case_id}_Ver2.md"
    if not ver2_path.exists():
        print(f"  [{case_id}] No canonical Ver2.md found — run select_best_run.py first. Skipping.")
        return False

    out_path = EXTRACTED_DIR / f"{case_id}.json"
    if out_path.exists() and not force:
        # Check if Ver2 is newer than the existing JSON
        if ver2_path.stat().st_mtime <= out_path.stat().st_mtime:
            print(f"  [{case_id}] {out_path.name} is up-to-date — skipping. (Use --force to overwrite.)")
            return False

    meta = _load_case_meta(case_id)
    ver2_text = ver2_path.read_text(encoding="utf-8")
    chunks = _build_chunks(case_id, meta, ver2_text)

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(chunks, indent=2, ensure_ascii=False))

    print(f"  [{case_id}] Wrote {len(chunks)} chunks → {out_path.relative_to(REPO_ROOT)}")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Convert selected Ver2.md files into RAG JSON chunks."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--case-id", nargs="+", metavar="ID",
                       help="Specific case IDs to process, e.g. CS1 CS12")
    group.add_argument("--all", action="store_true", default=True,
                       help="Process all case studies with a canonical Ver2.md (default)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing JSON even if Ver2.md hasn't changed")
    args = parser.parse_args(argv)

    case_ids = args.case_id if args.case_id else _all_case_ids()

    print(f"Ingesting pipeline outputs for: {', '.join(case_ids)}\n")
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    updated = 0
    for case_id in case_ids:
        if ingest_case(case_id, force=args.force):
            updated += 1

    print(f"\nIngested {updated} case study/studies.")
    if updated:
        print("\nNext Run: python3 ingest/embed_and_index.py")


if __name__ == "__main__":
    main()
