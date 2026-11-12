# Testes e evidências

Execução registrada em **27/10/2026** (última rodada após a revisão da cena e dos eventos) (Windows 11, Python 3.14.3, pytest 9.1.1, Streamlit 1.66.1):

```
> python -m pytest -q
109 passed in 15.64s
```

| Arquivo | Testes | O que cobre |
|---|---|---|
| `test_prioridade.py` | 27 | limites etários literais (80 anos exatos ≠ "mais de 80"; 60 anos exatos = "igual ou superior"; 29/02), doadores (120 dias vale, 121 não; sem comprovante; depois dos demais), múltiplas condições sem soma de pontos, todos os incisos I–XIV na mesma classe, extensão ao acompanhante só para VI–XV, mesa com 4 integrantes e uma urna |
| `test_fila_politicas.py` | 9 | heap rejeita duplicado, array interno ≠ ordem efetiva, remoção mantém a propriedade de heap, ordem 80+ → preferencial → comum, desempate estável, política eleitoral nunca promove comum, aging (níveis, piso e **necessidade de reconstruir a heap**), cotas (vaga para comum sem furar quem tem mais de 80) |
| `test_motor.py` | 55 | mesma seed → mesmo log (7 cenários); seed diferente → carga diferente; **velocidade da animação não altera o resultado** (4 tamanhos de passo); invariantes, urna exclusiva e nenhum ID duplicado (7 cenários × 3 políticas); não preempção; prioridade aplicada na admissão; falha de urna; boca de urna sem prisão automática e sem interromper a urna; encerramento com senhas; os 13 incidentes manuais; pausa e avanço unitário; métricas com quem ainda espera; comparação com a mesma carga (o aging reduz a espera máxima dos comuns em mais de 40%) |
| `test_auditoria.py` | 7 | **rollback** diante de falha no meio do lote (estado do motor restaurado, nada parcial no banco, simulação continua íntegra depois), UNIQUE contra duplicação, exportação → importação em banco vazio com equivalência linha a linha, escaping de literais hostis, texto com aspas e quebras de linha, hash detecta alteração e remoção, logs sem dados de voto |
| `test_coerencia.py` | 6 | a cada evento, a cena mostra a fila exatamente na ordem efetiva da heap e a cabine só com quem ocupa a urna; cada passo do rastreamento destaca a linha real `rastreador.ponto(`; todos os 8 pontos instrumentados são exercitados; as seleções no rastreamento batem com SAIDA_FILA da auditoria |
| `test_interface.py` | 15 | (Streamlit AppTest) as quatro visões renderizam sem erro e com aviso acadêmico; trocar de visão preserva a simulação; **reruns não duplicam nem avançam eventos**; ⏭ Próxima chamada para logo após uma SAIDA_FILA; ⟳ Recomeçar demo carrega demo_7min/2026; laboratório da visão 1 usa a heap real; modo apresentação; avançar 1 evento processa exatamente um; iniciar e pausar; reiniciar; troca de política |
| `test_explicacao.py` | 8 | a explicação da última chamada corresponde ao registro `SAIDA_FILA` (pessoa, chave, ultrapassados) nas 3 políticas; o próximo explicado é o 1º da projeção; ultrapassagem por 80+ cita o § 3º; fila vazia; laboratório FIFO × heap mantém a invariante e marca as posições alteradas |

## Verificação visual da reestruturação (10/11/2026)

Feita com Playwright + Microsoft Edge headless contra `streamlit run app.py` (capturas de tela revisadas uma a uma):

- 1366×768 (projetor), com e sem **Modo apresentação**, e 390×844 (celular): sem rolagem horizontal da página;
  sem erros no console do navegador.
- Visão 1: FIFO × prioridade legíveis; laboratório atualiza array, árvore e ordens.
- Visão 2: com o modo apresentação, cena, legenda e os dois cartões cabem numa tela de 1366×768; o selo
  **▼ PRÓXIMO** e o destaque **PASSOU À FRENTE!** aparecem no 9º clique de ⏭ Próxima chamada (`demo_7min`/2026).
- Visão 3: o array da heap e a ordem de atendimento aparecem lado a lado e diferem (ex.: E-0027 no índice 3 do
  array e 5º na ordem de atendimento).
- Contraste (WCAG 2.2 AA, 1.4.3/1.4.11) calculado para os pares de cor novos: todos ≥ 4,5:1 para texto e
  ≥ 3:1 para bordas; o vermelho do "!" foi escurecido (#c62828, 5,6:1) porque o anterior dava 3,5:1.

Corrigido durante a verificação: botões de controle truncados em 1366 px; conversas decorativas da cena
disputando atenção (agora desligadas por padrão, em *Exibição*); explicação abaixo da dobra no projetor;
barra lateral cobrindo o conteúdo no celular (agora `initial_sidebar_state="auto"`); apelidos fictícios repetidos
deixavam a explicação ambígua (agora com o ID).

Depende de validação manual: leitor de tela (NVDA) no canvas e nas tabelas, navegação só por teclado em todos
os controles do Streamlit, e o ensaio oral cronometrado da equipe.

## Verificação visual da interface anterior (seis abas)

Em 27/10/2026, com `streamlit run app.py` e o Chrome em 1389×665:

- A cena renderiza em escala inteira. Com o cenário `demo_7min` rodando, o grupo com prioridades entra pelo
  portão, os ícones "P"/"80+" aparecem, a Presidente mostra o balão "Documento, por favor" e as pessoas
  encaminhadas saem com o balão "Ir ao cartório".
- A simulação completa rodou até "✔ concluída" (212 eventos, 10:05:02 simulado).
- Aba B: código real de `motor.py` com a linha destacada.
- Aba C: array da heap separado da ordem efetiva.
- Aba D: gráfico da fila e comparação das 4 variantes.
- Aba E: "Cadeia de hash: 5 registros íntegros" e "Importação em banco vazio: OK, 0 violações de FK".
- Trocar de aba durante a execução não reiniciou nem duplicou eventos (o contador seguiu monotônico).

Revisão da cena: corte lateral 2D (rua, corredor, sala) com personagens procedurais e gestos por ação (entregar documento, biometria, cabine, comprovante); viatura policial; relógio analógico e céu conforme a hora; fonte bitmap em pixels inteiros; estações numeradas, painel de chamada, posições na fila, destaques e painel narrado; assentos preferenciais. Verificado no Chrome em escala 2×.

Problemas encontrados na verificação visual e corrigidos: mesários "flutuando" acima da mesa; rótulo da urna
cortado; botão "Pausar" continuava visível após o fim da simulação; resultados dos botões da aba E sumiam no
próximo tick (agora ficam guardados na sessão).

Observação: depois de editar o código com o app aberto, o *hot reload* do Streamlit pode quebrar a sessão
antiga, porque os objetos guardados usam classes do módulo anterior. Basta recarregar a página. Isso não
ocorre em uso normal.

## Não testado

- Outros navegadores além do Chrome; telas de celular.
- Som: o código WebAudio exige um clique dentro do iframe ("Ativar som"). Não foi verificado auditivamente.
- `sqlite3` de linha de comando não está instalado nesta máquina. A importação de `logs.sql` foi validada
  pelo módulo `sqlite3` do Python (`validar_importacao`), que usa a mesma biblioteca SQLite.


## Regressões da revisão de filas e troca de política

Ambiente da revisão: Linux, Python 3.12, Streamlit 1.66.1 e pytest 9.1.1.
Os testes adicionais verificam:
- projeção da fila e próximo anunciado para eleitoral, aging e cotas;
- presença de caso em que a cota chama alguém diferente do topo da heap;
- leitura da cena sem alterar chaves físicas, cotas, auditoria ou rastreamento;
- atualização do aging na projeção;
- troca de política pela interface com sincronização da configuração e reinício;
- falha de persistência na troca sem toast de sucesso, sem registro parcial e
  com preservação da política/configuração anterior.

A projeção considera o instante atual, sem novas chegadas nem avanço de tempo.
Não é uma promessa da ordem futura sob eventos que ainda não ocorreram.
A revisão não incluiu nova validação visual em navegador.

Resultado da suíte completa nesta revisão: **115 passed in 33.64s**.
Verificação de whitespace: `git diff --check` sem erros.
