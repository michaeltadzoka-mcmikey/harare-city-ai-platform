import numpy as np
from typing import List, Optional
import logging
from sentence_transformers import SentenceTransformer
from app.config import config

logger = logging.getLogger(__name__)

class EmbeddingModel:
    def __init__(self, model_name: str = None, batch_size: int = 100):
        """
        Initialize the embedding model.
        
        Args:
            model_name: Name of the sentence transformer model
            batch_size: Batch size for processing texts (default: 100)
        """
        self.model_name = model_name or config.EMBEDDING_MODEL
        self.batch_size = batch_size
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            try:
                logger.info(f"Loading embedding model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                self.embedding_dimension = self.model.get_sentence_embedding_dimension()
                logger.info(f"Model loaded successfully. Dimension: {self.embedding_dimension}")
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {e}")
                raise
    
    def embed(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """
        Generate embeddings for a list of texts with batch processing.
        
        Args:
            texts: List of text strings to embed
            batch_size: Optional batch size (overrides default)
            
        Returns:
            Numpy array of embeddings with shape (n_texts, embedding_dimension)
        """
        if not texts:
            return np.array([]).reshape(0, self.embedding_dimension)
        
        if self.model is None:
            self._load_model()
        
        # Use provided batch size or default
        batch_size = batch_size or self.batch_size
        
        # If only one text, process directly
        if len(texts) <= batch_size:
            return self._embed_batch(texts)
        
        # Process in batches
        logger.debug(f"Processing {len(texts)} texts in batches of {batch_size}")
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = self._embed_batch(batch_texts)
            all_embeddings.append(batch_embeddings)
            
            # Log progress for large batches
            if len(texts) > batch_size * 2:
                progress = min(i + batch_size, len(texts))
                logger.debug(f"Embedding progress: {progress}/{len(texts)} texts")
        
        # Combine all embeddings
        return np.vstack(all_embeddings)
    
    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed a single batch of texts."""
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=len(texts),  # Use batch size equal to number of texts
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
                device=self.model.device
            )
            return embeddings
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}")
            # Try with smaller batch size if failed
            if len(texts) > 1:
                logger.warning(f"Reducing batch size from {len(texts)} to 1")
                return self._embed_one_by_one(texts)
            raise
    
    def _embed_one_by_one(self, texts: List[str]) -> np.ndarray:
        """Embed texts one by one as fallback."""
        embeddings = []
        for text in texts:
            try:
                embedding = self.model.encode(
                    [text],
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                embeddings.append(embedding[0])
            except Exception as e:
                logger.error(f"Failed to embed text: {text[:50]}... Error: {e}")
                # Return zero vector as fallback
                embeddings.append(np.zeros(self.embedding_dimension))
        
        return np.array(embeddings)
    
    def embed_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            
        Returns:
            Numpy array of embedding
        """
        return self.embed([text])[0]
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings."""
        if self.model is None:
            self._load_model()
        return self.embedding_dimension
    
    def set_batch_size(self, batch_size: int):
        """Update the batch size."""
        if batch_size > 0:
            self.batch_size = batch_size
            logger.info(f"Batch size updated to {batch_size}")
        else:
            logger.warning(f"Ignoring invalid batch size: {batch_size}")