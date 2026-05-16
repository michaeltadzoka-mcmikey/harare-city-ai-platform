/**
 * Standalone Override Modal Helper (no dependencies on Documents module DOM)
 * Provides window.showOverrideModal for Knowledge Gaps and other pages.
 */

// Ensure the override modal exists in the DOM
function ensureOverrideModal() {
    let modal = document.getElementById('overrideModal');
    if (modal) return modal;

    const modalHtml = `
        <div id="overrideModal" class="modal" style="display:none;">
            <div class="modal-content" style="max-width: 600px;">
                <div class="modal-header">
                    <h3>Create Override (RAG 2.2)</h3>
                    <button class="close-btn" onclick="document.getElementById('overrideModal').style.display='none'">&times;</button>
                </div>
                <form id="overrideForm">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <div>
                            <label>Override Type *</label>
                            <select name="override_type" required class="form-control">
                                <option value="">Select</option>
                                <option value="pinned">Pinned Answer</option>
                                <option value="freeze">Freeze</option>
                                <option value="correction">Correction</option>
                                <option value="suspension">Suspension</option>
                                <option value="force_verbatim">Force Verbatim</option>
                                <option value="emergency">Emergency Notice</option>
                                <option value="intent_override">Intent Override</option>
                            </select>
                        </div>
                        <div>
                            <label>Target Type *</label>
                            <select name="target_type" required class="form-control">
                                <option value="document_id">Document ID</option>
                                <option value="intent_pattern">Intent Pattern</option>
                                <option value="keyword">Keyword/Topic</option>
                                <option value="service">Service</option>
                            </select>
                        </div>
                        <div>
                            <label>Target Value *</label>
                            <input type="text" name="target_value" required class="form-control">
                        </div>
                        <div>
                            <label>Service (optional)</label>
                            <select name="service" class="form-control"><option value="">None</option></select>
                        </div>
                        <div>
                            <label>Valid From</label>
                            <input type="date" name="valid_from" class="form-control" value="${new Date().toISOString().split('T')[0]}">
                        </div>
                        <div>
                            <label>Valid To</label>
                            <input type="date" name="valid_to" class="form-control">
                        </div>
                        <div style="grid-column:span 2;">
                            <label>Location Scope (comma separated)</label>
                            <input type="text" name="location_scope" class="form-control">
                        </div>
                        <div style="grid-column:span 2;">
                            <label>Trigger Conditions (JSON)</label>
                            <textarea name="trigger_conditions" rows="2" class="form-control"></textarea>
                        </div>
                        <div style="grid-column:span 2;">
                            <label>Override Content *</label>
                            <textarea name="content" rows="4" required class="form-control"></textarea>
                        </div>
                        <div style="grid-column:span 2;">
                            <label>Justification * (min 30 chars)</label>
                            <textarea name="justification" rows="3" required class="form-control"></textarea>
                        </div>
                        <div style="grid-column:span 2;">
                            <label><input type="checkbox" name="approved"> I confirm this override has been approved.</label>
                        </div>
                    </div>
                    <div style="margin-top:1rem; display:flex; gap:0.5rem; justify-content:flex-end;">
                        <button type="button" class="btn btn-secondary" id="cancelOverrideBtn">Cancel</button>
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

    // Attach close handlers
    const closeBtn = modal.querySelector('.close-btn');
    if (closeBtn) closeBtn.onclick = () => modal.style.display = 'none';
    const cancelBtn = document.getElementById('cancelOverrideBtn');
    if (cancelBtn) cancelBtn.onclick = () => modal.style.display = 'none';

    return modal;
}

window.showOverrideModal = function(gap) {
    const modal = ensureOverrideModal();
    const form = document.getElementById('overrideForm');
    if (form) form.reset();

    // Optional: pre-fill with gap data if provided
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

    // Handle form submission
    const overrideForm = document.getElementById('overrideForm');
    const handleSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(overrideForm);
        const data = Object.fromEntries(formData.entries());
        data.location_scope = data.location_scope ? data.location_scope.split(',').map(s => s.trim()) : [];
        try {
            data.trigger_conditions = data.trigger_conditions ? JSON.parse(data.trigger_conditions) : {};
        } catch (err) {
            alert('Trigger Conditions must be valid JSON');
            return;
        }
        data.approved = data.approved === 'on';
        if (data.justification.length < 20) {
            alert('Justification must be at least 20 characters.');
            return;
        }
        try {
            const response = await fetch('/documents/api/overrides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (result.success) {
                alert('Override created');
                modal.style.display = 'none';
                if (typeof loadAnalyticsSubTab === 'function') loadAnalyticsSubTab('overrides');
            } else {
                alert('Override failed: ' + (result.error || 'unknown'));
            }
        } catch (err) {
            alert('Network error: ' + err.message);
        }
    };
    overrideForm.removeEventListener('submit', handleSubmit);
    overrideForm.addEventListener('submit', handleSubmit);
};