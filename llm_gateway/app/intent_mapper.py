"""
Intent Mapper: Converts generic intent labels from DistilBERT to domain‑specific intents.
"""

def map_to_domain_intent(generic_intent: str) -> str:
    """
    Map a generic intent label (from DistilBERT) to one of:
    - knowledge_query
    - report_intent
    - status_check
    - chitchat
    - other
    """
    mapping = {
        "greeting": "chitchat",
        "farewell": "chitchat",
        "thanks": "chitchat",
        "information seeking": "knowledge_query",
        "question asking": "knowledge_query",
        "opinion expressing": "chitchat",
        "complaint": "report_intent",
        "report": "report_intent",          # added
        "issue": "report_intent",           # added
        "problem": "report_intent",         # added
        "request": "knowledge_query",
        "confirmation": "chitchat",
        "other": "other",
    }
    normalized = generic_intent.strip().lower()
    return mapping.get(normalized, "knowledge_query")