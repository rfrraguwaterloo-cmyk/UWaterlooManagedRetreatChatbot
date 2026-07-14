#!/usr/bin/env python3
"""
Run "Check 2" for one case study: send Prompt B (the independent-auditor
prompt from prompts.py) to ChatGPT/OpenAI as a fresh, standalone call --
auditing <CASE_ID>_Ver2.md against that case study's original sources, the
codebook, and the note-taking guidelines.

Use this when Version 2 was already produced separately (e.g. Claude revised
it by hand in a chat instead of through the Anthropic API) and you just need
the OpenAI audit + score. For the full 4-step pipeline (generate both versions
too), use run_case_study.py instead.

This is intentionally a fresh, separate call (not a continuation of Check 1):
  - It audits <CASE_ID>_Ver2.md (the revised document), not Ver1.
  - It has no memory of the Check 1 conversation -- it's a brand new API call
    with no prior messages, matching the pipeline's "no memory" requirement
    for Check 2.
  - If <CASE_ID>_Check1_report.md already exists, its grade is printed
    alongside the Check 2 grade so you can see the change.

HOW TO USE
----------
1. Make sure OPENAI_API_KEY is set, either in rfr-rag/.env or as an
   environment variable.
2. Run from the repo root, filling in your case study's ID:

       python -m case_study_pipeline.run_check2 --case-id CS11

Outputs (written next to the Version 2 document):
    data/raw/<CASE_ID>/pipeline_output/<CASE_ID>_Check2_report.md
    data/raw/<CASE_ID>/pipeline_output/<CASE_ID>_Check2_report.pdf
and prints the FINAL GRADE extracted from the report, plus the
Check 1 -> Check 2 grade change if a Check 1 report is present.
"""

from __future__ import annotations

import argparse
import sys

from .drive_upload import make_uploader
from .llm_clients import DEFAULT_MAX_TOKENS, DEFAULT_OPENAI_MODEL
from .standalone_audit import run_standalone_audit


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--case-id",
        required=True,
        help=(
            "Case study ID to audit, e.g. CS11. Looks for "
            "data/raw/<CASE_ID>/pipeline_output/<CASE_ID>_Ver2.md."
        ),
    )
    parser.add_argument(
        "--case-folder",
        default=None,
        help="Folder containing this case study's source documents (default: data/raw/<CASE_ID>).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Where the Version 2 document lives and the report is written (default: <case-folder>/pipeline_output).",
    )
    parser.add_argument(
        "--openai-model",
        default=None,
        help=(
            f"OpenAI model for the audit (default: {DEFAULT_OPENAI_MODEL}). "
            "Use the same model as Check 1 for an apples-to-apples comparison. "
            "If you hit rate limits on a long prompt, try a smaller model, "
            "e.g. --openai-model gpt-4o-mini."
        ),
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max output tokens for the audit response (default: {DEFAULT_MAX_TOKENS}).",
    )
    parser.add_argument(
        "--max-chars-per-source",
        type=int,
        default=120_000,
        help="Truncate each source file's extracted text to this many characters (default: 120000; use 0 for no limit).",
    )
    parser.add_argument(
        "--drive-folder-id",
        default=None,
        help="Google Drive folder ID to upload the Check 2 report PDF to after it is written. "
             "If omitted, Drive upload is skipped.",
    )
    parser.add_argument(
        "--drive-credentials",
        default=None,
        help="Path to your Google OAuth2 credentials.json file. "
             "Falls back to the GOOGLE_CREDENTIALS_FILE env var if not set.",
    )
    args = parser.parse_args(argv)

    try:
        uploader = make_uploader(
            folder_id=args.drive_folder_id,
            credentials_file=args.drive_credentials,
        )
        run_standalone_audit(
            case_id=args.case_id,
            version=2,
            case_folder=args.case_folder,
            output_dir=args.output_dir,
            openai_model=args.openai_model,
            max_tokens=args.max_tokens,
            max_chars_per_source=args.max_chars_per_source or None,
            uploader=uploader,
        )
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
