# app/hallucination_guard.py
"""
Post‑processing guard that removes any email or phone number not present
in the evidence.  Only catches real contact formats.
"""

import re
import logging

logger = logging.getLogger(__name__)


def guard_hallucinations(answer: str, source_context: str) -> str:
    # Emails
    for email in re.findall(r'[\w.\-+]+@[\w.\-]+\.\w+', answer):
        if email.lower() not in source_context.lower():
            logger.warning(f"Hallucination removed: {email}")
            answer = answer.replace(email, "[contact the council directly]")

    # Phone numbers – at least 6 digits
    for phone in re.findall(r'(?:\+263\s?|0)[\d\s\-\(\)]{6,}', answer):
        normalised = re.sub(r'\s|-|\(|\)', '', phone)
        if normalised not in re.sub(r'\s|-|\(|\)', '', source_context):
            logger.warning(f"Hallucination removed: {phone}")
            answer = answer.replace(phone, "[the council hotline]")

    return answer