#!/usr/bin/env python3
"""
Run "Check 1" for one case study: send Prompt B (the independent-auditor
prompt from prompts.py) to ChatGPT/OpenAI, auditing <CASE_ID>_Ver1.md against
that case study's original sources, the codebook, and the note-taking
guidelines.

Use this when Version 1 was already produced separately (e.g. Claude wrote it
by hand in a chat instead of through the Anthropic API) and you just need the
OpenAI audit + score. For the full 4-step pipeline (generate Version 1 too),
use run_case_study.py instead.

HOW TO USE
----------
1. Make sure OPENAI_API_KEY is set, either in rfr-rag/.env or as an
   environment variable.
2. Run from the repo root, filling in your case study's ID:

       python -m case_study_pipeline.run_check1 --case-id CS11

Outputs (written next to the Version 1 document):
    data/raw/<CASE_ID>/pipeline_output/<CASE_ID>_Check1_report.md
    data/raw/<CASE_ID>/pipeline_output/<CASE_ID>_Check1_report.pdf
and prints the FINAL GRADE extracted from the report.
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
            "data/raw/<CASE_ID>/pipeline_output/<CASE_ID>_Ver1.md."
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
        help="Where the Version 1 document lives and the report is written (default: <case-folder>/pipeline_output).",
    )
    parser.add_argument(
        "--openai-model",
        default=None,
        help=(
            f"OpenAI model for the audit (default: {DEFAULT_OPENAI_MODEL}). "
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
        help="Google Drive folder ID to upload the Check 1 report PDF to after it is written. "
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
            version=1,
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
