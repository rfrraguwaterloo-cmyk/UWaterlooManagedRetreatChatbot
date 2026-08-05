#!/usr/bin/env python3
"""
Acquire source evidence for a case study without manual browser downloads.

The extraction pipeline can read PDFs, .txt, and .md files. This command
therefore prefers PDFs, but falls back to provenance-labelled markdown captures
when a publisher blocks automated PDF access.

Usage:
    python3 -m case_study_pipeline.acquire_sources --case-id CS39
    python3 -m case_study_pipeline.acquire_sources --case-id CS38 \
        --extra-url https://www.academia.edu/37237146/Heritage_and_Postdisaster_Recovery_Indigenous_Community_Resilience
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

from .fetch_papers import find_case_dir, get_dois_for_case

REPO_ROOT = Path(__file__).resolve().parent.parent
URL_RE = re.compile(r"https?://[^\s;,)]+", re.I)

HEADERS = {
    "User-Agent": "rfr-rag-source-acquirer/0.1 (mailto:a74zhou@uwaterloo.ca)",
    "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
}


@dataclass
class Candidate:
    doi: str = ""
    title: str = ""
    url: str = ""
    pdf_url: str = ""
    source: str = ""


def _slug(value: str, fallback: str = "source") -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return (value[:90] or fallback).strip("_")


def _normalize_doi(doi: str) -> str:
    return doi.strip().rstrip(".,);]").lower()


def _safe_get(url: str, timeout: int = 30) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return resp
    except requests.RequestException as exc:
        print(f"    GET failed: {url} ({exc})")
        return None


def _is_pdf_response(resp: requests.Response) -> bool:
    content_type = resp.headers.get("content-type", "").lower()
    return "application/pdf" in content_type or resp.content.startswith(b"%PDF")


def _download_pdf(url: str, dest: Path, force: bool = False) -> Path | None:
    if dest.exists() and not force:
        print(f"    PDF exists: {dest.name}")
        return dest
    resp = _safe_get(url)
    if not resp or not resp.ok:
        return None
    if not _is_pdf_response(resp):
        print(f"    Not a PDF: {url} ({resp.headers.get('content-type', 'unknown')})")
        return None
    dest.write_bytes(resp.content)
    print(f"    Saved PDF: {dest.name} ({dest.stat().st_size:,} bytes)")
    return dest


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "footer"]):
        tag.decompose()
    lines: list[str] = []
    last = None
    for raw in soup.get_text("\n").splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line and line != last:
            lines.append(line)
            last = line
    return "\n".join(lines)


def _capture_markdown(url: str, dest: Path, title: str, doi: str = "", force: bool = False) -> Path | None:
    if dest.exists() and not force:
        print(f"    Markdown exists: {dest.name}")
        return dest

    resp = _safe_get(url)
    body = ""
    capture_url = url
    if resp and resp.ok and "text/html" in resp.headers.get("content-type", "").lower():
        body = _html_to_text(resp.text)

    # Some sites block direct scripted capture but are readable through Jina's
    # text mirror. This is not a paywall bypass; it is a text rendering proxy for
    # publicly reachable pages.
    if len(body) < 2_000:
        jina_url = "https://r.jina.ai/http://r.jina.ai/http://" + url
        jina = _safe_get(jina_url)
        if jina and jina.ok and len(jina.text) > len(body):
            body = jina.text
            capture_url = jina_url

    if len(body) < 1_000:
        print(f"    Markdown capture too thin ({len(body)} chars): {url}")
        return None

    header = (
        f"# {title or url}\n\n"
        f"Source URL: {url}\n"
        f"Capture URL: {capture_url}\n"
        f"DOI: {doi}\n"
        f"Captured: {datetime.now(timezone.utc).isoformat()}\n"
        f"Reliability note: Automated source capture; prefer publisher PDF when available.\n\n"
    )
    dest.write_text(header + body + "\n", encoding="utf-8")
    print(f"    Saved markdown: {dest.name} ({len(body):,} chars)")
    return dest


def _request_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        resp = requests.get(url, params=params or {}, headers=HEADERS, timeout=25)
        if not resp.ok:
            return None
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def _crossref_candidate(doi: str) -> Candidate:
    data = _request_json(f"https://api.crossref.org/works/{quote(doi, safe='')}")
    if not data:
        return Candidate(doi=doi, url=f"https://doi.org/{doi}", source="doi")
    msg = data.get("message", {})
    title = (msg.get("title") or [""])[0]
    links = msg.get("link") or []
    pdf_url = ""
    for link in links:
        if "pdf" in (link.get("content-type") or "").lower():
            pdf_url = link.get("URL") or ""
            break
    return Candidate(
        doi=doi,
        title=title,
        url=msg.get("URL") or f"https://doi.org/{doi}",
        pdf_url=pdf_url,
        source="crossref",
    )


def _unpaywall_pdf(doi: str, email: str = "a74zhou@uwaterloo.ca") -> str:
    data = _request_json(f"https://api.unpaywall.org/v2/{doi}", {"email": email})
    if not data:
        return ""
    best = data.get("best_oa_location") or {}
    return best.get("url_for_pdf") or best.get("url") or ""


def _openalex_pdf(doi: str) -> str:
    data = _request_json("https://api.openalex.org/works", {"filter": f"doi:{doi}"})
    if not data or not data.get("results"):
        return ""
    loc = (data["results"][0].get("best_oa_location") or {})
    return loc.get("pdf_url") or loc.get("landing_page_url") or ""


def _semantic_scholar_pdf(doi: str) -> str:
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}"
    data = _request_json(url, {"fields": "title,openAccessPdf,url"})
    if not data:
        return ""
    oa = data.get("openAccessPdf") or {}
    return oa.get("url") or ""


def _publisher_pdf_patterns(doi: str, landing_url: str) -> list[str]:
    parsed = urlparse(landing_url)
    urls = []
    if "springer" in parsed.netloc:
        urls.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
    if "mdpi.com" in parsed.netloc:
        urls.append(landing_url.rstrip("/") + "/pdf")
    return urls


def _load_candidates(case_dir: Path, cli_dois: list[str] | None, extra_urls: list[str]) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()

    def add(candidate: Candidate) -> None:
        key = candidate.doi or candidate.url or candidate.pdf_url or candidate.title
        key = key.lower()
        if key and key not in seen:
            seen.add(key)
            candidates.append(candidate)

    for doi in get_dois_for_case(case_dir, cli_dois):
        add(_crossref_candidate(_normalize_doi(doi)))

    sources_json = case_dir / "sources.json"
    if sources_json.exists():
        data = json.loads(sources_json.read_text(encoding="utf-8"))
        for src in data.get("sources", []):
            doi = _normalize_doi(src.get("doi", ""))
            add(Candidate(
                doi=doi,
                title=src.get("title", ""),
                url=src.get("url", "") or (f"https://doi.org/{doi}" if doi else ""),
                pdf_url=src.get("pdf_url", ""),
                source="sources.json",
            ))

    sources_txt = case_dir / "sources.txt"
    if sources_txt.exists():
        for url in URL_RE.findall(sources_txt.read_text(encoding="utf-8")):
            add(Candidate(url=url, title=Path(urlparse(url).path).stem or url, source="sources.txt"))

    for url in extra_urls:
        add(Candidate(url=url, title=Path(urlparse(url).path).stem or url, source="extra-url"))

    return candidates


def acquire_candidate(case_dir: Path, candidate: Candidate, force: bool = False) -> list[Path]:
    title = candidate.title or candidate.doi or candidate.url
    stem = _slug(title)
    print(f"\n  Source: {title}")
    if candidate.doi:
        print(f"    DOI: {candidate.doi}")

    outputs: list[Path] = []
    pdf_urls = [candidate.pdf_url]
    if candidate.doi:
        pdf_urls.extend([
            _unpaywall_pdf(candidate.doi),
            _semantic_scholar_pdf(candidate.doi),
            _openalex_pdf(candidate.doi),
        ])
        pdf_urls.extend(_publisher_pdf_patterns(candidate.doi, candidate.url))
    if candidate.url.lower().endswith(".pdf"):
        pdf_urls.append(candidate.url)

    seen_urls: set[str] = set()
    for pdf_url in [u for u in pdf_urls if u]:
        if pdf_url in seen_urls:
            continue
        seen_urls.add(pdf_url)
        out = _download_pdf(pdf_url, case_dir / f"{stem}.pdf", force=force)
        if out:
            outputs.append(out)
            return outputs

    # Fall back to text capture from DOI landing page or explicit source URL.
    capture_urls = [candidate.url]
    if candidate.doi:
        capture_urls.append(f"https://doi.org/{candidate.doi}")
    for url in [u for u in capture_urls if u]:
        out = _capture_markdown(url, case_dir / f"{stem}.md", title=title, doi=candidate.doi, force=force)
        if out:
            outputs.append(out)
            return outputs

    print("    Could not acquire source automatically.")
    return outputs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True, help="e.g. CS38")
    parser.add_argument("--dois", nargs="+", metavar="DOI")
    parser.add_argument("--extra-url", action="append", default=[], help="Additional article/report URL to capture")
    parser.add_argument("--force", action="store_true", help="Overwrite existing acquired files")
    args = parser.parse_args(argv)

    case_id = args.case_id.upper()
    case_dir = find_case_dir(case_id)
    if case_dir is None:
        raise SystemExit(f"Case directory not found for {case_id}")

    print(f"Acquiring sources for {case_id}: {case_dir}")
    candidates = _load_candidates(case_dir, args.dois, args.extra_url)
    print(f"Found {len(candidates)} candidate source(s).")

    acquired: list[Path] = []
    for candidate in candidates:
        acquired.extend(acquire_candidate(case_dir, candidate, force=args.force))

    report = {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acquired_files": [p.name for p in acquired],
        "candidate_count": len(candidates),
    }
    report_path = case_dir / "source_acquisition_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nAcquired {len(acquired)} file(s).")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
