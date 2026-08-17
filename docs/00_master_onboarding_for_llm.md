# 00 - Master Onboarding for a New VS Code LLM Session

Use this file as the first context document for a newly onboarded AI assistant,
VS Code agent, or team member working on the RFR Knowledge Platform.

## Project in One Paragraph

The RFR Knowledge Platform is a Streamlit website for querying managed retreat
case studies. It uses extracted case-study summaries and embeddings stored in
`data/extracted/`, retrieves relevant chunks with NumPy cosine similarity, and
generates grounded answers for planners, community leaders, and researchers. The
live site is hosted on Hugging Face Spaces, while GitHub is the main shared code
repository.

## Main Links

GitHub repository:

```text
https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot
```

Hugging Face Space:

```text
https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
```

Live website:

```text
https://uwrfr-uwaterloorfrchatbot.hf.space
```

New case study request intake folder:

```text
https://drive.google.com/drive/u/3/folders/10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y
```

Documentation folder:

```text
https://drive.google.com/drive/u/3/folders/1ZEb9riZZM9qWLYT70KzhdGzygsQHozYM
```

## Read These Files First

In the repository:

```text
AGENTS.md
README.md
docs/00_master_onboarding_for_llm.md
docs/01_get_the_code_and_run_locally.md
docs/02_hugging_face_and_api_keys.md
docs/03_new_case_study_requests_from_drive.md
docs/04_terminal_command_cheatsheet.md
docs/05_debugging_common_problems.md
docs/06_deploying_updates.md
```

In Google Drive, the ordered `.md` files mirror the most important handoff
instructions. Use this master file as the entry point, then open the numbered
guide that matches the task.

## Recommended Local Setup

Clone from GitHub:

```bash
git clone https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot.git
cd UWaterlooManagedRetreatChatbot
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Run the website:

```bash
streamlit run app/app.py
```

Open the local URL that Streamlit prints, usually:

```text
http://localhost:8501
```

## Git Remotes to Expect

On Anna's working machine, the useful remotes are:

```text
shared-github  https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot.git
uwrfr-chatbot  https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
```

On a fresh clone, the remote may simply be called `origin`.

Check remotes:

```bash
git remote -v
```

Add remotes if needed:

```bash
git remote add shared-github https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot.git
git remote add uwrfr-chatbot https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
```

## Normal Code Update Workflow

Start clean:

```bash
git status
git pull shared-github main
```

Create a branch:

```bash
git checkout -b your-name-short-task
```

Make edits, then test:

```bash
python3 -m py_compile app/app.py
streamlit run app/app.py
```

Commit:

```bash
git status
git diff --stat
git add path/to/changed_file.py
git commit -m "Describe the update"
```

Push to GitHub:

```bash
git push shared-github HEAD:main
```

Push to Hugging Face when the live website should update:

```bash
git push uwrfr-chatbot HEAD:main
```

Check the Space:

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
```

## Key Files and What They Do

Website:

```text
app/app.py
```

New case study request upload logic:

```text
app/drive_request_uploader.py
```

RAG answer pipeline:

```text
rag/pipeline.py
rag/retriever.py
rag/prompt_builder.py
```

Processed website data:

```text
data/extracted/CSxx.json
data/extracted/case_summaries.json
data/extracted/precomputed_embeddings.json
```

Raw case-study folders, metadata, source PDFs, and extraction outputs:

```text
data/raw/
```

Extraction pipeline:

```text
case_study_pipeline/
```

Ingestion and embedding rebuild scripts:

```text
ingest/ingest_pipeline_outputs.py
ingest/create_summary_chunks.py
ingest/embed_and_index.py
```

Source link cleanup:

```text
ingest/source_link_overrides.json
ingest/source_links.py
```

## How New Case Study Requests Work

Users submit candidate case studies through the website tab:

```text
New Case Study Requests
```

The form saves each request to Google Drive. Each request folder should contain:

```text
request.json
uploaded PDFs or supporting files
```

The form does not run the extraction pipeline. A team member still reviews the
request, chooses a case ID, runs the extraction pipeline locally, ingests the
result, rebuilds embeddings, tests, commits, and deploys.

Read:

```text
docs/03_new_case_study_requests_from_drive.md
```

## Process a New Case Study

Choose the next case ID:

```bash
ls data/extracted/CS*.json | sort -V | tail
find data/raw -maxdepth 1 -type d -name "CS*" | sort -V | tail
```

Create or onboard the local case folder from a Drive request:

```bash
python3 -m case_study_pipeline.onboard_case_study \
  --cs-num 124 \
  --name "Newtok to Mertarvik" \
  --country "United States" \
  --hazard "coastal erosion, flooding, permafrost thaw" \
  --stage "during relocation" \
  --actors "Newtok Village Council, State of Alaska, federal agencies" \
  --source-drive-folder "https://drive.google.com/drive/folders/<REQUEST_FOLDER_ID>"
```

Run the extraction:

```bash
python3 -m case_study_pipeline.run_case_study \
  --case-folder data/raw/CS124 \
  --case-id CS124 \
  --llm-provider claude \
  --max-chars-per-source 150000 \
  --force
```

Select, ingest, summarize, and embed:

```bash
python3 -m case_study_pipeline.select_best_run --case-id CS124
python3 ingest/ingest_pipeline_outputs.py --case-id CS124
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

Test locally:

```bash
streamlit run app/app.py
```

Ask:

```text
Summarize CS124.
```

Check that the case appears in the Case Studies tab and that source links are
present.

## Add or Fix Source Links

If a case has missing or messy source links, add APA-style entries to:

```text
ingest/source_link_overrides.json
```

Then rerun:

```bash
python3 ingest/ingest_pipeline_outputs.py --case-id CSxx
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

## Hugging Face Secrets and Variables

Do not put API keys or OAuth tokens in GitHub.

Hugging Face secrets are managed at:

```text
Hugging Face Space -> Settings -> Variables and secrets
```

Secrets currently expected by the live site:

```text
ANTHROPIC_API_KEY
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
GOOGLE_OAUTH_REFRESH_TOKEN
```

Optional OpenAI secrets if switching providers:

```text
OPENAI_API_KEY
OPENAI_MODEL
```

Drive intake folder variable:

```text
RFR_REQUESTS_DRIVE_FOLDER_ID
```

Current value:

```text
10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y
```

Generate Drive OAuth secrets locally:

```bash
python3 -m case_study_pipeline.create_drive_oauth_secrets \
  --credentials-file /path/to/oauth-client.json \
  --space-id UWRFR/UWaterlooRFRChatBot
```

When the browser opens, sign in as the shared Google account that should own
uploaded files, usually:

```text
rfr.rag.uwaterloo@gmail.com
```

## Common Debug Checks

Website does not load:

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
hf spaces logs UWRFR/UWaterlooRFRChatBot
```

Python syntax:

```bash
python3 -m py_compile app/app.py
python3 -m py_compile rag/pipeline.py
python3 -m py_compile rag/retriever.py
```

Case does not appear:

```bash
python3 ingest/ingest_pipeline_outputs.py --case-id CSxx
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

Hugging Face shows old content:

```bash
git log --oneline -5
hf spaces info UWRFR/UWaterlooRFRChatBot
git push uwrfr-chatbot HEAD:main
```

Drive request upload fails:

- Check the three `GOOGLE_OAUTH_*` secrets exist in Hugging Face.
- Check `RFR_REQUESTS_DRIVE_FOLDER_ID` points to the correct intake folder.
- Check the OAuth token was created by the Google account that can edit that
  folder.
- Restart the Space after changing secrets.

## What Not to Do

Do not commit:

- API keys.
- OAuth refresh tokens.
- `.env`.
- Raw PDFs, unless the team explicitly decides to store them in GitHub.
- Broad unrelated refactors while processing case studies.

Do not run destructive Git commands like:

```bash
git reset --hard
```

unless the team explicitly asks for that exact operation.

## Fast Handoff Prompt for Another LLM

Paste this into a new VS Code LLM session:

```text
You are helping maintain the RFR Knowledge Platform repository. First read
AGENTS.md and docs/00_master_onboarding_for_llm.md. This is a Streamlit RAG app
for managed retreat case studies. GitHub is the source of truth:
https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot.
Hugging Face Space UWRFR/UWaterlooRFRChatBot hosts the live app. Do not commit
secrets, raw PDFs, or unrelated changes. Before edits, inspect git status. For
new case studies, review the Drive request folder, choose the next CS ID, run
the case_study_pipeline extraction, ingest the result, rebuild summaries and
embeddings, test locally, then commit and push to GitHub and Hugging Face.
```

