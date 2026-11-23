"""Additional lightweight native modules for OUTPOST's offline integrations.

All functions operate on caller-supplied local data. No network access, shell
execution, telemetry, or model dependency is used.
"""
from __future__ import annotations
import csv, difflib, hashlib, json, mimetypes, os, re, sqlite3, time, urllib.parse, zlib
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
    CREATE TABLE IF NOT EXISTS uplink_eval_runs(
      id INTEGER PRIMARY KEY, query TEXT NOT NULL, expected_path TEXT NOT NULL,
      matched INTEGER, reciprocal_rank REAL, results_json TEXT NOT NULL, created REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS uplink_questions(
      id INTEGER PRIMARY KEY, query TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
      answer_note TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL
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
            rows=conn.execute("""SELECT c.id,c.path,c.title,c.section,c.body,
                bm25(uplink_fts,3.0,2.0,1.0) rank,
                COALESCE(f.helpful,0) helpful,COALESCE(f.unhelpful,0) unhelpful
                FROM uplink_fts JOIN uplink_chunks c ON c.id=uplink_fts.rowid
                LEFT JOIN (SELECT chunk_id,SUM(CASE WHEN helpful=1 THEN 1 ELSE 0 END) helpful,
                           SUM(CASE WHEN helpful=0 THEN 1 ELSE 0 END) unhelpful
                           FROM uplink_feedback WHERE chunk_id IS NOT NULL GROUP BY chunk_id) f ON f.chunk_id=c.id
                WHERE uplink_fts MATCH ? ORDER BY rank LIMIT ?""",(expr,max(1,min(limit*3,90)))).fetchall()
        except sqlite3.OperationalError: rows=[]
        if rows:
            results=[]
            for x in rows:
                adjusted=float(x["rank"])-min(int(x["helpful"]),5)*0.12+min(int(x["unhelpful"]),5)*0.12
                results.append({"id":x["id"],"path":x["path"],"title":x["title"],"section":x["section"],
                                "snippet":x["body"][:900],"rank":float(x["rank"]),
                                "feedback_score":adjusted,"helpful_votes":int(x["helpful"])})
            results.sort(key=lambda item:item["feedback_score"])
            results=results[:max(1,min(limit,30))]
            break
    return results


def record_uplink_feedback(conn, query: str, chunk_id: int | None, helpful: bool, note: str=""):
    ensure_uplink(conn)
    query=str(query).strip()[:500]
    note=str(note).strip()[:2000]
    if not query: raise ValueError("Feedback needs the original search query")
    if chunk_id is not None:
        exists=conn.execute("SELECT 1 FROM uplink_chunks WHERE id=?",(int(chunk_id),)).fetchone()
        if not exists: raise ValueError("The referenced passage no longer exists")
    cur=conn.execute("INSERT INTO uplink_feedback(query,chunk_id,helpful,note,created) VALUES(?,?,?,?,?)",
                     (query,int(chunk_id) if chunk_id is not None else None,1 if helpful else 0,note,time.time()))
    conn.commit()
    return int(cur.lastrowid)

def evaluate_uplink_query(conn, query: str, expected_path: str, limit: int=10):
    results=search_uplink(conn,query,limit)
    expected=str(expected_path).casefold().strip()
    matched=any(expected in str(x["path"]).casefold() for x in results) if expected else None
    rr=next((1/(i+1) for i,x in enumerate(results) if expected and expected in str(x["path"]).casefold()),0 if expected else None)
    payload={"query":query,"expected_path":expected_path,"top_k":len(results),"matched":matched,
             "reciprocal_rank":rr,
             "results":[{"path":x["path"],"title":x["title"],"rank":x["rank"]} for x in results]}
    conn.execute("INSERT INTO uplink_eval_runs(query,expected_path,matched,reciprocal_rank,results_json,created) VALUES(?,?,?,?,?,?)",
                 (query,expected,int(bool(matched)) if matched is not None else None,rr,json.dumps(payload["results"]),time.time()))
    conn.commit()
    return payload


def queue_uplink_question(conn, query: str):
    ensure_uplink(conn)
    query=str(query).strip()[:500]
    if not query: raise ValueError("Enter a question")
    cur=conn.execute("INSERT INTO uplink_questions(query,status,created,updated) VALUES(?,'open',?,?)",(query,time.time(),time.time()))
    conn.commit()
    return int(cur.lastrowid)

def list_uplink_questions(conn, limit: int=100):
    ensure_uplink(conn)
    rows=conn.execute("SELECT id,query,status,answer_note,created,updated FROM uplink_questions ORDER BY created DESC LIMIT ?",(max(1,min(limit,200)),)).fetchall()
    return [{"id":x[0],"query":x[1],"status":x[2],"answer_note":x[3],"created":x[4],"updated":x[5]} for x in rows]

def close_uplink_question(conn, question_id: int, answer_note: str=""):
    ensure_uplink(conn)
    cur=conn.execute("UPDATE uplink_questions SET status='resolved',answer_note=?,updated=? WHERE id=?",
                     (str(answer_note)[:4000],time.time(),int(question_id)))
    conn.commit()
    if cur.rowcount==0: raise ValueError("Question not found")
    return True


def uplink_report(conn):
    ensure_uplink(conn)
    documents=conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks=conn.execute("SELECT COUNT(*) FROM uplink_chunks").fetchone()[0]
    feedback=conn.execute("SELECT COUNT(*),COALESCE(SUM(helpful),0) FROM uplink_feedback").fetchone()
    sources=conn.execute("SELECT path,COUNT(*) passages FROM uplink_chunks GROUP BY path ORDER BY passages DESC LIMIT 20").fetchall()
    recent=conn.execute("SELECT query,chunk_id,helpful,note,created FROM uplink_feedback ORDER BY created DESC LIMIT 50").fetchall()
    evals=conn.execute("SELECT COUNT(*),COALESCE(SUM(CASE WHEN matched=1 THEN 1 ELSE 0 END),0),COALESCE(AVG(reciprocal_rank),0) FROM uplink_eval_runs").fetchone()
    questions=conn.execute("SELECT COUNT(*),COALESCE(SUM(CASE WHEN status='open' THEN 1 ELSE 0 END),0) FROM uplink_questions").fetchone()
    return {"generated":time.time(),"documents":documents,"passages":chunks,
            "evaluation_runs":evals[0],"evaluation_hits":evals[1],"mean_reciprocal_rank":evals[2],
            "questions_total":questions[0],"questions_open":questions[1],
            "feedback_count":feedback[0],"helpful_count":feedback[1],
            "top_sources":[{"path":x[0],"passages":x[1]} for x in sources],
            "recent_feedback":[{"query":x[0],"chunk_id":x[1],"helpful":bool(x[2]),"note":x[3],"created":x[4]} for x in recent]}


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
