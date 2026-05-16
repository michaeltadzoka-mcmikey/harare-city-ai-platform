Your current `deployment.md` is a great foundation – it covers starting the services and ingesting documents. It just needs **four critical steps** added so that a new user can go from clone to a fully working system. I’ve written the updated file below; replace your current `docs/deployment.md` with it.

The only other file you may want to update is the main `README.md` – just add a line pointing to the deployment guide. I’ll show you that at the end.

---

## 📄 Updated `docs/deployment.md`

```markdown
# Deployment Guide – First‑Time Setup

This guide walks through setting up the complete Harare City Council AI Platform
**from a fresh clone of the repository**.

## Prerequisites

- **Windows** (tested) or Linux/macOS
- **Python 3.10+** installed
- **Ollama** installed from [ollama.com](https://ollama.com) and running in the background
- **Git** (to clone the repo)
- At least **8 GB RAM** (16 GB recommended for local synthesis)
- (Optional) A **Groq API key** from https://console.groq.com if you want cloud synthesis

## 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/harare-city-council-ai.git
cd harare-city-council-ai
```

## 2. Set up Python virtual environments

```bash
# RAG System
cd rag_system
python -m venv .venv_rag
.venv_rag\Scripts\activate        # Windows
pip install -r requirements.txt
cd ..

# LLM Gateway
cd llm_gateway
python -m venv .venv_llm
.venv_llm\Scripts\activate
pip install -r requirements.txt
cd ..

# Dashboard
cd harare_chatbot_dashboard
python -m venv .venv_harare_chatbot_dashboard
.venv_harare_chatbot_dashboard\Scripts\activate
pip install -r requirements.txt
cd ..

# RASA (optional, for reporting)
cd rasa
python -m venv .venv_rasa
.venv_rasa\Scripts\activate
pip install -r requirements.txt
cd ..
```

## 3. Pull local AI models

```bash
ollama pull llama3.2:1b
ollama pull llama3.2:3b
```

## 4. Configure API keys

The project includes **placeholder values** that are safe for local use.
Only one change is needed to enable the full cloud‑boosted demo.

### Gateway configuration (`gateway_config.yaml`)

Open `llm_gateway/gateway_config.yaml` and find the `synthesis` section:

```yaml
synthesis:
  provider: groq                     # or ollama for fully offline
  model: llama-3.1-8b-instant
  api_key: ""                        # ← Put your Groq API key here
```

If you don’t have a Groq key, change `provider: ollama` and `model: llama3.2:3b`.
The rest of the file works out‑of‑the‑box.

### Environment file (`.env`)

The `.env` file in the project root contains keys like `INBOUND_API_KEY` and
`DASHBOARD_API_KEY`. The default value `change-this-in-production` works for
local development. Only change them if you are deploying to a shared server.

## 5. Train the RASA model (for reporting)

The pre‑trained RASA models are **not stored in the repository**.
If you plan to use the `REPORT123` reporting workflow, you must train a model:

```bash
cd rasa
.venv_rasa\Scripts\activate
rasa train
cd ..
```

This creates a new model inside `rasa/models/`. Skip this step if you don’t need reporting.

## 6. Start the services (4 terminals)

### Terminal 1 – RAG System (Port 8000)
```bash
cd rag_system
.venv_rag\Scripts\activate
python -B -m uvicorn app.main:app --port 8000
```

### Terminal 2 – Dashboard (Port 5000)
```bash
cd harare_chatbot_dashboard
.venv_harare_chatbot_dashboard\Scripts\activate
python app.py
```

### Terminal 3 – LLM Gateway (Port 8001)
```bash
cd llm_gateway
.venv_llm\Scripts\activate
python -B -m uvicorn app.main:app --port 8001
```

### Terminal 4 – RASA (Port 5005) & Action Server (Port 5055)
```bash
cd rasa
.venv_rasa\Scripts\activate
rasa run --enable-api --port 5005       # Terminal 4a
rasa run actions --port 5055            # Terminal 4b (separate window)
```

## 7. Ingest the demo documents

The knowledge base (17 council documents) is already in `shared_documents/`,
but the vector index must be rebuilt.

1. Open `http://localhost:5000` in your browser.
2. Log in with the default admin credentials (see the Dashboard README if needed).
3. Navigate to **Documents** → import all `.txt` files from the following folders:
   - `shared_documents/by_service/water`
   - `shared_documents/by_service/roads`
   - `shared_documents/by_service/health`
   - `shared_documents/by_service/general`
4. Wait for ingestion to finish (the health endpoint will show the new chunk count).

## 8. Test the platform

Run the demo test script:
```powershell
.\Test-Demo-Video.ps1
```

Or manually send a chat request:
```powershell
$body = @{message="Hello"; user_id="test"; session_id="s1"; source="web"} | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8001/chat -Method Post -Body $body -ContentType "application/json"
```

## Deployment Modes

| Mode | Configuration |
|------|---------------|
| **Fully offline** | Set all `llm_stages` to `provider: ollama` in Gateway config |
| **Cloud‑boosted** | Use local models for intent/rewrite, cloud (Groq) for synthesis |
| **Production** | Add PostgreSQL, Redis, HTTPS, and proper authentication |

## Troubleshooting

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Ollama connection refused | Ollama not running | Start Ollama from the system tray or run `ollama serve` |
| ChromaDB empty after ingestion | Ingestion not performed or index corrupted | Delete `rag_system/data/chroma` and `manifest.json`, restart RAG, re‑ingest |
| Gateway “Internal error” | Old bytecode cached | Delete all `__pycache__` folders and restart |
| Groq rate limits | Free tier limits reached | Wait a few minutes or switch to `synthesis.provider: ollama` |
| RASA form not triggering | Model not trained | Run `rasa train` (Step 5) |
| RASA action server fails | Wrong API key or URL | Check that Dashboard URL and API keys match the defaults in `gateway_config.yaml` and `.env` |
```

---

## 📝 Optional: Update the main `README.md`

Add this near the top so visitors find the setup guide immediately:

```markdown
## 🚀 Quick Start
See the **[Deployment Guide](docs/deployment.md)** for step‑by‑step instructions.
```

---

## 🚀 Commit and push

```powershell
git add docs/deployment.md
# If you also update README:
git add README.md
git commit -m "Add first‑time setup steps: API keys, RASA training, ingestion"
git push
```

Now your repository is truly self‑contained – anyone can clone, configure, and run your entire municipal AI platform with zero guesswork.