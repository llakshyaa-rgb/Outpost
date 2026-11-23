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
MAX_BODY = 8_000_000
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
    builtin = ROOT / "knowledge"
    if builtin.is_dir() and builtin.resolve() not in roots: roots.append(builtin.resolve())
    count = skipped = 0
    seen = set()
    for root in roots:
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in {".git","node_modules",".venv","venv","__pycache__","Android"} and not (Path(base) / d).is_symlink()]
            for name in names:
                p = Path(base) / name
                try:
                    resolved = p.resolve()
                    if root not in resolved.parents or not resolved.is_file():
                        skipped += 1
                        continue
                    if resolved.suffix.lower() not in TEXT_EXT:
                        skipped += 1
                        continue
                    st = resolved.stat()
                    if st.st_size > MAX_FILE:
                        skipped += 1
                        continue
                    content = resolved.read_text(encoding="utf-8", errors="replace")
                    with LOCK, connect() as c:
                        c.execute("""INSERT INTO documents(path,name,content,size,modified,indexed) VALUES(?,?,?,?,?,?)
                        ON CONFLICT(path) DO UPDATE SET name=excluded.name,content=excluded.content,size=excluded.size,modified=excluded.modified,indexed=excluded.indexed""",
                        (str(resolved),name,content,st.st_size,st.st_mtime,time.time()))
                    seen.add(str(resolved))
                    count += 1
                except (OSError, sqlite3.Error):
                    skipped += 1
    stale = 0
    with LOCK, connect() as c:
        rows = c.execute("SELECT id,path FROM documents").fetchall()
        for row in rows:
            path = Path(row["path"])
            if any(root == path or root in path.parents for root in roots) and str(path) not in seen and not path.exists():
                c.execute("DELETE FROM documents WHERE id=?", (row["id"],))
                stale += 1
    return {"indexed":count,"skipped":skipped,"removed":stale,"roots":[str(x) for x in roots]}

def payload(handler):
    n = int(handler.headers.get("Content-Length","0"))
    if n < 0 or n > MAX_BODY: raise ValueError("Request too large")
    raw = handler.rfile.read(n) if n else b"{}"
    return json.loads(raw.decode("utf-8"))


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
    p=Path(raw).expanduser().resolve()
    roots=managed_roots()
    if not any((p==r if allow_root else p!=r) or r in p.parents for r in roots):
        raise ValueError("Path is outside OUTPOST's configured folders")
    return p

def knowledge_catalog():
    base=ROOT/"knowledge"
    items=[]
    if not base.is_dir(): return items
    for p in base.rglob("*"):
        if not p.is_file() or p.is_symlink() or p.suffix.lower() not in {".md",".txt",".rst",".yaml",".yml",".json"}: continue
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
    server_version = "OUTPOST/0.2"
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
            self.send_json({"ok":True,"name":"OUTPOST","version":"0.2.0","storage":"local SQLite","counts":counts,"index_roots":load_config().get("index_roots",[])})
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
            bug_count=sum(1 for p in (knowledge/"bughunter").rglob("SKILL.md")) if (knowledge/"bughunter").is_dir() else 0
            security_count=sum(1 for p in (knowledge/"security").rglob("*") if p.is_file()) if (knowledge/"security").is_dir() else 0
            modules=[
              {"id":"afdrive","name":"AFDrive","role":"Local file vault and device-first file management","status":"core","detail":"OUTPOST uses its own loopback-only file layer; AFDrive is the architecture reference.","url":"https://github.com/ashwithfrank/AFDrive"},
              {"id":"kiwix","name":"Kiwix JS","role":"Offline ZIM library reader","status":"ready" if zim_count else "waiting","count":zim_count,"detail":"ZIM archives are discovered locally; open them with Kiwix JS/PWA.","url":"https://github.com/kiwix/kiwix-js"},
              {"id":"pfa","name":"Personal File Archive","role":"Local archive and incremental document indexing","status":"core","detail":"Unified local file index and search are built into OUTPOST.","url":"https://github.com/kevin0309/PersonalFileArchive"},
              {"id":"grimoire","name":"Grimoire","role":"Offline security knowledge and playbook search","status":"ready" if security_count else "waiting","count":security_count,"detail":"Knowledge folder is indexed locally; add licensed playbooks under knowledge/security.","url":"https://github.com/PentHertz/grimoire"},
              {"id":"termux","name":"Termux-Tools","role":"Android terminal utilities and environment checks","status":"ready" if os.environ.get("PREFIX","").startswith("/data/data/com.termux") else "partial","detail":"Read-only Termux environment and installed-command detection; no shell commands are run by the dashboard.","url":"https://github.com/termux/termux-tools"},
              {"id":"uplink","name":"Uplink","role":"Local document retrieval with citations","status":"core","detail":"OUTPOST search is local and indexes selected roots; citation-style source paths are shown.","url":"https://github.com/evanderpool/uplink"},
              {"id":"bughunter","name":"Claude-BugHunter","role":"Authorized security testing playbooks","status":"ready" if bug_count else "waiting","count":bug_count,"detail":"Optional local Agent Skills can be placed under knowledge/bughunter and searched offline.","url":"https://github.com/elementalsouls/Claude-BugHunter"},
              {"id":"cyberdesk","name":"CyberDesk","role":"Local security and file-analysis workbench","status":"partial","detail":"OUTPOST includes safe offline file analysis; active tools are not auto-run.","url":"https://github.com/JerenzeLevi/cyberdesk"}
            ]
            self.send_json(modules); return
        if u.path == "/api/system":
            import platform, shutil, sys
            termux=os.environ.get("PREFIX","").startswith("/data/data/com.termux") or "com.termux" in os.environ.get("HOME","")
            commands=["pkg","termux-info","termux-setup-storage","termux-open-url","git","python"]
            self.send_json({"termux":termux,"platform":platform.platform(),"machine":platform.machine(),"python":sys.version.split()[0],"commands":{x:bool(shutil.which(x)) for x in commands},"storage":str(Path.home()/"storage/shared") if (Path.home()/"storage/shared").exists() else None}); return
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
                            p=(Path(base)/name).resolve()
                            if p in seen: continue
                            seen.add(p)
                            try:
                                st=p.stat(); archives.append({"name":name,"path":str(p),"size":st.st_size,"modified":st.st_mtime})
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
        try: data=payload(self)
        except Exception as e: self.send_json({"error":str(e)},400); return
        now=time.time()
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
                if len(raw)>7_000_000: raise ValueError("Knowledge archive exceeds the 7 MB upload limit")
                target=(ROOT/"knowledge"/"imported").resolve()
                target.mkdir(parents=True,exist_ok=True)
                allowed={".md",".txt",".rst",".yaml",".yml",".json",".toml"}
                count=0; total=0; skipped=0
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    entries=z.infolist()
                    if len(entries)>250: raise ValueError("Archive contains too many entries")
                    for info in entries:
                        if info.is_dir(): continue
                        mode=(info.external_attr>>16)&0xFFFF
                        if stat.S_ISLNK(mode): skipped+=1; continue
                        rel=Path(info.filename)
                        if rel.is_absolute() or ".." in rel.parts or rel.suffix.lower() not in allowed: skipped+=1; continue
                        if info.file_size>2_000_000: skipped+=1; continue
                        total+=info.file_size
                        if total>25_000_000: raise ValueError("Expanded archive exceeds 25 MB")
                        dest=(target/rel).resolve()
                        if target not in dest.parents: skipped+=1; continue
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        with z.open(info) as src: content=src.read(2_000_001)
                        if len(content)>2_000_000: skipped+=1; continue
                        dest.write_bytes(content); count+=1
                self.send_json({"ok":True,"imported":count,"skipped":skipped,"catalog":knowledge_catalog()},201); return
            except (ValueError,OSError,zipfile.BadZipFile,base64.binascii.Error) as e:
                self.send_json({"error":str(e)},400); return
        if self.path == "/api/file/analyze":
            raw=str(data.get("path",""))
            try:
                p=Path(raw).expanduser().resolve()
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
