"""Stage 1: extract text per page from PDF / DOCX / TXT."""
import io
from typing import List, Dict


def extract_pdf(data: bytes) -> List[Dict]:
    import pymupdf as fitz
    pages = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            text = clean_text(page.get_text())
            if text:
                pages.append({"page": i, "text": text})
    return pages


def extract_docx(data: bytes) -> List[Dict]:
    from docx import Document
    doc = Document(io.BytesIO(data))
    text = clean_text("\n".join(p.text for p in doc.paragraphs))
    return [{"page": 1, "text": text}] if text else []


def extract_txt(data: bytes) -> List[Dict]:
    text = clean_text(data.decode("utf-8", errors="ignore"))
    return [{"page": 1, "text": text}] if text else []


def clean_text(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def extract_pages(filename: str, data: bytes) -> List[Dict]:
    """Returns [{'page': int, 'text': str}, ...]."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return extract_pdf(data)
    if ext == "docx":
        return extract_docx(data)
    if ext == "txt":
        return extract_txt(data)
    raise ValueError(f"Unsupported file type: .{ext}")
