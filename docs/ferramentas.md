# Ferramentas e versões

O projeto roda apenas com o que está em `requirements.txt`.

| Item | Versão | Uso |
|---|---|---|
| Python | 3.14.3 (compatível com 3.12+) | linguagem |
| Streamlit | 1.66.1 | interface; `st.fragment(run_every=…)` como relógio da interface; `components.v1.declare_component` para o componente HTML/JS da cena, sem etapa de build |
| pytest | 9.1.1 | testes |
| sqlite3 | biblioteca padrão | persistência de auditoria |
| pandas / pyarrow / altair | instalados como dependências do Streamlit | tabelas e gráficos |

## Decisões de API

- Componente da cena: protocolo `streamlit:componentReady`, `streamlit:render`, `streamlit:setFrameHeight` e
  `streamlit:setComponentValue`, conferido no código-fonte do Streamlit 1.66.1. O iframe persiste entre reruns
  (mesma `key`), então a animação continua de onde estava.
- Tema visual em `.streamlit/config.toml`, com opções do próprio Streamlit (`[theme]`), sem CSS de terceiros.
- Fonte da cena: bitmap 5×7 própria (`assets/cena8bit/fonte.js`), sem fontes externas. Funciona offline.

## Fontes oficiais

As páginas do TSE e do TRE-PR recusam clientes automatizados (HTTP 403). O texto foi lido num navegador comum
em 27/10/2026, e os trechos usados estão citados por artigo em `docs/regras_eleitorais.md`.
