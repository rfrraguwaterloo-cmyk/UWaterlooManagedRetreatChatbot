"""
PDF helpers for the case study pipeline:
- extract_text_from_pdf / extract_source_documents: pull text out of source PDFs
  (and plain text/markdown files) for a case study.
- text_to_pdf: render a generated narrative document (markdown-ish text) to PDF.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber
from fpdf import FPDF

SOURCE_EXTENSIONS = {".pdf", ".txt", ".md"}
SOURCE_METADATA_FILENAMES = {
    "dois.txt",
    "paper_discovery_report.md",
    "sources.txt",
}

# Roughly maps "smart" unicode punctuation (and a few common symbols) to ASCII so
# the core PDF fonts (latin-1 only) can render them without crashing.
_UNICODE_REPLACEMENTS = {
    "‘": "'", "’": "'",  # single quotes
    "“": '"', "”": '"',  # double quotes
    "–": "-", "—": "-",  # en/em dash
    "…": "...",  # ellipsis
    " ": " ",  # non-breaking space
    "•": "-",  # bullet
    "→": "->",
    "←": "<-",
    "×": "x",
}


def _sanitize(text: str) -> str:
    for src, dst in _UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    # Drop any remaining characters the core fonts can't encode.
    return text.encode("latin-1", "replace").decode("latin-1")


def extract_text_from_pdf(path: Path) -> str:
    """Extract all text from a PDF, page by page."""
    chunks = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            chunks.append(f"--- Page {i} ---\n{page_text}")
    return "\n\n".join(chunks)


def extract_source_documents(folder: Path, max_chars_per_file: int | None = None) -> str:
    """
    Read every PDF / .txt / .md file directly inside `folder` and return a single
    string with each file's text labelled by filename, ready to drop into a prompt.

    `max_chars_per_file` truncates very long individual files (set to None for no
    truncation).
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Source documents folder not found: {folder}")

    files = sorted(
        p for p in folder.iterdir()
        if (
            p.is_file()
            and p.suffix.lower() in SOURCE_EXTENSIONS
            and p.name not in SOURCE_METADATA_FILENAMES
        )
    )
    if not files:
        raise FileNotFoundError(
            f"No source documents (.pdf, .txt, .md) found in {folder}"
        )

    sections = []
    for f in files:
        if f.suffix.lower() == ".pdf":
            text = extract_text_from_pdf(f)
        else:
            text = f.read_text(encoding="utf-8", errors="replace")

        if max_chars_per_file and len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + "\n\n[... truncated ...]"

        sections.append(f"### Source file: {f.name} ###\n{text}")

    return "\n\n".join(sections)


def text_to_pdf(text: str, output_path: Path, title: str | None = None) -> Path:
    """
    Render a generated narrative document (plain text with light markdown-style
    `#`/`##`/`###` headings) to a PDF at `output_path`.
    """
    output_path = Path(output_path)
    pdf = FPDF(format="Letter")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def write_cell(h: float, content: str) -> None:
        """multi_cell, then reset cursor to the left margin (fpdf2 leaves x at the
        right edge after a width=0 multi_cell, which breaks the next call)."""
        pdf.multi_cell(0, h, content)
        pdf.set_x(pdf.l_margin)

    if title:
        pdf.set_font("Helvetica", style="B", size=16)
        write_cell(10, _sanitize(title))
        pdf.ln(4)

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        if not line.strip():
            pdf.ln(3)
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2).strip()
            size = {1: 15, 2: 13, 3: 12, 4: 11}.get(level, 11)
            pdf.set_font("Helvetica", style="B", size=size)
            pdf.ln(2)
            write_cell(8, _sanitize(content))
            pdf.set_font("Helvetica", size=10)
            continue

        # Bold "Question:" / "Answer:" / section markers written without '#'
        if re.match(r"^(Question|Answer|Narrative)\s*:", line, re.IGNORECASE):
            pdf.set_font("Helvetica", style="B", size=10)
            write_cell(6, _sanitize(line))
            pdf.set_font("Helvetica", size=10)
            continue

        pdf.set_font("Helvetica", size=10)
        write_cell(6, _sanitize(line))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path
