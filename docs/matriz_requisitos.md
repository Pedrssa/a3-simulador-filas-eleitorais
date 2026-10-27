# Matriz de requisitos do enunciado (A3: Filas de Prioridade)

Fonte: PDF "A3 – Projeto Semestral – Filas de Prioridade" (2 páginas), apresentação até 24/11/2026.

| # | Requisito do PDF | Onde é atendido | Evidência | Situação |
|---|---|---|---|---|
| 1 | Levantamento de cenário real | Seção eleitoral; [regras_eleitorais.md](regras_eleitorais.md) | fontes oficiais consultadas em 27/10/2026 | Atendido |
| 2 | Escopo: regras de negócio e cálculo de criticidade | [relatorio_tecnico.md §2](relatorio_tecnico.md), `domain/prioridade.py` | `test_prioridade.py` | Atendido |
| 3 | Mecanismo de justiça contra starvation (aging/cotas) | `PoliticaAging`, `PoliticaCotas` (modo LAB) | `test_comparacao_usa_a_mesma_carga_e_aging_reduz_espera_dos_comuns` | Atendido (com ressalva legal documentada) |
| 4 | Métricas de SLA: espera real × janela tolerada | `ServicoMetricas`, aba D | `test_metricas_incluem_quem_ainda_espera` | Atendido (metas = hipóteses) |
| 5 | Python + POO obrigatória | camadas domain/application/infrastructure/ui | [dicionario_e_uml.md](dicionario_e_uml.md) | Atendido |
| 6 | Interface web interativa em Streamlit | `app.py`, `secao8bit/ui` | `test_interface.py`, verificação visual | Atendido |
| 7 | Monitoramento visual em tempo real da fila e dos atendimentos | aba A (Canvas), aba C | `test_cena_reflete_exatamente_o_estado_do_motor` | Atendido |
| 8 | Logs em SQL na inserção e no atendimento, com estado da fila | `ENTRADA_FILA` e `SAIDA_FILA` com `ordem_fila` e `tamanho_fila` em `dados_json` | `test_invariantes_e_ninguem_duplicado` (entradas = saídas) | Atendido |
| 9 | Arquivo `.sql` legível e executável (schema.sql / logs.sql) | `sql/schema.sql`, `sql/logs.sql`, botão na aba E | `test_exportacao_importacao_em_banco_vazio_e_equivalencia` | Atendido |
| 10 | Repositório público no GitHub com commits distribuídos | — | — | **Pendente da equipe** (não simulamos autores) |
| 11 | README com instruções de execução | `README.md` | — | Atendido |
| 12 | Relatório técnico formal (problema, regras, justificativa do algoritmo) | [relatorio_tecnico.md](relatorio_tecnico.md) | — | Atendido (pode ser formatado em .docx/.pdf pela equipe) |
| 13 | Diagrama de classes UML completo (atributos, métodos, visibilidade, relações) | [dicionario_e_uml.md](dicionario_e_uml.md) (Mermaid) | — | Atendido |
| 14 | Dicionário de métodos, classes e estruturas | [dicionario_e_uml.md](dicionario_e_uml.md) | — | Atendido |
| 15 | Demonstração ao vivo: anti-starvation, SLA, histórico | cenários `demo_7min` e `starvation`; abas D e E | roteiro | Atendido |
| 16 | Teste de estresse | cenário `starvation`, "Aumento de movimento", "Gerar chegadas" | `test_invariantes_e_ninguem_duplicado[starvation-*]` | Atendido |
| 17 | Apresentação de 20 min (3 pitch + 7 demo + 10 arguição) | [roteiro_apresentacao.md](roteiro_apresentacao.md) | — | Roteiro pronto; ensaio pendente da equipe |
| 18 | Cada integrante explica trechos do código e as complexidades | perguntas por área no roteiro | — | **Depende da equipe** |
| 19 | Grupos de até 6 integrantes | roteiro com 6 áreas | — | — |
| 20 | Desclassificatório: plágio integral | código e modelagem próprios deste projeto | — | Atendido |
