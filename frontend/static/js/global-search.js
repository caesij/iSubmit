
(function () {
    const searchRoot = document.querySelector("[data-global-search]");

    if (!searchRoot) {
        return;
    }

    const input = searchRoot.querySelector("[data-global-search-input]");
    const dropdown = searchRoot.querySelector("[data-global-search-dropdown]");
    const menu = searchRoot.querySelector("[data-global-search-menu]");
    const suggestionsUrl = searchRoot.dataset.suggestionsUrl;

    if (!input || !dropdown || !menu || !suggestionsUrl) {
        return;
    }

    const advancedInputs = searchRoot.querySelectorAll(
        '[name="faculty_name"], [name="document_title"]'
    );

    let timer = null;
    let request = null;

    function openDropdown() {
        dropdown.hidden = false;
        input.setAttribute("aria-expanded", "true");
    }

    function closeDropdown() {
        dropdown.hidden = true;
        menu.hidden = true;
        menu.innerHTML = "";

        input.setAttribute("aria-expanded", "false");

        clearTimeout(timer);

        if (request) {
            request.abort();
            request = null;
        }
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function renderGroup(title, items) {
        if (!items || !items.length) {
            return "";
        }

        return `
            <section class="global-search-group">
                <h2>${escapeHtml(title)}</h2>

                ${items.map(item => `
                    <a
                        class="global-search-result"
                        href="${escapeHtml(item.url)}"
                    >
                        ${escapeHtml(item.label)}
                    </a>
                `).join("")}
            </section>
        `;
    }

    function renderDocuments(items) {
        if (!items || !items.length) {
            return "";
        }

        return `
            <section class="global-search-group">
                <h2>Documents</h2>

                ${items.map(document => `
                    <div class="global-search-document-result">
                        <small class="global-search-document-category">
                            ${escapeHtml(document.category || "Document")}
                        </small>

                        <a
                            class="global-search-result"
                            href="${escapeHtml(document.url)}"
                        >
                            ${escapeHtml(document.label)}
                        </a>

                        ${document.faculty_name ? `
                            <small class="global-search-document-owner">
                                Faculty:

                                ${document.faculty_url ? `
                                    <a href="${escapeHtml(document.faculty_url)}">
                                        ${escapeHtml(document.faculty_name)}
                                    </a>
                                ` : escapeHtml(document.faculty_name)}
                            </small>
                        ` : ""}
                    </div>
                `).join("")}
            </section>
        `;
    }

    function getResultsUrl(query) {
        const url = new URL(searchRoot.action, window.location.origin);

        url.searchParams.set("q", query);

        advancedInputs.forEach(field => {
            const value = field.value.trim();

            if (value) {
                url.searchParams.set(field.name, value);
            }
        });

        return url.toString();
    }

    function renderResults(data, query) {
        const groups = [
            renderGroup("Pages", data.pages),
            renderGroup("Faculty", data.faculty),
            renderGroup("Requirements", data.requirements),
            renderDocuments(data.documents),
        ].filter(Boolean);

        const resultsHtml = groups.length
            ? groups.join("")
            : `
                <div class="global-search-empty">
                    No matching results found.
                </div>
            `;

        menu.innerHTML = `
            ${resultsHtml}

            <a
                class="global-search-view-all"
                href="${escapeHtml(getResultsUrl(query))}"
            >
                View all search results
            </a>
        `;

        menu.hidden = false;
    }

    async function loadSuggestions(query) {
        if (request) {
            request.abort();
        }

        const controller = new AbortController();
        request = controller;

        const url = new URL(suggestionsUrl, window.location.origin);
        url.searchParams.set("q", query);

        advancedInputs.forEach(field => {
            const value = field.value.trim();

            if (value) {
                url.searchParams.set(field.name, value);
            }
        });

        try {
            const response = await fetch(url.toString(), {
                method: "GET",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
                cache: "no-store",
                signal: controller.signal,
            });

            if (!response.ok) {
                throw new Error("Search suggestions failed.");
            }

            const data = await response.json();

            if (request === controller) {
                renderResults(data, query);
            }

        } catch (error) {
            if (error.name !== "AbortError" && request === controller) {
                console.error(error);

                menu.innerHTML = `
                    <div class="global-search-empty">
                        Unable to load search results. Please try again.
                    </div>
                `;

                menu.hidden = false;
            }
        } finally {
            if (request === controller) {
                request = null;
            }
        }
    }

    function scheduleSuggestions() {
        openDropdown();
        clearTimeout(timer);

        const query = input.value.trim();

        if (query.length < 2) {
            if (request) {
                request.abort();
                request = null;
            }

            menu.innerHTML = "";
            menu.hidden = true;
            return;
        }

        timer = setTimeout(function () {
            loadSuggestions(query);
        }, 250);
    }

    input.addEventListener("focus", openDropdown);
    input.addEventListener("click", openDropdown);
    input.addEventListener("input", scheduleSuggestions);

    // Refresh suggestions when advanced filters change.
    advancedInputs.forEach(field => {
        field.addEventListener("input", scheduleSuggestions);
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeDropdown();
            input.blur();
        }
    });

    searchRoot.addEventListener("submit", function () {
        clearTimeout(timer);

        if (request) {
            request.abort();
            request = null;
        }
    });

    document.addEventListener("click", function (event) {
        if (!searchRoot.contains(event.target)) {
            closeDropdown();
        }
    });
})();
