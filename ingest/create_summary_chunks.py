"""
create_summary_chunks.py — Extract Case Study Overview sections as summary chunks.

Reads each CS*_Ver2.md, pulls the CASE STUDY OVERVIEW section (the rich intro block),
and writes data/extracted/case_summaries.json — one chunk per case study.

These chunks are indexed alongside the section-level chunks so summary/comparison
queries have a concise, self-contained chunk for every case study.

Usage:
    python3 ingest/create_summary_chunks.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
EXTRACTED_DIR = REPO_ROOT / "data" / "extracted"
OUT_FILE = EXTRACTED_DIR / "case_summaries.json"

# Match overview section — handles #, ##, and variations in heading text
_OVERVIEW_RE = re.compile(
    r"#{1,2}\s+CASE STUDY OVERVIEW\s*\n(.*?)(?=\n#{1,2}\s+(?:Is there|Date,|What is|Was this|Who or|Other notes|CODING|General Info)|\n---\n#{1,2}\s+Is there|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Fallback: grab everything before the first Q&A question
_PREAMBLE_RE = re.compile(
    r"^(.*?)(?=\n#{1,3}\s+(?:Is there any evidence|Date,\s+Number|What is the occurrence|General Information|Case Identification|CODING QUESTIONS))",
    re.IGNORECASE | re.DOTALL,
)


def _find_case_folder(case_id: str) -> Path | None:
    for p in DATA_RAW.iterdir():
        if p.is_dir() and re.match(rf"^{re.escape(case_id)}($|-)", p.name):
            return p
    return None


def _load_case_meta(case_id: str) -> dict:
    folder = _find_case_folder(case_id)
    if folder:
        meta_path = folder / "case_meta.json"
        if meta_path.exists():
            return json.loads(meta_path.read_text())
    return {"case_id": case_id, "name": case_id, "location": "Unknown", "country": "Unknown"}


def _all_case_ids() -> list[str]:
    ids = []
    for p in DATA_RAW.iterdir():
        if p.is_dir():
            m = re.match(r"^(CS\d+)", p.name)
            if m:
                ids.append(m.group(1))
    return sorted(set(ids), key=lambda x: int(x[2:]))


def build_summary_chunks() -> list[dict]:
    chunks = []
    for case_id in _all_case_ids():
        folder = _find_case_folder(case_id)
        if not folder:
            continue
        ver2_path = folder / "pipeline_output" / f"{case_id}_Ver2.md"
        if not ver2_path.exists():
            continue

        text = ver2_path.read_text(encoding="utf-8")
        m = _OVERVIEW_RE.search(text)
        if m:
            overview_text = m.group(1).strip()
        else:
            # Fallback: grab preamble before Q&A questions
            m2 = _PREAMBLE_RE.match(text)
            overview_text = m2.group(1).strip() if m2 else ""

        if not overview_text:
            print(f"  [{case_id}] No CASE STUDY OVERVIEW section found — skipping.")
            continue
        if len(overview_text) < 100:
            print(f"  [{case_id}] Overview too short — skipping.")
            continue

        meta = _load_case_meta(case_id)
        full_text = (
            f"Case study: {meta.get('name', case_id)} "
            f"({meta.get('location', '')}, {meta.get('country', '')})\n"
            f"Section: Case Study Overview (Summary)\n\n"
            f"{overview_text}"
        )

        chunks.append({
            "case_id": case_id,
            "chunk_index": 999,
            "section": "overview_summary",
            "location": meta.get("location", ""),
            "country": meta.get("country", ""),
            "source": f"Pipeline Ver2 — {meta.get('name', case_id)}",
            "text": full_text,
        })
        print(f"  [{case_id}] Extracted overview ({len(overview_text)} chars)")

    return chunks


def main():
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    print("Extracting Case Study Overview sections...\n")
    chunks = build_summary_chunks()
    OUT_FILE.write_text(json.dumps(chunks, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(chunks)} summary chunks → {OUT_FILE.relative_to(REPO_ROOT)}")
    print("Next: python3 ingest/embed_and_index.py")


if __name__ == "__main__":
    main()
