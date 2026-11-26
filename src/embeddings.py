"""Stage 3: Sentence Transformers embeddings (same model for docs and queries)."""
from typing import List
import config


class Embedder:
    def __init__(self, model_name: str = config.EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer  # lazy: slow import
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, normalize_embeddings=True,
                                 show_progress_bar=False).tolist()

    def embed_query(self, query: str) -> List[float]:
        return self.model.encode(config.QUERY_PREFIX + query,
                                 normalize_embeddings=True).tolist()
