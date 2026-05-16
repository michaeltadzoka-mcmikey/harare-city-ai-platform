"""
LLM Client with unified system prompt.
Optimized for citizen-friendly responses - no reasoning leakage.
Now with streaming enabled and reduced context window.
STRICT ANTI-HALLUCINATION RULES: Never invent information not in evidence.
"""

import httpx
import logging
import json
import asyncio
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class LlamaClient:
    # ULTRA-STRICT SYSTEM PROMPT - FORBIDS HALLUCINATION
    SYSTEM_PROMPT = """You are Coh Connect, the official digital assistant for Harare City Council.

CRITICAL RULES - YOU MUST FOLLOW THESE:

1. NEVER show your thinking process. No "Step 1:", "Analysis:", or internal reasoning.
2. NEVER mention document IDs, source names, or department names in your response.
3. NEVER use emojis like ✅, ✔️, or ⚠️ in your responses.
4. Give short, friendly answers - maximum 4 sentences or 3 bullet points.
5. Use simple, clear language that any citizen can understand.

**ABSOLUTE PROHIBITION AGAINST HALLUCINATION:**
- If a piece of information (cost, timeline, phone number, address, etc.) is NOT explicitly stated in the provided evidence, you MUST say "I don't have that information" or "That information is not available."
- NEVER invent, assume, guess, or copy information from other contexts (e.g., do not apply water fees to road questions).
- If the evidence contains a placeholder like "[Department name]" or "[AUTO-GENERATED]", ignore it and say the information is unavailable.
- If the user asks "how long does it take to fix a pothole?" and the evidence does NOT contain a specific timeline, say "I don't have that information" rather than guessing.
- If the evidence contains a fee for one service (e.g., water connection), never apply it to another service (e.g., pothole repair).

**WHEN IN DOUBT, SAY YOU DON'T KNOW.** It is better to admit lack of information than to provide incorrect information.

Your role is to help citizens with municipal services: water, rates, waste, permits, health, and reporting issues.
Be warm, helpful, and clear. Stay factual – if you don't know, say so.
If the user writes in Shona or Ndebele, respond in the same language when possible.
"""

    def __init__(self, config: dict):
        self.model = config["llama"]["model"]
        self.base_url = config["llama"]["base_url"]
        self.timeout = config["llama"]["timeout"]
        self.max_tokens = config["llama"].get("max_tokens", {})
        self.num_ctx = config["llama"].get("num_ctx", 2048)   # ← NEW: configurable context window
        
        # Create optimized HTTP client with no read timeout for streaming
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=self.timeout,
                connect=30.0,
                read=None,  # No read timeout - critical for streaming
                write=None
            ),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        
        self.is_available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            import httpx
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                available = any(m.get("name") == self.model for m in models)
                logger.info(f"Ollama available, model {self.model} present: {available}")
                return available
        except Exception as e:
            logger.warning(f"Ollama HTTP check failed: {e}")
        try:
            import subprocess
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=2)
            available = result.returncode == 0 and self.model in result.stdout
            logger.info(f"Ollama subprocess check: {available}")
            return available
        except Exception as e:
            logger.warning(f"Ollama subprocess check failed: {e}")
        return False

    async def _call_llm(
        self, 
        messages: List[Dict], 
        temperature: float = 0.1, 
        max_tokens: int = None,
        retry: bool = True,
        stream: bool = True
    ) -> Optional[str]:
        """Call Ollama with streaming enabled by default."""
        if not self.is_available:
            logger.warning("LLM not available, skipping call")
            return None
        
        url = f"{self.base_url}/api/chat"
        max_tokens = max_tokens or self.max_tokens.get("synthesis", 150)
        
        # Optimized payload for llama3.2:3b on CPU
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": min(max_tokens, 200),
                "num_ctx": self.num_ctx,          # ← now configurable
                "num_thread": 4,
                "repeat_penalty": 1.1,
                "top_k": 40,
                "top_p": 0.9
            }
        }
        
        logger.debug(f"Sending request to {url} with model {self.model}, stream={stream}")
        
        try:
            if stream:
                full_response = ""
                async with self.client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        logger.warning(f"LLM returned {response.status_code}")
                        if retry:
                            await asyncio.sleep(1)
                            return await self._call_llm(messages, temperature, max_tokens, retry=False, stream=stream)
                        return None
                    
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                chunk = json.loads(line)
                                if "message" in chunk and "content" in chunk["message"]:
                                    full_response += chunk["message"]["content"]
                                if chunk.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
                
                result = full_response.strip()
                logger.debug(f"LLM response (first 100 chars): {result[:100]}")
                return result if result else None
                
            else:
                # Non-streaming fallback
                async with self.client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        logger.warning(f"LLM returned {response.status_code}")
                        if retry:
                            await asyncio.sleep(1)
                            return await self._call_llm(messages, temperature, max_tokens, retry=False, stream=stream)
                        return None
                    
                    full_response = ""
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                chunk = json.loads(line)
                                if "message" in chunk and "content" in chunk["message"]:
                                    full_response += chunk["message"]["content"]
                            except json.JSONDecodeError:
                                continue
                    
                    result = full_response.strip()
                    logger.debug(f"LLM response (first 100 chars): {result[:100]}")
                    return result if result else None
                    
        except httpx.TimeoutException:
            logger.error(f"LLM call timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def build_messages_with_history(
        self,
        current_prompt: str,
        memory: dict,
        max_history_turns: int = 4
    ) -> List[Dict]:
        """Build messages list including system prompt and conversation history."""
        messages = []

        messages.append({"role": "system", "content": self.SYSTEM_PROMPT})

        # Add user context if available
        profile = memory.get('user_profile', {})
        if profile.get('name') or profile.get('location'):
            context_lines = []
            if profile.get('name'):
                context_lines.append(f"User's name: {profile['name']}")
            if profile.get('location'):
                context_lines.append(f"User's area: {profile['location']}")
            if context_lines:
                messages.append({
                    "role": "system",
                    "content": "Context:\n" + "\n".join(context_lines)
                })

        # Add conversation history
        history = memory.get('interaction_history', [])
        recent = history[-(max_history_turns * 2):]
        for turn in recent:
            messages.append({
                "role": turn['role'],
                "content": turn['content']
            })

        messages.append({"role": "user", "content": current_prompt})
        return messages

    async def generate_response(self, message: str, context: str = None) -> str:
        """Simple response generation for chitchat."""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        if context:
            messages.append({"role": "system", "content": f"Context: {context}"})
        messages.append({"role": "user", "content": message})
        return await self._call_llm(messages, temperature=0.3, max_tokens=self.max_tokens.get("chitchat", 80), stream=True) or "I'm here to help. Please ask your question."

    async def rewrite_follow_up(self, question: str, history: List[str]) -> str:
        """Rewrite follow-up question to be self-contained."""
        prompt = f"Rewrite this question to be self-contained based on the conversation history.\nHistory:\n{history}\nQuestion: {question}\nRewritten question:"
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        return await self._call_llm(messages, temperature=0.2, max_tokens=self.max_tokens.get("rewrite", 80), stream=True) or question

    async def think_and_respond(self, question: str, context: str, memory: dict, sources: list) -> str:
        """
        Simplified direct response without chain-of-thought.
        This replaces the old reasoning method that was leaking internal steps.
        """
        prompt = f"""
Based ONLY on the information below, give a clear, helpful answer to the user's question.

Information: {context[:1500]}

Question: {question}

CRITICAL INSTRUCTION:
- If the information does NOT contain an answer to the question, say "I don't have that information." DO NOT invent an answer.
- If the question asks for a cost, fee, timeline, or any number, and the information does not explicitly provide it, say "That information is not available."
- NEVER assume or copy numbers from other topics.
- Keep your answer under 150 words.

Answer:"""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        return await self._call_llm(messages, temperature=0.3, max_tokens=200, stream=True) or "I'm sorry, I couldn't formulate an answer."

    async def should_ask_follow_up(self, question: str, context: str, memory: dict, sources: list) -> tuple[bool, str]:
        """Determine if a follow-up question would help."""
        prompt = f"""Based on the conversation, determine if a follow-up question would help the citizen.
If yes, return a single, natural follow-up question.
If no, return "NO".

Question: {question}
Context: {context[:500]}

Output: [YES/NO] | [question]"""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        result = await self._call_llm(messages, max_tokens=50, stream=True)
        if result and "YES" in result:
            parts = result.split("|", 1)
            if len(parts) > 1:
                return True, parts[1].strip()
        return False, ""

    async def verify_answer(self, question: str, answer: str, sources: List[Dict]) -> Dict[str, Any]:
        """Verify if answer addresses the question and check for hallucinated numbers."""
        prompt = f"""Question: "{question}"
Answer: "{answer}"

Does the answer contain any information (especially numbers, costs, dates) that was NOT present in the original evidence? If yes, flag as hallucination.
Output JSON: {{"complete": boolean, "hallucinated": boolean, "missing_info": []}}"""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        result = await self._call_llm(messages, temperature=0.1, max_tokens=150, stream=True)
        if result:
            try:
                return json.loads(result)
            except:
                pass
        return {"complete": True, "hallucinated": False, "missing_info": []}