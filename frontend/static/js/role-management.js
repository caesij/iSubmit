
document.addEventListener('DOMContentLoaded', () => {
    const picker = document.querySelector('.role-picker');
    const search = document.getElementById('role-picker-search');
    if (picker && search) {
        const links = Array.from(picker.querySelectorAll('.settings-tab'));
        const empty = picker.querySelector('.role-picker-no-results');
        let roleType = 'all';
        const filters = picker.querySelectorAll('[data-role-filter]');
        const filterRoles = () => {
            const query = search.value.trim().toLocaleLowerCase();
            links.forEach(link => {
                link.hidden = !link.querySelector('span').textContent.toLocaleLowerCase().includes(query)
                    || (roleType !== 'all' && link.dataset.roleType !== roleType);
            });
            empty.hidden = !links.length || links.some(link => !link.hidden);
        };
        search.addEventListener('input', filterRoles);
        filters.forEach(button => button.addEventListener('click', () => {
            roleType = button.dataset.roleFilter;
            filters.forEach(filter => filter.setAttribute('aria-pressed', String(filter === button)));
            filterRoles();
        }));
        document.addEventListener('click', event => {
            if (!picker.contains(event.target)) picker.open = false;
        });
        picker.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                picker.open = false;
                picker.querySelector('summary').focus();
            }
        });
    }
    const pageToggles = document.querySelectorAll('[data-page-toggle]');

    pageToggles.forEach((pageToggle) => {
        const pageCard = pageToggle.closest('[data-permission-page]');

        if (!pageCard) {
            return;
        }

        const operations = pageCard.querySelectorAll(
            '[data-page-operation]'
        );

        function synchronizeOperations() {
            const pageEnabled = pageToggle.checked;

            operations.forEach((operation) => {
                operation.disabled = !pageEnabled;

                if (!pageEnabled) {
                    operation.checked = false;
                }
            });
        }

        pageToggle.addEventListener(
            'change',
            synchronizeOperations
        );

        synchronizeOperations();
    });
});
