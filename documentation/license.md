
---

## 2. `ARCHITECTURE.md`

```markdown
# System Architecture

## High‑Level Diagram
┌─────────────────────────────────────────────────────────────────────────────┐
│ External World │
│ (Dashboard Admin, Public Chat, WhatsApp, etc.) │
└─────────────────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LLM GATEWAY (FastAPI) │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│ │ Fast‑Path │ │ Governance │ │ Rate Limit │ │ Circuit Breaker │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────────┐│
│ │ Orchestrator (main handler) ││
│ │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ ││
│ │ │ Intent │ │ RAG Client │ │ RASA Client │ │ User Memory │ ││
│ │ │ Classifier │ │ (query, │ │ (forms, │ │ (session, │ ││
│ │ │ (LLM‑first) │ │ rewrite) │ │ trigger) │ │ facts) │ ││
│ │ └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘ ││
│ │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ ││
│ │ │ Trust Layer │ │ Cache │ │ Explainability│ │ Escalation │ ││
│ │ │ (source attr)│ │ (Redis) │ │ (citations) │ │ Handler │ ││
│ │ └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘ ││
│ └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
│
┌───────────────┬───────────┼───────────┬───────────────┐
▼ ▼ ▼ ▼ ▼
┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────────┐ ┌────────────┐
│ RAG │ │ RASA │ │Ollama│ │Dashboard │ │ External │
│ (port │ │ (port │ │(port │ │ (port │ │ APIs │
│ 8000) │ │ 5005) │ │11434)│ │ 5000) │ │ (ZESA,etc)│
└──────────┘ └──────────┘ └──────┘ └──────────┘ └────────────┘



## Components

### 1. LLM Gateway (FastAPI)
- **Role**: Central orchestrator, routes messages, manages state.
- **Key modules**:
  - `orchestrator.py` – main pipeline (governance, fast‑path, intent, RAG, RASA, post‑processing).
  - `semantic_classifier.py` – LLM‑first intent classification using descriptions.
  - `rag_client.py` – calls RAG, rewrites queries with history.
  - `rasa_client.py` – sends messages to RASA, handles trigger payloads.
  - `session_manager.py` – stores conversation history, RASA form state, user facts.
  - `knowledge_gap_logger.py` – logs unanswered questions to Dashboard.

### 2. RAG System (Chroma)
- **Role**: Retrieves relevant document chunks.
- **Port**: 8000.
- **Key features**: Vector search, metadata filtering, chunk preview.
- **Document standard**: See [RAG_DOCUMENT_STANDARD.md](RAG_DOCUMENT_STANDARD.md).

### 3. RASA (Forms)
- **Role**: Structured data collection (reports, future forms).
- **Ports**: 5005 (server), 5055 (actions).
- **Key components**:
  - `domain.yml` – intents, slots, forms, responses.
  - `rules.yml` – deterministic conversation paths.
  - `actions.py` – custom actions (submit report, check status, activate trigger).
  - `nlu.yml` – training data (minimal, because gateway handles intent).

### 4. Dashboard (Flask)
- **Role**: Admin UI, report management, knowledge gaps, overrides.
- **Port**: 5000.
- **Key modules**:
  - `routes/reports.py` – report CRUD, status API, spam management.
  - `routes/knowledge_gaps.py` – gap lifecycle, drafts, resolution.
  - `routes/documents.py` – document ingestion, overrides, conflicts.
  - `routes/chat.py` – admin chat.
  - `routes/public_chat.py` – citizen chat (no login).
  - `routes/conversations.py` – conversation viewer.

### 5. Ollama
- **Role**: Local LLM inference.
- **Port**: 11434.
- **Model**: `llama3.2:1b` (default) or `phi3:mini`.

## Data Flows

### Knowledge Query (RAG)
1. User message → Gateway.
2. Fast‑path (no match) → Spell correction → Intent classification (`knowledge_query`).
3. RAG client rewrites query with history → calls RAG.
4. LLM synthesises answer using retrieved chunks.
5. Trust layer adds source attribution.
6. Response returned.

### Report Submission (Trigger Word)
1. User sends `REPORT123` → Fast‑path matches.
2. Gateway sets `in_rasa_form=True` and sends `__trigger__` payload to RASA.
3. RASA activates `report_form`, returns description prompt.
4. All subsequent messages in same session are forwarded directly to RASA (bypass LLM).
5. RASA collects description, location, landmark, then confirmation.
6. On `CONFIRM`, RASA calls gateway `/webhook/rasa` → gateway forwards to Dashboard `/api/reports`.
7. Dashboard returns reference ID → RASA returns to user.
8. Gateway clears `in_rasa_form`.

### Direct Status Check
1. User sends `HCC-RPT-2026-00001` → Fast‑path matches.
2. Gateway calls Dashboard `/api/reports/status` directly.
3. Returns status (bypasses RASA).

### Knowledge Gap Logging
1. Gateway fails to answer (low confidence, timeout, fallback phrases).
2. Calls Dashboard `/knowledge-gaps/api/inbound` with question and metadata.
3. Dashboard creates a `KnowledgeGap` record.
4. Admin can review and resolve later.

## Zero‑Tuning Principle

| Item | Change Frequency | What you do |
|------|------------------|--------------|
| Intent descriptions | Quarterly | Add new intent type |
| System prompt | Quarterly | Update tone or scope |
| RAG documents | As policies change | Add/update/retire documents |
| Spell dictionary | Monthly | Add new suburb names |
| **Gateway code** | **NEVER** | No changes needed |

## Security

- **API keys** – `DASHBOARD_API_KEY` must match Dashboard’s `INBOUND_API_KEY`.
- **Rate limiting** – 20 requests per minute per session, 200 per day.
- **Circuit breaker** – opens if error rate >50% in 60 seconds.
- **Governance gate** – blocks profanity, injection, out‑of‑scope topics.
- **Sanitizer** – strips prompt injection from retrieved documents.