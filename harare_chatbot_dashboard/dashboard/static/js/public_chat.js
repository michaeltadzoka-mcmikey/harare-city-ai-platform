// public_chat.js – citizen chat interface with session persistence via cookie
// UPDATED: increased abort timeout to 5 minutes (300,000 ms) to allow full LLM generation.

let isSending = false;
let currentAbortController = null;

document.addEventListener('DOMContentLoaded', function () {
    const input = document.getElementById('messageInput');
    if (input) {
        input.addEventListener('keypress', handleEnter);
        input.focus();
    }
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    loadHistory();
    scrollToBottom();
});

async function loadHistory() {
    try {
        const response = await fetch('/public-chat/api/history');
        if (!response.ok) return;
        const history = await response.json();
        const chatHistory = document.getElementById('chatHistory');
        if (history.length) {
            const empty = chatHistory.querySelector('.empty-chat');
            if (empty) empty.remove();
            history.forEach(msg => {
                addMessageToUI('user', msg.user_message);
                addMessageToUI('bot', msg.bot_response, msg.source, msg.confidence, msg.intent, msg.metadata);
            });
        }
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

async function sendMessage() {
    if (isSending) return;
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const message = input.value.trim();
    if (!message) return;

    addMessageToUI('user', message);
    input.value = '';
    setInputDisabled(true);
    isSending = true;

    const thinkingId = showThinkingMessage();

    if (currentAbortController) {
        currentAbortController.abort();
    }
    currentAbortController = new AbortController();
    // Set timeout to 5 minutes (300,000 ms) – generous for slow LLM responses
    const timeoutId = setTimeout(() => {
        console.log("Request timed out after 5 minutes; aborting.");
        currentAbortController.abort();
    }, 300000);   // was 180000 (3 min) – increased to 300000 (5 min)

    try {
        const response = await fetch('/public-chat/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message }),
            signal: currentAbortController.signal
        });

        clearTimeout(timeoutId);
        removeThinkingMessage(thinkingId);

        if (!response.ok) {
            let errorMsg = `HTTP ${response.status}`;
            try {
                const errData = await response.json();
                errorMsg = errData.error || errorMsg;
            } catch (e) {}
            throw new Error(errorMsg);
        }

        const data = await response.json();
        addMessageToUI('bot', data.response, data.source, data.confidence, data.intent, data.metadata);
    } catch (error) {
        clearTimeout(timeoutId);
        removeThinkingMessage(thinkingId);
        let errorMessage = error.message || 'Failed to send message';
        if (error.name === 'AbortError') {
            errorMessage = 'The request timed out after 5 minutes. Please try again later.';
        }
        addMessageToUI('bot', `Error: ${errorMessage}`, 'offline', 0);
    } finally {
        setInputDisabled(false);
        isSending = false;
        currentAbortController = null;
        input.focus();
    }
}

function showThinkingMessage() {
    const chatHistory = document.getElementById('chatHistory');
    const empty = chatHistory.querySelector('.empty-chat');
    if (empty) empty.remove();

    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message bot-message thinking-message';
    thinkingDiv.setAttribute('data-thinking-id', Date.now().toString());
    thinkingDiv.innerHTML = `
        <div class="message-header">
            <span class="sender">Bot</span>
            <span class="timestamp">${new Date().toLocaleTimeString('en-GB', { hour:'2-digit', minute:'2-digit' })}</span>
        </div>
        <div class="message-text"><em>Bot is thinking…</em></div>
    `;
    chatHistory.appendChild(thinkingDiv);
    scrollToBottom();
    return thinkingDiv.getAttribute('data-thinking-id');
}

function removeThinkingMessage(thinkingId) {
    const thinkingMsg = document.querySelector(`.thinking-message[data-thinking-id="${thinkingId}"]`);
    if (thinkingMsg) thinkingMsg.remove();
}

function addMessageToUI(sender, text, source = null, confidence = null, intent = null, metadata = null) {
    const chatHistory = document.getElementById('chatHistory');
    if (!chatHistory) return;

    const empty = chatHistory.querySelector('.empty-chat');
    if (empty) empty.remove();

    const timestamp = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;

    let badgesHtml = '';
    if (sender === 'bot' && source) {
        const sourceMap = {
            'rag': '<span class="badge rag">📚 RAG</span>',
            'rag+llm': '<span class="badge rag">📚 RAG+LLM</span>',
            'rasa': '<span class="badge rasa">🤖 RASA</span>',
            'fallback': '<span class="badge fallback">⚙️ Fallback</span>',
            'offline': '<span class="badge offline">🔌 Offline</span>',
            'chitchat': '<span class="badge chitchat">💬 Chitchat</span>',
            'external': '<span class="badge external">🔗 External</span>',
            'llm': '<span class="badge llm">🧠 LLM</span>',
            'orchestrator': '<span class="badge llm">🧠 LLM</span>',
            'fastpath': '<span class="badge fastpath">⚡ FastPath</span>',
            'direct': '<span class="badge direct">📋 Direct</span>'
        };
        const sourceBadge = sourceMap[source] || '<span class="badge offline">🔌 Offline</span>';

        let confidenceBadge = '';
        const showConfidenceSources = ['rag', 'rag+llm', 'llm', 'orchestrator', 'fallback', 'chitchat'];
        if (confidence !== null && confidence !== undefined && showConfidenceSources.includes(source)) {
            let confClass = 'low';
            if (confidence >= 0.8) confClass = 'high';
            else if (confidence >= 0.5) confClass = 'medium';
            confidenceBadge = `<span class="badge confidence ${confClass}">${Math.round(confidence * 100)}%</span>`;
        } else if (['fastpath', 'direct', 'external'].includes(source)) {
            confidenceBadge = `<span class="badge confidence high">100%</span>`;
        }
        badgesHtml = `<div class="message-badges">${sourceBadge} ${confidenceBadge}</div>`;
    }

    const safeText = text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');

    messageDiv.innerHTML = `
        <div class="message-header">
            <span class="sender">${sender === 'user' ? 'You' : 'Bot'}</span>
            <span class="timestamp">${timestamp}</span>
        </div>
        <div class="message-text">${safeText}</div>
        ${badgesHtml}
    `;

    chatHistory.appendChild(messageDiv);
    scrollToBottom();
}

function scrollToBottom() {
    const chatHistory = document.getElementById('chatHistory');
    if (chatHistory) chatHistory.scrollTop = chatHistory.scrollHeight;
}

function setInputDisabled(disabled) {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    if (input) input.disabled = disabled;
    if (sendBtn) sendBtn.disabled = disabled;
}

function handleEnter(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}