# YourLLM – Intelligent Document Assistant

Upload PDF / DOCX / TXT files, then chat with them. Answers come only from your files and cite file + page.

**Stack:** React (Vite) · FastAPI · PyMuPDF · LangChain splitters · Sentence Transformers (bge-small) · ChromaDB · Gemini

## How it behaves
- **Per-chat sources:** each chat has its own attached files, and retrieval is filtered to them. A new chat never sees another chat's files or messages.
- **Previous chats only on request:** if you ask things like "what did we discuss in the previous chat?", the app adds a digest of your recent chats (and makes their files searchable) for that question only.
- **Documents base:** every uploaded file is stored separately (`data/uploads`) and listed on the Documents page. "Use in new chat" starts a chat with that file.
- **Chat History:** every chat is its own block; rename with the pencil icon, open or delete.
- **Everything persists:** files, chats, titles and vectors are saved under `data/` and reload after refresh or restart.
- **Accuracy defaults (no settings page):** chunks 800 / overlap 150, top-5 retrieval, temperature 0.3, strict context-only prompt.

## Run (Python only, the React app is pre-built)
```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env  -> add GEMINI_API_KEY
python server.py                  # opens http://127.0.0.1:8000
```
First start downloads the embedding model (about 130 MB) once.

## Edit the React UI (optional, needs Node 18+)
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to the Python server)
npm run build      # rebuilds frontend/dist, which server.py serves
```

## Layout
```
server.py            FastAPI API + serves frontend/dist
src/storage.py       JSON storage: one file per document and per chat
src/rag_pipeline.py  ingestion, scoped retrieval, previous-chat recall
src/llm.py           Gemini prompt, retry + fallback model, query rewriting
src/vector_store.py  ChromaDB with doc_id filtering
frontend/src/        React app (App.jsx, api.js, styles.css); icons in frontend/public/icons
data/                created at runtime (uploads, documents, chats, chroma) - back this up
scripts/             test_chunking.py, evaluate.py
```
