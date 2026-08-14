# 04 - Terminal Command Cheatsheet

This file lists common commands in the order a team member is most likely to
use them.

## Start Work

```bash
cd UWaterlooManagedRetreatChatbot
source venv/bin/activate
git status
git pull origin main
git checkout -b your-branch-name
```

## Run the Website

```bash
streamlit run app/app.py
```

## Check Python Syntax

```bash
python3 -m py_compile app/app.py
python3 -m py_compile rag/pipeline.py
python3 -m py_compile rag/retriever.py
```

## Rebuild All Ingested Case Data

Use this after changing many pipeline outputs:

```bash
python3 ingest/ingest_pipeline_outputs.py
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

## Rebuild One Case

Replace `CS124` with the case ID:

```bash
python3 ingest/ingest_pipeline_outputs.py --case-id CS124
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

## Run One New Case Through the Pipeline

```bash
python3 -m case_study_pipeline.run_case_study \
  --case-folder data/raw/CS124 \
  --case-id CS124 \
  --llm-provider claude \
  --max-chars-per-source 150000 \
  --force
```

Then:

```bash
python3 -m case_study_pipeline.select_best_run --case-id CS124
python3 ingest/ingest_pipeline_outputs.py --case-id CS124
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

## Download Papers from a Registered Case Drive Folder

This uses `case_study_pipeline/drive_folders.json`.

```bash
python3 -m case_study_pipeline.download_drive_papers --case-id CS124
```

## Sort a Downloaded PDF into a Case Folder

```bash
python3 -m case_study_pipeline.sort_inbox --list
```

Then:

```bash
python3 -m case_study_pipeline.sort_inbox \
  --filename "Downloaded Paper.pdf" \
  --case-id CS124 \
  --rename "Author_Year_Short_Title.pdf"
```

## Upload the Current Code to Hugging Face

Preferred if your Hugging Face remote exists:

```bash
git push uwrfr-chatbot HEAD:main
```

If the remote does not exist:

```bash
git remote add uwrfr-chatbot https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
git push uwrfr-chatbot HEAD:main
```

Alternative using the Hugging Face CLI:

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

## Push to Shared GitHub

```bash
git push shared-github HEAD:main
```

If the remote does not exist:

```bash
git remote add shared-github https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot.git
git push shared-github HEAD:main
```

## Check Hugging Face Space Status

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
```

Look for:

- `sha` - deployed commit.
- `runtime.stage` - whether it is running, building, or failed.
- `host` - public app URL.

## See Recent Git History

```bash
git log --oneline -10
```

## See What Changed

```bash
git status
git diff --stat
```

## Undo an Uncommitted Edit to One File

Only do this if you are sure you do not want your local changes to that file:

```bash
git restore path/to/file.py
```

Do not use broad destructive commands like `git reset --hard` unless the team
explicitly agrees.

