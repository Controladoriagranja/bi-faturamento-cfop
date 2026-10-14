/**
 * Componente técnico adaptado da referência; não calcula indicadores.
 */
// Stateless: dataset and filter state belong to the calling screen.
window.opcoesDisponiveis = (campo, dataset, filtrosAtivos, corresponde, valor) =>
    [...new Set(dataset.filter(row => corresponde(row, filtrosAtivos, campo))
        .map(row => valor(row, campo)).filter(v => v !== null && v !== undefined && String(v).trim() !== "")
        .map(String))].sort((a, b) => a.localeCompare(b, "pt-BR", { numeric: true }));

class FilterController {
    constructor({
        fields,
        onChange,
        includeDependentRefresh = true,
        contextProvider = null,
        filtersEndpoint = null,
        optionsProvider = null
    }) {
        this.fields = fields;
        this.optionsProvider = optionsProvider;
        this.onChange = onChange;
        this.includeDependentRefresh = includeDependentRefresh;
        this.contextProvider = contextProvider;
        this.filtersEndpoint = filtersEndpoint || APP_CONFIG.endpoints.filtros;
        this.silent = false;
        this.refreshController = null;
        this.refreshId = 0;
        this.changeId = 0;
        this.multiState = new Map();

        document.addEventListener("click", event => {
            if (!event.target.closest(".checkbox-multiselect")) {
                this.closeAll();
            }
        });
    }

    normalizeArray(value) {
        if (Array.isArray(value)) {
            return value.map(String).filter(Boolean);
        }

        if (value === null || value === undefined || value === "") {
            return [];
        }

        return [String(value)];
    }

    values() {
        const data = {};

        this.fields.forEach(field => {
            if (field.multi) {
                const state = this.multiState.get(field.apiKey);
                const selected = state ? [...state.selected] : [];

                if (selected.length) {
                    data[field.apiKey] = selected;
                }

                return;
            }

            const select = document.getElementById(field.id);
            const value = select?.value || "";

            if (value !== "") {
                data[field.apiKey] = value;
            }
        });

        return data;
    }

    getState(field) {
        let state = this.multiState.get(field.apiKey);

        if (!state) {
            state = {
                selected: new Set(),
                options: [],
                host: null,
                button: null,
                panel: null,
                list: null,
                search: null
            };

            this.multiState.set(field.apiKey, state);
        }

        return state;
    }

    escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    summary(state) {
        const selected = [...state.selected];

        if (!selected.length) {
            return "Todos";
        }

        if (selected.length === 1) {
            return (
                state.options.find(item => item.value === selected[0])?.label
                || selected[0]
            );
        }

        return `${selected.length} selecionados`;
    }

    updateButton(field) {
        const state = this.getState(field);

        if (!state.button) {
            return;
        }

        state.button
            .querySelector(".checkbox-multiselect-label")
            .textContent = this.summary(state);

        state.button.classList.toggle(
            "has-selection",
            state.selected.size > 0
        );
    }

    closeAll(except = null) {
        this.multiState.forEach(state => {
            if (state.host && state.host !== except) {
                state.host.classList.remove("open");
                state.button?.setAttribute("aria-expanded", "false");
            }
        });
    }

    buildMulti(field) {
        const host = document.getElementById(field.id);

        if (!host) {
            return null;
        }

        const state = this.getState(field);

        if (state.host) {
            return state;
        }

        host.innerHTML = `
            <button
                class="checkbox-multiselect-trigger"
                type="button"
                aria-haspopup="listbox"
                aria-expanded="false"
            >
                <span class="checkbox-multiselect-label">Todos</span>
                <span class="checkbox-multiselect-chevron">▾</span>
            </button>

            <div class="checkbox-multiselect-panel">
                ${
                    field.search
                    ? `
                        <div class="checkbox-multiselect-search-wrap">
                            <input
                                class="checkbox-multiselect-search"
                                type="search"
                                placeholder="Pesquisar..."
                                autocomplete="off"
                            >
                        </div>
                    `
                    : ""
                }

                <div class="checkbox-multiselect-list"></div>
            </div>
        `;

        state.host = host;
        state.button = host.querySelector(".checkbox-multiselect-trigger");
        state.panel = host.querySelector(".checkbox-multiselect-panel");
        state.list = host.querySelector(".checkbox-multiselect-list");
        state.search = host.querySelector(".checkbox-multiselect-search");

        state.button.addEventListener("click", event => {
            event.stopPropagation();

            const open = !host.classList.contains("open");
            this.closeAll(host);
            host.classList.toggle("open", open);
            state.button.setAttribute("aria-expanded", String(open));

        });

        state.panel.addEventListener("click", event => {
            event.stopPropagation();
        });

        if (state.search) {
            state.search.addEventListener("input", () => {
                const query = state.search.value
                    .trim()
                    .toLocaleLowerCase("pt-BR");

                state.list
                    .querySelectorAll("[data-filter-option]")
                    .forEach(row => {
                        const label = row.dataset.filterLabel
                            .toLocaleLowerCase("pt-BR");

                        row.hidden =
                            Boolean(query)
                            && !label.includes(query);
                    });
            });
        }

        return state;
    }

normalizeOptions(field, raw) {
    return raw.map(item => ({
        value: String(typeof item === "object" ? item.value ?? item.valor : item),
        label: String(typeof item === "object" ? item.label ?? item.nome ?? item.value ?? item.valor : item)
    }));
}
    renderMultiOptions(field, options, selected) {
        const state = this.buildMulti(field);

        if (!state) {
            return;
        }

        // API options are availability, never the source of selected values.
        state.options = options;
        if (selected !== undefined) {
            state.selected = new Set(this.normalizeArray(selected));
        }

        const available = new Set(options.map(option => option.value));
        state.selected = new Set([...state.selected].filter(value => available.has(value)));
        state.displayOptions = options;

        const allSelected =
            options.length > 0
            && state.selected.size === options.length;

        state.list.innerHTML = `
            <label
                class="checkbox-option checkbox-option-all"
                data-filter-option
                data-filter-label="Selecionar tudo"
            >
                <input
                    type="checkbox"
                    data-all
                    ${allSelected ? "checked" : ""}
                >
                <span>Selecionar tudo</span>
            </label>

            ${
                options.map(option => `
                    <label
                        class="checkbox-option"
                        data-filter-option
                        data-filter-label="${this.escapeHtml(option.label)}"
                    >
                        <input
                            type="checkbox"
                            value="${this.escapeHtml(option.value)}"
                            ${
                                state.selected.has(option.value)
                                ? "checked"
                                : ""
                            }
                        >
                        <span>${this.escapeHtml(option.label)}</span>
                    </label>
                `).join("")
            }
        `;

        const allInput =
            state.list.querySelector(
                "[data-all]"
            );

        const optionInputs = [
            ...state.list.querySelectorAll(
                'input[type="checkbox"]:not([data-all])'
            )
        ];

        const syncSelectAll = () => {
            allInput.checked =
                options.length > 0
                && state.selected.size === options.length;

            allInput.indeterminate =
                state.selected.size > 0
                && state.selected.size < options.length;
        };

        allInput.addEventListener(
            "change",
            async () => {
                if (this.silent) {
                    return;
                }

                state.selected.clear();

                if (allInput.checked) {
                    options.forEach(option => {
                        state.selected.add(
                            option.value
                        );
                    });
                }

                optionInputs.forEach(input => {
                    input.checked =
                        state.selected.has(
                            input.value
                        );
                });

                syncSelectAll();
                this.updateButton(field);
                await this.emitChange();
            }
        );

        optionInputs.forEach(input => {
            input.addEventListener(
                "change",
                async () => {
                    if (this.silent) {
                        return;
                    }

                    if (input.checked) {
                        state.selected.add(
                            input.value
                        );
                    }
                    else {
                        state.selected.delete(
                            input.value
                        );
                    }

                    syncSelectAll();
                    this.updateButton(field);
                    await this.emitChange();
                }
            );
        });

        syncSelectAll();
        this.updateButton(field);
    }

    async loadOptions({
        preserve = true
    } = {}) {
        const requestId = ++this.refreshId;
        const ownCurrent = preserve ? this.values() : {};

        const current = {
            ...(
                this.contextProvider
                ? this.contextProvider()
                : {}
            ),
            ...ownCurrent
        };

        if (this.refreshController) {
            this.refreshController.abort();
        }

        this.refreshController = new AbortController();

        const response = this.optionsProvider ? await this.optionsProvider(current) : await apiGet(
            this.filtersEndpoint,
            current,
            {
                signal: this.refreshController.signal
            }
        );

        if (requestId !== this.refreshId) {
            return false;
        }

        // Read live selections after await; never restore a stale snapshot.
        const latest = this.values();
        this.silent = true;

        try {
            for (const field of this.fields) {
                const options = this.normalizeOptions(
                    field,
                    response[field.apiKey] || []
                );

                if (field.multi) {
                    this.renderMultiOptions(
                        field,
                        options,
                        latest[field.apiKey] || []
                    );
                    continue;
                }

                const select = document.getElementById(field.id);

                if (!select) {
                    continue;
                }

                const currentValue = latest[field.apiKey]
                    ? String(latest[field.apiKey])
                    : "";

                select.innerHTML = "";

                const allOption = document.createElement("option");
                allOption.value = "";
                allOption.textContent = "Todos";
                select.appendChild(allOption);

                options.forEach(option => {
                    const el = document.createElement("option");
                    el.value = option.value;
                    el.textContent = option.label;
                    select.appendChild(el);
                });

                select.value = (
                    currentValue
                    && [...select.options]
                        .some(option => option.value === currentValue)
                )
                    ? currentValue
                    : "";
            }
        }
        finally {
            this.silent = false;
        }
        if (JSON.stringify(latest) !== JSON.stringify(this.values())) {
            return this.loadOptions({ preserve: true });
        }
    }

    invalidateRefresh() {
        ++this.refreshId;
        ++this.changeId;
        this.refreshController?.abort();
    }

    set(apiKey, value) {
        const field = this.fields.find(
            item => item.apiKey === apiKey
        );

        if (!field) {
            return;
        }

        this.invalidateRefresh();
        if (field.multi) {
            const state = this.getState(field);
            state.selected = new Set(this.normalizeArray(value));

            if (state.host || state.options.length) {
                this.renderMultiOptions(
                    field,
                    state.options,
                    [...state.selected]
                );
            }

            return;
        }

        const select = document.getElementById(field.id);

        if (select) {
            select.value = String(value ?? "");
        }
    }

    clear() {
        this.invalidateRefresh();
        this.silent = true;

        try {
            this.fields.forEach(field => {
                if (field.multi) {
                    const state = this.getState(field);
                    state.selected.clear();

                    if (state.host || state.options.length) {
                        this.renderMultiOptions(
                            field,
                            state.options,
                            []
                        );
                    }

                    return;
                }

                const select = document.getElementById(field.id);

                if (select) {
                    select.value = "";
                }
            });
        }
        finally {
            this.silent = false;
        }
    }

    async emitChange() {
        if (this.silent) {
            return;
        }

        const changeId = ++this.changeId;
        if (this.includeDependentRefresh) {
            try {
                const applied = await this.loadOptions({
                    preserve: true
                });
                if (applied === false) return;
            }
            catch (error) {
                if (error.name === "AbortError") return;
                console.error(
                    "Erro ao atualizar filtros dependentes:",
                    error
                );
            }
        }

        if (changeId === this.changeId && this.onChange) {
            this.onChange(this.values());
        }
    }

    register() {
        this.fields.forEach(field => {
            if (field.multi) {
                this.buildMulti(field);
                return;
            }

            const select = document.getElementById(field.id);

            if (!select) {
                return;
            }

            select.addEventListener("change", async () => {
                await this.emitChange();
            });
        });
    }
}
