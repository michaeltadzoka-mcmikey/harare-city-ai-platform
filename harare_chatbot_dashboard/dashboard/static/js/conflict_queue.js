// static/js/conflict_queue.js
// v3.2 – Conflict Queue management

import { showLoader, hideLoader } from './main.js';

let currentUnresolvedPage = 1;
let currentProvisionalPage = 1;
let unresolvedTotalPages = 1;
let provisionalTotalPages = 1;

document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const tabId = this.dataset.tab;
            document.getElementById(tabId + 'Tab').classList.add('active');
            if (tabId === 'unresolved') loadUnresolved(1);
            else loadProvisional(1);
        });
    });

    // Load initial data
    loadUnresolved(1);
});

function loadUnresolved(page = 1) {
    showLoader();
    fetch(`/documents/api/conflicts?page=${page}&status=unresolved`)
        .then(res => res.json())
        .then(data => {
            renderUnresolved(data.items);
            currentUnresolvedPage = data.page;
            unresolvedTotalPages = data.pages;
            renderPagination('unresolved', data.page, data.pages);
        })
        .catch(err => console.error(err))
        .finally(hideLoader);
}

function loadProvisional(page = 1) {
    showLoader();
    fetch(`/documents/api/conflicts/provisional?page=${page}`)
        .then(res => res.json())
        .then(data => {
            renderProvisional(data.items);
            currentProvisionalPage = data.page;
            provisionalTotalPages = data.pages;
            renderPagination('provisional', data.page, data.pages);
        })
        .catch(err => console.error(err))
        .finally(hideLoader);
}

function renderUnresolved(conflicts) {
    const container = document.getElementById('unresolvedList');
    if (!conflicts.length) {
        container.innerHTML = '<p>No unresolved conflicts found.</p>';
        return;
    }
    let html = '';
    conflicts.forEach(c => {
        html += `
            <div class="conflict-card" data-conflict-id="${c.id}">
                <div class="conflict-header">
                    <span class="badge badge-unresolved">Unresolved</span>
                    <span>Created: ${new Date(c.created_at).toLocaleString()}</span>
                </div>
                <p><strong>Reason:</strong> ${c.reason}</p>
                <div class="conflict-docs">
                    <div class="doc-panel">
                        <strong>${c.doc1.document_id}</strong><br>
                        ${c.doc1.title}<br>
                        <small>Service: ${c.doc1.service}</small>
                    </div>
                    <div class="doc-panel">
                        <strong>${c.doc2.document_id}</strong><br>
                        ${c.doc2.title}<br>
                        <small>Service: ${c.doc2.service}</small>
                    </div>
                </div>
                <div>
                    <button class="btn btn-primary btn-sm resolve-btn" data-conflict-id="${c.id}">Resolve Manually</button>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;

    // Attach resolve button handlers
    document.querySelectorAll('.resolve-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const conflictId = e.target.dataset.conflictId;
            showResolveModal(conflictId);
        });
    });
}

function renderProvisional(provisionals) {
    const container = document.getElementById('provisionalList');
    if (!provisionals.length) {
        container.innerHTML = '<p>No provisional resolutions pending review.</p>';
        return;
    }
    let html = '';
    provisionals.forEach(p => {
        const deadline = new Date(p.resolved_at);
        deadline.setDate(deadline.getDate() + 7);
        const now = new Date();
        const daysLeft = Math.floor((deadline - now) / (1000 * 60 * 60 * 24));
        const deadlineClass = daysLeft < 2 ? 'deadline-warning' : '';

        html += `
            <div class="conflict-card" data-prov-id="${p.id}">
                <div class="conflict-header">
                    <span class="badge badge-provisional">Provisional</span>
                    <span>Resolved: ${new Date(p.resolved_at).toLocaleString()}</span>
                </div>
                <p><strong>Selected Document:</strong> ${p.selected_doc.document_id} – ${p.selected_doc.title}</p>
                <p><strong>Justification:</strong> ${p.justification}</p>
                <p class="${deadlineClass}">Review deadline: ${deadline.toLocaleDateString()} (${daysLeft} days left)</p>
                <div>
                    <button class="btn btn-success btn-sm confirm-prov" data-prov-id="${p.id}">Confirm</button>
                    <button class="btn btn-warning btn-sm override-prov" data-prov-id="${p.id}">Override</button>
                    <button class="btn btn-secondary btn-sm reopen-prov" data-prov-id="${p.id}">Reopen</button>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;

    // Attach review button handlers
    document.querySelectorAll('.confirm-prov').forEach(btn => {
        btn.addEventListener('click', (e) => reviewProvisional(e.target.dataset.provId, 'confirm'));
    });
    document.querySelectorAll('.override-prov').forEach(btn => {
        btn.addEventListener('click', (e) => reviewProvisional(e.target.dataset.provId, 'override'));
    });
    document.querySelectorAll('.reopen-prov').forEach(btn => {
        btn.addEventListener('click', (e) => reviewProvisional(e.target.dataset.provId, 'reopen'));
    });
}

function renderPagination(type, current, total) {
    const container = document.getElementById(type + 'Pagination');
    if (total <= 1) {
        container.innerHTML = '';
        return;
    }
    let html = '<div class="pagination-controls">';
    if (current > 1) {
        html += `<button class="btn btn-sm btn-secondary" onclick="load${type.charAt(0).toUpperCase() + type.slice(1)}(${current - 1})">Previous</button>`;
    }
    html += `<span>Page ${current} of ${total}</span>`;
    if (current < total) {
        html += `<button class="btn btn-sm btn-secondary" onclick="load${type.charAt(0).toUpperCase() + type.slice(1)}(${current + 1})">Next</button>`;
    }
    html += '</div>';
    container.innerHTML = html;
}

function showResolveModal(conflictId) {
    // Simple prompt for now – in a real implementation, this would be a modal
    const resolution = prompt('Enter resolution method: retire_one, override, confirm_provisional (if applicable)');
    if (!resolution) return;
    const selectedDocId = prompt('Enter selected document ID (if retiring one) or leave blank');
    const justification = prompt('Enter justification (min 20 chars)');
    if (!justification || justification.length < 20) {
        alert('Justification must be at least 20 characters.');
        return;
    }
    fetch(`/documents/api/conflicts/${conflictId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            resolution: resolution,
            selected_doc_id: selectedDocId,
            justification: justification
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert('Conflict resolved');
            loadUnresolved(currentUnresolvedPage);
        } else {
            alert('Error: ' + (data.error || 'unknown'));
        }
    });
}

function reviewProvisional(provId, action) {
    const notes = prompt(`Enter notes for ${action} (optional)`);
    fetch(`/documents/api/conflicts/provisional/${provId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action, notes: notes || '' })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert('Provisional resolution reviewed');
            loadProvisional(currentProvisionalPage);
        } else {
            alert('Error: ' + (data.error || 'unknown'));
        }
    });
}

// Expose pagination functions globally for onclick handlers
window.loadUnresolved = loadUnresolved;
window.loadProvisional = loadProvisional;