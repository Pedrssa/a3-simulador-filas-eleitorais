# Regras eleitorais: matriz de rastreabilidade

> Simulação acadêmica **sem vínculo oficial com a Justiça Eleitoral**. Personagens e dados fictícios.
> Nenhum CPF, título, biometria ou voto real é coletado; nenhuma escolha de voto é modelada.

**Data da consulta de todas as fontes: 27/10/2026.** As páginas do TSE e do TRE-PR bloqueiam
clientes automatizados (HTTP 403); o texto foi lido num navegador comum.

## Fontes

| Código | Fonte | Endereço |
|---|---|---|
| RES | Resolução TSE nº 23.751, de 26/02/2026 (texto compilado) | https://www.tse.jus.br/legislacao/compilada/res/2026/resolucao-no-23-751-de-26-de-fevereiro-de-2026 |
| TRE-PR | "Eleições 2026: quem tem prioridade para votar?" (23/09/2026) | https://www.tre-pr.jus.br/comunicacao/noticias/2026/Setembro/eleicoes-2026-quem-tem-prioridade-para-votar |
| TSE-BU | "Até o fim da votação, propaganda eleitoral pode caracterizar boca de urna" (25/10/2026) | https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/ate-o-fim-da-votacao-propaganda-eleitoral-pode-caracterizar-boca-de-urna |
| MES | Portal de mesárias e mesários da Justiça Eleitoral | https://www.justicaeleitoral.jus.br/eleicoes/mesario/ |

O portal MES é uma página de entrada com cursos e materiais (ex.: "10 Dicas de Ouro"). As atribuições
usadas no código foram tiradas da Resolução, que é a fonte normativa.

## Classificação

- **Oficial**: transcreve a regra.
- **Simplificação didática**: segue a regra, mas reduz detalhes operacionais, ou atribui uma tarefa a um cargo
  quando a norma permite designação.
- **Hipótese experimental**: escolha do grupo, sem respaldo normativo, usada para estudo (SLA, aging, cotas, durações).

## Matriz

| # | Regra | Fonte e dispositivo | Interpretação implementada | Onde no código | Teste | Classe |
|---|---|---|---|---|---|---|
| R01 | A Mesa Receptora de Votos tem Presidente, 1º mesário, 2º mesário e secretário | RES art. 9º, I–IV | 4 integrantes; uma única urna como recurso exclusivo | `domain/secao.py: mesa_padrao` | `test_prioridade.py::test_mesa_tem_quatro_integrantes_e_uma_urna` | Oficial |
| R02 | O apoio logístico é facultativo e não integra a mesa; um dos nomeados atua como coordenador de acessibilidade | RES art. 10, caput e § 1º | Personagem "Apoio logístico", fora da mesa, junto ao portão | `domain/secao.py: PersonagemApoio` | mesmo teste acima | Oficial |
| R03 | Lista de quem tem preferência: incisos I a XV (candidatos, juízes, servidores, promotores, agentes em serviço, 60+, PcD, mobilidade reduzida, enfermos, TEA, obesos, gestantes, lactantes, pessoas com criança de colo, doadores) | RES art. 129, § 2º | Enum `Condicao`; idade (VI) derivada da data de nascimento | `domain/prioridade.py` | `test_incisos_i_a_xiv_tem_mesma_classe` | Oficial |
| R04 | Pessoas com **mais de 80 anos** têm precedência sobre as demais, independentemente da chegada | RES art. 129, § 3º; TRE-PR | Comparação **estrita**: no dia do 80º aniversário a pessoa ainda não tem "mais de 80" | `tem_mais_de()` | `test_exatamente_80_anos_nao_tem_mais_de_80`, `test_80_anos_e_um_dia_tem_mais_de_80` | Oficial (ver nota 1) |
| R05 | 60 anos: "igual ou superior" | RES art. 129, § 2º, VI | Inclui o dia do 60º aniversário | `tem_ao_menos()` | `test_exatamente_60_anos_tem_preferencia`, `test_um_dia_antes_dos_60_nao_tem_preferencia` | Oficial |
| R06 | Entre quem tem preferência, vale a ordem de chegada | RES art. 129, § 3º | Classe única para I–XIV; desempate por (chegada, sequência) | `PoliticaEleitoral.chave` | `test_desempate_estavel_por_chegada`, `test_ordem_eleitoral_...` | Oficial |
| R07 | A norma não cria precedência entre os incisos I–XIV | RES art. 129, §§ 2º–3º | Nenhuma ordem inventada entre gestantes, PcD etc. | `ClassePrioridade.PREFERENCIAL` | `test_incisos_i_a_xiv_tem_mesma_classe` | Oficial |
| R08 | Doadores de sangue votam após todos os demais beneficiados, com comprovante de até 120 dias | RES art. 129, § 5º; TRE-PR | Classe DOADOR depois de PREFERENCIAL; 120 dias vale, 121 não; sem comprovante = sem preferência | `ComprovanteDoacao.valido_em` | `TestDoadores` | Oficial |
| R09 | Várias condições ao mesmo tempo | RES art. 129 (silêncio) | Vale a classe mais favorável; todas as condições ficam no fundamento; nada de somar pontos | `PerfilPrioridade.classificar` | `TestMultiplasCondicoes` | Simplificação didática |
| R10 | A preferência se estende ao acompanhante dos titulares dos incisos VI a XV, ainda que vote em outra seção | RES art. 129, § 4º | O acompanhante que vota aqui herda a classe do titular; o de I–V não herda; o que não vota aqui só aparece na cena | `MotorSimulacao._criar_eleitor` | `test_extensao_ao_acompanhante_so_para_incisos_vi_a_xv` | Oficial (nota 2) |
| R11 | A Presidência pode tomar providências na organização da fila | RES art. 129, § 6º; art. 126 (designação) | O secretário organiza o acesso e a fila, por designação | `mesa_padrao` (tarefas) | — (descritivo) | Simplificação didática |
| R12 | Mesários e fiscais votam depois dos eleitores presentes | RES art. 129, § 1º | **Não modelado**: mesários e fiscais não votam na simulação | — | — | Limitação |
| R13 | Só vota quem está cadastrado na seção | RES art. 130, caput e § 2º | "Seção errada" → orientado a procurar o cartório; sai sem votar; registro em ata | `_ev_fim_identificacao` | `test_incidentes_manuais_nao_quebram_invariantes[secao_errada]` | Simplificação didática |
| R14 | Documentos com foto aceitos; certidão de nascimento ou casamento não | RES art. 131, caput, §§ 1º–3º | "Problema de documentação" → orientado a voltar com documento aceito (o retorno não é modelado) | `_ev_fim_identificacao` | `...[problema_documento]` | Simplificação didática |
| R15 | Sequência: fila → documento ao Presidente → CPF/título no terminal → caderno → biometria → cabine → comprovante | RES art. 133, I–IX | Pipeline identificação (Presidente) → habilitação (1º mesário, com a urna reservada) → votação → comprovante (2º mesário) | `motor.py` | `test_prioridade_aplicada_na_admissao` | Oficial (fluxo); a divisão entre cargos é didática |
| R16 | Biometria: até 4 leituras; nova tentativa após conferência; depois, ano de nascimento; se persistir, orientação para procurar a JE | RES art. 133, §§ 2º–3º; arts. 134–135 | Falha → tempo extra; "irrecuperável" → encaminhado sem votar | `_tentar_urna`, `_ev_fim_habilitacao` | `...[falha_biometria]` | Simplificação didática |
| R17 | Primeiro eleitor aguarda o segundo concluir | RES art. 136 | **Não modelado** | — | — | Limitação |
| R18 | Celular e equipamentos são vedados na cabine; ficam guardados à vista da Mesa | RES art. 137, caput, §§ 1º–3º | Registro "pertences guardados" no início do voto; prateleira de PERTENCES na cena; a recusa está em R29 | `_ev_fim_habilitacao` | — | Simplificação didática |
| R19 | Sigilo: nada que registre a escolha | RES art. 137, § 1º | A cabine mostra "Votando"; o log registra só o fato, nunca a escolha | `cena.py`, `_ev_fim_votacao` | `test_logs_nao_contem_dados_de_voto` | Oficial |
| R20 | Eleitor com deficiência ou mobilidade reduzida pode ter auxílio de pessoa de confiança na cabine, autorizado pela Presidência; registro em ata; o auxiliar não pode estar a serviço da JE nem de partido | RES art. 140, caput, §§ 1º–3º | Ocorrência "auxílio": o acompanhante entra na cabine; tempo extra; registro | `_ev_fim_habilitacao` | `...[auxilio]` | Simplificação didática |
| R21 | Falha de urna: desligar e religar; se persistir, equipe designada pelo Juízo reposiciona a mídia ou troca a urna por uma de contingência | RES art. 147, caput, §§ 1º–3º | Urna INTERROMPIDA; Presidente religa; técnico chega e coloca a urna de contingência; voto em curso termina antes (nota 3) | `_inc_falha_urna` e etapas | `test_falha_de_urna_interrompe_e_restabelece_sem_voto_simultaneo` | Simplificação didática |
| R22 | Recebimento termina às 17h; quem está na fila recebe senha a partir do último; votação em ordem decrescente das senhas | RES art. 160, caput, §§ 2º–3º | Evento ENCERRAMENTO; senhas; quem chega depois não é admitido | `_ev_encerramento` | `test_encerramento_distribui_senhas_e_recusa_quem_chega_depois` | Oficial |
| R23 | Polícia dos trabalhos: Presidente e Juízo; a Presidência dispõe da força pública para manter a ordem | RES arts. 126, VIII; 180; 181, § 1º | Polícia só aparece quando acionada; fica na área externa ou na porta | `_etapa_policia_chega` | `test_boca_de_urna_nao_interrompe_urna_nem_prende_automaticamente` | Simplificação didática |
| R24 | Força Armada a 100 m da seção, salvo ordem judicial ou da Presidência | RES art. 182 | Nenhuma patrulha circula dentro da seção por padrão | `cena.js` (posições) | — | Oficial (como restrição de cena) |
| R25 | Boca de urna: pedir votos, distribuir santinhos e arregimentar são condutas proibidas; a manifestação individual e silenciosa é permitida | TSE-BU (Lei nº 9.504/1997) | Dois casos: silenciosa → só observação; tentativa de influenciar → comunicação, polícia, avaliação. **Sem declaração de culpa nem prisão automática** | `_inc_boca_de_urna` | mesmo teste acima | Oficial (distinção); desfecho = hipótese |
| R26 | Presidente ausente ou ocupado: um mesário assume; a Presidência pode designar componentes | RES art. 124, § 2º; art. 126, caput | Mitigação opcional: um mesário segue identificando durante a ocorrência | `_ocupar_presidente` | `test_comparacao_usa_a_mesma_carga_...` | Simplificação didática |
| R28 | Impugnação da identidade (verbal ou escrita) antes do voto; a Presidência interroga, confere a assinatura e registra; se persistir, solicita o Juízo | RES art. 132, I–III, §§ 2º–3º | Ocorrência "impugnação": a identificação demora mais; se persistir, há tempo extra de decisão do Juízo e a identidade é confirmada | `_iniciar_impugnacao`, `_ev_fim_identificacao` | `test_incidentes_manuais_nao_quebram_invariantes[impugnacao]` | Simplificação didática (o desfecho "identidade confirmada" é hipótese) |
| R29 | Recusa em entregar o celular: a pessoa não é autorizada a votar; ata; força policial, havendo necessidade; comunicação ao Juízo | RES art. 137, § 5º | Ocorrência "celular": ou guarda o aparelho após orientação (art. 137, § 2º), ou recusa e sai sem votar; a polícia só vem em parte dos casos | `_recusa_celular` | `test_incidentes_manuais_nao_quebram_invariantes[celular]` | Oficial (fluxo); a probabilidade é hipótese |
| R27 | Só mesários, fiscais e, durante o tempo necessário à votação, o eleitor podem permanecer no recinto da Mesa; o coordenador de acessibilidade adota medidas para melhorar a acessibilidade | RES art. 181, caput; art. 10, § 1º, II–III | 8 **assentos preferenciais no corredor**, junto à porta da seção, para quem tem preferência e aguarda (na ordem da fila); a ordem de chamada não muda | `cena.py: ASSENTOS_PREFERENCIAIS` | `test_cena_reflete_exatamente_o_estado_do_motor` | Simplificação didática |
| H01 | Metas de SLA (15 e 30 min) e limiar de starvation (45 min) | — | Configuráveis; **não são garantia legal** | `config.py` | `test_metricas_incluem_quem_ainda_espera` | Hipótese experimental |
| H02 | Aging e cotas | — | Só no modo LABORATÓRIO, com aviso permanente | `politicas.py` | `test_aging_*`, `test_cotas_*` | Hipótese experimental |
| H03 | Durações, taxas de chegada, probabilidades | — | Distribuições triangulares e Poisson, com seed | `config.py`, `carga.py` | `test_mesma_seed_mesmo_resultado` | Hipótese experimental |

### Notas

1. **"Mais de 80 anos".** A leitura literal adotada é: no dia em que completa 80 anos, a pessoa tem exatamente
   80 anos, e a precedência começa no dia seguinte. Outra leitura possível exige 81 anos completos. A diferença
   só afeta quem tem entre 80 anos e 1 dia e 80 anos e 364 dias. Fica como ponto para discutir com o professor.
2. **Acompanhante de pessoa com mais de 80 anos.** O § 4º estende "a preferência" ao acompanhante dos incisos VI–XV,
   e o TRE-PR diz que o direito de quem tem mais de 80 "estende-se ao acompanhante". Por isso o acompanhante
   herda inclusive a classe "mais de 80". O acompanhante de titular dos incisos I–V (candidatos, juízes etc.)
   não herda nada.
3. **Falha de urna durante o voto.** Para não modelar o procedimento de voto interrompido (arts. 150 e seguintes),
   a falha programada começa assim que termina o voto em curso. Isso fica registrado na auditoria.

## Starvation e compatibilidade com as regras reais (para discussão)

- A política eleitoral é **prioridade estrita por classes**. Se o fluxo de pessoas com preferência ficar acima
  da capacidade da única urna por muito tempo, quem não tem preferência pode esperar sem limite. O cenário
  `starvation` mostra isso: espera máxima de 117 min para os comuns.
- No modo eleitoral, ninguém é promovido acima de uma preferência legal. As mitigações são operacionais
  (substituto na identificação, técnico de prontidão). Elas ajudam quando o gargalo é um recurso
  **indisponível**, mas não criam capacidade de votação. Por isso, no cenário `starvation`, não mudam nada.
- O aging e as cotas reduzem a espera de quem não tem preferência, mas **contrariam o art. 129, § 3º**: alguém
  que chegou depois, com preferência, passa a ser atendido depois de um comum. Por isso existem só no
  modo LABORATÓRIO. A questão para o professor é se uma política de justiça pode ser compatível com a
  regra real. Uma resposta possível: só como medida operacional externa à fila (mais capacidade, outra seção,
  fluxo de agendamento), e nunca reordenando quem tem preferência.
