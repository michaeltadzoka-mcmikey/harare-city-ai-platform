import os
import shutil
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def get_active_path(service, content_type, document_id):
    """Return the full path for an active document."""
    base = current_app.config['RAG_DOCUMENTS_PATH']
    # Sanitize inputs (remove path traversal)
    service = service.replace('..', '').replace('/', '').replace('\\', '')
    content_type = content_type.replace('..', '').replace('/', '').replace('\\', '')
    document_id = document_id.replace('..', '').replace('/', '').replace('\\', '')
    return os.path.join(base, 'by_service', service, content_type, f"{document_id}.txt")

def get_archived_path(service, content_type, document_id):
    """Return the full path for an archived document."""
    base = current_app.config['RAG_DOCUMENTS_PATH']
    service = service.replace('..', '').replace('/', '').replace('\\', '')
    content_type = content_type.replace('..', '').replace('/', '').replace('\\', '')
    document_id = document_id.replace('..', '').replace('/', '').replace('\\', '')
    return os.path.join(base, 'archived', 'by_service', service, content_type, f"{document_id}.txt")

def ensure_dir(path):
    """Ensure directory exists."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

def write_document_file(document):
    """Write document content to the active filesystem location."""
    if not document.service_area or not document.content_type:
        logger.error(f"Cannot write document {document.document_id}: missing service_area or content_type")
        return False
    path = get_active_path(document.service_area, document.content_type, document.document_id)
    ensure_dir(path)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(document.content)
        logger.info(f"Document written to {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write document {document.document_id}: {e}")
        return False

def delete_document_file(document):
    """Delete the active document file."""
    if not document.service_area or not document.content_type:
        return False
    path = get_active_path(document.service_area, document.content_type, document.document_id)
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted document file {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete document file {document.document_id}: {e}")
        return False

def archive_document_file(document):
    """Move document file from active to archive. Returns True on success, False on failure."""
    if not document.service_area or not document.content_type:
        logger.warning(f"Cannot archive document {document.document_id}: missing service_area or content_type. DB archival only.")
        return False
    
    src = get_active_path(document.service_area, document.content_type, document.document_id)
    dst = get_archived_path(document.service_area, document.content_type, document.document_id)
    ensure_dir(dst)
    
    try:
        if os.path.exists(src):
            shutil.move(src, dst)
            logger.info(f"Archived document file from {src} to {dst}")
            return True
        else:
            logger.warning(f"Active file not found for {document.document_id} at {src}. Creating placeholder in archive.")
            # Create placeholder to mark archival
            with open(dst, 'w', encoding='utf-8') as f:
                f.write(f"# Archived placeholder for {document.document_id}\n")
                f.write(f"# Original title: {document.title}\n")
                f.write("# File was missing at archival time.\n")
            return True
    except Exception as e:
        logger.error(f"Failed to archive document {document.document_id}: {e}")
        return False

def restore_document_file(document):
    """Move document file from archive back to active."""
    if not document.service_area or not document.content_type:
        return False
    src = get_archived_path(document.service_area, document.content_type, document.document_id)
    dst = get_active_path(document.service_area, document.content_type, document.document_id)
    ensure_dir(dst)
    try:
        if os.path.exists(src):
            shutil.move(src, dst)
            logger.info(f"Restored document file from {src} to {dst}")
            return True
        else:
            logger.warning(f"Archived file not found for {document.document_id} at {src}")
            return False
    except Exception as e:
        logger.error(f"Failed to restore document {document.document_id}: {e}")
        return False

def delete_archived_file(document):
    """Delete archived file (e.g., during permanent deletion)."""
    if not document.service_area or not document.content_type:
        return False
    path = get_archived_path(document.service_area, document.content_type, document.document_id)
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted archived file {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete archived file {document.document_id}: {e}")
        return False