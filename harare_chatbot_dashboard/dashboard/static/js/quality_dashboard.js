// static/js/quality_dashboard.js
// v3.2 – Dashboard for monitoring document metadata quality

import { showLoader, hideLoader } from './main.js';

document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadMissingTags();
    loadMissingRelated();
    loadMissingPrereqs();
    loadOverrides();

    document.getElementById('refreshBtn').addEventListener('click', function() {
        loadStats();
        loadMissingTags();
        loadMissingRelated();
        loadMissingPrereqs();
        loadOverrides();
    });

    document.getElementById('bulkUpdateBtn').addEventListener('click', function() {
        const action = prompt('Choose action: add-tags, add-related', 'add-tags');
        if (!action) return;
        
        if (action === 'add-tags') {
            const tag = prompt('Enter tag to add to all documents missing tags:');
            if (!tag) return;
            if (!confirm(`Add tag "${tag}" to all documents currently shown in the "Missing Topic Tags" table? This may take a moment.`)) return;

            showLoader();
            const rows = document.querySelectorAll('#missingTagsTable tbody tr');
            const docIds = Array.from(rows).map(row => row.dataset.docId);
            if (docIds.length === 0) {
                alert('No documents to update.');
                hideLoader();
                return;
            }
            fetch('/documents/api/quality/bulk-add-tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ doc_ids: docIds, tag: tag })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(`Tag added to ${data.count} documents.`);
                    loadMissingTags(); // refresh
                } else {
                    alert('Error: ' + (data.error || 'unknown'));
                }
            })
            .catch(err => alert('Network error: ' + err.message))
            .finally(hideLoader);
        } else if (action === 'add-related') {
            const relatedId = prompt('Enter related document ID to add to all documents missing related docs:');
            if (!relatedId) return;
            if (!confirm(`Add related document "${relatedId}" to all documents currently shown in the "Missing Related Documents" table?`)) return;

            showLoader();
            const rows = document.querySelectorAll('#missingRelatedTable tbody tr');
            const docIds = Array.from(rows).map(row => row.dataset.docId);
            if (docIds.length === 0) {
                alert('No documents to update.');
                hideLoader();
                return;
            }
            fetch('/documents/api/quality/bulk-add-related', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ doc_ids: docIds, related_id: relatedId })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(`Related document added to ${data.count} documents.`);
                    loadMissingRelated(); // refresh
                } else {
                    alert('Error: ' + (data.error || 'unknown'));
                }
            })
            .catch(err => alert('Network error: ' + err.message))
            .finally(hideLoader);
        }
    });
});

function loadStats() {
    fetch('/documents/api/quality/stats')
        .then(res => res.json())
        .then(data => {
            document.getElementById('totalDocs').textContent = data.total;
            document.getElementById('completePct').textContent = data.complete_pct + '%';
            document.getElementById('missingTags').textContent = data.missing_tags;
            document.getElementById('missingRelated').textContent = data.missing_related;
            document.getElementById('missingPrereqs').textContent = data.missing_prereqs || 0;
            document.getElementById('withOverrides').textContent = data.with_overrides;
        });
}

function loadMissingTags() {
    const tbody = document.querySelector('#missingTagsTable tbody');
    tbody.innerHTML = '<tr><td colspan="5">Loading...</td></tr>';
    fetch('/documents/api/quality/missing-tags')
        .then(res => res.json())
        .then(docs => {
            tbody.innerHTML = '';
            if (docs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5">No documents missing topic tags.</td></tr>';
                return;
            }
            docs.forEach(doc => {
                const row = tbody.insertRow();
                row.dataset.docId = doc.id;
                row.innerHTML = `
                    <td>${doc.document_id}</td>
                    <td>${doc.title}</td>
                    <td>${doc.service || '-'}</td>
                    <td>${doc.content_type || '-'}</td>
                    <td><a href="/documents/?id=${doc.id}" target="_blank" class="btn btn-small">Edit</a></td>
                `;
            });
        });
}

function loadMissingRelated() {
    const tbody = document.querySelector('#missingRelatedTable tbody');
    tbody.innerHTML = '<tr><td colspan="5">Loading...</td></tr>';
    fetch('/documents/api/quality/missing-related')
        .then(res => res.json())
        .then(docs => {
            tbody.innerHTML = '';
            if (docs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5">No documents missing related documents.</td></tr>';
                return;
            }
            docs.forEach(doc => {
                const row = tbody.insertRow();
                row.dataset.docId = doc.id;
                row.innerHTML = `
                    <td>${doc.document_id}</td>
                    <td>${doc.title}</td>
                    <td>${doc.service || '-'}</td>
                    <td>${doc.content_type || '-'}</td>
                    <td><a href="/documents/?id=${doc.id}" target="_blank" class="btn btn-small">Edit</a></td>
                `;
            });
        });
}

function loadMissingPrereqs() {
    const tbody = document.querySelector('#missingPrereqsTable tbody');
    if (!tbody) return; // optional table
    tbody.innerHTML = '<tr><td colspan="4">Loading...</td></tr>';
    fetch('/documents/api/quality/missing-prereqs')
        .then(res => res.json())
        .then(docs => {
            tbody.innerHTML = '';
            if (docs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4">No documents missing prerequisites.</td></tr>';
                return;
            }
            docs.forEach(doc => {
                const row = tbody.insertRow();
                row.dataset.docId = doc.id;
                row.innerHTML = `
                    <td>${doc.document_id}</td>
                    <td>${doc.title}</td>
                    <td>${doc.service || '-'}</td>
                    <td><a href="/documents/?id=${doc.id}" target="_blank" class="btn btn-small">Edit</a></td>
                `;
            });
        });
}

function loadOverrides() {
    const tbody = document.querySelector('#overridesTable tbody');
    tbody.innerHTML = '<tr><td colspan="6">Loading...</td></tr>';
    fetch('/documents/api/quality/overrides')
        .then(res => res.json())
        .then(docs => {
            tbody.innerHTML = '';
            if (docs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6">No authority overrides found.</td></tr>';
                return;
            }
            docs.forEach(doc => {
                const row = tbody.insertRow();
                row.dataset.docId = doc.id;
                row.innerHTML = `
                    <td>${doc.document_id}</td>
                    <td>${doc.title}</td>
                    <td>${doc.service || '-'}</td>
                    <td>${doc.content_type}</td>
                    <td>${doc.override ? doc.override.tier : '-'}</td>
                    <td>${doc.override ? doc.override.justification.substring(0, 50) + '...' : '-'}</td>
                    <td><a href="/documents/?id=${doc.id}" target="_blank" class="btn btn-small">View</a></td>
                `;
            });
        });
}