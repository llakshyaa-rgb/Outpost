"""Small, dependency-free local retrieval helpers inspired by Uplink and Grimoire.

No network, model, embedding, or background worker is used. SQLite FTS5 remains
the persistent index; these helpers make its query language safe and rankable.
"""
from __future__ import annotations
import re

_WORDS = re.compile(r"\w+", re.UNICODE)
_STOP = {"a","an","and","are","as","at","be","by","do","does","for","from","how","i","in","is","it","me","my","of","on","or","our","the","this","to","was","we","what","when","where","which","who","why","with","you"}

def match_expressions(query: str) -> list[str]:
    words = _WORDS.findall(query[:500])
    if not words:
        return []
    useful = [w for w in words if w.casefold() not in _STOP] or words
    # Quoting every token prevents user-supplied FTS operators from changing
    # the query grammar. Try AND first, then OR for natural-language recall.
    quoted = ['"' + w.replace('"', '""') + '"' for w in useful[:24]]
    strict = " AND ".join(quoted)
    loose = " OR ".join(quoted)
    return [strict] if strict == loose else [strict, loose]

def split_sections(text: str, max_chars: int = 1800, overlap: int = 180) -> list[str]:
    """Create bounded, overlapping retrieval passages without retaining copies."""
    text = text.strip()
    if not text:
        return []
    blocks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not blocks:
        blocks = [text]
    chunks, current = [], ""
    for block in blocks:
        while len(block) > max_chars:
            head, block = block[:max_chars], block[max_chars-overlap:]
            if current:
                chunks.append(current)
                current = ""
            chunks.append(head)
        if current and len(current) + len(block) + 1 > max_chars:
            chunks.append(current)
            current = current[-overlap:] + "\n" + block if overlap else block
        else:
            current = (current + "\n" + block).strip()
    if current:
        chunks.append(current)
    return chunks
