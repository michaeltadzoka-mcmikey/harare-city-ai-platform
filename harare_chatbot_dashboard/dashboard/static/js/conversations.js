// Conversations page – Hybrid view with Sessions / Messages toggle

let currentView = 'sessions';   // 'sessions' or 'messages'
let currentFilters = {
    date: 'last_7_days',
    user_type: 'all',
    user_id: 'all',
    department: 'all',
    service: 'all',
    search: '',
    page: 1
};
let currentSessionId = null;

document.addEventListener('DOMContentLoaded', function() {
    // Setup view toggle buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentView = this.getAttribute('data-view');
            loadCurrentView();
        });
    });
    // Initial load
    loadCurrentView();
});

async function loadCurrentView() {
    if (currentView === 'sessions') {
        await loadSessions();
    } else {
        await loadMessagesList();
    }
}

// ---------- Sessions view ----------
async function loadSessions() {
    // Update filters from UI
    currentFilters.date = document.getElementById('dateFilter').value;
    currentFilters.user_type = document.getElementById('userTypeFilter').value;
    currentFilters.user_id = document.getElementById('userFilter').value;
    currentFilters.department = document.getElementById('deptFilter').value;
    currentFilters.service = document.getElementById('serviceFilter').value;
    currentFilters.search = document.getElementById('searchInput').value;
    currentFilters.page = 1; // reset to first page

    const container = document.getElementById('contentArea');
    container.innerHTML = '<div class="loading-spinner"><p>Loading conversations...</p></div>';

    const params = new URLSearchParams(currentFilters);
    try {
        const response = await fetch(`/conversations/api/sessions?${params}`);
        if (!response.ok) throw new Error('Failed to load');
        const data = await response.json();
        displaySessions(data.items, data.total, data.page, data.pages);
    } catch (error) {
        console.error('Error loading sessions:', error);
        container.innerHTML = '<p class="error">Failed to load conversations</p>';
    }
}

function displaySessions(sessions, total, page, pages) {
    const container = document.getElementById('contentArea');
    if (!sessions.length) {
        container.innerHTML = '<div class="empty-state"><p>No conversations found</p></div>';
        return;
    }

    let html = `
        <div class="session-layout">
            <div class="session-list-panel">
                <div class="list-header">
                    <p class="total-count">Total: ${formatNumber(total)} conversations</p>
                </div>
                <div class="sessions">
    `;
    sessions.forEach(sess => {
        const date = new Date(sess.last_activity).toLocaleString();
        const userTypeIcon = sess.user_type === 'admin' ? '[Admin]' : '';
        const activeClass = (currentSessionId === sess.session_id) ? 'active' : '';
        html += `
            <div class="session-card ${activeClass}" onclick="selectSession('${sess.session_id}')">
                <div class="session-header">
                    <span class="session-user">${escapeHtml(sess.user_id || 'Anonymous')} ${userTypeIcon}</span>
                    <span class="session-date">${date}</span>
                </div>
                <div class="session-preview">${escapeHtml(sess.last_message)}</div>
                <div class="session-meta">
                    <span class="session-message-count">${sess.message_count} messages</span>
                </div>
            </div>
        `;
    });
    html += `</div>`;
    if (pages > 1) {
        html += `<div class="pagination">
            ${page > 1 ? `<button onclick="changePage(${page - 1})">Previous</button>` : ''}
            <span>Page ${page} of ${pages}</span>
            ${page < pages ? `<button onclick="changePage(${page + 1})">Next</button>` : ''}
        </div>`;
    }
    html += `</div><div class="thread-panel" id="threadPanel"><div class="empty-thread"><p>Select a conversation to view details</p></div></div></div>`;
    container.innerHTML = html;

    // If there was a previously selected session, try to re-select it after refresh
    if (currentSessionId) {
        const card = document.querySelector(`.session-card[onclick="selectSession('${currentSessionId}')"]`);
        if (card) {
            card.classList.add('active');
            selectSession(currentSessionId);
        } else {
            currentSessionId = null;
        }
    }
}

async function selectSession(sessionId) {
    currentSessionId = sessionId;
    // Highlight active card
    document.querySelectorAll('.session-card').forEach(card => {
        card.classList.remove('active');
    });
    const activeCard = document.querySelector(`.session-card[onclick="selectSession('${sessionId}')"]`);
    if (activeCard) activeCard.classList.add('active');

    const threadPanel = document.getElementById('threadPanel');
    if (!threadPanel) return;
    threadPanel.innerHTML = '<div class="loading-spinner"><p>Loading conversation...</p></div>';

    try {
        const response = await fetch(`/conversations/api/session/${sessionId}`);
        if (!response.ok) throw new Error('Failed to load thread');
        const data = await response.json();
        displayThread(data.thread, threadPanel);
    } catch (error) {
        console.error('Error loading thread:', error);
        threadPanel.innerHTML = '<p class="error">Failed to load conversation</p>';
    }
}

function displayThread(thread, container) {
    if (!thread.length) {
        container.innerHTML = '<div class="empty-thread"><p>No messages in this session</p></div>';
        return;
    }

    let html = '<div class="thread">';
    thread.forEach(msg => {
        const time = new Date(msg.timestamp).toLocaleString();
        const confidenceClass = (msg.confidence && msg.confidence < 0.6) ? 'low-confidence' : '';
        const confidenceBadge = msg.confidence
            ? `<span class="badge confidence-${getConfidenceClass(msg.confidence)}">${Math.round(msg.confidence * 100)}%</span>`
            : '';
        const sourceBadge = msg.source ? `<span class="badge ${msg.source}">${getSourceLabel(msg.source)}</span>` : '';
        const metadata = msg.metadata || {};

        html += `
            <div class="message-pair">
                <div class="user-message">
                    <strong>User ${msg.user_type === 'admin' ? '(Admin)' : ''}:</strong>
                    <div>${escapeHtml(msg.user_message)}</div>
                    <div class="message-meta">
                        <span>${time}</span>
                    </div>
                </div>
                <div class="bot-message ${confidenceClass}">
                    <strong>Bot:</strong>
                    <div class="bot-response-content" id="bot-content-${msg.id}">
                        ${formatBotResponse(msg.bot_response, msg.id)}
                    </div>
                    <div class="message-meta">
                        ${sourceBadge} ${confidenceBadge}
                        ${msg.intent ? `<span>Intent: ${msg.intent}</span>` : ''}
                        ${metadata.response_time_ms ? `<span>Response time: ${metadata.response_time_ms}ms</span>` : ''}
                    </div>
                    ${(!msg.bot_response || msg.confidence < 0.6) ? `
                        <button class="knowledge-gap-btn" onclick="createKnowledgeGap('${escapeHtml(msg.user_message)}', ${msg.id})">
                            Create Knowledge Gap
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;

    // Add expand/collapse for long bot responses
    document.querySelectorAll('.bot-response-content').forEach(el => {
        const text = el.innerText.trim();
        if (text.length > 300) {
            const id = el.id;
            const truncatedText = text.substring(0, 300);
            const fullText = text;
            el.innerHTML = `
                <div id="${id}-truncated" class="truncated-text">${escapeHtml(truncatedText)}...</div>
                <div id="${id}-full" style="display:none;">${escapeHtml(fullText)}</div>
                <span class="expand-btn" onclick="toggleExpand('${id}')">Show more</span>
            `;
        }
    });
}

function formatBotResponse(text, msgId) {
    if (!text) return '<em>No response</em>';
    return `<div id="bot-${msgId}">${escapeHtml(text)}</div>`;
}

function toggleExpand(elementId) {
    const truncated = document.getElementById(`${elementId}-truncated`);
    const full = document.getElementById(`${elementId}-full`);
    const btn = document.querySelector(`#${elementId} .expand-btn`);
    if (truncated && full) {
        if (truncated.style.display !== 'none') {
            truncated.style.display = 'none';
            full.style.display = 'block';
            btn.innerText = 'Show less';
        } else {
            truncated.style.display = 'block';
            full.style.display = 'none';
            btn.innerText = 'Show more';
        }
    }
}

// ---------- Messages view (original list) ----------
async function loadMessagesList() {
    // Update filters from UI
    currentFilters.date = document.getElementById('dateFilter').value;
    currentFilters.user_type = document.getElementById('userTypeFilter').value;
    currentFilters.user_id = document.getElementById('userFilter').value;
    currentFilters.department = document.getElementById('deptFilter').value;
    currentFilters.service = document.getElementById('serviceFilter').value;
    currentFilters.search = document.getElementById('searchInput').value;
    currentFilters.page = 1;

    const container = document.getElementById('contentArea');
    container.innerHTML = '<div class="loading-spinner"><p>Loading messages...</p></div>';

    const params = new URLSearchParams(currentFilters);
    try {
        const response = await fetch(`/conversations/api/list?${params}`);
        if (!response.ok) throw new Error('Failed to load');
        const data = await response.json();
        displayMessagesList(data.items, data.total, data.page, data.pages);
    } catch (error) {
        console.error('Error loading messages:', error);
        container.innerHTML = '<p class="error">Failed to load messages</p>';
    }
}

function displayMessagesList(messages, total, page, pages) {
    const container = document.getElementById('contentArea');
    if (!messages.length) {
        container.innerHTML = '<div class="empty-state"><p>No messages found</p></div>';
        return;
    }

    let html = `
        <div class="messages-view-container">
            <div class="list-header">
                <p class="total-count">Total: ${formatNumber(total)} messages</p>
            </div>
            <div class="table-container" style="overflow-x: auto;">
                <table class="messages-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>User ID</th>
                            <th>Type</th>
                            <th>Question</th>
                            <th>Service</th>
                            <th>Intent</th>
                            <th>Confidence</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
    `;
    messages.forEach(msg => {
        const time = new Date(msg.timestamp).toLocaleString();
        const confidence = msg.confidence ? `${(msg.confidence * 100).toFixed(0)}%` : '-';
        const userTypeLabel = msg.user_type === 'admin' ? 'Admin' : 'Citizen';
        const serviceName = msg.service || '-';
        html += `
            <tr>
                <td>${time}</td>
                <td><a href="#" onclick="viewUser('${msg.user_id}'); return false;">${escapeHtml(msg.user_id)}</a></td>
                <td>${userTypeLabel}</td>
                <td>${escapeHtml(msg.user_message)}</td>
                <td>${serviceName}</td>
                <td>${msg.intent || '-'}</td>
                <td>${confidence}</td>
                <td><button class="btn-view-message" onclick="viewMessageDetails(${msg.id})">View</button></td>
            </tr>
        `;
    });
    html += `
                    </tbody>
                </table>
            </div>
            <div class="pagination">
                ${page > 1 ? `<button onclick="changePage(${page - 1})">Previous</button>` : ''}
                <span>Page ${page} of ${pages}</span>
                ${page < pages ? `<button onclick="changePage(${page + 1})">Next</button>` : ''}
            </div>
        </div>
    `;
    container.innerHTML = html;
}

async function viewMessageDetails(id) {
    try {
        const response = await fetch(`/conversations/api/${id}`);
        if (!response.ok) throw new Error('Failed to load');
        const data = await response.json();
        displayConversationModal(data);
    } catch (error) {
        console.error('Error loading message details:', error);
        alert('Failed to load message details');
    }
}

function displayConversationModal(convo) {
    let modal = document.getElementById('conversationModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'conversationModal';
        modal.className = 'modal';
        modal.innerHTML = `<div class="modal-content"><span class="close" onclick="closeModal()">&times;</span><div id="modalDetails"></div></div>`;
        document.body.appendChild(modal);
        modal.style.display = 'flex';
    } else {
        modal.style.display = 'flex';
    }
    const detailsDiv = document.getElementById('modalDetails');
    const hasResponse = convo.bot_response && convo.bot_response.length > 0;
    const userType = convo.user_type === 'admin' ? 'Admin' : 'Citizen';
    const metadata = convo.metadata || {};

    detailsDiv.innerHTML = `
        <h2>Conversation Details</h2>
        <div class="details-grid">
            <div class="detail-row"><strong>User:</strong> ${escapeHtml(convo.user_id)} (${userType})</div>
            <div class="detail-row"><strong>Time:</strong> ${new Date(convo.timestamp).toLocaleString()}</div>
            <div class="detail-row"><strong>Session ID:</strong> ${convo.session_id}</div>
            <div class="detail-row"><strong>Service:</strong> ${convo.service || '-'}</div>
            <div class="detail-section"><h3>Question</h3><div class="message-box">${escapeHtml(convo.user_message)}</div></div>
            ${hasResponse ? `<div class="detail-section"><h3>Answer</h3><div class="message-box">${escapeHtml(convo.bot_response)}</div></div>` : '<div class="detail-section"><h3>Answer</h3><div class="message-box">No response provided</div></div>'}
            <div class="detail-section"><h3>Metadata</h3>
            <table class="metadata-table">
                <tr><th>Intent</th><td>${convo.intent || '-'}</td></tr>
                <tr><th>Confidence</th><td>${convo.confidence ? (convo.confidence * 100).toFixed(1) + '%' : '-'}</td></tr>
                <tr><th>Department</th><td>${metadata.department || '-'}</td></tr>
                <tr><th>Response Time</th><td>${metadata.response_time_ms ? metadata.response_time_ms + 'ms' : '-'}</td></tr>
                <tr><th>RAG Used</th><td>${metadata.rag_used ? 'Yes' : 'No'}</td></tr>
                <tr><th>RASA Used</th><td>${metadata.rasa_used ? 'Yes' : 'No'}</td></tr>
                <tr><th>Source</th><td>${convo.source || 'whatsapp'}</td></tr>
                <tr><th>User Type</th><td>${convo.user_type || 'citizen'}</td></tr>
            </table>
            </div>
        </div>
    `;
}

function closeModal() {
    const modal = document.getElementById('conversationModal');
    if (modal) modal.style.display = 'none';
}

// ---------- Helper functions ----------
function getConfidenceClass(conf) {
    if (conf >= 0.8) return 'high';
    if (conf >= 0.5) return 'medium';
    return 'low';
}

function getSourceLabel(source) {
    const labels = {
        'rag': 'RAG',
        'rag+llm': 'RAG',
        'rasa': 'RASA',
        'fallback': 'Fallback',
        'chitchat': 'Chitchat',
        'external': 'External',
        'llm': 'LLM',
        'system': 'System',
        'domain_handler': 'Chitchat'
    };
    return labels[source] || 'Unknown';
}

function changePage(page) {
    currentFilters.page = page;
    loadCurrentView();
}

function filterChanged() {
    currentFilters.page = 1;
    loadCurrentView();
}

const debouncedSearch = debounce(filterChanged, 500);

function toggleAdvancedFilters() {
    const adv = document.getElementById('advancedFilters');
    if (adv.style.display === 'none') {
        adv.style.display = 'block';
    } else {
        adv.style.display = 'none';
    }
}

function viewUser(userId) {
    // Switch to messages view and filter by that user
    document.getElementById('userFilter').value = userId;
    document.querySelector('.view-btn[data-view="messages"]').click();
    filterChanged();
}

function exportCSV() {
    const params = new URLSearchParams(currentFilters);
    window.location.href = `/conversations/api/export?${params}`;
}

function createKnowledgeGap(question, messageId) {
    window.location.href = `/knowledge_gaps/new?question=${encodeURIComponent(question)}&message_id=${messageId}`;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}