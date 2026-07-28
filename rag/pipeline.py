import os
import re
import requests
import anthropic
from openai import OpenAI
from dotenv import load_dotenv
from rag.retriever import MRRetriever
from rag.prompt_builder import build_prompt

load_dotenv()

OLLAMA_URL = "http://localhost:11434/api/generate"

# Detect queries about a specific case study ID
_CS_ID_RE = re.compile(r"\bCS(\d+)\b", re.IGNORECASE)

# Detect broad overview/summary/comparison queries
_OVERVIEW_RE = re.compile(
    r"\b(summar|overview|all case|every case|list.*case|compare|across.*case|what case|which case)",
    re.IGNORECASE,
)


def query_ollama(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": "gemma4", "prompt": prompt, "stream": False},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


def query_claude(prompt: str, max_tokens: int = 4096) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def query_openai(prompt: str, max_tokens: int = 2048) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        max_completion_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def run_pipeline(
    query: str,
    questionnaire_answers: dict | None = None,
    filters: dict | None = None,
    model: str = "claude",
    return_chunks: bool = False,
) -> str | tuple[str, list[dict]]:
    retriever = MRRetriever(n_results=8)

    # Mode 1: specific CS ID mentioned → fetch all chunks for that case
    cs_match = _CS_ID_RE.search(query)
    if cs_match:
        case_id = f"CS{cs_match.group(1)}"
        chunks = retriever.retrieve_for_case(case_id)
        if not chunks:
            # Fall back to semantic search if case not found
            chunks = retriever.retrieve(query, filters=filters, max_per_case=2)

    # Mode 2: broad overview/summary → one overview chunk per case study
    elif _OVERVIEW_RE.search(query):
        chunks = retriever.retrieve_all_overviews()
        if not chunks:
            chunks = retriever.retrieve(query, filters=filters, max_per_case=1)

    # Mode 3: topic query → semantic search with diversity cap
    else:
        chunks = retriever.retrieve(query, filters=filters, max_per_case=2)

    if not chunks:
        no_result = "No relevant case studies found in the knowledge base. Please ingest documents first."
        return (no_result, []) if return_chunks else no_result

    prompt = build_prompt(query, chunks, questionnaire_answers)

    if model == "claude":
        answer = query_claude(prompt, max_tokens=8192 if _OVERVIEW_RE.search(query) else 4096)
    elif model in ("openai", "gpt"):
        answer = query_openai(prompt, max_tokens=4096 if _OVERVIEW_RE.search(query) else 2048)
    else:
        answer = query_ollama(prompt)

    return (answer, chunks) if return_chunks else answer


if __name__ == "__main__":
    print("RFR Managed Retreat RAG Pipeline — v0")
    print("Type 'quit' to exit.\n")
    while True:
        q = input("Your question: ").strip()
        if q.lower() in ("quit", "exit"):
            break
        if not q:
            continue
        print("\nThinking...\n")
        answer = run_pipeline(q)
        print(f"Answer:\n{answer}\n")
        print("-" * 60)
