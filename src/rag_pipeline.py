"""Ingestion and per-chat question answering."""
import random
import re
import time
from pathlib import Path
from typing import Dict, Iterator, List, Optional
import config
from src import storage
from src.document_processor import extract_pages
from src.chunker import chunk_pages
from src.embeddings import Embedder
from src.vector_store import VectorStore

# Earlier chats are only pulled in when the user explicitly refers to them.
RECALL = re.compile(
    r"\b(previous|earlier|last|past|prior|old|other)\s+(chat|chats|conversation|conversations|session|sessions)\b"
    r"|\b(we|you)\s+(discussed|talked|spoke|covered)\b|\bremember when\b|\bearlier (you|we)\b",
    re.I)

NO_DOCS = ("This chat has no documents attached yet. Upload files with the paperclip button "
           "(or from the Documents page) and ask again.")

_SMALL_TALK_ALIASES = {
    "hii": "hi",
    "hiii": "hi",
    "helloo": "hello",
    "heyy": "hey",
    "thankyou": "thank you",
    "thx": "thanks",
    "ty": "thanks",
    "okayy": "okay",
}

_SMALL_TALK_PHRASES = {
    "greeting": {
        "hi", "hello", "hey", "hiya", "yo", "good morning", "good afternoon",
        "good evening", "hi there", "hello there", "hey there",
    },
    "how_are_you": {
        "how are you", "hows it going", "whats up", "how do you do",
    },
    "thanks": {
        "thanks", "thank you", "thanks a lot", "thank you so much", "appreciate it",
    },
    "acknowledgement": {
        "ok", "okay", "k", "cool", "got it", "alright", "great", "nice", "sure",
        "fine", "sounds good",
    },
    "goodbye": {
        "bye", "goodbye", "see you", "see ya", "take care", "good night", "later",
    },
    "identity": {
        "who are you", "what can you do", "help", "what do you do", "what are you",
    },
}

_SMALL_TALK_REPLIES = {
    "how_are_you": (
        "I'm doing well and ready to help. What would you like to know about your files?",
        "I'm here and ready to help. What would you like to explore in your documents?",
        "Doing well, thanks! What would you like to know about your files?",
    ),
    "thanks": (
        "You're welcome! Let me know if you'd like more help with your documents.",
        "You're very welcome. I'm here if you need anything else with your files.",
        "Happy to help! Feel free to ask about your documents anytime.",
    ),
    "acknowledgement": (
        "Great! Let me know if you'd like to explore anything else in your documents.",
        "Sounds good. I'm here if you'd like help with anything else in your files.",
        "Understood. Just ask if you'd like to explore your documents further.",
    ),
    "goodbye": (
        "Goodbye! This chat will be saved here if you'd like to return.",
        "Take care! Your chat will be saved here for when you need it.",
        "See you next time. This chat will be saved here.",
    ),
    "identity": (
        "I'm YourLLM, a document assistant that answers questions about uploaded PDF, DOCX, and TXT files with source citations. I can also summarize or compare them.",
        "I answer questions about your uploaded PDF, DOCX, and TXT files with source citations, and can summarize or compare them.",
        "I'm your document assistant for uploaded PDF, DOCX, and TXT files. I can answer with source citations, summarize, and compare them.",
    ),
}


def _normalize_small_talk(text: str) -> str:
    text = re.sub(r"(?<=\w)['’](?=\w)", "", text.casefold())
    words = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    normalized_words = []
    for word in words:
        normalized_words.extend(_SMALL_TALK_ALIASES.get(word, word).split())
    return " ".join(normalized_words)


def _small_talk_category(text: str) -> Optional[str]:
    normalized = _normalize_small_talk(text)
    if not normalized or len(normalized.split()) > 6:
        return None
    for category, phrases in _SMALL_TALK_PHRASES.items():
        if normalized in phrases:
            return category
    return None


def is_small_talk(text: str) -> bool:
    return _small_talk_category(text) is not None


def small_talk_reply(text: str, document_count: int = 0) -> str:
    category = _small_talk_category(text)
    if category is None:
        raise ValueError("Cannot create a small-talk reply for a non-small-talk message.")
    if category == "greeting":
        if document_count:
            files = "file" if document_count == 1 else "files"
            replies = (
                f"Hello! I have {document_count} {files} ready. What would you like to know?",
                f"Hi! Your {document_count} {files} are ready to explore. What can I help you find?",
                f"Hey! I have {document_count} {files} ready. What would you like to explore?",
            )
        else:
            replies = (
                "Hello! Upload your documents whenever you're ready, and I'll help you explore them.",
                "Hi! I'm here to help with your documents whenever you're ready.",
                "Hey! Ask me to summarize or find something in your documents whenever you're ready.",
            )
        return random.choice(replies)
    return random.choice(_SMALL_TALK_REPLIES[category])


def safe_name(n: str) -> str:
    return re.sub(r"[^\w.\- ]", "_", Path(n).name)[:120]


def digest(chats: List[Dict]) -> str:
    out = []
    for c in chats:
        lines = "\n".join(f"{m['role'].upper()}: {m['content'][:400]}" for m in c["messages"][-6:])
        out.append(f"### Chat: {c['title']}\n{lines}")
    return "\n\n".join(out)


class RAGPipeline:
    def __init__(self, embedder=None, llm=None):
        self.embedder = embedder or Embedder()
        self.store = VectorStore()
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            from src.llm import GeminiLLM
            self._llm = GeminiLLM()
        return self._llm

    # ---- ingestion ----
    def ingest(self, filename: str, data: bytes) -> dict:
        pages = extract_pages(filename, data)
        if not pages:
            raise ValueError("No extractable text found (empty or scanned file).")
        doc_id = storage.new_id()
        chunks = chunk_pages(pages, filename, {"doc_id": doc_id})
        embeddings = self.embedder.embed_documents([c["text"] for c in chunks])
        self.store.add_chunks(doc_id, chunks, embeddings)
        path = config.UPLOAD_DIR / f"{doc_id}_{safe_name(filename)}"
        path.write_bytes(data)
        meta = {"id": doc_id, "name": filename, "size": len(data), "pages": pages[-1]["page"],
                "chunks": len(chunks), "uploaded_at": time.time(), "path": str(path)}
        storage.save_doc(meta)
        return storage.public_doc(meta)

    def delete_doc(self, doc_id: str):
        self.store.delete_doc(doc_id)
        storage.delete_doc(doc_id)
        storage.remove_doc_from_chats(doc_id)

    # ---- retrieval ----
    def search(self, question: str, doc_ids: List[str], history: Optional[List[Dict]] = None,
               top_k: int = config.TOP_K) -> List[Dict]:
        q = self.llm.rewrite_question(question, history) if history else question
        return self.store.search(self.embedder.embed_query(q), top_k, doc_ids)

    # ---- question answering (yields events) ----
    def ask(self, chat: dict, question: str, history: List[Dict]) -> Iterator[dict]:
        if is_small_talk(question):
            yield {"type": "sources", "sources": []}
            yield {"type": "token", "text": small_talk_reply(
                question, len(set(chat.get("doc_ids", []))))}
            return
        doc_ids, extra = list(chat["doc_ids"]), ""
        if RECALL.search(question):
            others = [c for c in storage.all_chats() if c["id"] != chat["id"] and c["messages"]][:5]
            extra = digest(others)
            for c in others:  # their files become searchable only for this request
                doc_ids += [d for d in c["doc_ids"] if d not in doc_ids]
        chunks = self.search(question, doc_ids, history)
        yield {"type": "sources", "sources": chunks}
        if not chunks and not extra:
            yield {"type": "token", "text": NO_DOCS}
            return
        for t in self.llm.stream_answer(question, chunks, history, extra, config.TEMPERATURE):
            yield {"type": "token", "text": t}
