# Case Study Processing Pipeline

Automates the 4-step managed retreat case study workflow:

1. **Claude** generates a narrative case-study questionnaire document (**Version 1**)
   from the RFR questionnaire, codebook, cross-cutting themes guide, note-taking
   guidelines, and a folder of source documents for one case study.
2. **ChatGPT** audits Version 1 against the sources and codebook (**Check 1**),
   producing a scored report (0-100).
3. **Claude** revises Version 1 into **Version 2** using the Check 1 feedback.
4. **ChatGPT** audits Version 2 in a fresh, standalone call with no memory of
   Check 1 (**Check 2**), producing another scored report so you can compare
   Check 1 vs. Check 2 to measure improvement.

## Setup

1. Make sure `rfr-rag/.env` has both keys:
   ```
   ANTHROPIC_API_KEY=...
   OPENAI_API_KEY=...
   ```
2. Install dependencies (adds `fpdf2` to the existing requirements):
   ```bash
   pip install -r requirements.txt
   ```

## Context documents

The `context/` folder contains the shared reference material used in every run:

- `ai_questionnaire.md` — the RFR coding questions
- `codebook.md` — the RFR codebook (categories, codes, descriptions)
- `cross_cutting_guide.md` — the RFR cross-cutting themes guide
- `note_taking_guidelines.md` — the RFR note-taking guidelines for LLMs

These were generated from the RFR Drive docs. If the team updates those docs,
re-export them (File > Download > Plain text for Google Docs, or re-export the
codebook spreadsheet) and overwrite the corresponding file here.

## Usage

For any case study, put its source documents (PDFs of papers/reports; `.txt`/`.md`
also supported) in their own folder, then run:

```bash
python -m case_study_pipeline.run_case_study --case-folder data/raw/CS6
```

This writes to `data/raw/CS6/pipeline_output/` by default:

- `CS6_Ver1.md` / `CS6_Ver1.pdf` — initial questionnaire document
- `CS6_Check1_report.md` / `.pdf` — Check 1 audit report + grade
- `CS6_Ver2.md` / `.pdf` — revised questionnaire document
- `CS6_Check2_report.md` / `.pdf` — Check 2 audit report + grade

A summary with both grades and the change is printed at the end.

### Useful options

```bash
python -m case_study_pipeline.run_case_study \
  --case-folder data/raw/CS6 \
  --case-id CS6 \                 # defaults to the folder name
  --output-dir outputs/CS6 \      # defaults to <case-folder>/pipeline_output/
  --claude-model claude-sonnet-4-6 \
  --openai-model gpt-5.4-mini \
  --max-tokens 8000 \             # max output tokens per LLM call
  --max-chars-per-source 120000 \ # truncate very long source files (0 = no limit)
  --force                         # overwrite existing output files without asking
```

By default, if an output PDF already exists you'll be asked to confirm before it's
overwritten (the `.md` files are always (re)written so you don't lose the run, but
existing PDFs are kept unless you confirm or pass `--force`).

## Running just the audit step (Check 1 / Check 2 only)

Sometimes Version 1 or Version 2 of a case study's questionnaire document is written
by hand (e.g. Claude generated it directly in a chat, without calling the Anthropic
API). In that situation you don't need to re-run the whole pipeline -- you just need
ChatGPT/OpenAI to audit the existing document and produce a scored report.

```bash
# Audit data/raw/CS11/pipeline_output/CS11_Ver1.md
python -m case_study_pipeline.run_check1 --case-id CS11

# Audit data/raw/CS11/pipeline_output/CS11_Ver2.md (also compares against the
# Check 1 grade, if a CS11_Check1_report.md is already there)
python -m case_study_pipeline.run_check2 --case-id CS11
```

`--case-id` is the only required option -- it's how you tell the script which case
study to audit (e.g. `CS6`, `CS11`, ...). Both scripts accept the same `--case-folder`,
`--output-dir`, `--openai-model`, `--max-tokens`, and `--max-chars-per-source` options
as `run_case_study.py`. Each writes `<CASE_ID>_Check1_report.{md,pdf}` or
`<CASE_ID>_Check2_report.{md,pdf}` into the case study's `pipeline_output/` folder.

Requires `OPENAI_API_KEY` (in `rfr-rag/.env` or the environment) -- no Anthropic key
needed for these two scripts.

## High-precision paper discovery

Use `discover_sources.py` before running the extraction pipeline when a case
needs source cleanup, DOI lookup, or supplemental paper discovery.

```bash
python3 -m case_study_pipeline.discover_sources --case-id CS36
python3 -m case_study_pipeline.discover_sources \
  --case-id CS36 \
  --alias "Pitt County" \
  --alias "Hurricane Floyd"
```

The discovery command is deliberately conservative:

- Existing `sources.txt` / `dois.txt` entries are treated as accepted seed
  sources, but still resolved through scholarly metadata APIs where possible.
- New search results are not silently accepted. They are classified as
  `review_required` or `rejected_by_identity_filter`.
- Direct case evidence must match the core place identity, such as the village,
  city, resettlement name, province/state, and country from the spreadsheet or
  `case_meta.json`.
- National/provincial/local legal and policy papers can be surfaced as
  `candidate_policy_context`, but they stay separate from direct case evidence.

The command writes:

```text
data/raw/<CASE>/
├── sources.json                 # structured accepted seed sources
├── paper_candidates.json         # all candidates with evidence/scoring
└── paper_discovery_report.md     # human-readable review report
```

Recommended review rule: only use `accepted_seed` sources and manually approved
`review_required` candidates in the LLM extraction. Do not use rejected/background
papers unless a human reclassifies them after reading the full text.

## Automated source acquisition

After discovery, run `acquire_sources.py` to populate the case folder with source
files the extraction pipeline can read:

```bash
python3 -m case_study_pipeline.acquire_sources --case-id CS39
python3 -m case_study_pipeline.acquire_sources \
  --case-id CS38 \
  --extra-url "https://www.academia.edu/37237146/Heritage_and_Postdisaster_Recovery_Indigenous_Community_Resilience"
```

This command prefers publisher/open-access PDFs, then falls back to a
provenance-labelled `.md` capture when the PDF is blocked but the article/report
text is publicly reachable. That fallback is intentional: the extraction
pipeline reads `.pdf`, `.txt`, and `.md`, so a full-text markdown capture is
better than stopping the pipeline on a missing PDF. Use the generated
`source_acquisition_report.json` to see what was acquired.

If a publisher PDF is paywalled and no public full-text route is available, the
script will not bypass access controls. In that case, the non-manual route is to
add an authorized/open URL with `--extra-url`, or use the EZproxy/browser flow
below for institutional access.

## Session notes

`session_notes/` holds one-off "continue this work" notes written for specific case
studies (for example, a note describing how CS11's Version 1 document was produced
by hand). These are historical records, not part of the reusable pipeline -- the
scripts above work for any case study ID.

## Notes

- Source PDFs are read with `pdfplumber` (already a project dependency).
- Output PDFs are generated with `fpdf2` from the LLM's narrative text. Smart
  quotes/dashes are converted to plain ASCII for compatibility with the built-in
  PDF fonts.
- "No memory" for Check 2: each ChatGPT call in this pipeline is a single
  standalone request (system + user message only, no prior turns or
  `previous_response_id`). The Chat Completions API has no per-conversation memory
  by default, so Check 2 is independent of Check 1 by construction — there's no
  separate toggle to flip.

## Fetching paywalled papers via UWaterloo EZproxy (Chrome-assisted)

For papers that `fetch_papers.py` can't get through Unpaywall / Sci-Hub /
Semantic Scholar (i.e. paywalled, behind a major publisher), use UWaterloo's
institutional library access. **This cannot be fully scripted** — WatIAM
requires Duo two-factor authentication, which only a human can complete. The
workflow below uses the Claude-in-Chrome browser extension to drive an
already-logged-in browser session, with the actual login/Duo step done by
the user once per browser session (sessions last several hours).

### One-time setup (per machine)

In Chrome, go to `chrome://settings/downloads` and set:

- **Location:** `/Users/AnnaZhou/rfr-rag/data/raw/_inbox`
- **"Ask where to save each file before downloading"** — turn this **OFF**

This makes every PDF download save automatically into the repo's inbox
folder with no save dialog, so an agent driving the browser can trigger a
download and immediately find the file on disk (this folder is gitignored
via `data/raw/` in `.gitignore`).

### Recurring procedure (every session, every case study)

1. Run `fetch_papers.py` first — it handles every paper it can without
   needing institutional access:
   ```
   python3 -m case_study_pipeline.fetch_papers --case-id CS13
   ```
2. For DOIs that still fail, use UWaterloo EZproxy through Chrome:
   - Navigate to `https://login.proxy.lib.uwaterloo.ca/login?qurl=<any target URL>`
     and click "Using WatIAM". **Ask the user to enter credentials and
     approve Duo themselves** — never enter passwords for them.
   - Once logged in, for each remaining DOI:
     a. Navigate to `https://doi.org/<DOI>` — this redirects to the
        publisher's real article URL.
     b. Convert that URL to its EZproxy form using the dash-domain rule
        (see `case_study_pipeline/ezproxy.py`):
        `link.springer.com` → `link-springer-com.proxy.lib.uwaterloo.ca`
        `agupubs.onlinelibrary.wiley.com` → `agupubs-onlinelibrary-wiley-com.proxy.lib.uwaterloo.ca`
        (any publisher domain follows this same pattern)
     c. Navigate to the EZproxy URL, use `find` to locate the "Download PDF"
        link, and click it. The PDF lands in `data/raw/_inbox/` automatically
        (no dialog, because of the one-time Chrome setting above).
     d. Check the inbox and file it away:
        ```
        python3 -m case_study_pipeline.sort_inbox --list
        python3 -m case_study_pipeline.sort_inbox \
            --filename "<exact name in inbox>" \
            --case-id CS13 \
            --rename "Author_Year_Journal_FULLTEXT.pdf"
        ```
        This moves the PDF into `data/raw/CS13/` and uploads it to the
        correct Drive folder automatically (via `drive_folders.json` +
        `drive_upload.py` — same OAuth token already set up for the
        pipeline's own output uploads).
3. The EZproxy session stays alive in the browser for the rest of the
   working session — no need to re-login for subsequent papers/case studies
   unless the session expires (multi-hour timeout) or Chrome is restarted.
