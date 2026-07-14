#!/usr/bin/env python3
"""Quick relevance check for a candidate source (paper/journal/file).

Small sanity check before adding a paper to a case study: does its title (e.g. the
title shown in Google Drive, or a filename) share meaningful words with the case?
Pure stdlib, no dependencies, no network.

Examples:
  # check one title against a case profile
  python -m case_study_pipeline.source_check.check_relevance \
      --case "Dhye Upper Mustang Nepal drought snowfall relocation resettlement" \
      --title "Climate change adaptation measure on agricultural communities of Dhye in Upper Mustang, Nepal"

  # treat some words as must-relate keywords (e.g. the place name)
  ... --keywords "dhye,mustang,nepal"

  # check every file already staged in a case folder
  python -m case_study_pipeline.source_check.check_relevance \
      --case "Dhye Upper Mustang Nepal drought relocation" --folder data/raw/CS12
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

# Generic words to ignore so matches reflect case-specific overlap, not boilerplate.
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "with", "from", "as", "at",
    "by", "is", "are", "was", "were", "be", "this", "that", "these", "those", "its", "their",
    "study", "studies", "case", "paper", "journal", "article", "report", "review", "analysis",
    "research", "vol", "no", "pp", "doi", "et", "al", "pdf", "draft", "final", "content",
    "approach", "approaches", "based", "using", "use", "toward", "towards", "into", "how",
}

WORD_RE = re.compile(r"[a-z][a-z'-]+")


def tokenize(text: str) -> set[str]:
    return {w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS and len(w) > 2}


def check(case: str, title: str, keywords: list[str], min_shared: int) -> dict:
    case_terms = tokenize(case)
    title_terms = tokenize(title)
    shared = sorted(case_terms & title_terms)
    kw = [k.strip().lower() for k in keywords if k.strip()]
    kw_hit = sorted(k for k in kw if k in title_terms)
    if kw and not kw_hit:
        verdict = "FLAG (no required keyword present)"
    elif kw_hit or len(shared) >= min_shared:
        verdict = "RELEVANT"
    elif shared:
        verdict = "REVIEW (weak overlap)"
    else:
        verdict = "FLAG (no shared words)"
    return {"title": title, "shared": shared, "keyword_hits": kw_hit, "verdict": verdict}


def fmt(r: dict) -> str:
    bits = [f"[{r['verdict']}] {r['title']}"]
    if r["keyword_hits"]:
        bits.append(f"    keyword hits: {', '.join(r['keyword_hits'])}")
    bits.append(f"    shared words: {', '.join(r['shared']) if r['shared'] else '(none)'}")
    return "\n".join(bits)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Quick relevance check for a candidate source.")
    p.add_argument("--case", required=True, help="Case profile text (place, country, hazard, action).")
    p.add_argument("--title", help="Candidate title or filename to check.")
    p.add_argument("--folder", help="Check every file's name in this folder instead of --title.")
    p.add_argument("--keywords", default="", help="Comma-separated must-relate terms (e.g. the place name).")
    p.add_argument("--min", type=int, default=2, dest="min_shared",
                   help="Min shared words to call it RELEVANT without a keyword hit (default 2).")
    args = p.parse_args(argv)
    kw = args.keywords.split(",") if args.keywords else []

    titles: list[str] = []
    if args.folder:
        folder = Path(args.folder)
        titles = [f.stem.replace("_", " ") for f in sorted(folder.iterdir()) if f.is_file()]
        if not titles:
            print(f"No files found in {folder}")
            return
    elif args.title:
        titles = [args.title]
    else:
        p.error("provide --title or --folder")

    for t in titles:
        print(fmt(check(args.case, t, kw, args.min_shared)))


if __name__ == "__main__":
    main()
