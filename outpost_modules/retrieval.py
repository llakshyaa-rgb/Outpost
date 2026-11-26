"""Small, dependency-free local retrieval helpers inspired by Uplink and Grimoire.

No network, model, embedding, or background worker is used. SQLite FTS5 remains
the persistent index; these helpers make its query language safe and rankable.
"""
from __future__ import annotations
import re
import difflib

_WORDS = re.compile(r"(\w+)(\*)?", re.UNICODE)
_STOP = {"a","an","and","are","as","at","be","by","do","does","for","from","how","i","in","is","it","me","my","of","on","or","our","the","this","to","was","we","what","when","where","which","who","why","with","you"}
# Small, explicit vocabulary bridges for common wording, spelling variants and
# misspellings. These expand recall without making unrelated terms synonyms.
_SYNONYMS = {
    "sex": ("sexual", "sexuality", "sexual health"),
    "sexual": ("sex", "sexuality"),
    "porn": ("pornography", "sexual media"),
    "pornography": ("porn", "sexual media"),
    "nude": ("nudity", "naked"),
    "nudity": ("nude", "naked"),
    "nudely": ("nudity", "nude"),
    "reproduce": ("reproduction", "reproductive"),
    "reproduction": ("reproduce", "reproductive"),
    "reproductive": ("reproduction",),
    "period": ("menstruation", "menstrual"),
    "menstruation": ("period", "menstrual"),
    "sti": ("sexually transmitted infection", "sexually transmitted infections"),
    "math": ("maths", "mathematics"),
    "maths": ("math", "mathematics"),
    "civilization": ("civilisation",),
    "civilisation": ("civilization",),
}

def _fts_token(word: str, prefix: bool = False) -> str:
    # Tokens originate only from the conservative word regex above.
    token = '"' + word.replace('"', '""') + '"'
    return token + "*" if prefix else token

def match_expressions(query: str) -> list[str]:
    matches = _WORDS.findall(query[:500])
    if not matches:
        return []
    terms = []
    for word, wildcard in matches:
        if word.casefold() in _STOP and word not in {"AND","OR","NOT","NEAR"}:
            continue
        terms.append((word, bool(wildcard)))
    if not terms:
        terms = [(word, False) for word, _ in matches]
    clauses = []
    for word, prefix in terms[:24]:
        variants = [word]
        if not prefix:
            variants.extend(_SYNONYMS.get(word.casefold(), ()))
            if len(word) >= 2:
                variants.append(word + "*")
        tokens = list(dict.fromkeys(
            _fts_token(v[:-1], True) if v.endswith("*") else _fts_token(v, prefix if v == word else False)
            for v in variants
        ))
        clauses.append("(" + " OR ".join(tokens) + ")" if len(tokens) > 1 else tokens[0])
    strict = " AND ".join(clauses)
    loose = " OR ".join(clauses)
    return [strict] if strict == loose else [strict, loose]

def typo_candidates(query: str, vocabulary, limit: int = 2) -> list[str]:
    """Suggest close indexed terms for misspelled query words."""
    words = [w.casefold() for w, _ in _WORDS.findall(query[:300]) if len(w) >= 5]
    vocab = {str(v).casefold() for v in vocabulary if str(v)}
    found = []
    for word in words:
        if word not in vocab:
            found.extend(difflib.get_close_matches(word, vocab, n=limit, cutoff=0.82))
    return list(dict.fromkeys(found))[:8]

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
