#!/usr/bin/env python3
"""OUTPOST: offline-first, loopback-only personal command centre."""
from __future__ import annotations
import json, mimetypes, os, sqlite3, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STATIC = ROOT / "static"
DATA.mkdir(exist_ok=True)
DB = DATA / "outpost.db"
CONFIG = DATA / "config.json"
MAX_BODY = 1_000_000
MAX_FILE = 1_000_000
TEXT_EXT = {".txt",".md",".markdown",".json",".csv",".py",".js",".ts",".tsx",".jsx",".html",".css",".yml",".yaml",".toml",".ini",".cfg",".log",".xml",".sh",".sql"}
LOCK = threading.RLock()

def connect():
    c = sqlite3.connect(DB, timeout=10)
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with LOCK, connect() as c:
        c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS collections(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT DEFAULT '', created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS bookmarks(id INTEGER PRIMARY KEY, collection_id INTEGER, title TEXT NOT NULL, url TEXT DEFAULT '', note TEXT DEFAULT '', created REAL NOT NULL, FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE SET NULL);
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE, name TEXT NOT NULL, content TEXT NOT NULL, size INTEGER NOT NULL, modified REAL NOT NULL, indexed REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(name, path, content, content='documents', content_rowid='id')")
            c.executescript("""
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
              INSERT INTO documents_fts(rowid,name,path,content) VALUES(new.id,new.name,new.path,new.content);
            END;
            CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
              INSERT INTO documents_fts(documents_fts,rowid,name,path,content) VALUES('delete',old.id,old.name,old.path,old.content);
            END;
            CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
              INSERT INTO documents_fts(documents_fts,rowid,name,path,content) VALUES('delete',old.id,old.name,old.path,old.content);
              INSERT INTO documents_fts(rowid,name,path,content) VALUES(new.id,new.name,new.path,new.content);
            END;
            """)
        except sqlite3.OperationalError:
            pass
        c.execute("INSERT OR IGNORE INTO collections(name,description,created) VALUES('Inbox','Saved items',?)",(time.time(),))

def load_config():
    if not CONFIG.exists():
        CONFIG.write_text(json.dumps({"index_roots":[]}, indent=2))
    try: return json.loads(CONFIG.read_text())
    except Exception: return {"index_roots":[]}

def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2))

def index_files():
    cfg = load_config()
    roots = []
    for raw in cfg.get("index_roots", []):
        p = Path(raw).expanduser().resolve()
        if p.exists() and p.is_dir(): roots.append(p)
    count = skipped = 0
    for root in roots:
        for base, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {".git","node_modules",".venv","venv","__pycache__","Android"}]
            for name in names:
                p = Path(base) / name
                try:
                    if p.suffix.lower() not in TEXT_EXT: skipped += 1; continue
                    st = p.stat()
                    if st.st_size > MAX_FILE: skipped += 1; continue
                    content = p.read_text(encoding="utf-8", errors="replace")
                    with LOCK, connect() as c:
                        c.execute("""INSERT INTO documents(path,name,content,size,modified,indexed) VALUES(?,?,?,?,?,?)
                        ON CONFLICT(path) DO UPDATE SET name=excluded.name,content=excluded.content,size=excluded.size,modified=excluded.modified,indexed=excluded.indexed""",
                        (str(p),name,content,st.st_size,st.st_mtime,time.time()))
                    count += 1
                except (OSError, sqlite3.Error): skipped += 1
    return {"indexed":count,"skipped":skipped,"roots":[str(x) for x in roots]}

def payload(handler):
    n = int(handler.headers.get("Content-Length","0"))
    if n < 0 or n > MAX_BODY: raise ValueError("Request too large")
    raw = handler.rfile.read(n) if n else b"{}"
    return json.loads(raw.decode("utf-8"))

class Handler(BaseHTTPRequestHandler):
    server_version = "OUTPOST/0.1"
    def log_message(self, *_): pass
    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/status":
            with connect() as c:
                counts = {t:c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("notes","collections","bookmarks","documents")}
            self.send_json({"ok":True,"name":"OUTPOST","version":"0.1.0","storage":"local SQLite","counts":counts,"index_roots":load_config().get("index_roots",[])})
            return
        if u.path == "/api/export":
            with connect() as c:
                notes=[dict(x) for x in c.execute("SELECT title,body,created,updated FROM notes")]
                collections=[dict(x) for x in c.execute("SELECT name,description,created FROM collections")]
                bookmarks=[dict(x) for x in c.execute("SELECT b.title,b.url,b.note,b.created,c.name AS collection_name FROM bookmarks b LEFT JOIN collections c ON c.id=b.collection_id")]
            self.send_json({"version":1,"exported_at":time.time(),"notes":notes,"collections":collections,"bookmarks":bookmarks}); return
        if u.path == "/api/notes":
            with connect() as c: rows=[dict(x) for x in c.execute("SELECT * FROM notes ORDER BY updated DESC LIMIT 200")]
            self.send_json(rows); return
        if u.path == "/api/collections":
            with connect() as c: rows=[dict(x) for x in c.execute("SELECT * FROM collections ORDER BY name")]
            self.send_json(rows); return
        if u.path == "/api/bookmarks":
            with connect() as c:
                rows=[dict(x) for x in c.execute("""SELECT b.*, c.name AS collection_name
                    FROM bookmarks b LEFT JOIN collections c ON c.id=b.collection_id
                    ORDER BY b.created DESC LIMIT 300""")]
            self.send_json(rows); return
        if u.path == "/api/search":
            from urllib.parse import parse_qs
            q = parse_qs(u.query).get("q",[""])[0].strip()
            if not q: self.send_json([]); return
            like="%"+q.replace("%","")+"%"
            with connect() as c:
                try:
                    docs=[dict(x) for x in c.execute("SELECT d.id,d.name,d.path,substr(d.content,1,260) snippet,'file' kind FROM documents_fts f JOIN documents d ON d.id=f.rowid WHERE documents_fts MATCH ? LIMIT 40",(q,))]
                except sqlite3.OperationalError:
                    docs=[dict(x) for x in c.execute("SELECT id,name,path,substr(content,1,260) snippet,'file' kind FROM documents WHERE name LIKE ? OR content LIKE ? LIMIT 40",(like,like))]
                notes=[dict(x) for x in c.execute("SELECT id,title name,'note' path,substr(body,1,260) snippet,'note' kind FROM notes WHERE title LIKE ? OR body LIKE ? LIMIT 30",(like,like))]
                refs=[dict(x) for x in c.execute("SELECT id,title name,url path,substr(note,1,260) snippet,'bookmark' kind FROM bookmarks WHERE title LIKE ? OR note LIKE ? OR url LIKE ? LIMIT 30",(like,like,like))]
            self.send_json(docs+notes+refs); return
        if u.path == "/":
            return self.serve_static("index.html")
        if u.path.startswith("/static/"):
            return self.serve_static(u.path.removeprefix("/static/"))
        self.send_json({"error":"Not found"},404)
    def serve_static(self, rel):
        p=(STATIC / rel).resolve()
        if STATIC.resolve() not in p.parents and p != STATIC.resolve(): self.send_json({"error":"Forbidden"},403); return
        if not p.is_file(): self.send_json({"error":"Not found"},404); return
        data=p.read_bytes(); typ=mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        self.send_response(200); self.send_header("Content-Type",typ); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        try: data=payload(self)
        except Exception as e: self.send_json({"error":str(e)},400); return
        now=time.time()
        if self.path == "/api/notes":
            title=str(data.get("title","")).strip()[:160]; body=str(data.get("body",""))[:50000]
            if not title or not body: self.send_json({"error":"Title and body are required"},400); return
            with connect() as c: cur=c.execute("INSERT INTO notes(title,body,created,updated) VALUES(?,?,?,?)",(title,body,now,now))
            self.send_json({"ok":True,"id":cur.lastrowid},201); return
        if self.path == "/api/import":
            if not isinstance(data,dict) or data.get("version") != 1:
                self.send_json({"error":"Unsupported backup format"},400); return
            try:
                notes=data.get("notes",[]); collections=data.get("collections",[]); bookmarks=data.get("bookmarks",[])
                if any(not isinstance(x,dict) for group in (notes,collections,bookmarks) for x in group):
                    raise ValueError("Backup contains invalid records")
                if sum(map(len,(notes,collections,bookmarks)))>10000:
                    raise ValueError("Backup contains too many records")
                with LOCK, connect() as c:
                    for row in collections:
                        name=str(row.get("name","")).strip()[:100]
                        if name: c.execute("INSERT OR IGNORE INTO collections(name,description,created) VALUES(?,?,?)",(name,str(row.get("description",""))[:500],float(row.get("created",now))))
                    ids={x["name"]:x["id"] for x in c.execute("SELECT id,name FROM collections")}
                    for row in notes:
                        title=str(row.get("title","Untitled")).strip()[:160]
                        body=str(row.get("body",""))[:50000]
                        if title and body: c.execute("INSERT INTO notes(title,body,created,updated) VALUES(?,?,?,?)",(title,body,float(row.get("created",now)),float(row.get("updated",now))))
                    for row in bookmarks:
                        title=str(row.get("title","Untitled")).strip()[:200]
                        url=str(row.get("url","")).strip()[:1000]
                        if url and not url.startswith(("https://","http://")): url=""
                        if title: c.execute("INSERT INTO bookmarks(collection_id,title,url,note,created) VALUES(?,?,?,?,?)",(ids.get(row.get("collection_name")),title,url,str(row.get("note",""))[:2000],float(row.get("created",now))))
                self.send_json({"ok":True,"imported":{"notes":len(notes),"collections":len(collections),"bookmarks":len(bookmarks)}})
            except Exception as e:
                self.send_json({"error":"Backup could not be imported: "+str(e)},400)
            return
        if self.path == "/api/notes/update":
            try: ident=int(data.get("id",0))
            except (ValueError,TypeError): ident=0
            title=str(data.get("title","")).strip()[:160]; body=str(data.get("body",""))[:50000]
            if ident<1 or not title or not body: self.send_json({"error":"Valid note, title and body required"},400); return
            with connect() as c: cur=c.execute("UPDATE notes SET title=?,body=?,updated=? WHERE id=?",(title,body,now,ident))
            self.send_json({"ok":True,"updated":cur.rowcount>0}); return
        if self.path == "/api/collections":
            name=str(data.get("name","")).strip()[:100]
            if not name: self.send_json({"error":"Name required"},400); return
            try:
                with connect() as c: cur=c.execute("INSERT INTO collections(name,description,created) VALUES(?,?,?)",(name,str(data.get("description",""))[:500],now))
                self.send_json({"ok":True,"id":cur.lastrowid},201)
            except sqlite3.IntegrityError: self.send_json({"error":"Collection already exists"},409)
            return
        if self.path == "/api/bookmarks":
            title=str(data.get("title","")).strip()[:200]; url=str(data.get("url","")).strip()[:1000]
            if not title: self.send_json({"error":"Title required"},400); return
            if url and not url.startswith(("https://","http://")):
                self.send_json({"error":"URL must start with http:// or https://"},400); return
            cid=data.get("collection_id")
            with connect() as c: cur=c.execute("INSERT INTO bookmarks(collection_id,title,url,note,created) VALUES(?,?,?,?,?)",(cid,title,url,str(data.get("note",""))[:2000],now))
            self.send_json({"ok":True,"id":cur.lastrowid},201); return
        if self.path == "/api/index":
            self.send_json(index_files()); return
        if self.path == "/api/settings":
            roots=data.get("index_roots",[])
            if not isinstance(roots,list) or len(roots)>20: self.send_json({"error":"Provide up to 20 folder paths"},400); return
            clean=[]
            for r in roots:
                p=Path(str(r)).expanduser().resolve()
                if p.exists() and p.is_dir(): clean.append(str(p))
            save_config({"index_roots":clean})
            self.send_json({"ok":True,"index_roots":clean}); return
        self.send_json({"error":"Not found"},404)
    def do_DELETE(self):
        from urllib.parse import parse_qs
        u=urlparse(self.path); q=parse_qs(u.query)
        try: ident=int(q.get("id",["0"])[0])
        except ValueError: ident=0
        if ident<1: self.send_json({"error":"Valid id required"},400); return
        table={"notes":"notes","collections":"collections","bookmarks":"bookmarks"}.get(u.path)
        if not table: self.send_json({"error":"Not found"},404); return
        with connect() as c: c.execute(f"DELETE FROM {table} WHERE id=?",(ident,))
        self.send_json({"ok":True})
    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()

def main():
    init_db()
    host="127.0.0.1"; port=int(os.environ.get("OUTPOST_PORT","8765"))
    print(f"OUTPOST running at http://{host}:{port} (loopback only)")
    try: ThreadingHTTPServer((host,port),Handler).serve_forever()
    except KeyboardInterrupt: print("\nOUTPOST stopped.")

if __name__=="__main__": main()
