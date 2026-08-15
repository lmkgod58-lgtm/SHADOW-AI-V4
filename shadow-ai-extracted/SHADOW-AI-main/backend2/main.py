import os
import sqlite3
import time
from contextlib import closing
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

app = FastAPI(title="Shadow AI Memory Service", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
DB_PATH = os.getenv("SQLITE_PATH", "/data/shadow_memory.db")
MONGO_URI = os.getenv("MONGO_URI", "").strip()
MONGO_DB = os.getenv("MONGO_DB", "shadow_ai")
MEMORY_API_KEY = os.getenv("MEMORY_API_KEY", "").strip()

mongo_db = None
if MONGO_URI and MongoClient:
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        mongo_db = client[MONGO_DB]
        print("[Memory] MongoDB connected")
    except Exception as exc:
        print(f"[Memory] MongoDB unavailable, using SQLite: {exc}")

if mongo_db is None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, content TEXT NOT NULL, importance INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL)")
        conn.commit()


def auth(key: Optional[str]):
    if MEMORY_API_KEY and key != MEMORY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid memory API key")


class MemoryRequest(BaseModel):
    user_id: str = "default"
    content: str
    importance: int = 1


class SearchRequest(BaseModel):
    user_id: str = "default"
    query: str
    limit: int = 8


class MessageRequest(BaseModel):
    user_id: str = "default"
    role: str
    content: str


@app.get("/")
def root():
    return {"status": "Shadow AI memory service operational", "storage": "mongodb" if mongo_db else "sqlite"}


@app.get("/health")
def health():
    return {"status": "ok", "storage": "mongodb" if mongo_db else "sqlite"}


@app.post("/memory/save")
def save_memory(req: MemoryRequest, x_memory_key: Optional[str] = Header(default=None)):
    auth(x_memory_key)
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    importance = max(1, min(5, req.importance))
    now = time.time()
    if mongo_db:
        result = mongo_db.memories.insert_one({"user_id": req.user_id, "content": content, "importance": importance, "created_at": now})
        return {"ok": True, "id": str(result.inserted_id)}
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("INSERT INTO memories(user_id, content, importance, created_at) VALUES(?,?,?,?)", (req.user_id, content, importance, now))
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}


@app.post("/memory/search")
def search_memory(req: SearchRequest, x_memory_key: Optional[str] = Header(default=None)):
    auth(x_memory_key)
    q = req.query.strip().lower()
    limit = max(1, min(20, req.limit))
    if not q:
        return {"memories": []}
    if mongo_db:
        docs = list(mongo_db.memories.find({"user_id": req.user_id, "content": {"$regex": q, "$options": "i"}}).sort([("importance", -1), ("created_at", -1)]).limit(limit))
        return {"memories": [{"content": d["content"], "importance": d.get("importance", 1), "created_at": d.get("created_at", 0)} for d in docs]}
    words = [w for w in q.split() if len(w) > 1][:8] or [q]
    clauses = " OR ".join("content LIKE ?" for _ in words)
    params = [req.user_id] + [f"%{w}%" for w in words] + [limit]
    with closing(sqlite3.connect(DB_PATH)) as conn:
        rows = conn.execute(f"SELECT content, importance, created_at FROM memories WHERE user_id=? AND ({clauses}) ORDER BY importance DESC, created_at DESC LIMIT ?", params).fetchall()
    return {"memories": [{"content": r[0], "importance": r[1], "created_at": r[2]} for r in rows]}


@app.post("/conversation/message")
def save_message(req: MessageRequest, x_memory_key: Optional[str] = Header(default=None)):
    auth(x_memory_key)
    if req.role not in {"user", "assistant", "system"}:
        raise HTTPException(status_code=400, detail="invalid role")
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    now = time.time()
    if mongo_db:
        result = mongo_db.messages.insert_one({"user_id": req.user_id, "role": req.role, "content": content, "created_at": now})
        return {"ok": True, "id": str(result.inserted_id)}
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("INSERT INTO messages(user_id, role, content, created_at) VALUES(?,?,?,?)", (req.user_id, req.role, content, now))
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}


@app.get("/conversation/recent")
def recent_conversation(user_id: str = "default", limit: int = 20, x_memory_key: Optional[str] = Header(default=None)):
    auth(x_memory_key)
    limit = max(1, min(50, limit))
    if mongo_db:
        docs = list(mongo_db.messages.find({"user_id": user_id}).sort("created_at", -1).limit(limit))
        docs.reverse()
        return {"messages": [{"role": d["role"], "content": d["content"], "created_at": d["created_at"]} for d in docs]}
    with closing(sqlite3.connect(DB_PATH)) as conn:
        rows = conn.execute("SELECT role, content, created_at FROM messages WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
    rows.reverse()
    return {"messages": [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]}
