#!/usr/bin/env python3
"""Audit OUTPOST's built-in knowledge library for visible coverage gaps."""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
ATLAS = KNOWLEDGE / "coverage" / "KNOWLEDGE_ATLAS.md"
MIN_WORDS = 120

def main():
    errors, warnings = [], []
    if not ATLAS.is_file():
        errors.append("Missing coverage atlas: " + str(ATLAS))
    articles = sorted(p for p in KNOWLEDGE.rglob("*.md")
                      if p.is_file() and p != ATLAS and p.name.upper() not in {"README.MD", "ARTICLE_TEMPLATE.MD"} and "bughunter" not in p.parts)
    if not articles:
        errors.append("No Markdown knowledge articles found")
    for path in articles:
        text = path.read_text(encoding="utf-8", errors="replace")
        words = re.findall(r"\b[\w'-]+\b", text)
        rel = path.relative_to(ROOT)
        if len(words) < MIN_WORDS:
            warnings.append(f"{rel}: only {len(words)} words (target >= {MIN_WORDS})")
        if not re.search(r"(?im)^\*\*Search terms:\*\*", text):
            warnings.append(f"{rel}: missing Search terms metadata")
        if not re.search(r"(?im)^##?\s+", text):
            errors.append(f"{rel}: missing Markdown heading")
        if re.search(r"(?i)TODO|PLACEHOLDER|lorem ipsum", text):
            warnings.append(f"{rel}: contains TODO/placeholder marker")
    print(f"OUTPOST knowledge audit: {len(articles)} Markdown articles")
    print(f"Errors: {len(errors)} | Warnings: {len(warnings)}")
    for item in errors: print("ERROR:", item)
    for item in warnings: print("WARN:", item)
    print("Coverage atlas:", "present" if ATLAS.is_file() else "MISSING")
    print("Note: this checks structure and discoverability, not factual completeness.")
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
