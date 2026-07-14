"""
Run a standalone "Check" audit (Prompt B from prompts.py) for one case study,
against an already-generated Version 1 or Version 2 questionnaire document.

This is the audit-only half of the full pipeline in run_case_study.py. Use it
when Version 1 / Version 2 was produced separately -- for example, Claude
generated it by hand in a chat instead of through the Anthropic API -- and you
just need ChatGPT/OpenAI to audit that document and produce a scored report.

Each call to OpenAI here is a single, standalone request (see
llm_clients.query_openai), so a Check 2 audit has no memory of Check 1 by
construction -- there is nothing extra to configure.

CLI entry points:
    run_check1.py  -- audits <CASE_ID>_Ver1.md, writes <CASE_ID>_Check1_report
    run_check2.py  -- audits <CASE_ID>_Ver2.md, writes <CASE_ID>_Check2_report
                      (and compares against an existing Check 1 grade, if any)

Both take the case study's ID (e.g. "CS11") as a required --case-id argument.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Optional

from . import pdf_utils, prompts
from .drive_upload import DriveUploader, try_upload
from .grading import extract_grade
from .llm_clients import DEFAULT_MAX_TOKENS, DEFAULT_OPENAI_MODEL, query_openai

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = Path(__file__).resolve().parent / "context"

VERSION_LABELS = {
    1: "Version 1 (initial draft)",
    2: "Version 2 (revised)",
}


class AuditResult(NamedTuple):
    case_id: str
    version: int
    grade: str
    report_md_path: Path
    report_pdf_path: Path
    previous_grade: Optional[str] = None


def run_standalone_audit(
    case_id: str,
    version: int,
    case_folder: Path | str | None = None,
    output_dir: Path | str | None = None,
    openai_model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_chars_per_source: int | None = 120_000,
    uploader: Optional[DriveUploader] = None,
) -> AuditResult:
    """
    Audit data/raw/<case_id>/pipeline_output/<case_id>_Ver<version>.md with
    Prompt B, writing <case_id>_Check<version>_report.md/.pdf alongside it.

    `case_id` is the fill-in-the-blank for "which case study" -- e.g. "CS11".
    Raises FileNotFoundError if the Version <version> document doesn't exist
    yet (generate it first, e.g. with run_case_study.py).
    """
    if version not in VERSION_LABELS:
        raise ValueError(f"version must be 1 or 2, got {version!r}")

    case_folder = Path(case_folder) if case_folder else REPO_ROOT / "data" / "raw" / case_id
    output_dir = Path(output_dir) if output_dir else case_folder / "pipeline_output"

    print(f"Case ID: {case_id}")
    print(f"Source documents folder: {case_folder}")
    print(f"Output folder: {output_dir}")

    # --- Load context docs ---------------------------------------------------
    codebook = (CONTEXT_DIR / "codebook.md").read_text(encoding="utf-8")
    note_taking_guidelines = (CONTEXT_DIR / "note_taking_guidelines.md").read_text(
        encoding="utf-8"
    )

    # --- Load the document to audit -------------------------------------------
    doc_path = output_dir / f"{case_id}_Ver{version}.md"
    if not doc_path.exists():
        raise FileNotFoundError(
            f"Could not find {doc_path} -- generate Version {version} first "
            f"(e.g. via run_case_study.py, or manually)."
        )
    document_text = doc_path.read_text(encoding="utf-8")

    # --- Extract source documents ---------------------------------------------
    print("Extracting text from source documents...")
    source_documents = pdf_utils.extract_source_documents(
        case_folder, max_chars_per_file=max_chars_per_source
    )
    print(f"  -> {len(source_documents):,} characters of source text")

    # --- Build and send Prompt B ------------------------------------------------
    prompt_b = prompts.build_prompt_b(
        case_id=case_id,
        version_label=VERSION_LABELS[version],
        case_study_document=document_text,
        codebook=codebook,
        note_taking_guidelines=note_taking_guidelines,
        source_documents=source_documents,
    )

    model = openai_model or DEFAULT_OPENAI_MODEL
    print(f"\nSending Check {version} audit prompt to OpenAI ({model})...")
    report_text = query_openai(prompt_b, model=model, max_tokens=max_tokens)

    # --- Save outputs -------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"{case_id}_Check{version}_report.md"
    pdf_path = output_dir / f"{case_id}_Check{version}_report.pdf"

    md_path.write_text(report_text, encoding="utf-8")
    pdf_utils.text_to_pdf(report_text, pdf_path, title=f"{case_id} - Check {version} Report")

    grade = extract_grade(report_text)
    print(f"\n  -> {md_path}")
    print(f"  -> {pdf_path}")
    print(f"  Check {version} grade: {grade}/100")
    try_upload(uploader, pdf_path)

    # --- Compare against the previous check, if this is Check 2 -------------------
    previous_grade = None
    if version == 2:
        previous_path = output_dir / f"{case_id}_Check1_report.md"
        if previous_path.exists():
            previous_grade = extract_grade(previous_path.read_text(encoding="utf-8"))
            print(f"\n  Check 1 grade (Version 1): {previous_grade}/100")
            print(f"  Check 2 grade (Version 2): {grade}/100")
            try:
                delta = int(grade) - int(previous_grade)
                print(f"  Change: {delta:+d}")
            except ValueError:
                pass

    return AuditResult(
        case_id=case_id,
        version=version,
        grade=grade,
        report_md_path=md_path,
        report_pdf_path=pdf_path,
        previous_grade=previous_grade,
    )
