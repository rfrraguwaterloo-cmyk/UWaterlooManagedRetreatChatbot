# 06 - Deploying Updates

This guide explains how to get local changes onto GitHub and Hugging Face.

## Recommended Workflow

Use GitHub as the shared source of truth and Hugging Face as the live app host.

The usual flow is:

```text
local computer -> GitHub -> Hugging Face
```

## Before Deploying

Run:

```bash
git status
git diff --stat
python3 -m py_compile app/app.py
```

If you changed case-study data, also run:

```bash
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

If you changed the app, test locally:

```bash
streamlit run app/app.py
```

## Commit the Right Files

For website text/code changes:

```bash
git add app/app.py
git commit -m "Update website"
```

For a new case study:

```bash
git add data/extracted/CS124.json
git add data/extracted/case_summaries.json
git add data/extracted/precomputed_embeddings.json
git add data/raw/CS124/case_meta.json
git add case_study_pipeline/drive_folders.json
git add ingest/source_link_overrides.json
git commit -m "Add CS124 case study"
```

Do not add raw PDFs unless the team explicitly decides to store PDFs in GitHub.

## Push to GitHub

```bash
git push shared-github HEAD:main
```

If working on a branch:

```bash
git push origin your-branch-name
```

Then open a pull request into `main`.

## Push to Hugging Face

Manual push:

```bash
git push uwrfr-chatbot HEAD:main
```

Check status:

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
```

The Hugging Face Space may take a minute to rebuild.

## GitHub Action Deployment

The repo has a GitHub Action:

```text
.github/workflows/deploy-hf-space.yml
```

It can upload the repo to a Hugging Face Space.

For it to work, GitHub needs:

Secret:

```text
HF_TOKEN
```

Variable or workflow input:

```text
HF_SPACE_ID
```

For this project, the target Space is:

```text
UWRFR/UWaterlooRFRChatBot
```

## Files Excluded from Hugging Face Upload

The deployment excludes files such as:

```text
.git/
.github/
venv/
__pycache__/
data/raw/
*.pdf
```

That means raw source PDFs usually stay in Google Drive, while processed JSON
and embeddings are deployed to the website.

## After Deploying

Open:

```text
https://uwrfr-uwaterloorfrchatbot.hf.space
```

Check:

- The website loads.
- The navigation works.
- New case studies appear.
- Source links appear.
- A test question works.
- Previous Responses still work.

