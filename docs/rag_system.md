# RAG System – Authority Layer

## Role in the Platform

The RAG system is the **single source of truth** for all citizen‑facing information. It does not generate answers—it retrieves authoritative passages from verified council documents. Every response displayed to a citizen is traceable back to a specific document, version, and validity period.

This is the **retrieval-grounded foundation** that makes the platform hallucination‑resistant.

## System Philosophy

> **Retrieval is the authority layer. Synthesis is only a formatting convenience.**

The LLM never invents facts. It can only restructure or summarise what the RAG system returns. If the RAG system cannot find relevant documents, the system honestly admits the gap rather than guessing—and logs it for administrators to address.

## Core Capabilities

- **Document ingestion** – council administrators upload `.txt` files following a standard markdown template with mandatory metadata (document ID, title, version, department, validity dates, content type, service area, topic tags, related documents).
- **Automatic chunking** – documents are split into retrievable sections based on markdown headings (`##` and `###`), ensuring every section (Fee Table, Symptoms, Eligibility) is independently searchable.
- **Vector storage** – chunks are embedded using BGE‑base‑en‑v1.5 (768 dimensions) and stored in ChromaDB for fast semantic search.
- **Temporal validity** – documents with expired `valid_to` dates are automatically excluded from retrieval, ensuring citizens never receive outdated information.
- **Overlap detection** – when two active documents cover the same service and content type with overlapping validity, the system flags a conflict for human review.
- **Contradiction detection** – conflicting documents are detected and entered into a resolution queue with deterministic precedence rules.

## Integration Points

| Service | Endpoint | Purpose |
|---------|----------|---------|
| LLM Gateway | `POST /api/v1/query` | Retrieve relevant chunks for citizen queries |
| Dashboard | `POST /api/v1/ingest` | Ingest new or updated documents |
| Dashboard | `GET /api/v1/health` | Monitor index status |

## Document Lifecycle

1. **Creation** – administrators create documents through the Dashboard, following content‑type‑specific templates (procedure, policy, FAQ, fee schedule, emergency notice, contact directory).
2. **Validation** – metadata is validated for completeness and correctness.
3. **Ingestion** – the document is chunked, embedded, and stored in the vector database.
4. **Serving** – when citizens ask questions, the most relevant chunks are retrieved and provided to the Gateway for answer generation.
5. **Expiry** – when a document reaches its `valid_to` date, it is automatically excluded from retrieval.
6. **Updates** – new versions supersede old ones, with the previous version archived but recoverable.

## Why This Matters for Municipal AI

Most RAG systems fail in production because:
- Documents expire and no one notices
- Contradictions appear between overlapping documents
- Metadata becomes inconsistent over time
- Retrieval quality degrades without monitoring

This system was designed from the ground up to prevent these failures through:
- **Automated expiry enforcement**
- **Conflict detection and escalation**
- **Strict metadata validation**
- **Continuous knowledge gap monitoring**

The result is a knowledge base that remains trustworthy, maintainable, and auditable over years of operation—exactly what a municipality requires.
