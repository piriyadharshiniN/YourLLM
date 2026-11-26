"""Milestone 1: python scripts/test_chunking.py path/to/file.pdf"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.document_processor import extract_pages
from src.chunker import chunk_pages

path = Path(sys.argv[1])
pages = extract_pages(path.name, path.read_bytes())
chunks = chunk_pages(pages, path.name)
print(f"{len(pages)} pages -> {len(chunks)} chunks\n")
for c in chunks[:5]:
    print(c["metadata"], "\n", c["text"], "\n" + "-" * 50)
