# RASA Reporting Engine – Transactional Workflow Layer

## Role in the Platform

The RASA engine handles **structured data collection**. While the LLM Gateway handles free‑form conversation, RASA manages deterministic step‑by‑step workflows where reliable data capture is critical—such as infrastructure reports.

This separation exists for a deliberate architectural reason: **conversational AI is good at understanding intent, but it is not reliable for collecting structured fields** (exact location, description, urgency). A workflow engine guarantees that every required field is collected, validated, and stored correctly.

## Why a Separate Workflow Engine?

> **Free‑form citizen questions are handled through semantic LLM reasoning. Structured reporting flows use deterministic step‑by‑step collection to guarantee reliable data capture.**

This is one of the most important design decisions in the platform. It reflects a mature AI engineering philosophy: **use AI where flexibility is needed, use deterministic systems where reliability is required.**

The reporting workflow exists not just to handle pothole reports—it exists to **demonstrate that the architecture can seamlessly evolve from informational AI into transactional government services**. The same engine can be extended to handle permit applications, service requests, appointment scheduling, and any other structured citizen‑to‑council transaction.

## How It Integrates

1. The LLM Gateway detects `report_intent` or frustration combined with an infrastructure issue.
2. The Gateway forwards the message to RASA.
3. RASA activates a structured form, collecting:
   - Description of the issue
   - Location (validated against known suburbs)
   - Landmark
4. Each field is validated (minimum length, spam detection).
5. On confirmation, RASA submits the report to the Dashboard.
6. The citizen receives a reference ID for tracking.
7. The citizen can later check the status of their report using the reference ID.

## Key Features

- **Spam detection** – keyword blacklist, repeated character detection, script injection prevention.
- **Rate limiting** – maximum 3 reports per session per hour to prevent abuse.
- **Dead‑letter queue** – if the Gateway is unreachable, reports are stored for later processing. Zero data loss.
- **Status checking** – citizens can query report status using their reference ID.

## Configuration

RASA runs as two processes:
```bash
rasa run --enable-api --port 5005       # NLU + dialogue management
rasa run actions --port 5055            # Custom action server
```

## Future Expansion

The same workflow engine can be extended to handle:
- Permit applications
- Service requests
- Appointment scheduling
- Any structured citizen‑to‑council transaction

This is not a reporting module bolted onto a chatbot. It is a **transactional platform capability** that will grow with the municipality's digital transformation.
