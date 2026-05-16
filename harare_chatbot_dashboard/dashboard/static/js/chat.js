// chat.js – admin chat interface with timeout and loading indicator
// Updated source mapping for all gateway response types

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

    const copyBtn = document.getElementById('copySession');
    if (copyBtn) copyBtn.addEventListener('click', copySessionId);
    const clearBtn = document.getElementById('clearSession');
    if (clearBtn) clearBtn.addEventListener('click', clearChat);

    loadHistory();
    scrollToBottom();
});

async function loadHistory() {
    try {
        const response = await fetch('/chat/api/history');
        if (!response.ok) return;
        const history = await response.json();
        const chatHistory = document.getElementById('chatHistory');
        if (history.length) {
            const empty = chatHistory.querySelector('.empty-chat');
            if (empty) empty.remove();
            history.forEach(msg => {
                addMessageToUI('user', msg.user_message, null, null, null, null);
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
    const timeoutId = setTimeout(() => currentAbortController.abort(), 180000);

    try {
        const response = await fetch('/chat/api/send', {
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
            } catch (e) { /* ignore */ }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        addMessageToUI('bot', data.response, data.source, data.confidence, data.intent, data.metadata);
        console.log('Chat response:', data);
    } catch (error) {
        clearTimeout(timeoutId);
        removeThinkingMessage(thinkingId);

        let errorMessage = error.message || 'Failed to send message';
        if (error.name === 'AbortError') {
            errorMessage = 'The request timed out. Please try again later.';
        }
        console.error('Error sending message:', error);
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
        // Comprehensive source map for all gateway response types
        const sourceMap = {
            'rag': '<span class="badge rag">📚 RAG</span>',
            'rag+llm': '<span class="badge rag">📚 RAG+LLM</span>',
            'rasa': '<span class="badge rasa">🤖 RASA</span>',
            'fallback': '<span class="badge fallback">⚙️ Fallback</span>',
            'offline': '<span class="badge offline">🔌 Offline</span>',
            'chitchat': '<span class="badge chitchat">💬 Chitchat</span>',
            'domain_handler': '<span class="badge chitchat">💬 Chitchat</span>',
            'external': '<span class="badge external">🔗 External</span>',
            'llm': '<span class="badge llm">🧠 LLM</span>',
            'orchestrator': '<span class="badge llm">🧠 LLM</span>',
            'fastpath': '<span class="badge fastpath">⚡ FastPath</span>',
            'direct': '<span class="badge direct">📋 Direct</span>',
            'system': '<span class="badge system">⚙️ System</span>',
            'dashboard': '<span class="badge dashboard">📊 Dashboard</span>',
            'error': '<span class="badge fallback">⚙️ Fallback</span>'
        };
        const sourceBadge = sourceMap[source] || '<span class="badge offline">🔌 Offline</span>';

        let confidenceBadge = '';
        // Only show confidence for sources that actually have meaningful confidence values
        const showConfidenceSources = ['rag', 'rag+llm', 'llm', 'orchestrator', 'fallback', 'chitchat'];
        if (confidence !== null && confidence !== undefined && showConfidenceSources.includes(source)) {
            let confClass = 'low';
            if (confidence >= 0.8) confClass = 'high';
            else if (confidence >= 0.5) confClass = 'medium';
            confidenceBadge = `<span class="badge confidence ${confClass}">${Math.round(confidence * 100)}%</span>`;
        } else if (['fastpath', 'direct', 'external'].includes(source)) {
            // Fast-path responses are deterministic – show 100% confidence
            confidenceBadge = `<span class="badge confidence high">100%</span>`;
        }
        badgesHtml = `<div class="message-badges">${sourceBadge} ${confidenceBadge}</div>`;
    }

    const safeText = text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');

    let tooltipTitle = '';
    if (sender === 'bot' && metadata) {
        const intentStr = intent ? `Intent: ${intent}` : '';
        const docs = metadata.documents ? `Docs: ${metadata.documents.join(', ')}` : '';
        tooltipTitle = [intentStr, docs].filter(Boolean).join(' | ');
    }

    messageDiv.innerHTML = `
        <div class="message-header">
            <span class="sender">${sender === 'user' ? 'You' : 'Bot'}</span>
            <span class="timestamp">${timestamp}</span>
        </div>
        <div class="message-text" ${tooltipTitle ? `title="${tooltipTitle}"` : ''}>${safeText}</div>
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

async function clearChat() {
    if (!confirm('Clear chat history?')) return;
    try {
        const response = await fetch('/chat/api/clear', { method: 'POST' });
        if (response.ok) {
            const chatHistory = document.getElementById('chatHistory');
            chatHistory.innerHTML = '<div class="empty-chat"><p>No messages yet. Start a conversation!</p></div>';
        } else {
            alert('Failed to clear chat');
        }
    } catch (error) {
        console.error('Error clearing chat:', error);
        alert('Error clearing chat');
    }
}

function copySessionId() {
    const sessionIdSpan = document.getElementById('sessionId');
    if (!sessionIdSpan) return;
    const sessionId = sessionIdSpan.textContent.replace('Session: ', '').trim();
    navigator.clipboard.writeText(sessionId).then(() => {
        const copyBtn = document.getElementById('copySession');
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copied!';
        setTimeout(() => copyBtn.textContent = originalText, 1500);
    }).catch(() => alert('Failed to copy'));
}