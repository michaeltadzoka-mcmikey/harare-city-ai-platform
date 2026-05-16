1. # Installation Guide

## System Requirements

| Component | CPU (cores) | RAM | Disk | GPU (optional) |
|-----------|-------------|-----|------|----------------|
| Ollama | 8 | 16 GB | 2 GB | NVIDIA T4/RTX 3060 |
| RAG | 4 | 4 GB | 20 GB | – |
| RASA | 2 | 2 GB | 1 GB | – |
| Gateway | 2 | 1 GB | 1 GB | – |
| Dashboard | 2 | 2 GB | 10 GB | – |
| **Total** | **18** | **25 GB** | **34 GB** | – |

*With GPU, inference times drop to < 1 second.*

## Prerequisites

- **Python 3.10+** (for all components)
- **Ollama** – [Download](https://ollama.com/download)
- **Node.js** (only if you modify RASA frontend – optional)
- **Git**

## Step‑by‑Step Installation

### 1. Clone the Repository

```bash
git clone https://github.com/harare/llm-gateway.git
cd llm-gateway



2. Install Ollama and Pull the Model
ollama pull llama3.2:1b
ollama serve   # keep this terminal open

3. Set Up the RAG System

cd rag_system
python -m venv venv
source venv/bin/activate   # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py   # runs on port 8000


4. Set Up RASA

cd rasa
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
rasa train   # train the model (once)
rasa run --enable-api --port 5005   # server
# in another terminal, same directory:
rasa run actions --port 5055        # action server

5. Set Up the Dashboard

cd harare_chatbot_dashboard
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your secrets
python app.py          # runs on port 5000

6. Set Up the LLM Gateway

cd llm_gateway
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DASHBOARD_API_KEY
export DASHBOARD_API_KEY="change-this-in-production"   # or set in .env
uvicorn app.main:app --port 8001