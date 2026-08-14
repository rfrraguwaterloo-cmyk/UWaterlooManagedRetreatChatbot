# 02 - Hugging Face, Secrets, and API Keys

This guide explains where the live website runs and how API keys are managed.

## Where the Website Runs

The live website is a Hugging Face Space:

```text
https://huggingface.co/spaces/UWRFR/UWaterlooRFRChatBot
```

The public app URL is:

```text
https://uwrfr-uwaterloorfrchatbot.hf.space
```

Hugging Face stores:

- The deployed app code.
- Space settings.
- Runtime logs.
- Variables and secrets.
- The mounted storage bucket, if enabled.

## How to See Space Logs

1. Open the Hugging Face Space.
2. Click **Logs** near the top of the Space page.
3. Look for Python errors, missing secrets, API failures, or build errors.

Useful CLI command:

```bash
hf spaces info UWRFR/UWaterlooRFRChatBot
```

This shows the current commit SHA and runtime state.

## Hugging Face Variables and Secrets

Go to:

```text
Hugging Face Space -> Settings -> Variables and secrets
```

Use **Variables** for non-sensitive values.

Use **Secrets** for private values, such as API keys.

Important: Hugging Face does not show the value of an existing secret after it
is saved. You can see that the secret exists, but you cannot reveal the stored
key. If a key is lost or wrong, replace the secret with a new value.

## Required Secrets

For LLM answers:

```text
ANTHROPIC_API_KEY
```

or, if using OpenAI:

```text
OPENAI_API_KEY
OPENAI_MODEL
```

For Google Drive request uploads:

```text
GOOGLE_SERVICE_ACCOUNT_JSON
```

Optional override for the new case study request intake folder:

```text
RFR_REQUESTS_DRIVE_FOLDER_ID
```

Current request intake folder ID:

```text
10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y
```

## What Each Secret Does

### `ANTHROPIC_API_KEY`

Used by the chatbot when the app is configured to answer with Claude.

If this key is missing, expired, or has no credits, the Ask tab can fail.

### `OPENAI_API_KEY`

Used when the app or local pipeline is configured to use OpenAI.

If using OpenAI, also set:

```text
OPENAI_MODEL
```

Example:

```text
gpt-4o-mini
```

### `GOOGLE_SERVICE_ACCOUNT_JSON`

Used by the website to upload New Case Study Requests into Google Drive.

This should contain the full JSON service account credential, not just the
service account email.

The Drive intake folder must be shared with the service account email. If it is
not shared, uploads will fail even if the secret is present.

## How to Add or Replace a Secret

1. Open the Hugging Face Space.
2. Click **Settings**.
3. Scroll to **Variables and secrets**.
4. Click **New secret**.
5. Enter the exact name, such as `ANTHROPIC_API_KEY`.
6. Paste the value.
7. Save.
8. Restart or rebuild the Space if needed.

## How to Check Whether a Secret Is the Problem

Open Space logs and look for messages like:

```text
ANTHROPIC_API_KEY is not set
OPENAI_API_KEY is not set
GOOGLE_SERVICE_ACCOUNT_JSON is not set
credit balance is too low
invalid_api_key
permission denied
```

For Drive upload problems, check:

- The `GOOGLE_SERVICE_ACCOUNT_JSON` secret exists.
- It is valid JSON.
- The Drive intake folder is shared with the service account email.
- The Space was restarted after the secret was added.

## Do Not Put API Keys in GitHub

Never commit API keys to:

- `README.md`
- `.env`
- Python files
- Markdown docs
- screenshots

Use Hugging Face secrets for the live website.

Use a local `.env` file for your own computer. Do not commit `.env`.

