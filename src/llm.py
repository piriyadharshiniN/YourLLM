"""Gemini prompting, query rewriting, streaming answers (retry + fallback model)."""
import time
from typing import List, Dict, Iterator
from google import genai
from google.genai import types
import config

NOT_FOUND = "I could not find this in the uploaded documents."

SYSTEM_PROMPT = f"""You are YourLLM, a document assistant.
Answer the user's question using ONLY the material provided below.
Rules:
1. DOCUMENT CONTEXT is the only source of facts. If it does not contain the answer,
   reply exactly: "{NOT_FOUND}" Do not guess and never use outside knowledge.
2. Cite sources for every claim as [Source: filename]. Do not include page numbers.
3. CURRENT CHAT shows the conversation so far; use it only to understand follow-ups.
4. A PREVIOUS CHATS section appears only when the user explicitly asked about earlier
   conversations. Use it to answer that request. Never mention other chats otherwise.
5. Be clear and concise. Use bullet points or a table when comparing things.
6. For longer messages with pleasantries, acknowledge them briefly in one polite sentence, then answer the question using DOCUMENT CONTEXT only."""

FALLBACK_MODELS = ["gemini-3.5-flash-lite"]
RETRIES_PER_MODEL = 3


def _is_overload(e: Exception) -> bool:
    s = str(e)
    return any(c in s for c in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded"))


def _convo(history: List[Dict], n: int = 6, limit: int = 500) -> str:
    return "\n".join(f"{m['role']}: {m['content'][:limit]}" for m in history[-n:])


class GeminiLLM:
    def __init__(self, model: str = config.GEMINI_MODEL):
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY missing. Add it to your .env file and restart.")
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.models = [model] + [m for m in FALLBACK_MODELS if m != model]

    @staticmethod
    def build_context(chunks: List[Dict]) -> str:
        return "\n\n".join(f"[Source: {c['source']}]\n{c['text']}" for c in chunks)

    def stream_answer(self, question: str, chunks: List[Dict], history: List[Dict],
                      extra: str = "", temperature: float = config.TEMPERATURE) -> Iterator[str]:
        parts = []
        if chunks:
            parts.append("DOCUMENT CONTEXT:\n" + self.build_context(chunks))
        if extra:
            parts.append("PREVIOUS CHATS (the user asked about them):\n" + extra)
        if history:
            parts.append("CURRENT CHAT:\n" + _convo(history))
        prompt = "\n\n".join(parts) + f"\n\nQUESTION:\n{question}"
        cfg = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=temperature)
        last_err = None
        for model in self.models:
            for attempt in range(RETRIES_PER_MODEL):
                started = False
                try:
                    for part in self.client.models.generate_content_stream(
                            model=model, contents=prompt, config=cfg):
                        if part.text:
                            started = True
                            yield part.text
                    return
                except Exception as e:
                    last_err = e
                    if started or not _is_overload(e):
                        raise
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError("Gemini is busy right now. Please try again in a minute. "
                           f"(last error: {last_err})")

    def rewrite_question(self, question: str, history: List[Dict]) -> str:
        """Turn a follow-up ('what are its applications?') into a standalone search query."""
        if not history:
            return question
        prompt = ("Rewrite the final user question as a standalone search query, "
                  "resolving pronouns using the conversation. Output only the query.\n\n"
                  f"CONVERSATION:\n{_convo(history, 6, 300)}\n\nFINAL QUESTION: {question}")
        for model in self.models:
            try:
                r = self.client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(temperature=0))
                return (r.text or question).strip()
            except Exception:
                continue
        return question
