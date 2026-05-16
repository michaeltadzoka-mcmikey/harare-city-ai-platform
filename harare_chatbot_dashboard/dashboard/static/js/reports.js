// Reports JavaScript – Module 7 (Full Implementation with improved modal layout)

let currentFilters = {
    status: 'all',
    urgency: 'all',
    duplicate: 'all',
    spam: 'all',
    date: '30d',
    search: '',
    page: 1,
    per_page: 50
};
let totalPages = 1;
let currentReportRef = null;
let currentOverrideField = null;
let spamKeywords = [];

document.addEventListener('DOMContentLoaded', function () {
    loadReports();
    loadStats();
    loadSpamKeywords();
});

// ----------------------------------------------------------------------
// Reports Table & Filters
// ----------------------------------------------------------------------
async function loadReports() {
    const params = new URLSearchParams();
    Object.entries(currentFilters).forEach(([key, value]) => {
        if (value && value !== 'all') params.append(key, value);
    });
    const tbody = document.getElementById('reportsTableBody');
    tbody.innerHTML = '<tr><td colspan="9" class="loading">Loading reports...</td></tr>';

    try {
        const response = await fetch(`/reports/api/list?${params}`);
        const data = await response.json();
        displayReports(data.items);
        renderPagination(data.page, data.pages);
        totalPages = data.pages;
    } catch (error) {
        console.error('Error loading reports:', error);
        tbody.innerHTML = '<tr><td colspan="9" class="loading">Failed to load reports</td></tr>';
    }
}

function displayReports(reports) {
    const tbody = document.getElementById('reportsTableBody');
    if (!reports.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading">No reports found</td></tr>';
        return;
    }

    tbody.innerHTML = reports.map(r => {
        const urgencyClass = `urgency-${r.urgency}`;
        const statusClass = `status-${r.status}`;
        let flags = '';
        if (r.duplicate_flag) flags += '<span class="flag-icon" title="Duplicate">🔁</span>';
        if (r.spam_flag) flags += '<span class="flag-icon" title="Spam">🚫</span>';
        return `
            <tr onclick="viewReport('${r.reference_id}')">
                <td>${r.reference_id}</td>
                <td>${formatDate(r.submitted_at)}</td>
                <td>${r.reference_id.substring(0, 8)}…</td>
                <td>${r.standardized_type || '—'}</td>
                <td>${r.standardized_location || '—'}</td>
                <td><span class="urgency-badge ${urgencyClass}">${r.urgency.toUpperCase()}</span></td>
                <td><span class="status-badge ${statusClass}">${formatStatus(r.status)}</span></td>
                <td>${flags}</td>
                <td><button class="btn-sm" onclick="event.stopPropagation(); viewReport('${r.reference_id}')">View</button></td>
            </tr>
        `;
    }).join('');
}

function formatStatus(status) {
    return status.replace(/_/g, ' ');
}

async function loadStats() {
    try {
        const response = await fetch('/reports/api/stats');
        const stats = await response.json();
        document.getElementById('totalReports').textContent = stats.total;
        document.getElementById('submittedCount').textContent = stats.submitted;
        document.getElementById('inProgressCount').textContent = stats.in_progress;
        document.getElementById('resolvedCount').textContent = stats.resolved;
        document.getElementById('avgTime').textContent = stats.avg_resolution_days + 'd';
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function renderPagination(currentPage, pages) {
    const div = document.getElementById('pagination');
    if (pages <= 1) {
        div.innerHTML = '';
        return;
    }
    let html = '';
    if (currentPage > 1) {
        html += `<button onclick="changePage(${currentPage - 1})">Previous</button>`;
    }
    html += `<span>Page ${currentPage} of ${pages}</span>`;
    if (currentPage < pages) {
        html += `<button onclick="changePage(${currentPage + 1})">Next</button>`;
    }
    // Page size selector
    html += `<select onchange="changePerPage(this.value)" style="margin-left: 15px;">
        <option value="25" ${currentFilters.per_page == 25 ? 'selected' : ''}>25 per page</option>
        <option value="50" ${currentFilters.per_page == 50 ? 'selected' : ''}>50 per page</option>
        <option value="100" ${currentFilters.per_page == 100 ? 'selected' : ''}>100 per page</option>
    </select>`;
    div.innerHTML = html;
}

function changePage(page) {
    currentFilters.page = page;
    loadReports();
}

function changePerPage(value) {
    currentFilters.per_page = parseInt(value);
    currentFilters.page = 1;
    loadReports();
}

function applyFilters() {
    // Map UI values to API expected values
    const status = document.getElementById('statusFilter').value;
    currentFilters.status = status === 'all' ? null : status;

    const urgency = document.getElementById('urgencyFilter').value;
    currentFilters.urgency = urgency === 'all' ? null : urgency;

    const duplicate = document.getElementById('duplicateFilter').value;
    if (duplicate === 'duplicate') currentFilters.duplicate = 'true';
    else if (duplicate === 'not_duplicate') currentFilters.duplicate = 'false';
    else currentFilters.duplicate = null;

    const spam = document.getElementById('spamFilter').value;
    if (spam === 'spam') currentFilters.spam = 'true';
    else if (spam === 'not_spam') currentFilters.spam = 'false';
    else currentFilters.spam = null;

    const date = document.getElementById('dateFilter').value;
    if (date === 'today') currentFilters.date = 'today';
    else if (date === 'last_7_days') currentFilters.date = '7d';
    else if (date === 'last_30_days') currentFilters.date = '30d';
    else currentFilters.date = null;

    currentFilters.search = document.getElementById('searchInput').value;
    currentFilters.page = 1;
    loadReports();
}

const debouncedSearch = debounce(applyFilters, 500);

function filterByStatus(status) {
    document.getElementById('statusFilter').value = status;
    applyFilters();
}

// ----------------------------------------------------------------------
// Report Detail Modal
// ----------------------------------------------------------------------
async function viewReport(reference) {
    try {
        const response = await fetch(`/reports/api/report/${reference}`);
        const report = await response.json();
        currentReportRef = reference;
        displayReportDetails(report);
        loadAuditLog(reference);
        document.getElementById('reportModal').style.display = 'flex';
    } catch (error) {
        console.error('Error loading report:', error);
        alert('Failed to load report details');
    }
}

async function loadAuditLog(reference) {
    try {
        const response = await fetch(`/reports/api/report/${reference}/audit`);
        const logs = await response.json();
        displayAuditLog(logs);
    } catch (error) {
        console.error('Error loading audit log:', error);
    }
}

function displayAuditLog(logs) {
    const container = document.getElementById('auditLogContainer');
    if (!container) return;
    if (logs.length === 0) {
        container.innerHTML = '<div class="audit-item">No audit entries</div>';
        return;
    }
    container.innerHTML = logs.map(log => `
        <div class="audit-item">
            <span class="audit-time">${formatDateTime(log.timestamp)}</span>
            <strong>${log.username}:</strong> ${log.action}
            ${log.old_value ? ` (from: ${log.old_value})` : ''}
            ${log.new_value ? ` (to: ${log.new_value})` : ''}
            ${log.note ? `<br><em>${escapeHtml(log.note)}</em>` : ''}
        </div>
    `).join('');
}

function displayReportDetails(r) {
    const detailsDiv = document.getElementById('reportDetails');
    const urgencyClass = `urgency-${r.urgency}`;
    const statusClass = `status-${r.status}`;

    // Build timeline from notes
    let timelineHtml = '';
    if (r.internal_notes) {
        const notes = r.internal_notes.split('\n');
        timelineHtml = notes.map(n => `
            <div class="timeline-item">${escapeHtml(n)}</div>
        `).join('');
    } else {
        timelineHtml = '<div class="timeline-item">No notes recorded</div>';
    }

    detailsDiv.innerHTML = `
        <div class="report-detail">
            <div class="report-header">
                <h2>Report: ${r.reference_id}</h2>
                <div class="submitted">Submitted: ${formatDateTime(r.submitted_at)}</div>
                ${r.last_updated ? `<div class="submitted">Last updated: ${formatDateTime(r.last_updated)}</div>` : ''}
            </div>

            <div class="detail-grid">
                <div class="label">Type:</div>
                <div class="value">
                    ${r.standardized_type || '—'} (conf: ${r.standardized_type_confidence ? (r.standardized_type_confidence * 100).toFixed(0) + '%' : '—'})
                    <button class="btn-outline" onclick="showOverrideModal('standardized_type', '${r.standardized_type || ''}')">Override</button>
                </div>

                <div class="label">Location:</div>
                <div class="value">
                    ${r.standardized_location || '—'} (conf: ${r.standardized_location_confidence ? (r.standardized_location_confidence * 100).toFixed(0) + '%' : '—'})
                    <button class="btn-outline" onclick="showOverrideModal('standardized_location', '${r.standardized_location || ''}')">Override</button>
                </div>

                <div class="label">Landmark:</div>
                <div class="value">${r.landmark || '—'}</div>

                <div class="label">Urgency:</div>
                <div class="value"><span class="urgency-badge ${urgencyClass}">${r.urgency}</span></div>

                <div class="label">Status:</div>
                <div class="value"><span class="status-badge ${statusClass}">${formatStatus(r.status)}</span></div>

                <div class="label">Duplicate Flag:</div>
                <div class="value">${r.duplicate_flag ? 'Yes (of ' + r.duplicate_of + ')' : 'No'}</div>

                <div class="label">Spam Flag:</div>
                <div class="value">${r.spam_flag ? 'Yes' + (r.spam_reason ? ': ' + r.spam_reason : '') : 'No'}</div>

                <div class="label">Assigned Dept:</div>
                <div class="value">${r.assigned_department || '—'}</div>

                <div class="label">Handled By:</div>
                <div class="value">${r.handled_by_username || '—'}</div>
            </div>

            <div class="detail-section">
                <h3>Description</h3>
                <div class="message-box">${escapeHtml(r.raw_text)}</div>
            </div>

            <div class="detail-section">
                <h3>Internal Notes</h3>
                <div class="timeline">${timelineHtml}</div>
                <div class="form-group" style="margin-top: 12px;">
                    <textarea id="newNote" placeholder="Add a note..." rows="2" style="width:100%;"></textarea>
                </div>
                <div class="form-actions">
                    <button class="btn btn-primary" onclick="addNote()">Add Note</button>
                </div>
            </div>

            <div class="detail-section">
                <h3>Status Update</h3>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <select id="newStatus" style="padding: 8px;">
                        <option value="submitted" ${r.status == 'submitted' ? 'selected' : ''}>Submitted</option>
                        <option value="in_progress" ${r.status == 'in_progress' ? 'selected' : ''}>In Progress</option>
                        <option value="on_hold" ${r.status == 'on_hold' ? 'selected' : ''}>On Hold</option>
                        <option value="resolved" ${r.status == 'resolved' ? 'selected' : ''}>Resolved</option>
                        <option value="closed" ${r.status == 'closed' ? 'selected' : ''}>Closed</option>
                    </select>
                    <button class="btn btn-primary" onclick="updateStatus()">Update</button>
                </div>
            </div>

            <div class="detail-section">
                <h3>Duplicate Management</h3>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="text" id="duplicateRef" placeholder="Original reference" value="${r.duplicate_of || ''}" style="flex: 1;">
                    <button class="btn btn-warning" onclick="markDuplicate()">Mark as Duplicate</button>
                    ${r.duplicate_of ? `<button class="btn btn-secondary" onclick="viewReport('${r.duplicate_of}')">View Original</button>` : ''}
                </div>
            </div>

            <div class="detail-section">
                <h3>Audit Log</h3>
                <div id="auditLogContainer" class="audit-log"></div>
            </div>
        </div>
    `;
}

function showOverrideModal(field, currentValue) {
    currentOverrideField = field;
    document.getElementById('overrideFieldLabel').innerHTML = `Override ${field} (was: ${currentValue})`;
    document.getElementById('overrideNewValue').value = '';
    document.getElementById('overrideJustification').value = '';
    document.getElementById('overrideModal').style.display = 'flex';
}

function closeOverrideModal() {
    document.getElementById('overrideModal').style.display = 'none';
    currentOverrideField = null;
}

async function confirmOverride() {
    if (!currentReportRef || !currentOverrideField) return;
    const newValue = document.getElementById('overrideNewValue').value;
    const justification = document.getElementById('overrideJustification').value;
    if (!newValue) {
        alert('New value required');
        return;
    }
    if (!justification || justification.length < 10) {
        alert('Justification must be at least 10 characters');
        return;
    }
    try {
        const response = await fetch(`/reports/api/report/${currentReportRef}/override`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                field: currentOverrideField,
                value: newValue,
                justification: justification
            })
        });
        if (!response.ok) throw new Error('Override failed');
        closeOverrideModal();
        viewReport(currentReportRef); // refresh
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function addNote() {
    const note = document.getElementById('newNote').value;
    if (!note) return;
    try {
        const response = await fetch(`/reports/api/report/${currentReportRef}/note`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: note })
        });
        if (!response.ok) throw new Error('Failed to add note');
        document.getElementById('newNote').value = '';
        viewReport(currentReportRef);
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function updateStatus() {
    const newStatus = document.getElementById('newStatus').value;
    try {
        const response = await fetch(`/reports/api/report/${currentReportRef}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        if (!response.ok) throw new Error('Status update failed');
        viewReport(currentReportRef);
        loadReports(); // refresh table
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function markDuplicate() {
    const originalRef = document.getElementById('duplicateRef').value;
    if (!originalRef) return;
    try {
        const response = await fetch(`/reports/api/report/${currentReportRef}/duplicate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ original_reference: originalRef })
        });
        if (!response.ok) throw new Error('Failed to mark duplicate');
        viewReport(currentReportRef);
        loadReports();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function closeModal() {
    document.getElementById('reportModal').style.display = 'none';
}

// ----------------------------------------------------------------------
// Export & Refresh
// ----------------------------------------------------------------------
function exportCSV() {
    const params = new URLSearchParams();
    Object.entries(currentFilters).forEach(([key, value]) => {
        if (value && value !== 'all') params.append(key, value);
    });
    window.location.href = `/reports/api/export?${params}`;
}

function exportJSON() {
    const params = new URLSearchParams();
    Object.entries(currentFilters).forEach(([key, value]) => {
        if (value && value !== 'all') params.append(key, value);
    });
    fetch(`/reports/api/list?${params}`)
        .then(res => res.json())
        .then(data => {
            const blob = new Blob([JSON.stringify(data.items, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `reports_${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
        });
}

function refreshReports() {
    loadReports();
    loadStats();
}

// ----------------------------------------------------------------------
// Spam Blacklist Management
// ----------------------------------------------------------------------
async function loadSpamKeywords() {
    try {
        const response = await fetch('/reports/api/spam_keywords');
        spamKeywords = await response.json();
        renderSpamKeywords();
    } catch (error) {
        console.error('Error loading spam keywords:', error);
    }
}

function renderSpamKeywords() {
    const list = document.getElementById('spamKeywordList');
    if (!list) return;
    list.innerHTML = spamKeywords.map(k => `
        <li>
            ${k.keyword}
            <button class="btn-sm" onclick="deleteSpamKeyword(${k.id})">Delete</button>
        </li>
    `).join('');
}

async function addSpamKeyword() {
    const input = document.getElementById('newSpamKeyword');
    const keyword = input.value.trim();
    if (!keyword) return;
    try {
        const response = await fetch('/reports/api/spam_keywords', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword })
        });
        if (!response.ok) throw new Error('Failed to add');
        input.value = '';
        loadSpamKeywords();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function deleteSpamKeyword(id) {
    if (!confirm('Delete this keyword?')) return;
    try {
        const response = await fetch(`/reports/api/spam_keywords/${id}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error('Failed to delete');
        loadSpamKeywords();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// ----------------------------------------------------------------------
// Utility Functions
// ----------------------------------------------------------------------
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString();
}

function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleString();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}