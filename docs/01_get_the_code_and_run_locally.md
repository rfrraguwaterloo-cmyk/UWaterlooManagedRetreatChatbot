# 01 - Get the Code and Run It Locally

This guide is for a team member who wants to edit or run the RFR Knowledge
Platform from their own computer.

## What You Need

- A GitHub account with access to the shared repository.
- Git installed.
- Python 3.11 or newer.
- A terminal app.
- Optional but recommended: Visual Studio Code.

## Main Project Links

- GitHub repository:
  https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot
- Hugging Face Space:
  https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
- Live website:
  https://uwrfr-uwaterloorfrchatbot.hf.space

## Option A: Get the Code from GitHub

This is the recommended way to work on the project.

```bash
git clone https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot.git
cd UWaterlooManagedRetreatChatbot
```

Create a branch before editing:

```bash
git checkout -b your-name-short-change-description
```

Example:

```bash
git checkout -b anna-update-case-request-docs
```

## Option B: Get the Code from Hugging Face

This is useful if you only have Hugging Face access.

```bash
git clone https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
cd UWaterlooRFRChatBot
```

You can also download with the Hugging Face CLI:

```bash
hf download UWRFR/UWaterlooRFRChatBot --repo-type=space
```

For team development, prefer GitHub because it supports pull requests and code
review more clearly.

## Install Python Dependencies

From inside the project folder:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell, activate the virtual environment with:

```powershell
venv\Scripts\Activate.ps1
```

## Run the Website Locally

```bash
streamlit run app/app.py
```

The terminal will print a local URL, usually:

```text
http://localhost:8501
```

Open that URL in your browser.

## Important Files

- `app/app.py` - website tabs, text, layout, and main Streamlit app.
- `app/drive_request_uploader.py` - uploads new case study requests to Google Drive.
- `rag/pipeline.py` - sends retrieved context to the LLM for answer generation.
- `rag/retriever.py` - searches the precomputed embedding file.
- `data/extracted/` - processed case-study JSON and embeddings used by the website.
- `data/raw/` - source PDFs, case metadata, and pipeline outputs.
- `case_study_pipeline/` - extraction and audit workflow.
- `ingest/` - converts pipeline outputs into website-ready JSON and embeddings.
- `docs/` - documentation.

## Basic Local Test

Run this after editing code:

```bash
python3 -m py_compile app/app.py
streamlit run app/app.py
```

Then check:

- The website loads.
- The navigation buttons stay in the same browser tab.
- The Ask tab can answer a simple question.
- The Case Studies tab still opens and lists cases.

## Save Your Work

Check changed files:

```bash
git status
```

Commit changes:

```bash
git add path/to/changed_file.py
git commit -m "Describe the change"
```

Push your branch:

```bash
git push origin your-branch-name
```

Then open a pull request on GitHub into `main`.

