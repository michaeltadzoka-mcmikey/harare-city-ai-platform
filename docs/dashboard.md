# Dashboard – Governance & Administration Layer

## Role in the Platform

The Dashboard is the **administrative control centre** for the municipal AI platform. It transforms the system from a smart Q&A bot into a **manageable, governable, and auditable municipal platform**.

Without the dashboard, the system would be an AI that answers questions—but with no way to manage knowledge over time, track unanswered questions, resolve contradictions, or ensure quality. The dashboard solves the biggest real‑world AI problem: **who maintains the knowledge base, and how?**

## The Three Pillars of Governance

The dashboard provides three categories of operational control:

| Pillar | What It Does |
|--------|-------------|
| **Knowledge Management** | Document lifecycle, metadata enforcement, version control, expiry tracking |
| **Operational Oversight** | Knowledge gap detection, conflict resolution, report review, analytics |
| **Governance Controls** | Human overrides, authority management, audit logging, permission enforcement |

## Key Features

### 1. Knowledge Gap Detection
The platform continuously identifies unanswered citizen questions and surfaces them to administrators as actionable knowledge gaps. When the same question goes unanswered repeatedly, it is escalated. Administrators can generate document drafts directly from gaps, ensuring the knowledge base improves over time.

This is a **self‑improving architecture**—not a static system.

### 2. Document Lifecycle Management
- Mandatory metadata for every document (content type, validity dates, service area, topic tags)
- Automatic expiry enforcement—expired documents are excluded from retrieval
- Version control with side‑by‑side diff
- Overlap detection when two active documents cover the same topic
- Content‑type‑specific templates (procedure, policy, FAQ, fee schedule, emergency, contact directory)

### 3. Governance & Overrides
- **Pinned overrides** – administrators can force specific answers for specific queries
- **Emergency notices** – temporary priority overrides for urgent situations
- **Authority precedence** – deterministic rules resolve conflicts between documents
- **Conflict escalation** – unresolved conflicts are automatically escalated with timed notifications
- **Provisional auto‑resolution** – if conflicts remain unresolved, the system provisionally resolves them and queues for mandatory human review

### 4. Conflict Resolution Engine
When two documents contradict each other, the system applies a deterministic precedence order:
1. Manual overrides
2. Emergency flags
3. Content type hierarchy (statutory > policy > notice > informational)
4. Active validity window
5. Most recent effective date
6. Exact service match
7. Cross‑service flag allowance
8. Escalation to human review

This is not a simple chatbot feature—it is **institutional governance architecture**.

### 5. Intelligence Metrics
The dashboard tracks:
- **Clarification rate** – how often the system needs to ask follow‑up questions
- **Recurrence rate** – how often resolved knowledge gaps reappear
- **Benchmark scoring** – weekly evaluation on a curated test set
- **User satisfaction** – aggregate feedback from citizens

These metrics enable **scientific, data‑driven improvement** of the platform.

### 6. Citizen Report Management
Infrastructure reports submitted through the RASA workflow are displayed for review. Administrators can:
- View and search all reports
- Merge duplicate reports
- Manage spam keywords
- Track report status and resolution

## Permissions

Access is controlled by a two‑flag system:

| Flag | Access |
|------|--------|
| **Manage Knowledge** | Full document, gap, override, and conflict management |
| **Manage Users** | User administration |
| **Both** | Complete system access |

All administrative actions are logged in an **immutable audit trail**—every change is traceable to a specific user and timestamp.

## Why This Matters

Most student AI projects stop at the chatbot interface. This dashboard demonstrates an understanding that **real production AI systems require operational governance**—they need to be maintained, monitored, and improved over time by non‑technical administrators. That is enterprise‑grade thinking, and it transforms this project from a demo into a platform.
