# Relatório técnico: SEÇÃO 8-BIT

*A3 — Programação de Soluções Computacionais (enunciado: "Algoritmos, Modelagem OO, Auditoria e Aplicação em Casos Reais"). Simulação acadêmica sem vínculo
oficial com a Justiça Eleitoral.*

## 1. Problema

Numa seção eleitoral, todos disputam um recurso exclusivo: **uma única urna**. A lei dá preferência a alguns
grupos (art. 129 da Res. TSE 23.751/2026). Prioridade estrita resolve "quem vai primeiro", mas cria um problema
de justiça: se o fluxo de pessoas com preferência ficar acima da capacidade da urna por muito tempo, quem não
tem preferência pode esperar indefinidamente (**starvation**). O projeto simula esse sistema para:

- mostrar como a prioridade é calculada e aplicada, e por quê;
- medir a espera real contra metas (SLA acadêmico), incluindo quem ainda está esperando;
- mostrar como incidentes (falha de urna, discussões, boca de urna) afetam a capacidade;
- comparar, com a mesma carga, a regra eleitoral, mitigações operacionais e políticas experimentais
  (aging e cotas);
- auditar cada entrada e saída da fila em SQL transacional, com exportação executável.

## 2. Regras de negócio e cálculo de criticidade

As regras e suas fontes estão na [matriz de regras](regras_eleitorais.md). Resumo do cálculo:

| Classe | Quem | Fundamento |
|---|---|---|
| 0: Mais de 80 anos | idade **estritamente** acima de 80 anos (comparação por data) e seus acompanhantes | art. 129, § 3º e § 4º |
| 1: Preferencial | incisos I–XIV (inclui 60+ "igual ou superior"), sem precedência entre si; acompanhantes dos incisos VI–XIV | art. 129, § 2º e § 4º |
| 2: Doador(a) | comprovante de doação de no máximo 120 dias | art. 129, § 5º |
| 3: Comum | demais pessoas (inclusive doador sem comprovante válido) | — |

Chave na política eleitoral: `(classe, chegada, seq_chegada)`. Condições simultâneas não somam pontos: vale a
classe mais favorável, e todas as condições ficam registradas no fundamento.

## 3. Arquitetura

```
ui (Streamlit) ──► application (motor, métricas, cena, rastreamento) ──► domain (regras, heap, políticas)
                              │
                              └──► infrastructure (SQLite, exportação SQL) via PortaAuditoria
assets/cena8bit (Canvas/JS): só desenha o dicionário produzido por application/cena.py
```

- **Domínio** não importa Streamlit nem SQLite. As classes usam composição: `Eleitor` *tem um*
  `PerfilPrioridade`; `SecaoEleitoral` *tem* mesa, urna, postos e fila. Não existe uma subclasse de pessoa por
  condição de prioridade.
- **Herança** só onde existe "é um": `Urna(RecursoAtendimento)`; `PoliticaEleitoral`, `PoliticaAging` e
  `PoliticaCotas` herdam de `PoliticaAtendimento` (classe abstrata com `chave`, `formula` e `selecionar`).
- **Porta de persistência** (`PortaAuditoria`, um `Protocol`): o motor grava pelo repositório SQLite ou pela
  implementação em memória, usada na comparação de políticas.

## 4. Motor de eventos discretos

- **Agenda** (`AgendaEventos`): heap de `(instante, prioridade do tipo, sequência)`. No mesmo instante, as
  liberações vêm antes das chegadas, e a sequência garante uma ordem estável. É uma estrutura diferente da
  fila de eleitores: a agenda decide **quando**, a fila decide **quem**.
- **Três relógios separados**: tempo simulado (`RelogioSimulado`); relógio da interface (o fragmento do
  Streamlit roda a cada 0,5 s e avança o tempo simulado na proporção do tempo real × velocidade); e a
  interpolação visual (JS, `requestAnimationFrame`). O teste `test_velocidade_da_animacao_nao_altera_resultado`
  avança o mesmo cenário em fatias de 0,1 a 25 min e obtém logs idênticos.
- **Fluxo**: chegada → classificação/orientação → fila → identificação (Presidente) → habilitação (1º mesário,
  com a urna reservada) → votação → comprovante (2º mesário) → saída. Há caminhos alternativos: encaminhado
  (seção errada, documento, biometria) e não admitido (depois das 17h).
- **Capacidades explícitas**: posto de identificação = 1 (inclui quem já foi identificado e espera a urna);
  urna = 1; comprovante = 1, com uma fila FIFO pós-voto que não interfere na prioridade. A prioridade é aplicada
  num único ponto, a admissão ao posto de identificação, e não existe fila interna que a anule. O custo
  dessa escolha: quem chega com prioridade espera no máximo uma pessoa já admitida a mais.
- **Não preempção**: um atendimento iniciado nunca é interrompido por uma chegada prioritária
  (`test_nao_preempcao_atendimento_iniciado_nao_e_interrompido`).
- **Invariantes** (`SecaoEleitoral.verificar_invariantes`, chamado a cada evento): no máximo uma pessoa na
  urna; postos coerentes com os estados; heap válida; fila igual ao conjunto de quem está "aguardando";
  nenhum ID duplicado. `RecursoAtendimento` recusa reserva dupla e liberação por quem não ocupa o recurso.

## 5. Estrutura de prioridade e políticas

`FilaPrioridade` encapsula o `heapq` (heap binária mínima):

| Operação | Complexidade |
|---|---|
| inserir / extrair mínimo | O(log n) |
| espiar | O(1) |
| reconstruir (aging: recalcula todas as chaves + heapify) | O(n) |
| remover / extrair_onde (cotas) | O(n) |
| ordem_efetiva (exibição) | O(n log n) |

**Por que heap**: as operações dominantes são inserir e retirar o menor. Com uma lista ordenada, a inserção
custaria O(n); com uma lista simples, a extração custaria O(n). Com n ≤ algumas centenas, qualquer escolha
seria rápida, mas a heap é a estrutura correta para o problema e permite discutir a diferença entre a
**ordem física** do array e a **ordem efetiva** de atendimento (a aba C mostra as duas).

**Aging com chave dependente do tempo**: mudar o relógio não reorganiza a heap. Antes de cada chamada, o motor
executa `FilaPrioridade.reconstruir(calcular_chave)`, que recalcula todas as chaves e refaz a heap.
O teste `test_aging_exige_reconstruir_a_heap` mostra que, sem isso, o topo estaria errado.

| Política | Fórmula | Status |
|---|---|---|
| Eleitoral | `(classe, chegada, seq)` | regra verificada |
| Aging | `nível = max(piso, classe − ⌊espera / intervalo⌋)`; chave `(nível, chegada, seq)`; piso padrão = 1 (quem tem mais de 80 continua sempre à frente) | LABORATÓRIO |
| Cotas | chave eleitoral; depois de *k* atendimentos com preferência seguidos, com algum comum esperando, chama o comum mais antigo, exceto se houver alguém com mais de 80 anos na fila | LABORATÓRIO |

Hipótese de justiça do aging: ninguém deveria esperar mais que aproximadamente `(classe − piso) × intervalo`
para disputar em pé de igualdade, por ordem de chegada, com quem tem preferência. Isso **não** garante ausência
de starvation: se a demanda total supera a capacidade, a espera cresce para todos.

## 6. Resultados reproduzíveis (comparação com a mesma carga)

Gerados por `python scripts/gerar_exemplos.py` em 27/10/2026. Esperas em minutos, contando quem ainda
aguardava ("incl.").

**Cenário `starvation`** (seed 7, 30 pessoas/h com preferência e 8/h sem; capacidade da urna ≈ 25–27/h; sem incidentes):

| Variante | comum máx | comum p95 | pref. máx | doador máx | 80+ máx | violações SLA |
|---|---|---|---|---|---|---|
| Regras eleitorais | 117,2 | 117,2 | 19,4 | 109,7 | 2,9 | 23 |
| Regras + mitigação operacional | 117,2 | 117,2 | 19,4 | 109,7 | 2,9 | 23 |
| LAB: aging (15 min) | 36,8 | 36,8 | 40,6 | 35,4 | 3,9 | 54 |
| LAB: cotas (k=3) | 43,9 | 43,9 | 36,0 | 154,8 | 4,5 | 34 |

**Cenário `demo_7min`** (incidentes programados + eventos aleatórios ligados):

| Variante | comum máx | comum p95 | pref. máx | doador máx | 80+ máx | violações SLA |
|---|---|---|---|---|---|---|
| Regras eleitorais | 104,8 | 104,0 | 48,8 | 97,0 | 2,3 | 45 |
| Regras + mitigação operacional | 94,3 | 93,5 | 38,3 | 86,5 | 2,3 | 45 |
| LAB: aging (15 min) | 84,7 | 78,3 | 85,6 | 62,2 | 2,3 | 45 |
| LAB: cotas (k=3) | 100,8 | 100,8 | 65,0 | 115,2 | 2,3 | 44 |

Leitura:

1. Com a **regra eleitoral**, o pior caso dos comuns cresce com a duração do pico. É starvation real.
2. A **mitigação operacional** só ajuda quando o gargalo é um recurso **indisponível** (demo: falha de urna, Presidente ocupado; a espera máxima
   dos comuns cai de 104,8 para 94,3 min). No cenário `starvation` não há o que recuperar: a urna está quase 100% ocupada.
3. O **aging** limita a espera dos comuns (117 → 37 min), mas aumenta a dos preferenciais e o total de
   violações. Ele redistribui a espera; não cria capacidade.
4. As **cotas** atendem só a classe "comum": a espera é empurrada para os **doadores** (109,7 → 154,8 min).
   Um efeito colateral que vale levar para a discussão.

## 7. SLA e métricas

As metas (15 min com preferência, 30 min sem; alerta de starvation a 45 min) são **hipóteses acadêmicas**,
configuráveis e não garantidas. As métricas incluem quem ainda espera (espera observada até o momento, um
limite inferior), para não esconder o pior caso. São elas: média, mediana, p95 (posto mais próximo) e máximo
por grupo; maior fila; vazão; ocupação e indisponibilidade da urna e do posto de identificação; violações;
número de vezes que cada pessoa foi ultrapassada.

## 8. Auditoria

- Tabelas `execucao`, `eleitor` e `evento_auditoria` (`sql/schema.sql`), com PK, FKs (`PRAGMA foreign_keys=ON`),
  `UNIQUE(execucao_id, seq)` e `CHECK`.
- Cada passo do motor é uma **transação**. Se a gravação falhar, o banco faz ROLLBACK e o motor restaura a
  cópia do estado anterior (`test_falha_de_auditoria_desfaz_o_passo_e_nao_grava_parcial`). A interface exibe
  o erro e pausa; ela não confirma sucesso.
- Cada linha traz a justificativa (por que entrou ou saiu da fila), a versão da política, o estado
  anterior/posterior e `dados_json` com a chave e o retrato da fila (ordem efetiva) no momento da inserção e
  do atendimento.
- O **hash encadeado** (SHA-256) detecta alteração ou remoção pontual. Limite: quem controla o banco inteiro
  pode reescrever todo o histórico e recalcular a cadeia. Para evitar isso, seria preciso ancorar o último hash
  fora do sistema.
- `logs.sql` é gerado com escaping SQL (aspas duplicadas, NUL rejeitado) na ordem execucao → eleitor → evento,
  e validado por importação num banco vazio, com comparação linha a linha.
- Reruns do Streamlit não duplicam nada: o motor fica em `st.session_state` e só avança por ação explícita ou
  pelo relógio; uma duplicação acidental viola a UNIQUE e aparece como erro.

## 9. Animação

A cena é um **corte lateral 2D**: rua com calçada, árvore, poste e área externa; portão; corredor com painel de
chamada, mural, extintor e **assentos preferenciais**; porta da seção; sala com lousa, relógio analógico (marca a
hora simulada), ventilador de teto, mesa com terminal do mesário, leitor biométrico e comprovantes; cabine com
biombo e urna vista por trás (a tela nunca aparece); saída. O céu muda de cor conforme a hora.

- **Personagens procedurais** (cerca de 10×28 px): pele, cabelo, penteado e roupa variam pelo ID, **nunca** pela
  condição de prioridade. Os uniformes distinguem a mesa (colete azul e crachá), a polícia (farda e quepe), o
  técnico (colete laranja e caixa de ferramentas), o fiscal (crachá verde) e o apoio (colete amarelo).
- **Gestos derivados do estado** (`acao`, calculada em `application/cena.py`): entregar documento, dedo no
  leitor (luz verde, ou vermelha piscando na falha), entrar na cabine de costas, receber comprovante, discutir
  (braços erguidos), panfletar (boca de urna), consertar agachado (técnico), conferir documento (Presidente).
- **Diálogos**: falas roteirizadas por situação, alternando entre os personagens envolvidos (Presidente ↔ eleitor no documento; 1º mesário ↔ eleitor na biometria, com roteiro próprio para falha, celular e recusa; 2º mesário ↔ eleitor no comprovante; secretário ↔ eleitor na discussão; apoio ↔ pessoa abordando eleitores ↔ polícia; técnico ↔ Presidente na troca da urna; fiscal ↔ Presidente na impugnação). A fala atual aparece em balão branco e a anterior em cinza; os balões se afastam para não se sobrepor. Na fila há conversa leve e neutra. Na cabine não há fala (sigilo). As falas são escolhidas pelo estado e não alteram a simulação.
- **Desfecho da boca de urna**: depois da abordagem, a pessoa recolhe o material e vai embora a pé, ou é levada pelos agentes até a viatura, que parte em direção à autoridade competente.
- **Postura**: quem está sentado nos assentos e o fiscal aparecem de perfil, em L (tronco ereto, coxa no assento, canela vertical), em cadeiras de perfil; os mesários ficam sentados rentes à mesa.
- **Polícia de viatura**: quando há agentes no estado, a viatura entra pela rua com o giroflex ligado e os
  agentes descem e caminham até o local (área externa ou porta). Quando saem do estado, voltam ao carro, que
  vai embora.
- **Leitura**: textos em fonte bitmap 5×7 desenhada em pixels inteiros (nítida em qualquer escala), estações
  numeradas, posição de cada pessoa na fila ("3º P"), destaques "CHAMADO!", "VOTOU!" e "NÃO VOTOU", e um
  painel HTML abaixo da cena com quem está em cada estação e a narração dos últimos eventos.
- **Profundidade e ambientes**: piso em perspectiva (faixas que se alargam à frente, juntas convergindo), rodapé, sombra sob cada pessoa e três faixas de profundidade (fundo: assentos e mesários; meio: passagem; frente: fila e atendimento). Paredes em corte do teto ao chão, com batente, folha aberta e soleira; nomes RUA, CORREDOR e SALA DA SEÇÃO.
- **Multidão legível**: no corredor ficam no máximo 10 pessoas em pé e 8 sentadas; até 6 aguardam na calçada e o restante aparece no contador "+N AGUARDANDO". As etiquetas aparecem só para os 3 primeiros, quem está numa estação, pessoas com mais de 80 anos, alertas de espera e a pessoa selecionada. A lista completa fica nas tabelas acessíveis.
- **Acessibilidade**: prioridade sempre em texto; som opcional, desligado por padrão; movimento reduzido
  (também respeita `prefers-reduced-motion`); tabelas fora do Canvas.

O JS só interpola posições entre estados. O teste `test_cena_reflete_exatamente_o_estado_do_motor` confere, a
cada evento, que as posições da fila são a ordem efetiva da heap e que a cabine contém só quem ocupa a urna.

## 10. Limitações

- Durações, taxas e probabilidades são hipóteses, não dados oficiais.
- Não modelados: mesários e fiscais votando (art. 129, § 1º); primeiro eleitor aguardando o segundo (art. 136);
  falha de urna no meio do voto e votação por cédula (arts. 150 e
  seguintes); retorno de quem foi buscar documento; justificativa eleitoral; decisão real do Juízo numa impugnação (o modelo assume identidade confirmada).
- O acompanhante que vota aqui recebe um perfil neutro (não tem condições próprias de prioridade).
- Quando a Presidência está ocupada, novas ocorrências que a exigiriam são assumidas por um mesário
  (art. 124, § 2º) sem custo extra modelado.
- O rastreamento mostra pontos instrumentados, não todas as linhas executadas.
- A interface roda num único processo Streamlit. O SQLite local serve para demonstração, não para muitos
  usuários simultâneos.
- Verificação visual feita no Chrome (Windows 11, 1389 px de largura); outros navegadores não foram testados.
