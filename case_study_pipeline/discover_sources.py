#!/usr/bin/env python3
"""
High-precision paper discovery for one managed-retreat case study.

This command is intentionally conservative. It auto-records sources already
listed in the case folder (sources.txt / dois.txt) as seed sources, then searches
scholarly APIs for additional candidates and labels them with evidence. New
discoveries are not silently accepted as case evidence; they are written to a
review report for human approval.

Usage:
    python3 -m case_study_pipeline.discover_sources --case-id CS36
    python3 -m case_study_pipeline.discover_sources --case-id CS36 --max-results 8
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z.'-]*")

CASE_EVIDENCE_TERMS = (
    "buyout",
    "buy-out",
    "acquisition",
    "relocation",
    "resettlement",
    "retreat",
    "managed realignment",
    "floodplain",
    "hazard mitigation",
    "disaster recovery",
)

POLICY_TERMS = (
    "policy",
    "law",
    "legal",
    "program",
    "governance",
    "funding",
    "fema",
    "hud",
    "cdbg",
    "hm gp",
    "hazard mitigation grant",
    "national flood insurance",
)

STOPWORDS = {
    "the",
    "and",
    "of",
    "for",
    "in",
    "on",
    "at",
    "to",
    "from",
    "with",
    "a",
    "an",
    "city",
    "village",
    "district",
    "county",
    "province",
    "state",
    "region",
    "new",
    "north",
    "south",
    "east",
    "west",
}


@dataclass
class CaseIdentity:
    case_id: str
    name: str = ""
    location: str = ""
    country: str = ""
    aliases: list[str] = field(default_factory=list)

    @property
    def core_place_terms(self) -> list[str]:
        terms = []
        for value in [self.name, (self.location.split(",")[0] if self.location else "")]:
            for part in re.split(r"[,;/()]+", value or ""):
                part = re.sub(r"\s+", " ", part).strip()
                if len(part) >= 3 and part.lower() not in STOPWORDS:
                    terms.append(part)
        return _dedupe(terms)

    @property
    def alias_terms(self) -> list[str]:
        terms = []
        for value in self.aliases:
            for part in re.split(r"[,;/()]+", value or ""):
                part = re.sub(r"\s+", " ", part).strip()
                if len(part) >= 3 and part.lower() not in STOPWORDS:
                    terms.append(part)
        return _dedupe(terms)

    @property
    def admin_terms(self) -> list[str]:
        pieces = []
        location_parts = [p.strip() for p in re.split(r"[,;/()]+", self.location or "") if p.strip()]
        for part in location_parts[1:]:
            if len(part) >= 3:
                pieces.append(part)
        if self.country:
            pieces.append(self.country)
        return _dedupe(pieces)


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = _norm(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _norm(value: str) -> str:
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _title_key(title: str) -> str:
    words = [w for w in _norm(title).split() if len(w) > 2 and w not in STOPWORDS]
    return " ".join(words[:18])


def find_case_dir(case_id: str) -> Path | None:
    exact = DATA_RAW / case_id
    if exact.exists():
        return exact
    for path in DATA_RAW.iterdir():
        if path.is_dir() and re.match(rf"^{re.escape(case_id)}($|-)", path.name):
            return path
    return None


def load_case_identity(case_dir: Path, aliases: list[str]) -> CaseIdentity:
    meta_path = case_dir / "case_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing case_meta.json in {case_dir}")
    meta = json.loads(meta_path.read_text())
    return CaseIdentity(
        case_id=meta.get("case_id", case_dir.name.split("-")[0]),
        name=meta.get("name", ""),
        location=meta.get("location", ""),
        country=meta.get("country", ""),
        aliases=aliases,
    )


def parse_sources_txt(case_dir: Path) -> list[dict[str, Any]]:
    path = case_dir / "sources.txt"
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    primary = ""
    supplemental = ""
    if "PRIMARY SOURCE:" in text:
        after_primary = text.split("PRIMARY SOURCE:", 1)[1]
        if "SUPPLEMENTAL SOURCES:" in after_primary:
            primary, supplemental = after_primary.split("SUPPLEMENTAL SOURCES:", 1)
        else:
            primary = after_primary
    else:
        supplemental = text

    entries = []
    for role, block in (("primary_case_evidence", primary), ("secondary_case_evidence", supplemental)):
        for raw in _split_citation_block(block):
            doi = _extract_doi(raw)
            entries.append({
                "role": role,
                "status": "accepted_seed",
                "citation": raw,
                "doi": doi,
                "source": "sources.txt",
            })
    return entries


def parse_dois_txt(case_dir: Path) -> list[str]:
    path = case_dir / "dois.txt"
    if not path.exists():
        return []
    return [_extract_doi(line) for line in path.read_text().splitlines() if _extract_doi(line)]


def _split_citation_block(block: str) -> list[str]:
    block = re.sub(r"\bAND\b", "\n\n", block)
    chunks = [re.sub(r"\s+", " ", c).strip() for c in re.split(r"\n\s*\n", block)]
    return [c for c in chunks if len(c) > 20 and not c.lower().startswith(("journal page:", "local pdf:", "findable "))]


def _extract_doi(text: str) -> str:
    match = DOI_RE.search(text or "")
    if not match:
        return ""
    return match.group(0).rstrip(".,);]").lower()


def request_json(url: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    headers = {"User-Agent": "rfr-rag-paper-discovery/0.1 (mailto:a74zhou@uwaterloo.ca)"}
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def resolve_crossref_by_doi(doi: str) -> dict[str, Any] | None:
    if not doi:
        return None
    try:
        data = request_json(f"https://api.crossref.org/works/{doi}", {})
        item = data.get("message", {})
        return _crossref_item_to_candidate(item)
    except Exception:
        return None


def search_crossref(query: str, rows: int) -> list[dict[str, Any]]:
    try:
        data = request_json(
            "https://api.crossref.org/works",
            {"query.bibliographic": query, "rows": rows, "select": "DOI,title,author,issued,container-title,URL,abstract,type"},
        )
        return [_crossref_item_to_candidate(item) for item in data.get("message", {}).get("items", [])]
    except Exception:
        return []


def _crossref_item_to_candidate(item: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for author in item.get("author", [])[:8]:
        name = " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part)
        if name:
            authors.append(name)
    year = None
    parts = item.get("issued", {}).get("date-parts", [])
    if parts and parts[0]:
        year = parts[0][0]
    title = " ".join(item.get("title", [])[:1])
    venue = " ".join(item.get("container-title", [])[:1])
    doi = (item.get("DOI") or "").lower()
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "doi": doi,
        "venue": venue,
        "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
        "abstract": _strip_tags(item.get("abstract", "")),
        "source_api": "crossref",
        "type": item.get("type", ""),
    }


def search_semantic_scholar(query: str, limit: int) -> list[dict[str, Any]]:
    try:
        data = request_json(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            {
                "query": query,
                "limit": limit,
                "fields": "title,authors,year,venue,abstract,externalIds,openAccessPdf,url",
            },
        )
        return [_semantic_item_to_candidate(item) for item in data.get("data", [])]
    except Exception:
        return []


def _semantic_item_to_candidate(item: dict[str, Any]) -> dict[str, Any]:
    external = item.get("externalIds", {}) or {}
    doi = (external.get("DOI") or "").lower()
    pdf = item.get("openAccessPdf") or {}
    return {
        "title": item.get("title", ""),
        "authors": [a.get("name", "") for a in item.get("authors", [])[:8] if a.get("name")],
        "year": item.get("year"),
        "doi": doi,
        "venue": item.get("venue", ""),
        "url": item.get("url", "") or (f"https://doi.org/{doi}" if doi else ""),
        "pdf_url": pdf.get("url", "") if isinstance(pdf, dict) else "",
        "abstract": item.get("abstract", "") or "",
        "source_api": "semantic_scholar",
        "type": "paper",
    }


def search_openalex(query: str, per_page: int) -> list[dict[str, Any]]:
    try:
        data = request_json(
            "https://api.openalex.org/works",
            {"search": query, "per-page": per_page, "mailto": "a74zhou@uwaterloo.ca"},
        )
        return [_openalex_item_to_candidate(item) for item in data.get("results", [])]
    except Exception:
        return []


def _openalex_item_to_candidate(item: dict[str, Any]) -> dict[str, Any]:
    doi_url = item.get("doi") or ""
    doi = doi_url.replace("https://doi.org/", "").lower()
    authors = []
    for auth in item.get("authorships", [])[:8]:
        name = (auth.get("author") or {}).get("display_name", "")
        if name:
            authors.append(name)
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    oa = item.get("open_access") or {}
    return {
        "title": item.get("display_name", ""),
        "authors": authors,
        "year": item.get("publication_year"),
        "doi": doi,
        "venue": source.get("display_name", ""),
        "url": item.get("id", "") or doi_url,
        "pdf_url": location.get("pdf_url") or oa.get("oa_url") or "",
        "abstract": _openalex_abstract(item.get("abstract_inverted_index") or {}),
        "source_api": "openalex",
        "type": item.get("type", ""),
    }


def _openalex_abstract(index: dict[str, list[int]]) -> str:
    if not index:
        return ""
    words = []
    for word, positions in index.items():
        for pos in positions:
            words.append((pos, word))
    return " ".join(word for _, word in sorted(words))


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def build_queries(identity: CaseIdentity, seed_entries: list[dict[str, Any]], max_seed_titles: int = 3) -> list[str]:
    queries = []
    place = identity.name or identity.location
    location = identity.location or identity.name
    country = identity.country
    if place and country:
        queries.extend([
            f'"{place}" "{country}" buyout relocation resettlement',
            f'"{place}" "{country}" floodplain acquisition managed retreat',
        ])
    if location and location != place:
        queries.append(f'"{location}" buyout relocation flood')

    for entry in seed_entries[:max_seed_titles]:
        title = infer_title_from_citation(entry.get("citation", ""))
        if title:
            queries.append(title)

    return _dedupe(queries)


def infer_title_from_citation(citation: str) -> str:
    quoted = re.findall(r"[“\"]([^”\"]{12,180})[”\"]", citation)
    if quoted:
        return quoted[0]
    # Fallback: text between year and journal-ish punctuation.
    match = re.search(r"\(\d{4}\)\.?\s*([^\.]{20,180})\.", citation)
    if match:
        return match.group(1).strip()
    return ""


def merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for cand in candidates:
        title = cand.get("title", "")
        doi = cand.get("doi", "")
        key = f"doi:{doi}" if doi else f"title:{_title_key(title)}"
        if not key.endswith(":"):
            existing = merged.get(key)
            if existing:
                existing["source_api"] = ", ".join(_dedupe([existing.get("source_api", ""), cand.get("source_api", "")]))
                if not existing.get("abstract") and cand.get("abstract"):
                    existing["abstract"] = cand["abstract"]
                if not existing.get("pdf_url") and cand.get("pdf_url"):
                    existing["pdf_url"] = cand["pdf_url"]
            else:
                merged[key] = cand
    return list(merged.values())


def classify_candidate(candidate: dict[str, Any], identity: CaseIdentity, seed_dois: set[str], seed_titles: set[str]) -> dict[str, Any]:
    text = " ".join([
        candidate.get("title", ""),
        candidate.get("abstract", ""),
        candidate.get("venue", ""),
    ])
    norm_text = _norm(text)

    found_core_place = [term for term in identity.core_place_terms if _norm(term) and _norm(term) in norm_text]
    found_alias = [term for term in identity.alias_terms if _norm(term) and _norm(term) in norm_text]
    found_admin = [term for term in identity.admin_terms if _norm(term) and _norm(term) in norm_text]
    found_case_terms = [term for term in CASE_EVIDENCE_TERMS if _norm(term) in norm_text]
    found_policy_terms = [term for term in POLICY_TERMS if _norm(term) in norm_text]

    doi = candidate.get("doi", "")
    title_key = _title_key(candidate.get("title", ""))
    is_seed = bool((doi and doi in seed_dois) or (title_key and title_key in seed_titles))

    score = 0
    reasons = []
    if is_seed:
        score += 60
        reasons.append("matches DOI/title already listed in local source notes")
    if found_core_place:
        score += 25
        reasons.append(f"core case place term found: {', '.join(found_core_place[:3])}")
    if found_alias:
        score += 8
        reasons.append(f"case alias/event term found: {', '.join(found_alias[:3])}")
    if found_admin:
        score += 15
        reasons.append(f"administrative/country term found: {', '.join(found_admin[:3])}")
    if found_case_terms:
        score += 15
        reasons.append(f"retreat/recovery term found: {', '.join(found_case_terms[:3])}")
    if found_policy_terms:
        score += 8
        reasons.append(f"policy/legal term found: {', '.join(found_policy_terms[:3])}")
    if candidate.get("pdf_url"):
        score += 3
        reasons.append("open PDF URL available")

    if is_seed:
        source_class = "primary_or_secondary_seed"
        status = "accepted_seed"
    elif found_core_place and (found_admin or len(identity.admin_terms) <= 1) and found_case_terms:
        source_class = "candidate_case_evidence"
        status = "review_required"
    elif found_admin and found_policy_terms and found_case_terms:
        source_class = "candidate_policy_context"
        status = "review_required"
    elif found_core_place and found_admin:
        source_class = "weak_location_candidate"
        status = "rejected_by_identity_filter"
        reasons.append("mentions the place but lacks managed-retreat/recovery terms")
    else:
        source_class = "reject_or_background"
        status = "rejected_by_identity_filter"
        reasons.append("does not mention required case identity terms in title/abstract metadata")

    candidate["identity_evidence"] = {
        "core_place_terms_found": found_core_place,
        "alias_terms_found": found_alias,
        "admin_terms_found": found_admin,
        "case_terms_found": found_case_terms,
        "policy_terms_found": found_policy_terms,
    }
    candidate["confidence_score"] = min(score, 100)
    candidate["source_class"] = source_class
    candidate["status"] = status
    candidate["acceptance_reason"] = "; ".join(reasons)
    return candidate


def local_pdf_matches(case_dir: Path, candidate: dict[str, Any]) -> str:
    title_key = _title_key(candidate.get("title", ""))
    doi = candidate.get("doi", "")
    for pdf in case_dir.glob("*.pdf"):
        name_key = _title_key(pdf.stem)
        if title_key and title_key[:40] in name_key:
            return pdf.name
        if doi:
            # Some downloaded files include DOI fragments poorly; title match is the main route.
            continue
    return ""


def write_sources_json(case_dir: Path, identity: CaseIdentity, candidates: list[dict[str, Any]]) -> None:
    accepted = [c for c in candidates if c.get("status") == "accepted_seed"]
    payload = {
        "schema_version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_identity": {
            "case_id": identity.case_id,
            "name": identity.name,
            "location": identity.location,
            "country": identity.country,
            "aliases": identity.aliases,
        },
        "acceptance_policy": {
            "accepted_seed": "Existing spreadsheet/local sources are accepted but still carry evidence metadata.",
            "review_required": "Newly discovered candidate sources must be manually approved before use.",
            "rejected_by_identity_filter": "Candidate did not pass strict case identity matching.",
        },
        "sources": accepted,
    }
    (case_dir / "sources.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_candidates(case_dir: Path, candidates: list[dict[str, Any]]) -> None:
    (case_dir / "paper_candidates.json").write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n")


def write_report(case_dir: Path, identity: CaseIdentity, queries: list[str], candidates: list[dict[str, Any]]) -> None:
    review = [c for c in candidates if c.get("status") == "review_required"]
    accepted = [c for c in candidates if c.get("status") == "accepted_seed"]
    rejected = [c for c in candidates if c.get("status") == "rejected_by_identity_filter"]

    lines = [
        f"# Paper Discovery Report — {identity.case_id}",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Case Identity",
        "",
        f"- Name: {identity.name}",
        f"- Location: {identity.location}",
        f"- Country: {identity.country}",
        f"- Aliases: {', '.join(identity.aliases) if identity.aliases else 'None'}",
        "",
        "## Queries",
        "",
    ]
    lines.extend(f"- `{q}`" for q in queries)
    lines.extend([
        "",
        "## Accepted Seed Sources",
        "",
    ])
    if accepted:
        for c in sorted(accepted, key=lambda x: x.get("confidence_score", 0), reverse=True):
            lines.extend(_candidate_md(c))
    else:
        lines.append("No accepted seed sources found.")

    lines.extend([
        "",
        "## Review Required",
        "",
        "These are not automatically accepted. Approve only if the full text truly covers the case or governing policy.",
        "",
    ])
    if review:
        for c in sorted(review, key=lambda x: x.get("confidence_score", 0), reverse=True):
            lines.extend(_candidate_md(c))
    else:
        lines.append("No new candidates passed the review threshold.")

    lines.extend([
        "",
        "## Rejected / Background",
        "",
        f"{len(rejected)} candidates did not pass strict identity matching.",
    ])
    (case_dir / "paper_discovery_report.md").write_text("\n".join(lines) + "\n")


def _candidate_md(c: dict[str, Any]) -> list[str]:
    title = c.get("title") or "(untitled)"
    authors = ", ".join(c.get("authors", [])[:4])
    if len(c.get("authors", [])) > 4:
        authors += ", et al."
    abstract = c.get("abstract", "")
    abstract = textwrap.shorten(re.sub(r"\s+", " ", abstract), width=500, placeholder=" ...") if abstract else ""
    lines = [
        f"### {title}",
        "",
        f"- Status: `{c.get('status')}`",
        f"- Class: `{c.get('source_class')}`",
        f"- Score: {c.get('confidence_score')}",
        f"- Authors: {authors or 'Unknown'}",
        f"- Year: {c.get('year') or 'Unknown'}",
        f"- Venue: {c.get('venue') or 'Unknown'}",
        f"- DOI: {c.get('doi') or 'None'}",
        f"- URL: {c.get('url') or 'None'}",
        f"- PDF URL: {c.get('pdf_url') or 'None'}",
        f"- Local PDF: {c.get('local_pdf') or 'None'}",
        f"- Evidence: {c.get('acceptance_reason') or 'None'}",
    ]
    if abstract:
        lines.extend(["", f"> {abstract}"])
    lines.append("")
    return lines


def discover(case_id: str, aliases: list[str], max_results: int) -> tuple[Path, list[dict[str, Any]]]:
    case_dir = find_case_dir(case_id.upper())
    if not case_dir:
        raise FileNotFoundError(f"No case folder found for {case_id}")

    identity = load_case_identity(case_dir, aliases)
    seed_entries = parse_sources_txt(case_dir)
    doi_entries = parse_dois_txt(case_dir)
    for doi in doi_entries:
        if doi and not any(e.get("doi") == doi for e in seed_entries):
            seed_entries.append({
                "role": "source_from_dois_txt",
                "status": "accepted_seed",
                "citation": "",
                "doi": doi,
                "source": "dois.txt",
            })

    seed_candidates = []
    for entry in seed_entries:
        resolved = resolve_crossref_by_doi(entry.get("doi", "")) if entry.get("doi") else None
        if not resolved and entry.get("citation"):
            hits = search_crossref(entry["citation"], rows=1)
            resolved = hits[0] if hits else None
        candidate = resolved or {
            "title": infer_title_from_citation(entry.get("citation", "")),
            "authors": [],
            "year": None,
            "doi": entry.get("doi", ""),
            "venue": "",
            "url": f"https://doi.org/{entry.get('doi')}" if entry.get("doi") else "",
            "abstract": "",
            "source_api": "local_sources",
            "type": "unknown",
        }
        candidate["seed_role"] = entry.get("role")
        candidate["seed_citation"] = entry.get("citation")
        candidate["seed_source"] = entry.get("source")
        seed_candidates.append(candidate)

    queries = build_queries(identity, seed_entries)
    discovered = []
    for query in queries:
        discovered.extend(search_semantic_scholar(query, limit=max_results))
        discovered.extend(search_openalex(query, per_page=max_results))
        discovered.extend(search_crossref(query, rows=max_results))

    all_candidates = merge_candidates(seed_candidates + discovered)
    seed_dois = {e.get("doi") for e in seed_entries if e.get("doi")}
    seed_titles = {_title_key(infer_title_from_citation(e.get("citation", ""))) for e in seed_entries if e.get("citation")}
    seed_titles = {t for t in seed_titles if t}

    classified = []
    for candidate in all_candidates:
        candidate = classify_candidate(candidate, identity, seed_dois, seed_titles)
        local_pdf = local_pdf_matches(case_dir, candidate)
        if local_pdf:
            candidate["local_pdf"] = local_pdf
        classified.append(candidate)

    classified.sort(key=lambda c: (c.get("status") != "accepted_seed", -c.get("confidence_score", 0), c.get("title", "")))
    write_sources_json(case_dir, identity, classified)
    write_candidates(case_dir, classified)
    write_report(case_dir, identity, queries, classified)
    return case_dir, classified


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True, help="Case ID, e.g. CS36")
    parser.add_argument("--alias", action="append", default=[], help="Additional accepted location/program alias. Repeatable.")
    parser.add_argument("--max-results", type=int, default=5, help="Results per query per API (default: 5)")
    args = parser.parse_args(argv)

    case_dir, candidates = discover(args.case_id, args.alias, args.max_results)
    accepted = sum(1 for c in candidates if c.get("status") == "accepted_seed")
    review = sum(1 for c in candidates if c.get("status") == "review_required")
    rejected = sum(1 for c in candidates if c.get("status") == "rejected_by_identity_filter")
    print(f"Discovery complete for {args.case_id.upper()} -> {case_dir}")
    print(f"  accepted seed sources: {accepted}")
    print(f"  review-required candidates: {review}")
    print(f"  rejected/background candidates: {rejected}")
    print(f"  wrote: {case_dir / 'sources.json'}")
    print(f"  wrote: {case_dir / 'paper_candidates.json'}")
    print(f"  wrote: {case_dir / 'paper_discovery_report.md'}")


if __name__ == "__main__":
    main()
