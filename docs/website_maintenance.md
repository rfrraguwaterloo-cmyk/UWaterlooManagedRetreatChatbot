# Website Maintenance and New Case Study Guide

This guide explains how to maintain the RFR Knowledge Platform website and how
to add new managed retreat case studies to the searchable knowledge base.

## Repositories and Live Website

- Shared GitHub repo:
  `https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot`
- Shared Hugging Face Space:
  `https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot`
- Live app:
  `https://uwrfr-uwaterloorfrchatbot.hf.space`

GitHub is the easiest shared place for code review. Hugging Face is where the
Streamlit app runs.

## Editing the Website From Another Computer

1. Install Git and Python 3.11 or newer.
2. Clone the shared GitHub repo:

```bash
git clone https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot.git
cd UWaterlooManagedRetreatChatbot
```

3. Create a working branch:

```bash
git checkout -b update-website-text
```

4. Install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

5. Run the website locally:

```bash
streamlit run app/app.py
```

6. Edit the code. Most website text and tabs are in:

```text
app/app.py
```

7. Check the app still compiles:

```bash
python3 -m py_compile app/app.py
```

8. Commit and push:

```bash
git status
git add app/app.py
git commit -m "Update website text"
git push origin update-website-text
```

9. Open a Pull Request on GitHub into `main`.

After the change is merged into `main`, the GitHub Action can deploy to Hugging
Face if the shared repo has `HF_TOKEN` and `HF_SPACE_ID` configured. The team can
also push manually to Hugging Face from a machine that is logged in with `hf`.

## Manual Hugging Face Push

From a local repo with the Hugging Face CLI logged in:

```bash
git remote add uwrfr-chatbot https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
git push uwrfr-chatbot HEAD:main
```

If the remote already exists, update it instead:

```bash
git remote set-url uwrfr-chatbot https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
git push uwrfr-chatbot HEAD:main
```

Or upload the current folder with the CLI:

```bash
hf upload UWRFR/UWaterlooRFRChatBot . \
  --type space \
  --exclude ".git/*" \
  --exclude ".github/*" \
  --exclude ".venv/*" \
  --exclude "venv/*" \
  --exclude "__pycache__/*" \
  --exclude "data/raw/*" \
  --exclude "*.pdf" \
  --commit-message "Update website"
```

Check Space status:

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
```

## Website Secrets

Set these in Hugging Face Space settings under **Variables and secrets**.

Required for the chatbot:

```text
ANTHROPIC_API_KEY
```

Optional if using OpenAI mode:

```text
OPENAI_API_KEY
OPENAI_MODEL
```

Required for Google Sheets logging and Google Drive case-study request uploads:

```text
GOOGLE_SERVICE_ACCOUNT_JSON
```

Optional Drive override for new case study requests:

```text
RFR_REQUESTS_DRIVE_FOLDER_ID
```

By default, new case study requests are uploaded to this Drive folder:

```text
10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y
```

The Drive folder must be shared with the service account email inside
`GOOGLE_SERVICE_ACCOUNT_JSON`. Otherwise uploads from the website will fail.

## How New Case Study Requests Work

Users can submit candidate papers through the **New Case Study Requests** tab.
The app creates a new Google Drive folder for each request. Each folder contains:

- `request.json`
- uploaded PDFs or supporting documents

The request tab only collects files and notes. It does not run the extraction
pipeline and does not call an LLM.

## Adding a New Case Study to the Knowledge Base

Use this workflow after the team accepts a submitted request or identifies a new
case study.

### 1. Choose the Next Case ID

Check the highest indexed case:

```bash
ls data/extracted/CS*.json | sort -V | tail
```

If the latest indexed case is `CS54`, the next one is usually `CS55`.

### 2. Create the Raw Case Folder

Create a folder under `data/raw/`:

```bash
mkdir -p data/raw/CS55-ShortName_COUNTRY
```

Put source PDFs, `.md`, or `.txt` files in that folder.

Add or confirm `case_meta.json` in that folder. Example:

```json
{
  "case_id": "CS55",
  "name": "Short case study name",
  "location": "City or region",
  "country": "Country"
}
```

### 3. Run the One-Provider Extraction Pipeline

Use one provider for all four extraction and audit steps. Claude is the current
simplest option:

```bash
python3 -m case_study_pipeline.run_case_study \
  --case-folder data/raw/CS55-ShortName_COUNTRY \
  --case-id CS55 \
  --llm-provider claude \
  --max-chars-per-source 150000 \
  --force
```

This writes outputs to:

```text
data/raw/CS55-ShortName_COUNTRY/pipeline_output/
```

Expected output files:

- `CS55_Ver1.md`
- `CS55_Check1_report.md`
- `CS55_Ver2.md`
- `CS55_Check2_report.md`
- matching PDFs

### 4. Select the Best Run

```bash
python3 -m case_study_pipeline.select_best_run --case-id CS55
```

This creates or updates:

```text
data/raw/CS55-ShortName_COUNTRY/pipeline_output/selected.json
```

### 5. Ingest the Case Study

```bash
python3 ingest/ingest_pipeline_outputs.py --case-id CS55
```

This creates:

```text
data/extracted/CS55.json
```

### 6. Rebuild Summaries and Embeddings

Always run both commands after adding or changing extracted case data:

```bash
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

These update:

```text
data/extracted/case_summaries.json
data/extracted/precomputed_embeddings.json
```

The live website will not know about the new case until these files are updated
and deployed.

### 7. Test Locally

```bash
streamlit run app/app.py
```

Check:

- the new case appears in **Case Studies**
- the app can answer a direct question such as `Summarize CS55`
- source links appear if `source_links` metadata is available

### 8. Commit and Push

Commit only the files needed by the app. Usually this means:

```bash
git add data/extracted/CS55.json
git add data/extracted/case_summaries.json
git add data/extracted/precomputed_embeddings.json
git add data/raw/CS55-ShortName_COUNTRY/case_meta.json
git commit -m "Add CS55 case study"
```

The raw source PDFs are usually not committed. Keep them in Drive or local raw
storage unless the team explicitly decides otherwise.

Push to GitHub:

```bash
git push shared-github HEAD:main
```

Push to Hugging Face:

```bash
git push uwrfr-chatbot HEAD:main
```

## Updating an Existing Case Study

If a case study already exists and you are improving its sources or extraction:

```bash
python3 -m case_study_pipeline.run_case_study \
  --case-folder data/raw/CS55-ShortName_COUNTRY \
  --case-id CS55 \
  --llm-provider claude \
  --max-chars-per-source 150000 \
  --force

python3 -m case_study_pipeline.select_best_run --case-id CS55
python3 ingest/ingest_pipeline_outputs.py --case-id CS55
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

Then test, commit, and push as above.

## Common Problems

### New case does not show on the website

Re-run:

```bash
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

Then commit and deploy the updated files in `data/extracted/`.

### Hugging Face rebuilds but old content appears

Check the Space commit SHA:

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
```

Confirm it matches the commit you pushed.

### Drive request upload fails

Check:

- `GOOGLE_SERVICE_ACCOUNT_JSON` exists as a Hugging Face secret
- the Drive folder is shared with the service account email
- the Space has restarted after the secret was added

### LLM key fails

Check the relevant Hugging Face secret:

```text
ANTHROPIC_API_KEY
OPENAI_API_KEY
```

The app currently defaults to Claude for answer generation. The extraction
pipeline can use one provider with `--llm-provider claude` or
`--llm-provider openai`.
