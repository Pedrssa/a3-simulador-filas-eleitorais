# UML e dicionário de classes, métodos e estruturas

Convenção de visibilidade em Python: `+` público, `#` protegido (prefixo `_`, uso interno da classe e das
subclasses), `-` privado (detalhe de implementação). O diagrama usa Mermaid (o GitHub renderiza diretamente).

```mermaid
classDiagram
    direction LR

    class Condicao {
        <<enumeration>>
        CANDIDATO … DOADOR_SANGUE
        +rotulo str
    }
    class ClassePrioridade {
        <<enumeration>>
        MAIS_DE_80=0
        PREFERENCIAL=1
        DOADOR=2
        COMUM=3
        +rotulo str
        +icone str
    }
    class ComprovanteDoacao {
        +data_doacao date
        +valido_em(referencia) bool
    }
    class PerfilPrioridade {
        +nascimento date
        +condicoes frozenset~Condicao~
        +comprovante_doacao ComprovanteDoacao
        +classificar(data_eleicao) Classificacao
    }
    class Classificacao {
        +classe ClassePrioridade
        +fundamentos tuple~str~
        +estende_a_acompanhante bool
        +texto str
    }
    class Eleitor {
        +id str
        +apelido str
        +perfil PerfilPrioridade
        +classificacao Classificacao
        +chegada float
        +seq_chegada int
        +duracoes dict
        +ocorrencias Ocorrencias
        +estado EstadoEleitor
        +inicio_atendimento float
        +ultrapassado_por int
        +transicionar(novo, agora) EstadoEleitor
        +espera(agora) float
        +classe ClassePrioridade
    }
    class EntradaFila {
        +chave tuple
        +ordem_insercao int
        +eleitor_id str
    }
    class FilaPrioridade {
        -_heap list~EntradaFila~
        -_ids set
        -_contador int
        +inserir(id, chave) EntradaFila
        +extrair_minimo() EntradaFila
        +espiar() EntradaFila
        +extrair_onde(pred) EntradaFila
        +remover(id) EntradaFila
        +reconstruir(calcular_chave) int
        +array_interno() list
        +ordem_efetiva() list
        +invariante_ok() bool
    }
    class PoliticaAtendimento {
        <<abstract>>
        +nome str
        +versao str
        +experimental bool
        +depende_do_tempo bool
        +chave(eleitor, agora)* tuple
        +formula()* str
        +selecionar(fila, eleitores, agora) Selecao
        +ao_atender(eleitor, fila, eleitores)
        #_justificar(entrada, fila, eleitores, agora) str
    }
    class PoliticaEleitoral
    class PoliticaAging {
        +intervalo_min float
        +piso int
        +nivel_efetivo(eleitor, agora) int
    }
    class PoliticaCotas {
        +k int
        +seguidos int
    }
    class RecursoAtendimento {
        +nome str
        +ocupante str
        +interrompido bool
        +estado EstadoRecurso
        +livre bool
        +reservar(id, agora)
        +liberar(id, agora)
        +interromper(motivo, agora)
        +restabelecer(agora)
        +ocupacao_ate(agora) float
    }
    class Urna {
        +em_contingencia bool
        +votos_registrados int
    }
    class IntegranteMesa {
        +cargo Cargo
        +apelido str
        +tarefas tuple
        +ocupado_com_incidente str
        +disponivel bool
    }
    class PersonagemApoio {
        +id str
        +papel str
        +zona str
        +balao str
    }
    class SecaoEleitoral {
        +mesa dict~Cargo, IntegranteMesa~
        +posto_identificacao RecursoAtendimento
        +urna Urna
        +posto_comprovante RecursoAtendimento
        +fila FilaPrioridade
        +eleitores dict~str, Eleitor~
        +apoio dict~str, PersonagemApoio~
        +recebendo_eleitores bool
        +registrar(eleitor)
        +em_estado(*estados) list
        +verificar_invariantes()
    }
    class EventoSimulacao {
        +instante float
        +tipo TipoEvento
        +seq int
        +dados dict
    }
    class AgendaEventos {
        -_heap list
        +agendar(instante, tipo, **dados)
        +retirar() EventoSimulacao
        +proximo_instante() float
    }
    class RelogioSimulado {
        +hora_inicio_min int
        +agora float
        +avancar_para(instante)
        +hora(instante) str
    }
    class GeradorCarga {
        +gerar() Carga
        +especificar(...) EspecChegada
        +resolver_incidente(inc, rng)
    }
    class MotorSimulacao {
        +config ConfiguracaoSimulacao
        +carga Carga
        +repo PortaAuditoria
        +rastreador Rastreador
        +estado EstadoMotor
        +log list~RegistroAuditoria~
        +passo() EventoSimulacao
        +avancar_ate(alvo) int
        +executar_tudo() int
        +inserir_manual(tipo, forcar)
        +disparar_incidente(tipo)
        +trocar_politica(nome, **params)
        #_transacao(acao)
        #_auditar(tipo, justificativa, ...)
        #_tentar_admitir() bool
        #_tentar_urna() bool
    }
    class EstadoMotor {
        +secao SecaoEleitoral
        +agenda AgendaEventos
        +relogio RelogioSimulado
        +politica PoliticaAtendimento
        +seq_auditoria int
        +ultimo_hash str
    }
    class Rastreador {
        +passos list~PassoRastreado~
        +ponto(ponto, explicacao, ...)
        +marca() int
        +desfazer_ate(total)
    }
    class ServicoMetricas {
        +resumo(motor) dict
        +por_grupo(eleitores, agora) list
        +violacoes(eleitores, agora) int
        +alertas_starvation(eleitores, agora) list
    }
    class PortaAuditoria {
        <<interface>>
        +registrar_execucao(execucao)
        +gravar_lote(eleitores, registros)
    }
    class RepositorioAuditoria {
        +conn Connection
        +gravar_lote(eleitores, registros)
        +eventos(execucao_id, tipo, eleitor_id) list
        +verificar_integridade(execucao_id)
        #_transacao()
    }
    class AuditoriaEmMemoria
    class RegistroAuditoria {
        +execucao_id str
        +seq int
        +tipo str
        +estado_anterior str
        +estado_posterior str
        +justificativa str
        +politica_versao str
        +hash_anterior str
        +hash str
    }

    PerfilPrioridade *-- ComprovanteDoacao
    PerfilPrioridade ..> Classificacao : cria
    Classificacao --> ClassePrioridade
    Eleitor *-- PerfilPrioridade
    Eleitor *-- Classificacao
    FilaPrioridade *-- "0..*" EntradaFila
    PoliticaAtendimento <|-- PoliticaEleitoral
    PoliticaAtendimento <|-- PoliticaAging
    PoliticaAtendimento <|-- PoliticaCotas
    PoliticaAtendimento ..> FilaPrioridade : seleciona
    RecursoAtendimento <|-- Urna
    SecaoEleitoral *-- "4" IntegranteMesa
    SecaoEleitoral *-- "1" Urna
    SecaoEleitoral *-- "2" RecursoAtendimento
    SecaoEleitoral *-- FilaPrioridade
    SecaoEleitoral o-- "0..*" Eleitor
    SecaoEleitoral o-- "0..*" PersonagemApoio
    MotorSimulacao *-- EstadoMotor
    EstadoMotor *-- SecaoEleitoral
    EstadoMotor *-- AgendaEventos
    EstadoMotor *-- RelogioSimulado
    EstadoMotor *-- PoliticaAtendimento
    AgendaEventos *-- "0..*" EventoSimulacao
    MotorSimulacao *-- Rastreador
    MotorSimulacao --> PortaAuditoria
    MotorSimulacao ..> GeradorCarga
    MotorSimulacao ..> RegistroAuditoria : cria
    PortaAuditoria <|.. RepositorioAuditoria
    PortaAuditoria <|.. AuditoriaEmMemoria
    ServicoMetricas ..> MotorSimulacao : lê
```

## Dicionário

### Domínio (`secao8bit/domain`)

| Classe / função | Responsabilidade | Métodos principais |
|---|---|---|
| `Condicao` (Enum) | Incisos do art. 129, § 2º (exceto idade, que é derivada) | `rotulo` |
| `ClassePrioridade` (IntEnum) | Classe de atendimento; o valor menor é atendido antes | `rotulo`, `icone` |
| `tem_mais_de` / `tem_ao_menos` | Comparação etária literal ("mais de" é estrita; "igual ou superior" inclui o dia) | — |
| `ComprovanteDoacao` | Valida o comprovante de doação (≤ 120 dias) | `valido_em` |
| `PerfilPrioridade` | Composição das condições de uma pessoa | `classificar(data)` → `Classificacao` |
| `Classificacao` | Resultado imutável: classe, fundamentos, extensão ao acompanhante | `texto` |
| `Eleitor` | Pessoa fictícia; máquina de estados validada (`TRANSICOES_VALIDAS`) | `transicionar`, `espera` |
| `FilaPrioridade` | Heap mínima encapsulada (`heapq`) | `inserir`, `extrair_minimo`, `reconstruir`, `ordem_efetiva`, `array_interno` |
| `PoliticaAtendimento` (ABC) | Contrato das políticas: chave, fórmula, seleção | `chave`, `selecionar`, `ao_atender` |
| `PoliticaEleitoral` / `PoliticaAging` / `PoliticaCotas` | Ver relatório, seção 5 | — |
| `RecursoAtendimento` | Recurso de capacidade 1 com invariantes e contabilidade de tempo | `reservar`, `liberar`, `interromper`, `restabelecer` |
| `Urna` | Recurso exclusivo de votação; conta votos (sem escolha) | — |
| `IntegranteMesa` / `Cargo` | Integrante da mesa e suas tarefas didáticas | `disponivel` |
| `SecaoEleitoral` | Agrega mesa, postos, urna, fila e pessoas; verifica invariantes | `verificar_invariantes` |

### Aplicação (`secao8bit/application`)

| Classe | Responsabilidade |
|---|---|
| `ConfiguracaoSimulacao`, `CENARIOS` | Parâmetros imutáveis; 7 cenários reproduzíveis |
| `GeradorCarga`, `Carga`, `EspecChegada` | Carga prévia com fluxos aleatórios separados (chegadas, perfis, durações, incidentes) |
| `AgendaEventos`, `EventoSimulacao`, `TipoEvento` | Heap de eventos futuros (instante, prioridade do tipo, seq) |
| `RelogioSimulado` | Tempo simulado, que nunca volta |
| `MotorSimulacao`, `EstadoMotor` | Processa eventos, aplica a política na admissão, trata incidentes, audita em transação com rollback |
| `Rastreador`, `PassoRastreado`, `ReferenciaCodigo` | Pontos instrumentados com arquivo, método e linha reais |
| `ServicoMetricas`, `Estatistica` | Esperas (com censura), SLA, starvation, ocupação, vazão |
| `RegistroAuditoria`, `calcular_hash`, `verificar_cadeia` | Registro imutável e hash encadeado |
| `montar_cena` | Converte o estado em zonas e vagas para o Canvas (sem lógica de negócio) |
| `comparar` | Roda variantes de política com a mesma carga |

### Infraestrutura (`secao8bit/infrastructure`)

| Classe / função | Responsabilidade |
|---|---|
| `RepositorioAuditoria` | SQLite, FKs ligadas, consultas parametrizadas, `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` |
| `exportar_logs`, `literal_sql` | Gera o `logs.sql` executável com escaping |
| `validar_importacao` | Importa schema + logs num banco vazio e compara linha a linha |

### Estruturas de dados

| Estrutura | Onde | Por quê |
|---|---|---|
| Heap binária (lista + `heapq`) | `FilaPrioridade`, `AgendaEventos` | O(log n) para inserir e extrair o mínimo |
| Tupla como chave | políticas | Comparação lexicográfica = critério + desempate estável |
| Dicionário id → objeto | `SecaoEleitoral.eleitores` | Acesso O(1) para a heap guardar só IDs |
| Conjunto | `FilaPrioridade._ids` | `in` em O(1) e detecção de duplicados |
| Lista FIFO | `aguardando_comprovante` | Pós-voto, sem prioridade |
| Lista encadeada por hash | `evento_auditoria.hash_anterior` | Detecção de adulteração |



### Projeção e troca de política

- `MotorSimulacao.prever_atendimento() -> list[EntradaFila]`: projeta a ordem
  no instante atual sobre cópias da heap e da política. Considera cotas e
  recalcula aging, sem alterar o motor, logs ou rastreamento. A projeção não
  antecipa chegadas nem envelhecimento futuro; pode mudar com o tempo.
  Custo O(n log n) nas políticas eleitoral/aging e O(n²) no pior caso de cotas.
- `MotorSimulacao.trocar_politica(nome, **params)`: sincroniza a configuração
  somente depois de a transação de auditoria ter sucesso.
- `SessaoSimulacao.trocar_politica(nome, **params) -> bool`: sincroniza a
  configuração da sessão e informa sucesso à interface. Em falha, pausa e
  mantém a configuração anterior; não exibe confirmação de gravação.
