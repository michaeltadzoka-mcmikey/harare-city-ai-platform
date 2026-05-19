# Harare City Council AI Platform

> 🎥 [Watch Full Demo (9 minutes) https://youtu.be/d9Vfx6875o0?feature=shared

A governance-aware municipal AI platform built for the City of Harare, 
Zimbabwe. Combines intelligent document retrieval, LLM orchestration, 
structured workflow automation, and administrative governance — designed 
for institutional self-hosting in African government environments.

Built during and after industrial attachment at the City of Harare.

---

## This Is Not A Simple Chatbot

This is a complete municipal AI platform with five integrated components:

| Component | Role |
|---|---|
| LLM Gateway | Intent detection, reasoning, conversation orchestration |
| RAG System | Verified knowledge retrieval from official documents |
| RASA Workflow Engine | Structured citizen reporting and transactions |
| Redis | Conversation context and session management |
| Administrative Dashboard | Document governance, analytics, access control |

---

## Core Design Philosophy — Truth First

The system never invents answers. If the answer is not in the 
approved knowledge base, the system logs a knowledge gap instead 
of hallucinating. Administrators review gaps and generate draft 
documents directly from them — the system improves itself over time.

---

## What Citizens Can Do

- Ask questions in natural language about any municipal service
- Receive accurate answers sourced exclusively from verified documents
- Report burst pipes, potholes, illegal dumping through a guided 
  conversational form
- Receive a unique reference number for tracking their report

---

## Administrative Dashboard Features

- **Documents** — full metadata management with validity dates, 
  service area tagging, conflict detection, and version history
- **Knowledge Gaps** — every unanswered question logged and reviewable, 
  with one-click draft document generation
- **Analytics** — clarification rates, follow-up success, 
  recurrence patterns
- **Reports** — structured citizen complaints with duplicate 
  detection and categorisation
- **Access Control** — granular permissions with immutable audit trail

---

## Deployment Flexibility

The system supports two deployment modes switched by a single 
config change:

| Stage | Demo Mode | Fully Offline Mode |
|---|---|---|
| Intent detection | Local lightweight model | Local model |
| Query rewriting | Local lightweight model | Local model |
| Answer synthesis | Groq API (cloud) | Local model |
| Fallback | Automatic local fallback | Always local |

Fully offline mode requires no internet connection and no API keys. 
Designed for African government environments with variable connectivity.

---

## Architecture Readiness For Expansion

The RASA workflow engine is built for transactional expansion. 
Current: citizen reporting. Ready for: balance enquiries, permit 
applications, service requests, payment follow-ups. Adding a new 
transaction is a new form, not a new system.

---

## Tech Stack

Python · Flask · RAG Architecture · ChromaDB · RASA · Redis · 
Groq API · SQLite · LLM Orchestration · HTML/CSS · JavaScript

---

## Running The Demo

```bash
# Clone the repository
git clone [your repo URL]
cd harare-city-ai-platform

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Groq API key and paths

# Start all services
python start_services.py

# Access dashboard
# Open browser: localhost:5000
```

See SETUP.md for full installation instructions and 
offline mode configuration.

---

## About

Built during industrial attachment at the City of Harare (Sept 2025 
– April 2026) and continued independently after attachment ended.

Michael Tadzoka — Bindura University of Science Education  
Software Engineering, graduating 2027

www.linkedin.com/in/michael-tadzoka· [Demo Video]  https://youtu.be/d9Vfx6875o0?feature=shared
