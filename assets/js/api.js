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

        if (normalizedEndpoint === APP_CONFIG.fretesManuais || normalizedEndpoint === APP_CONFIG.custosJanuaria) {
            throw freightApiError(response.status, body);
        }

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

// Os GETs dos relatórios mantêm seu comportamento. PUT usa o mesmo token/base,
// sem retries: resultado incerto exige reconciliação com uma nova consulta.
function freightApiError(status, body) {
    const messages = {
        401: "Sessão ausente ou expirada. Entre novamente pela CENTRAL.",
        403: "Sem permissão comercial.frete.editar para esta operação.",
        409: "O registro foi alterado por outra pessoa ou seus dados mudaram. Consulte novamente e revise os valores.",
        422: "Dados inválidos ou identificação inconsistente. Confira os valores informados.",
        503: "CENTRAL ou banco indisponível. Aguarde e consulte novamente."
    };
    const detail = body?.detail ?? body?.mensagem;
    const description = typeof detail === "string" ? detail : Array.isArray(detail)
        ? detail.map(item => typeof item?.msg === "string" ? item.msg : "Dado inválido").join("; ") : "";
    const error = new Error([messages[status] || `Erro na API de fretes: ${status}.`, description].filter(Boolean).join(" "));
    error.status = status;
    return error;
}

async function apiPut(endpoint, payload, options = {}) {
    const token = getPortalToken();
    if (!token || APP_CONFIG.auth?.mode !== "portal-token") {
        throw freightApiError(401);
    }
    const base = String(APP_CONFIG.API_URL || "").replace(/\/+$/, "");
    if (!base || typeof endpoint !== "string" || !endpoint.startsWith("/api/") || endpoint.includes("?")) {
        throw new Error("Endpoint da API não configurado corretamente.");
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 45000);
    const abort = () => controller.abort();
    options.signal?.addEventListener("abort", abort, {once:true});
    if (options.signal?.aborted) controller.abort();
    try {
        const response = await fetch(base + endpoint, {
            method:"PUT", signal:controller.signal, cache:"no-store", credentials:"omit",
            headers:{Accept:"application/json", "Content-Type":"application/json", Authorization:`Bearer ${token}`},
            body:JSON.stringify(payload)
        });
        let body;
        try { body = await response.json(); }
        catch (_) {
            const error = freightApiError(response.status);
            error.uncertain = response.ok || response.status >= 500;
            throw error;
        }
        if (!response.ok) {
            const error = freightApiError(response.status, body);
            error.uncertain = response.status >= 500;
            throw error;
        }
        return body;
    } catch (error) {
        if (error.status) throw error;
        const uncertain = new Error("Não foi possível confirmar o salvamento. Não reenvie: consulte novamente e confira os valores no servidor.");
        uncertain.uncertain = true;
        throw uncertain;
    } finally {
        clearTimeout(timeout);
        options.signal?.removeEventListener("abort", abort);
    }
}
