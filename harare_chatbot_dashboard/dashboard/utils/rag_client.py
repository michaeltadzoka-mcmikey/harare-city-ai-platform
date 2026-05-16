import requests
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def _headers():
    return {'X-API-Key': current_app.config['RAG_API_KEY']}

def _url(path):
    if not path.startswith('/api/v1'):
        path = '/api/v1' + path
    return current_app.config['RAG_SYSTEM_URL'] + path

def _safe_request(method, path, **kwargs):
    timeout = kwargs.pop('timeout', 10)
    try:
        resp = requests.request(method, _url(path), headers=_headers(), timeout=timeout, **kwargs)
        if 200 <= resp.status_code < 300:
            try:
                return resp.json()
            except ValueError:
                return {'success': True, 'message': resp.text, 'raw': True}
        else:
            return {'error': f'HTTP {resp.status_code}', 'status': 'error'}
    except requests.exceptions.Timeout:
        return {'error': 'Timeout', 'status': 'offline'}
    except requests.exceptions.ConnectionError:
        return {'error': 'Connection refused', 'status': 'offline'}
    except Exception as e:
        return {'error': str(e), 'status': 'error'}

def rag_get_health():
    result = _safe_request('GET', '/health', timeout=10)
    if 'error' in result:
        return {'status': 'offline', 'chunks': 0, 'documents': 0, 'queue': 0, 'last_ingest': None}
    status = result.get('status', 'healthy')
    if status == 'degraded':
        status = 'healthy'
    return {
        'status': status,
        'chunks': result.get('index', {}).get('total_chunks_active', 0),
        'documents': result.get('documents', {}).get('total_documents', 0),
        'queue': 0,
        'last_ingest': result.get('last_ingest')
    }

def rag_get_detailed_health():
    result = _safe_request('GET', '/health/details', timeout=10)
    if 'error' in result:
        return {'status': 'offline', 'components': {}, 'uptime': None, 'last_error': None}
    return result

def rag_validate_document(doc_data):
    if hasattr(doc_data, '__table__'):
        content = doc_data.content
        metadata = {
            'document_id': doc_data.document_id,
            'title': doc_data.title,
            'service_area': doc_data.service_area,
            'content_type': doc_data.content_type,
            'department': doc_data.department,
            'owner_email': doc_data.owner_email,
            'valid_from': doc_data.valid_from.isoformat() if doc_data.valid_from else None,
            'valid_to': doc_data.valid_to.isoformat() if doc_data.valid_to else None,
            'locations': doc_data.locations,
            'authority_confidence': doc_data.authority_confidence,
            'confidence_source': doc_data.confidence_source,
            'prerequisites': doc_data.prerequisites,
            'related_documents': doc_data.related_documents,
            'topic_tags': doc_data.topic_tags,
            'review_cycle': doc_data.review_cycle,
            'cross_service_flag': doc_data.cross_service_flag,
            'authority_override': doc_data.authority_override,
        }
    else:
        content = doc_data.get('content', '')
        metadata = {
            'document_id': doc_data.get('document_id'),
            'title': doc_data.get('title'),
            'service_area': doc_data.get('service_area') or doc_data.get('service'),
            'content_type': doc_data.get('content_type') or doc_data.get('category'),
            'department': doc_data.get('department'),
            'owner_email': doc_data.get('owner_email'),
            'valid_from': doc_data.get('valid_from'),
            'valid_to': doc_data.get('valid_to'),
            'locations': doc_data.get('locations'),
            'authority_confidence': doc_data.get('authority_confidence'),
            'confidence_source': doc_data.get('confidence_source'),
            'prerequisites': doc_data.get('prerequisites'),
            'related_documents': doc_data.get('related_documents'),
            'topic_tags': doc_data.get('topic_tags'),
            'review_cycle': doc_data.get('review_cycle'),
            'cross_service_flag': doc_data.get('cross_service_flag'),
            'authority_override': doc_data.get('authority_override'),
        }
    metadata = {k: v for k, v in metadata.items() if v is not None}
    payload = {'content': content, 'metadata': metadata}
    return _safe_request('POST', '/admin/validate', json=payload, timeout=10)

def rag_auto_fix_metadata(doc_data):
    if hasattr(doc_data, '__table__'):
        content = doc_data.content
        metadata = {
            'document_id': doc_data.document_id,
            'title': doc_data.title,
            'service_area': doc_data.service_area,
            'content_type': doc_data.content_type,
            'topic_tags': doc_data.topic_tags,
            'prerequisites': doc_data.prerequisites,
            'related_documents': doc_data.related_documents,
        }
    else:
        content = doc_data.get('content', '')
        metadata = {
            'document_id': doc_data.get('document_id'),
            'title': doc_data.get('title'),
            'service_area': doc_data.get('service_area') or doc_data.get('service'),
            'content_type': doc_data.get('content_type') or doc_data.get('category'),
            'topic_tags': doc_data.get('topic_tags'),
            'prerequisites': doc_data.get('prerequisites'),
            'related_documents': doc_data.get('related_documents'),
        }
    metadata = {k: v for k, v in metadata.items() if v is not None}
    payload = {'content': content, 'metadata': metadata}
    return _safe_request('POST', '/admin/auto-fix-metadata', json=payload, timeout=10)

# ══════════════════════════════════════════════════════════════════
# FIX: Send ONLY the content block, not the full file
# ══════════════════════════════════════════════════════════════════
def rag_ingest_document(doc, override_overlap=False, override_justification=None):
    # Extract only the content block
    raw_content = doc.content
    if "## CONTENT_BLOCK" in raw_content:
        clean_content = raw_content.split("## CONTENT_BLOCK", 1)[-1].strip()
    else:
        clean_content = raw_content

    data = {
        'document_id': doc.document_id,
        'title': doc.title,
        'content': clean_content,                    # ← now only the content block
        'summary': doc.summary,
        'service': doc.service_area,
        'category': doc.content_type,
        'document_type': doc.content_type,
        'department': doc.department,
        'owner_email': doc.owner_email,
        'valid_from': doc.valid_from.isoformat() if doc.valid_from else None,
        'valid_to': doc.valid_to.isoformat() if doc.valid_to else None,
        'locations': doc.locations,
        'authority_confidence': doc.authority_confidence,
        'confidence_source': doc.confidence_source,
        'prerequisites': doc.prerequisites,
        'related_documents': doc.related_documents,
        'topic_tags': doc.topic_tags,
        'review_cycle': doc.review_cycle,
        'cross_service_flag': doc.cross_service_flag,
        'authority_override': doc.authority_override,
    }
    params = {}
    if override_overlap:
        params['override_overlap'] = 'true'
        if override_justification:
            params['override_justification'] = override_justification
    result = _safe_request('POST', '/ingest', json=data, params=params, timeout=30)
    if isinstance(result, dict) and 'error' in result:
        return result
    else:
        return {'success': True}

def rag_chunk_preview(content):
    return _safe_request('POST', '/admin/chunk-preview', json={'content': content}, timeout=5)

def rag_get_expiring_docs(days=7):
    return _safe_request('GET', f'/admin/documents/expiring?days={days}', timeout=5)

def rag_get_conflict_analytics():
    return _safe_request('GET', '/admin/conflict-analytics?days=30', timeout=5)

def rag_get_conflict_details(conflict_id=None, service=None):
    params = {}
    if conflict_id:
        params['conflict_id'] = conflict_id
    if service:
        params['service'] = service
    return _safe_request('GET', '/admin/conflict-details', params=params, timeout=5)

def rag_get_service_coverage():
    return _safe_request('GET', '/admin/stats/coverage', timeout=5)

# ========== FIXED: Accept service parameter ==========
def rag_wipe_knowledge_base(scope='full', service=None):
    """Wipe knowledge base with optional scope and service."""
    params = {'scope': scope, 'backup': 'true'}
    if service:
        params['service'] = service
    return _safe_request('DELETE', '/ingest/clear', params=params, timeout=30)

def rag_archive_expired():
    return _safe_request('POST', '/admin/archive-expired', timeout=10)

def rag_get_document_tree():
    return _safe_request('GET', '/ingest/status', timeout=10)

def get_rag_status():
    health = rag_get_health()
    return {
        'status': health.get('status'),
        'chunks': health.get('chunks', 0),
        'documents': health.get('documents', 0),
        'queue': health.get('queue', 0)
    }

def get_expired_docs_count():
    if get_rag_status().get('status') != 'healthy':
        return 0
    data = rag_get_expiring_docs(days=0)
    if isinstance(data, dict) and 'error' not in data:
        return len(data.get('documents', []))
    return 0

def get_conflicts_count():
    if get_rag_status().get('status') != 'healthy':
        return 0
    data = rag_get_conflict_analytics()
    if isinstance(data, dict) and 'error' not in data:
        return data.get('same_type', {}).get('count', 0)
    return 0