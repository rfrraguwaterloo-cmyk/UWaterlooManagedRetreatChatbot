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

# 2. Ingest case studies into vector store
python ingest/embed_and_index.py

# 3. Run CLI pipeline
python rag/pipeline.py

# 4. Launch Streamlit web app
streamlit run app/app.py
```

## Ingesting documents

```bash
# Parse a PDF case study
python ingest/parse_pdf.py data/raw/isle_de_jean_charles.pdf CS1

# Parse a spreadsheet (Ana's human-coded extractions)
python ingest/parse_spreadsheet.py data/raw/extraction_framework.xlsx

# Embed everything into ChromaDB
python ingest/embed_and_index.py
```

## Project structure

```
rfr-rag/
├── data/raw/           # Original PDFs and spreadsheets (not committed)
├── data/extracted/     # JSON outputs from parsing
├── ingest/             # PDF + spreadsheet parsers, embedding script
├── rag/                # Retriever, prompt builder, pipeline
├── persona/            # Decision-maker persona config
├── questionnaire/      # Guided questionnaire structure
├── app/                # Streamlit interface
├── docs/               # Extraction schema, memos
└── tests/
```

See [CLAUDE.md](CLAUDE.md) for full project context.
