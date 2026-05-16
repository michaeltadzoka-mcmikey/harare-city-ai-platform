/**
 * main.js – Global utilities and health polling
 */

let mainLoader = document.getElementById('main-loader');
let ragDot = document.getElementById('ragStatus');
let llmDot = document.getElementById('llmStatus');
let rasaDot = document.getElementById('rasaStatus');
let offlineBanner = document.getElementById('offline-banner');

window.healthState = {
    rag: 'offline',
    llm: 'offline',
    rasa: 'offline'
};

function setStatusDot(element, status) {
    if (!element) return;
    element.classList.remove('degraded', 'offline');
    if (status === 'healthy' || status === 'online') {
        element.style.backgroundColor = '#2ecc71';
    } else if (status === 'degraded') {
        element.style.backgroundColor = '#f39c12';
        element.classList.add('degraded');
    } else {
        element.style.backgroundColor = '#e74c3c';
        element.classList.add('offline');
    }
}

export function updateSystemStatus() {
    fetch('/api/system-status')
        .then(response => response.json())
        .then(data => {
            window.healthState.rag = data.rag;
            window.healthState.llm = data.llm;
            window.healthState.rasa = data.rasa;

            setStatusDot(ragDot, data.rag);
            setStatusDot(llmDot, data.llm);
            setStatusDot(rasaDot, data.rasa);

            window.dispatchEvent(new CustomEvent('health-update', { detail: window.healthState }));

            if (offlineBanner) {
                const offlineServices = [];
                if (data.rag !== 'healthy') offlineServices.push('RAG');
                if (data.llm !== 'healthy') offlineServices.push('LLM');
                if (data.rasa !== 'healthy') offlineServices.push('RASA');
                if (offlineServices.length) {
                    offlineBanner.textContent = `Offline: ${offlineServices.join(', ')}. Some features may be limited.`;
                    offlineBanner.style.display = 'block';
                } else {
                    offlineBanner.style.display = 'none';
                }
            }
        })
        .catch(err => {
            console.error('Status fetch failed:', err);
            window.healthState.rag = 'offline';
            window.healthState.llm = 'offline';
            window.healthState.rasa = 'offline';
            setStatusDot(ragDot, 'offline');
            setStatusDot(llmDot, 'offline');
            setStatusDot(rasaDot, 'offline');
            if (offlineBanner) {
                offlineBanner.textContent = 'Unable to reach status service.';
                offlineBanner.style.display = 'block';
            }
        });
}

export function showLoader() {
    if (mainLoader) mainLoader.style.display = 'flex';
}

export function hideLoader() {
    if (mainLoader) mainLoader.style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    updateSystemStatus();
    setInterval(updateSystemStatus, 60000);
});

window.copyToClipboard = function(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('Copied to clipboard!');
    }).catch(err => {
        console.error('Copy failed:', err);
    });
};