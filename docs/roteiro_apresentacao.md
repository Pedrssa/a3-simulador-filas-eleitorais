# Roteiro da apresentação (20 minutos)

Estrutura do enunciado: **3 min** de problema, **7 min** de demonstração e **10 min** de arguição.
A demonstração não depende de sorte: o cenário `demo_7min` com seed `2026` produz sempre os mesmos eventos,
e o botão **⏭ Próxima chamada** para exatamente depois de cada pessoa sair da fila. Os números de cliques abaixo
foram medidos em ensaio técnico (10/11/2026) e são reproduzíveis.

## Preparação (antes de a banca entrar)

1. `streamlit run app.py` e navegador em tela cheia (F11). Resolução mínima testada: 1366×768.
2. Visão **1 · Entenda a fila**, com o laboratório no exemplo inicial (botão **Recomeçar**).
3. Ligue **Modo apresentação** (canto superior direito). A barra lateral some e a cena fica ao lado da explicação.
   Para voltar à barra lateral, desligue o mesmo botão.
4. Não é preciso configurar nada: **⟳ Recomeçar demo** (visão 2) carrega `demo_7min`, seed `2026`, regras eleitorais.

## 1. O problema (3 min) — visão 1 · Entenda a fila

| Tempo | Na tela | O que dizer |
|---|---|---|
| 0:00 | Texto de abertura | "Uma seção eleitoral tem **uma única urna**. Todo mundo espera numa fila, mas o art. 129 da Res. TSE 23.751/2026 manda algumas pessoas passarem à frente." |
| 0:40 | **Fila comum (FIFO)** × **Fila de prioridade** | "Numa fila comum, Ana sai primeiro porque chegou primeiro. Numa fila de prioridade, cada pessoa tem uma **chave**: primeiro o nível, depois a chegada. Carla chegou por último, mas é gestante: sai antes." |
| 1:20 | Laboratório: clique **+ Mais de 80** | "Davi entrou no fim do array, comparou com o pai e **subiu** até a raiz. É a mesma classe `FilaPrioridade` do simulador. Isso custa no máximo a altura da árvore: O(log n)." |
| 2:00 | Clique **Chamar próximo** | "A fila de prioridade chamou Davi; uma fila comum chamaria Ana. Repare: o **array** não fica em ordem — só o menor fica no índice 0. A lista de atendimento ao lado é uma cópia ordenada." |
| 2:40 | — | "A pergunta do projeto: prioridade estrita diz **quem vai primeiro**, mas não garante espera limitada. Como medir, explicar e auditar isso?" |

## 2. Demonstração (7 min) — visões 2, 3 e 4

| Tempo | Ação | O que aparece | O que dizer |
|---|---|---|---|
| 0:00 | Visão **2 · Ao vivo** → **⟳ Recomeçar demo** → **⏭ Próxima chamada** (1º clique) | 08:01, Ubiratã (E-0001) é chamado; fila vazia | "Cada movimento é um evento do motor Python; a animação só desenha. Com a fila vazia, não há o que ordenar." |
| 0:45 | **⏭ Próxima chamada** até o **9º clique** (sem parar para explicar os intermediários) | 2º clique: boca de urna e polícia acionada. 6º: grupo com 4 prioridades chega (08:16). | "Chegam pessoas com preferência. O selo **▼ PRÓXIMO** fica sobre quem a política vai chamar." |
| 2:00 | Parar no **9º clique** e ler o cartão da esquerda | 08:22, **Iara (E-0020)**, mais de 80 anos, aparece **PASSOU À FRENTE!** | Ler o cartão: "Iara chegou às 08:22, depois de Pietra e mais 10 pessoas, mas tem mais de 80 anos, e esse grupo passa à frente de todas as outras preferências (§ 3º)." |
| 2:45 | **⏭** até o **12º clique** | 10º: discussão na fila e polícia requisitada à porta. 12º: Xênia (mobilidade reduzida) passa à frente de uma doadora | "Ocorrência registrada; a urna não para; ninguém é preso por aparência. E a regra continua: preferência legal antes de doadores." |
| 3:30 | Visão **3 · Algoritmo** → aba **Heap agora: array × atendimento** | Duas tabelas lado a lado | "À esquerda, a heap como está na memória. À direita, a ordem em que serão chamados. **Não são a mesma lista**: a heap só garante pai ≤ filhos." |
| 4:15 | Aba **Código em execução** → passo mais recente com ponto *seleção* | Método `selecionar` da política (em `politicas.py`), linha destacada e a chave | "Esta é a linha real que escolheu a Xênia. A chave é (nível, chegada, seq). A **agenda de eventos** é outra heap: decide *quando*; a fila decide *quem*." |
| 5:00 | Visão **4 · Resultados** → aba **Starvation e políticas** → **Rodar comparação** | Tabela e gráfico de 4 variantes com a mesma carga | "Regra estrita: quem não tem preferência chega a **105 min**. Aging de laboratório: **85**, mas preferenciais pioram (49 → 86). Cotas empurram a espera para doadores (115). **Laboratório não é procedimento eleitoral.**" |
| 6:15 | Aba **Auditoria SQL** → **Verificar cadeia de hash** → **Validar importação** | "Cadeia de hash: … íntegros" e "Importação em banco vazio: OK" | "Cada entrada e saída da fila virou registro SQL com o estado da fila. O `logs.sql` reimporta idêntico em banco vazio." |

Momento extra, se sobrar tempo: o **15º clique** (09:05) mostra a falha de urna programada, com a luz vermelha
na cena, o Presidente religando e a indisponibilidade aparecendo em *Resultados → Métricas e SLA*.

## 3. Plano de contingência

| Falha | O que fazer |
|---|---|
| A cena (canvas) não carrega ou trava | Os cartões de explicação e a lista "Quem está esperando" (visão 2) e as tabelas da visão 3 funcionam sem a animação. Em *Exibição*, ligue **Movimento reduzido**. |
| O estado ficou confuso (alguém clicou demais) | **⟳ Recomeçar demo** e repetir os cliques: o resultado é o mesmo. |
| O Streamlit não abre | `python scripts/gerar_exemplos.py` imprime a comparação de políticas e gera `sql/logs.sql`; `python -m pytest -q` mostra a suíte passando. `docs/media/demo-secao8bit.gif` mostra a cena gravada. |
| Projetor com baixa resolução | Modo apresentação ligado; zoom do navegador em 90%. Nada depende de passar o mouse. |

## 4. Arguição (10 min): divisão para até 6 integrantes

Cada integrante deve **ter feito alterações reais** na sua área (os próprios commits) e saber explicá-las.
Não usar autores ou commits simulados.

| Integrante | Área | Arquivos | Perguntas prováveis |
|---|---|---|---|
| 1 | Regras e classificação | `domain/prioridade.py`, `docs/regras_eleitorais.md` | Por que 80 anos exatos não é "mais de 80"? Por que não há ordem entre gestante e PcD? O que acontece com o doador com 121 dias? E com o acompanhante de um candidato? |
| 2 | Heap e políticas | `domain/fila.py`, `domain/politicas.py`, `application/didatica.py` | Complexidade de inserir e extrair? Por que o array não é a ordem de atendimento? Por que o aging exige `reconstruir`? Por que as cotas são O(n)? |
| 3 | Motor de eventos | `application/motor.py`, `eventos.py` | Diferença entre agenda e fila? Onde a prioridade é aplicada? Por que não há preempção? Como a velocidade não altera o resultado? |
| 4 | Incidentes e invariantes | `motor.py` (incidentes), `domain/secao.py`, `recursos.py` | O que impede duas pessoas na urna? Por que a boca de urna não para a urna? O que acontece com a fila no encerramento? |
| 5 | Auditoria SQL | `infrastructure/*`, `application/auditoria.py`, `sql/schema.sql` | Como funciona o rollback? Por que consultas parametrizadas? Como evitar duplicação em reruns? Qual é o limite do hash encadeado? |
| 6 | Interface, explicações e cena | `ui/*`, `application/explicacao.py`, `cena.py`, `assets/cena8bit/cena.js` | Como garantir que a explicação não inventa nada? Por que incluir quem ainda espera nas métricas? Como a animação garante que não decide nada? |

### Respostas-chave

- **Inserir/extrair na heap**: O(log n), porque o elemento sobe ou desce no máximo a altura da árvore, ⌊log₂ n⌋.
  Uma lista ordenada custaria O(n) para inserir; uma lista comum, O(n) para achar o menor.
- **Array × ordem de atendimento**: a heap só garante que cada pai tem chave ≤ filhos (índices 2i+1 e 2i+2).
  A ordem completa é uma cópia ordenada, O(n log n), feita só para exibir (visão 3).
- **Agenda × fila**: são duas heaps diferentes. A agenda ordena *eventos* por (instante, tipo, seq) e decide
  quando algo acontece; a fila ordena *pessoas* pela chave da política e decide quem é chamado.
- **A explicação é real?** Sim. `explicacao.py` só lê `motor.estado.ultima_chamada`, gravado no mesmo método
  que retira a pessoa da heap (`_tentar_admitir`). O teste `test_ultima_chamada_corresponde_ao_registro_de_auditoria`
  confere, nas três políticas, que a pessoa, a chave e os ultrapassados batem com o registro SQL `SAIDA_FILA`.
- **Aging**: a chave depende do tempo; a heap só reorganiza em push/pop. Recalcular e aplicar `heapify` custa
  O(n) por chamada, aceitável para algumas centenas de pessoas.
- **Aging e cotas são legais?** Não. São hipóteses de laboratório para discutir starvation; a interface marca
  em laranja e escreve "sem validade eleitoral" sempre que estão ativas.
- **Não preempção**: interromper quem já está votando violaria o sigilo e o fluxo da norma, e só deslocaria a espera.
- **Censura nas métricas**: quem ainda espera tem espera ≥ espera observada; excluí-lo esconde o pior caso,
  justamente o de starvation.
- **Hash encadeado**: detecta adulteração pontual; não impede a reescrita total por quem controla o banco
  (seria preciso ancorar o hash fora do sistema).
