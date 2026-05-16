/**
 * documents.js – Full Documents & RAG module (FULLY FIXED)
 * Includes:
 * - Removed bulk import button
 * - Edit mode: back button, undo/redo/cancel working, collapsible metadata/validation
 * - Stats clicks switch to list view with correct filters
 * - Fixed blank center panel after save
 * - Auto‑refresh tree and list after any document change
 */

import { showLoader, hideLoader } from './main.js';

window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
};

document.addEventListener('DOMContentLoaded', function() {
    // State
    let currentDocId = null;
    let currentDocData = null;
    let originalContent = '';
    let historyStack = [];
    let historyIndex = -1;
    let currentPage = 1;
    let totalPages = 1;
    let selectedDocs = new Set();
    let currentTab = 'knowledge';
    let ledgerPage = 1;
    let ledgerFilter = '';
    let isEditMode = false;

    // DOM elements
    const treeEl = document.getElementById('knowledgeTree');
    const listView = document.getElementById('listView');
    const editorView = document.getElementById('editorView');
    const validationList = document.getElementById('validationList');
    const ingestBtn = document.getElementById('ingestBtn');
    const knowledgeView = document.getElementById('knowledgeView');
    const analyticsView = document.getElementById('analyticsView');
    const expiredView = document.getElementById('expiredView');
    const ledgerView = document.getElementById('ledgerView');
    const conflictView = document.getElementById('conflictView');
    const tabs = document.querySelectorAll('.doc-tab');
    const rightPanel = document.getElementById('rightPanel');
    const treePanel = document.getElementById('knowledgeTreePanel');
    const toggleTreeBtn = document.getElementById('toggleTreeBtn');
    const editModeTemplate = document.getElementById('editModeTemplate');
    const autoFixBtn = document.getElementById('autoFixBtn');
    const overrideRisk = document.getElementById('overrideRisk');

    if (rightPanel) rightPanel.style.display = 'none';

    const ragOnline = () => window.healthState?.rag === 'healthy';

    function setRagButtonsEnabled(enabled) {
        document.querySelectorAll('[data-requires-rag]').forEach(el => {
            el.disabled = !enabled;
            el.title = enabled ? '' : 'RAG offline – action unavailable';
        });
    }
    setInterval(() => setRagButtonsEnabled(ragOnline()), 5000);

    function updateRagStatus() {
        fetch('/documents/api/health')
            .then(res => res.json())
            .then(data => {
                const ragHealthSpan = document.getElementById('ragHealth');
                const ragStatusDiv = document.getElementById('ragStatus');
                if (data.status === 'healthy') {
                    ragHealthSpan.innerHTML = '<i class="fas fa-circle" style="color:#2ecc71;"></i> Healthy';
                    ragStatusDiv.style.color = '';
                } else {
                    ragHealthSpan.innerHTML = '<i class="fas fa-exclamation-triangle" style="color:#e74c3c;"></i> Unhealthy';
                    ragStatusDiv.style.color = 'red';
                }
            })
            .catch(() => {
                document.getElementById('ragHealth').innerHTML = '<i class="fas fa-power-off"></i> Offline';
            });
    }

    // Tab switching
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });

    function switchTab(tabName) {
        tabs.forEach(t => t.classList.remove('active'));
        document.querySelector(`.doc-tab[data-tab="${tabName}"]`).classList.add('active');
        
        knowledgeView.style.display = 'none';
        analyticsView.style.display = 'none';
        expiredView.style.display = 'none';
        ledgerView.style.display = 'none';
        conflictView.style.display = 'none';
        
        if (tabName === 'knowledge') {
            knowledgeView.style.display = 'flex';
            currentTab = 'knowledge';
            loadStats();
            loadList(1);
        } else if (tabName === 'analytics') {
            analyticsView.style.display = 'block';
            currentTab = 'analytics';
            loadAnalyticsStrip();
        } else if (tabName === 'expired') {
            expiredView.style.display = 'block';
            currentTab = 'expired';
            loadExpiredMonitor();
        } else if (tabName === 'ledger') {
            ledgerView.style.display = 'block';
            currentTab = 'ledger';
            loadDecisionLedger(1);
        } else if (tabName === 'conflict') {
            conflictView.style.display = 'block';
            currentTab = 'conflict';
            loadConflictQueue();
        }
    }

    // Initial data load
    showLoader();
    Promise.all([
        fetch('/documents/api/tree').then(res => res.json()),
        fetch('/documents/api/list?page=1&per_page=50').then(res => res.json()),
        fetch('/documents/api/list?page=1&per_page=1').then(res => res.json()),
        fetch('/documents/api/filter-options').then(res => res.json())
    ]).then(([treeData, listData, countData, filterData]) => {
        renderTree(treeData);
        renderList(listData);
        document.getElementById('totalDocs').textContent = countData.total;
        populateFilters(filterData);
        loadStats();
        hideLoader();
        setupModalCloseHandlers();
        attachStatsClickHandlers();
        updateRagStatus();
        setInterval(updateRagStatus, 30000);
    }).catch(err => {
        console.error('Failed to load documents:', err);
        treeEl.innerHTML = '<li class="error">Unable to load knowledge tree.</li>';
        hideLoader();
        setupModalCloseHandlers();
        updateRagStatus();
        setInterval(updateRagStatus, 30000);
    });

    // Helper: display active overrides
    function displayActiveOverrides(docId) {
        fetch('/documents/api/overrides?show_expired=false')
            .then(res => res.json())
            .then(overrides => {
                const targetOverrides = overrides.filter(o => o.target_type === 'document_id' && o.target_value === docId);
                const container = document.getElementById('activeOverridesList');
                if (!container) return;
                if (targetOverrides.length === 0) {
                    container.innerHTML = '<div class="meta-field">No active overrides targeting this document.</div>';
                    return;
                }
                let html = '<div class="meta-field"><label>Active Overrides:</label></div>';
                targetOverrides.forEach(ov => {
                    html += `<div class="override-item" data-id="${ov.id}">
                                <strong>${ov.override_type}</strong> – ${ov.justification.substring(0, 50)}...
                                <button class="btn btn-small revoke-override-btn" data-id="${ov.id}">Revoke</button>
                             </div>`;
                });
                container.innerHTML = html;
                document.querySelectorAll('.revoke-override-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const id = btn.dataset.id;
                        if (confirm('Revoke this override?')) {
                            fetch(`/documents/api/overrides/${id}/revoke`, { method: 'POST' })
                                .then(res => res.json())
                                .then(data => {
                                    if (data.success) {
                                        alert('Override revoked');
                                        displayActiveOverrides(docId);
                                    } else alert('Revoke failed');
                                });
                        }
                    });
                });
            })
            .catch(err => console.error('Failed to load overrides', err));
    }

    // Utility functions
    function setupModalCloseHandlers() {
        document.querySelectorAll('.close-btn').forEach(btn => {
            btn.removeEventListener('click', closeHandler);
            btn.addEventListener('click', closeHandler);
        });
        document.querySelectorAll('[onclick^="closeModal"]').forEach(btn => {
            const onclickAttr = btn.getAttribute('onclick');
            if (onclickAttr) {
                btn.removeAttribute('onclick');
                btn.addEventListener('click', function(e) {
                    const match = onclickAttr.match(/closeModal\(['"]([^'"]+)['"]\)/);
                    if (match && match[1]) {
                        const modal = document.getElementById(match[1]);
                        if (modal) modal.style.display = 'none';
                    }
                });
            }
        });
    }

    function closeHandler(e) {
        const modal = e.target.closest('.modal');
        if (modal) modal.style.display = 'none';
    }

    function populateFilters(filterData) {
        const serviceSelect = document.getElementById('serviceFilter');
        const contentTypeSelect = document.getElementById('contentTypeFilter');
        
        serviceSelect.innerHTML = '<option value="">All Services</option>';
        contentTypeSelect.innerHTML = '<option value="">All Content Types</option>';
        
        filterData.services.forEach(s => {
            const option = document.createElement('option');
            option.value = s;
            option.textContent = s.charAt(0).toUpperCase() + s.slice(1);
            serviceSelect.appendChild(option);
        });
        
        filterData.content_types.forEach(ct => {
            const option = document.createElement('option');
            option.value = ct;
            option.textContent = ct.replace('_', ' ').charAt(0).toUpperCase() + ct.slice(1).replace('_', ' ');
            contentTypeSelect.appendChild(option);
        });
    }

    // ========== FIXED: Stats clicks now switch to list view ==========
    function attachStatsClickHandlers() {
        document.getElementById('totalDocs').addEventListener('click', () => {
            switchTab('knowledge');
            document.getElementById('serviceFilter').value = '';
            document.getElementById('contentTypeFilter').value = '';
            document.getElementById('statusFilter').value = '';
            document.getElementById('searchInput').value = '';
            loadList(1);
        });
        document.getElementById('pendingDocs').addEventListener('click', () => {
            switchTab('knowledge');
            document.getElementById('serviceFilter').value = '';
            document.getElementById('contentTypeFilter').value = '';
            document.getElementById('statusFilter').value = 'draft';
            document.getElementById('searchInput').value = '';
            loadList(1);
        });
        document.getElementById('expiredDocs').addEventListener('click', () => {
            switchTab('knowledge');
            document.getElementById('serviceFilter').value = '';
            document.getElementById('contentTypeFilter').value = '';
            document.getElementById('statusFilter').value = 'expired';
            document.getElementById('searchInput').value = '';
            loadList(1);
        });
    }

    // Event listeners (using event delegation for dynamic elements inside #editorView)
    document.getElementById('newDocumentBtn').addEventListener('click', showCreateDocumentModal);
    document.getElementById('newServiceBtn').addEventListener('click', showServiceModal);
    document.getElementById('createOverrideBtn').addEventListener('click', () => showOverrideModal(null));
    // Bulk import button removed – no event listener
    document.getElementById('refreshStats').addEventListener('click', () => {
        loadStats();
        refreshTree();
        loadList(1);
    });

    function attachWipeMenuListeners() {
        const wipeMenu = document.getElementById('wipeMenu');
        if (wipeMenu) {
            const items = wipeMenu.querySelectorAll('a');
            items.forEach(a => {
                a.removeEventListener('click', wipeHandler);
                a.addEventListener('click', wipeHandler);
            });
        }
    }

    function wipeHandler(e) {
        e.preventDefault();
        const scope = this.dataset.scope;
        if (!ragOnline()) {
            alert('RAG offline – wipe unavailable');
            return;
        }
        showWipeModal(scope);
    }

    document.getElementById('serviceFilter').addEventListener('change', () => {
        if (currentTab === 'knowledge') loadList(1);
    });
    document.getElementById('contentTypeFilter').addEventListener('change', () => {
        if (currentTab === 'knowledge') loadList(1);
    });
    document.getElementById('statusFilter').addEventListener('change', () => {
        if (currentTab === 'knowledge') loadList(1);
    });
    document.getElementById('searchInput').addEventListener('input', debounce(() => {
        if (currentTab === 'knowledge') loadList(1);
    }, 500));
    document.getElementById('exportBtn').addEventListener('click', exportFiltered);

    document.getElementById('expandAll').addEventListener('click', expandAll);
    document.getElementById('collapseAll').addEventListener('click', collapseAll);

    document.getElementById('selectAllCheckbox').addEventListener('change', toggleSelectAll);
    document.getElementById('selectAllBtn').addEventListener('click', () => {
        document.getElementById('selectAllCheckbox').click();
    });
    document.getElementById('bulkActionsBtn').addEventListener('click', showBulkActions);
    document.getElementById('prevPageDoc').addEventListener('click', () => changePage(currentPage - 1));
    document.getElementById('nextPageDoc').addEventListener('click', () => changePage(currentPage + 1));

    // Event delegation for editor view buttons
    editorView.addEventListener('click', (e) => {
        const target = e.target;
        if (target.id === 'editBtn') {
            enterEditMode();
        } else if (target.id === 'saveBtn') {
            saveDocument();
        } else if (target.id === 'undoBtn') {
            undo();
        } else if (target.id === 'redoBtn') {
            redo();
        } else if (target.id === 'moreBtn') {
            toggleMoreMenu();
        } else if (target.id === 'newVersionLink') {
            e.preventDefault();
            showNewVersionModal(currentDocId);
        } else if (target.id === 'historyLink') {
            e.preventDefault();
            showHistoryModal(currentDocId);
        } else if (target.id === 'downloadLink') {
            e.preventDefault();
            downloadDocument(currentDocId);
        } else if (target.id === 'assignLink') {
            e.preventDefault();
            showAssignModal(currentDocId);
        } else if (target.id === 'requestApprovalLink') {
            e.preventDefault();
            requestApproval(currentDocId);
        } else if (target.id === 'lockToggleLink') {
            e.preventDefault();
            toggleLock(currentDocId);
        } else if (target.id === 'backToListBtn') {
            listView.style.display = 'block';
            editorView.style.display = 'none';
            if (rightPanel) rightPanel.style.display = 'none';
            loadList(currentPage);
        } else if (target.id === 'createOverrideForDocBtn') {
            if (currentDocData) {
                showOverrideModal(null);
                setTimeout(() => {
                    const targetType = document.querySelector('[name="target_type"]');
                    const targetValue = document.querySelector('[name="target_value"]');
                    if (targetType) targetType.value = 'document_id';
                    if (targetValue) targetValue.value = currentDocData.document_id;
                }, 100);
            }
        }
    });

    document.getElementById('autoFixBtn').addEventListener('click', autoFixMetadata);
    document.getElementById('ingestBtn').addEventListener('click', ingestDocument);

    document.getElementById('refreshAnalytics').addEventListener('click', loadAnalyticsStrip);
    document.getElementById('refreshExpired').addEventListener('click', loadExpiredMonitor);
    document.getElementById('refreshLedger').addEventListener('click', () => loadDecisionLedger(1));
    document.getElementById('refreshConflict').addEventListener('click', loadConflictQueue);
    
    document.querySelectorAll('[data-analytics-tab]').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('[data-analytics-tab]').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            loadAnalyticsSubTab(this.dataset.analyticsTab);
        });
    });

    document.getElementById('ragStatus').addEventListener('click', showRagHealthDetails);

    window.addEventListener('click', (e) => {
        if (!e.target.matches('#moreBtn')) {
            const moreDropdown = document.getElementById('moreDropdown');
            if (moreDropdown) moreDropdown.style.display = 'none';
        }
    });

    // API calls
    function loadStats() {
        fetch('/documents/api/list?page=1&per_page=1')
            .then(res => res.json())
            .then(data => document.getElementById('totalDocs').textContent = data.total);
        fetch('/documents/api/list?status=draft&per_page=1')
            .then(res => res.json())
            .then(data => document.getElementById('pendingDocs').textContent = data.total);
        fetch('/documents/api/list?status=expired&per_page=1')
            .then(res => res.json())
            .then(data => document.getElementById('expiredDocs').textContent = data.total)
            .catch(() => document.getElementById('expiredDocs').textContent = '0');
    }

    function refreshTree() {
        fetch('/documents/api/tree')
            .then(res => res.json())
            .then(data => renderTree(data))
            .catch(() => treeEl.innerHTML = '<li class="error">Unable to refresh knowledge tree.</li>');
    }

    function loadList(page = 1) {
        const params = new URLSearchParams({
            page, per_page: 50,
            service: document.getElementById('serviceFilter').value,
            content_type: document.getElementById('contentTypeFilter').value,
            status: document.getElementById('statusFilter').value,
            search: document.getElementById('searchInput').value
        });
        fetch('/documents/api/list?' + params)
            .then(res => res.json())
            .then(data => {
                renderList(data);
                currentPage = data.page;
                totalPages = data.pages;
                document.getElementById('pageInfoDoc').textContent = `Page ${currentPage} of ${totalPages}`;
                document.getElementById('prevPageDoc').disabled = currentPage <= 1;
                document.getElementById('nextPageDoc').disabled = currentPage >= totalPages;
            })
            .catch(() => document.getElementById('docTableBody').innerHTML = '<tr><td colspan="10">Failed to load documents.');
    }

    function loadDocument(id) {
        fetch('/documents/api/document/' + id)
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const contentType = res.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    return res.text().then(text => { throw new Error('Response is not JSON'); });
                }
                return res.json();
            })
            .then(data => {
                if (isEditMode) exitEditMode();
                currentDocId = id;
                currentDocData = data;
                originalContent = data.content;
                historyStack = [data.content];
                historyIndex = 0;
                showEditorView(data);
                validateDocument(data);
                highlightTreeNode(id);
                if (rightPanel) rightPanel.style.display = 'block';
                if (treePanel && !treePanel.classList.contains('collapsed')) toggleTreeBtn.click();
            })
            .catch(err => {
                console.error('Error loading document:', err);
                alert('Could not load document. Check console for details.');
            });
    }

    // Validation
    function validateDocument(docData) {
        fetch('/documents/api/validate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(docData) })
        .then(res => res.json())
        .then(result => {
            validationList.innerHTML = '';
            if (result.valid) {
                validationList.innerHTML = '<li class="check-pass"><i class="fas fa-check-circle"></i> All validation checks passed</li>';
                ingestBtn.disabled = false;
                const overlapDiv = document.getElementById('overlap-resolution');
                if (overlapDiv) overlapDiv.remove();
            } else {
                const progress = Math.max(0, 100 - (result.errors.length * 10));
                validationList.innerHTML = `<div class="validation-progress"><div class="progress-bar" style="width:${progress}%; background:#3498db; height:8px; border-radius:4px;"></div><span>${result.errors.length} issue(s)</span></div>`;
                const summary = document.createElement('div');
                summary.className = 'validation-summary';
                summary.innerHTML = `<i class="fas fa-exclamation-triangle"></i> <strong>${result.errors.length} issue(s) found</strong> <span style="float:right;">▼</span>`;
                const details = document.createElement('ul');
                details.className = 'validation-details';
                details.style.display = 'none';
                result.errors.forEach(err => {
                    const li = document.createElement('li');
                    li.className = 'check-fail';
                    li.innerHTML = `<i class="fas fa-times-circle"></i> ${err}`;
                    details.appendChild(li);
                });
                summary.addEventListener('click', () => {
                    const isHidden = details.style.display === 'none';
                    details.style.display = isHidden ? 'block' : 'none';
                    summary.querySelector('span:last-child').textContent = isHidden ? '▲' : '▼';
                });
                validationList.appendChild(summary);
                validationList.appendChild(details);
                ingestBtn.disabled = true;
                if (result.overlap_detected && result.overlap_with) showOverlapResolution(result.overlap_with);
            }
        })
        .catch(() => { validationList.innerHTML = '<li class="check-fail">Validation service unavailable</li>'; ingestBtn.disabled = true; });
    }

    function showOverlapResolution(conflictingId) {
        const existing = document.getElementById('overlap-resolution');
        if (existing) existing.remove();

        const div = document.createElement('div');
        div.id = 'overlap-resolution';
        div.style.marginTop = '1rem';
        div.style.padding = '1rem';
        div.style.background = '#fff3cd';
        div.style.border = '1px solid #ffeeba';
        div.style.borderRadius = '4px';
        div.innerHTML = `
            <p><strong><i class="fas fa-exclamation-triangle"></i> Overlap detected</strong> with document <code>${conflictingId}</code>. Choose action:</p>
            <button id="retireOldBtn" class="btn btn-warning">Retire Old Document</button>
            <button id="overrideOverlapBtn" class="btn btn-danger">Override with Justification</button>
            <div id="overrideJustification" style="display:none; margin-top:0.5rem;">
                <label>Justification (min 20 chars):</label>
                <textarea id="justificationText" rows="2" style="width:100%;"></textarea>
                <button id="confirmOverrideBtn" class="btn btn-primary" style="margin-top:0.5rem;">Confirm Override</button>
            </div>
        `;
        document.getElementById('rightPanel').appendChild(div);

        document.getElementById('retireOldBtn').addEventListener('click', () => {
            fetch('/documents/api/overlap/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_id: currentDocId, action: 'retire', conflicting_id: conflictingId })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('Old document retired and new document ingested.');
                    loadDocument(currentDocId);
                    refreshTree();
                    loadList(currentPage);
                } else {
                    alert('Failed: ' + (data.error || 'unknown'));
                }
            });
        });

        document.getElementById('overrideOverlapBtn').addEventListener('click', () => {
            document.getElementById('overrideJustification').style.display = 'block';
        });

        document.getElementById('confirmOverrideBtn').addEventListener('click', () => {
            const justification = document.getElementById('justificationText').value;
            if (justification.length < 20) {
                alert('Justification must be at least 20 characters.');
                return;
            }
            fetch('/documents/api/overlap/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_id: currentDocId, action: 'override', justification })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('Override accepted and document ingested.');
                    loadDocument(currentDocId);
                    refreshTree();
                    loadList(currentPage);
                } else {
                    alert('Failed: ' + (data.error || 'unknown'));
                }
            });
        });
    }

    // Rendering
    function renderTree(data) {
        treeEl.innerHTML = '';
        const serviceLi = document.createElement('li');
        const serviceCount = Object.keys(data.by_service).length;
        serviceLi.innerHTML = `<div class="tree-folder" data-path="by_service"><span class="expand-icon">▶</span> <i class="fas fa-folder"></i> by_service/ <span class="badge">${serviceCount} services</span></div>`;
        const serviceUl = document.createElement('ul');
        serviceUl.style.display = 'none';
        serviceLi.appendChild(serviceUl);
        treeEl.appendChild(serviceLi);

        if (serviceCount === 0) {
            const emptyLi = document.createElement('li');
            emptyLi.className = 'empty-message';
            emptyLi.style.padding = '0.5rem 1rem';
            emptyLi.style.color = '#999';
            emptyLi.style.fontStyle = 'italic';
            emptyLi.textContent = 'No services created yet.';
            serviceUl.appendChild(emptyLi);
        } else {
            for (const [service, cts] of Object.entries(data.by_service)) {
                const serviceFolder = document.createElement('li');
                const totalDocs = Object.values(cts).reduce((acc, ct) => acc + ct.count, 0);
                const standardTypes = ['procedure', 'policy', 'fee_schedule', 'faq', 'emergency', 'contact_directory'];
                const presentTypes = Object.keys(cts);
                const completeness = `${presentTypes.length}/${standardTypes.length}`;
                const missingTypes = standardTypes.filter(t => !presentTypes.includes(t));
                serviceFolder.innerHTML = `<div class="tree-folder" data-path="by_service/${service}"><span class="expand-icon">▶</span> <i class="fas fa-folder"></i> ${service}/ <span class="badge">${totalDocs} docs</span> <span class="completeness-badge" title="Missing: ${missingTypes.join(', ')}">${completeness}</span><span class="add-icon" title="Add content types"><i class="fas fa-plus-circle"></i></span></div>`;
                const ctUl = document.createElement('ul');
                ctUl.style.display = 'none';
                for (const [ct, ctData] of Object.entries(cts)) {
                    const ctLi = document.createElement('li');
                    ctLi.innerHTML = `<div class="tree-folder" data-path="by_service/${service}/${ct}"><span class="expand-icon">▶</span> <i class="fas fa-folder"></i> ${ct}/ <span class="badge">${ctData.count} docs</span></div>`;
                    const docUl = document.createElement('ul');
                    docUl.style.display = 'none';
                    ctData.documents.forEach(doc => {
                        const docLi = document.createElement('li');
                        docLi.className = 'tree-file';
                        docLi.dataset.id = doc.id;
                        docLi.dataset.path = `by_service/${service}/${ct}/${doc.document_id}`;
                        docLi.dataset.archived = doc.status === 'archived' ? 'true' : 'false';
                        docLi.dataset.locked = doc.locked ? 'true' : 'false';
                        let crossIcon = doc.cross_service_flag ? '<i class="fas fa-globe"></i>' : '';
                        docLi.innerHTML = `<i class="fas fa-file-alt"></i> ${doc.title} v${doc.version} ${doc.locked ? '<i class="fas fa-lock"></i>' : ''} ${crossIcon}`;
                        docLi.addEventListener('click', (e) => { e.stopPropagation(); loadDocument(doc.id); });
                        docUl.appendChild(docLi);
                    });
                    ctLi.appendChild(docUl);
                    ctUl.appendChild(ctLi);
                }
                serviceFolder.appendChild(ctUl);
                serviceUl.appendChild(serviceFolder);
            }
        }

        const archivedLi = document.createElement('li');
        archivedLi.innerHTML = `<div class="tree-folder" data-path="archived"><span class="expand-icon">▶</span> <i class="fas fa-archive"></i> archived/ <span class="badge">${data.archived.count} docs</span></div>`;
        const archivedUl = document.createElement('ul');
        archivedUl.style.display = 'none';
        data.archived.documents.forEach(doc => {
            const docLi = document.createElement('li');
            docLi.className = 'tree-file';
            docLi.dataset.id = doc.id;
            docLi.dataset.path = `archived/${doc.document_id}`;
            docLi.dataset.archived = 'true';
            docLi.innerHTML = `<i class="fas fa-file-archive"></i> ${doc.title} v${doc.version} (archived)`;
            docLi.addEventListener('click', (e) => { e.stopPropagation(); loadDocument(doc.id); });
            archivedUl.appendChild(docLi);
        });
        archivedLi.appendChild(archivedUl);
        treeEl.appendChild(archivedLi);

        document.querySelectorAll('.tree-folder').forEach(folder => {
            folder.addEventListener('click', function(e) {
                if (e.target.classList.contains('add-icon') || e.target.closest('.add-icon')) return;
                const ul = this.nextElementSibling;
                const expandIcon = this.querySelector('.expand-icon');
                if (ul.style.display === 'none') {
                    ul.style.display = 'block';
                    expandIcon.textContent = '▼';
                } else {
                    ul.style.display = 'none';
                    expandIcon.textContent = '▶';
                }
            });
        });

        document.querySelectorAll('.tree-folder .add-icon').forEach(icon => {
            icon.addEventListener('click', function(e) {
                e.stopPropagation();
                const path = this.closest('.tree-folder').dataset.path;
                showAddContentTypesModal(path.split('/')[1]);
            });
        });

        enableContextMenu();
    }

    function highlightTreeNode(docId) {
        document.querySelectorAll('.tree-file.selected').forEach(el => el.classList.remove('selected'));
        const node = document.querySelector(`.tree-file[data-id="${docId}"]`);
        if (!node) return;
        node.classList.add('selected');
        let parent = node.closest('ul');
        while (parent) {
            const folderDiv = parent.previousElementSibling;
            if (folderDiv && folderDiv.classList.contains('tree-folder')) {
                const expandIcon = folderDiv.querySelector('.expand-icon');
                if (expandIcon && expandIcon.textContent === '▶') {
                    expandIcon.textContent = '▼';
                    if (parent.style.display !== 'block') parent.style.display = 'block';
                }
            }
            parent = parent.parentElement?.closest('ul');
        }
    }

    // Column picker
    function initColumnPicker() {
        const container = document.getElementById('columnPickerContainer');
        if (!container) return;
        const columns = [
            { key: 'title', label: 'Title' },
            { key: 'service', label: 'Service' },
            { key: 'content_type', label: 'Content Type' },
            { key: 'status', label: 'Status' },
            { key: 'document_id', label: 'Document ID' },
            { key: 'version', label: 'Version' },
            { key: 'uploaded_at', label: 'Last Modified' },
            { key: 'tags', label: 'Tags' },
            { key: 'actions', label: 'Actions' }
        ];
        const saved = localStorage.getItem('docTableColumns');
        let visibility = saved ? JSON.parse(saved) : {
            title: true, service: true, content_type: true, status: true,
            document_id: false, version: false, uploaded_at: false, tags: false, actions: true
        };
        function applyVisibility() {
            for (let col of columns) {
                const cells = document.querySelectorAll(`#docTable th.${col.key}, #docTable td.${col.key}`);
                cells.forEach(cell => cell.style.display = visibility[col.key] ? '' : 'none');
            }
            localStorage.setItem('docTableColumns', JSON.stringify(visibility));
        }
        applyVisibility();
        
        const pickerHtml = `
            <div class="dropdown" style="display:inline-block; margin-left:10px;">
                <button class="btn btn-secondary btn-small" id="columnPickerBtn"><i class="fas fa-columns"></i> Columns</button>
                <div id="columnPickerDropdown" style="display:none; position:absolute; background:white; border:1px solid #ccc; padding:10px; z-index:100; min-width:150px;">
                    ${columns.map(col => `<label><input type="checkbox" data-col="${col.key}" ${visibility[col.key] ? 'checked' : ''}> ${col.label}</label><br>`).join('')}
                    <hr><button id="resetColumnsBtn" class="btn btn-small">Reset to Default</button>
                </div>
            </div>
        `;
        container.innerHTML = pickerHtml;
        const btn = document.getElementById('columnPickerBtn');
        const dropdown = document.getElementById('columnPickerDropdown');
        btn.addEventListener('click', () => dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none');
        document.querySelectorAll('#columnPickerDropdown input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', (e) => {
                visibility[e.target.dataset.col] = e.target.checked;
                applyVisibility();
            });
        });
        document.getElementById('resetColumnsBtn').addEventListener('click', () => {
            visibility = { title: true, service: true, content_type: true, status: true, document_id: false, version: false, uploaded_at: false, tags: false, actions: true };
            document.querySelectorAll('#columnPickerDropdown input').forEach(cb => cb.checked = visibility[cb.dataset.col]);
            applyVisibility();
        });
    }

    function renderList(data) {
        const tbody = document.getElementById('docTableBody');
        tbody.innerHTML = '';
        data.items.forEach(doc => {
            const row = tbody.insertRow();
            row.dataset.id = doc.id;
            const cbCell = row.insertCell();
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = selectedDocs.has(doc.id);
            cb.addEventListener('change', (e) => {
                if (e.target.checked) selectedDocs.add(doc.id);
                else selectedDocs.delete(doc.id);
            });
            cbCell.appendChild(cb);
            
            const titleCell = row.insertCell(); titleCell.textContent = doc.title; titleCell.className = 'title';
            const serviceCell = row.insertCell(); serviceCell.textContent = doc.service; serviceCell.className = 'service';
            const contentTypeCell = row.insertCell(); contentTypeCell.textContent = doc.content_type; contentTypeCell.className = 'content_type';
            const statusCell = row.insertCell(); statusCell.textContent = doc.status + (doc.locked ? ' <i class="fas fa-lock"></i>' : ''); statusCell.className = 'status';
            const docIdCell = row.insertCell(); docIdCell.textContent = doc.document_id; docIdCell.className = 'document_id';
            const versionCell = row.insertCell(); versionCell.textContent = doc.version; versionCell.className = 'version';
            const dateCell = row.insertCell(); dateCell.textContent = doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : ''; dateCell.className = 'uploaded_at';
            const tagsCell = row.insertCell(); tagsCell.className = 'tags';
            if (doc.topic_tags && doc.topic_tags.length) {
                tagsCell.innerHTML = doc.topic_tags.map(t => `<span class="badge">${t}</span>`).join(' ');
            } else {
                tagsCell.textContent = '-';
            }
            const actionsCell = row.insertCell(); actionsCell.className = 'actions';
            const viewBtn = document.createElement('button');
            viewBtn.textContent = 'View';
            viewBtn.className = 'btn btn-small';
            viewBtn.addEventListener('click', (e) => { e.stopPropagation(); loadDocument(doc.id); });
            actionsCell.appendChild(viewBtn);
            row.addEventListener('click', (e) => {
                if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'BUTTON') {
                    loadDocument(doc.id);
                }
            });
        });
        initColumnPicker();
    }

    // ========== FIXED: showEditorView now clears previous content ==========
    function showEditorView(doc) {
        if (isEditMode) return;
        // Clear editorView before rendering new content
        editorView.innerHTML = '';
        listView.style.display = 'none';
        editorView.style.display = 'block';
        
        const contentHtml = `<pre>${escapeHtml(doc.content)}</pre>`;
        
        let authorityHtml = `<div class="meta-field"><label>Authority Tier (derived):</label> ${doc.derived_tier}</div>`;
        if (doc.authority_override) {
            authorityHtml += `<div class="meta-field override-active"><label><i class="fas fa-exclamation-triangle"></i> Override Active:</label> ${doc.authority_override.tier}<br><small>Justification: ${doc.authority_override.justification}</small></div>`;
        }
        if (doc.can_edit && window.currentUser?.can_manage_knowledge) {
            authorityHtml += `<button id="authorityOverrideBtn" class="btn btn-small btn-warning">Set Authority Tier</button>`;
        }

        const metaHtml = `
            <div class="meta-collapsible">
                <button class="meta-toggle" id="metaToggleBtn"><i class="fas fa-chevron-down"></i> Hide Metadata</button>
                <div id="metadataContent" style="display: block;">
                    <div class="meta-field"><label>Document ID:</label> ${doc.document_id}</div>
                    <div class="meta-field"><label>Version:</label> ${doc.version}</div>
                    <div class="meta-field"><label>Service Area:</label> ${doc.service}</div>
                    <div class="meta-field"><label>Content Type:</label> ${doc.content_type}</div>
                    <div class="meta-field"><label>Department:</label> ${doc.department || '-'}</div>
                    <div class="meta-field"><label>Owner:</label> ${doc.owner_email || '-'}</div>
                    <div class="meta-field"><label>Valid From:</label> ${doc.valid_from || '-'}</div>
                    <div class="meta-field"><label>Valid To:</label> ${doc.valid_to || '-'}</div>
                    <div class="meta-field"><label>Locations:</label> ${doc.locations ? doc.locations.join(', ') : '-'}</div>
                    <div class="meta-field"><label>Topic Tags:</label> ${doc.topic_tags ? doc.topic_tags.join(', ') : '-'}</div>
                    <div class="meta-field"><label>Review Cycle:</label> ${doc.review_cycle || '-'}</div>
                    <div class="meta-field"><label>Cross‑Service:</label> ${doc.cross_service_flag ? '<i class="fas fa-check-circle"></i> Yes' : '<i class="fas fa-times-circle"></i> No'}</div>
                    <div class="meta-field"><label>Prerequisites:</label> ${doc.prerequisites ? doc.prerequisites.join(', ') : '-'}</div>
                    <div class="meta-field"><label>Related Documents:</label> ${doc.related_documents ? doc.related_documents.join(', ') : '-'}</div>
                    ${authorityHtml}
                    <div class="meta-field"><label>Status:</label> ${doc.status} ${doc.locked ? '<i class="fas fa-lock"></i>' : ''}</div>
                </div>
            </div>
            <div id="activeOverridesList"></div>
        `;

        editorView.innerHTML = `
            <div class="editor-header">
                <button id="backToListBtn" class="btn-back"><i class="fas fa-arrow-left"></i> Back to List</button>
                <div class="editor-toolbar">
                    <button id="editBtn" class="btn-primary"><i class="fas fa-edit"></i> Edit</button>
                    <button id="saveBtn" class="btn-primary" disabled><i class="fas fa-save"></i> Save</button>
                    <button id="undoBtn" class="btn-secondary" disabled><i class="fas fa-undo-alt"></i> Undo</button>
                    <button id="redoBtn" class="btn-secondary" disabled><i class="fas fa-redo-alt"></i> Redo</button>
                    <button id="moreBtn" class="btn-secondary">···</button>
                    <button id="createOverrideForDocBtn" class="btn-secondary"><i class="fas fa-plus"></i> Create Override for this Document</button>
                    <div id="moreDropdown" style="display:none; position:absolute; background:white; border:1px solid #ccc;">
                        <a href="#" id="newVersionLink"><i class="fas fa-code-branch"></i> New Version</a>
                        <a href="#" id="historyLink"><i class="fas fa-history"></i> History</a>
                        <a href="#" id="downloadLink"><i class="fas fa-download"></i> Download</a>
                        <a href="#" id="assignLink"><i class="fas fa-user-plus"></i> Assign</a>
                        <a href="#" id="requestApprovalLink"><i class="fas fa-check-circle"></i> Request Approval</a>
                        <a href="#" id="lockToggleLink"><i class="fas fa-lock"></i> Lock/Unlock</a>
                    </div>
                </div>
            </div>
            <div class="document-meta" id="documentMeta">${metaHtml}</div>
            <div class="document-content" id="documentContent">${contentHtml}</div>
        `;

        const toggleBtn = document.getElementById('metaToggleBtn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                const content = document.getElementById('metadataContent');
                if (content.style.display === 'none') {
                    content.style.display = 'block';
                    toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i> Hide Metadata';
                } else {
                    content.style.display = 'none';
                    toggleBtn.innerHTML = '<i class="fas fa-chevron-right"></i> Show Metadata';
                }
            });
        }
        
        displayActiveOverrides(doc.document_id);

        const overrideBtn = document.getElementById('authorityOverrideBtn');
        if (overrideBtn) {
            overrideBtn.addEventListener('click', () => showAuthorityOverrideModal(doc));
        }

        document.getElementById('ingestBtn')?.setAttribute('data-requires-rag', '');
        document.getElementById('autoFixBtn')?.setAttribute('data-requires-rag', '');
        setRagButtonsEnabled(ragOnline());
    }

    function showAuthorityOverrideModal(doc) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'block';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header"><h3>Set Authority Tier</h3><button class="close-btn">&times;</button></div>
                <div class="modal-body">
                    <p>Current derived tier: <strong>${doc.derived_tier}</strong></p>
                    <p>Override only in exceptional circumstances. Provide justification.</p>
                    <select id="overrideTier" class="form-control">
                        <option value="">Select new tier</option>
                        <option value="STATUTORY">STATUTORY</option>
                        <option value="POLICY">POLICY</option>
                        <option value="NOTICE">NOTICE</option>
                        <option value="INFORMATIONAL">INFORMATIONAL</option>
                    </select>
                    <textarea id="overrideJustification" class="form-control" rows="3" placeholder="Justification (min 20 characters)"></textarea>
                    <p><small>This action will be logged in the audit ledger.</small></p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" id="cancelOverride">Cancel</button>
                    <button class="btn btn-warning" id="saveOverride">Save Override</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.querySelector('.close-btn').addEventListener('click', () => modal.remove());
        document.getElementById('cancelOverride').addEventListener('click', () => modal.remove());
        document.getElementById('saveOverride').addEventListener('click', () => {
            const tier = document.getElementById('overrideTier').value;
            const justification = document.getElementById('overrideJustification').value;
            if (!tier) { alert('Please select a tier.'); return; }
            if (justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
            fetch(`/documents/api/document/${doc.id}/authority-override`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tier, justification })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) { alert('Authority override saved.'); modal.remove(); loadDocument(doc.id); }
                else { alert('Error: ' + (data.error || 'unknown')); }
            })
            .catch(err => alert('Network error: ' + err.message));
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ========== EDIT MODE FUNCTIONS (FIXED) ==========
    function collapseKnowledgeTree() {
        if (treePanel && !treePanel.classList.contains('collapsed')) toggleTreeBtn.click();
    }

    function buildEditLayout(doc) {
        let metaHtml = `
            <div class="meta-field"><label>Document ID:</label> <span class="value">${doc.document_id}</span></div>
            <div class="meta-field"><label>Version:</label> <span class="value">${doc.version}</span></div>
            <div class="meta-field"><label>Service Area:</label> <span class="value">${doc.service}</span></div>
            <div class="meta-field"><label>Content Type:</label> <span class="value">${doc.content_type}</span></div>
            <div class="meta-field"><label>Department:</label> <span class="value">${doc.department || '-'}</span></div>
            <div class="meta-field"><label>Owner:</label> <span class="value">${doc.owner_email || '-'}</span></div>
            <div class="meta-field"><label>Valid From:</label> <span class="value">${doc.valid_from || '-'}</span></div>
            <div class="meta-field"><label>Valid To:</label> <span class="value">${doc.valid_to || '-'}</span></div>
            <div class="meta-field"><label>Locations:</label> <span class="value">${doc.locations ? doc.locations.join(', ') : '-'}</span></div>
            <div class="meta-field"><label>Topic Tags:</label> <span class="value">${doc.topic_tags ? doc.topic_tags.join(', ') : '-'}</span></div>
            <div class="meta-field"><label>Review Cycle:</label> <span class="value">${doc.review_cycle || '-'}</span></div>
            <div class="meta-field"><label>Cross‑Service:</label> <span class="value">${doc.cross_service_flag ? '<i class="fas fa-check-circle"></i> Yes' : '<i class="fas fa-times-circle"></i> No'}</span></div>
            <div class="meta-field"><label>Prerequisites:</label> <span class="value">${doc.prerequisites ? doc.prerequisites.join(', ') : '-'}</span></div>
            <div class="meta-field"><label>Related Documents:</label> <span class="value">${doc.related_documents ? doc.related_documents.join(', ') : '-'}</span></div>
            <div class="meta-field"><label>Authority Tier:</label> <span class="value">${doc.derived_tier}</span></div>
            <div class="meta-field"><label>Status:</label> <span class="value">${doc.status}</span></div>
        `;
        if (doc.can_edit && window.currentUser?.can_manage_knowledge) {
            metaHtml += `<div><button id="authorityOverrideBtn" class="btn btn-small btn-warning override-btn">Set Authority Tier</button></div>`;
        }

        const validationClone = validationList.cloneNode(true);
        const autoFixClone = autoFixBtn.cloneNode(true);
        const ingestClone = ingestBtn.cloneNode(true);
        const overrideRiskClone = overrideRisk.cloneNode(true);

        const metaPanel = document.getElementById('editMetadataPanel');
        const valPanel = document.getElementById('editValidationPanel');
        if (metaPanel) metaPanel.innerHTML = metaHtml;
        if (valPanel) {
            valPanel.innerHTML = '';
            valPanel.appendChild(validationClone);
            valPanel.appendChild(autoFixClone);
            valPanel.appendChild(ingestClone);
            valPanel.appendChild(overrideRiskClone);
        }

        if (autoFixClone) autoFixClone.addEventListener('click', autoFixMetadata);
        if (ingestClone) ingestClone.addEventListener('click', ingestDocument);
        const overrideBtn = document.getElementById('authorityOverrideBtn');
        if (overrideBtn) overrideBtn.addEventListener('click', () => showAuthorityOverrideModal(doc));

        const editorDiv = document.getElementById('editDocumentContent');
        if (editorDiv) {
            editorDiv.innerHTML = `<textarea id="docEditor" style="width:100%; min-height:400px; font-family:monospace;">${escapeHtml(doc.content)}</textarea>`;
        }
    }

    function enterEditMode() {
        if (!currentDocData || !currentDocData.can_edit) return;
        collapseKnowledgeTree();
        if (rightPanel) rightPanel.style.display = 'none';
        editorView.innerHTML = '';
        const editLayout = editModeTemplate.cloneNode(true);
        editLayout.id = '';
        editLayout.style.display = 'block';
        editorView.appendChild(editLayout);
        buildEditLayout(currentDocData);
        
        // Setup collapsible header
        const collapsibleHeader = document.getElementById('editCollapseHeader');
        const metadataRow = document.getElementById('editMetadataValidationRow');
        if (collapsibleHeader && metadataRow) {
            collapsibleHeader.addEventListener('click', () => {
                const isVisible = metadataRow.style.display !== 'none';
                metadataRow.style.display = isVisible ? 'none' : 'flex';
                const icon = collapsibleHeader.querySelector('i');
                if (icon) {
                    icon.className = isVisible ? 'fas fa-chevron-right' : 'fas fa-chevron-down';
                }
            });
            // Default collapsed
            metadataRow.style.display = 'none';
            collapsibleHeader.querySelector('i').className = 'fas fa-chevron-right';
        }
        
        // Attach edit mode button listeners
        const backBtn = document.getElementById('editBackBtn');
        const saveBtn = document.getElementById('editSaveBtn');
        const undoBtn = document.getElementById('editUndoBtn');
        const redoBtn = document.getElementById('editRedoBtn');
        const cancelBtn = document.getElementById('editCancelBtn');
        
        if (backBtn) backBtn.onclick = () => exitEditMode();
        if (cancelBtn) cancelBtn.onclick = () => exitEditMode();
        if (saveBtn) saveBtn.onclick = () => saveDocument();
        if (undoBtn) undoBtn.onclick = () => undo();
        if (redoBtn) redoBtn.onclick = () => redo();
        
        const docEditor = document.getElementById('docEditor');
        if (docEditor) docEditor.focus();
        isEditMode = true;
    }

    // ========== FIXED: exitEditMode sets isEditMode false before showing editor ==========
    function exitEditMode() {
        if (rightPanel) rightPanel.style.display = 'block';
        const editLayout = editorView.querySelector('.edit-layout');
        if (editLayout) editLayout.remove();
        isEditMode = false;  // Must be BEFORE showEditorView
        showEditorView(currentDocData);
    }

    // ========== FIXED: saveDocument now reloads fresh data and refreshes UI ==========
    function saveDocument() {
        const docEditor = document.getElementById('docEditor');
        if (!docEditor) return;
        const newContent = docEditor.value;
        if (newContent === originalContent) {
            exitEditMode();
            return;
        }
        
        // Update history
        historyStack = historyStack.slice(0, historyIndex + 1);
        historyStack.push(newContent);
        historyIndex++;
        originalContent = newContent;
        
        const updatedData = { ...currentDocData, content: newContent };
        
        fetch('/documents/api/document/' + currentDocId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedData)
        })
        .then(res => {
            if (!res.ok) throw new Error('Server responded with ' + res.status);
            return res.json();
        })
        .then(data => {
            if (data.success) {
                // Reload the document from server to get fresh data
                return fetch('/documents/api/document/' + currentDocId);
            } else {
                throw new Error(data.error || 'Save failed');
            }
        })
        .then(res => {
            if (!res.ok) throw new Error('Failed to load updated document');
            return res.json();
        })
        .then(freshDocData => {
            // Update global state with fresh data
            currentDocData = freshDocData;
            originalContent = freshDocData.content;
            historyStack = [freshDocData.content];
            historyIndex = 0;
            
            // Exit edit mode (this will call showEditorView with updated currentDocData)
            exitEditMode();
            
            // Re-validate and refresh tree/list
            if (ragOnline()) validateDocument(freshDocData);
            refreshTree();
            loadList(currentPage);
        })
        .catch(err => {
            console.error('Save error:', err);
            alert('Save failed: ' + err.message);
            // Revert history changes
            historyStack = [originalContent];
            historyIndex = 0;
        });
    }

    function undo() {
        if (historyIndex > 0) {
            historyIndex--;
            const docEditor = document.getElementById('docEditor');
            if (docEditor) docEditor.value = historyStack[historyIndex];
        }
    }

    function redo() {
        if (historyIndex < historyStack.length - 1) {
            historyIndex++;
            const docEditor = document.getElementById('docEditor');
            if (docEditor) docEditor.value = historyStack[historyIndex];
        }
    }

    // ========== FIXED: ingestDocument now refreshes tree and list ==========
    function ingestDocument() {
        if (!ragOnline()) { alert('RAG is offline. Cannot ingest document.'); return; }
        if (!currentDocId) return;
        
        fetch('/documents/api/document/' + currentDocId + '/ingest', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('Document ingested successfully');
                    loadDocument(currentDocId);
                    refreshTree();
                    loadStats();
                } else {
                    alert('Ingestion failed: ' + (data.error || 'unknown'));
                }
            });
    }

    function toggleLock(docId) {
        if (!docId) return;
        fetch('/documents/api/document/' + docId + '/lock', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.locked !== undefined) {
                    if (currentDocId == docId) {
                        currentDocData.locked = data.locked;
                        showEditorView(currentDocData);
                    }
                    refreshTree();
                }
            });
    }

    function showNewVersionModal(docId) {
        if (!ragOnline()) { alert('RAG offline – cannot create new version'); return; }
        const modal = document.getElementById('versionModal');
        if (!modal) return;
        document.getElementById('versionDocId').value = docId;
        document.getElementById('versionValidFrom').value = new Date().toISOString().split('T')[0];
        modal.style.display = 'block';
        document.getElementById('cancelVersion').onclick = () => modal.style.display = 'none';
        document.getElementById('createVersion').onclick = () => {
            const data = {
                valid_from: document.getElementById('versionValidFrom').value,
                valid_to: document.getElementById('versionValidTo').value || null
            };
            fetch('/documents/api/document/' + docId + '/new-version', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(res => {
                if (res.success) { alert('New version created'); modal.style.display = 'none'; loadDocument(docId); refreshTree(); }
                else { alert('Error creating version'); }
            });
        };
    }

    function showHistoryModal(docId) {
        const modal = document.getElementById('historyModal');
        if (!modal) return;
        const tbody = document.getElementById('historyBody');
        fetch('/documents/api/document/' + docId + '/versions')
            .then(res => res.json())
            .then(versions => {
                tbody.innerHTML = '';
                versions.forEach(v => {
                    const row = tbody.insertRow();
                    row.insertCell().textContent = v.version;
                    row.insertCell().textContent = new Date(v.created_at).toLocaleString();
                    row.insertCell().textContent = v.created_by || 'System';
                    row.insertCell().textContent = v.reason || 'Edit';
                    const compareCell = row.insertCell();
                    const radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.name = 'compareVersion';
                    radio.value = v.id;
                    compareCell.appendChild(radio);
                });
                const compareBtn = document.getElementById('compareVersionsBtn');
                if (!compareBtn) {
                    const btn = document.createElement('button');
                    btn.id = 'compareVersionsBtn';
                    btn.textContent = 'Compare Selected';
                    btn.className = 'btn btn-primary';
                    btn.addEventListener('click', () => {
                        const selected = document.querySelectorAll('input[name="compareVersion"]:checked');
                        if (selected.length !== 2) { alert('Please select exactly two versions to compare.'); return; }
                        showVersionDiff(selected[0].value, selected[1].value);
                    });
                    modal.querySelector('.modal-footer').prepend(btn);
                }
                modal.style.display = 'block';
            });
        document.getElementById('closeHistory').onclick = () => modal.style.display = 'none';
    }

    function showVersionDiff(v1Id, v2Id) {
        fetch(`/documents/api/version-diff?v1=${v1Id}&v2=${v2Id}`)
            .then(res => res.json())
            .then(data => {
                let modal = document.getElementById('versionDiffModal');
                if (!modal) {
                    const newModal = document.createElement('div');
                    newModal.id = 'versionDiffModal';
                    newModal.className = 'modal';
                    newModal.style.display = 'block';
                    newModal.innerHTML = `
                        <div class="modal-content" style="max-width: 900px;">
                            <div class="modal-header"><h3><i class="fas fa-code-branch"></i> Version Comparison</h3><button class="close-btn">&times;</button></div>
                            <div class="modal-body" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                                <div><h4>Version <span id="diffVersion1"></span></h4><pre id="diffContent1" style="background: #f5f5f5; padding: 1rem; overflow: auto; max-height: 400px;"></pre></div>
                                <div><h4>Version <span id="diffVersion2"></span></h4><pre id="diffContent2" style="background: #f5f5f5; padding: 1rem; overflow: auto; max-height: 400px;"></pre></div>
                            </div>
                            <div class="modal-footer"><button class="btn btn-secondary close-btn">Close</button></div>
                        </div>
                    `;
                    document.body.appendChild(newModal);
                    newModal.querySelector('.close-btn').addEventListener('click', () => newModal.remove());
                    modal = newModal;
                }
                document.getElementById('diffVersion1').textContent = data.v1.version;
                document.getElementById('diffVersion2').textContent = data.v2.version;
                document.getElementById('diffContent1').textContent = data.v1.content;
                document.getElementById('diffContent2').textContent = data.v2.content;
                modal.style.display = 'block';
            });
    }

    function downloadDocument(docId) {
        fetch('/documents/api/document/' + docId)
            .then(res => res.json())
            .then(doc => {
                const blob = new Blob([doc.content], {type: 'text/plain'});
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = doc.document_id + '.txt';
                a.click();
                window.URL.revokeObjectURL(url);
            });
    }

    function showAssignModal(docId) {
        const assignee = prompt('Enter username or team to assign:');
        if (!assignee) return;
        const message = prompt('Optional message:');
        fetch('/documents/api/document/' + docId + '/assign', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({assignee, message})
        })
        .then(res => res.json())
        .then(data => { if (data.success) alert('Assigned'); });
    }

    function requestApproval(docId) {
        fetch('/documents/api/document/' + docId + '/request-approval', {method: 'POST'})
            .then(res => res.json())
            .then(data => {
                if (data.success) { alert('Approval requested'); loadDocument(docId); }
            });
    }

    function autoFixMetadata() {
        if (!ragOnline()) { alert('RAG offline – auto‑fix unavailable'); return; }
        if (!currentDocData) return;
        fetch('/documents/api/auto-fix-metadata', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(currentDocData)
        })
        .then(res => res.json())
        .then(result => {
            if (result.fixed) {
                currentDocData = {...currentDocData, ...result.fixed};
                showEditorView(currentDocData);
                if (ragOnline()) validateDocument(currentDocData);
                alert('Metadata auto‑fixed. Changes: ' + (result.changes || []).join(', '));
            }
        });
    }

    // ========== Wipe Modal ==========
    function showWipeModal(scope) {
        if (!ragOnline()) { alert('RAG offline – wipe unavailable'); return; }
        
        let modal = document.getElementById('wipeModal');
        if (!modal) {
            const modalHtml = `
                <div id="wipeModal" class="modal" style="display:none;">
                    <div class="modal-content" style="max-width: 500px;">
                        <div class="modal-header"><h3 style="color:#e74c3c;">⚠️ Confirm Wipe</h3><button class="close-btn">&times;</button></div>
                        <p id="wipeScopeText">You are about to perform a <strong>full wipe</strong>.</p>
                        <p>This action cannot be undone. A backup will be created automatically.</p>
                        <div class="form-group"><label>Justification * (min 20 characters)</label><textarea id="wipeJustification" rows="3" class="form-control"></textarea></div>
                        <div class="form-group"><label><input type="checkbox" id="backupConfirm"> I confirm an automatic backup was created</label></div>
                        <div class="form-group"><label>Type "CONFIRM WIPE" to proceed:</label><input type="text" id="wipeConfirmText" class="form-control"></div>
                        <div class="modal-footer"><button type="button" class="btn btn-secondary" id="cancelWipe">Cancel</button><button type="button" class="btn btn-danger" id="executeWipe">WIPE KNOWLEDGE BASE</button></div>
                    </div>
                </div>
            `;
            const div = document.createElement('div');
            div.innerHTML = modalHtml;
            document.body.appendChild(div.firstElementChild);
            modal = document.getElementById('wipeModal');
            setupModalCloseHandlers();
        }

        document.getElementById('wipeScopeText').innerHTML = `You are about to perform a <strong>${scope}</strong> wipe.`;
        const existingSelect = document.getElementById('wipeServiceSelect');
        if (existingSelect) existingSelect.remove();
        if (scope === 'service') {
            const serviceSelectHtml = `<div class="form-group"><label>Select Service Area:</label><select id="wipeServiceSelect" class="form-control"></select></div>`;
            const wipeJustification = document.getElementById('wipeJustification');
            if (wipeJustification) {
                wipeJustification.insertAdjacentHTML('beforebegin', serviceSelectHtml);
                fetch('/documents/api/service-areas')
                    .then(res => res.json())
                    .then(services => {
                        const select = document.getElementById('wipeServiceSelect');
                        if (select) {
                            services.forEach(s => { const opt = document.createElement('option'); opt.value = s; opt.textContent = s; select.appendChild(opt); });
                        }
                    });
            }
        }
        modal.style.display = 'block';
        
        const cancelBtn = document.getElementById('cancelWipe');
        if (cancelBtn) cancelBtn.onclick = () => modal.style.display = 'none';
        
        const executeBtn = document.getElementById('executeWipe');
        if (executeBtn) {
            executeBtn.onclick = () => {
                const justification = document.getElementById('wipeJustification')?.value || '';
                const backupConfirm = document.getElementById('backupConfirm')?.checked || false;
                const confirmText = document.getElementById('wipeConfirmText')?.value || '';
                if (!justification || justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
                if (!backupConfirm) { alert('You must confirm backup.'); return; }
                if (confirmText !== 'CONFIRM WIPE') { alert('Type "CONFIRM WIPE" exactly.'); return; }
                const payload = { scope, justification, backup_confirmed: backupConfirm };
                if (scope === 'service') {
                    const serviceSelect = document.getElementById('wipeServiceSelect');
                    if (!serviceSelect || !serviceSelect.value) { alert('Please select a service area.'); return; }
                    payload.service = serviceSelect.value;
                }
                fetch('/documents/api/wipe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                .then(res => {
                    if (!res.ok) return res.text().then(text => { throw new Error(text); });
                    return res.json();
                })
                .then(data => {
                    if (data.success) { alert('Wipe completed. Page will reload.'); location.reload(); }
                    else { alert('Wipe failed: ' + (data.error || 'unknown')); }
                })
                .catch(err => {
                    console.error('Wipe error:', err);
                    alert('Wipe failed: ' + err.message);
                });
            };
        }
    }

    // Override modal (unchanged)
    window.showOverrideModal = function(gap) {
        let modal = document.getElementById('overrideModal');
        if (!modal) {
            const modalHtml = `
                <div id="overrideModal" class="modal" style="display:none;">
                    <div class="modal-content" style="max-width: 600px;">
                        <div class="modal-header"><h3>Create Override (RAG 2.2)</h3><button class="close-btn">&times;</button></div>
                        <form id="overrideForm">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                                <div><label>Override Type *</label><select name="override_type" required class="form-control"><option value="">Select</option><option value="pinned">Pinned Answer</option><option value="freeze">Freeze</option><option value="correction">Correction</option><option value="suspension">Suspension</option><option value="force_verbatim">Force Verbatim</option><option value="emergency">Emergency Notice</option><option value="intent_override">Intent Override</option></select></div>
                                <div><label>Target Type *</label><select name="target_type" required class="form-control"><option value="document_id">Document ID</option><option value="intent_pattern">Intent Pattern</option><option value="keyword">Keyword/Topic</option><option value="service">Service</option></select></div>
                                <div><label>Target Value *</label><input type="text" name="target_value" required class="form-control"></div>
                                <div><label>Service (optional)</label><select name="service" class="form-control"><option value="">None</option></select></div>
                                <div><label>Valid From</label><input type="date" name="valid_from" class="form-control" value="${new Date().toISOString().split('T')[0]}"></div>
                                <div><label>Valid To</label><input type="date" name="valid_to" class="form-control"></div>
                                <div style="grid-column:span 2;"><label>Location Scope (comma separated)</label><input type="text" name="location_scope" class="form-control"></div>
                                <div style="grid-column:span 2;"><label>Trigger Conditions (JSON)</label><textarea name="trigger_conditions" rows="2" class="form-control"></textarea></div>
                                <div style="grid-column:span 2;"><label>Override Content *</label><textarea name="content" rows="4" required class="form-control"></textarea></div>
                                <div style="grid-column:span 2;"><label>Justification * (min 30 chars)</label><textarea name="justification" rows="3" required class="form-control"></textarea></div>
                                <div style="grid-column:span 2;"><label><input type="checkbox" name="approved"> I confirm this override has been approved.</label></div>
                            </div>
                            <div style="margin-top:1rem; display:flex; gap:0.5rem; justify-content:flex-end;">
                                <button type="button" class="btn btn-secondary" id="cancelOverride">Cancel</button>
                                <button type="submit" class="btn btn-primary">Create Override</button>
                            </div>
                        </form>
                    </div>
                </div>
            `;
            const div = document.createElement('div');
            div.innerHTML = modalHtml;
            document.body.appendChild(div.firstElementChild);
            modal = document.getElementById('overrideModal');
            setupModalCloseHandlers();
        }

        const form = document.getElementById('overrideForm');
        if (form) form.reset();
        
        const oldSearch = modal.querySelector('.doc-search-group');
        if (oldSearch) oldSearch.remove();
        
        const targetValueField = modal.querySelector('[name="target_value"]');
        if (targetValueField) {
            const parent = targetValueField.closest('.form-group');
            if (parent) {
                const searchHtml = `
                    <div class="form-group doc-search-group">
                        <label>Search Document (optional)</label>
                        <input type="text" id="docSearchInput" class="form-control" placeholder="Type to search documents...">
                        <div id="docSearchResults" style="max-height:150px; overflow-y:auto; border:1px solid #ccc; margin-top:5px; display:none;"></div>
                    </div>
                `;
                parent.insertAdjacentHTML('afterend', searchHtml);
                
                const searchInput = document.getElementById('docSearchInput');
                const resultsDiv = document.getElementById('docSearchResults');
                if (searchInput && resultsDiv) {
                    let debounceTimer;
                    searchInput.addEventListener('input', function() {
                        clearTimeout(debounceTimer);
                        const query = this.value.trim();
                        if (query.length < 2) { resultsDiv.style.display = 'none'; return; }
                        debounceTimer = setTimeout(() => {
                            fetch(`/documents/api/list?search=${encodeURIComponent(query)}&per_page=10`)
                                .then(res => res.json())
                                .then(data => {
                                    if (data.items.length === 0) {
                                        resultsDiv.innerHTML = '<div class="search-result-item">No results</div>';
                                    } else {
                                        let html = '';
                                        data.items.forEach(doc => {
                                            html += `<div class="search-result-item" data-id="${doc.document_id}" data-title="${doc.title}" style="padding:5px; cursor:pointer; border-bottom:1px solid #eee;">${doc.document_id} – ${doc.title}</div>`;
                                        });
                                        resultsDiv.innerHTML = html;
                                        resultsDiv.querySelectorAll('.search-result-item').forEach(el => {
                                            el.addEventListener('click', () => {
                                                const docId = el.dataset.id;
                                                const targetValue = modal.querySelector('[name="target_value"]');
                                                const targetType = modal.querySelector('[name="target_type"]');
                                                if (targetValue) targetValue.value = docId;
                                                if (targetType) targetType.value = 'document_id';
                                                searchInput.value = '';
                                                resultsDiv.style.display = 'none';
                                            });
                                        });
                                    }
                                    resultsDiv.style.display = 'block';
                                });
                        }, 300);
                    });
                    document.addEventListener('click', function(e) {
                        if (!resultsDiv.contains(e.target) && e.target !== searchInput) resultsDiv.style.display = 'none';
                    });
                }
            }
        }
        
        if (gap) {
            const targetType = modal.querySelector('[name="target_type"]');
            const targetValue = modal.querySelector('[name="target_value"]');
            const service = modal.querySelector('[name="service"]');
            const justification = modal.querySelector('[name="justification"]');
            if (targetType) targetType.value = gap.target_type || 'keyword';
            if (targetValue) targetValue.value = gap.question || '';
            if (service) service.value = gap.service || '';
            if (justification) justification.value = gap.justification || '';
        }
        
        modal.style.display = 'block';
        const cancelBtn = document.getElementById('cancelOverride');
        if (cancelBtn) cancelBtn.onclick = () => modal.style.display = 'none';
        const overrideForm = document.getElementById('overrideForm');
        if (overrideForm) {
            overrideForm.removeEventListener('submit', handleOverride);
            overrideForm.addEventListener('submit', handleOverride);
        }
    };

    function handleOverride(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        data.location_scope = data.location_scope ? data.location_scope.split(',').map(s => s.trim()) : [];
        try { data.trigger_conditions = data.trigger_conditions ? JSON.parse(data.trigger_conditions) : {}; } catch (err) { alert('Trigger Conditions must be valid JSON'); return; }
        data.approved = data.approved === 'on';
        if (data.justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
        fetch('/documents/api/overrides', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(res => {
            if (res.success) {
                alert('Override created');
                document.getElementById('overrideModal').style.display = 'none';
                if (currentTab === 'analytics') loadAnalyticsSubTab('overrides');
            } else { alert('Override failed: ' + (res.error || 'unknown')); }
        })
        .catch(err => alert('Network error: ' + err.message));
    }

    // Create Document Modal (unchanged)
    function showStep(step) {
        const modal = document.getElementById('createDocumentModal');
        if (!modal) return;
        modal.querySelectorAll('.step-content').forEach(el => el.style.display = 'none');
        const stepContent = modal.querySelector(`.step-content[data-step="${step}"]`);
        if (stepContent) stepContent.style.display = 'block';
        modal.querySelectorAll('.step').forEach((el, index) => {
            const stepNum = index + 1;
            el.style.borderBottomColor = stepNum === step ? '#3498db' : '#ccc';
            el.style.fontWeight = stepNum === step ? 'bold' : 'normal';
        });
        modal.dataset.currentStep = step;
    }

    function goToNextStep(e) {
        const modal = document.getElementById('createDocumentModal');
        const currentStep = parseInt(modal.dataset.currentStep || '1');
        if (validateStep(currentStep)) {
            if (currentStep < 4) showStep(currentStep + 1);
        }
    }

    function goToPreviousStep(e) {
        const modal = document.getElementById('createDocumentModal');
        const currentStep = parseInt(modal.dataset.currentStep || '1');
        if (currentStep > 1) showStep(currentStep - 1);
    }

    function validateStep(step) {
        const modal = document.getElementById('createDocumentModal');
        const stepContent = modal.querySelector(`.step-content[data-step="${step}"]`);
        const requiredFields = stepContent.querySelectorAll('[required]');
        const missing = [];
        for (let field of requiredFields) {
            if (!field.value.trim()) {
                let label = '';
                const parent = field.closest('.form-group');
                if (parent) {
                    const labelEl = parent.querySelector('label');
                    if (labelEl) label = labelEl.innerText.replace('*', '').trim();
                }
                missing.push(label || field.name || 'This field');
                field.style.borderColor = '#e74c3c';
            } else {
                field.style.borderColor = '';
            }
        }
        if (missing.length > 0) {
            const errorDiv = document.getElementById('stepErrorMsg');
            if (errorDiv) {
                errorDiv.innerHTML = `<strong>Missing required field(s):</strong> ${missing.join(', ')}. Please fill them before proceeding.`;
                errorDiv.style.display = 'block';
            } else {
                alert(`Missing required field(s): ${missing.join(', ')}`);
            }
            return false;
        } else {
            const errorDiv = document.getElementById('stepErrorMsg');
            if (errorDiv) errorDiv.style.display = 'none';
            return true;
        }
    }

    function updateReviewSummary() {
        const modal = document.getElementById('createDocumentModal');
        if (!modal) return;
        const serviceSelect = modal.querySelector('select[name="service_area"]');
        document.getElementById('reviewService').textContent = serviceSelect ? serviceSelect.options[serviceSelect.selectedIndex]?.textContent || '-' : '-';
        document.getElementById('reviewContentType').textContent = modal.querySelector('select[name="content_type"] option:checked')?.textContent || '-';
        document.getElementById('reviewTitle').textContent = modal.querySelector('input[name="title"]').value || '-';
        document.getElementById('reviewDepartment').textContent = modal.querySelector('input[name="department"]').value || '-';
        document.getElementById('reviewEmail').textContent = modal.querySelector('input[name="owner_email"]').value || '-';
        document.getElementById('reviewValidFrom').textContent = modal.querySelector('input[name="valid_from"]').value || '-';
        document.getElementById('reviewValidTo').textContent = modal.querySelector('input[name="valid_to"]').value || '-';
        document.getElementById('reviewLocations').textContent = modal.querySelector('input[name="locations"]').value || '-';
        document.getElementById('reviewTags').textContent = modal.querySelector('input[name="topic_tags"]').value || '-';
        document.getElementById('reviewPrereqs').textContent = modal.querySelector('input[name="prerequisites"]').value || '-';
        document.getElementById('reviewRelated').textContent = modal.querySelector('input[name="related_documents"]').value || '-';
        const reviewCycle = modal.querySelector('select[name="review_cycle"] option:checked')?.value;
        document.getElementById('reviewCycle').textContent = reviewCycle ? (reviewCycle === '' ? 'None' : reviewCycle) : '-';
        document.getElementById('reviewCross').textContent = modal.querySelector('input[name="cross_service_flag"]').checked ? 'Yes' : 'No';
    }

    // ========== FIXED: showCreateDocumentModal now refreshes UI after creation ==========
    function showCreateDocumentModal() {
        const modal = document.getElementById('createDocumentModal');
        if (!modal) { console.error('Create document modal not found'); return; }

        fetch('/documents/api/service-areas')
            .then(res => res.json())
            .then(services => {
                const serviceSelect = modal.querySelector('#serviceAreaSelect');
                if (serviceSelect) {
                    serviceSelect.innerHTML = '<option value="">-- Select a service --</option>';
                    services.forEach(service => {
                        const option = document.createElement('option');
                        option.value = service;
                        option.textContent = service.charAt(0).toUpperCase() + service.slice(1);
                        serviceSelect.appendChild(option);
                    });
                }
            })
            .catch(err => console.error('Failed to load services:', err));

        if (window.currentUser) {
            const deptField = modal.querySelector('input[name="department"]');
            const emailField = modal.querySelector('input[name="owner_email"]');
            if (deptField && window.currentUser.department) deptField.value = window.currentUser.department;
            if (emailField && window.currentUser.email) emailField.value = window.currentUser.email;
        }

        showStep(1);
        const errorDiv = document.getElementById('stepErrorMsg');
        if (errorDiv) errorDiv.style.display = 'none';

        const nextBtns = modal.querySelectorAll('.next-step');
        const prevBtns = modal.querySelectorAll('.prev-step');
        nextBtns.forEach(btn => btn.removeEventListener('click', goToNextStep));
        prevBtns.forEach(btn => btn.removeEventListener('click', goToPreviousStep));
        nextBtns.forEach(btn => btn.addEventListener('click', goToNextStep));
        prevBtns.forEach(btn => btn.addEventListener('click', goToPreviousStep));

        const inputs = modal.querySelectorAll('input, select, textarea');
        inputs.forEach(input => input.removeEventListener('input', updateReviewSummary));
        inputs.forEach(input => input.addEventListener('input', updateReviewSummary));
        updateReviewSummary();

        modal.style.display = 'block';
        const form = document.getElementById('createDocForm');
        form.removeEventListener('submit', handleCreateDocument);
        form.addEventListener('submit', handleCreateDocument);
    }

    // ========== FIXED: handleCreateDocument now refreshes tree and list ==========
    function handleCreateDocument(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        data.locations = data.locations ? data.locations.split(',').map(s => s.trim()) : ['Council-wide'];
        data.prerequisites = data.prerequisites ? data.prerequisites.split(',').map(s => s.trim()) : [];
        data.related_documents = data.related_documents ? data.related_documents.split(',').map(s => s.trim()) : [];
        data.topic_tags = data.topic_tags ? data.topic_tags.split(',').map(s => s.trim()) : [data.service_area];
        data.authority_confidence = parseFloat(data.authority_confidence) || 0.9;
        data.cross_service_flag = data.cross_service_flag === 'on';
        data.review_cycle = data.review_cycle || null;

        fetch('/documents/api/document', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(result => {
            if (result.id) {
                document.getElementById('createDocumentModal').style.display = 'none';
                loadDocument(result.id);
                refreshTree();
                loadList(1);
                fetch('/documents/api/filter-options')
                    .then(res => res.json())
                    .then(filterData => populateFilters(filterData));
            } else {
                alert('Error: ' + (result.error || 'unknown'));
            }
        });
    }

    function showServiceModal() {
        const modal = document.getElementById('serviceModal');
        if (!modal) { console.error('Service modal not found'); return; }
        const form = document.getElementById('serviceForm');
        if (form) form.reset();
        document.getElementById('customContentTypes').style.display = 'none';
        modal.style.display = 'block';
        document.querySelectorAll('input[name="template"]').forEach(radio => {
            radio.removeEventListener('change', templateChangeHandler);
            radio.addEventListener('change', templateChangeHandler);
        });
        form.removeEventListener('submit', handleCreateService);
        form.addEventListener('submit', handleCreateService);
        const cancelBtn = modal.querySelector('.btn-secondary');
        if (cancelBtn) cancelBtn.onclick = () => modal.style.display = 'none';
    }

    function templateChangeHandler(e) {
        document.getElementById('customContentTypes').style.display = e.target.value === 'custom' ? 'block' : 'none';
    }

    function handleCreateService(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        const data = {
            name: formData.get('name'),
            description: formData.get('description') || '',
            tags: formData.get('tags') ? formData.get('tags').split(',').map(s => s.trim()) : [],
            template: formData.get('template'),
            content_types: formData.getAll('content_types')
        };
        if (!data.name) { alert('Service name is required'); return; }
        if (data.template === 'custom' && data.content_types.length === 0) { alert('Please select at least one content type for custom template'); return; }
        showLoader();
        fetch('/documents/api/service', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(result => {
            hideLoader();
            if (result.success) {
                alert('Service created successfully');
                document.getElementById('serviceModal').style.display = 'none';
                refreshTree();
                fetch('/documents/api/filter-options')
                    .then(res => res.json())
                    .then(filterData => populateFilters(filterData));
            } else {
                alert('Error creating service: ' + (result.error || 'Unknown error'));
            }
        })
        .catch(err => { hideLoader(); alert('Network error: ' + err.message); });
    }

    function showAddContentTypesModal(service) {
        const modal = document.getElementById('addContentTypesModal');
        if (!modal) { console.error('Add content types modal not found'); return; }
        document.getElementById('addContentTypesService').textContent = service;
        const container = document.getElementById('contentTypesList');
        container.innerHTML = '';
        const contentTypes = ['procedure', 'policy', 'fee_schedule', 'faq', 'emergency', 'contact_directory'];
        contentTypes.forEach(ct => {
            const div = document.createElement('div');
            div.style.margin = '0.25rem 0';
            div.innerHTML = `<label><input type="checkbox" value="${ct}"> ${ct.replace('_', ' ')}</label>`;
            container.appendChild(div);
        });
        modal.style.display = 'block';
        const cancelBtn = document.getElementById('cancelAddContentTypes');
        const addBtn = document.getElementById('addContentTypesBtn');
        cancelBtn.onclick = () => modal.style.display = 'none';
        addBtn.onclick = () => {
            const selected = Array.from(document.querySelectorAll('#contentTypesList input:checked')).map(cb => cb.value);
            if (selected.length === 0) { alert('Please select at least one content type.'); return; }
            fetch('/documents/api/service/' + service + '/content-types', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content_types: selected })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    alert('Content types added successfully');
                    modal.style.display = 'none';
                    refreshTree();
                    fetch('/documents/api/filter-options')
                        .then(res => res.json())
                        .then(filterData => populateFilters(filterData));
                } else {
                    alert('Error adding content types: ' + (result.error || 'Unknown error'));
                }
            })
            .catch(err => alert('Network error: ' + err.message));
        };
    }

    function showRagHealthDetails() {
        fetch('/documents/api/health/details')
            .then(res => res.json())
            .then(data => {
                let msg = `RAG Status: ${data.status}\n`;
                if (data.components) {
                    msg += 'Components:\n';
                    for (const [comp, status] of Object.entries(data.components)) msg += `  ${comp}: ${status}\n`;
                }
                if (data.uptime) msg += `Uptime: ${data.uptime}\n`;
                if (data.last_error) msg += `Last Error: ${data.last_error}\n`;
                alert(msg);
            })
            .catch(err => alert('Could not fetch health details: ' + err.message));
    }

    // Context menu actions (uploadToFolder removed)
    function uploadToFolder(path) {
        alert('Bulk import has been removed from the UI.');
    }

    function exportFolderAsZip(path) {
        fetch('/documents/api/export-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        })
        .then(res => {
            if (!res.ok) return res.json().then(err => { throw new Error(err.error); });
            return res.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = path.replace(/\//g, '_') + '.zip';
            a.click();
            window.URL.revokeObjectURL(url);
        })
        .catch(err => alert('Export failed: ' + err.message));
    }

    function renameService(service) {
        const newName = prompt('Enter new service name (lowercase, underscores allowed):', service);
        if (!newName || newName === service) return;
        const justification = prompt('Justification for renaming service (min 20 chars):');
        if (!justification || justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
        fetch(`/documents/api/service/${service}/rename`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: newName, justification })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert('Service renamed successfully');
                refreshTree();
                fetch('/documents/api/filter-options')
                    .then(res => res.json())
                    .then(filterData => populateFilters(filterData));
            } else { alert('Error: ' + (data.error || 'unknown')); }
        });
    }

    function deleteService(service) {
        if (!confirm(`Are you sure you want to delete service "${service}"? This will move all documents to archive first.`)) return;
        const justification = prompt('Justification for deleting service (min 20 chars):');
        if (!justification || justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
        fetch(`/documents/api/service/${service}/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ justification })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) { alert('Service deleted'); refreshTree(); fetch('/documents/api/filter-options').then(res => res.json()).then(filterData => populateFilters(filterData)); }
            else { alert('Error: ' + (data.error || 'unknown')); }
        });
    }

    function archiveAllDocuments(service) {
        if (!confirm(`Archive all documents in service "${service}"?`)) return;
        const justification = prompt('Justification (min 20 chars):');
        if (!justification || justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
        fetch(`/documents/api/service/${service}/archive-all`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ justification })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) { alert('All documents archived'); refreshTree(); }
            else { alert('Error: ' + (data.error || 'unknown')); }
        });
    }

    function bulkAddTagToService(service) {
        const tag = prompt('Enter tag to add to all documents in this service:');
        if (!tag) return;
        const scope = confirm('Add to archived documents as well? Click OK for yes, Cancel for active only.');
        fetch(`/documents/api/service/${service}/bulk-add-tag`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag, include_archived: scope })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) { alert(`Tag added to ${data.count} documents`); }
            else { alert('Error: ' + (data.error || 'unknown')); }
        });
    }

    function exportServiceCSV(service) {
        window.location.href = `/documents/api/service/${service}/export-csv`;
    }

    function viewServiceDetails(service) {
        fetch(`/documents/api/service/${service}/details`)
            .then(res => res.json())
            .then(data => {
                let msg = `Service: ${service}\n`;
                msg += `Total documents: ${data.total}\nActive: ${data.active}\nArchived: ${data.archived}\nExpired: ${data.expired}\n`;
                msg += `Content types present: ${data.content_types.join(', ')}\nMissing types: ${data.missing_types.join(', ')}\nConflicts: ${data.conflicts}`;
                alert(msg);
            });
    }

    function renameDocument(id) {
        const newTitle = prompt('Enter new title:');
        if (!newTitle) return;
        const justification = prompt('Justification (min 20 chars):');
        if (!justification || justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
        fetch(`/documents/api/document/${id}/rename`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle, justification })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) { alert('Document renamed'); loadDocument(id); refreshTree(); }
            else { alert('Error: ' + (data.error || 'unknown')); }
        });
    }

    function changeContentType(id) {
        fetch('/documents/api/filter-options')
            .then(res => res.json())
            .then(filterData => {
                const types = filterData.content_types;
                const newType = prompt('Enter new content type (e.g., procedure, policy):\n' + types.join(', '));
                if (!newType) return;
                const justification = prompt('Justification (min 20 chars):');
                if (!justification || justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
                fetch(`/documents/api/document/${id}/change-content-type`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content_type: newType, justification })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) { alert('Content type changed'); loadDocument(id); refreshTree(); }
                    else { alert('Error: ' + (data.error || 'unknown')); }
                });
            });
    }

    function manageTags(id) {
        fetch(`/documents/api/document/${id}`)
            .then(res => res.json())
            .then(doc => {
                const currentTags = doc.topic_tags ? doc.topic_tags.join(', ') : '';
                const tagsInput = prompt('Enter new tags (comma separated):', currentTags);
                if (tagsInput === null) return;
                const newTags = tagsInput.split(',').map(t => t.trim()).filter(t => t);
                fetch(`/documents/api/document/${id}/update-tags`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tags: newTags })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) { alert('Tags updated'); if (currentDocId == id) loadDocument(id); refreshTree(); }
                    else { alert('Error: ' + (data.error || 'unknown')); }
                });
            });
    }

    // ========== FIXED: archiveDocument now refreshes UI ==========
    function archiveDocument(id) {
        if (!confirm('Are you sure you want to archive this document? It will be moved to the archive folder.')) return;
        fetch(`/documents/api/document/${id}/archive`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('Document archived');
                    refreshTree();
                    if (currentDocId == id) {
                        document.getElementById('listView').style.display = 'block';
                        document.getElementById('editorView').style.display = 'none';
                    }
                    loadList(currentPage);
                } else { alert('Archive failed: ' + (data.error || 'unknown')); }
            });
    }

    // ========== FIXED: deleteDocumentPermanently now refreshes UI ==========
    function deleteDocumentPermanently(id) {
        const justification = prompt('Provide a justification for permanent deletion (min 20 characters):');
        if (!justification || justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
        if (!confirm('This action cannot be undone. The document will be permanently removed from the system. Continue?')) return;
        fetch(`/documents/api/document/${id}/delete-permanent`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ justification })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert('Document permanently deleted');
                refreshTree();
                if (currentDocId == id) {
                    document.getElementById('listView').style.display = 'block';
                    document.getElementById('editorView').style.display = 'none';
                }
                loadList(currentPage);
            } else { alert('Deletion failed: ' + (data.error || 'unknown')); }
        });
    }

    // ========== FIXED: restoreDocument now refreshes UI ==========
    function restoreDocument(id) {
        const modal = document.getElementById('restoreModal');
        if (!modal) return;
        document.getElementById('restoreDocId').value = id;
        document.getElementById('restoreValidFrom').value = new Date().toISOString().split('T')[0];
        modal.style.display = 'block';
        document.getElementById('cancelRestore').onclick = () => modal.style.display = 'none';
        document.getElementById('executeRestore').onclick = () => {
            const data = {
                valid_from: document.getElementById('restoreValidFrom').value,
                valid_to: document.getElementById('restoreValidTo').value || null,
                mode: document.querySelector('input[name="restoreMode"]:checked').value
            };
            fetch('/documents/api/document/' + id + '/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(res => {
                if (res.success) {
                    alert('Document restored');
                    modal.style.display = 'none';
                    loadDocument(id);
                    refreshTree();
                    loadList(currentPage);
                    fetch('/documents/api/filter-options')
                        .then(res => res.json())
                        .then(filterData => populateFilters(filterData));
                } else { alert('Restore failed'); }
            });
        };
    }

    // Tab content loaders (unchanged)
    function loadAnalyticsStrip() {
        loadAnalyticsSubTab('coverage');
        loadServiceHealth();
    }

    function loadServiceHealth() {
        fetch('/documents/api/service-health')
            .then(res => res.json())
            .then(data => {
                let container = document.querySelector('#analyticsContent .service-health-list');
                if (!container) {
                    const healthDiv = document.createElement('div');
                    healthDiv.className = 'service-health-list';
                    document.getElementById('analyticsContent').appendChild(healthDiv);
                    container = healthDiv;
                }
                container.innerHTML = '<h4>Service Health Scores</h4>';
                data.forEach(s => {
                    const div = document.createElement('div');
                    div.className = `service-health-item ${s.color}`;
                    div.innerHTML = `<span class="service-name">${s.service}</span> <span class="service-coverage">${s.coverage}%</span> <span class="service-health-score ${s.color}">●</span> <small>Health: ${s.health}%</small>`;
                    container.appendChild(div);
                });
            });
    }

    function loadAnalyticsSubTab(subTab) {
        const contentDiv = document.getElementById('analyticsContent');
        contentDiv.innerHTML = '<p>Loading...</p>';
        if (subTab === 'coverage') {
            if (!ragOnline()) {
                contentDiv.innerHTML = '<p>RAG is offline – showing local data. Ingest documents to see RAG coverage.</p>';
            }
            fetch('/documents/api/service-coverage')
                .then(res => res.json())
                .then(data => {
                    let html = '<h4>Service Coverage</h4>';
                    if (data.services && data.services.length > 0) {
                        html += '<ul>';
                        data.services.forEach(s => {
                            let color = 'green';
                            if (s.coverage < 50) color = 'red';
                            else if (s.coverage < 80) color = 'yellow';
                            html += `<li><span class="service-name">${s.name}:</span> <span class="service-coverage">${s.coverage}%</span> <span class="service-health-score ${color}">●</span> (${s.missing_categories || 0} missing)</li>`;
                        });
                        html += '</ul>';
                    } else if (data.message) {
                        html += `<p>${data.message}</p>`;
                    } else {
                        html += '<p>No coverage data available. Please create services and ingest documents.</p>';
                    }
                    contentDiv.innerHTML = html;
                })
                .catch(() => contentDiv.innerHTML = '<p>Failed to load coverage data.</p>');
        } else if (subTab === 'conflict') {
            fetch('/documents/api/conflict-analytics')
                .then(res => res.json())
                .then(data => {
                    let html = '<h4>Conflict Analytics</h4>';
                    html += `<p>Total conflicts: ${data.total_conflicts || 0}</p>`;
                    if (data.breakdown) {
                        html += '<h5>Breakdown:</h5><ul>';
                        Object.entries(data.breakdown).forEach(([key, value]) => { html += `<li>${key}: ${value}</li>`; });
                        html += '</ul>';
                    }
                    if (data.by_department) {
                        html += '<h5>By Service:</h5><ul>';
                        Object.entries(data.by_department).forEach(([key, value]) => { html += `<li>${key}: ${value}</li>`; });
                        html += '</ul>';
                    }
                    contentDiv.innerHTML = html;
                })
                .catch(() => contentDiv.innerHTML = '<p>Failed to load conflict analytics.</p>');
        } else if (subTab === 'overrides') {
            fetch('/documents/api/overrides')
                .then(res => res.json())
                .then(data => {
                    let html = '<h4>Override Registry</h4>';
                    if (data.length > 0) {
                        html += '<table class="table"><thead><th>ID</th><th>Type</th><th>Target</th><th>Service</th><th>Valid From</th><th>Valid To</th><th>Justification</th><th>Actions</th></thead><tbody>';
                        data.forEach(o => {
                            html += `<tr>
                                <td>${o.override_id}</td>
                                <td>${o.override_type}</td>
                                <td>${o.target_value}</td>
                                <td>${o.service || '-'}</td>
                                <td>${o.valid_from || '-'}</td>
                                <td>${o.valid_to || '∞'}</td>
                                <td>${o.justification.substring(0, 30)}...</td>
                                <td><button class="btn btn-small revoke-override" data-id="${o.id}">Revoke</button></td>
                            </tr>`;
                        });
                        html += '</tbody></table>';
                    } else {
                        html += '<p>No active overrides.</p>';
                    }
                    contentDiv.innerHTML = html;
                    document.querySelectorAll('.revoke-override').forEach(btn => {
                        btn.addEventListener('click', () => {
                            const id = btn.dataset.id;
                            if (confirm('Revoke this override?')) {
                                fetch('/documents/api/overrides/' + id + '/revoke', { method: 'POST' })
                                    .then(res => res.json())
                                    .then(data => {
                                        if (data.success) { alert('Override revoked'); loadAnalyticsSubTab('overrides'); }
                                        else { alert('Failed to revoke'); }
                                    });
                            }
                        });
                    });
                })
                .catch(() => contentDiv.innerHTML = '<p>Failed to load overrides.</p>');
        }
    }

    function loadExpiredMonitor() {
        const contentDiv = document.getElementById('expiredContent');
        contentDiv.innerHTML = '<p>Loading expired documents...</p>';
        fetch('/documents/api/expiring-docs?days=0')
            .then(res => res.json())
            .then(data => {
                let html = '<h4>Expired Documents</h4>';
                if (data.documents && data.documents.length > 0) {
                    const byService = {};
                    data.documents.forEach(d => {
                        const service = d.service || 'Unknown';
                        if (!byService[service]) byService[service] = [];
                        byService[service].push(d);
                    });
                    html += '<p>Total expired: ' + data.documents.length + '</p>';
                    for (const [service, docs] of Object.entries(byService)) {
                        html += `<h5>${service}: ${docs.length}</h5><ul>`;
                        docs.forEach(d => { html += `<li>${d.document_id} (expired ${d.expired_date})</li>`; });
                        html += '</ul>';
                    }
                } else {
                    html += '<p>No expired documents.</p>';
                }
                contentDiv.innerHTML = html;
            })
            .catch(() => contentDiv.innerHTML = '<p>Failed to load expired documents.</p>');
    }

    function loadDecisionLedger(page = 1, filterAction = '') {
        ledgerPage = page;
        ledgerFilter = filterAction;
        const contentDiv = document.getElementById('ledgerContent');
        contentDiv.innerHTML = '<p>Loading ledger...</p>';
        const params = new URLSearchParams({ page, per_page: 20, action: filterAction });
        fetch('/documents/api/audit?' + params)
            .then(res => res.json())
            .then(data => {
                let html = '<h4>Decision Ledger</h4>';
                if (data.items && data.items.length > 0) {
                    html += '<table class="table"><thead><th>Timestamp</th><th>User</th><th>Action</th><th>Target</th><th>Details</th></thead><tbody>';
                    data.items.forEach(log => {
                        html += `<tr>
                            <td>${new Date(log.timestamp).toLocaleString()}</td>
                            <td>${log.user || 'System'}</td>
                            <td>${log.action}</td>
                            <td>${log.target_type}: ${log.target_id}</td>
                            <td title="${log.note || ''}">${(log.note || '').substring(0, 100)}${(log.note || '').length > 100 ? '…' : ''}</td>
                        </tr>`;
                    });
                    html += '</tbody></table>';
                    html += `<div class="pagination"><button id="prevLedgerPage" ${data.page <= 1 ? 'disabled' : ''}>Previous</button><span>Page ${data.page} of ${data.pages}</span><button id="nextLedgerPage" ${data.page >= data.pages ? 'disabled' : ''}>Next</button></div>`;
                } else {
                    html += '<p>No audit entries.</p>';
                }
                contentDiv.innerHTML = html;
                document.getElementById('prevLedgerPage')?.addEventListener('click', () => { if (ledgerPage > 1) loadDecisionLedger(ledgerPage - 1, ledgerFilter); });
                document.getElementById('nextLedgerPage')?.addEventListener('click', () => { if (ledgerPage < data.pages) loadDecisionLedger(ledgerPage + 1, ledgerFilter); });
            })
            .catch(() => contentDiv.innerHTML = '<p>Failed to load ledger – endpoint not available.</p>');
    }

    function loadConflictQueue() {
        const contentDiv = document.getElementById('conflictContent');
        contentDiv.innerHTML = '<p>Loading conflict queue...</p>';
        fetch('/documents/api/conflicts?page=1&status=unresolved')
            .then(res => res.json())
            .then(data => {
                let html = '<h4>Unresolved Conflicts</h4>';
                if (data.items.length === 0) {
                    html += '<p>No unresolved conflicts.</p>';
                } else {
                    html += '<table class="table"><thead><th>ID</th><th>Document 1</th><th>Document 2</th><th>Reason</th><th>Created</th><th>Actions</th></thead><tbody>';
                    data.items.forEach(c => {
                        html += `<tr>
                            <td>${c.id}</td>
                            <td>${c.doc1.document_id}<br><small>${c.doc1.title}</small></td>
                            <td>${c.doc2.document_id}<br><small>${c.doc2.title}</small></td>
                            <td>${c.reason}</td>
                            <td>${new Date(c.created_at).toLocaleDateString()}</td>
                            <td><button class="btn btn-small resolve-conflict" data-id="${c.id}">Resolve</button></td>
                        </tr>`;
                    });
                    html += '</tbody></table>';
                }
                contentDiv.innerHTML = html;
                document.querySelectorAll('.resolve-conflict').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const conflictId = btn.dataset.id;
                        const resolution = prompt('Resolution method: retire_one, override');
                        if (!resolution) return;
                        const selectedDocId = prompt('Document ID to retire (if retire_one)');
                        const justification = prompt('Justification (min 20 chars)');
                        if (!justification || justification.length < 20) { alert('Justification must be at least 20 characters.'); return; }
                        fetch(`/documents/api/conflicts/${conflictId}/resolve`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ resolution, selected_doc_id: selectedDocId, justification })
                        })
                        .then(res => res.json())
                        .then(data => {
                            if (data.success) { alert('Conflict resolved'); loadConflictQueue(); }
                            else { alert('Error: ' + (data.error || 'unknown')); }
                        });
                    });
                });
            })
            .catch(err => { contentDiv.innerHTML = '<p>Failed to load conflicts.</p>'; console.error(err); });
    }

    // Bulk actions & pagination (unchanged)
    function toggleSelectAll() {
        const checkboxes = document.querySelectorAll('#docTableBody input[type="checkbox"]');
        const checked = document.getElementById('selectAllCheckbox').checked;
        checkboxes.forEach(cb => {
            cb.checked = checked;
            if (checked) selectedDocs.add(cb.closest('tr').dataset.id);
            else selectedDocs.delete(cb.closest('tr').dataset.id);
        });
    }

    function showBulkActions() {
        const ids = Array.from(selectedDocs);
        if (ids.length === 0) { alert('No documents selected'); return; }
        const action = prompt('Enter action: archive, restore, ingest', 'archive');
        if (!action) return;
        fetch('/documents/api/bulk', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action, document_ids: ids })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert(`Bulk ${action} completed on ${data.count} documents`);
                loadList(currentPage);
                selectedDocs.clear();
                document.getElementById('selectAllCheckbox').checked = false;
                refreshTree();
                fetch('/documents/api/filter-options')
                    .then(res => res.json())
                    .then(filterData => populateFilters(filterData));
            } else { alert('Bulk action failed'); }
        });
    }

    function changePage(page) {
        if (page >= 1 && page <= totalPages) loadList(page);
    }

    function exportFiltered() {
        const params = new URLSearchParams({
            service: document.getElementById('serviceFilter').value,
            content_type: document.getElementById('contentTypeFilter').value,
            status: document.getElementById('statusFilter').value,
            search: document.getElementById('searchInput').value
        });
        window.location.href = '/documents/api/export?' + params;
    }

    function expandAll() {
        document.querySelectorAll('.knowledge-tree ul').forEach(ul => ul.style.display = 'block');
        document.querySelectorAll('.tree-folder .expand-icon').forEach(icon => icon.textContent = '▼');
    }

    function collapseAll() {
        document.querySelectorAll('.knowledge-tree ul').forEach(ul => ul.style.display = 'none');
        document.querySelectorAll('.tree-folder .expand-icon').forEach(icon => icon.textContent = '▶');
    }

    function toggleMoreMenu() {
        const menu = document.getElementById('moreDropdown');
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }

    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Context menu (unchanged, but uploadToFolder now alerts removal)
    function enableContextMenu() {
        document.querySelectorAll('.tree-folder, .tree-file').forEach(el => {
            el.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const type = el.classList.contains('tree-folder') ? 'folder' : 'file';
                const path = el.dataset.path;
                const id = el.dataset.id;
                showContextMenu(e.clientX, e.clientY, type, path, id);
            });
        });
    }

    function showContextMenu(x, y, type, path, id) {
        const oldMenu = document.getElementById('context-menu');
        if (oldMenu) oldMenu.remove();

        const menu = document.createElement('div');
        menu.id = 'context-menu';
        menu.style.position = 'fixed';
        menu.style.background = 'white';
        menu.style.border = '1px solid #ccc';
        menu.style.boxShadow = '2px 2px 5px rgba(0,0,0,0.2)';
        menu.style.zIndex = 1000;
        menu.style.maxHeight = '400px';
        menu.style.overflowY = 'auto';

        const canManage = window.currentUser?.can_manage_knowledge === true;
        let items = [];

        if (type === 'folder') {
            const parts = path.split('/');
            const isServiceFolder = parts.length === 2;
            const serviceName = parts[1];
            items.push({ label: 'View Coverage', action: () => alert('View coverage for: ' + path) });
            if (canManage) {
                items.push({ label: 'Add Content Types', action: () => { const service = path.split('/')[1]; showAddContentTypesModal(service); } });
                if (isServiceFolder) {
                    items.push({ label: 'Rename Service', action: () => renameService(serviceName) });
                    items.push({ label: 'Delete Service', action: () => deleteService(serviceName) });
                    items.push({ label: 'Archive All Documents', action: () => archiveAllDocuments(serviceName) });
                    items.push({ label: 'Bulk Add Tag', action: () => bulkAddTagToService(serviceName) });
                }
            }
            items.push({ label: 'Export as ZIP', action: () => exportFolderAsZip(path) });
            if (isServiceFolder) {
                items.push({ label: 'Export as CSV', action: () => exportServiceCSV(serviceName) });
                items.push({ label: 'View Service Details', action: () => viewServiceDetails(serviceName) });
            }
        } else {
            const node = document.querySelector(`.tree-file[data-id="${id}"]`);
            const isArchived = node?.dataset.archived === 'true';
            const isLocked = node?.dataset.locked === 'true';
            items.push({ label: 'Download', action: () => downloadDocument(id) });
            items.push({ label: 'History', action: () => showHistoryModal(id) });
            if (!isArchived) {
                if (canManage) {
                    items.push({ label: 'Edit', action: () => loadDocument(id) });
                    items.push({ label: 'New Version', action: () => showNewVersionModal(id) });
                    items.push({ label: 'Archive', action: () => archiveDocument(id) });
                    items.push({ label: isLocked ? 'Unlock' : 'Lock', action: () => toggleLock(id) });
                    items.push({ label: 'Assign', action: () => showAssignModal(id) });
                    items.push({ label: 'Rename Document', action: () => renameDocument(id) });
                    items.push({ label: 'Change Content Type', action: () => changeContentType(id) });
                    items.push({ label: 'Manage Tags', action: () => manageTags(id) });
                }
            } else {
                if (canManage) {
                    items.push({ label: 'Restore', action: () => restoreDocument(id) });
                    items.push({ label: 'Delete Permanently', action: () => deleteDocumentPermanently(id) });
                }
            }
        }

        items.forEach(item => {
            const div = document.createElement('div');
            div.textContent = item.label;
            div.style.padding = '8px 12px';
            div.style.cursor = 'pointer';
            div.addEventListener('mouseenter', () => div.style.background = '#f0f0f0');
            div.addEventListener('mouseleave', () => div.style.background = 'white');
            div.addEventListener('click', () => { item.action(); menu.remove(); });
            menu.appendChild(div);
        });

        document.body.appendChild(menu);
        const menuWidth = menu.offsetWidth;
        const menuHeight = menu.offsetHeight;
        let left = x, top = y;
        if (left + menuWidth > window.innerWidth) left = window.innerWidth - menuWidth - 5;
        if (top + menuHeight > window.innerHeight) top = window.innerHeight - menuHeight - 5;
        menu.style.left = left + 'px';
        menu.style.top = top + 'px';
        setTimeout(() => {
            window.addEventListener('click', function closeMenu(e) {
                if (!menu.contains(e.target)) { menu.remove(); window.removeEventListener('click', closeMenu); }
            });
        }, 0);
    }

    // Re-attach wipe menu listeners
    attachWipeMenuListeners();
});