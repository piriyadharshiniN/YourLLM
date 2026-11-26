"""Stage 4: ChromaDB storage and similarity search, filtered by document id."""
from typing import List, Dict
import chromadb
import config


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=config.CHROMA_DIR)
        self.col = self.client.get_or_create_collection(
            config.COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    def add_chunks(self, doc_id: str, chunks: List[Dict], embeddings: List[List[float]]):
        self.col.upsert(
            ids=[f"{doc_id}-{c['metadata']['chunk_id']}" for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks])

    def search(self, query_embedding: List[float], k: int, doc_ids: List[str]) -> List[Dict]:
        """Only chunks that belong to doc_ids can ever be returned."""
        if not doc_ids or self.col.count() == 0:
            return []
        where = {"doc_id": doc_ids[0]} if len(doc_ids) == 1 else {"doc_id": {"$in": list(doc_ids)}}
        res = self.col.query(query_embeddings=[query_embedding], n_results=k, where=where)
        out = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            out.append({"text": doc, "source": meta["source"], "page": meta["page"],
                        "doc_id": meta["doc_id"], "score": round(max(0.0, 1 - dist), 3)})
        return out

    def delete_doc(self, doc_id: str):
        self.col.delete(where={"doc_id": doc_id})
