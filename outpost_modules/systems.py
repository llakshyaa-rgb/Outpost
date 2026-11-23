"""Additional lightweight native modules for OUTPOST's offline integrations.

All functions operate on caller-supplied local data. No network access, shell
execution, telemetry, or model dependency is used.
"""
from __future__ import annotations
import csv, difflib, hashlib, mimetypes, os, re, sqlite3, time, urllib.parse, zlib
from pathlib import Path

STOP={"a","an","and","are","as","at","be","by","for","from","how","in","is","it","of","on","or","the","this","to","was","what","when","where","which","with"}

def chunk_text(text: str, max_chars: int=1600, overlap: int=200) -> list[str]:
    max_chars=max(128,int(max_chars))
    overlap=max(0,min(int(overlap),max_chars//2))
    text=text.strip()
    if not text: return []
    blocks=[x.strip() for x in re.split(r"\n\s*\n",text) if x.strip()] or [text]
    out=[]; current=""
    for block in blocks:
        while len(block)>max_chars:
            if current: out.append(current); current=""
            out.append(block[:max_chars])
            block=block[max_chars-overlap:]
        if current and len(current)+len(block)+1>max_chars:
            out.append(current); current=current[-overlap:]+"\n"+block if overlap else block
        else: current=(current+"\n"+block).strip()
    if current: out.append(current)
    return out

def ensure_uplink(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS uplink_chunks(
      id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL, path TEXT NOT NULL,
      title TEXT NOT NULL, section TEXT NOT NULL, body TEXT NOT NULL,
      ordinal INTEGER NOT NULL, indexed REAL NOT NULL, content_sha TEXT NOT NULL DEFAULT '',
      UNIQUE(document_id,ordinal)
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS uplink_fts USING fts5(title,section,body,content='uplink_chunks',content_rowid='id',tokenize='unicode61');
    CREATE TRIGGER IF NOT EXISTS uplink_ai AFTER INSERT ON uplink_chunks BEGIN
      INSERT INTO uplink_fts(rowid,title,section,body) VALUES(new.id,new.title,new.section,new.body);
    END;
    CREATE TRIGGER IF NOT EXISTS uplink_ad AFTER DELETE ON uplink_chunks BEGIN
      INSERT INTO uplink_fts(uplink_fts,rowid,title,section,body) VALUES('delete',old.id,old.title,old.section,old.body);
    END;
    CREATE TABLE IF NOT EXISTS uplink_feedback(
      id INTEGER PRIMARY KEY, query TEXT NOT NULL, chunk_id INTEGER,
      helpful INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', created REAL NOT NULL
    );
    """)
    columns={row[1] for row in conn.execute("PRAGMA table_info(uplink_chunks)")}
    if "content_sha" not in columns:
        conn.execute("ALTER TABLE uplink_chunks ADD COLUMN content_sha TEXT NOT NULL DEFAULT ''")

def rebuild_uplink(conn, max_docs=5000, max_chunks=100000):
    ensure_uplink(conn)
    docs=conn.execute("SELECT id,path,name,content FROM documents ORDER BY id LIMIT ?",(max_docs,)).fetchall()
    valid={int(d["id"]) for d in docs}
    existing={int(x[0]) for x in conn.execute("SELECT DISTINCT document_id FROM uplink_chunks")}
    removed=0
    for did in existing-valid:
        conn.execute("DELETE FROM uplink_chunks WHERE document_id=?",(did,)); removed+=1
    added=0; skipped=0; refreshed=0
    for d in docs:
        did=int(d["id"])
        body=str(d["content"] or "")
        digest=hashlib.sha256(body.encode("utf-8",errors="replace")).hexdigest()
        old=conn.execute("SELECT content_sha FROM uplink_chunks WHERE document_id=? LIMIT 1",(did,)).fetchone()
        if old and old[0]==digest: continue
        title=str(d["name"] or Path(d["path"]).name)
        chunks=chunk_text(body)
        if not chunks: skipped+=1; continue
        if added+len(chunks)>max_chunks:
            skipped+=1
            continue
        if old:
            conn.execute("DELETE FROM uplink_chunks WHERE document_id=?",(did,)); refreshed+=1
        for n,chunk in enumerate(chunks):
            section=f"Part {n+1}"
            conn.execute("""INSERT INTO uplink_chunks(document_id,path,title,section,body,ordinal,indexed,content_sha)
                VALUES(?,?,?,?,?,?,?,?)""",(did,d["path"],title,section,chunk,n,time.time(),digest))
            added+=1
    conn.commit()
    return {"documents_seen":len(docs),"chunks_added":added,"documents_removed":removed,
            "documents_refreshed":refreshed,"skipped":skipped,
            "chunks_total":conn.execute("SELECT COUNT(*) FROM uplink_chunks").fetchone()[0]}

def search_uplink(conn, query: str, limit: int=10):
    ensure_uplink(conn)
    words=[w for w in re.findall(r"\w+",query[:500]) if w.casefold() not in STOP] or re.findall(r"\w+",query[:500])
    if not words: return []
    quoted=['"'+w.replace('"','""')+'"' for w in words[:24]]
    results=[]
    for joiner in (" AND "," OR "):
        expr=joiner.join(quoted)
        try:
            rows=conn.execute("""SELECT c.id,c.path,c.title,c.section,c.body,bm25(uplink_fts,3.0,2.0,1.0) rank
                FROM uplink_fts JOIN uplink_chunks c ON c.id=uplink_fts.rowid
                WHERE uplink_fts MATCH ? ORDER BY rank LIMIT ?""",(expr,max(1,min(limit,30)))).fetchall()
        except sqlite3.OperationalError: rows=[]
        if rows:
            results=[{"id":x["id"],"path":x["path"],"title":x["title"],"section":x["section"],"snippet":x["body"][:900],"rank":x["rank"]} for x in rows]
            break
    return results

def corpus_stats(conn, root: Path):
    counts={}
    total=0
    for base,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d not in {".git","node_modules","__pycache__"} and not (Path(base)/d).is_symlink()]
        for name in files:
            p=Path(base)/name
            if p.is_symlink() or p.suffix.lower() not in {".md",".txt",".rst",".yaml",".yml",".json",".py",".sh",".pdf",".ipynb"}: continue
            try:
                size=p.stat().st_size
                if size>5_000_000: continue
                ext=p.suffix.lower() or "[no extension]"
                counts[ext]=counts.get(ext,0)+1; total+=1
            except OSError: pass
    return {"files":total,"by_type":dict(sorted(counts.items())),"root":str(root)}

def find_local_files(roots, query: str, limit: int=100):
    q=query.casefold().strip()
    out=[]
    if not q: return out
    for root in roots:
        for base,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[d for d in dirs if d not in {".git","node_modules",".venv","venv","__pycache__"} and not (Path(base)/d).is_symlink()]
            for name in files:
                p=Path(base)/name
                if p.is_symlink(): continue
                try:
                    resolved=p.resolve()
                    if root.resolve() not in resolved.parents: continue
                    if q in name.casefold() or q in str(resolved.parent).casefold():
                        st=resolved.stat()
                        out.append({"name":name,"path":str(resolved),"size":st.st_size,"modified":st.st_mtime,
                                    "type":mimetypes.guess_type(name)[0] or "application/octet-stream"})
                        if len(out)>=limit: return out
                except OSError: pass
    return out

def text_diff(before: str, after: str, limit: int=400):
    a=before.splitlines(); b=after.splitlines()
    return {"added":len(set(b)-set(a)),"removed":len(set(a)-set(b)),
            "diff":"\n".join(difflib.unified_diff(a,b,fromfile="before",tofile="after",lineterm=""))[:limit*120]}

def decode_candidates(value: str):
    import base64, binascii
    s=value.strip()
    found=[]
    def add(kind, raw):
        try:
            decoded=raw.decode("utf-8")
            if decoded and sum(c.isprintable() or c in "\n\r\t" for c in decoded)/len(decoded)>.88:
                found.append({"method":kind,"text":decoded[:4000]})
        except (UnicodeDecodeError,ZeroDivisionError): pass
    try: add("Base64",base64.b64decode(s,validate=True))
    except (binascii.Error,ValueError): pass
    try: add("Hex",bytes.fromhex(s))
    except ValueError: pass
    if "%" in s: add("URL decode",urllib.parse.unquote_to_bytes(s))
    if s.startswith(("0x","0X")): 
        try: add("Hex with 0x prefix",bytes.fromhex(s[2:]))
        except ValueError: pass
    add("ROT13",s.translate(str.maketrans("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ","nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM")).encode())
    return found[:8]
