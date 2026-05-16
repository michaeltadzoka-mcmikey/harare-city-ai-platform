"""
Rasa Client for Harare LLM Gateway.
"""

import httpx
import logging

logger = logging.getLogger(__name__)

class RasaClient:
    def __init__(self, config):
        self.base_url = config["rasa"]["server_url"]
        self.timeout = config["rasa"].get("timeout", 120)  # increased default

    async def send_message(self, message: str, sender_id: str = "default"):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/webhooks/rest/webhook",
                    json={"sender": sender_id, "message": message}
                )
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        # Combine all messages
                        full_text = "\n".join([msg.get('text', '') for msg in data if msg.get('text')])
                        form_complete = self._is_form_complete(full_text)
                        return {"text": full_text, "form_complete": form_complete}
                return {"text": "I can help you report issues to Harare City Council. Please provide location, description, and urgency.", "form_complete": False}
        except httpx.TimeoutException:
            logger.error(f"RASA message timed out after {self.timeout}s")
            return {"text": "The report system is currently busy. Please try again in a moment.", "form_complete": True}
        except Exception as e:
            logger.warning(f"RASA error: {e}")
            return {"text": "The report system is currently busy. Please try again in a moment.", "form_complete": True}

    async def send_custom_message(self, payload: dict) -> dict:
        """Send a custom payload to RASA (e.g., trigger form)."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/webhooks/rest/webhook",
                    json=payload
                )
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        # Combine all messages into one response
                        full_text = "\n".join([msg.get('text', '') for msg in data if msg.get('text')])
                        return {"text": full_text, "metadata": data[0].get('metadata', {})}
                return {"text": "I'm sorry, I couldn't process that request.", "metadata": {}}
        except httpx.TimeoutException:
            logger.error(f"RASA custom message timed out after {self.timeout}s")
            return {"text": "The reporting service is taking too long. Please try again.", "metadata": {}}
        except Exception as e:
            logger.error(f"RASA custom message error: {e}")
            return {"text": "Unable to reach the reporting service.", "metadata": {}}

    def _is_form_complete(self, text: str) -> bool:
        text_lower = text.lower()
        complete_phrases = ["submitted successfully", "reference number", "thank you for reporting", "report cancelled", "is there anything else"]
        for phrase in complete_phrases:
            if phrase in text_lower:
                return True
        form_phrases = ["i'll need", "please provide", "proceed?", "location", "description", "urgency"]
        for phrase in form_phrases:
            if phrase in text_lower:
                return False
        return True

    async def health_check(self):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/")
                return response.status_code == 200
        except:
            return False