from pathlib import Path


def build_prompt(query: str, retrieved_chunks: list[dict], questionnaire_answers: dict | None = None) -> str:
    context_blocks = "\n\n".join(
        f"[Source: {c['metadata'].get('source', 'unknown')} | Case: {c['metadata'].get('case_id', '?')}]\n{c['text']}"
        for c in retrieved_chunks
    )

    answers_section = ""
    if questionnaire_answers:
        answers_section = "\n\nUser context from questionnaire:\n" + "\n".join(
            f"- {k}: {v}" for k, v in questionnaire_answers.items()
        )

    is_overview = any(
        kw in query.lower()
        for kw in ("summar", "overview", "all case", "every case", "list", "compare", "across")
    )

    if is_overview:
        instruction = (
            "You are a research assistant. The user wants a summary of ALL case studies provided. "
            "For EVERY case study in the excerpts below, write exactly 2-3 sentences covering: "
            "location, hazard type, and key outcome or lesson. "
            "Do not skip any case. Format as a numbered list with the case ID bolded. "
            "Be concise — do not write long paragraphs."
        )
    else:
        instruction = (
            "You are a research assistant helping municipal planners and community leaders understand managed retreat. "
            "Answer in plain, formal language grounded strictly in the case study evidence below. "
            "Do not use informal metaphors or colloquial expressions. "
            "Cite specific case studies (e.g. CS5, CS20) and name sources where possible. "
            "Structure your answer with clear numbered sections if the question has multiple dimensions."
        )

    return f"""{instruction}{answers_section}

Case study excerpts:
{context_blocks}

Question: {query}

Answer:"""
