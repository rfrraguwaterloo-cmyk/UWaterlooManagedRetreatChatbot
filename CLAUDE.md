# RFR Co-op: LLM-Assisted Managed Retreat Pipeline

> This file is read automatically by Claude Code. It provides full project context so every session starts with shared understanding.

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

- **Setup once per session:** `bash cowork_setup.sh` — installs only the minimal deps (`requirements-cowork.txt`), not the heavy RAG stack (torch/chromadb) in `requirements.txt`.
- **The live API run does NOT work in Cowork.** `api.anthropic.com` returns a proxy `401`; `api.openai.com` is unreachable. Run the full 4-step pipeline on your **Mac**, not here.
- **If attempting outbound HTTPS from Python here,** the proxy uses a self-signed cert — prefix with `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`.
- **Works fine offline in Cowork:** PDF rendering (`pdf_utils.text_to_pdf`), source-text extraction (`pdfplumber`), manual Ver1/Ver2 drafting.

### Finding & downloading source papers for a case study

1. First try `python3 -m case_study_pipeline.fetch_papers --case-id CSxx` —
   pulls open-access PDFs automatically (Unpaywall, Semantic Scholar, Sci-Hub).
   Also blocked by the Cowork egress proxy; run on the Mac.
2. For anything still paywalled, use UWaterloo's institutional library
   access (EZproxy) via the Claude-in-Chrome browser extension — **this
   requires a human to complete WatIAM login + Duo 2FA, it cannot be
   scripted**. Full step-by-step procedure, including the one-time Chrome
   download-folder setting, is in
   `case_study_pipeline/README.md` under "Fetching paywalled papers via
   UWaterloo EZproxy (Chrome-assisted)". Read that section before attempting
   this — it documents the exact URL pattern (`ezproxy.py`) and the
   inbox-sorting + Drive-upload script (`sort_inbox.py`).

### Searching for new supplemental papers (consensus search process)

When looking for additional papers beyond what's in `sources.txt`, follow this process:

**1. Read `sources.txt` first** — check what's already listed so you don't duplicate.

**2. Always anchor searches on the location name** — every search must include the specific town/city name in quotes (e.g. `"Cagayan de Oro"`, `"Valmeyer"`). Papers must mention the actual place, not just the general topic.

**3. Run 2–3 targeted searches in parallel:**
- `"[Location]" "[disaster event]" resettlement OR buyout OR relocation journal doi`
- `"[Location]" flood OR hazard managed retreat academic paper`
- `"[Location]" "Natural Hazards" OR "IJDRR" OR "Climatic Change" doi`

**4. Verify each paper actually covers the location** — fetch the abstract to confirm the location name appears in the paper itself, not just in a reference list or tangentially.

**5. Get the DOI** for each confirmed paper so it can be downloaded directly.

**6. Flag open access vs paywalled** — open access (PMC, ResearchGate, IOP open) can be downloaded directly; paywalled ones need UWaterloo EZproxy.

> **The most common mistake:** finding papers *about* the general topic (flood buyouts, managed retreat in the Philippines, etc.) that don't actually study the specific case study location. The location name check is the critical filter.

### Automated high-precision discovery

Use the structured discovery command before relying on broad web or Consensus
search results:

```bash
python3 -m case_study_pipeline.discover_sources --case-id CS36
python3 -m case_study_pipeline.discover_sources --case-id CS36 --alias "Pitt County" --alias "Hurricane Floyd"
```

This writes `sources.json`, `paper_candidates.json`, and
`paper_discovery_report.md` in the case folder. Existing `sources.txt` /
`dois.txt` entries are treated as accepted seed sources. New papers are only
marked `review_required` unless they pass strict identity checks against the
case village/city, province/state, country, aliases, and managed-retreat terms.
Policy/legal context is labelled separately from direct case evidence.

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
Extraction schema (JSON) — human + LLM comparison
        ↓
Vector store (ChromaDB) — embedded chunks
        ↓
Retrieval (semantic search)
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
| Vector store | ChromaDB | Runs locally, no setup |
| Embeddings | sentence-transformers | Free, local (`all-MiniLM-L6-v2`) |
| LLM (local) | Ollama + Llama 3 8B or Mistral | Run with `ollama run llama3` |
| RAG framework | LangChain or LlamaIndex | TBD |
| Web interface | Streamlit or Gradio | Simple, fast to prototype |
| Hosting | HuggingFace Spaces (dev) → AWS EC2 (prod) | |
| Project tracking | Linear (MAN- issues) | |
| Version control | GitHub (AnnasBeef) | Branch names: `MAN-XX-short-description` |

---

## Repo structure

```
rfr-rag/
├── CLAUDE.md               ← you are here
├── data/
│   ├── raw/                # original PDFs and spreadsheets
│   └── extracted/          # JSON outputs from extraction schema
├── ingest/
│   ├── parse_spreadsheet.py
│   ├── parse_pdf.py
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
├── docs/
│   ├── reflection_memo_week2.md
│   └── extraction_schema.md
├── tests/
└── requirements.txt
```

---

## Extraction schema (key variables)

When extracting from case studies, capture these fields:

```json
{
  "case_id": "",
  "location": "",
  "country": "",
  "hazard_type": "",
  "trigger": "",
  "year_initiated": "",
  "stage": "pre-retreat | during | post-retreat",
  "governance": "",
  "funding_mechanism": "",
  "compensation_type": "",
  "voluntariness": "voluntary | incentivized | involuntary",
  "equity_outcomes": "",
  "implementation_barriers": [],
  "community_engagement": "",
  "success_rating": "successful | failed | ongoing",
  "source": ""
}
```

---

## Case studies in scope

| ID | Location | Country | Stage | Hazard |
|----|----------|---------|-------|--------|
| CS1 | Kwantlen First Nation (McMillan Island) | Canada | Pre-retreat | Riverine flood + erosion |
| CS2 | Sts'Ailes First Nation | Canada | Pre-retreat | Riverine + tsunami |
| CS3 | Gatineau, Quebec | Canada | During (reactive) | Riverine flood |
| CS4 | Erie Shore Drive, Chatham-Kent | Canada | Pre-retreat | Shoreline erosion |
| CS5 | Cedar Rapids, Iowa | USA | Post-retreat | Riverine flood |
| CS6 | Houston-Galveston, Texas | USA | During | Coastal + riverine |
| CS7 | Sayung Demak | Indonesia | During (forced) | Tidal inundation |
| CS8 | Bengawan Solo | Indonesia | Post-retreat | Riverine flood |

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
| MAN-15 | Connect GitHub to Linear and Claude Code | May 12 | Urgent |
| MAN-16 | Build v0 RAG pipeline locally today | May 11 | Urgent |
| MAN-17 | Research cloud hosting strategy | May 16 | High |

Branch naming convention: `MAN-XX-short-description`  
e.g. `MAN-16-rag-v0-local`

---

## Key files in this repo to read first

- `data/extracted/` — JSON case study extractions (start here for RAG ingestion)
- `rag/pipeline.py` — main RAG query loop
- `persona/decision_maker.json` — persona config used in prompt construction
- `questionnaire/questions.json` — guided questionnaire structure

---

## Quick start (local dev)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start local LLM
ollama pull llama3
ollama run llama3

# 3. Ingest case studies into vector store
python ingest/embed_and_index.py

# 4. Run the RAG pipeline
python rag/pipeline.py

# 5. Launch the web app
streamlit run app/app.py
```

---

## Key concepts to know

**Managed retreat (MR):** The purposeful relocation of people, property, and infrastructure out of areas vulnerable to recurrent climatic hazards. Ranges from voluntary property buyouts to forced community resettlement.

**RAG (Retrieval-Augmented Generation):** An LLM pattern where relevant documents are retrieved from a vector store and included in the prompt, so the model's response is grounded in specific source material rather than relying on training data alone.

**Decision Support Framework (DSF):** The broader research output of the RFR project — a framework to help communities evaluate MR as a viable adaptation strategy. This pipeline is a technical tool to support the DSF.

**OCAP principles:** Ownership, Control, Access, Possession — Indigenous data governance principles that must be respected when working with First Nations case study data.

---

*Last updated: May 11, 2026 — generated from Claude.ai project context*
