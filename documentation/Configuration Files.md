Gateway (llm_gateway/gateway_config.yaml)

llm_gateway:
  llama:
    model: "llama3.2:1b"
    timeout: 300
  rag:
    url: "http://localhost:8000"
    top_k: 3
  rasa:
    server_url: "http://localhost:5005"
    timeout: 120
  dashboard:
    url: "http://localhost:5000"
    api_key: "${DASHBOARD_API_KEY}"
  # ... other settings




  Dashboard (harare_chatbot_dashboard/.env)


  SECRET_KEY=your-secret-key
INBOUND_API_KEY=change-this-in-production
DATABASE_URL=sqlite:///data/production.db