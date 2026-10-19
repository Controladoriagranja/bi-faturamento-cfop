/**
 * Cliente HTTP do BI Zootécnico.
 * O navegador nunca conecta diretamente no PostgreSQL e não lê Parquet.
 */
function getPortalToken() {
    const auth = APP_CONFIG.auth || {};
    if (auth.mode !== "portal-token") return "";

    try {
        return sessionStorage.getItem(auth.storageKey || "granjabi_auth_token") || "";
    } catch (_) {
        return "";
    }
}

async function apiGet(endpoint, params = {}, options = {}) {
    if (!endpoint) {
        throw new Error("Endpoint da API não informado.");
    }

    const baseUrl = String(APP_CONFIG.API_URL || "").replace(/\/+$/, "");
    if (!baseUrl) {
        throw new Error("APP_CONFIG.API_URL não configurada.");
    }

    const auth = APP_CONFIG.auth || { mode: "none", required: false };
    const token = getPortalToken();

    if (auth.mode === "portal-token" && auth.required && !token) {
        throw new Error(
            "Sessão do Portal BI não encontrada. Entre pelo Portal BI e abra o relatório novamente."
        );
    }

    const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const url = new URL(baseUrl + normalizedEndpoint);

    Object.entries(params || {}).forEach(([key, value]) => {
        if (value === null || value === undefined || value === "") return;

        if (Array.isArray(value)) {
            value.forEach((item) => {
                if (item !== null && item !== undefined && item !== "") {
                    url.searchParams.append(key, String(item));
                }
            });
            return;
        }

        url.searchParams.append(key, String(value));
    });

    const headers = {
        Accept: "application/json",
        ...(options.headers || {})
    };

    if (auth.mode === "portal-token" && token) {
        headers.Authorization = `Bearer ${token}`;
    }

    let response;
    try {
        response = await fetch(url.toString(), {
            method: "GET",
            signal: options.signal,
            cache: options.cache || "no-store",
            headers
        });
    } catch (error) {
        if (error?.name === "AbortError") throw error;
        throw new Error(
            "Não foi possível conectar à API do BI. Verifique a internet e a disponibilidade da Cloudflare/API."
        );
    }

    if (!response.ok) {
        let body = null;
        try { body = await response.json(); } catch (_) {}

        if (response.status === 401) {
            throw new Error(
                body?.detail || body?.mensagem ||
                "Sessão inválida ou expirada. Entre novamente no Portal BI."
            );
        }

        if (response.status === 403) {
            throw new Error(
                body?.detail || body?.mensagem ||
                "Você não possui permissão para acessar este relatório."
            );
        }

        if (response.status === 404) {
            if (normalizedEndpoint.startsWith("/api/comercial/comparativo-fob/")) {
                throw new Error("O módulo Comparativo FOB ainda não está disponível na API. Instale o pacote do Anderson e confira o encaminhamento desta rota no Worker.");
            }
            if (normalizedEndpoint.endsWith("/detalhes")) {
                throw new Error("O detalhamento ainda não está disponível nessa API. Atualize o módulo de Faturamento no backend e confira a rota de detalhes no Worker.");
            }
            throw new Error("O módulo de Faturamento ainda não está disponível nessa API. Confira a implantação das rotas pelo Portal BI.");
        }

        const detail = body?.detail || body?.mensagem || body?.erro || "";
        throw new Error(`Erro na API: ${response.status}${detail ? ` - ${detail}` : ""}`);
    }

    return response.json();
}
