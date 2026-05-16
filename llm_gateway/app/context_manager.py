"""
Context Manager for Harare City Council LLM Gateway v5.6.2
"""

import logging
from typing import Optional
from .embedding_utils import embedding_generator

logger = logging.getLogger(__name__)

def compute_relevance(message: str, context_summary: str) -> float:
    """
    Compute embedding similarity between the user message and the context summary.
    Returns a score between 0 and 1.
    """
    if not context_summary:
        return 0.0
    if embedding_generator.model is None:
        return 0.5  # fallback

    msg_emb = embedding_generator.encode(message)
    ctx_emb = embedding_generator.encode(context_summary)
    if msg_emb is None or ctx_emb is None:
        return 0.0
    return embedding_generator.similarity(msg_emb[0], ctx_emb[0])

def detect_topic_shift(message: str, previous_topic: str, threshold: float = 0.5) -> bool:
    """
    Detect if the current message represents a topic shift from the previous topic.
    Returns True if similarity below threshold.
    """
    if not previous_topic:
        return False
    sim = compute_relevance(message, previous_topic)
    return sim < threshold