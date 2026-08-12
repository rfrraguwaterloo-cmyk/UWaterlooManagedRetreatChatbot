#!/usr/bin/env python3
"""
Managed retreat case study processing pipeline.

Pipeline:
  1. Claude generates a narrative case-study questionnaire document (Version 1)
     from the RFR questionnaire/codebook/guides + a folder of source documents
     for one case study.
  2. ChatGPT audits Version 1 against the sources and codebook ("Check 1"),
     producing a scored report.
  3. Claude revises Version 1 into Version 2 using the Check 1 report.
  4. ChatGPT audits Version 2 with a fresh, standalone call ("Check 2", no
     memory of Check 1), producing a scored report -> compare scores to measure
     improvement.

Usage:
    python -m case_study_pipeline.run_case_study --case-folder data/raw/CS6 [options]

Reusable for any case study: pass any folder containing that case study's source
PDFs (papers, reports, etc.) via --case-folder.

Use --llm-provider claude or --llm-provider openai to run all four steps with
one provider/key instead of the default mixed Claude + ChatGPT workflow.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pdf_utils, prompts
from .drive_upload import make_uploader, try_upload
from .onboard_case_study import get_folder_id
from .grading import extract_grade
from .llm_clients import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_OPENAI_MODEL,
    query_claude,
    query_openai,
)

CONTEXT_DIR = Path(__file__).resolve().parent / "context"


def provider_label(provider: str) -> str:
    if provider == "openai":
        return "ChatGPT"
    if provider == "claude":
        return "Claude"
    return provider


def query_provider(
    provider: str,
    prompt: str,
    args: argparse.Namespace,
) -> str:
    if provider == "openai":
        return query_openai(prompt, model=args.openai_model, max_tokens=args.max_tokens)
    if provider == "claude":
        return query_claude(prompt, model=args.claude_model, max_tokens=args.max_tokens)
    raise ValueError(f"Unsupported LLM provider: {provider}")


def step_provider(args: argparse.Namespace, step: str) -> str:
    if args.llm_provider in {"claude", "openai"}:
        return args.llm_provider
    if step in {"ver1", "ver2"}:
        return "claude"
    return "openai"


def load_context_docs() -> dict[str, str]:
    files = {
        "ai_questionnaire": "ai_questionnaire.md",
        "codebook": "codebook.md",
        "cross_cutting_guide": "cross_cutting_guide.md",
        "note_taking_guidelines": "note_taking_guidelines.md",
    }
    docs = {}
    for key, filename in files.items():
        path = CONTEXT_DIR / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Missing context file: {path}\n"
                "Expected the RFR questionnaire/codebook/guides under "
                "case_study_pipeline/context/."
            )
        docs[key] = path.read_text(encoding="utf-8")
    return docs


def confirm_overwrite(path: Path, force: bool) -> bool:
    """Return True if it's OK to write to `path`."""
    if not path.exists():
        return True
    if force:
        return True
    answer = input(f"'{path}' already exists. Overwrite? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def write_outputs(
    output_dir: Path,
    case_id: str,
    name: str,
    text: str,
    title: str,
    force: bool,
) -> tuple[Path | None, Path]:
    """Write `text` as both .md and (if confirmed) a rendered .pdf. Returns (pdf_path_or_None, md_path)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"{case_id}_{name}.md"
    pdf_path = output_dir / f"{case_id}_{name}.pdf"

    md_path.write_text(text, encoding="utf-8")

    if confirm_overwrite(pdf_path, force):
        pdf_utils.text_to_pdf(text, pdf_path, title=title)
        return pdf_path, md_path
    else:
        print(f"  Skipped writing {pdf_path} (kept existing file).")
        return None, md_path


def run(args: argparse.Namespace) -> None:
    case_folder = Path(args.case_folder).resolve()
    case_id = args.case_id or case_folder.name
    output_dir = Path(args.output_dir).resolve() if args.output_dir else case_folder / "pipeline_output"

    print(f"Case ID: {case_id}")
    print(f"Source documents folder: {case_folder}")
    print(f"Output folder: {output_dir}")

    # Resolve Drive folder: CLI flag > drive_folders.json lookup > env var
    drive_folder_id = getattr(args, "drive_folder_id", None) or get_folder_id(case_id)
    uploader = make_uploader(
        folder_id=drive_folder_id,
        credentials_file=getattr(args, "drive_credentials", None),
    )

    print("\nLoading RFR context documents (questionnaire, codebook, guides)...")
    context = load_context_docs()

    print("Extracting text from source documents...")
    source_documents = pdf_utils.extract_source_documents(
        case_folder, max_chars_per_file=args.max_chars_per_source
    )
    print(f"  -> {len(source_documents):,} characters of source text")

    ver1_provider = step_provider(args, "ver1")
    check1_provider = step_provider(args, "check1")
    ver2_provider = step_provider(args, "ver2")
    check2_provider = step_provider(args, "check2")

    # --- Step 1: Generate Version 1 ---------------------------------------
    print(f"\n[1/4] {provider_label(ver1_provider)}: generating Version 1 (initial questionnaire document)...")
    prompt_a = prompts.build_prompt_a(
        case_id=case_id,
        ai_questionnaire=context["ai_questionnaire"],
        codebook=context["codebook"],
        cross_cutting_guide=context["cross_cutting_guide"],
        note_taking_guidelines=context["note_taking_guidelines"],
        source_documents=source_documents,
    )
    version_1 = query_provider(ver1_provider, prompt_a, args)
    pdf1, md1 = write_outputs(output_dir, case_id, "Ver1", version_1, f"{case_id} - Case Study Questionnaire (Version 1)", args.force)
    print(f"  -> {md1}" + (f"\n  -> {pdf1}" if pdf1 else ""))
    try_upload(uploader, pdf1)

    # --- Step 2: Check 1 ---------------------------------------------------
    print(f"\n[2/4] {provider_label(check1_provider)}: Check 1 (auditing Version 1)...")
    check_source = source_documents
    if args.max_check_source_chars and len(check_source) > args.max_check_source_chars:
        check_source = check_source[:args.max_check_source_chars]
        print(f"  [Note] Source text truncated to {args.max_check_source_chars:,} chars for audit checks (use --max-check-source-chars 0 to disable)")
    prompt_b1 = prompts.build_prompt_b(
        case_id=case_id,
        version_label="Version 1 (initial draft)",
        case_study_document=version_1,
        codebook=context["codebook"],
        note_taking_guidelines=context["note_taking_guidelines"],
        source_documents=check_source,
    )
    check_1 = query_provider(check1_provider, prompt_b1, args)
    check1_pdf, check1_md = write_outputs(output_dir, case_id, "Check1_report", check_1, f"{case_id} - Check 1 Report", args.force)
    check_1_grade = extract_grade(check_1)
    print(f"  -> {check1_md}")
    print(f"  Check 1 grade: {check_1_grade}/100")
    try_upload(uploader, check1_pdf)

    # --- Step 3: Revise into Version 2 ------------------------------------
    print(f"\n[3/4] {provider_label(ver2_provider)}: revising into Version 2 using Check 1 feedback...")
    prompt_revision = prompts.build_prompt_revision(
        case_id=case_id,
        version_1_document=version_1,
        check_1_report=check_1,
        ai_questionnaire=context["ai_questionnaire"],
        codebook=context["codebook"],
        cross_cutting_guide=context["cross_cutting_guide"],
        note_taking_guidelines=context["note_taking_guidelines"],
        source_documents=source_documents,
    )
    version_2 = query_provider(ver2_provider, prompt_revision, args)
    pdf2, md2 = write_outputs(output_dir, case_id, "Ver2", version_2, f"{case_id} - Case Study Questionnaire (Version 2)", args.force)
    print(f"  -> {md2}" + (f"\n  -> {pdf2}" if pdf2 else ""))
    try_upload(uploader, pdf2)

    # --- Step 4: Check 2 (fresh call, no memory of Check 1) ----------------
    print(f"\n[4/4] {provider_label(check2_provider)}: Check 2 (fresh audit of Version 2, no memory of Check 1)...")
    prompt_b2 = prompts.build_prompt_b(
        case_id=case_id,
        version_label="Version 2 (revised)",
        case_study_document=version_2,
        codebook=context["codebook"],
        note_taking_guidelines=context["note_taking_guidelines"],
        source_documents=check_source,
    )
    # New, standalone call: no prior messages are passed, so this call has no
    # memory of Check 1.
    check_2 = query_provider(check2_provider, prompt_b2, args)
    check2_pdf, check2_md = write_outputs(output_dir, case_id, "Check2_report", check_2, f"{case_id} - Check 2 Report", args.force)
    check_2_grade = extract_grade(check_2)
    print(f"  -> {check2_md}")
    print(f"  Check 2 grade: {check_2_grade}/100")
    try_upload(uploader, check2_pdf)

    # --- Summary -------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"Case {case_id} complete.")
    print(f"  Check 1 grade (Version 1): {check_1_grade}/100")
    print(f"  Check 2 grade (Version 2): {check_2_grade}/100")
    try:
        delta = int(check_2_grade) - int(check_1_grade)
        print(f"  Change: {delta:+d}")
    except ValueError:
        pass
    print(f"  All outputs written to: {output_dir}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--case-folder",
        required=True,
        help="Folder containing this case study's source documents (.pdf, .txt, .md).",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Case ID label (defaults to the case folder's name, e.g. CS6).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Where to write outputs (defaults to '<case-folder>/pipeline_output/').",
    )
    parser.add_argument("--claude-model", default=DEFAULT_CLAUDE_MODEL, help=f"Claude model (default: {DEFAULT_CLAUDE_MODEL})")
    parser.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL, help=f"OpenAI model (default: {DEFAULT_OPENAI_MODEL})")
    parser.add_argument(
        "--llm-provider",
        choices=("mixed", "claude", "openai"),
        default="mixed",
        help="Provider routing for the 4-step workflow. 'mixed' uses Claude for Ver1/Ver2 and OpenAI for checks; "
             "'claude' or 'openai' uses one provider for all four steps.",
    )
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS, help=f"Max output tokens per LLM call (default: {DEFAULT_MAX_TOKENS})")
    parser.add_argument(
        "--max-check-source-chars",
        type=int,
        default=80_000,
        help="Truncate source documents to this many characters when sending to ChatGPT checks "
             "(default: 80000 ≈ 20k tokens). Claude steps always get the full source text. "
             "Use 0 to disable truncation.",
    )
    parser.add_argument(
        "--max-chars-per-source",
        type=int,
        default=120_000,
        help="Truncate any single source document's extracted text to this many characters (default: 120000). Use 0 for no limit.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files without prompting.")
    parser.add_argument(
        "--drive-folder-id",
        default=None,
        help="Google Drive folder ID to upload each output PDF to after it is written. "
             "If omitted, Drive uploads are skipped. The folder ID is the last segment of "
             "the folder's URL (e.g. '11vGsMiYTaR2wERyiISjrwBq6akVzzZH6').",
    )
    parser.add_argument(
        "--drive-credentials",
        default=None,
        help="Path to your Google OAuth2 credentials.json file. "
             "Falls back to the GOOGLE_CREDENTIALS_FILE env var if not set.",
    )

    args = parser.parse_args(argv)
    if args.max_chars_per_source == 0:
        args.max_chars_per_source = None

    try:
        run(args)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
