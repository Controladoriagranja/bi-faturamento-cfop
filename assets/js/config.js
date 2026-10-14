/** Mesma integração da CENTRAL. Nunca armazenar credenciais técnicas aqui. */
const APP_CONFIG = {
  API_URL: "https://api-bi-granja.controladoriagb05.workers.dev",
  auth: {mode: "portal-token", storageKey: "granjabi_auth_token", required: true},
  endpoints: {filtros: "/api/bi/faturamento-nf/filtros", resumo: "/api/bi/faturamento-nf/resumo"}
};
