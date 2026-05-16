let trendChart = null;
let reportsChart = null;
let currentTrend = 'conversations';
let currentPeriod = '30d';
let currentCompare = 'none';

document.addEventListener('DOMContentLoaded', function () {
    loadDashboard();
    setupEventListeners();
    setupTabs();
});

function setupEventListeners() {
    document.getElementById('periodSelect').addEventListener('change', function (e) {
        currentPeriod = e.target.value;
        loadDashboard();
    });
    document.getElementById('compareSelect').addEventListener('change', function (e) {
        currentCompare = e.target.value;
        loadDashboard();
    });
    document.getElementById('exportBtn').addEventListener('click', exportData);
    document.getElementById('refreshBtn').addEventListener('click', refreshDashboard);
}

function setupTabs() {
    document.querySelectorAll('.analytics-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            document.querySelectorAll('.analytics-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.getElementById(`tab-${tabId}`).classList.add('active');
        });
    });
}

async function loadDashboard() {
    try {
        const url = `/analytics/api/data?period=${currentPeriod}&compare=${currentCompare}`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        console.log('Analytics data:', data);

        // III
        document.getElementById('healthValue').textContent = data.iii + ' / 100';
        const comps = data.iii_components || {};
        document.getElementById('healthComponents').innerHTML =
            `Coverage ${comps.coverage || 0}% | Health ${comps.knowledge_health || 0}% | Recurrence ${comps.recurrence || 0}% | Override Dep ${comps.override_dependence || 0}%`;

        // Risk panel
        const risk = data.risk_stability || {};
        document.getElementById('openGaps').textContent = risk.open_gaps || 0;
        document.getElementById('highRiskGaps').textContent = risk.high_risk_gaps || 0;
        document.getElementById('recurringGaps').textContent = risk.recurring_gaps || 0;
        document.getElementById('overrideTriggers').textContent = risk.override_triggers || 0;
        document.getElementById('avgResolution').textContent = (risk.avg_resolution_days || 0) + 'd';
        document.getElementById('expiredDocs').textContent = risk.expired_docs || 0;
        document.getElementById('missingValidity').textContent = risk.missing_validity || 0;
        document.getElementById('pinnedOverrides').textContent = risk.pinned_overrides || 0;

        // Service cards
        const serviceHealth = Array.isArray(data.service_health) ? data.service_health : [];
        renderServiceCards(serviceHealth);

        // Reports
        const reports = data.reports_overview || {};
        document.getElementById('reportsSubmitted').textContent = reports.submitted || 0;
        document.getElementById('reportsInProgress').textContent = reports.in_progress || 0;
        document.getElementById('reportsResolved').textContent = reports.resolved || 0;
        document.getElementById('reportsAvgTime').textContent = (reports.avg_resolution_days || 0) + 'd';
        renderReportsChart(reports.distribution || []);

        // Load trends chart
        await loadTrends();

        // Comparison
        if (data.comparison) {
            document.getElementById('compareIndicator').style.display = 'inline';
            const diff = data.iii - data.comparison.iii_prev;
            const percent = Math.abs(((diff) / (data.comparison.iii_prev || 1) * 100).toFixed(1));
            document.getElementById('healthTrend').textContent = diff > 0 ? '▲' : (diff < 0 ? '▼' : '→');
            document.getElementById('healthTrendPercent').textContent = percent + '%';
        } else {
            document.getElementById('compareIndicator').style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function renderServiceCards(services) {
    const container = document.getElementById('serviceCards');
    container.innerHTML = '';
    if (!services || services.length === 0) {
        container.innerHTML = '<div class="empty">No service data available</div>';
        return;
    }
    services.forEach(s => {
        let colorClass = 'green';
        if (s.coverage < 50) colorClass = 'red';
        else if (s.coverage < 80) colorClass = 'yellow';

        const card = document.createElement('div');
        card.className = `service-card ${colorClass}`;
        card.setAttribute('data-service', s.service);
        card.onclick = () => showServiceDetails(s.service);

        const sparkline = s.sparkline || [];
        const maxSpark = Math.max(...sparkline, 1);
        const sparkBars = sparkline.map(val =>
            `<div style="height:${val / maxSpark * 20}px; width:4px; background:#2c3e50; margin-right:2px;"></div>`
        ).join('');

        card.innerHTML = `
            <div class="service-name">${s.name}</div>
            <div class="service-score">${s.coverage}%</div>
            <div class="service-gaps">
                ⚠️ ${s.gaps} gaps
                ${s.critical_gaps > 0 ? `<span class="critical-badge">🔴 ${s.critical_gaps} critical</span>` : ''}
            </div>
            <div class="service-overrides">Overrides: ${s.overrides}</div>
            <div class="service-expiry">Expired: ${s.expired} | Missing: ${s.missing_validity}</div>
            <div class="sparkline" style="display:flex; align-items:flex-end; height:20px; margin-top:8px;">
                ${sparkBars}
            </div>
        `;
        container.appendChild(card);
    });
}

async function showServiceDetails(service) {
    try {
        const response = await fetch(`/knowledge-gaps/api/list?service=${service}&status=open`);
        const gaps = await response.json();
        let overrides = [];
        try {
            const overrideResponse = await fetch(`/documents/api/overrides?service=${service}`);
            if (overrideResponse.ok) overrides = await overrideResponse.json();
        } catch (e) {
            console.warn('Overrides endpoint not available', e);
        }

        let modal = document.getElementById('serviceDetailModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'serviceDetailModal';
            modal.className = 'modal';
            document.body.appendChild(modal);
        }
        modal.innerHTML = `
            <div class="modal-content">
                <span class="close" onclick="document.getElementById('serviceDetailModal').style.display='none'">&times;</span>
                <h3>Service Details: ${service}</h3>
                <h4>Open Gaps</h4>
                <ul>${gaps.items.slice(0, 10).map(g => `<li>${g.question} (priority ${g.priority_score})</li>`).join('')}</ul>
                <h4>Recent Overrides</h4>
                <ul>${overrides.slice(0, 10).map(o => `<li>${o.document_title} (${o.override_type})</li>`).join('')}</ul>
            </div>
        `;
        modal.style.display = 'block';
    } catch (error) {
        console.error('Error fetching service details:', error);
    }
}

async function loadTrends() {
    try {
        const url = `/analytics/api/data?period=${currentPeriod}&compare=${currentCompare}`;
        const response = await fetch(url);
        const data = await response.json();
        console.log('Trends data:', data.trends);
        renderTrendChart(data.trends, currentTrend);
    } catch (error) {
        console.error('Error loading trends:', error);
    }
}

function renderTrendChart(trends, trendType) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (trendChart) trendChart.destroy();

    if (!trends) {
        console.warn('No trends data');
        displayNoDataMessage(ctx);
        return;
    }

    console.log('trends.conversation_volume:', trends.conversation_volume);

    let labels = [];
    let datasets = [];

    switch (trendType) {
        case 'conversations':
            if (!trends.conversation_volume || trends.conversation_volume.length === 0) {
                console.warn('No conversation_volume data');
                displayNoDataMessage(ctx);
                return;
            }
            labels = trends.conversation_volume.map(d => d.date);
            datasets = [{
                label: 'Conversations',
                data: trends.conversation_volume.map(d => d.count),
                borderColor: '#3498db',
                tension: 0.1
            }];
            break;
        case 'gaps':
            if (!trends.gap_creation || trends.gap_creation.length === 0) {
                displayNoDataMessage(ctx);
                return;
            }
            labels = trends.gap_creation.map(d => d.date);
            datasets = [{
                label: 'New Gaps',
                data: trends.gap_creation.map(d => d.count),
                borderColor: '#e74c3c',
                tension: 0.1
            }];
            break;
        case 'overrides':
            if (!trends.override_usage || trends.override_usage.length === 0) {
                displayNoDataMessage(ctx);
                return;
            }
            labels = trends.override_usage.map(d => d.date);
            datasets = [{
                label: 'Overrides',
                data: trends.override_usage.map(d => d.count),
                borderColor: '#f39c12',
                tension: 0.1
            }];
            break;
        case 'expiry':
            if (!trends.expiry_trends || trends.expiry_trends.length === 0) {
                displayNoDataMessage(ctx);
                return;
            }
            labels = trends.expiry_trends.map(d => d.date);
            datasets = [{
                label: 'Expired Docs',
                data: trends.expiry_trends.map(d => d.count),
                borderColor: '#9b59b6',
                tension: 0.1
            }];
            break;
        case 'pinned':
            if (!trends.pinned_usage || trends.pinned_usage.length === 0) {
                displayNoDataMessage(ctx);
                return;
            }
            labels = trends.pinned_usage.map(d => d.date);
            datasets = [{
                label: 'Pinned Overrides',
                data: trends.pinned_usage.map(d => d.count),
                borderColor: '#1abc9c',
                tension: 0.1
            }];
            break;
        case 'service':
            labels = trends.conversation_volume.map(d => d.date);
            const perf = trends.service_performance || {};
            datasets = Object.keys(perf).map((service, idx) => ({
                label: service,
                data: perf[service].map(d => d.success),
                borderColor: `hsl(${idx * 60 % 360}, 70%, 50%)`,
                tension: 0.1,
                fill: false
            }));
            break;
        default:
            displayNoDataMessage(ctx);
            return;
    }

    if (labels.length === 0) {
        console.warn('No labels for trend chart, displaying no data message');
        displayNoDataMessage(ctx);
        return;
    }

    trendChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } }
        }
    });
}

function displayNoDataMessage(ctx) {
    ctx.font = '14px Arial';
    ctx.fillStyle = '#999';
    ctx.fillText('No data available for the selected period', 50, 150);
}

function renderReportsChart(distribution) {
    const ctx = document.getElementById('reportsChart').getContext('2d');
    if (reportsChart) reportsChart.destroy();
    const labels = distribution.map(d => d.status);
    const values = distribution.map(d => d.count);
    reportsChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: ['#3498db', '#f39c12', '#2ecc71', '#e74c3c', '#95a5a6']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

function switchTrend(trend) {
    currentTrend = trend;
    document.querySelectorAll('.trend-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelector(`.trend-tab[data-trend="${trend}"]`).classList.add('active');
    loadTrends();
}

function exportData() {
    window.location.href = `/analytics/api/export?period=${currentPeriod}`;
}

function refreshDashboard() {
    loadDashboard();
}