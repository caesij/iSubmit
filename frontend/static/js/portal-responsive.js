/* Shared progressive enhancement for the existing portal navigation and tables. */
(() => {
    const mobile = window.matchMedia('(max-width: 1024px)');
    const sidebar = document.getElementById('portal-sidebar');
    const toggle = document.querySelector('.mobile-nav-toggle');
    const close = document.querySelector('.mobile-nav-close');
    const overlay = document.querySelector('.mobile-nav-overlay');
    const main = document.querySelector('.main-area');
    if (!sidebar || !toggle || !close || !overlay || !main) return;

    document.documentElement.classList.add('portal-enhanced');
    let returnFocus;
    const focusable = () => [...sidebar.querySelectorAll('a[href], button:not([disabled]), [tabindex="0"]')]
        .filter(element => element.getClientRects().length);

    function setOpen(open, restoreFocus = true) {
        open = mobile.matches && open;
        const wasOpen = document.body.classList.contains('mobile-nav-open');
        if (open && !wasOpen) returnFocus = document.activeElement;
        document.body.classList.toggle('mobile-nav-open', open);
        toggle.setAttribute('aria-expanded', String(open));
        overlay.hidden = !open;
        sidebar.inert = mobile.matches && !open;
        main.inert = open;
        if (mobile.matches) {
            sidebar.setAttribute('role', 'dialog');
            sidebar.setAttribute('aria-modal', 'true');
        } else {
            sidebar.removeAttribute('role');
            sidebar.removeAttribute('aria-modal');
        }
        if (open) close.focus();
        else if (wasOpen && restoreFocus && mobile.matches) (returnFocus || toggle).focus();
    }

    function adaptTables() {
        if (mobile.matches) {
            document.querySelectorAll('.content-shell table').forEach(table => {
                if (table.parentElement.classList.contains('responsive-table-scroll')) return;
                const region = document.createElement('div');
                region.className = 'responsive-table-scroll';
                region.tabIndex = 0;
                region.setAttribute('role', 'region');
                region.setAttribute('aria-label', table.getAttribute('aria-label') || 'Scrollable table');
                table.before(region);
                region.append(table);
            });
        } else {
            document.querySelectorAll('.responsive-table-scroll').forEach(region => region.replaceWith(...region.childNodes));
        }
    }

    toggle.addEventListener('click', () => setOpen(true));
    close.addEventListener('click', () => setOpen(false));
    overlay.addEventListener('click', () => setOpen(false));
    sidebar.addEventListener('click', event => {
        if (event.target.closest('a[href]')) setOpen(false);
    });
    document.addEventListener('keydown', event => {
        if (!document.body.classList.contains('mobile-nav-open')) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            setOpen(false);
        } else if (event.key === 'Tab') {
            const items = focusable();
            const first = items[0], last = items[items.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault(); last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault(); first.focus();
            }
        }
    });
    mobile.addEventListener('change', () => { setOpen(false); adaptTables(); });
    setOpen(false, false);
    adaptTables();
})();
