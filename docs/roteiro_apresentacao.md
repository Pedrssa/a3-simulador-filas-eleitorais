# Roteiro da apresentação (20 minutos)

Preparação: `streamlit run app.py`, navegador em tela cheia, cenário **demo_7min**, seed **2026**, política
**Regras eleitorais**, velocidade **120×**. Deixe uma segunda aba aberta com o cenário **starvation** já carregado,
se a rede da sala permitir.

## 1. Pitch do problema (3 min)

1. Uma seção, **uma urna**, fila única com preferências legais (art. 129 da Res. TSE 23.751/2026).
2. Prioridade estrita responde "quem vai primeiro", mas não garante espera limitada: com fluxo preferencial
   acima da capacidade, quem não tem preferência sofre starvation.
3. Nossa pergunta: como medir, explicar e auditar isso? E quais estratégias de justiça existem, sabendo que
   aging e cotas **não** são permitidos pela regra real?

## 2. Demonstração (7 min, 1 min por item)

| Min | O que fazer | O que dizer |
|---|---|---|
| 0–1 | **Funcionamento normal.** ▶ Iniciar. Mostrar portão → fila → mesa → cabine → comprovante → saída. | "Cada movimento é um evento do motor; a animação só desenha." |
| 1–2 | **Boca de urna e chegada de prioridades** (por volta de 08:04 a viatura chega; o grupo chega por volta de 08:12). Clicar numa pessoa "80+" ou "P". | "Aqui está o fundamento legal e a justificativa da posição." |
| 2–3 | **Modo apresentação** ligado; ⏸ e ⏭ Avançar 1 evento até uma seleção. Aba B. | "Este é o `selecionar` real, linha destacada, com a chave (classe, chegada, seq)." |
| 3–4 | **Discussão na fila** (por volta de 08:24, com polícia requisitada à porta) e um incidente aleatório (celular ou impugnação). | "Observação, comunicação, polícia na área externa, avaliação. A urna não para e ninguém é preso por aparência." |
| 4–5 | **Falha de urna** (por volta de 08:40): luz vermelha, Presidente religa, técnico, contingência. Aba D: indisponibilidade. | "Mitigação operacional: substituto na identificação e técnico de prontidão." |
| 5–6 | **Starvation:** aba D → Rodar comparação (ou cenário `starvation`). | "117 min para os comuns na regra estrita; 37 com aging, mas os preferenciais pioram. As cotas empurram a espera para os doadores. LAB não tem validade eleitoral." |
| 6–7 | **Auditoria:** aba E → Verificar hash → Validar importação → Baixar logs.sql. | "Transação com rollback; hash encadeado e seu limite; importação em banco vazio idêntica." |

Plano B se a interface travar: `python scripts/gerar_exemplos.py` imprime a comparação e gera `sql/logs.sql`.

## 3. Arguição (10 min): divisão sugerida para até 6 integrantes

Cada integrante deve **ter feito alterações reais** na sua área (os próprios commits) e saber explicá-las.
Não usar autores ou commits simulados.

| Integrante | Área | Arquivos | Perguntas prováveis |
|---|---|---|---|
| 1 | Regras e classificação | `domain/prioridade.py`, `docs/regras_eleitorais.md` | Por que 80 anos exatos não é "mais de 80"? Por que não há ordem entre gestante e PcD? O que acontece com o doador com 121 dias? E com o acompanhante de um candidato? |
| 2 | Heap e políticas | `domain/fila.py`, `domain/politicas.py` | Complexidade de inserir e extrair? Por que o array não é a ordem de atendimento? Por que o aging exige `reconstruir`? Qual é o custo? Por que as cotas são O(n)? |
| 3 | Motor de eventos | `application/motor.py`, `eventos.py` | Diferença entre agenda e fila? Onde a prioridade é aplicada? Por que não há preempção? Como a velocidade não altera o resultado? |
| 4 | Incidentes e invariantes | `motor.py` (seção de incidentes), `domain/secao.py`, `recursos.py` | O que impede duas pessoas na urna? Por que a boca de urna não para a urna? O que acontece com a fila no encerramento? |
| 5 | Auditoria SQL | `infrastructure/*`, `application/auditoria.py`, `sql/schema.sql` | Como funciona o rollback? Por que consultas parametrizadas? Como evitar duplicação em reruns? Qual é o limite do hash encadeado? |
| 6 | Interface, métricas e cena | `ui/*`, `application/metricas.py`, `cena.py`, `assets/cena8bit/cena.js` | Por que incluir quem ainda espera nas métricas? Por que o p95? Como a animação garante que não decide nada? Como trocar de aba sem reiniciar? |

### Respostas-chave (para estudo)

- **Inserir/extrair na heap**: O(log n), porque o elemento sobe ou desce no máximo pela altura da árvore, ⌊log₂ n⌋.
- **Aging**: a chave depende do tempo; a heap só reorganiza em push/pop. Recalcular e aplicar `heapify` custa
  O(n) por chamada, o que é aceitável para n de algumas centenas. Uma alternativa seria recalcular só quando
  alguém cruza um limite de nível.
- **Não preempção**: interromper quem já está votando violaria o sigilo e o fluxo da norma, e só deslocaria a
  espera.
- **Censura nas métricas**: quem ainda espera tem espera ≥ espera observada. Excluí-lo esconde o pior caso,
  justamente o caso de starvation.
- **Hash encadeado**: detecta adulteração pontual; não impede a reescrita total por quem controla o banco
  (seria preciso ancorar o hash fora do sistema).
