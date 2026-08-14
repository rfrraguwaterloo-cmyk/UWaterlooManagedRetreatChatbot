"""Helpers for attaching source-paper links to extracted case-study chunks."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
TRACKED_OVERRIDES = REPO_ROOT / "ingest" / "source_link_overrides.json"

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
_URL_RE = re.compile(r"https?://[^\s)>\]]+")
_KNOWN_BAD_DOIS = {
    "10.1016/j.ijdrr.2020.315193",
    "10.1016/j.ijdrr.2025.007988",
    "10.1080/17477891.2017.1316763",
}


def _find_case_folder(case_id: str) -> Path | None:
    for p in DATA_RAW.iterdir():
        if p.is_dir() and re.match(rf"^{re.escape(case_id)}($|-)", p.name):
            return p
    return None


def _clean_doi(raw: str) -> str:
    return raw.strip().rstrip(".,;:")


def _is_generic_title(title: str) -> bool:
    return (
        not title
        or title.startswith("DOI ")
        or title.startswith("Location:")
        or title.startswith("URL:")
        or title in {"Source", "Source URL"}
    )


def _title_from_source_line(line: str, doi: str | None = None) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"^(PRIMARY|SUPPLEMENTAL|GREY LITERATURE)\s*:\s*", "", line, flags=re.I)
    if doi:
        line = re.sub(rf"\bDOI:\s*{re.escape(doi)}\b.*$", "", line, flags=re.I).strip()
        line = line.rstrip(" .;-")
    line = re.sub(r"\s+(URL|Local source|Local PDF|Covers|Note):\s+.*$", "", line, flags=re.I)
    return line[:320]


def _dedupe_links(links: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    order: list[str] = []
    for link in links:
        doi = _clean_doi(link.get("doi", "")) if link.get("doi") else ""
        url = (link.get("url") or "").strip()
        pdf_url = (link.get("pdf_url") or "").strip()
        if doi and not url:
            url = f"https://doi.org/{doi}"
        key = (doi or url or pdf_url).lower()
        if not key:
            continue

        candidate = {
            "title": (link.get("title") or "Source").strip(),
            "doi": doi,
            "url": url,
            "pdf_url": pdf_url,
        }
        candidate = {k: v for k, v in candidate.items() if v}
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = candidate
            order.append(key)
            continue

        if _is_generic_title(existing.get("title", "")) and not _is_generic_title(candidate.get("title", "")):
            existing["title"] = candidate["title"]
        for field in ("doi", "url", "pdf_url"):
            if not existing.get(field) and candidate.get(field):
                existing[field] = candidate[field]

    return [by_key[key] for key in order]


def _load_override_links(case_id: str) -> list[dict]:
    links: list[dict] = []
    for overrides_path in (TRACKED_OVERRIDES, DATA_RAW / "source_link_overrides.json"):
        if not overrides_path.exists():
            continue
        try:
            overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        case_links = overrides.get(case_id, [])
        if isinstance(case_links, list):
            links.extend(
                link
                for link in case_links
                if (link.get("doi") or "").lower() not in _KNOWN_BAD_DOIS
            )
    return links


def _add_sources_txt(folder: Path, links: list[dict]) -> None:
    sources_txt = folder / "sources.txt"
    if not sources_txt.exists():
        return

    last_title = ""
    last_meaningful_title = ""
    for line in sources_txt.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_heading = bool(re.match(r"^(PRIMARY SOURCE|SUPPLEMENTAL SOURCES|GREY LITERATURE|NONE)\s*:?$", stripped, re.I))
        is_case_info = bool(re.match(r"^(Case ID|Location):", stripped, re.I))
        has_identifier = bool(_DOI_RE.search(stripped) or _URL_RE.search(stripped))

        if not is_heading and not is_case_info:
            title = _title_from_source_line(stripped)
            if title and not title.startswith(("Local source:", "Local PDF:", "Covers:", "Note:")):
                last_title = title
                if not has_identifier:
                    last_meaningful_title = title

        for doi in _DOI_RE.findall(stripped):
            doi = _clean_doi(doi)
            if doi.lower() in _KNOWN_BAD_DOIS:
                continue
            links.append({
                "title": _title_from_source_line(stripped, doi) or last_title or f"DOI {doi}",
                "doi": doi,
                "url": f"https://doi.org/{doi}",
            })

        for url in _URL_RE.findall(stripped):
            title = _title_from_source_line(stripped)
            if title.startswith(("URL:", "https://", "http://")) or is_case_info:
                title = last_meaningful_title or last_title
            links.append({
                "title": title or "Source URL",
                "url": url.rstrip(".,;"),
            })


def _add_sources_json(folder: Path, links: list[dict]) -> None:
    sources_json = folder / "sources.json"
    if not sources_json.exists():
        return
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
            "title": source.get("apa") or source.get("title") or source.get("seed_citation") or "Source",
            "doi": doi,
            "url": source.get("url") or (f"https://doi.org/{doi}" if doi else ""),
            "pdf_url": source.get("pdf_url") or "",
        })


def _add_dois_txt(folder: Path, links: list[dict]) -> None:
    dois_txt = folder / "dois.txt"
    if not dois_txt.exists():
        return
    for doi in _DOI_RE.findall(dois_txt.read_text(encoding="utf-8", errors="ignore")):
        doi = _clean_doi(doi)
        if doi.lower() in _KNOWN_BAD_DOIS:
            continue
        links.append({"title": f"DOI {doi}", "doi": doi, "url": f"https://doi.org/{doi}"})


def load_source_links(case_id: str) -> list[dict]:
    """Return article/DOI/PDF links known for a case study.

    The source catalog files live in data/raw and are not all shipped to the
    app, so ingestion embeds a compact copy of these links into data/extracted.
    """
    folder = _find_case_folder(case_id)
    if not folder:
        return []

    links: list[dict] = []
    links.extend(_load_override_links(case_id))
    _add_sources_txt(folder, links)
    _add_sources_json(folder, links)
    _add_dois_txt(folder, links)
    return _dedupe_links(links)
