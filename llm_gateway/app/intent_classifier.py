"""
DistilBERT Intent Classifier for Harare City Council LLM Gateway v5.5
Uses pre‑trained model from Hugging Face for fast, accurate intent classification.
"""

import logging
from transformers import pipeline

logger = logging.getLogger(__name__)

class DistilBertIntentClassifier:
    def __init__(self, model_name="Falconsai/intent_classification", device=-1):
        """
        Initialize the intent classifier.
        Args:
            model_name: Hugging Face model name (default: Falconsai/intent_classification)
            device: -1 for CPU, 0 for GPU
        """
        try:
            self.classifier = pipeline(
                "text-classification",
                model=model_name,
                device=device
            )
            logger.info(f"DistilBERT intent classifier loaded: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load intent classifier: {e}")
            raise

    def classify(self, text: str) -> dict:
        """
        Classify the intent of the given text.
        Returns a dict with 'intent' (label) and 'confidence' (score).
        """
        if not text:
            return {"intent": "other", "confidence": 0.0}
        result = self.classifier(text)[0]
        return {
            "intent": result['label'],
            "confidence": result['score']
        }