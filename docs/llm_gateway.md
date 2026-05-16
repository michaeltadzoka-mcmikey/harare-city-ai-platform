# LLM Gateway – Orchestration Layer

## Role in the Platform

The Gateway is the **central orchestrator**. It does not store knowledge (that's the RAG system) and it does not manage documents (that's the Dashboard). It coordinates: understanding what the citizen wants, finding the right information, and presenting it safely.

This separation of orchestration from knowledge storage and administration is a deliberate architectural choice—it allows each layer to be independently scaled, monitored, and upgraded.

## Design Philosophy

> **The Gateway separates concerns so that each AI responsibility can be independently configured, replaced, or upgraded.**

This means:
- Intent classification can use a different model than query rewriting.
- Synthesis can use a different model than intent.
- Everything can run locally for privacy, or selectively use cloud APIs for better fluency.
- The system never depends on any single AI provider.

## Architecture

```
Citizen Query
   │
   ▼
Fast‑path detection (greetings, external services, report triggers)
   │
   ▼
Intent classification (local LLM by default)
   │
   ▼
Query rewriting (local LLM by default)
   │
   ▼
RAG retrieval (always local – ChromaDB)
   │
   ▼
Synthesis (cloud or local – configurable)
   │
   ▼
Hallucination guard (validates numbers, timeframes, jurisdiction)
   │
   ▼
Self‑healing fallback (searches source documents if answer is weak)
   │
   ▼
Final response
```

## Hybrid Deployment Model

The architecture separates AI responsibilities so municipalities can choose between cost, performance, privacy, and hardware constraints—not be locked into any single vendor.

| Layer | Default | Can Be |
|-------|---------|--------|
| Intent | Local 1B | Any Ollama model or cloud API |
| Rewrite | Local 1B | Any Ollama model or cloud API |
| Synthesis | Groq (free cloud) | Local 3B, Grok, OpenAI, or any compatible API |
| Fallback | Local file search | Always available, zero dependency |

**Full offline mode:** set all three stages to local Ollama models. No internet required.  
**Cloud‑boosted mode:** use local models for fast, cheap tasks, and a cloud model only for the final answer polish.

This flexibility is critical for municipalities with varying infrastructure—some may have powerful local servers, others may prefer cloud services, and some may need to operate entirely offline for privacy or connectivity reasons.

## Configuration

All behaviour is controlled by a single YAML file. Switching from fully offline to cloud‑boosted takes one configuration change and a restart:

```yaml
llm_gateway:
  llm_stages:
    intent:
      provider: ollama
      model: llama3.2:1b
    rewrite:
      provider: ollama
      model: llama3.2:1b
    synthesis:
      provider: groq          # or ollama for offline
      model: llama-3.1-8b-instant
      api_key: "gsk_..."
```

## Safety Guarantees

- **Grounded answers** – the LLM is instructed to only use provided document chunks; it is prohibited from inventing facts, dates, phone numbers, or prices.
- **Hallucination guard** – post‑processing validates any numbers, dates, or jurisdiction claims against the source text before the answer reaches the citizen.
- **Self‑healing fallback** – if the synthesis produces a weak or uncertain answer, the system automatically searches the original `.txt` files and returns the best‑matching paragraph directly. This guarantees accurate information even when retrieval or synthesis underperforms.
- **Knowledge gap logging** – unanswered questions are sent to the Dashboard so administrators can create new documents to fill the gap.
- **External service redirection** – common queries about ZESA, police, ZINARA, etc., are intercepted and redirected with correct contact numbers—no RAG call needed.

## API

**`POST /chat`**
```json
{
  "message": "How do I apply for a new water connection?",
  "user_id": "citizen-123",
  "session_id": "session-abc",
  "source": "web"
}
```

Returns:
```json
{
  "response": "To apply for a new residential water connection, follow these steps: ...",
  "intent": "knowledge_query",
  "source": "orchestrator"
}
```

**`GET /health`** – returns status of Gateway and all connected services.
