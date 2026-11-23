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
MAX_BODY = 24_000_000
MAX_FILE = 5_000_000
TEXT_EXT = {".txt",".md",".markdown",".json",".csv",".py",".js",".ts",".tsx",".jsx",".html",".css",".yml",".yaml",".toml",".ini",".cfg",".log",".xml",".sh",".sql"}
DOC_EXT = {".pdf",".docx",".xlsx",".xls"}
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

def extract_document(p):
    ext=p.suffix.lower()
    if ext in TEXT_EXT:
        return p.read_text(encoding="utf-8",errors="replace")
    if ext==".pdf":
        try:
            from pypdf import PdfReader
            reader=PdfReader(str(p))
            return "\n".join((page.extract_text() or "") for page in reader.pages[:250])
        except ImportError:
            return ""
    if ext==".docx":
        try:
            from docx import Document
            doc=Document(str(p))
            return "\n".join(x.text for x in doc.paragraphs)
        except ImportError:
            return ""
    if ext==".xlsx":
        try:
            from openpyxl import load_workbook
            wb=load_workbook(str(p),read_only=True,data_only=True)
            out=[]
            for ws in wb.worksheets[:30]:
                out.append("SHEET: "+ws.title)
                for row in ws.iter_rows(max_row=2000,values_only=True):
                    vals=[str(v) for v in row if v is not None]
                    if vals: out.append(" | ".join(vals))
            wb.close()
            return "\n".join(out)
        except ImportError:
            return ""
    if ext==".xls":
        try:
            import xlrd
            wb=xlrd.open_workbook(str(p),on_demand=True)
            out=[]
            for ws in wb.sheets():
                out.append("SHEET: "+ws.name)
                for row in range(min(ws.nrows,2000)):
                    vals=[str(v) for v in ws.row_values(row) if v not in ("",None)]
                    if vals: out.append(" | ".join(vals))
            return "\n".join(out)
        except ImportError:
            return ""
    return ""

def index_files():
    cfg = load_config()
    roots = []
    for raw in cfg.get("index_roots", []):
        p = Path(raw).expanduser().resolve()
        if p.exists() and p.is_dir(): roots.append(p)
    builtin = ROOT / "knowledge"
    if builtin.is_dir() and builtin.resolve() not in roots: roots.append(builtin.resolve())
    count = skipped = 0
    total_bytes = 0
    seen = set()
    for root in roots:
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in {".git","node_modules",".venv","venv","__pycache__","Android"} and not (Path(base) / d).is_symlink()]
            for name in names:
                p = Path(base) / name
                try:
                    if p.is_symlink():
                        skipped += 1
                        continue
                    resolved = p.resolve()
                    if root not in resolved.parents or not resolved.is_file():
                        skipped += 1
                        continue
                    if str(resolved) in seen:
                        continue
                    if resolved.suffix.lower() not in TEXT_EXT | DOC_EXT:
                        skipped += 1
                        continue
                    st = resolved.stat()
                    if count >= 5000 or total_bytes + st.st_size > 300_000_000:
                        skipped += 1
                        continue
                    if st.st_size > MAX_FILE:
                        skipped += 1
                        continue
                    content = extract_document(resolved)
                    if not content.strip():
                        skipped += 1
                        continue
                    with LOCK, connect() as c:
                        c.execute("""INSERT INTO documents(path,name,content,size,modified,indexed) VALUES(?,?,?,?,?,?)
                        ON CONFLICT(path) DO UPDATE SET name=excluded.name,content=excluded.content,size=excluded.size,modified=excluded.modified,indexed=excluded.indexed""",
                        (str(resolved),name,content,st.st_size,st.st_mtime,time.time()))
                    seen.add(str(resolved))
                    count += 1
                    total_bytes += st.st_size
                except Exception:
                    skipped += 1
    stale = 0
    with LOCK, connect() as c:
        rows = c.execute("SELECT id,path FROM documents").fetchall()
        for row in rows:
            path = Path(row["path"])
            inside = any(root == path or root in path.parents for root in roots)
            if not inside or not path.exists():
                c.execute("DELETE FROM documents WHERE id=?", (row["id"],))
                stale += 1
    return {"indexed":count,"skipped":skipped,"removed":stale,"roots":[str(x) for x in roots]}

def payload(handler):
    n = int(handler.headers.get("Content-Length","0"))
    if n < 0 or n > MAX_BODY: raise ValueError("Request too large")
    raw = handler.rfile.read(n) if n else b"{}"
    value=json.loads(raw.decode("utf-8"))
    if not isinstance(value,dict): raise ValueError("Request body must be a JSON object")
    return value


def managed_roots():
    roots=[]
    for raw in load_config().get("index_roots", []):
        try:
            p=Path(raw).expanduser().resolve()
            if p.is_dir(): roots.append(p)
        except OSError: pass
    k=(ROOT/"knowledge").resolve()
    if k.is_dir(): roots.append(k)
    return list(dict.fromkeys(roots))

def managed_path(raw, allow_root=False):
    if not isinstance(raw,str) or not raw.strip(): raise ValueError("A file path is required")
    candidate=Path(raw).expanduser()
    probe=candidate
    while True:
        if probe.is_symlink(): raise ValueError("Symlink paths are not allowed")
        if probe.parent==probe: break
        probe=probe.parent
    p=candidate.resolve()
    roots=managed_roots()
    if not any((p==r if allow_root else p!=r) or r in p.parents for r in roots):
        raise ValueError("Path is outside OUTPOST's configured folders")
    return p

def knowledge_catalog():
    base=ROOT/"knowledge"
    items=[]
    if not base.is_dir(): return items
    for p in base.rglob("*"):
        if not p.is_file() or p.is_symlink() or p.suffix.lower() not in {".md",".txt",".rst",".yaml",".yml",".json",".py",".sh"}: continue
        try:
            if p.stat().st_size>2_000_000: continue
            raw=p.read_text(encoding="utf-8",errors="replace")
            title=p.stem.replace("-"," ").replace("_"," ").title()
            description=""
            if p.name.upper()=="SKILL.MD":
                for line in raw.splitlines()[:40]:
                    if line.lower().startswith("name:"): title=line.split(":",1)[1].strip() or title
                    if line.lower().startswith("description:"): description=line.split(":",1)[1].strip()
            else:
                for line in raw.splitlines():
                    if line.startswith("# "): title=line[2:].strip(); break
                description=next((x.strip() for x in raw.splitlines() if x.strip() and not x.startswith("#")), "")[:220]
            items.append({"name":p.name,"title":title,"description":description,"path":str(p),"size":p.stat().st_size,"skill":p.name.upper()=="SKILL.MD"})
        except OSError: pass
    return items

class Handler(BaseHTTPRequestHandler):
    server_version = "OUTPOST/0.3.1"
    def log_message(self, *_): pass
    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","DENY")
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        host=self.headers.get("Host","").split(":")[0].strip("[]").lower()
        if host not in {"127.0.0.1","localhost"}:
            self.send_json({"error":"Invalid local Host header"},403); return
        u = urlparse(self.path)
        if u.path == "/api/status":
            with connect() as c:
                counts = {t:c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("notes","collections","bookmarks","documents")}
            self.send_json({"ok":True,"name":"OUTPOST","version":"0.3.1","storage":"local SQLite","counts":counts,"index_roots":load_config().get("index_roots",[])})
            return
        if u.path == "/api/export":
            with connect() as c:
                notes=[dict(x) for x in c.execute("SELECT title,body,created,updated FROM notes")]
                collections=[dict(x) for x in c.execute("SELECT name,description,created FROM collections")]
                bookmarks=[dict(x) for x in c.execute("SELECT b.title,b.url,b.note,b.created,c.name AS collection_name FROM bookmarks b LEFT JOIN collections c ON c.id=b.collection_id")]
            self.send_json({"version":1,"exported_at":time.time(),"notes":notes,"collections":collections,"bookmarks":bookmarks}); return
        if u.path == "/api/modules":
            knowledge=ROOT/"knowledge"
            zim_dirs=[DATA/"zim"]+[Path(x).expanduser() for x in load_config().get("index_roots",[])]
            zim_count=sum(1 for root in zim_dirs if root.is_dir() for base,ds,fs in os.walk(root) for f in fs if f.lower().endswith(".zim"))
            bug_count=sum(1 for folder in (knowledge/"bughunter",knowledge/"imported") if folder.is_dir() for p in folder.rglob("SKILL.md"))
            security_count=sum(1 for folder in (knowledge/"security",knowledge/"imported") if folder.is_dir() for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in {".md",".txt",".rst",".yaml",".yml"})
            modules=[
              {"id":"afdrive","name":"AFDrive","role":"Local file vault and device-first file management","status":"core","detail":"OUTPOST uses its own loopback-only file layer; AFDrive is the architecture reference."},
              {"id":"kiwix","name":"Kiwix JS","role":"Offline ZIM library reader","status":"partial","count":zim_count,"detail":"Local ZIM archive discovery is available; the reader itself is not bundled."},
              {"id":"pfa","name":"Personal File Archive","role":"Local archive and incremental document indexing","status":"core","detail":"Unified local file index and search are built into OUTPOST."},
              {"id":"grimoire","name":"Grimoire","role":"Offline security knowledge and playbook search","status":"ready" if security_count else "waiting","count":security_count,"detail":"Local knowledge folders and imported packs are indexed and searchable offline."},
              {"id":"termux","name":"Termux-Tools","role":"Android terminal utilities and environment checks","status":"ready" if os.environ.get("PREFIX","").startswith("/data/data/com.termux") else "partial","detail":"Read-only Termux environment and installed-command detection; no shell commands are run by the dashboard."},
              {"id":"uplink","name":"Uplink","role":"Local document retrieval with citations","status":"core","detail":"OUTPOST search is local and indexes selected roots; citation-style source paths are shown."},
              {"id":"bughunter","name":"Claude-BugHunter","role":"Authorized security testing playbooks","status":"partial" if bug_count else "waiting","count":bug_count,"detail":"Local Agent Skills and support files can be imported and searched; scripts are never executed."},
              {"id":"cyberdesk","name":"CyberDesk","role":"Local security and file-analysis workbench","status":"partial","detail":"Static file triage, ZIP audit, hashes, entropy, strings, IOC extraction, JWT decoding, classical ciphers and local transforms are available."}
            ]
            self.send_json(modules); return
        if u.path == "/api/system":
            import platform, shutil, sys
            termux=os.environ.get("PREFIX","").startswith("/data/data/com.termux") or "com.termux" in os.environ.get("HOME","")
            commands=["pkg","termux-info","termux-setup-storage","termux-open-url","git","python"]
            self.send_json({"termux":termux,"platform":platform.platform(),"machine":platform.machine(),"python":sys.version.split()[0],"commands":{x:bool(shutil.which(x)) for x in commands},"storage":str(Path.home()/"storage/shared") if (Path.home()/"storage/shared").exists() else None}); return
        if u.path == "/api/knowledge/read":
            from urllib.parse import parse_qs
            raw=parse_qs(u.query).get("path",[""])[0]
            try:
                p=(ROOT/"knowledge"/raw).resolve()
                base=(ROOT/"knowledge").resolve()
                if base not in p.parents or p.is_symlink() or not p.is_file(): raise ValueError("Knowledge file not found")
                if p.suffix.lower() not in {".md",".txt",".rst",".yaml",".yml",".json",".toml",".py",".sh",".html",".css",".js"}: raise ValueError("Unsupported reference format")
                if p.stat().st_size>2_000_000: raise ValueError("Reference exceeds the 2 MB preview limit")
                self.send_json({"name":p.name,"path":str(p.relative_to(base)),"content":p.read_text(encoding="utf-8",errors="replace")}); return
            except (OSError,ValueError) as e: self.send_json({"error":str(e)},400); return
        if u.path == "/api/duplicates":
            import hashlib
            roots=managed_roots(); buckets={}; scanned=0; total=0
            for root in roots:
                for base,dirs,names in os.walk(root,followlinks=False):
                    dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink() and d not in {".git","node_modules",".venv","venv","__pycache__"}]
                    for name in names:
                        p=Path(base)/name
                        if p.is_symlink(): continue
                        try:
                            st=p.stat()
                            if not p.is_file() or st.st_size<1 or st.st_size>100_000_000 or scanned>=5000 or total+st.st_size>1_000_000_000: continue
                            key=(st.st_size)
                            buckets.setdefault(key,[]).append(p)
                            scanned+=1; total+=st.st_size
                        except OSError: continue
            duplicates=[]
            for size,paths in buckets.items():
                if len(paths)<2: continue
                hashes={}
                for p in paths:
                    try:
                        digest=hashlib.sha256()
                        with p.open("rb") as stream:
                            while True:
                                block=stream.read(262144)
                                if not block: break
                                digest.update(block)
                        hashes.setdefault(digest.hexdigest(),[]).append(str(p))
                    except OSError: continue
                for digest,group in hashes.items():
                    if len(group)>1: duplicates.append({"sha256":digest,"size":size,"files":group})
            self.send_json({"groups":duplicates,"files_scanned":scanned,"bytes_scanned":total,"limited":scanned>=5000 or total>=1_000_000_000}); return
        if u.path == "/api/knowledge/catalog":
            self.send_json(knowledge_catalog()); return
        if u.path == "/api/file/download":
            from urllib.parse import parse_qs
            raw=parse_qs(u.query).get("path",[""])[0]
            try:
                p=managed_path(raw)
                if not p.is_file(): raise ValueError("File not found")
                st=p.stat()
                if st.st_size>100_000_000: raise ValueError("Download exceeds the 100 MB safety limit")
                data=p.read_bytes()
                self.send_response(200); self.send_header("Content-Type","application/octet-stream")
                self.send_header("Content-Disposition","attachment; filename*=UTF-8''"+__import__("urllib.parse",fromlist=["quote"]).quote(p.name))
                self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store")
                self.end_headers(); self.wfile.write(data)
            except (OSError,ValueError) as e: self.send_json({"error":str(e)},400)
            return
        if u.path == "/api/fs/list":
            from urllib.parse import parse_qs
            raw=parse_qs(u.query).get("path",[""])[0]
            try:
                if raw:
                    folder=managed_path(raw,allow_root=True)
                    if not folder.is_dir(): raise ValueError("Folder not found")
                    roots=managed_roots()
                else:
                    roots=managed_roots()
                    entries=[]
                    for root in roots:
                        try:
                            st=root.stat()
                            entries.append({"name":root.name or str(root),"path":str(root),"root":str(root),"directory":True,"size":0,"modified":st.st_mtime})
                        except OSError: pass
                    self.send_json({"current":"","parent":"","entries":entries}); return
                entries=[]
                for child in folder.iterdir():
                    try:
                        if child.is_symlink(): continue
                        p=child.resolve()
                        if not any(p==r or r in p.parents for r in roots): continue
                        st=p.stat()
                        entries.append({"name":p.name,"path":str(p),"root":next((str(r) for r in roots if p==r or r in p.parents),str(folder)),"directory":p.is_dir(),"size":st.st_size if p.is_file() else 0,"modified":st.st_mtime})
                    except OSError: pass
                entries.sort(key=lambda x:(not x["directory"],x["name"].lower()))
                self.send_json({"current":str(folder),"parent":str(folder.parent) if any(folder!=r and r in folder.parents for r in roots) else "", "entries":entries[:1000]})
            except (OSError,ValueError) as e: self.send_json({"error":str(e)},400)
            return
        if u.path == "/api/files":
            roots=[Path(x).expanduser().resolve() for x in load_config().get("index_roots",[]) if Path(x).expanduser().exists()]
            roots.append((ROOT/"knowledge").resolve())
            found=[]
            for root in dict.fromkeys(roots):
                if not root.is_dir(): continue
                for base,dirs,files in os.walk(root, followlinks=False):
                    dirs[:]=[d for d in dirs if not d.startswith(".") and d not in {"node_modules",".git",".venv","venv","__pycache__"} and not (Path(base)/d).is_symlink()]
                    for name in files:
                        p=Path(base)/name
                        try:
                            if p.is_symlink(): continue
                            resolved=p.resolve()
                            if root not in resolved.parents or not resolved.is_file(): continue
                            st=resolved.stat()
                            found.append({"name":name,"path":str(resolved),"root":str(root),"size":st.st_size,"modified":st.st_mtime,"extension":resolved.suffix.lower()})
                        except OSError: pass
                        if len(found)>=1500: break
                    if len(found)>=1500: break
            found.sort(key=lambda x:x["name"].lower())
            self.send_json(found); return
        if u.path == "/api/zim":
            roots=[DATA/"zim"]+[Path(x).expanduser().resolve() for x in load_config().get("index_roots",[]) if Path(x).expanduser().exists()]
            archives=[]; seen=set()
            for root in dict.fromkeys(roots):
                if not root.is_dir(): continue
                for base,dirs,files in os.walk(root):
                    dirs[:]=[d for d in dirs if not d.startswith(".") and d not in {"node_modules",".git"}]
                    for name in files:
                        if name.lower().endswith(".zim"):
                            candidate=Path(base)/name
                            if candidate.is_symlink(): continue
                            p=candidate.resolve()
                            if p in seen: continue
                            seen.add(p)
                            try:
                                st=p.stat()
                                meta={"name":name,"path":str(p),"size":st.st_size,"modified":st.st_mtime,"valid_header":False}
                                try:
                                    with p.open("rb") as stream: header=stream.read(32)
                                    if len(header)>=32 and header[:3]==b"ZIM":
                                        import struct
                                        major,minor=struct.unpack_from("<HH",header,4)
                                        articles,clusters=struct.unpack_from("<II",header,24)
                                        meta.update({"valid_header":True,"version":str(major)+"."+str(minor),"articles":articles,"clusters":clusters})
                                except (OSError,ValueError,struct.error): pass
                                archives.append(meta)
                            except OSError: pass
            self.send_json(archives); return
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
        host=self.headers.get("Host","").split(":")[0].strip("[]").lower()
        if host not in {"127.0.0.1","localhost"}:
            self.send_json({"error":"Invalid local Host header"},403); return
        try: data=payload(self)
        except Exception as e: self.send_json({"error":str(e)},400); return
        now=time.time()
        if self.path == "/api/security/tool":
            import hashlib, math, re, base64, binascii, io, zipfile, stat
            try:
                mode=str(data.get("tool",""))
                text_input=str(data.get("text",""))[:200000]
                raw=b""
                if data.get("path"):
                    fp=managed_path(str(data.get("path")))
                    if not fp.is_file() or fp.stat().st_size>20_000_000: raise ValueError("Choose a file smaller than 20 MB")
                    raw=fp.read_bytes()
                else:
                    raw=text_input.encode("utf-8",errors="replace")
                if mode=="triage":
                    if not raw: raise ValueError("Provide text or select a file")
                    sample=raw[:65536]
                    counts={}
                    for b in sample: counts[b]=counts.get(b,0)+1
                    entropy=round(-sum((n/len(sample))*math.log2(n/len(sample)) for n in counts.values()),4)
                    signatures=[(b"\x7fELF","ELF executable"),(b"MZ","Windows executable / DOS"),(b"PK\x03\x04","ZIP / Office / APK"),(b"%PDF-","PDF document"),(b"\x89PNG\r\n\x1a\n","PNG image"),(b"\xff\xd8\xff","JPEG image"),(b"GIF8","GIF image"),(b"SQLite format 3","SQLite database"),(b"RIFF","RIFF media container"),(b"OggS","Ogg media"),(b"pcap","Packet capture")]
                    kind=next((label for magic,label in signatures if raw.startswith(magic)),"Text or unknown binary")
                    strings=re.findall(rb"[\x20-\x7e]{5,}",raw[:2_000_000])
                    utf16=re.findall(rb"(?:[\x20-\x7e]\x00){5,}",raw[:2_000_000])
                    blocks=[]
                    for offset in range(0,min(len(raw),262144),4096):
                        block=raw[offset:offset+4096]
                        freq={}
                        for byte in block: freq[byte]=freq.get(byte,0)+1
                        h=-sum((n/len(block))*math.log2(n/len(block)) for n in freq.values()) if block else 0
                        blocks.append({"offset":offset,"entropy":round(h,3)})
                    embedded=[]
                    for magic,label in signatures:
                        pos=raw.find(magic,1)
                        if pos>0: embedded.append({"offset":pos,"type":label})
                    result={"type":kind,"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"sha1":hashlib.sha1(raw).hexdigest(),"md5":hashlib.md5(raw).hexdigest(),"sample_entropy":entropy,"block_entropy":blocks,"embedded_signatures":embedded[:30],"strings":[x.decode("ascii","replace") for x in strings[:100]],"utf16le_strings":[x.decode("utf-16le","replace") for x in utf16[:50]],"note":"Static triage only; no execution or active probing."}
                    self.send_json(result); return
                if mode=="zip-audit":
                    if not raw: raise ValueError("Choose a ZIP file")
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        members=[]; warnings=[]
                        for info in archive.infolist()[:2000]:
                            name=info.filename
                            normalized=name.replace("\\","/")
                            parts=Path(normalized).parts
                            unsafe=Path(normalized).is_absolute() or ".." in parts or normalized.startswith("/") or (len(normalized)>1 and normalized[0].isalpha() and normalized[1]==":")
                            is_link=stat.S_ISLNK((info.external_attr>>16)&0xFFFF)
                            if unsafe or is_link: warnings.append({"entry":name,"reason":"path traversal or symlink entry"})
                            ratio=round(info.file_size/max(1,info.compress_size),1)
                            members.append({"name":name,"size":info.file_size,"compressed":info.compress_size,"ratio":ratio,"directory":info.is_dir(),"unsafe":unsafe or is_link})
                        self.send_json({"entries":len(archive.infolist()),"listed":len(members),"total_uncompressed":sum(x["size"] for x in members),"warnings":warnings[:100],"members":members,"note":"Archive inspected without extracting files."}); return
                if mode=="hash":
                    if not raw: raise ValueError("Enter text or select a file")
                    self.send_json({"size":len(raw),"md5":hashlib.md5(raw).hexdigest(),"sha1":hashlib.sha1(raw).hexdigest(),"sha256":hashlib.sha256(raw).hexdigest(),"sha384":hashlib.sha384(raw).hexdigest(),"sha512":hashlib.sha512(raw).hexdigest()}); return
                if mode=="ioc":
                    source=raw.decode("utf-8","replace")
                    patterns={"ipv4":r"(?<![\w.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\w.])","domain":r"(?i)(?<![@\w-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|dev|app|co|in|edu|gov|info|biz|xyz|ru|cn|uk|de|me|tv)(?![\w-])","url":r"https?://[^\s<>\"']+","email":r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}","hash":r"\b(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64}|[a-fA-F0-9]{128})\b"}
                    found={name:sorted(set(re.findall(pattern,source)))[:500] for name,pattern in patterns.items()}
                    self.send_json({"indicators":found,"counts":{k:len(v) for k,v in found.items()},"note":"Offline extraction only. Values are unverified indicators, not reputation verdicts."}); return
                if mode=="jwt":
                    token=text_input.strip()
                    parts=token.split(".")
                    if len(parts)!=3: raise ValueError("Enter a three-part JWT")
                    def dec(part):
                        return base64.urlsafe_b64decode(part+"="*((4-len(part)%4)%4)).decode("utf-8","replace")
                    header=json.loads(dec(parts[0])); claims=json.loads(dec(parts[1]))
                    self.send_json({"header":header,"claims":claims,"signature_present":bool(parts[2]),"warning":"Decoded locally without signature verification. Claims are untrusted until verified."}); return
                if mode=="hashid":
                    value=text_input.strip()
                    if not value: raise ValueError("Enter a hash")
                    patterns=[]
                    if re.fullmatch(r"[a-fA-F0-9]{32}",value): patterns=["MD5 / NTLM / MD4 (ambiguous 32-hex digest)"]
                    elif re.fullmatch(r"[a-fA-F0-9]{40}",value): patterns=["SHA-1 (or another 160-bit digest)"]
                    elif re.fullmatch(r"[a-fA-F0-9]{64}",value): patterns=["SHA-256 (or another 256-bit digest)"]
                    elif re.fullmatch(r"[a-fA-F0-9]{96}",value): patterns=["SHA-384 (or another 384-bit digest)"]
                    elif re.fullmatch(r"[a-fA-F0-9]{128}",value): patterns=["SHA-512 (or another 512-bit digest)"]
                    elif value.startswith(("$2a$","$2b$","$2y$")): patterns=["bcrypt"]
                    elif value.startswith("$6$"): patterns=["sha512crypt"]
                    elif value.startswith("$5$"): patterns=["sha256crypt"]
                    elif value.startswith("$1$"): patterns=["md5crypt"]
                    elif value.startswith("$argon2"): patterns=["Argon2 family"]
                    else: patterns=["Unknown / unsupported format"]
                    self.send_json({"candidates":patterns,"warning":"Format identification is heuristic. Never assume a digest's algorithm from length alone."}); return
                if mode in {"caesar","atbash","rot47"}:
                    source=text_input
                    def caesar(k):
                        out=[]
                        for ch in source:
                            if "a"<=ch<="z": out.append(chr((ord(ch)-97+k)%26+97))
                            elif "A"<=ch<="Z": out.append(chr((ord(ch)-65+k)%26+65))
                            else: out.append(ch)
                        return "".join(out)
                    if mode=="caesar":
                        results=[{"shift":k,"text":caesar(k)} for k in range(1,26)]
                        self.send_json({"results":results}); return
                    if mode=="atbash":
                        self.send_json({"text":"".join(chr(122-(ord(c)-97)) if "a"<=c<="z" else chr(90-(ord(c)-65)) if "A"<=c<="Z" else c for c in source)}); return
                    self.send_json({"text":"".join(chr(33+(ord(c)-33+47)%94) if 33<=ord(c)<=126 else c for c in source)}); return
                if mode=="xor-single":
                    if not raw: raise ValueError("Provide input text or a file")
                    ranked=[]
                    for key in range(256):
                        out=bytes(b^key for b in raw[:65536])
                        printable=sum(1 for b in out if b in (9,10,13) or 32<=b<127)/max(1,len(out))
                        common=sum(out.lower().count(x) for x in (b" the ",b" and ",b" to ",b" of "))
                        ranked.append((printable+min(common,20)*0.005,key,out))
                    ranked.sort(reverse=True)
                    self.send_json({"candidates":[{"key":k,"printable_score":round(score,4),"preview":out[:500].decode("utf-8","replace")} for score,k,out in ranked[:5]]}); return
                if mode=="pipeline":
                    doc=text_input
                    steps=data.get("steps",[])
                    if not isinstance(steps,list) or len(steps)>20: raise ValueError("Provide at most 20 transform steps")
                    for step in steps:
                        op=str(step.get("op",""))
                        args=step.get("args",[])
                        if op=="filter": doc="\n".join(x for x in doc.splitlines() if str(args[0]) in x)
                        elif op=="replace": doc=doc.replace(str(args[0]),str(args[1]) if len(args)>1 else "")
                        elif op=="sort": doc="\n".join(sorted(doc.splitlines(),reverse=(bool(args and args[0]=="desc"))))
                        elif op=="unique": doc="\n".join(dict.fromkeys(doc.splitlines()))
                        elif op=="reverse": doc=doc[::-1]
                        elif op=="base64-decode": doc=base64.b64decode(doc,validate=True).decode("utf-8","replace")
                        elif op=="base64-encode": doc=base64.b64encode(doc.encode()).decode()
                        elif op=="hex-decode": doc=bytes.fromhex(doc).decode("utf-8","replace")
                        elif op=="hex-encode": doc=doc.encode().hex()
                        else: raise ValueError("Unsupported pipeline operation: "+op)
                        if len(doc)>200000: raise ValueError("Pipeline output limit exceeded")
                    self.send_json({"result":doc}); return
                raise ValueError("Unknown security tool")
            except (ValueError, OSError, binascii.Error, zipfile.BadZipFile, IndexError, KeyError) as e:
                self.send_json({"error":str(e)},400); return
        if self.path == "/api/file/action":
            import base64, shutil
            op=str(data.get("operation",""))
            try:
                if op=="mkdir":
                    parent=managed_path(str(data.get("parent","")),allow_root=True)
                    name=Path(str(data.get("name",""))).name
                    if not name or name in {".",".."}: raise ValueError("A valid folder name is required")
                    target=(parent/name).resolve()
                    if target.parent!=parent: raise ValueError("Invalid folder name")
                    target.mkdir(exist_ok=False)
                    self.send_json({"ok":True,"path":str(target)},201); return
                if op=="upload":
                    parent=managed_path(str(data.get("parent","")),allow_root=True)
                    name=Path(str(data.get("name",""))).name
                    encoded=str(data.get("content_base64",""))
                    if not name or name in {".",".."}: raise ValueError("A valid file name is required")
                    raw=base64.b64decode(encoded,validate=True)
                    if len(raw)>5_000_000: raise ValueError("Upload exceeds the 5 MB limit")
                    target=(parent/name).resolve()
                    if target.parent!=parent: raise ValueError("Invalid file name")
                    if target.exists(): raise ValueError("A file with that name already exists")
                    target.write_bytes(raw)
                    self.send_json({"ok":True,"path":str(target),"size":len(raw)},201); return
                if op=="rename":
                    source=managed_path(str(data.get("path","")))
                    name=Path(str(data.get("name",""))).name
                    if not name or name in {".",".."}: raise ValueError("A valid new name is required")
                    target=(source.parent/name).resolve()
                    if target.parent!=source.parent: raise ValueError("Invalid new name")
                    if target.exists(): raise ValueError("Destination already exists")
                    source.rename(target)
                    self.send_json({"ok":True,"path":str(target)}); return
                if op=="delete":
                    target=managed_path(str(data.get("path","")))
                    if target.is_dir():
                        target.rmdir()
                    else: target.unlink()
                    self.send_json({"ok":True}); return
                if op=="zip":
                    import zipfile
                    paths=data.get("paths",[])
                    if not isinstance(paths,list) or not paths or len(paths)>200: raise ValueError("Select 1–200 files to archive")
                    parent=managed_path(str(data.get("parent","")),allow_root=True)
                    name=Path(str(data.get("name") or "outpost-archive.zip")).name
                    if not name.lower().endswith(".zip"): name+=".zip"
                    target=(parent/name).resolve()
                    if target.parent!=parent or target.exists(): raise ValueError("Archive name is invalid or already exists")
                    resolved=[]; total_size=0
                    for raw in paths:
                        p=managed_path(str(raw))
                        if not p.is_file(): raise ValueError("Only files can be added to a ZIP")
                        size=p.stat().st_size
                        if size>100_000_000: raise ValueError("A selected file exceeds 100 MB")
                        total_size+=size
                        if total_size>300_000_000: raise ValueError("Selected files exceed the 300 MB archive limit")
                        resolved.append(p)
                    with zipfile.ZipFile(target,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                        for p in resolved: archive.write(p,p.name)
                    self.send_json({"ok":True,"path":str(target),"files":len(resolved),"size":target.stat().st_size},201); return
                if op=="extract":
                    import zipfile, stat
                    source=managed_path(str(data.get("path","")))
                    parent=managed_path(str(data.get("parent","")),allow_root=True)
                    if not source.is_file() or source.suffix.lower()!=".zip": raise ValueError("Choose a ZIP file")
                    if source.stat().st_size>100_000_000: raise ValueError("ZIP exceeds 100 MB")
                    folder=Path(str(data.get("name") or source.stem)).name
                    if not folder or folder in {".",".."}: raise ValueError("Invalid destination folder name")
                    target=(parent/folder).resolve()
                    if target.parent!=parent or target.exists(): raise ValueError("Destination folder already exists or is invalid")
                    target.mkdir()
                    try:
                        with zipfile.ZipFile(source) as archive:
                            entries=archive.infolist()
                            if len(entries)>500: raise ValueError("ZIP contains more than 500 entries")
                            total=0
                            for info in entries:
                                rawname=info.filename.replace("\\","/")
                                rel=Path(rawname)
                                mode=(info.external_attr>>16)&0xFFFF
                                if rel.is_absolute() or ".." in rel.parts or rawname.startswith("/") or (len(rawname)>1 and rawname[0].isalpha() and rawname[1]==":") or stat.S_ISLNK(mode): continue
                                if info.file_size>20_000_000: continue
                                total+=info.file_size
                                if total>100_000_000: raise ValueError("Expanded ZIP exceeds 100 MB")
                                if info.compress_size and info.file_size/max(1,info.compress_size)>500: continue
                                dest=(target/rel).resolve()
                                if target not in dest.parents and dest!=target: continue
                                if info.is_dir(): dest.mkdir(parents=True,exist_ok=True); continue
                                dest.parent.mkdir(parents=True,exist_ok=True)
                                if dest.exists(): continue
                                with archive.open(info) as src, dest.open("xb") as dst:
                                    shutil.copyfileobj(src,dst,262144)
                    except Exception:
                        shutil.rmtree(target,ignore_errors=True)
                        raise
                    self.send_json({"ok":True,"path":str(target)} ,201); return
                if op=="copy":
                    source=managed_path(str(data.get("path","")))
                    parent=managed_path(str(data.get("parent","")),allow_root=True)
                    name=Path(str(data.get("name") or source.name)).name
                    target=(parent/name).resolve()
                    if target.parent!=parent or target.exists(): raise ValueError("Invalid or existing destination")
                    if source.is_dir(): raise ValueError("Folder copying is not supported")
                    shutil.copy2(source,target)
                    self.send_json({"ok":True,"path":str(target)}); return
                raise ValueError("Unsupported file operation")
            except (OSError,ValueError,base64.binascii.Error) as e:
                self.send_json({"error":str(e)},400); return
        if self.path == "/api/knowledge/import":
            import base64, zipfile, io, stat
            try:
                raw=base64.b64decode(str(data.get("archive_base64","")),validate=True)
                if len(raw)>15_000_000: raise ValueError("Knowledge archive exceeds the 15 MB upload limit")
                knowledge_root=ROOT/"knowledge"
                imported_root=knowledge_root/"imported"
                if knowledge_root.is_symlink() or imported_root.is_symlink():
                    raise ValueError("Knowledge import folder cannot be a symlink")
                target=imported_root.resolve()
                if target.parent!=knowledge_root.resolve():
                    raise ValueError("Knowledge import folder is outside OUTPOST")
                target.mkdir(parents=True,exist_ok=True)
                allowed={".md",".txt",".rst",".yaml",".yml",".json",".toml",".py",".sh",".html",".css",".js"}
                count=0; total=0; skipped=0
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    entries=z.infolist()
                    if len(entries)>2000: raise ValueError("Archive contains too many entries")
                    for info in entries:
                        if info.is_dir(): continue
                        mode=(info.external_attr>>16)&0xFFFF
                        if stat.S_ISLNK(mode): skipped+=1; continue
                        normalized=info.filename.replace("\\","/")
                        rel=Path(normalized)
                        if rel.is_absolute() or ".." in rel.parts or normalized.startswith("/") or (len(normalized)>1 and normalized[0].isalpha() and normalized[1]==":") or rel.suffix.lower() not in allowed: skipped+=1; continue
                        if info.file_size>5_000_000: skipped+=1; continue
                        if info.compress_size and info.file_size/max(1,info.compress_size)>200: skipped+=1; continue
                        total+=info.file_size
                        if total>50_000_000: raise ValueError("Expanded archive exceeds 50 MB")
                        dest=(target/rel).resolve()
                        if target not in dest.parents or dest.exists(): skipped+=1; continue
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        with z.open(info) as src: content=src.read(5_000_001)
                        if len(content)>5_000_000: skipped+=1; continue
                        with dest.open("xb") as stream: stream.write(content)
                        count+=1
                self.send_json({"ok":True,"imported":count,"skipped":skipped,"catalog":knowledge_catalog()},201); return
            except (ValueError,OSError,zipfile.BadZipFile,base64.binascii.Error) as e:
                self.send_json({"error":str(e)},400); return
        if self.path == "/api/file/analyze":
            raw=str(data.get("path",""))
            try:
                p=managed_path(raw)
                roots=[Path(x).expanduser().resolve() for x in load_config().get("index_roots",[]) if Path(x).expanduser().exists()]
                roots.append((ROOT/"knowledge").resolve())
                if not any(p==root or root in p.parents for root in roots): raise ValueError("File is outside configured archive roots")
                if not p.is_file(): raise ValueError("File not found")
                st=p.stat()
                if st.st_size>5_000_000: raise ValueError("File exceeds the 5 MB analysis limit")
                import hashlib
                digest=hashlib.sha256()
                with p.open("rb") as f:
                    head=f.read(32); digest.update(head)
                    while True:
                        block=f.read(65536)
                        if not block: break
                        digest.update(block)
                signatures=[(b"\x7fELF","ELF executable"),(b"PK\x03\x04","ZIP archive / Office document"),(b"%PDF-","PDF document"),(b"\x89PNG","PNG image"),(b"\xff\xd8\xff","JPEG image"),(b"GIF8","GIF image"),(b"SQLite format 3","SQLite database")]
                kind=next((label for magic,label in signatures if head.startswith(magic)), "Text or unknown binary")
                preview=""
                if p.suffix.lower() in TEXT_EXT and st.st_size<=1_000_000:
                    preview=p.read_text(encoding="utf-8",errors="replace")[:4000]
                self.send_json({"name":p.name,"path":str(p),"size":st.st_size,"modified":st.st_mtime,"sha256":digest.hexdigest(),"type":kind,"preview":preview})
            except (OSError,ValueError) as e: self.send_json({"error":str(e)},400)
            return
        if self.path == "/api/ip/calculate":
            raw=str(data.get("address","")).strip()
            try:
                import ipaddress
                interface=ipaddress.ip_interface(raw)
                net=interface.network
                hosts=list(net.hosts()) if net.num_addresses<=2 else None
                first=str(next(net.hosts(),net.network_address))
                last=str(list(net.hosts())[-1]) if net.num_addresses<=4096 else str(net[-2] if net.version==4 and net.prefixlen<31 else net[-1])
                result={"input":raw,"version":net.version,"address":str(interface.ip),"prefix":net.prefixlen,"network":str(net.network_address),"broadcast":str(net.broadcast_address) if net.version==4 else None,"netmask":str(net.netmask),"hostmask":str(net.hostmask),"total_addresses":net.num_addresses,"first_host":first,"last_host":last,"is_private":interface.ip.is_private,"is_global":interface.ip.is_global,"is_loopback":interface.ip.is_loopback,"is_link_local":interface.ip.is_link_local,"is_multicast":interface.ip.is_multicast}
                self.send_json(result); return
            except ValueError as e:
                self.send_json({"error":"Enter a valid IPv4/IPv6 address or CIDR range: "+str(e)},400); return
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
            for raw in roots:
                if not isinstance(raw,str) or not raw.strip(): continue
                candidate=Path(raw).expanduser()
                probe=candidate; unsafe=False
                while True:
                    if probe.is_symlink(): unsafe=True; break
                    if probe.parent==probe: break
                    probe=probe.parent
                if unsafe: continue
                p=candidate.resolve()
                if p.is_dir() and p not in clean: clean.append(str(p))
            save_config({"index_roots":clean})
            self.send_json({"ok":True,"index_roots":clean}); return
        self.send_json({"error":"Not found"},404)
    def do_DELETE(self):
        host=self.headers.get("Host","").split(":")[0].strip("[]").lower()
        if host not in {"127.0.0.1","localhost"}:
            self.send_json({"error":"Invalid local Host header"},403); return
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
