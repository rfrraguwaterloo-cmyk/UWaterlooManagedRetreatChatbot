import re
import json
import ast


_OVERVIEW_CONTEXT_CHARS = 1800


def _extract_label(text: str, label: str) -> str:
    pattern = re.compile(
        rf"\*\*{re.escape(label)}:\*\*\s*(.*?)(?=\n\n\*\*[^*\n]+:\*\*|\n---|\n#{1,6}\s|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _compact_overview_text(text: str) -> str:
    """Keep overview prompts small enough that all cases fit in the answer."""
    fields = []
    for label in ("Case Name and Location", "Hazard(s)", "Type of Retreat", "Key Outcomes"):
        value = _extract_label(text, label)
        if value:
            fields.append(f"{label}: {value}")

    compact = "\n".join(fields)
    if not compact:
        compact = re.sub(r"\s+", " ", text).strip()

    if len(compact) > _OVERVIEW_CONTEXT_CHARS:
        compact = compact[:_OVERVIEW_CONTEXT_CHARS].rsplit(" ", 1)[0] + " ..."
    return compact


def _parse_source_links(raw) -> list[dict]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(raw)
            except Exception:
                continue
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
    return []


def _format_source_links(metadata: dict, limit: int = 3) -> str:
    links = _parse_source_links(metadata.get("source_links"))
    pieces = []
    for link in links[:limit]:
        label = link.get("title") or link.get("doi") or "source"
        url = link.get("url") or (f"https://doi.org/{link['doi']}" if link.get("doi") else "")
        if url:
            pieces.append(f"{label}: {url}")
    return "; ".join(pieces)


def build_prompt(query: str, retrieved_chunks: list[dict], questionnaire_answers: dict | None = None) -> str:
    is_overview = any(
        kw in query.lower()
        for kw in ("summar", "overview", "all case", "every case", "list", "compare", "across")
    )

    if is_overview:
        context_blocks = "\n\n".join(
            f"[Source: {c['metadata'].get('source', 'unknown')} | Case: {c['metadata'].get('case_id', '?')}]\n"
            f"Source links: {_format_source_links(c['metadata'])}\n"
            f"{_compact_overview_text(c['text'])}"
            for c in retrieved_chunks
        )
    else:
        context_blocks = "\n\n".join(
            f"[Source: {c['metadata'].get('source', 'unknown')} | Case: {c['metadata'].get('case_id', '?')}]\n"
            f"Source links: {_format_source_links(c['metadata'])}\n"
            f"{c['text']}"
            for c in retrieved_chunks
        )

    answers_section = ""
    if questionnaire_answers:
        answers_section = "\n\nUser context from questionnaire:\n" + "\n".join(
            f"- {k}: {v}" for k, v in questionnaire_answers.items()
        )

    if is_overview:
        case_ids = ", ".join(c["metadata"].get("case_id", "?") for c in retrieved_chunks)
        instruction = (
            "You are a research assistant. The user wants a summary of ALL case studies provided. "
            f"The provided cases are: {case_ids}. "
            "Write exactly one numbered bullet for EVERY provided case, in the same order. "
            "Each bullet must start with the bold case ID, then give one concise sentence covering "
            "location, hazard or retreat type, and the key outcome or lesson. "
            "Keep each bullet under 45 words. Do not skip cases. Do not invent missing case IDs."
        )
    else:
        instruction = (
            "You are a research assistant helping municipal planners and community leaders understand managed retreat. "
            "Answer in plain, formal language grounded strictly in the case study evidence below. "
            "Do not use informal metaphors or colloquial expressions. "
            "Cite specific case studies (e.g. CS5, CS20), name sources where possible, and include DOI/source links when they are supplied in the context. "
            "Structure your answer with clear numbered sections if the question has multiple dimensions."
        )

    return f"""{instruction}{answers_section}

Case study excerpts:
{context_blocks}

Question: {query}

Answer:"""
