"""
embed_and_index.py — Precompute and save embeddings for all case study chunks.

Saves data/extracted/precomputed_embeddings.json:
  { "ids": [...], "embeddings": [...], "texts": [...], "metadatas": [...] }

Retrieval uses numpy cosine similarity in rag/retriever.py (no ChromaDB —
it is broken on Python 3.13 / HuggingFace Spaces).
"""
import json
import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EXTRACTED_DIR = Path("data/extracted")
EMBED_MODEL = "all-MiniLM-L6-v2"
PRECOMPUTED_PATH = Path("data/extracted/precomputed_embeddings.json")


def load_all_chunks() -> list[dict]:
    chunks = []
    for f in sorted(EXTRACTED_DIR.glob("*.json")):
        if f.name in ("precomputed_embeddings.json",):
            continue
        data = json.loads(f.read_text())
        if isinstance(data, list):
            chunks.extend(data)
    return chunks


def embed_and_index():
    chunks = load_all_chunks()
    if not chunks:
        print("No extracted data found in data/extracted/.")
        return

    texts = [c.get("text", json.dumps(c)) for c in chunks]
    ids = [f"{c.get('case_id', 'unknown')}_{c.get('chunk_index', i)}" for i, c in enumerate(chunks)]
    metadatas = [{k: str(v) for k, v in c.items() if k != "text"} for c in chunks]

    # Use precomputed embeddings if IDs match — nothing to do
    if PRECOMPUTED_PATH.exists():
        pre = json.loads(PRECOMPUTED_PATH.read_text())
        if pre.get("ids") == ids and "texts" in pre and "metadatas" in pre:
            print(f"Precomputed embeddings up to date ({len(ids)} chunks).")
            return
        print("Precomputed embeddings stale — recomputing...")
    else:
        print("No precomputed embeddings found — computing...")

    print(f"Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    print(f"Embedding {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    PRECOMPUTED_PATH.write_text(json.dumps({
        "ids": ids,
        "embeddings": embeddings,
        "texts": texts,
        "metadatas": metadatas,
    }))
    print(f"Saved precomputed embeddings for {len(texts)} chunks.")
    print("\nNext: streamlit run app/app.py")


if __name__ == "__main__":
    embed_and_index()
