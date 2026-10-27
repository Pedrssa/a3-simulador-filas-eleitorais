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
| `test_interface.py` | 5 | (Streamlit AppTest) seis abas e aviso acadêmico; **reruns não duplicam nem avançam eventos**; avançar 1 evento processa exatamente um; iniciar e pausar; reiniciar cria nova execução |

## Verificação visual (feita, não automatizada)

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
