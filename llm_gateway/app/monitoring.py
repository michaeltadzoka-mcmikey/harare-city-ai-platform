"""
Prometheus Monitoring for Harare City Council LLM Gateway v5.3
Metrics registry and exporters for operational visibility
"""

import logging
from prometheus_client import (
    Counter, Histogram, Gauge, Info,
    generate_latest, CONTENT_TYPE_LATEST
)
from fastapi.responses import Response

logger = logging.getLogger(__name__)

# ===== COUNTERS =====

# Total requests
llm_gateway_requests_total = Counter(
    'llm_gateway_requests_total',
    'Total number of chat requests',
    ['source', 'workflow']
)

# Confidence bands
llm_gateway_confidence_band_total = Counter(
    'llm_gateway_confidence_band_total',
    'Total requests by confidence band',
    ['band']  # insufficient, low, medium, high
)

# Expired documents filtered
llm_gateway_expired_docs_filtered_total = Counter(
    'llm_gateway_expired_docs_filtered_total',
    'Total expired documents filtered out'
)

# Documents with missing validity metadata
llm_gateway_documents_missing_validity_total = Counter(
    'llm_gateway_documents_missing_validity_total',
    'Total documents with missing validity metadata'
)

# Service update injections
llm_gateway_service_updates_injected_total = Counter(
    'llm_gateway_service_updates_injected_total',
    'Total service updates injected before procedures'
)

llm_gateway_service_updates_skipped_already_ahead_total = Counter(
    'llm_gateway_service_updates_skipped_already_ahead_total',
    'Service updates skipped because already ahead'
)

# Conflict resolutions
llm_gateway_conflict_resolutions_total = Counter(
    'llm_gateway_conflict_resolutions_total',
    'Total document conflicts resolved',
    ['method', 'scope_overlap']  # method: newer|version|authority, scope_overlap: true|false
)

# Pinned override activations
llm_gateway_pinned_overrides_activated_total = Counter(
    'llm_gateway_pinned_overrides_activated_total',
    'Total pinned override activations',
    ['sufficient']  # sufficient: true|false
)

# Component hard floors triggered
llm_gateway_hard_floor_triggered_total = Counter(
    'llm_gateway_hard_floor_triggered_total',
    'Hard floor triggers',
    ['component']  # authority, freshness, retrieval
)

# Emergency mode
llm_gateway_emergency_mode_activations_total = Counter(
    'llm_gateway_emergency_mode_activations_total',
    'Emergency mode activations',
    ['mode']  # water_outage, health_alert, etc.
)

# Knowledge gaps
llm_gateway_knowledge_gaps_total = Counter(
    'llm_gateway_knowledge_gaps_total',
    'Knowledge gaps logged',
    ['gap_type']  # no_match, low_confidence, contradictory
)

# Citizen feedback
llm_gateway_citizen_feedback_total = Counter(
    'llm_gateway_citizen_feedback_total',
    'Citizen feedback submissions',
    ['feedback_type']  # incorrect, missing, outdated
)

# Overrides applied
llm_gateway_overrides_applied_total = Counter(
    'llm_gateway_overrides_applied_total',
    'Human authority overrides applied',
    ['override_type']  # freeze, correction, suspension, force_verbatim, pinned
)

# Decision ledger entries
llm_gateway_ledger_entries_total = Counter(
    'llm_gateway_ledger_entries_total',
    'Decision ledger entries written'
)

# Errors
llm_gateway_errors_total = Counter(
    'llm_gateway_errors_total',
    'Total errors',
    ['error_type']  # rag_failure, llm_failure, redis_failure, etc.
)

# Location inferences
llm_gateway_location_inferences_total = Counter(
    'llm_gateway_location_inferences_total',
    'Location inferences from messages'
)

# ===== HISTOGRAMS =====

# Response latency
llm_gateway_response_duration_seconds = Histogram(
    'llm_gateway_response_duration_seconds',
    'Response duration in seconds',
    ['workflow'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# RAG query duration
llm_gateway_rag_query_duration_seconds = Histogram(
    'llm_gateway_rag_query_duration_seconds',
    'RAG query duration in seconds',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

# LLM synthesis duration
llm_gateway_llm_synthesis_duration_seconds = Histogram(
    'llm_gateway_llm_synthesis_duration_seconds',
    'LLM synthesis duration in seconds',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0]
)

# Confidence scores
llm_gateway_confidence_score = Histogram(
    'llm_gateway_confidence_score',
    'Confidence scores',
    ['component'],  # retrieval, authority_raw, authority_multiplied, freshness, composite
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# ===== GAUGES =====

# Active sessions
llm_gateway_active_sessions = Gauge(
    'llm_gateway_active_sessions',
    'Number of active sessions'
)

# Active emergency modes
llm_gateway_active_emergency_modes = Gauge(
    'llm_gateway_active_emergency_modes',
    'Number of active emergency modes'
)

# Active overrides
llm_gateway_active_overrides = Gauge(
    'llm_gateway_active_overrides',
    'Number of active overrides',
    ['override_type']
)

# ===== INFO =====

# Version info
llm_gateway_info = Info(
    'llm_gateway',
    'LLM Gateway version and configuration'
)

# Set version info
llm_gateway_info.info({
    'version': '5.3.0',
    'deployment': 'production'
})

# ===== METRICS ENDPOINT =====

async def metrics_endpoint():
    """
    Prometheus metrics endpoint.
    
    Returns:
        Prometheus-formatted metrics
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# ===== HELPER FUNCTIONS =====

def increment_request(source: str, workflow: str):
    """Increment request counter."""
    llm_gateway_requests_total.labels(source=source, workflow=workflow).inc()

def record_confidence_band(band: str):
    """Record confidence band."""
    llm_gateway_confidence_band_total.labels(band=band).inc()

def record_expired_docs_filtered(count: int):
    """Record expired documents filtered."""
    llm_gateway_expired_docs_filtered_total.inc(count)

def record_missing_validity(count: int):
    """Record documents with missing validity."""
    llm_gateway_documents_missing_validity_total.inc(count)

def record_service_update_injection(injected: bool):
    """Record service update injection."""
    if injected:
        llm_gateway_service_updates_injected_total.inc()
    else:
        llm_gateway_service_updates_skipped_already_ahead_total.inc()

def record_conflict_resolution(method: str, scope_overlap: bool):
    """Record conflict resolution."""
    llm_gateway_conflict_resolutions_total.labels(
        method=method,
        scope_overlap=str(scope_overlap).lower()
    ).inc()

def record_pinned_override(sufficient: bool):
    """Record pinned override activation."""
    llm_gateway_pinned_overrides_activated_total.labels(
        sufficient=str(sufficient).lower()
    ).inc()

def record_hard_floor_trigger(component: str):
    """Record hard floor trigger."""
    llm_gateway_hard_floor_triggered_total.labels(component=component).inc()

def record_emergency_activation(mode: str):
    """Record emergency mode activation."""
    llm_gateway_emergency_mode_activations_total.labels(mode=mode).inc()

def record_knowledge_gap(gap_type: str):
    """Record knowledge gap."""
    llm_gateway_knowledge_gaps_total.labels(gap_type=gap_type).inc()

def record_citizen_feedback(feedback_type: str):
    """Record citizen feedback."""
    llm_gateway_citizen_feedback_total.labels(feedback_type=feedback_type).inc()

def record_override_applied(override_type: str):
    """Record override application."""
    llm_gateway_overrides_applied_total.labels(override_type=override_type).inc()

def record_ledger_entry():
    """Record decision ledger entry."""
    llm_gateway_ledger_entries_total.inc()

def record_error(error_type: str):
    """Record error."""
    llm_gateway_errors_total.labels(error_type=error_type).inc()

def record_location_inference():
    """Record location inference."""
    llm_gateway_location_inferences_total.inc()

def observe_response_duration(workflow: str, duration: float):
    """Observe response duration."""
    llm_gateway_response_duration_seconds.labels(workflow=workflow).observe(duration)

def observe_rag_duration(duration: float):
    """Observe RAG query duration."""
    llm_gateway_rag_query_duration_seconds.observe(duration)

def observe_llm_duration(duration: float):
    """Observe LLM synthesis duration."""
    llm_gateway_llm_synthesis_duration_seconds.observe(duration)

def observe_confidence(component: str, score: float):
    """Observe confidence score."""
    llm_gateway_confidence_score.labels(component=component).observe(score)

def set_active_sessions(count: int):
    """Set active sessions gauge."""
    llm_gateway_active_sessions.set(count)

def set_active_emergency_modes(count: int):
    """Set active emergency modes gauge."""
    llm_gateway_active_emergency_modes.set(count)

def set_active_overrides(override_type: str, count: int):
    """Set active overrides gauge."""
    llm_gateway_active_overrides.labels(override_type=override_type).set(count)

logger.info("✓ Prometheus monitoring initialized")