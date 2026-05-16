"""
LLM Gateway package initializer.
Sets up global instances and imports.
"""

from .llama_client import LlamaClient
from .rag_client import RagClient
from .rasa_client import RasaClient
from .session_manager import session_manager
from .precedence_engine import precedence_engine
from .time_filter import TimeFilter
from .override_manager import OverrideManager
from .sanitizer import Sanitizer
from .contradiction_handler import ContradictionHandler
from .decision_ledger import DecisionLedger
from .response_formatter import ResponseFormatter
from .workflow_orchestrator import WorkflowOrchestrator
from .domain_handler import domain_handler
from .domain_classifier import domain_classifier
from .form_continuation import form_handler
from .knowledge_gap_logger import gap_logger
from .intent_analyzer import EnhancedIntentAnalyzer, intent_analyzer
from .location_resolver import location_resolver
from .emergency_manager import emergency_manager
# Do NOT import dashboard_client globally – it is configured in main.py
# from .dashboard_client import dashboard_client  <-- REMOVED
from .monitoring import *
from .redis_client import redis_client_instance, get_redis_client
from .query_type_classifier import QueryTypeClassifier
from .reasoning import ReasoningEngine
from .explainability import ExplainabilityGenerator

__all__ = [
    'LlamaClient',
    'RagClient',
    'RasaClient',
    'session_manager',
    'precedence_engine',
    'TimeFilter',
    'OverrideManager',
    'Sanitizer',
    'ContradictionHandler',
    'DecisionLedger',
    'ResponseFormatter',
    'WorkflowOrchestrator',
    'domain_handler',
    'domain_classifier',
    'form_handler',
    'gap_logger',
    'EnhancedIntentAnalyzer',
    'intent_analyzer',
    'location_resolver',
    'emergency_manager',
    # 'dashboard_client',  # removed from exports
    'redis_client_instance',
    'get_redis_client',
    'QueryTypeClassifier',
    'ReasoningEngine',
    'ExplainabilityGenerator',
]