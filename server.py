"""YourLLM server. Run: python server.py  (opens http://127.0.0.1:8000)"""
import json
import mimetypes
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from src import storage

rag = None
_lock = threading.Lock()


def get_rag():
    global rag
    with _lock:
        if rag is None:
            from src.rag_pipeline import RAGPipeline
            rag = RAGPipeline()
    return rag


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=get_rag, daemon=True).start()  # warm up the embedding model
    yield


app = FastAPI(title="YourLLM", lifespan=lifespan)


# ---------------- documents ----------------
@app.get("/api/documents")
def list_documents():
    return [storage.public_doc(d) for d in storage.list_docs()]


@app.post("/api/documents")
def upload_documents(files: List[UploadFile] = File(...), chat_id: Optional[str] = None):
    chat = _chat_or_404(chat_id) if chat_id else None
    docs, errors = [], []
    for f in files:
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in config.SUPPORTED_TYPES:
            errors.append({"name": f.filename, "error": "Unsupported file type (use PDF, DOCX or TXT)."})
            continue
        try:
            docs.append(get_rag().ingest(f.filename, f.file.read()))
        except Exception as e:
            errors.append({"name": f.filename, "error": str(e)})
    if chat and docs:
        chat["doc_ids"] += [d["id"] for d in docs]
        storage.save_chat(chat)
    return {"docs": docs, "errors": errors}


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: str):
    d = _try(storage.get_doc, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    return FileResponse(d["path"], media_type=mimetypes.guess_type(d["name"])[0] or "application/octet-stream",
                        headers={"Content-Disposition": f'inline; filename="{d["name"]}"'})


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    if not _try(storage.get_doc, doc_id):
        raise HTTPException(404, "Document not found")
    get_rag().delete_doc(doc_id)
    return {"ok": True}


# ---------------- chats ----------------
class NewChat(BaseModel):
    doc_ids: List[str] = []
    title: str = "New chat"


class PatchChat(BaseModel):
    title: Optional[str] = None
    add_doc_ids: List[str] = []
    remove_doc_ids: List[str] = []


class AskBody(BaseModel):
    question: str


def _try(fn, *a):
    try:
        return fn(*a)
    except KeyError:
        return None


def _chat_or_404(cid: str) -> dict:
    c = _try(storage.get_chat, cid)
    if not c:
        raise HTTPException(404, "Chat not found")
    return c


@app.get("/api/chats")
def list_chats():
    return storage.list_chats()


@app.post("/api/chats")
def create_chat(body: NewChat):
    valid = [i for i in body.doc_ids if _try(storage.get_doc, i)]
    return storage.create_chat(valid, body.title.strip() or "New chat")


@app.get("/api/chats/{cid}")
def get_chat(cid: str):
    return _chat_or_404(cid)


@app.patch("/api/chats/{cid}")
def patch_chat(cid: str, body: PatchChat):
    c = _chat_or_404(cid)
    if body.title is not None and body.title.strip():
        c["title"] = body.title.strip()[:80]
    c["doc_ids"] = [i for i in c["doc_ids"] if i not in body.remove_doc_ids]
    c["doc_ids"] += [i for i in body.add_doc_ids if i not in c["doc_ids"] and _try(storage.get_doc, i)]
    storage.save_chat(c)
    return c


@app.delete("/api/chats/{cid}")
def delete_chat(cid: str):
    _chat_or_404(cid)
    storage.delete_chat(cid)
    return {"ok": True}


@app.post("/api/chats/{cid}/ask")
def ask(cid: str, body: AskBody):
    chat = _chat_or_404(cid)
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Empty question")
    from src.rag_pipeline import is_small_talk, small_talk_reply

    small_talk = is_small_talk(q)
    history = list(chat["messages"])
    chat["messages"].append({"role": "user", "content": q, "ts": time.time()})
    if chat["title"] == "New chat" and not small_talk:
        chat["title"] = q[:48]
    storage.save_chat(chat)  # the question is stored even if the answer fails

    def gen():
        text, sources, error = "", [], False
        try:
            if small_talk:
                reply = small_talk_reply(q, len(set(chat.get("doc_ids", []))))
                events = ({"type": "sources", "sources": []},
                          {"type": "token", "text": reply})
            else:
                events = get_rag().ask(chat, q, history)
            for ev in events:
                if ev["type"] == "sources":
                    sources = ev["sources"]
                elif ev["type"] == "token":
                    text += ev["text"]
                yield json.dumps(ev) + "\n"
        except Exception as e:
            error, text = True, text or f"Error: {e}"
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
        finally:
            fresh = storage.get_chat(cid) or chat  # keep a rename made meanwhile
            fresh["messages"].append({"role": "assistant", "content": text, "sources": sources,
                                      "error": error, "ts": time.time()})
            storage.save_chat(fresh)
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------------- frontend (built React app) ----------------
DIST = config.BASE_DIR / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    threading.Timer(2.0, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    uvicorn.run("server:app", host="127.0.0.1", port=8000)
