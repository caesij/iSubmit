
document.addEventListener('DOMContentLoaded', () => {
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
