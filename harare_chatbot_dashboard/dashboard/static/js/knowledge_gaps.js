// Knowledge Gaps JavaScript – Fully fixed, no infinite loading

let currentGapId = null;
let currentFilters = {
    priority: 'all',
    service: 'all',
    status: 'all',
    page: 1
};
let allGaps = [];
let currentUserId = null;
let canManageKnowledge = false;
let lastSavedDraftId = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('Knowledge Gaps JS loaded');
    currentUserId = document.getElementById('currentUserId')?.value || null;
    canManageKnowledge = document.getElementById('canManageKnowledge')?.value === 'true';

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.getElementById(`tab-${tabId}`).classList.add('active');
            if (tabId === 'metrics') loadMetrics();
            else if (tabId === 'trends') loadTrends();
            else if (tabId === 'recurrence') loadRecurrence();
            else if (tabId === 'audit') loadAudit();
        });
    });

    loadIssues();
    loadStats();
    attachDragAndDrop();
    // attachContextMenu is optional – define empty to avoid error
    if (typeof attachContextMenu !== 'undefined') attachContextMenu();

    if (!canManageKnowledge) {
        document.querySelectorAll('.btn-primary, .btn-success, .btn-warning, .btn-danger')
            .forEach(btn => btn.disabled = true);
    }
});

// Placeholder for context menu if not defined elsewhere
window.attachContextMenu = window.attachContextMenu || function() {};

// ==================== Issues List ====================
async function loadIssues() {
    const params = new URLSearchParams(currentFilters);
    const listDiv = document.getElementById('issuesList');
    if (!listDiv) return;
    listDiv.innerHTML = '<div class="loading">Loading issues...</div>';

    try {
        const response = await fetch(`/knowledge-gaps/api/list?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        allGaps = data.items || [];
        renderIssuesList(allGaps);
        renderKanban(allGaps);
        updateKanbanCounts(allGaps);
    } catch (error) {
        console.error('Error loading issues:', error);
        listDiv.innerHTML = '<div class="error">Failed to load issues: ' + error.message + '</div>';
    }
}

function renderIssuesList(gaps) {
    const listDiv = document.getElementById('issuesList');
    if (!listDiv) return;
    if (!gaps.length) {
        listDiv.innerHTML = '<div class="empty">No issues found</div>';
        return;
    }

    listDiv.innerHTML = gaps.map(gap => {
        const impactClass = `impact-${gap.impact}`;
        const selected = gap.id === currentGapId ? 'selected' : '';
        return `
            <div class="issue-item ${selected} ${impactClass}" data-id="${gap.id}" data-contextmenu="issue">
                <div class="issue-header">
                    <span class="issue-service">${escapeHtml(gap.service)}</span>
                    <span class="issue-priority">${gap.impact}</span>
                </div>
                <div class="issue-question">${escapeHtml(gap.question.substring(0, 60))}${gap.question.length > 60 ? '…' : ''}</div>
                <div class="issue-meta">
                    <span>Freq: ${gap.frequency}</span>
                    <span>${gap.recurrence_count ? '↻ ' + gap.recurrence_count : ''}</span>
                </div>
            </div>
        `;
    }).join('');

    // Attach click handlers
    document.querySelectorAll('.issue-item').forEach(el => {
        el.addEventListener('click', () => selectIssue(parseInt(el.dataset.id)));
    });
}

async function selectIssue(gapId) {
    currentGapId = gapId;
    document.querySelectorAll('.issue-item').forEach(el => el.classList.remove('selected'));
    const selectedEl = document.querySelector(`.issue-item[data-id="${gapId}"]`);
    if (selectedEl) selectedEl.classList.add('selected');

    try {
        const response = await fetch(`/knowledge-gaps/api/gap/${gapId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const gap = await response.json();
        displayIssueDetail(gap);
        loadInsights(gap);
        const actionsDiv = document.getElementById('detailActions');
        if (actionsDiv) actionsDiv.style.display = 'flex';
    } catch (error) {
        console.error('Error loading issue:', error);
        const detailDiv = document.getElementById('detailContent');
        if (detailDiv) detailDiv.innerHTML = '<div class="error">Failed to load issue details.</div>';
    }
}

function displayIssueDetail(gap) {
    const detailDiv = document.getElementById('detailContent');
    if (!detailDiv) return;
    detailDiv.innerHTML = `
        <h3>${escapeHtml(gap.question)}</h3>
        <div class="detail-grid">
            <div><strong>Service:</strong> ${escapeHtml(gap.service)}</div>
            <div><strong>Risk:</strong> ${escapeHtml(gap.service_risk)}</div>
            <div><strong>Impact:</strong> <span class="impact-${gap.impact}">${gap.impact}</span></div>
            <div><strong>Frequency:</strong> ${gap.frequency}</div>
            <div><strong>Priority Score:</strong> ${gap.priority_score}</div>
            <div><strong>Recurrence:</strong> ${gap.recurrence_count}</div>
            <div><strong>Root Cause:</strong> ${escapeHtml(gap.root_cause || 'Unknown')}</div>
            <div><strong>Status:</strong> ${escapeHtml(gap.status)}</div>
            <div><strong>Assigned:</strong> ${escapeHtml(gap.assigned_to_name || 'Unassigned')}</div>
            <div><strong>First Asked:</strong> ${formatDate(gap.first_asked)}</div>
            <div><strong>Last Asked:</strong> ${formatDate(gap.last_asked)}</div>
        </div>
        <div class="detail-section collapsible">
            <div class="section-header" onclick="toggleSection(this)">
                <span>▶ Retrieval Details</span>
            </div>
            <div class="section-content" style="display: none;">
                <pre>${escapeHtml(JSON.stringify(gap.retrieval_result, null, 2))}</pre>
            </div>
        </div>
        <div class="detail-section collapsible">
            <div class="section-header" onclick="toggleSection(this)">
                <span>▶ Risk & Priority</span>
            </div>
            <div class="section-content" style="display: none;">
                <div>Base Priority: ${gap.base_priority}</div>
                <div>Final Priority: ${gap.priority_score}</div>
                <div>Resolution Quality Score: ${gap.resolution_quality_score || 'N/A'}</div>
            </div>
        </div>
        <div class="detail-section collapsible">
            <div class="section-header" onclick="toggleSection(this)">
                <span>▶ History</span>
            </div>
            <div class="section-content" style="display: none;">
                <div id="historyContent">Loading history...</div>
            </div>
        </div>
        <div class="detail-section collapsible">
            <div class="section-header" onclick="toggleSection(this)">
                <span>▶ Insights</span>
            </div>
            <div class="section-content" style="display: none;">
                <div id="insightsContent">Loading insights...</div>
            </div>
        </div>
    `;
    loadHistory(gap.id);
}

function loadInsights(gap) {
    const insightsDiv = document.getElementById('insightsContent');
    if (!insightsDiv) return;
    insightsDiv.innerHTML = `
        <div><strong>Root Cause:</strong> ${escapeHtml(gap.root_cause || 'Unknown')}</div>
        <div><strong>Similar Queries:</strong> ${gap.frequency} occurrences</div>
        <button class="btn btn-sm btn-link" onclick="findSimilarGaps(${gap.id})">View similar gaps</button>
        <div><strong>Existing Drafts:</strong> ${gap.draft_id ? '<a href="#" onclick="openDraft('+gap.draft_id+')">Draft #'+gap.draft_id+'</a>' : 'None'}</div>
        <div><strong>Recent Overrides:</strong> <button class="btn btn-sm btn-link" onclick="loadOverrides('${escapeHtml(gap.service)}')">Check overrides</button></div>
        <div><strong>Related Services:</strong> ${escapeHtml(gap.service)}</div>
    `;
}

function toggleSection(header) {
    const section = header.closest('.collapsible');
    const content = section.querySelector('.section-content');
    const isExpanded = content.style.display !== 'none';
    content.style.display = isExpanded ? 'none' : 'block';
    const span = header.querySelector('span');
    if (span) {
        span.innerHTML = isExpanded ? '▶ ' + span.innerText.slice(2) : '▼ ' + span.innerText.slice(2);
    }
}

async function loadHistory(gapId) {
    const historyDiv = document.getElementById('historyContent');
    if (!historyDiv) return;
    try {
        const response = await fetch(`/knowledge-gaps/api/audit?target_id=${gapId}`);
        const data = await response.json();
        if (data.items.length === 0) {
            historyDiv.innerHTML = '<p>No history available.</p>';
        } else {
            historyDiv.innerHTML = '<ul>' + data.items.map(log => 
                `<li>${log.timestamp} – ${escapeHtml(log.user)} – ${escapeHtml(log.action)} – ${escapeHtml(log.note || '')}</li>`
            ).join('') + '</ul>';
        }
    } catch (error) {
        console.error('Error loading history:', error);
        historyDiv.innerHTML = '<p>Error loading history.</p>';
    }
}

// ==================== Kanban ====================
function renderKanban(gaps) {
    const columns = {
        open: document.getElementById('kanban-open'),
        drafting: document.getElementById('kanban-drafting'),
        review: document.getElementById('kanban-review'),
        completed: document.getElementById('kanban-completed')
    };
    Object.values(columns).forEach(col => { if (col) col.innerHTML = ''; });

    gaps.forEach(gap => {
        const card = createKanbanCard(gap);
        const column = columns[gap.status];
        if (column) column.appendChild(card);
    });
}

function createKanbanCard(gap) {
    const div = document.createElement('div');
    div.className = `kanban-card ${gap.impact.toLowerCase()}`;
    div.setAttribute('draggable', canManageKnowledge ? 'true' : 'false');
    div.setAttribute('data-id', gap.id);
    div.setAttribute('data-status', gap.status);
    div.innerHTML = `
        <div class="card-question" title="${escapeHtml(gap.question)}">${escapeHtml(gap.question.substring(0, 40))}${gap.question.length > 40 ? '…' : ''}</div>
        <div class="card-meta">
            <span>${escapeHtml(gap.service)}</span>
            <span>${gap.frequency}</span>
        </div>
    `;
    div.addEventListener('dragstart', handleDragStart);
    div.addEventListener('dragend', handleDragEnd);
    div.addEventListener('click', () => selectIssue(gap.id));
    return div;
}

function updateKanbanCounts(gaps) {
    const counts = { open: 0, drafting: 0, review: 0, completed: 0 };
    gaps.forEach(g => { if (counts[g.status] !== undefined) counts[g.status]++; });
    const openSpan = document.getElementById('kanbanOpenCount');
    if (openSpan) openSpan.textContent = counts.open;
    const draftingSpan = document.getElementById('kanbanDraftingCount');
    if (draftingSpan) draftingSpan.textContent = counts.drafting;
    const reviewSpan = document.getElementById('kanbanReviewCount');
    if (reviewSpan) reviewSpan.textContent = counts.review;
    const completedSpan = document.getElementById('kanbanCompletedCount');
    if (completedSpan) completedSpan.textContent = counts.completed;
}

function toggleKanban() {
    const board = document.querySelector('.kanban-board');
    const icon = document.querySelector('.toggle-icon');
    if (board && icon) {
        if (board.style.display === 'none') {
            board.style.display = 'grid';
            icon.textContent = '▼';
        } else {
            board.style.display = 'none';
            icon.textContent = '▶';
        }
    }
}

// Drag and drop
let draggedItem = null;
function handleDragStart(e) {
    draggedItem = this;
    e.dataTransfer.setData('text/plain', this.dataset.id);
    this.style.opacity = '0.5';
}
function handleDragEnd(e) {
    this.style.opacity = '1';
}
function handleDragOver(e) {
    e.preventDefault();
}
async function handleDrop(e) {
    e.preventDefault();
    if (!canManageKnowledge) return;
    const column = e.currentTarget;
    const newStatus = column.dataset.status;
    const gapId = e.dataTransfer.getData('text/plain');

    if (newStatus === 'completed') {
        showResolveModal(gapId, true);
        return;
    }

    const oldCard = document.querySelector(`.kanban-card[data-id="${gapId}"]`);
    if (oldCard) oldCard.remove();

    const gap = allGaps.find(g => g.id == gapId);
    if (gap) {
        gap.status = newStatus;
        const newCard = createKanbanCard(gap);
        const cardsContainer = column.querySelector('.column-cards');
        if (cardsContainer) cardsContainer.appendChild(newCard);
    }

    try {
        await fetch(`/knowledge-gaps/api/gap/${gapId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        loadIssues(); // refresh full list to keep counts correct
    } catch (error) {
        console.error('Error updating status:', error);
        alert('Failed to update status');
    }
}

function attachDragAndDrop() {
    document.querySelectorAll('.kanban-column').forEach(col => {
        col.addEventListener('dragover', handleDragOver);
        col.addEventListener('drop', handleDrop);
    });
}

// ==================== Filters & Actions ====================
function applyFilters() {
    currentFilters.priority = document.getElementById('priorityFilter')?.value || 'all';
    currentFilters.service = document.getElementById('serviceFilter')?.value || 'all';
    currentFilters.status = document.getElementById('statusFilter')?.value || 'all';
    currentFilters.page = 1;
    loadIssues();
}

function filterByStatus(status) {
    if (status === 'critical') {
        const priorityFilter = document.getElementById('priorityFilter');
        if (priorityFilter) priorityFilter.value = 'critical';
    } else {
        const statusFilter = document.getElementById('statusFilter');
        if (statusFilter) statusFilter.value = status;
    }
    applyFilters();
}

async function loadStats() {
    try {
        const response = await fetch('/knowledge-gaps/api/stats');
        const stats = await response.json();
        const openSpan = document.getElementById('openCount');
        if (openSpan) openSpan.textContent = stats.open;
        const criticalSpan = document.getElementById('criticalCount');
        if (criticalSpan) criticalSpan.textContent = stats.critical;
        const recurringSpan = document.getElementById('recurringCount');
        if (recurringSpan) recurringSpan.textContent = stats.recurring;
        const trendSpan = document.getElementById('trendIndicator');
        if (trendSpan) trendSpan.textContent = stats.trend;
        const healthSpan = document.getElementById('healthIndicator');
        if (healthSpan) healthSpan.textContent = stats.health + '%';
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ==================== Tab Content Loaders ====================
async function loadMetrics() {
    const container = document.getElementById('metricsContent');
    if (!container) return;
    container.innerHTML = 'Loading...';
    try {
        const response = await fetch('/knowledge-gaps/api/metrics');
        const data = await response.json();
        container.innerHTML = `
            <h3>Service Breakdown</h3>
            <ul>
                ${data.service_stats.map(s => `<li>${escapeHtml(s.service)}: ${s.count} gaps (avg priority ${s.avg_priority})</li>`).join('')}
            </ul>
            <h3>Priority Distribution</h3>
            <ul>
                <li>Critical: ${data.priority_counts.critical}</li>
                <li>High: ${data.priority_counts.high}</li>
                <li>Medium: ${data.priority_counts.medium}</li>
                <li>Low: ${data.priority_counts.low}</li>
            </ul>
            <p>Avg Resolution Time: ${data.avg_resolution_days} days</p>
        `;
    } catch (error) {
        container.innerHTML = '<div class="error">Failed to load metrics</div>';
    }
}

async function loadTrends() {
    const container = document.getElementById('trendsContent');
    if (!container) return;
    container.innerHTML = '<div class="loading">Loading trends...</div>';
    try {
        const response = await fetch('/knowledge-gaps/api/trends?days=30');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data.created || !data.resolved) throw new Error('Invalid data format');
        if (data.created.length === 0 && data.resolved.length === 0) {
            container.innerHTML = '<p>No trend data available.</p>';
            return;
        }
        container.innerHTML = `
            <h3>Daily Created / Resolved (Last 30 Days)</h3>
            <table class="trends-table">
                <thead>
                    <tr><th>Date</th><th>Created</th><th>Resolved</th></tr>
                </thead>
                <tbody>
                    ${data.created.map(c => {
                        const resolved = data.resolved.find(r => r.date === c.date);
                        return `<tr><td>${c.date}</td><td>${c.count}</td><td>${resolved ? resolved.count : 0}</td></tr>`;
                    }).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Error loading trends:', error);
        container.innerHTML = `<div class="error">Failed to load trends: ${error.message}</div>`;
    }
}

async function loadRecurrence() {
    const container = document.getElementById('recurrenceContent');
    if (!container) return;
    container.innerHTML = 'Loading...';
    try {
        const response = await fetch('/knowledge-gaps/api/recurrence/list');
        const items = await response.json();
        if (items.length === 0) {
            container.innerHTML = '<p>No recurring gaps.</p>';
        } else {
            container.innerHTML = '<ul>' + items.map(g => 
                `<li><a href="#" onclick="selectIssue(${g.id}); document.querySelector(\'[data-tab="issues"]\').click();">${escapeHtml(g.question)}</a> (recurred ${g.recurrence_count} times, last resolved ${g.last_resolved})</li>`
            ).join('') + '</ul>';
        }
    } catch (error) {
        container.innerHTML = '<div class="error">Failed to load recurrence list</div>';
    }
}

async function loadAudit() {
    const container = document.getElementById('auditContent');
    if (!container) return;
    container.innerHTML = 'Loading...';
    try {
        const response = await fetch('/knowledge-gaps/api/audit?per_page=50');
        const data = await response.json();
        container.innerHTML = `
            <table class="audit-table">
                <thead>
                    <tr><th>Time</th><th>User</th><th>Action</th><th>Target</th><th>Note</th></tr>
                </thead>
                <tbody>
                    ${data.items.map(log => `
                        <tr>
                            <td>${log.timestamp}</td>
                            <td>${escapeHtml(log.user)}</td>
                            <td>${escapeHtml(log.action)}</td>
                            <td>${escapeHtml(log.target_type)}:${escapeHtml(log.target_id)}</td>
                            <td>${escapeHtml(log.note || '')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        container.innerHTML = '<div class="error">Failed to load audit log</div>';
    }
}

// ==================== Helper Functions ====================
function showCreateModal() { 
    const modal = document.getElementById('createIssueModal');
    if (modal) modal.style.display = 'flex';
}
function closeCreateModal() { 
    const modal = document.getElementById('createIssueModal');
    if (modal) modal.style.display = 'none';
}
async function saveNewIssue(event) {
    event.preventDefault();
    const data = {
        question: document.getElementById('issueQuestion')?.value,
        service: document.getElementById('issueService')?.value,
        root_cause: document.getElementById('issueRootCause')?.value,
        priority_score: parseInt(document.getElementById('issuePriority')?.value || 50)
    };
    if (!data.question || !data.service) {
        alert('Question and Service are required');
        return;
    }
    try {
        const response = await fetch('/knowledge-gaps/api/gap', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error('Creation failed');
        closeCreateModal();
        loadIssues();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function showSmartDraftModal() {
    const modal = document.getElementById('smartDraftModal');
    if (!modal) return;
    modal.style.display = 'flex';
    const select = document.getElementById('draftIssueId');
    if (select) {
        select.innerHTML = '<option value="">-- Create from scratch --</option>' +
            allGaps.map(g => `<option value="${g.id}">${escapeHtml(g.question.substring(0, 30))}…</option>`).join('');
    }
}
function closeSmartDraftModal() { 
    const modal = document.getElementById('smartDraftModal');
    if (modal) modal.style.display = 'none';
}
async function saveDraft() {
    const issueId = document.getElementById('draftIssueId')?.value;
    const service = document.getElementById('draftService')?.value;
    const docType = document.getElementById('draftType')?.value;
    const title = document.getElementById('draftTitle')?.value;
    const content = document.getElementById('draftContent')?.value;

    if (!service || !content) {
        alert('Service and Content are required');
        return;
    }

    if (!issueId) {
        const conflictCheck = await fetch('/knowledge-gaps/api/draft/conflict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service, question: title })
        });
        const conflict = await conflictCheck.json();
        if (conflict.conflict && !confirm(`A similar draft already exists (ID: ${conflict.draft_id}). Create anyway?`)) {
            return;
        }
    }

    let url = '/knowledge-gaps/api/draft';
    let payload = { service, content, document_type: docType, title };
    if (issueId) {
        url = `/knowledge-gaps/api/gap/${issueId}/draft`;
        payload = { ...payload, content };
    }

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.draft_id) {
            lastSavedDraftId = result.draft_id;
            alert(`Draft saved with ID ${result.draft_id}`);
            closeSmartDraftModal();
            loadIssues();
        } else {
            alert('Error saving draft: ' + (result.error || 'unknown'));
        }
    } catch (error) {
        alert('Network error: ' + error.message);
    }
}
async function submitForReview() {
    if (!lastSavedDraftId) { alert('Please save the draft first.'); return; }
    try {
        const response = await fetch(`/knowledge-gaps/api/draft/${lastSavedDraftId}/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();
        if (result.success) {
            alert('Draft submitted for review.');
            closeSmartDraftModal();
            loadIssues();
        } else {
            alert('Validation failed:\n' + (result.errors || []).join('\n'));
        }
    } catch (error) {
        alert('Network error: ' + error.message);
    }
}
function generateDraft() {
    if (!currentGapId) return;
    showSmartDraftModal();
    const gap = allGaps.find(g => g.id == currentGapId);
    if (gap) {
        const draftIssueSelect = document.getElementById('draftIssueId');
        if (draftIssueSelect) draftIssueSelect.value = gap.id;
        const draftServiceSelect = document.getElementById('draftService');
        if (draftServiceSelect) draftServiceSelect.value = gap.service;
        const draftTitleInput = document.getElementById('draftTitle');
        if (draftTitleInput) draftTitleInput.value = `Answer: ${gap.question.substring(0, 50)}`;
    }
}
function showCreateOverrideModal() {
    if (!currentGapId) return;
    const gap = allGaps.find(g => g.id == currentGapId);
    if (gap && typeof window.showOverrideModal === 'function') {
        window.showOverrideModal(gap);
    } else {
        alert('Override modal not available. Please ensure the Documents module is loaded.');
    }
}
function assignToMe(gapId) {
    fetch(`/knowledge-gaps/api/gap/${gapId}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentUserId })
    }).then(() => { selectIssue(gapId); loadIssues(); }).catch(err => alert('Assign failed: ' + err.message));
}
function markResolved() { showResolveModal(currentGapId, false); }
function showResolveModal(gapId, fromDrag = false) {
    currentGapId = gapId;
    const modal = document.getElementById('resolveModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.dataset.fromDrag = fromDrag;
    }
}
function closeResolveModal() { 
    const modal = document.getElementById('resolveModal');
    if (modal) modal.style.display = 'none';
}
async function confirmResolve() {
    const gapId = currentGapId;
    const modal = document.getElementById('resolveModal');
    const fromDrag = modal ? modal.dataset.fromDrag === 'true' : false;
    const data = {
        resolution_type: document.getElementById('resolveType')?.value,
        document_id: document.getElementById('resolveLink')?.value,
        notes: document.getElementById('resolveNotes')?.value
    };
    try {
        await fetch(`/knowledge-gaps/api/gap/${gapId}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        closeResolveModal();
        if (fromDrag) {
            const card = document.querySelector(`.kanban-card[data-id="${gapId}"]`);
            if (card) card.remove();
            const gap = allGaps.find(g => g.id == gapId);
            if (gap) {
                gap.status = 'completed';
                const newCard = createKanbanCard(gap);
                const completedColumn = document.querySelector('#kanban-completed .column-cards');
                if (completedColumn) completedColumn.appendChild(newCard);
            }
        }
        loadIssues();
        if (!fromDrag) selectIssue(gapId);
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
function refreshPage() { location.reload(); }

// Helper functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}