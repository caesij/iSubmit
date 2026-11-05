(function () {
    const searchRoot = document.querySelector("[data-global-search]");
    if (!searchRoot) {
        return;
    }

    const input = searchRoot.querySelector("[data-global-search-input]");
    const menu = searchRoot.querySelector("[data-global-search-menu]");
    const suggestionsUrl = searchRoot.dataset.suggestionsUrl;
    const resultsUrl = searchRoot.dataset.resultsUrl;
    let timer;
    let request;

    function closeMenu() {
        menu.hidden = true;
        menu.innerHTML = "";
    }

    function renderGroup(title, items) {
        if (!items.length) {
            return "";
        }

        return `<section class="global-search-group">
            <h2>${escapeHtml(title)}</h2>
            ${items.map((item) => `
                <a class="global-search-result" href="${escapeHtml(item.url)}">
                    ${escapeHtml(item.label)}
                </a>
            `).join("")}
        </section>`;
    }


    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function renderResults(data) {
        const documentGroups = {};

        data.documents.forEach((document) => {
            if (!documentGroups[document.category]) {
                documentGroups[document.category] = [];
            }

            documentGroups[document.category].push(document);
        });

        menu.innerHTML =
            renderGroup("Pages", data.pages) +
            renderGroup("Requirements", data.requirements) +
            Object.entries(documentGroups)
                .map(([category, items]) => renderGroup(category, items))
                .join("");

        menu.hidden = !menu.innerHTML;
    }

    async function loadSuggestions(query) {
        if (request) {
            request.abort();
        }

        request = new AbortController();
        try {
            const response = await fetch(
                `${suggestionsUrl}?q=${encodeURIComponent(query)}`,
                {
                    headers: {"X-Requested-With": "XMLHttpRequest"},
                    signal: request.signal,
                },
            );
            if (!response.ok) {
                throw new Error("Search suggestions failed.");
            }
            renderResults(await response.json());
        } catch (error) {
            if (error.name !== "AbortError") {
                console.error(error);
                closeMenu();
            }
        }
    }

    input.addEventListener("input", function () {
        clearTimeout(timer);
        const query = input.value.trim();
        if (query.length < 2) {
            closeMenu();
            return;
        }
        timer = setTimeout(() => loadSuggestions(query), 250);
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && input.value.trim()) {
            event.preventDefault();
            window.location.href =
                `${resultsUrl}?q=${encodeURIComponent(input.value.trim())}`;
        }
        if (event.key === "Escape") {
            closeMenu();
        }
    });

    document.addEventListener("click", function (event) {
        if (!searchRoot.contains(event.target)) {
            closeMenu();
        }
    });
})();
