# Harare City Council AI Platform – Architecture

## Product Vision

**A natural‑language municipal service assistant that citizens can talk to naturally, while every response remains grounded in official council documents.**

This is not a chatbot experiment. It is a **modular municipal AI platform** designed to evolve from answering questions into handling real workflows—reporting infrastructure issues, permit applications, balance enquiries, and future citizen service requests.

## The Three Pillars

The platform is built on three equally important pillars:

| Pillar | Purpose |
|--------|---------|
| **Citizen AI Assistant** | Natural language interaction—understanding messy citizen questions and providing clear, sourced answers |
| **Workflow & Reporting Engine** | Structured municipal processes—deterministic data collection for reliability |
| **Governance Dashboard** | Administrative control and operational oversight—keeping the AI trustworthy, maintainable, and auditable |

Without the dashboard, the system is a smart Q&A bot. With the dashboard, it becomes a **manageable municipal AI platform**—a system that can be governed, improved, and trusted over years of operation.

## Architectural Philosophy

> **Use AI where flexibility is needed. Use deterministic systems where reliability is required.**

Every design decision follows this principle:

| Concern | Approach | Why |
|---------|----------|-----|
| Understanding messy citizen language | LLM (local or cloud) | Flexibility |
| Authoritative facts | RAG retrieval from council documents | Accuracy |
| Structured data collection | Deterministic workflow engine (RASA) | Reliability |
| Safety and validation | Rule‑based guardrails | Governance |

This separation means each component can be independently scaled, replaced, or upgraded—a deliberate choice for long‑term municipal deployment.

## High‑Level Architecture

```
Citizen Message
       │
       ▼
┌─────────────────┐
│  LLM Gateway    │  ← Orchestration layer
│  (Port 8001)    │    Intent, rewrite, retrieval, synthesis, guardrails
└───────┬─────────┘
        │
   ┌────┼────────────┐
   │    │            │
   ▼    ▼            ▼
┌──────┐ ┌──────┐ ┌──────┐
│ RAG  │ │LLM   │ │RASA  │
│System│ │Models│ │Engine│
│(8000)│ │(11434│ │(5005)│
└──────┘ └──────┘ └──────┘
   │                  │
   ▼                  ▼
┌──────┐         ┌──────────┐
│ChromaDB│       │Dashboard │
│Vector │        │(5000)    │
│Store  │        └──────────┘
└──────┘
```

## Core Components

| Component | Role |
|-----------|------|
| **LLM Gateway** | Orchestration: intent classification, query rewriting, RAG retrieval, LLM synthesis, safety guardrails |
| **RAG System** | Authority layer: document ingestion, semantic search, temporal validity, contradiction detection |
| **Dashboard** | Governance layer: document management, knowledge gaps, overrides, conflict resolution, analytics |
| **RASA Engine** | Transactional layer: deterministic step‑by‑step workflows for structured data collection (reports, future permits) |
| **Ollama** | Local AI runtime: serves models for intent, rewrite, and offline synthesis |

## Expansion‑Ready Platform

The architecture was deliberately designed so the same infrastructure supports both current and future capabilities:

| Current Capability | Future Capability (same architecture) |
|-------------------|---------------------------------------|
| Natural language Q&A | Bill balance enquiries |
| Information retrieval | Permit applications |
| Pothole reports | Service request tracking |
| Jurisdiction routing | Payments |
| Guided reporting flows | Citizen account systems |

The reporting workflow exists primarily to demonstrate that the architecture can seamlessly evolve from informational AI into **transactional government services**.

## Hybrid Local + Cloud Architecture

The system separates AI responsibilities so municipalities can choose between cost, performance, privacy, and hardware constraints—not be locked into any single vendor.

| Layer | Current Default | Rationale |
|-------|----------------|-----------|
| Intent detection | Local Llama 1B | Cheap, fast, always available |
| Query rewriting | Local Llama 1B | Low latency |
| Retrieval | Fully local (ChromaDB) | Reliability and privacy |
| Final synthesis | Cloud model (configurable) | Better fluency when available |
| Fallback | Local generation + document search | Offline resilience |

**Full offline mode:** set all stages to local models. Zero internet required.  
**Cloud‑boosted mode:** use local models for routine tasks, cloud only for final polish.

## Governance as a First‑Class Layer

Safety checks, jurisdiction validation, and audit logging are not afterthoughts—they are independent layers that apply to every response, regardless of which model or retrieval method was used. The system includes:

- **Hallucination guard** – validates numbers, timeframes, and jurisdiction claims against source documents
- **Knowledge gap detection** – unanswered questions are logged and surfaced to administrators
- **Human override system** – administrators can pin answers, correct errors, or freeze documents
- **Conflict resolution** – when documents contradict, the system escalates to human review with deterministic precedence rules
- **Immutable audit trail** – every action is logged for accountability

## Data Flow

1. Citizen message arrives at the Gateway.
2. Intent classified (LLM or fast‑path regex).
3. Query rewritten for better retrieval (LLM).
4. RAG retrieves relevant chunks from ChromaDB (semantic + keyword search).
5. Chunks are re‑ranked with heading, title, and tag boosts.
6. Synthesis prompt generates a citizen‑friendly answer (cloud or local LLM).
7. Hallucination guard validates numbers, timeframes, and jurisdiction.
8. If the answer is uncertain, a local file scanner extracts the best matching paragraph directly from source documents.
9. Final response returned to the citizen.
