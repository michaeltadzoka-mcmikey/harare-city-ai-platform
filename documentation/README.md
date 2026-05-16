# Harare City Council LLM Gateway

[![Version](https://img.shields.io/badge/version-6.0.0-blue.svg)](https://github.com/harare-llm-gateway)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)

## Overview

The **Harare City Council LLM Gateway** is a production‑ready, zero‑tuning conversational AI system that provides citizens with intelligent, governed access to municipal services. It combines:

- **LLM Gateway** – Central orchestrator (FastAPI).
- **RAG (Retrieval‑Augmented Generation)** – Knowledge retrieval from council documents.
- **RASA** – Structured report collection (forms).
- **Dashboard** – Admin UI for reports, knowledge gaps, overrides, and analytics.
- **Ollama** – Local LLM inference (`llama3.2:1b`).

> **Zero‑tuning guarantee:** After deployment, you never need to change the Python code. All improvements happen through document updates or configuration changes.

## Quick Start (5 minutes)

1. **Install Ollama** and pull the model:
   ```bash
   ollama pull llama3.2:1b
   ollama serve