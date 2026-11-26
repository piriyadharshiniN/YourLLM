"""Retrieval hit-rate + latency over everything in the document base.
Create eval_questions.json next to server.py:
[{"question": "...", "expected_source": "file.pdf", "expected_page": 12}, ...]
Run: python scripts/evaluate.py
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import storage
from src.rag_pipeline import RAGPipeline

rag = RAGPipeline()
doc_ids = [d["id"] for d in storage.list_docs()]
qs = json.loads(Path("eval_questions.json").read_text())
hits, lat = 0, []
for q in qs:
    t = time.time()
    chunks = rag.search(q["question"], doc_ids)
    lat.append(time.time() - t)
    if any(c["source"] == q["expected_source"] and
           c["page"] == q.get("expected_page", c["page"]) for c in chunks):
        hits += 1
print(f"Retrieval hit-rate: {hits}/{len(qs)} = {hits/len(qs):.0%}")
print(f"Avg retrieval latency: {sum(lat)/len(lat):.2f}s")
