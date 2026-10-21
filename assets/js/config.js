/** Mesma integração da CENTRAL. Nunca armazenar credenciais técnicas aqui. */
const APP_CONFIG = {
  API_URL: "https://api-bi-granja.controladoriagb05.workers.dev",
  auth: {mode: "portal-token", storageKey: "granjabi_auth_token", required: true},
  endpoints: {filtros: "/api/bi/faturamento-nf/filtros", resumo: "/api/bi/faturamento-nf/resumo", detalhes: "/api/bi/faturamento-nf/detalhes"},
  fob: {filtros:"/api/comercial/comparativo-fob/filtros",resumo:"/api/comercial/comparativo-fob/resumo",detalhes:"/api/comercial/comparativo-fob/detalhes"},
  fretesManuais: "/api/comercial-html/fretes-manuais",
  custosJanuaria: "/api/comercial-html/fretes-manuais/custos-januaria"
};
