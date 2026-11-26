#!/usr/bin/env python3
"""Audit OUTPOST's built-in knowledge library for visible coverage gaps."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
ATLAS = KNOWLEDGE / "coverage" / "KNOWLEDGE_ATLAS.md"
MIN_WORDS = 120

def audit_knowledge():
    errors, warnings = [], []
    if not ATLAS.is_file():
        errors.append("Missing coverage atlas")
    articles = sorted(p for p in KNOWLEDGE.rglob("*.md")
                      if p.is_file() and p != ATLAS
                      and p.name.upper() not in {"README.MD", "ARTICLE_TEMPLATE.MD"}
                      and "bughunter" not in p.parts)
    if not articles:
        errors.append("No Markdown knowledge articles found")
    for path in articles:
        content = path.read_text(encoding="utf-8", errors="replace")
        words = re.findall(r"\b[\w'-]+\b", content)
        rel = path.relative_to(ROOT).as_posix()
        if len(words) < MIN_WORDS:
            warnings.append(f"{rel}: only {len(words)} words (target >= {MIN_WORDS})")
        if not re.search(r"(?im)^\*\*Search terms:\*\*", content):
            warnings.append(f"{rel}: missing Search terms metadata")
        if not re.search(r"(?im)^#{1,6}\s+", content):
            errors.append(f"{rel}: missing Markdown heading")
        if re.search(r"(?i)TODO|PLACEHOLDER|lorem ipsum", content):
            warnings.append(f"{rel}: contains TODO/placeholder marker")
    atlas_text = ATLAS.read_text(encoding="utf-8", errors="replace") if ATLAS.is_file() else ""
    if "\\n" in atlas_text:
        errors.append("Coverage atlas contains literal \\n text instead of real line breaks")
    gaps = re.findall(r"(?m)^\\s*-\\s*\\[ \\]\\s+(.+)$", atlas_text)
    return {"articles":len(articles),"errors":errors,"warnings":warnings,
            "atlas_present":ATLAS.is_file(),"domains":16,"atlas_gaps":gaps,
            "note":"Structural and discoverability checks only; unchecked atlas items are review prompts, not proof of missing facts."}

def main():
    result=audit_knowledge()
    print(f"OUTPOST knowledge audit: {result['articles']} Markdown articles")
    print(f"Errors: {len(result['errors'])} | Warnings: {len(result['warnings'])}")
    for item in result["errors"]: print("ERROR:",item)
    for item in result["warnings"]: print("WARN:",item)
    print("Coverage atlas:","present" if result["atlas_present"] else "MISSING")
    print("Note:",result["note"])
    return 1 if result["errors"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
