# 03 - New Case Study Requests from Google Drive

This guide explains how a submitted New Case Study Request becomes a processed
case study in the website.

## Request Intake Folder

New requests from the website are saved in this Google Drive folder:

```text
https://drive.google.com/drive/u/3/folders/10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y
```

Folder ID:

```text
10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y
```

Each website submission creates a new folder inside that intake folder.

Each submitted request folder should contain:

- `request.json`
- uploaded PDFs or source documents, if the user attached any

The request form only collects materials. It does not run the LLM extraction
pipeline automatically.

## Documentation Folder

These instructions are stored in this Google Drive folder:

```text
https://drive.google.com/drive/u/3/folders/1ZEb9riZZM9qWLYT70KzhdGzygsQHozYM
```

## Step 1: Review a Submitted Request

Open the request intake folder and choose a submitted request folder.

Read:

```text
request.json
```

Check:

- Case study name.
- Location and country.
- Why the case should be added.
- Source links.
- Uploaded PDFs.
- Whether the case already exists in `data/raw/` or `data/extracted/`.

## Step 2: Choose a Case ID

Processed cases currently appear in:

```text
data/extracted/
```

Existing raw/backlog case folders appear in:

```text
data/raw/
```

Commands:

```bash
ls data/extracted/CS*.json | sort -V | tail
find data/raw -maxdepth 1 -type d -name "CS*" | sort -V | tail
```

If the request is a brand-new case that is not already in the backlog, use the
next unused case ID after the existing backlog.

For example, if the repo already has folders up to `CS123`, use:

```text
CS124
```

If the request matches an existing backlog case, use that existing case ID
instead.

## Step 3: Set Up the Case Locally from the Request Folder

The helper script can create a local case folder, create/register the matching
case Drive folder, and copy PDFs from the submitted request folder.

You need a Google OAuth client secret file on your computer, usually named like:

```text
client_secret_....json
```

Run:

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

Replace:

- `124` with the chosen case number.
- Name, country, hazard, stage, and actors with the submitted case details.
- `<REQUEST_FOLDER_ID>` with the Google Drive folder for that request.

The first time you use the Drive script, your browser may ask you to sign in and
approve Google Drive access.

## Step 4: Check the Created Files

The script creates:

```text
data/raw/CS124/
data/raw/CS124/case_meta.json
data/raw/CS124/CS124_paper_discovery_prompt.md
```

It also copies uploaded PDFs into:

```text
data/raw/CS124/
```

Open and edit `case_meta.json` if needed:

```json
{
  "case_id": "CS124",
  "name": "Newtok to Mertarvik",
  "location": "Newtok / Mertarvik, Alaska",
  "country": "United States"
}
```

## Step 5: Add Source Links for the Website

The Case Studies tab displays source links from the extracted JSON.

Source links are collected from:

- `sources.txt`
- `sources.json`
- `dois.txt`
- `ingest/source_link_overrides.json`

For clean APA-style links, add an entry to:

```text
ingest/source_link_overrides.json
```

Example:

```json
"CS124": [
  {
    "title": "Bronen, R., & Chapin, F. S. III. (2013). Adaptive governance and institutional strategies for climate-induced community relocations in Alaska. Proceedings of the National Academy of Sciences, 110(23), 9320-9325. https://doi.org/10.1073/pnas.1210508110",
    "doi": "10.1073/pnas.1210508110",
    "url": "https://doi.org/10.1073/pnas.1210508110"
  }
]
```

Then re-run ingestion after the extraction pipeline finishes.

## Step 6: Run the Extraction Pipeline

Use one LLM provider for the whole run. Claude is the current simplest path.

```bash
python3 -m case_study_pipeline.run_case_study \
  --case-folder data/raw/CS124 \
  --case-id CS124 \
  --llm-provider claude \
  --max-chars-per-source 150000 \
  --force
```

This creates:

```text
data/raw/CS124/pipeline_output/CS124_Ver1.md
data/raw/CS124/pipeline_output/CS124_Check1_report.md
data/raw/CS124/pipeline_output/CS124_Ver2.md
data/raw/CS124/pipeline_output/CS124_Check2_report.md
```

## Step 7: Select, Ingest, Embed

```bash
python3 -m case_study_pipeline.select_best_run --case-id CS124
python3 ingest/ingest_pipeline_outputs.py --case-id CS124
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

These create or update:

```text
data/extracted/CS124.json
data/extracted/case_summaries.json
data/extracted/precomputed_embeddings.json
```

## Step 8: Test Locally

```bash
streamlit run app/app.py
```

Check:

- The case appears in the Case Studies tab.
- Source links appear.
- A direct question works, such as `Summarize CS124`.
- The answer cites the right case.

## Step 9: Commit and Deploy

Commit the app-facing files:

```bash
git status
git add data/extracted/CS124.json
git add data/extracted/case_summaries.json
git add data/extracted/precomputed_embeddings.json
git add data/raw/CS124/case_meta.json
git add case_study_pipeline/drive_folders.json
git add ingest/source_link_overrides.json
git commit -m "Add CS124 case study"
```

Usually do not commit raw PDFs unless the team explicitly wants them in GitHub.
Keep source PDFs in Google Drive.

Push to GitHub and Hugging Face:

```bash
git push shared-github HEAD:main
git push uwrfr-chatbot HEAD:main
```

