"""Streaming, local-only Wikipedia XML importer for OUTPOST.

Stores article bodies compressed in a dedicated SQLite database. The importer
keeps main-namespace articles, strips most presentation markup, retains useful
section structure, and records only likely instructional/technical image
references. It does not fetch media or contact the network.
"""
from __future__ import annotations
import bz2, gzip, html, re, sqlite3, time, zlib
from pathlib import Path
from xml.etree import ElementTree as ET

WIKI_DB_NAME = "wiki.db"
MAX_SOURCE_BYTES = 80 * 1024**3
MAX_WIKI_DB_BYTES = 10 * 1024**3
IMAGE_HINTS = (
    "diagram", "map", "anatomy", "anatomical", "structure", "cross_section",
    "cross-section", "schematic", "circuit", "chart", "graph", "timeline",
    "periodic_table", "constellation", "orbit", "solar_system", "blueprint",
    "flowchart", "topology", "architecture", "anatomy", "cell_", "molecule",
    "geology", "geologic", "anatomical", "map_of"
)
FILE_RE = re.compile(r"\[\[(?:File|Image):([^\]|#]+)(?:\|([^\]]*))?\]\]", re.I)
LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
EXT_LINK_RE = re.compile(r"\[(?:https?://\S+\s+)?([^\]]+)\]")
TAG_RE = re.compile(r"<[^>]{1,500}>")
SPACE_RE = re.compile(r"[ \t\r\f\v]+")
TEMPLATE_NAMES = ("infobox", "cite", "citation", "reflist", "navbox", "sidebar", "authority control", "short description")

def _open_dump(path: Path):
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".bz2"): return bz2.open(path, "rb")
    if suffixes.endswith(".gz"): return gzip.open(path, "rb")
    return path.open("rb")

def _remove_templates(text: str) -> str:
    # Drop nested template blocks without a catastrophic regular expression.
    out=[]; i=0; depth=0
    while i < len(text):
        if text.startswith("{{", i):
            depth += 1; i += 2; continue
        if depth and text.startswith("}}", i):
            depth -= 1; i += 2; continue
        if depth == 0: out.append(text[i])
        i += 1
    return "".join(out)

def _clean_wikitext(raw: str):
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    images=[]
    def take_file(m):
        name=m.group(1).strip().replace("_"," ")
        low=name.casefold()
        if any(h in low for h in IMAGE_HINTS) and len(images)<40:
            images.append(name)
        return " "
    raw=FILE_RE.sub(take_file, raw)
    raw=_remove_templates(raw)
    raw=re.sub(r"<(ref|references)\b[^>]*>.*?</\1\s*>", " ", raw, flags=re.I|re.S)
    raw=re.sub(r"<ref\b[^>]*/\s*>", " ", raw, flags=re.I)
    raw=re.sub(r"\[\[(?:Category|File|Image|Portal|Wikipedia):[^\]]*\]\]", " ", raw, flags=re.I)
    raw=LINK_RE.sub(lambda m: m.group(2) or m.group(1).replace("_"," "), raw)
    raw=EXT_LINK_RE.sub(lambda m: m.group(1), raw)
    raw=re.sub(r"^\s*={2,6}\s*(.*?)\s*={2,6}\s*$", lambda m: "\n\n"+m.group(1).strip().upper()+"\n", raw, flags=re.M)
    raw=re.sub(r"'{2,5}", "", raw)
    raw=TAG_RE.sub(" ", raw)
    raw=html.unescape(raw)
    raw=re.sub(r"\[\[[^\]]*\]\]", " ", raw)
    raw=re.sub(r"\{\|.*?\|\}", " ", raw, flags=re.S)
    lines=[]
    for line in raw.splitlines():
        line=re.sub(r"^\s*[*#;:]+\s*", "• ", line)
        line=SPACE_RE.sub(" ", line).strip()
        if line: lines.append(line)
    text="\n".join(lines)
    text=re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, images

def _schema(conn):
    conn.executescript("""
      PRAGMA journal_mode=WAL;
      PRAGMA synchronous=NORMAL;
      CREATE TABLE IF NOT EXISTS articles(
        id INTEGER PRIMARY KEY, title TEXT NOT NULL UNIQUE, body BLOB NOT NULL,
        chars INTEGER NOT NULL, lead TEXT NOT NULL, images TEXT NOT NULL,
        updated REAL NOT NULL
      );
      CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(title, lead, content='articles', content_rowid='id', tokenize='unicode61');
      CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)

def import_dump(source: str, db_path: str, progress=None):
    path=Path(source).expanduser().resolve()
    if not path.is_file(): raise ValueError("Choose an existing Wikipedia XML dump (.xml, .bz2 or .gz)")
    if path.stat().st_size > MAX_SOURCE_BYTES: raise ValueError("Source dump exceeds the 80 GB safety limit")
    conn=sqlite3.connect(db_path, timeout=60)
    try:
        _schema(conn)
        conn.execute("DELETE FROM articles")
        total=kept=0; batch=[]
        with _open_dump(path) as stream:
            root=None
            for event, elem in ET.iterparse(stream, events=("start","end")):
                if root is None:
                    root=elem
                    continue
                if event != "end" or elem.tag.rsplit("}",1)[-1] != "page": continue
                title=elem.findtext("./{*}title") or ""
                ns=elem.findtext("./{*}ns") or "0"
                revision=elem.find("./{*}revision")
                text_node=revision.find("./{*}text") if revision is not None else None
                raw=text_node.text if text_node is not None and text_node.text else ""
                total += 1
                if ns=="0" and title and raw:
                    body,images=_clean_wikitext(raw)
                    if len(body)>=80:
                        lead=body[:1800]
                        batch.append((title,zlib.compress(body.encode("utf-8"),6),len(body),lead,"\n".join(images),time.time()))
                        kept += 1
                elem.clear()
                if root is not None: root.clear()
                if len(batch)>=300:
                    with conn:
                        conn.executemany("INSERT OR REPLACE INTO articles(title,body,chars,lead,images,updated) VALUES(?,?,?,?,?,?)",batch)
                    batch=[]
                    current=sum((Path(db_path).parent/(Path(db_path).name+suffix)).stat().st_size for suffix in ("","-wal") if (Path(db_path).parent/(Path(db_path).name+suffix)).exists())
                    if current > MAX_WIKI_DB_BYTES:
                        raise ValueError("Compact encyclopedia reached the 10 GiB storage ceiling; import stopped to protect device storage")
                    if progress: progress({"pages_seen":total,"articles_saved":kept})
            if batch:
                with conn:
                    conn.executemany("INSERT OR REPLACE INTO articles(title,body,chars,lead,images,updated) VALUES(?,?,?,?,?,?)",batch)
        with conn:
            conn.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('source',?)",(path.name,))
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('imported_at',?)",(str(time.time()),))
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('pages_seen',?)",(str(total),))
        return {"pages_seen":total,"articles_saved":kept,"database":str(db_path)}
    finally:
        conn.close()

def stats(db_path: str):
    p=Path(db_path)
    if not p.exists(): return {"ready":False,"articles":0,"size_bytes":0}
    conn=sqlite3.connect(db_path, timeout=30)
    try:
        count=conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        meta=dict(conn.execute("SELECT key,value FROM meta"))
    finally: conn.close()
    return {"ready":count>0,"articles":count,"size_bytes":p.stat().st_size,"source":meta.get("source",""),"imported_at":meta.get("imported_at","")}

def search(db_path: str, query: str, limit: int=30):
    q=query.strip()[:200]
    if not q: return []
    conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row
    try:
        words=[w for w in re.findall(r"\w+",q) if w][:12]
        if not words: return []
        expr=" AND ".join('"'+w.replace('"','""')+'"' for w in words)
        try:
            rows=conn.execute("SELECT a.id,a.title,a.chars,a.lead,bm25(articles_fts) rank FROM articles_fts JOIN articles a ON a.id=articles_fts.rowid WHERE articles_fts MATCH ? ORDER BY rank LIMIT ?",(expr,max(1,min(limit,50)))).fetchall()
        except sqlite3.OperationalError:
            rows=[]
        if not rows:
            rows=conn.execute("SELECT id,title,chars,lead,0 rank FROM articles WHERE title LIKE ? OR lead LIKE ? ORDER BY title LIMIT ?",("%"+q+"%","%"+q+"%",max(1,min(limit,50)))).fetchall()
        return [dict(x) for x in rows]
    finally: conn.close()

def article(db_path: str, article_id: int):
    conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row
    try:
        row=conn.execute("SELECT id,title,body,chars,images FROM articles WHERE id=?",(int(article_id),)).fetchone()
        if not row: return None
        return {"id":row["id"],"title":row["title"],"body":zlib.decompress(row["body"]).decode("utf-8","replace"),"chars":row["chars"],"images":[x for x in row["images"].split("\n") if x]}
    finally: conn.close()
