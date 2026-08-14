# 05 - Debugging Common Problems

This guide lists common failures and what to check first.

## The Website Does Not Load

Check Hugging Face logs:

```text
Hugging Face Space -> Logs
```

Common causes:

- Build failed.
- Missing dependency in `requirements.txt`.
- Python syntax error.
- Missing required file.
- Space is still rebuilding.

CLI check:

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
```

If the Space is building, wait and refresh.

## Ask Tab Fails with an LLM Error

Common messages:

```text
credit balance is too low
ANTHROPIC_API_KEY is not set
OPENAI_API_KEY is not set
APIConnectionError
invalid_api_key
```

Check:

- The correct key exists in Hugging Face secrets.
- The key has credits.
- The app is configured for the provider you expect.
- The Space was restarted after changing secrets.

If Anthropic credits are unavailable, switch the app to OpenAI only if
`OPENAI_API_KEY` is available and configured.

## New Case Study Request Upload Fails

The request tab uploads to Google Drive using:

```text
GOOGLE_SERVICE_ACCOUNT_JSON
```

Check:

- The secret exists in Hugging Face.
- The secret value is the full service account JSON.
- The intake folder is shared with the service account email.
- The intake folder ID is correct:

```text
10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y
```

If using a different folder, set:

```text
RFR_REQUESTS_DRIVE_FOLDER_ID
```

## New Case Does Not Appear in Case Studies

Usually one of these files was not rebuilt or committed:

```text
data/extracted/CSxx.json
data/extracted/case_summaries.json
data/extracted/precomputed_embeddings.json
```

Run:

```bash
python3 ingest/ingest_pipeline_outputs.py --case-id CSxx
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

Then commit and push the changed files.

## Case Appears but Sources Are Missing

The Case Studies tab reads source links from each case's `source_links` field in
`data/extracted/CSxx.json`.

Source links come from:

- `sources.txt`
- `sources.json`
- `dois.txt`
- `ingest/source_link_overrides.json`

Fix:

1. Add APA-style links to `ingest/source_link_overrides.json`.
2. Re-run:

```bash
python3 ingest/ingest_pipeline_outputs.py --case-id CSxx --force
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

3. Commit and push.

## Case Summary Looks Wrong

Check the canonical Ver2 memo:

```text
data/raw/CSxx/pipeline_output/CSxx_Ver2.md
```

If the wrong paper was processed, replace the source files in:

```text
data/raw/CSxx/
```

Then rerun:

```bash
python3 -m case_study_pipeline.run_case_study \
  --case-folder data/raw/CSxx \
  --case-id CSxx \
  --llm-provider claude \
  --max-chars-per-source 150000 \
  --force
```

Then select, ingest, summarize, and embed:

```bash
python3 -m case_study_pipeline.select_best_run --case-id CSxx
python3 ingest/ingest_pipeline_outputs.py --case-id CSxx --force
python3 ingest/create_summary_chunks.py
python3 ingest/embed_and_index.py
```

## Hugging Face Shows Old Content

Check the deployed commit:

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
```

Compare the `sha` with:

```bash
git log --oneline -5
```

If the Hugging Face SHA is old, push again:

```bash
git push uwrfr-chatbot HEAD:main
```

## Git Push Fails

Check remotes:

```bash
git remote -v
```

Expected remotes:

```text
shared-github https://github.com/rfrraguwaterloo-cmyk/UWaterlooManagedRetreatChatbot.git
uwrfr-chatbot https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
```

If authentication fails:

- For GitHub, sign in with GitHub credentials or a GitHub token.
- For Hugging Face, run:

```bash
hf auth login --add-to-git-credential
```

Use a Hugging Face token with write access to the Space.

## Drive Pipeline Output Upload Fails

The extraction pipeline can still run locally even if Drive output uploads fail.

Common warning:

```text
[Drive] Warning: could not initialize uploader
Drive uploads will be skipped for this run.
```

This means the local files were created, but the PDF outputs were not uploaded
to Drive.

Check:

- `GOOGLE_CREDENTIALS_FILE` points to an OAuth client credential file.
- Your browser completed Google login.
- The target case folder exists in `case_study_pipeline/drive_folders.json`.
- The Google account has permission to write to the Drive folder.

