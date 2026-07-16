# RFR Co-op: LLM-Assisted Managed Retreat Pipeline

> This file is read automatically by Codex. It provides full project context so every session starts with shared understanding.

## What this project is

This is a 4-month co-op research project embedded in the **Retreat From Risk (RFR)** project — a NFRF-funded international research initiative (Canada, USA, Indonesia) studying **managed retreat (MR)** as a climate adaptation strategy for flood-prone communities.

The co-op goal is to build an **LLM-assisted framework** for extracting and synthesizing insights from MR case study literature, and to deliver a working **RAG pipeline** that helps decision-makers (municipal planners, First Nations leaders) query those insights through a guided questionnaire and persona-aware interface.

**Supervisors:** Dr. Costa (systems engineering, UW) and Dr. Doberstein (geography, UW)  
**PhD collaborator:** Ana (has an existing human-coded extraction framework — this project compares LLM vs human extraction)  
**GitHub:** https://github.com/AnnasBeef  
**Linear:** https://linear.app/managed-retreat (team: Managed Retreat, issues prefixed MAN-)

---

## Working in Cowork (read this before running the pipeline here)

The Cowork sandbox is **ephemeral** (installed packages don't persist between sessions) and its **egress proxy blocks the LLM APIs**. To avoid re-diagnosing this every time:

- **Setup once per session:** `bash cowork_setup.sh` — installs only the minimal deps (`requirements-cowork.txt`), not the heavy RAG stack (`torch`, `sentence-transformers`) in `requirements.txt`.
- **The live API run does NOT work in Cowork.** `api.anthropic.com` returns a proxy `401`; `api.openai.com` is unreachable. Run the full 4-step pipeline on your **Mac**, not here.
- **If attempting outbound HTTPS from Python here,** the proxy uses a self-signed cert — prefix with `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`.
- **Works fine offline in Cowork:** PDF rendering (`pdf_utils.text_to_pdf`), source-text extraction (`pdfplumber`), manual Ver1/Ver2 drafting.

### Finding & downloading source papers for a case study

1. First try `python3 -m case_study_pipeline.fetch_papers --case-id CSxx` —
   pulls open-access PDFs automatically (Unpaywall, Semantic Scholar, Sci-Hub).
   Also blocked by the Cowork egress proxy; run on the Mac.
2. For anything still paywalled, use UWaterloo's institutional library
   access (EZproxy) via the Codex-in-Chrome browser extension — **this
   requires a human to complete WatIAM login + Duo 2FA, it cannot be
   scripted**. Full step-by-step procedure, including the one-time Chrome
   download-folder setting, is in
   `case_study_pipeline/README.md` under "Fetching paywalled papers via
   UWaterloo EZproxy (Chrome-assisted)". Read that section before attempting
   this — it documents the exact URL pattern (`ezproxy.py`) and the
   inbox-sorting + Drive-upload script (`sort_inbox.py`).

---

## Core research questions

1. Can LLMs reliably extract key information from MR case studies compared to human coders?
2. How does question structure (the guided questionnaire) affect LLM output quality?
3. What does a useful decision-support tool look like for a community leader considering managed retreat?

---

## What we're building

### Pipeline architecture

```
MR case studies (PDFs, spreadsheets)
        ↓
Case-study source catalog (Ajibade et al. spreadsheet + local case_meta.json)
        ↓
LLM extraction/audit pipeline (Ver1 → Check1 → Ver2 → Check2)
        ↓
Section-level JSON chunks in data/extracted/
        ↓
Precomputed embedding store (data/extracted/precomputed_embeddings.json)
        ↓
NumPy cosine retrieval (semantic search)
        ↓
Persona layer (decision-maker framing)
        ↓
Guided questionnaire (shapes the query)
        ↓
LLM response (grounded, source-cited)
        ↓
Web interface (hosted on AWS / HuggingFace Spaces)
```

### Month 1 deliverables (by ~June 6)
- [ ] v0 RAG pipeline running locally (MAN-16)
- [ ] Decision-maker persona defined (MAN-11)
- [ ] Guided questionnaire v1 (MAN-12)
- [ ] Persona + questionnaire integrated into RAG (MAN-13)
- [ ] Cloud hosting decision made (MAN-17)

---

## Tech stack

| Layer | Tool | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Retrieval store | `data/extracted/precomputed_embeddings.json` | JSON file with chunk text, metadata, embeddings, and a content hash |
| Embeddings | sentence-transformers | Free, local (`all-MiniLM-L6-v2`) |
| Retrieval | NumPy cosine similarity | Runtime replacement for ChromaDB; see `rag/retriever.py` |
| LLM (local fallback) | Ollama | `rag/pipeline.py` currently calls Ollama model `gemma4` for non-Claude/OpenAI mode |
| Web interface | Streamlit | `app/app.py` |
| Hosting | HuggingFace Spaces (dev) → AWS EC2 (prod) | |
| Project tracking | Linear (MAN- issues) | |
| Version control | GitHub (AnnasBeef) | Branch names: `MAN-XX-short-description` |

---

## Repo structure

```
rfr-rag/
├── AGENTS.md               ← you are here
├── data/
│   ├── raw/                # original PDFs and spreadsheets
│   └── extracted/          # Ver2-derived JSON chunks + precomputed embeddings
├── ingest/
│   ├── ingest_pipeline_outputs.py
│   ├── create_summary_chunks.py
│   └── embed_and_index.py
├── rag/
│   ├── retriever.py
│   ├── prompt_builder.py
│   └── pipeline.py
├── persona/
│   └── decision_maker.json  # persona config
├── questionnaire/
│   └── questions.json       # guided questionnaire structure
├── app/
│   └── app.py              # Streamlit/Gradio interface
├── case_study_pipeline/    # Ver1/Check1/Ver2/Check2 extraction workflow
├── docs/
│   └── extraction_schema.md
├── tests/
└── requirements.txt
```

---

## Current extraction/indexing format

The original plan used a compact structured schema. The current RAG index uses
long-form Ver2 memo sections instead:

```json
{
  "case_id": "CS24",
  "chunk_index": 0,
  "section": "overview",
  "location": "Queens, New York",
  "country": "United States",
  "source": "Pipeline Ver2 — Queens",
  "text": "Case study: Queens ... Section: CASE STUDY OVERVIEW ..."
}
```

The active index is built by:

1. `python3 -m case_study_pipeline.select_best_run --case-id CSxx` if multiple runs exist.
2. `python3 ingest/ingest_pipeline_outputs.py --case-id CSxx` to convert canonical `CSxx_Ver2.md` into `data/extracted/CSxx.json`.
3. `python3 ingest/create_summary_chunks.py` to refresh one overview chunk per case in `data/extracted/case_summaries.json`.
4. `python3 ingest/embed_and_index.py` to refresh `data/extracted/precomputed_embeddings.json`.

`embed_and_index.py` checks chunk IDs, text, metadata, and a content hash. If a
Ver2 memo or JSON chunk changes, rebuild the embedding file before testing the app.

---

## Case studies and source spreadsheet

The expanded case-study catalog is based on the Ajibade et al. spreadsheet:
`https://docs.google.com/spreadsheets/d/1PGvxXlBUP-DFTuaYKhO5xSesHnPGhMlM/edit`

As of July 14, 2026, the local RAG knowledge base has canonical Ver2 outputs,
extracted JSON, and embeddings for 34 cases:

`CS1`-`CS31`, `CS33`, `CS34`, and `CS35`.

`CS32` exists in the spreadsheet/local metadata as Nono District / Jiru Gamachu
Resettlement Site, Ethiopia, but does not currently have a canonical Ver2 output
or extracted JSON in this repo.

Current CS1-CS20 local names from `case_meta.json` and canonical Ver2 outputs:

| ID | Current local name | Location | Country |
|----|--------------------|----------|---------|
| CS1 | Isle de Jean Charles Resettlement | Isle de Jean Charles, Terrebonne Parish, Louisiana | USA |
| CS2 | Shaanxi Ecological Resettlement | Shaanxi Province | China |
| CS3 | Oakwood Beach Buyout Program | Oakwood Beach, Staten Island, New York | USA |
| CS4 | Metro Manila Resettlement (Oplan LIKAS) | Metro Manila | Philippines |
| CS5 | Matata Managed Retreat | Matata, Bay of Plenty | New Zealand |
| CS6 | Pointe-Gatineau Home Buyout Program | Pointe-Gatineau, Quebec | Canada |
| CS7 | Hambantota Post-Tsunami Relocation | Hambantota | Sri Lanka |
| CS8 | Cedar Rapids Buyout Program | Cedar Rapids, Iowa | USA |
| CS9 | Grand Forks Floodplain Buyout | Grand Forks, North Dakota | USA |
| CS10 | San Juan Managed Retreat | San Juan, Puerto Rico | USA |
| CS11 | Terrebonne Parish Resettlement | Terrebonne Parish, Louisiana | USA |
| CS12 | Dhye Community Relocation | Dhye, Mustang District | Nepal |
| CS13 | Soldiers Grove Floodplain Relocation | Soldiers Grove, Wisconsin | USA |
| CS14 | Simbach am Inn Household Relocation | Simbach am Inn, Bavaria | Germany |
| CS15 | Tegua Island Planned Relocation | Tegua, Torba Province | Vanuatu |
| CS16 | Vunidogola Village Relocation | Vunidogola, Koralau Island | Fiji |
| CS17 | San Martin Planned Relocation | San Martin Region | Peru |
| CS18 | High River Buyout Program | High River, Alberta | Canada |
| CS19 | Nusa Hope Village Relocation | Nusa Hope, New Georgia | Solomon Islands |
| CS20 | East Riding Managed Retreat | East Riding of Yorkshire | UK |

---

## Decision-maker persona (v0)

The RAG pipeline frames responses for this user:

- **Role:** Municipal planner or First Nations community leader
- **Knowledge level:** Non-technical; familiar with community planning, not with ML or hydrology
- **Key concerns:** Equity, community buy-in, funding availability, cultural impacts, legal barriers
- **Preferred tone:** Plain language, practical, grounded in real examples
- **What "useful" looks like:** "Here's what worked in a similar community, here's what to watch out for, here are the key decisions you need to make"

---

## Linear issues (current)

| ID | Title | Due | Priority |
|----|-------|-----|----------|
| MAN-5 | Review human-coded extraction framework with Ana | May 16 | Urgent |
| MAN-6 | Read key MR case studies and synthesis papers | May 23 | High |
| MAN-7 | Build structured extraction schema | May 23 | High |
| MAN-8 | Apply framework to Isle de Jean Charles | May 23 | High |
| MAN-9 | Write Week 2 reflection memo | May 23 | Medium |
| MAN-10 | Build basic RAG pipeline | May 16 | High |
| MAN-11 | Define decision-maker persona | May 16 | High |
| MAN-12 | Design guided questionnaire | May 29 | High |
| MAN-13 | Integrate persona + questionnaire into RAG | May 29 | Medium |
| MAN-14 | Set up GitHub repo (AnnasBeef) | May 12 | Urgent |
| MAN-15 | Connect GitHub to Linear and Codex | May 12 | Urgent |
| MAN-16 | Build v0 RAG pipeline locally today | May 11 | Urgent |
| MAN-17 | Research cloud hosting strategy | May 16 | High |

Branch naming convention: `MAN-XX-short-description`  
e.g. `MAN-16-rag-v0-local`

---

## Key files in this repo to read first

- `data/extracted/` — Ver2-derived JSON case study chunks and embedding index
- `case_study_pipeline/README.md` — end-to-end extraction/audit workflow
- `ingest/ingest_pipeline_outputs.py` — converts canonical Ver2 memos into JSON chunks
- `ingest/create_summary_chunks.py` — builds overview chunks for summary queries
- `ingest/embed_and_index.py` — builds `precomputed_embeddings.json`
- `rag/pipeline.py` — main RAG query loop
- `persona/decision_maker.json` — persona config used in prompt construction
- `questionnaire/questions.json` — guided questionnaire structure

---

## Quick start (local dev)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Optional: start local LLM fallback
ollama pull gemma4
ollama run gemma4

# 3. Convert canonical Ver2 memos to JSON chunks when case outputs change
python ingest/ingest_pipeline_outputs.py
python ingest/create_summary_chunks.py

# 4. Build or refresh the precomputed embedding index
python ingest/embed_and_index.py

# 5. Run the RAG pipeline
python rag/pipeline.py

# 6. Launch the web app
streamlit run app/app.py
```

---

## Key concepts to know

**Managed retreat (MR):** The purposeful relocation of people, property, and infrastructure out of areas vulnerable to recurrent climatic hazards. Ranges from voluntary property buyouts to forced community resettlement.

**RAG (Retrieval-Augmented Generation):** An LLM pattern where relevant documents are retrieved from a vector store and included in the prompt, so the model's response is grounded in specific source material rather than relying on training data alone.

**Decision Support Framework (DSF):** The broader research output of the RFR project — a framework to help communities evaluate MR as a viable adaptation strategy. This pipeline is a technical tool to support the DSF.

**OCAP principles:** Ownership, Control, Access, Possession — Indigenous data governance principles that must be respected when working with First Nations case study data.

---

*Last updated: May 11, 2026 — generated from Codex.ai project context*
