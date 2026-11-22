document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('id_assigned_programs');
    if (!select || !select.multiple) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'program-multiselect';
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.id = 'assigned-programs-toggle';
    trigger.className = 'program-multiselect-toggle';
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', 'assigned-programs-options');
    const panel = document.createElement('div');
    panel.id = 'assigned-programs-options';
    panel.className = 'program-multiselect-options';
    panel.hidden = true;
    panel.setAttribute('role', 'group');
    panel.setAttribute('aria-label', 'Assigned programs');
    const header = document.createElement('div');
    header.className = 'program-options-header';
    const heading = document.createElement('strong');
    heading.textContent = 'Select programs';
    const count = document.createElement('span');
    header.append(heading, count);
    panel.append(header);
    const splitProgram = option => {
        const parts = option.textContent.trim().split(/\s+[–—-]\s+/);
        return { code: parts[0], name: parts.slice(1).join(' - ') };
    };
    const update = () => {
        const selected = Array.from(select.selectedOptions);
        const badges = document.createElement('span');
        badges.className = 'program-selected-badges';
        if (selected.length) {
            selected.forEach(option => {
                const badge = document.createElement('span');
                badge.className = 'program-selected-badge';
                badge.textContent = splitProgram(option).code;
                badges.append(badge);
            });
        } else {
            badges.textContent = 'Select programs';
        }
        trigger.replaceChildren(badges);
        count.textContent = `${selected.length} selected`;
        trigger.setAttribute('aria-label', `Assigned programs: ${selected.length ? selected.map(option => splitProgram(option).code).join(', ') : 'none selected'}`);
        trigger.title = selected.map(option => option.textContent.trim()).join(', ');
        panel.querySelectorAll('input').forEach((checkbox, index) => {
            checkbox.checked = select.options[index].selected;
        });
    };
    for (const option of select.options) {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = option.selected;
        checkbox.disabled = option.disabled;
        checkbox.addEventListener('change', () => {
            option.selected = checkbox.checked;
            select.dispatchEvent(new Event('change', { bubbles: true }));
        });
        const text = document.createElement('span');
        text.className = 'program-option-copy';
        const program = splitProgram(option);
        const code = document.createElement('strong');
        code.textContent = program.code;
        text.append(code);
        if (program.name) {
            const description = document.createElement('span');
            description.textContent = program.name;
            text.append(description);
        }
        label.append(checkbox, text);
        panel.append(label);
    }
    if (!select.options.length) panel.textContent = 'No programs available.';
    const close = () => {
        panel.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
    };
    trigger.addEventListener('click', () => {
        panel.hidden = !panel.hidden;
        trigger.setAttribute('aria-expanded', String(!panel.hidden));
    });
    wrapper.addEventListener('keydown', event => {
        if (event.key === 'Escape') { close(); trigger.focus(); }
        if (event.key === 'ArrowDown' && event.target === trigger) {
            event.preventDefault();
            panel.hidden = false;
            trigger.setAttribute('aria-expanded', 'true');
            panel.querySelector('input:not(:disabled)')?.focus();
        }
    });
    document.addEventListener('click', event => { if (!wrapper.contains(event.target)) close(); });
    wrapper.addEventListener('focusout', event => { if (!wrapper.contains(event.relatedTarget)) close(); });
    select.addEventListener('change', update);
    select.form?.addEventListener('reset', () => window.setTimeout(update, 0));
    select.insertAdjacentElement('afterend', wrapper);
    wrapper.append(trigger, panel);
    const fieldLabel = document.querySelector('label[for="id_assigned_programs"]');
    if (fieldLabel) fieldLabel.htmlFor = trigger.id;
    trigger.disabled = select.disabled;
    select.hidden = true;
    update();
});
