

## Production vs Development

| Aspect | Development | Production |
|--------|-------------|-------------|
| Web server | Flask/Werkzeug dev server | Gunicorn (Linux) / Waitress (Windows) |
| Database | SQLite | PostgreSQL |
| Session store | In‑memory | Redis |
| Rate limiting | In‑memory | Redis |
| Embedding model | Downloaded on first run | Pre‑cached, offline mode enabled |
| API keys | Hardcoded in `.env` | Managed via secrets manager |

## Production Architecture

- **LLM Gateway** – behind a reverse proxy (nginx) with SSL termination.
- **RAG** – separate process, can be scaled horizontally.
- **RASA** – single instance with Redis tracker store.
- **Dashboard** – served via WSGI server (Gunicorn/Waitress).
- **Ollama** – on same machine (or GPU instance).

## Environment Variables (Production)

Set these in your deployment environment (systemd, Docker, Kubernetes secrets):

```bash
# Gateway
DASHBOARD_API_KEY=<strong-random-key>
LLM_GATEWAY_API_KEY=<another-key>

# Dashboard
INBOUND_API_KEY=<same-as-DASHBOARD_API_KEY>
DATABASE_URL=postgresql://user:pass@host/db
REDIS_URL=redis://redis:6379/0