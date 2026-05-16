"""
Embedding utilities for Harare Chatbot Gateway
Uses sentence-transformers to generate embeddings and compute similarity.
No training required – uses pre‑trained model.
"""

import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Union, Optional

logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    """Generates embeddings and computes similarity scores."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Load pre‑trained sentence transformer model."""
        try:
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"✓ Embedding model '{model_name}' loaded (dim={self.embedding_dim})")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.model = None
    
    def encode(self, texts: Union[str, List[str]]) -> Optional[np.ndarray]:
        """Generate embeddings for text(s)."""
        if self.model is None:
            return None
        try:
            if isinstance(texts, str):
                texts = [texts]
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None
    
    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity between two embeddings."""
        if emb1 is None or emb2 is None:
            return 0.0
        # Normalise
        emb1 = emb1 / np.linalg.norm(emb1)
        emb2 = emb2 / np.linalg.norm(emb2)
        return float(np.dot(emb1, emb2))

# Global instance
embedding_generator = EmbeddingGenerator()