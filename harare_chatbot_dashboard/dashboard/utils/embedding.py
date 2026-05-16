# dashboard/utils/embedding.py
# Utility for generating and comparing embeddings (v3.2)

import numpy as np
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# Try to import sentence-transformers; if not available, use a fallback or log error
try:
    from sentence_transformers import SentenceTransformer
    _model = None
    MODEL_NAME = 'all-MiniLM-L6-v2'  # lightweight, good for semantic similarity
except ImportError:
    logger.error("sentence-transformers not installed. Embedding functionality will be disabled.")
    SentenceTransformer = None
    _model = None

def _get_model():
    """Lazy-load the embedding model."""
    global _model
    if SentenceTransformer is None:
        return None
    if _model is None:
        try:
            _model = SentenceTransformer(MODEL_NAME)
            logger.info(f"Loaded embedding model: {MODEL_NAME}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return None
    return _model

def get_embedding(text):
    """
    Generate an embedding vector for the given text.
    Returns a list of floats, or None if model unavailable or error.
    """
    model = _get_model()
    if model is None:
        return None
    try:
        # Truncate text to avoid excessive tokenization (model has 512 token limit)
        # Simple truncation by characters is not ideal, but we'll do a rough limit.
        # Better to use model's tokenizer, but this is a fallback.
        if len(text) > 10000:
            text = text[:10000]
        embedding = model.encode(text).tolist()
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def cosine_similarity(vec1, vec2):
    """
    Compute cosine similarity between two embedding vectors (lists of floats).
    Returns a float between -1 and 1.
    """
    if vec1 is None or vec2 is None:
        return 0.0
    a = np.array(vec1)
    b = np.array(vec2)
    # Avoid division by zero
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)

def batch_get_embeddings(texts):
    """
    Generate embeddings for a list of texts.
    Returns a list of embedding lists, or None for texts that failed.
    """
    model = _get_model()
    if model is None:
        return [None] * len(texts)
    try:
        # Truncate each text roughly
        truncated = [t[:10000] for t in texts]
        embeddings = model.encode(truncated)
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        logger.error(f"Error in batch embedding: {e}")
        return [None] * len(texts)