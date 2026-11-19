(() => {
    const dialog = document.querySelector('.requirement-dialog');
    if (!dialog) return;
    const content = dialog.querySelector('.modal-content');
    let opener;
    let busy = false;
    const close = () => { if (!busy) dialog.close(); };
    function syncOptions() {
        const extraction = content.querySelector('[name="text_extraction_enabled"]');
        const validation = content.querySelector('[name="validation_enabled"]');
        if (!extraction || !validation) return;
        if (!validation.dataset.locked) validation.dataset.locked = String(validation.disabled);
        const locked = validation.dataset.locked === 'true';
        if (!extraction.checked && !locked) validation.checked = false;
        validation.disabled = locked || !extraction.checked;
        content.querySelector('[data-nlp-hint]').hidden = extraction.checked || locked;
        content.querySelector('[data-validation-box]').hidden = !validation.checked;
    }
    function showForm(html) {
        content.innerHTML = html;
        content.querySelectorAll('option[value="REGULAR"]').forEach(option => { option.textContent = 'Regular courses'; });
        syncOptions();
        content.querySelector('[name="requirement_title"]').focus();
    }
    document.addEventListener('click', async event => {
        const link = event.target.closest('[data-edit-requirement]');
        if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (dialog.open) return;
        opener = link;
        content.innerHTML = '<h2 id="requirement-modal-title">Edit requirement</h2><p role="status">Loading requirement…</p>';
        dialog.showModal();
        try {
            const response = await fetch(link.dataset.editRequirement, {headers: {'Accept': 'application/json'}});
            if (!response.ok) throw new Error('Unable to load this requirement. Please close and try again.');
            const data = await response.json();
            if (dialog.open) showForm(data.html);
        } catch (error) {
            content.innerHTML = '<h2 id="requirement-modal-title">Edit requirement</h2><p role="alert"></p>';
            content.querySelector('[role="alert"]').textContent = error.message;
        }
    });
    dialog.addEventListener('click', event => {
        if (event.target.closest('[data-close-modal]')) close();
        if (event.target === dialog) {
            const rect = dialog.getBoundingClientRect();
            if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close();
        }
    });
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', () => { content.innerHTML = ''; opener?.focus(); });
    dialog.addEventListener('change', syncOptions);
    dialog.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy) return;
        const form = event.target;
        const payload = new FormData(form);
        busy = true;
        const save = form.querySelector('[type="submit"]');
        save.disabled = true;
        save.setAttribute('aria-busy', 'true');
        const errorBox = form.querySelector('.modal-error');
        errorBox.hidden = true;
        try {
            const response = await fetch(form.action, {method: 'POST', body: payload, headers: {'Accept': 'application/json'}});
            if (response.status === 422) { showForm((await response.json()).html); return; }
            if (!response.ok || !(await response.json()).saved) throw new Error('Could not save. Please try again.');
            // Refresh the displayed data while retaining the current page and table position.
            const refreshed = await fetch(window.location.href);
            if (!refreshed.ok) throw new Error('Saved, but the table could not refresh. Reload the page to see your changes.');
            const doc = new DOMParser().parseFromString(await refreshed.text(), 'text/html');
            const summary = doc.querySelector('.period-summary-card');
            const rows = doc.querySelector('[data-live-container="requirements-table"]');
            if (!summary || !rows) throw new Error('Saved. Reload the page to see your changes.');
            const selected = new Set([...document.querySelectorAll('.requirement-select:checked')].map(box => box.closest('tr').dataset.rowId));
            document.querySelector('.period-summary-card').replaceWith(summary);
            document.querySelector('[data-live-container="requirements-table"]').replaceWith(rows);
            rows.querySelectorAll('tr[data-row-id]').forEach(row => { row.querySelector('.requirement-select').checked = selected.has(row.dataset.rowId); });
            const id = opener.closest('tr').dataset.rowId;
            opener = [...rows.querySelectorAll('tr[data-row-id]')].find(row => row.dataset.rowId === id)?.querySelector('[data-edit-requirement]');
            dialog.close();
            document.querySelector('.requirement-save-status').textContent = 'Requirement saved.';
        } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;
        } finally {
            busy = false;
            save.disabled = false;
            save.removeAttribute('aria-busy');
        }
    });
})();
