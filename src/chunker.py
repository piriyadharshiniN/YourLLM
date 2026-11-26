"""Stage 2: split page text into overlapping chunks, keeping metadata."""
from typing import List, Dict, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
import config


def chunk_pages(pages: List[Dict], source: str, extra: Optional[Dict] = None,
                chunk_size: int = config.CHUNK_SIZE,
                chunk_overlap: int = config.CHUNK_OVERLAP) -> List[Dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks, chunk_id = [], 0
    for p in pages:
        for piece in splitter.split_text(p["text"]):
            meta = {"source": source, "page": p["page"], "chunk_id": chunk_id, **(extra or {})}
            chunks.append({"text": piece, "metadata": meta})
            chunk_id += 1
    return chunks
