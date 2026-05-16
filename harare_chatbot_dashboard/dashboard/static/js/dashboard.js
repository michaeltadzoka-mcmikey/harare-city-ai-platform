// dashboard/static/js/dashboard.js

let liveRefreshInterval = null;
let liveEnabled = true;

document.addEventListener('DOMContentLoaded', function () {
    console.log('Dashboard JS loaded');
    if (window.initialDashboardData) {
        console.log('Initial data received:', window.initialDashboardData.system_health);
        updateAllComponents(window.initialDashboardData);
    } else {
        console.log('No initial data, fetching...');
        loadDashboardData();
    }
    startLiveRefresh();
    updateClock();
    setInterval(updateClock, 1000);
});

function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const liveTimeEl = document.getElementById('liveTime');
    if (liveTimeEl) liveTimeEl.textContent = timeStr;
}

function startLiveRefresh() {
    if (liveRefreshInterval) clearInterval(liveRefreshInterval);
    liveRefreshInterval = setInterval(loadDashboardData, 30000);
}

function stopLiveRefresh() {
    if (liveRefreshInterval) {
        clearInterval(liveRefreshInterval);
        liveRefreshInterval = null;
    }
}

function toggleLiveRefresh() {
    liveEnabled = !liveEnabled;
    const dot = document.getElementById('liveDot');
    const btn = document.querySelector('.btn-live');
    if (liveEnabled) {
        if (dot) dot.style.backgroundColor = '#2ecc71';
        if (btn) btn.textContent = 'Live';
        startLiveRefresh();
    } else {
        if (dot) dot.style.backgroundColor = '#95a5a6';
        if (btn) btn.textContent = 'Paused';
        stopLiveRefresh();
    }
}

async function loadDashboardData() {
    console.log('Fetching dashboard data from /api/dashboard...');
    try {
        const response = await fetch('/api/dashboard');
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        const data = await response.json();
        console.log('Dashboard data received:', data.system_health);
        updateAllComponents(data);
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

function updateAllComponents(data) {
    const requiredIds = [
        'ragStatusText', 'ragChunks', 'ragDocs',
        'llmStatusText', 'llmSessions', 'llmAvgResp',
        'rasaStatusText', 'rasaError',
        'readinessScore', 'gapsCount', 'expiredCount', 'conflictsCount',
        'todayConvos', 'weekConvos', 'monthConvos', 'coverage',
        'alertBanner', 'conflictSummary', 'serviceCards', 'emptyServices',
        'recentConversations', 'recentReports'
    ];
    const missing = requiredIds.filter(id => !document.getElementById(id));
    if (missing.length > 0) {
        console.warn('Missing DOM elements:', missing);
    }

    updateComponentRag(data.system_health.rag);
    updateComponentLlm(data.system_health.llm);
    updateComponentRasa(data.system_health.rasa);

    const readiness = data.deployment_readiness.readiness;
    let statusClass = readiness >= 70 ? '🟢 READY' : (readiness >= 40 ? '🟡 PARTIAL' : '🔴 AT RISK');
    setElementText('readinessScore', readiness + '% ' + statusClass);
    setElementHtml('gapsCount', `<i class="fas fa-exclamation-triangle"></i> ${data.deployment_readiness.open_gaps} Gaps`);
    setElementHtml('expiredCount', `<i class="fas fa-calendar-times"></i> ${data.deployment_readiness.expired_docs} Expired`);
    setElementHtml('conflictsCount', `<i class="fas fa-code-branch"></i> ${data.deployment_readiness.conflicts} Conflicts`);
    setElementHtml('todayConvos', `<i class="fas fa-calendar-day"></i> Today ${data.quick_stats.today}`);
    setElementHtml('weekConvos', `<i class="fas fa-calendar-week"></i> Week ${data.quick_stats.week}`);
    setElementHtml('monthConvos', `<i class="fas fa-calendar-alt"></i> Month ${formatNumber(data.quick_stats.month)}`);
    setElementHtml('coverage', `<i class="fas fa-chart-line"></i> Coverage ${data.quick_stats.coverage}%`);

    renderAlertBanner(data.alert);
    renderConflictSummary(data.conflict_summary);
    renderServiceCards(data.service_performance);
    renderRecentConversations(data.recent_conversations);
    renderRecentReports(data.recent_reports);
}

function setElementText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
    else console.warn(`Element #${id} not found`);
}

function setElementHtml(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
    else console.warn(`Element #${id} not found`);
}

function updateComponentRag(ragData) {
    console.log('Updating RAG component with:', ragData);
    const statusEl = document.getElementById('ragStatusText');
    if (statusEl) {
        let statusText = '';
        let statusColor = '';
        if (ragData.status === 'healthy') {
            statusText = '🟢 HEALTHY';
            statusColor = '#2ecc71';
        } else if (ragData.status === 'offline' || ragData.status === 'unreachable') {
            statusText = '🔴 OFFLINE';
            statusColor = '#e74c3c';
        } else if (ragData.status === 'timeout') {
            statusText = '🟡 TIMEOUT';
            statusColor = '#f39c12';
        } else if (ragData.status === 'degraded') {
            statusText = '🟡 DEGRADED';
            statusColor = '#f39c12';
        } else {
            statusText = '⚫ UNKNOWN';
            statusColor = '#95a5a6';
        }
        statusEl.innerHTML = statusText;
        statusEl.style.color = statusColor;
    } else {
        console.warn('Element #ragStatusText not found');
    }

    setElementText('ragChunks', ragData.chunks || 0);
    setElementText('ragDocs', ragData.documents || 0);
    if (ragData.error) console.warn('RAG error:', ragData.error);
}

function updateComponentLlm(llmData) {
    console.log('Updating LLM component with:', llmData);
    const statusEl = document.getElementById('llmStatusText');
    if (statusEl) {
        let statusText = '';
        let statusColor = '';
        if (llmData.status === 'healthy') {
            statusText = '🟢 HEALTHY';
            statusColor = '#2ecc71';
        } else if (llmData.status === 'offline' || llmData.status === 'unreachable') {
            statusText = '🔴 OFFLINE';
            statusColor = '#e74c3c';
        } else if (llmData.status === 'timeout') {
            statusText = '🟡 TIMEOUT';
            statusColor = '#f39c12';
        } else {
            statusText = '⚫ UNKNOWN';
            statusColor = '#95a5a6';
        }
        statusEl.innerHTML = statusText;
        statusEl.style.color = statusColor;
    } else {
        console.warn('Element #llmStatusText not found');
    }

    setElementText('llmSessions', llmData.sessions || 0);
    setElementText('llmAvgResp', llmData.avg_response || 0);
    if (llmData.error) console.warn('LLM error:', llmData.error);
}

function updateComponentRasa(rasaData) {
    console.log('Updating RASA component with:', rasaData);
    const statusEl = document.getElementById('rasaStatusText');
    if (statusEl) {
        let statusText = '';
        let statusColor = '';
        if (rasaData.status === 'healthy') {
            statusText = '🟢 HEALTHY';
            statusColor = '#2ecc71';
        } else if (rasaData.status === 'offline' || rasaData.status === 'unreachable') {
            statusText = '🔴 OFFLINE';
            statusColor = '#e74c3c';
        } else if (rasaData.status === 'timeout') {
            statusText = '🟡 TIMEOUT';
            statusColor = '#f39c12';
        } else {
            statusText = '⚫ UNKNOWN';
            statusColor = '#95a5a6';
        }
        statusEl.innerHTML = statusText;
        statusEl.style.color = statusColor;
    } else {
        console.warn('Element #rasaStatusText not found');
    }

    const errorMsg = rasaData.error || 'No error';
    setElementText('rasaError', errorMsg);
}

function renderAlertBanner(alert) {
    const bannerContainer = document.getElementById('alertBanner');
    if (!bannerContainer) return;
    if (alert && alert.message) {
        bannerContainer.innerHTML = `
            <div class="alert alert-${alert.type}">
                <i class="fas fa-exclamation-triangle"></i> ${escapeHtml(alert.message)}
                <button class="close-btn" onclick="this.parentElement.remove()">×</button>
            </div>
        `;
        bannerContainer.style.display = 'block';
    } else {
        bannerContainer.style.display = 'none';
        bannerContainer.innerHTML = '';
    }
}

function renderConflictSummary(summary) {
    const container = document.getElementById('conflictSummary');
    if (!container) return;
    if (summary && (summary.over_48h > 0 || summary.over_5d > 0 || summary.provisional > 0)) {
        container.innerHTML = `
            <div class="conflict-summary">
                <h4><i class="fas fa-exclamation"></i> Conflict Escalations</h4>
                <ul>
                    ${summary.over_48h > 0 ? `<li><span style="color: #ff6b6b;">🔴</span> ${summary.over_48h} unresolved >48h</li>` : ''}
                    ${summary.over_5d > 0 ? `<li><span style="color: #ff9f43;">🔥</span> ${summary.over_5d} unresolved >5d</li>` : ''}
                    ${summary.provisional > 0 ? `<li><span style="color: #feca57;">⏳</span> ${summary.provisional} provisional resolutions pending review</li>` : ''}
                </ul>
                <a href="/documents?conflict=true" class="btn-sm"><i class="fas fa-arrow-right"></i> View Conflicts</a>
            </div>
        `;
    } else {
        container.innerHTML = '';
    }
}

function renderServiceCards(services) {
    const container = document.getElementById('serviceCards');
    const emptyMsg = document.getElementById('emptyServices');
    if (!services || services.length === 0) {
        if (container) container.innerHTML = '';
        if (emptyMsg) emptyMsg.style.display = 'block';
        return;
    }
    if (emptyMsg) emptyMsg.style.display = 'none';
    let html = '';
    services.forEach(s => {
        let colorClass = 'green';
        if (s.success < 50) colorClass = 'red';
        else if (s.success < 80) colorClass = 'yellow';
        html += `
            <div class="service-card ${colorClass}" onclick="window.location.href='/knowledge-gaps?service=${encodeURIComponent(s.name.toLowerCase())}'">
                <div class="service-name">${escapeHtml(s.name)}</div>
                <div class="service-score">${s.success}%</div>
                <div class="service-gaps"><i class="fas fa-exclamation-circle"></i> ${s.gaps} gaps</div>
            </div>
        `;
    });
    if (container) container.innerHTML = html;
}

function renderRecentConversations(convos) {
    const container = document.getElementById('recentConversations');
    if (!container) return;
    if (!convos || convos.length === 0) {
        container.innerHTML = '<p class="empty-message">No recent conversations</p>';
        return;
    }
    let html = '';
    convos.forEach(c => {
        const badgeClass = c.user_type === 'admin' ? 'admin' : '';
        const badgeIcon = c.user_type === 'admin' ? '<i class="fas fa-crown"></i> Admin' : '<i class="fas fa-user"></i> Citizen';
        html += `
            <div class="activity-item" onclick="window.location.href='/conversations/${c.id}'">
                <span class="activity-time">${c.time}</span>
                <span class="activity-text">${escapeHtml(c.preview)}</span>
                <span class="activity-badge ${badgeClass}">${badgeIcon}</span>
            </div>
        `;
    });
    container.innerHTML = html;
}

function renderRecentReports(reports) {
    const container = document.getElementById('recentReports');
    if (!container) return;
    if (!reports || reports.length === 0) {
        container.innerHTML = '<p class="empty-message">No recent reports</p>';
        return;
    }
    let html = '';
    reports.forEach(r => {
        html += `
            <div class="activity-item" onclick="window.location.href='/reports/${r.reference}'">
                <span class="activity-time">${r.time || ''}</span>
                <span class="activity-text">${escapeHtml(r.type)} – ${escapeHtml(r.location)}</span>
            </div>
        `;
    });
    container.innerHTML = html;
}

function formatNumber(num) {
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num.toString();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function generateReport() {
    alert('Generate PDF report – to be implemented');
}