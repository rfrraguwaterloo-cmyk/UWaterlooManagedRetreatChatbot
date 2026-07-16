---
title: RFR Knowledge Platform
emoji: 🌊
colorFrom: blue
colorTo: green
sdk: streamlit
app_file: app/app.py
pinned: false
---

# RFR Co-op: LLM-Assisted Managed Retreat RAG Pipeline

A RAG (Retrieval-Augmented Generation) pipeline for extracting and synthesizing insights from managed retreat case study literature, built for the **Retreat From Risk (RFR)** research initiative.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# 1. Set API keys
export ANTHROPIC_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here

# 2. Convert canonical Ver2 memos to JSON chunks, then build embeddings
python ingest/ingest_pipeline_outputs.py
python ingest/create_summary_chunks.py
python ingest/embed_and_index.py

# 3. Run CLI pipeline
python rag/pipeline.py

# 4. Launch Streamlit web app
streamlit run app/app.py
```

## Ingesting documents

```bash
# Convert canonical case-study memos into section chunks
python ingest/ingest_pipeline_outputs.py

# Refresh overview-summary chunks for broad comparison queries
python ingest/create_summary_chunks.py

# Build the precomputed embedding store used by rag/retriever.py
python ingest/embed_and_index.py
```

## Project structure

```
rfr-rag/
├── data/raw/           # Original PDFs and spreadsheets (not committed)
├── data/extracted/     # Ver2-derived JSON chunks + embedding store
├── ingest/             # Ver2 ingestion, summary chunks, embedding script
├── case_study_pipeline/# Source extraction/audit workflow
├── rag/                # Retriever, prompt builder, pipeline
├── persona/            # Decision-maker persona config
├── questionnaire/      # Guided questionnaire structure
├── app/                # Streamlit interface
├── docs/               # Extraction schema, memos
└── tests/
```

See [CLAUDE.md](CLAUDE.md) for full project context.
