"""
Multi‑provider LLM client – local Ollama, cloud Groq, or any OpenAI‑compatible API.
"""
import aiohttp
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class LLMProvider:
    def __init__(self, config: dict):
        self.provider = config.get("provider", "ollama")
        self.model = config.get("model", "llama3.2:1b")
        self.url = config.get("url", "http://localhost:11434")
        self.api_key = config.get("api_key", "")
        self.timeout = config.get("timeout", 60)

    async def chat(self, messages: List[Dict[str, str]], max_tokens=300, temperature=0.0) -> Optional[str]:
        if self.provider == "grok":
            return await self._call_openai_compatible(
                messages, max_tokens, temperature,
                base_url="https://api.x.ai/v1",
                model=self.model, api_key=self.api_key
            )
        elif self.provider == "groq":
            return await self._call_openai_compatible(
                messages, max_tokens, temperature,
                base_url="https://api.groq.com/openai/v1",
                model=self.model, api_key=self.api_key
            )
        elif self.provider == "openai_compatible":
            return await self._call_openai_compatible(
                messages, max_tokens, temperature,
                base_url=self.url, model=self.model, api_key=self.api_key
            )
        elif self.provider == "ollama":
            return await self._call_ollama(messages, max_tokens, temperature)
        else:
            logger.error(f"Unknown provider: {self.provider}")
            return None

    async def _call_ollama(self, messages, max_tokens, temperature):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.url}/api/chat", json=payload, timeout=self.timeout) as resp:
                    data = await resp.json()
                    return data["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return None

    async def _call_openai_compatible(self, messages, max_tokens, temperature,
                                      base_url: str, model: str, api_key: str):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{base_url}/chat/completions",
                                  json=payload, headers=headers,
                                  timeout=self.timeout) as resp:
                    data = await resp.json()
                    if "choices" not in data:
                        logger.error(f"Groq/OpenAI response missing 'choices': {data}")
                        return None
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI‑compatible call failed: {e}")
            return None