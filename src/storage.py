"""JSON file storage: one file per document and one per chat (survives restarts)."""
import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional
import config


def new_id() -> str:
    return uuid.uuid4().hex


def _ok(i: str) -> str:
    if not (isinstance(i, str) and i.isalnum()):
        raise KeyError(i)  # blocks path tricks like ../
    return i


def _write(path: Path, obj: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # atomic: a crash never leaves half a file


def _read(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------- documents ----------------
def public_doc(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "path"}


def save_doc(d: dict):
    _write(config.DOC_DIR / f"{_ok(d['id'])}.json", d)


def get_doc(i: str) -> Optional[dict]:
    p = config.DOC_DIR / f"{_ok(i)}.json"
    return _read(p) if p.exists() else None


def list_docs() -> List[dict]:
    docs = [d for d in (_read(p) for p in config.DOC_DIR.glob("*.json")) if d]
    return sorted(docs, key=lambda d: d["uploaded_at"], reverse=True)


def delete_doc(i: str):
    d = get_doc(i)
    if d:
        Path(d["path"]).unlink(missing_ok=True)
        (config.DOC_DIR / f"{i}.json").unlink(missing_ok=True)


# ---------------- chats ----------------
def save_chat(c: dict):
    c["updated_at"] = time.time()
    _write(config.CHAT_DIR / f"{_ok(c['id'])}.json", c)


def create_chat(doc_ids: Optional[List[str]] = None, title: str = "New chat") -> dict:
    t = time.time()
    c = {"id": new_id(), "title": title, "created_at": t, "updated_at": t,
         "doc_ids": list(doc_ids or []), "messages": []}
    save_chat(c)
    return c


def get_chat(i: str) -> Optional[dict]:
    p = config.CHAT_DIR / f"{_ok(i)}.json"
    return _read(p) if p.exists() else None


def all_chats() -> List[dict]:
    chats = [c for c in (_read(p) for p in config.CHAT_DIR.glob("*.json")) if c]
    return sorted(chats, key=lambda c: c["updated_at"], reverse=True)


def list_chats() -> List[dict]:
    return [{"id": c["id"], "title": c["title"], "created_at": c["created_at"],
             "updated_at": c["updated_at"], "message_count": len(c["messages"]),
             "doc_ids": c["doc_ids"]} for c in all_chats()]


def delete_chat(i: str):
    (config.CHAT_DIR / f"{_ok(i)}.json").unlink(missing_ok=True)


def remove_doc_from_chats(doc_id: str):
    for c in all_chats():
        if doc_id in c["doc_ids"]:
            c["doc_ids"].remove(doc_id)
            save_chat(c)
