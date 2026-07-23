"""Helpers for attaching source-paper links to extracted case-study chunks."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
_URL_RE = re.compile(r"https?://[^\s)>\]]+")


def _find_case_folder(case_id: str) -> Path | None:
    for p in DATA_RAW.iterdir():
        if p.is_dir() and re.match(rf"^{re.escape(case_id)}($|-)", p.name):
            return p
    return None


def _clean_doi(raw: str) -> str:
    return raw.strip().rstrip(".,;:")


def _title_from_source_line(line: str, doi: str | None = None) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"^(PRIMARY|SUPPLEMENTAL|GREY LITERATURE)\s*:\s*", "", line, flags=re.I)
    if doi:
        line = re.sub(rf"\bDOI:\s*{re.escape(doi)}\b.*$", "", line, flags=re.I).strip()
        line = line.rstrip(" .;-")
    return line[:320]


def _dedupe_links(links: list[dict]) -> list[dict]:
    seen: set[str] = set()
    output: list[dict] = []
    for link in links:
        doi = _clean_doi(link.get("doi", "")) if link.get("doi") else ""
        url = (link.get("url") or "").strip()
        pdf_url = (link.get("pdf_url") or "").strip()
        if doi and not url:
            url = f"https://doi.org/{doi}"
        key = (doi or url or pdf_url).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned = {
            "title": (link.get("title") or "Source").strip(),
            "doi": doi,
            "url": url,
            "pdf_url": pdf_url,
        }
        output.append({k: v for k, v in cleaned.items() if v})
    return output


def load_source_links(case_id: str) -> list[dict]:
    """Return article/DOI/PDF links known for a case study.

    The source catalog files live in data/raw and are not all shipped to the
    app, so ingestion embeds a compact copy of these links into data/extracted.
    """
    folder = _find_case_folder(case_id)
    if not folder:
        return []

    links: list[dict] = []

    sources_json = folder / "sources.json"
    if sources_json.exists():
        try:
            catalog = json.loads(sources_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            catalog = {}
        for source in catalog.get("sources", []):
            status = str(source.get("status", "")).lower()
            if "rejected" in status:
                continue
            doi = _clean_doi(str(source.get("doi", ""))) if source.get("doi") else ""
            links.append({
                "title": source.get("title") or source.get("seed_citation") or "Source",
                "doi": doi,
                "url": source.get("url") or (f"https://doi.org/{doi}" if doi else ""),
                "pdf_url": source.get("pdf_url") or "",
            })

    dois_txt = folder / "dois.txt"
    if dois_txt.exists():
        for doi in _DOI_RE.findall(dois_txt.read_text(encoding="utf-8", errors="ignore")):
            doi = _clean_doi(doi)
            links.append({"title": f"DOI {doi}", "doi": doi, "url": f"https://doi.org/{doi}"})

    sources_txt = folder / "sources.txt"
    if sources_txt.exists():
        last_title = ""
        for line in sources_txt.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            is_heading = bool(re.match(r"^(PRIMARY SOURCE|SUPPLEMENTAL SOURCES|GREY LITERATURE|NONE)\s*:?$", stripped, re.I))
            has_identifier = bool(_DOI_RE.search(stripped) or _URL_RE.search(stripped))
            if not is_heading and not has_identifier:
                last_title = _title_from_source_line(stripped)
            for doi in _DOI_RE.findall(stripped):
                doi = _clean_doi(doi)
                links.append({
                    "title": _title_from_source_line(stripped, doi) or f"DOI {doi}",
                    "doi": doi,
                    "url": f"https://doi.org/{doi}",
                })
            for url in _URL_RE.findall(stripped):
                links.append({
                    "title": last_title or _title_from_source_line(stripped) or "Source URL",
                    "url": url.rstrip(".,;"),
                })

    return _dedupe_links(links)
