"""Motor de simulação de eventos discretos (independente do Streamlit).

Fluxo básico:
chegada → orientação/classificação → espera na fila de prioridade → identificação
(Presidente) → habilitação (1º mesário, urna reservada) → votação (cabine) →
comprovante (2º mesário) → saída.

Capacidades explícitas:
- posto de identificação: 1 pessoa (inclui quem já foi identificado e aguarda a urna);
- urna: 1 pessoa (recurso exclusivo, da habilitação ao fim do voto);
- comprovante: 1 pessoa; quem terminou de votar e espera o comprovante forma uma
  pequena fila FIFO que não interfere na prioridade de acesso à urna.

A prioridade é aplicada num único ponto — a admissão ao posto de identificação.
Atendimento iniciado nunca é interrompido por chegada prioritária (não preemptivo).

Cada passo é uma transação: se a auditoria falhar, o estado volta ao anterior.
"""

from __future__ import annotations

import copy
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from secao8bit.application.auditoria import (
    HASH_INICIAL, AuditoriaEmMemoria, ErroPersistencia, PortaAuditoria, RegistroAuditoria,
    RegistroEleitor, RegistroExecucao, calcular_hash,
)
from secao8bit.application.carga import Carga, EspecChegada, GeradorCarga, IncidenteProgramado, rng_de
from secao8bit.application.config import ConfiguracaoSimulacao
from secao8bit.application.eventos import AgendaEventos, EventoSimulacao, RelogioSimulado, TipoEvento
from secao8bit.application.rastreamento import Rastreador
from secao8bit.domain.eleitor import Eleitor, EstadoEleitor, Ocorrencias
from secao8bit.domain.fila import EntradaFila, FilaPrioridade
from secao8bit.domain.politicas import PoliticaAtendimento, criar_politica
from secao8bit.domain.prioridade import Classificacao, ClassePrioridade, PerfilPrioridade
from secao8bit.domain.recursos import Cargo
from secao8bit.domain.secao import PersonagemApoio, SecaoEleitoral

TIPOS_INCIDENTE = {
    "grupo": "Chegada de grupo",
    "aumento_movimento": "Aumento de movimento",
    "secao_errada": "Pessoa na seção errada",
    "problema_documento": "Problema de documentação",
    "falha_biometria": "Falha de biometria",
    "auxilio": "Necessidade de auxílio acessível",
    "votacao_demorada": "Votação mais demorada",
    "celular": "Recusa em deixar o celular (art. 137, § 5º)",
    "impugnacao": "Fiscal impugna identidade (art. 132)",
    "falha_urna": "Falha de urna (chama técnico)",
    "discussao": "Discussão / tentativa de furar fila",
    "boca_de_urna": "Suspeita de boca de urna (área externa)",
    "encerramento": "Encerrar recebimento de eleitores",
}

# Ocorrências individuais disparadas manualmente = inserir alguém com a condição.
_OCORRENCIA_MANUAL = {
    "secao_errada": "secao_errada",
    "problema_documento": "problema_documento",
    "falha_biometria": "falha_biometria",
    "auxilio": "precisa_auxilio",
    "votacao_demorada": "votacao_demorada",
    "celular": "celular_recusa",
    "impugnacao": "impugnacao",
}


@dataclass
class EstadoMotor:
    """Tudo o que muda durante a simulação (copiado para permitir rollback)."""

    secao: SecaoEleitoral
    agenda: AgendaEventos
    relogio: RelogioSimulado
    politica: PoliticaAtendimento
    rng_manual: random.Random
    seq_auditoria: int = 0
    ultimo_hash: str = HASH_INICIAL
    contador_eleitores: int = 0
    contador_incidentes: int = 0
    specs_extras: dict[int, EspecChegada] = field(default_factory=dict)
    serie_fila: list[tuple[float, int]] = field(default_factory=list)
    maior_fila: int = 0
    incidentes_ativos: dict[str, dict] = field(default_factory=dict)
    presidente_em: str | None = None
    falha_urna_pendente: tuple[str, dict] | None = None
    encerrado: bool = False
    eventos_processados: int = 0
    ultimo_evento: str = ""
    recentes: list[dict] = field(default_factory=list)
    # última retirada da fila: quem foi chamado, por qual regra e quem chegou antes e ficou para trás
    ultima_chamada: dict | None = None


class MotorSimulacao:
    def __init__(self, config: ConfiguracaoSimulacao, repositorio: PortaAuditoria | None = None,
                 carga: Carga | None = None, execucao_id: str | None = None) -> None:
        self.config = config
        self.gerador = GeradorCarga(config)
        self.carga = carga if carga is not None else self.gerador.gerar()
        self.repo: PortaAuditoria = repositorio if repositorio is not None else AuditoriaEmMemoria()
        self._rollback = repositorio is not None
        self.rastreador = Rastreador()
        self.log: list[RegistroAuditoria] = []
        self.ultimo_erro: str | None = None
        politica = criar_politica(config.politica, **config.politica_params)
        self.execucao_id = execucao_id or f"EX-{config.seed}-{config.politica}-{uuid.uuid4().hex[:8]}"
        self.estado = EstadoMotor(
            secao=SecaoEleitoral(), agenda=AgendaEventos(),
            relogio=RelogioSimulado(config.hora_inicio_min), politica=politica,
            rng_manual=rng_de(config.seed, "manual"),
        )
        self._buf_eleitores: list[RegistroEleitor] = []
        self._buf_registros: list[RegistroAuditoria] = []

        for i, spec in enumerate(self.carga.chegadas):
            self.estado.agenda.agendar(spec.instante, TipoEvento.CHEGADA, spec=("carga", i))
        for inc in self.carga.incidentes:
            tipo = TipoEvento.ENCERRAMENTO if inc.tipo == "encerramento" else TipoEvento.INCIDENTE
            self.estado.agenda.agendar(inc.instante, tipo, tipo_incidente=inc.tipo, params=inc.params)

        self.repo.registrar_execucao(RegistroExecucao(
            self.execucao_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
            config.seed, config.cenario, config.politica, politica.versao,
            json.dumps(config.como_dict(), ensure_ascii=False, sort_keys=True, default=str),
        ))
        self._transacao(lambda: self._auditar(
            "EXECUCAO_INICIADA",
            f"Cenário '{config.cenario}', seed {config.seed}, política {politica.nome}.",
            chegadas_previstas=len(self.carga.chegadas), incidentes_previstos=len(self.carga.incidentes),
        ))

    # ------------------------------------------------------------------ atalhos
    @property
    def secao(self) -> SecaoEleitoral:
        return self.estado.secao

    @property
    def politica(self) -> PoliticaAtendimento:
        return self.estado.politica

    @property
    def agora(self) -> float:
        return self.estado.relogio.agora

    def hora(self, t: float | None = None) -> str:
        return self.estado.relogio.hora(t)

    @property
    def concluida(self) -> bool:
        return len(self.estado.agenda) == 0

    def prever_atendimento(self) -> list[EntradaFila]:
        """Ordem projetada no instante atual, sem novas chegadas nem avanço de tempo.

        Trabalha sobre cópias: cotas podem evoluir durante a projeção, mas não
        consomem a cota real. Aging é atualizado só na cópia da heap.
        """
        fila = copy.deepcopy(self.secao.fila)
        politica = copy.deepcopy(self.politica)
        if self.estado.encerrado:
            return fila.ordem_efetiva()
        if politica.depende_do_tempo:
            fila.reconstruir(lambda eid: politica.chave(self.secao.eleitores[eid], self.agora))
        ordem = []
        while len(fila):
            entrada = politica.selecionar(fila, self.secao.eleitores, self.agora).entrada
            ordem.append(entrada)
            politica.ao_atender(self.secao.eleitores[entrada.eleitor_id], fila, self.secao.eleitores)
        return ordem

    # ------------------------------------------------------------- transações
    def _transacao(self, acao):
        snapshot = copy.deepcopy(self.estado) if self._rollback else None
        marca = self.rastreador.marca()
        self._buf_eleitores, self._buf_registros = [], []
        try:
            resultado = acao()
            if self._buf_registros or self._buf_eleitores:
                registros = list(self._buf_registros)
                try:
                    self.repo.gravar_lote(list(self._buf_eleitores), registros)
                except Exception as exc:  # qualquer falha de persistência desfaz o passo
                    raise ErroPersistencia(str(exc)) from exc
                self.rastreador.ponto(
                    "auditoria",
                    f"Transação confirmada com {len(registros)} registro(s) de auditoria.",
                    antes=f"seq até {registros[0].seq - 1}", depois=f"seq até {registros[-1].seq}",
                    animacao="nenhuma (persistência)", referencia=type(self.repo).gravar_lote,
                    tipos=[r.tipo for r in registros], ultimo_hash=registros[-1].hash[:16],
                )
                self.log.extend(registros)
            self.ultimo_erro = None
            return resultado
        except ErroPersistencia as exc:
            if snapshot is not None:
                self.estado = snapshot
            self.rastreador.desfazer_ate(marca)
            self.ultimo_erro = f"Falha de auditoria: passo desfeito ({exc})"
            raise
        finally:
            self._buf_eleitores, self._buf_registros = [], []

    def _auditar(self, tipo_registro: str, justificativa: str, eleitor: Eleitor | None = None,
                 anterior: str | None = None, posterior: str | None = None, som: str = "", **dados) -> None:
        est = self.estado
        est.seq_auditoria += 1
        dados_json = json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        eid = eleitor.id if eleitor else None
        h = calcular_hash(self.execucao_id, est.seq_auditoria, self.agora, eid, tipo_registro, anterior, posterior,
                          justificativa, self.politica.versao, dados_json, est.ultimo_hash)
        reg = RegistroAuditoria(self.execucao_id, est.seq_auditoria, round(self.agora, 6), self.hora(), eid, tipo_registro,
                                anterior, posterior, justificativa, self.politica.versao,
                                json.loads(dados_json), est.ultimo_hash, h)
        est.ultimo_hash = h
        self._buf_registros.append(reg)
        est.recentes.append({"seq": reg.seq, "hora": self.hora()[:5], "tipo": tipo_registro, "eleitor": eid,
                              "texto": justificativa, "som": som})
        del est.recentes[:-40]

    # ------------------------------------------------------------ API pública
    def passo(self) -> EventoSimulacao | None:
        """Processa exatamente um evento da agenda."""
        if self.concluida:
            return None
        return self._transacao(self._processar_proximo)

    def avancar_ate(self, alvo: float) -> int:
        """Processa todos os eventos com instante <= alvo e leva o relógio até o alvo."""
        def acao() -> int:
            n = 0
            while (prox := self.estado.agenda.proximo_instante()) is not None and prox <= alvo:
                self._processar_proximo()
                n += 1
            if not self.concluida:
                self.estado.relogio.avancar_para(max(self.agora, alvo))
            return n
        return self._transacao(acao)

    def executar_tudo(self, limite_eventos: int = 200_000) -> int:
        n = 0
        while not self.concluida and n < limite_eventos:
            self.passo()
            n += 1
        return n

    def inserir_manual(self, tipo_prioridade: str | None = None, forcar: str | None = None,
                       origem: str = "manual") -> None:
        """tipo_prioridade: None/"comum" ou uma chave de config.pesos_prioridade."""
        def acao() -> None:
            self._agendar_extra(tipo_prioridade, forcar, origem, self.agora)
            self._auditar("ACAO_MANUAL", f"Inserção manual de eleitor fictício ({tipo_prioridade or 'comum'}"
                          f"{', ' + forcar if forcar else ''}).", tipo=tipo_prioridade, ocorrencia=forcar)
        self._transacao(acao)

    def gerar_chegadas(self, n: int, fracao_prioritaria: float = 0.3, janela_min: float = 0.0) -> None:
        def acao() -> None:
            r = self.estado.rng_manual
            for k in range(n):
                prio = r.random() < fracao_prioritaria
                tipo = r.choices(list(self.config.pesos_prioridade), list(self.config.pesos_prioridade.values()))[0] if prio else None
                t = self.agora + (r.uniform(0, janela_min) if janela_min else 0.05 * k)
                self._agendar_extra(tipo, None, "manual", t)
            self._auditar("ACAO_MANUAL", f"Geração manual de {n} chegada(s) em {janela_min:g} min.", n=n)
        self._transacao(acao)

    def disparar_incidente(self, tipo: str) -> None:
        if tipo not in TIPOS_INCIDENTE:
            raise ValueError(tipo)
        if tipo in _OCORRENCIA_MANUAL:
            prio = "deficiencia" if tipo == "auxilio" else None
            self.inserir_manual(prio, _OCORRENCIA_MANUAL[tipo], origem="incidente")
            return
        if tipo == "aumento_movimento":
            self.gerar_chegadas(12, 0.35, janela_min=15.0)
            return
        if tipo == "grupo":
            def acao_grupo() -> None:
                r = self.estado.rng_manual
                n, prio = r.randint(3, 6), r.randint(1, 3)
                for k in range(n):
                    tipo_p = "idade_60" if k < prio else None
                    self._agendar_extra(tipo_p, None, "grupo", self.agora + 0.05 * k)
                self._auditar("ACAO_MANUAL", f"Chegada manual de grupo com {n} pessoas.", n=n)
            self._transacao(acao_grupo)
            return

        def acao() -> None:
            inc = IncidenteProgramado(self.agora, tipo, {})
            if tipo != "encerramento":
                inc = self.gerador.resolver_incidente(inc, self.estado.rng_manual)
            tipo_ev = TipoEvento.ENCERRAMENTO if tipo == "encerramento" else TipoEvento.INCIDENTE
            self.estado.agenda.agendar(self.agora, tipo_ev, tipo_incidente=tipo, params=inc.params)
            self._auditar("ACAO_MANUAL", f"Incidente disparado manualmente: {TIPOS_INCIDENTE[tipo]}.", tipo=tipo)
        self._transacao(acao)

    def trocar_politica(self, nome: str, **params) -> None:
        nova_config = self.config.com(politica=nome, politica_params=dict(params))
        def acao() -> None:
            antiga = self.politica
            nova = criar_politica(nome, **params)
            self.estado.politica = nova
            if not self.estado.encerrado:
                eleitores = self.secao.eleitores
                self.secao.fila.reconstruir(lambda eid: nova.chave(eleitores[eid], self.agora))
            self._auditar("POLITICA_ALTERADA", f"Política alterada de '{antiga.nome}' para '{nova.nome}'.",
                          anterior=antiga.versao, posterior=nova.versao, parametros=nova.parametros())
        self._transacao(acao)
        self.config = nova_config  # publicar somente após confirmar a auditoria

    # ------------------------------------------------------ processamento
    def _processar_proximo(self) -> EventoSimulacao:
        est = self.estado
        ev = est.agenda.retirar()
        est.relogio.avancar_para(ev.instante)
        self.rastreador.contexto(ev.descricao(), ev.instante, self.hora())
        getattr(self, f"_ev_{ev.tipo.name.lower()}")(ev)
        self._despachar()
        tamanho = len(self.secao.fila)
        if not est.serie_fila or est.serie_fila[-1][1] != tamanho:
            est.serie_fila.append((round(self.agora, 4), tamanho))
        est.maior_fila = max(est.maior_fila, tamanho)
        est.eventos_processados += 1
        est.ultimo_evento = f"{self.hora()} · {ev.descricao()}"
        self.secao.verificar_invariantes()
        return ev

    def _despachar(self) -> None:
        """Ocupa recursos livres, de jusante para montante, até estabilizar."""
        while self._tentar_comprovante() or self._tentar_urna() or self._tentar_admitir():
            pass

    def _spec(self, ref: tuple[str, int]) -> EspecChegada:
        origem, i = ref
        return self.carga.chegadas[i] if origem == "carga" else self.estado.specs_extras[i]

    def _agendar_extra(self, tipo_prioridade: str | None, forcar: str | None, origem: str, instante: float) -> None:
        r = self.estado.rng_manual
        prio = tipo_prioridade not in (None, "comum")
        spec = self.gerador.especificar(instante, prio, origem, rng=r,
                                        tipo=tipo_prioridade if prio else None, forcar=forcar)
        k = len(self.estado.specs_extras)
        self.estado.specs_extras[k] = spec
        self.estado.agenda.agendar(instante, TipoEvento.CHEGADA, spec=("extra", k))

    # ---------------------------------------------------------------- chegada
    def _ev_chegada(self, ev: EventoSimulacao) -> None:
        spec = self._spec(ev.dados["spec"])
        titular = self._criar_eleitor(spec, spec.duracoes, None)
        if spec.acompanhante and spec.acompanhante.vota_aqui and spec.duracoes_acompanhante:
            self._criar_eleitor(spec, spec.duracoes_acompanhante, titular)

    def _criar_eleitor(self, spec: EspecChegada, duracoes: dict, titular: Eleitor | None) -> Eleitor:
        est, agora = self.estado, self.agora
        est.contador_eleitores += 1
        eid = f"E-{est.contador_eleitores:04d}"
        if titular is None:
            perfil, ocorr = spec.perfil, spec.ocorrencias
            classificacao = perfil.classificar(self.config.data_eleicao)
            self.rastreador.ponto(
                "classificacao", f"Classe '{classificacao.classe.rotulo}': {classificacao.texto}.",
                antes="sem classe", depois=classificacao.classe.rotulo,
                animacao=f"ícone '{classificacao.classe.icone or '—'}' sobre {eid}",
                referencia=PerfilPrioridade.classificar,
                eleitor=eid, condicoes=[c.name for c in perfil.condicoes], classe=int(classificacao.classe),
            )
        else:
            perfil, ocorr = PerfilPrioridade(date(1990, 6, 15)), Ocorrencias()
            base = titular.classificacao
            if base.estende_a_acompanhante:
                classificacao = Classificacao(base.classe, (f"acompanhante de {titular.id} — art. 129, § 4º",), False)
            else:
                classificacao = Classificacao(
                    ClassePrioridade.COMUM,
                    (f"acompanhante de {titular.id}: extensão só vale para os incisos VI–XV (§ 4º)",), False)

        e = Eleitor(id=eid, apelido=spec.apelido if titular is None else f"{spec.apelido} (acomp.)",
                    perfil=perfil, classificacao=classificacao, chegada=agora,
                    seq_chegada=est.contador_eleitores, duracoes=dict(duracoes), ocorrencias=ocorr,
                    acompanha=titular.id if titular else None, origem=spec.origem,
                    acompanhante_visual=titular is None and spec.acompanhante is not None
                    and not spec.acompanhante.vota_aqui)
        self.secao.registrar(e)
        self._buf_eleitores.append(RegistroEleitor(
            self.execucao_id, e.id, e.apelido, round(agora, 6), e.classe.name, classificacao.texto,
            e.origem, e.acompanha))
        self.rastreador.ponto(
            "criacao", f"{eid} ({e.apelido}) chega à seção às {self.hora()}.",
            antes="—", depois=EstadoEleitor.CHEGANDO.value, animacao=f"{eid} surge no portão e caminha",
            eleitor=eid, origem=e.origem, acompanha=e.acompanha,
        )
        if not self.secao.recebendo_eleitores:
            anterior = e.transicionar(EstadoEleitor.NAO_ADMITIDO, agora)
            e.saida = agora
            e.motivo_saida = "chegou após o encerramento"
            self._auditar("CHEGADA_NAO_ADMITIDA", "Recebimento encerrado (art. 160): só vota quem já estava na fila.",
                          e, anterior.value, e.estado.value)
            return e

        anterior = e.transicionar(EstadoEleitor.AGUARDANDO, agora)
        chave = self.politica.chave(e, agora)
        self.secao.fila.inserir(e.id, chave)
        ordem = [x.eleitor_id for x in self.secao.fila.ordem_efetiva()]
        posicao = ordem.index(e.id) + 1
        self.rastreador.ponto(
            "insercao", f"Inserido na heap com chave {chave}; posição efetiva {posicao} de {len(ordem)}.",
            antes=f"fila com {len(ordem) - 1}", depois=f"fila com {len(ordem)}",
            animacao=f"{eid} caminha até a posição {posicao} da fila", referencia=FilaPrioridade.inserir,
            eleitor=eid, chave=list(chave), posicao=posicao, tamanho=len(ordem),
        )
        self._auditar("ENTRADA_FILA", classificacao.texto, e, anterior.value, e.estado.value, som="chegada",
                      classe=e.classe.name, chave=list(chave), posicao_efetiva=posicao,
                      tamanho_fila=len(ordem), ordem_fila=ordem[:30])
        return e

    # ------------------------------------------------------------- admissão
    def _tentar_admitir(self) -> bool:
        secao, fila, agora = self.secao, self.secao.fila, self.agora
        if not secao.posto_identificacao.livre or len(fila) == 0:
            return False
        eleitores = secao.eleitores
        if self.estado.encerrado:
            entrada = fila.extrair_minimo()
            e = eleitores[entrada.eleitor_id]
            justificativa = f"{e.id} chamado pela senha {e.senha} (ordem decrescente das senhas, art. 160, § 3º)."
            regra = "senha"
        else:
            if self.politica.depende_do_tempo:
                mudaram = fila.reconstruir(lambda eid: self.politica.chave(eleitores[eid], agora))
                self.rastreador.ponto(
                    "atualizacao_espera",
                    f"Chaves recalculadas para {len(fila)} pessoa(s); {mudaram} mudaram de nível; heap refeita (O(n)).",
                    antes="chaves antigas", depois="chaves atualizadas",
                    animacao="fila pode se reorganizar" if mudaram else "sem mudança na fila",
                    referencia=FilaPrioridade.reconstruir, mudaram=mudaram, tamanho=len(fila),
                )
            topo_antes = [x.eleitor_id for x in fila.ordem_efetiva()[:5]]
            selecao = self.politica.selecionar(fila, eleitores, agora)
            entrada, justificativa, regra = selecao.entrada, selecao.justificativa, selecao.regra
            e = eleitores[entrada.eleitor_id]
            self.rastreador.ponto(
                "selecao", justificativa, antes=f"topo: {topo_antes}", depois=f"chamado: {e.id}",
                animacao=f"{e.id} sai da fila e vai à mesa", referencia=type(self.politica).selecionar,
                politica=self.politica.versao, chave=list(entrada.chave), regra=regra,
                espera=e.espera(agora), fila_restante=len(fila),
            )
        ultrapassados = []
        for outro in fila:
            o = eleitores[outro.eleitor_id]
            if (o.chegada, o.seq_chegada) < (e.chegada, e.seq_chegada):
                o.ultrapassado_por += 1
                ultrapassados.append(o.id)
        ultrapassados.sort(key=lambda i: (eleitores[i].chegada, eleitores[i].seq_chegada))
        self.estado.ultima_chamada = {
            "eleitor": e.id, "regra": regra, "chave": list(entrada.chave), "instante": agora,
            "ultrapassou": ultrapassados, "politica": self.politica.nome,
            "experimental": self.politica.experimental and not self.estado.encerrado,
            "parametros": self.politica.parametros(), "justificativa": justificativa,
        }

        secao.posto_identificacao.reservar(e.id, agora)
        anterior = e.transicionar(EstadoEleitor.IDENTIFICACAO, agora)
        e.inicio_atendimento = agora
        self.rastreador.ponto(
            "recurso", f"Posto de identificação reservado para {e.id}.",
            antes="posto livre", depois=f"posto ocupado por {e.id}", animacao="Presidente confere documento",
            referencia=type(secao.posto_identificacao).reservar, recurso=secao.posto_identificacao.nome,
        )
        if not self.estado.encerrado:
            self.politica.ao_atender(e, fila, eleitores)
        self._auditar("SAIDA_FILA", justificativa, e, anterior.value, e.estado.value, som="chamada",
                      regra=regra, chave=list(entrada.chave), espera_min=round(e.espera(agora), 3),
                      tamanho_fila=len(fila), ordem_fila=[x.eleitor_id for x in fila.ordem_efetiva()[:30]],
                      parametros=self.politica.parametros())
        dur = e.duracoes["identificacao"]
        if e.ocorrencias.secao_errada or e.ocorrencias.problema_documento:
            dur += 1.0
        if e.ocorrencias.impugnacao:
            dur += e.duracoes["impugnacao"]
            if e.ocorrencias.impugnacao_persiste:
                dur += e.duracoes["impugnacao_juizo"]
            self._iniciar_impugnacao(e)
        self.estado.agenda.agendar(agora + dur, TipoEvento.FIM_IDENTIFICACAO, eleitor_id=e.id)
        return True

    def _iniciar_impugnacao(self, e: Eleitor) -> None:
        inc_id = self._novo_incidente("impugnacao")
        self.estado.incidentes_ativos[inc_id]["eleitor"] = e.id
        self.secao.apoio["fiscal-1"].balao = "Impugno!"
        self.rastreador.ponto(
            "incidente", f"Fiscal impugna a identidade de {e.id} antes do voto; a Presidência interroga e confere "
                         "a assinatura (art. 132). A identificação demora mais, sem mudar a fila.",
            antes="identificação comum", depois="identificação com impugnação",
            animacao="fiscal ergue a mão; balão 'Impugno a identidade!'", incidente=inc_id, eleitor=e.id,
            persiste=e.ocorrencias.impugnacao_persiste,
        )
        self._auditar("INCIDENTE_INICIO", "Impugnação verbal da identidade por fiscal, antes do início do voto "
                      "(art. 132, § 2º); Presidência interroga e confere a assinatura (art. 132, I–II).",
                      e, som="alerta", incidente=inc_id)

    def _ev_fim_identificacao(self, ev: EventoSimulacao) -> None:
        e = self.secao.eleitores[ev.dados["eleitor_id"]]
        o = e.ocorrencias
        for inc_id, inc in list(self.estado.incidentes_ativos.items()):
            if inc.get("tipo") == "impugnacao" and inc.get("eleitor") == e.id:
                self.secao.apoio["fiscal-1"].balao = ""
                self._encerrar_incidente(inc_id, (
                    "Dúvida persistiu; o Juízo Eleitoral foi acionado e decidiu pela identidade (art. 132, § 3º). "
                    "Ocorrência consignada em ata." if o.impugnacao_persiste else
                    "Dúvida sanada após interrogatório e conferência de assinatura; consignado em ata (art. 132, III)."))
        if o.secao_errada or o.problema_documento:
            if o.secao_errada:
                motivo = "não consta do cadastro desta urna: orientado(a) a contatar o cartório (art. 130, § 2º)"
            else:
                motivo = "sem documento oficial com foto aceito (art. 131): orientado(a) a retornar com documento"
            self.secao.posto_identificacao.liberar(e.id, self.agora)
            self._encaminhar(e, motivo, "posto de identificação liberado")
            return
        anterior = e.transicionar(EstadoEleitor.AGUARDANDO_URNA, self.agora)
        self._auditar("FIM_IDENTIFICACAO", "Documento conferido e CPF/título aceito (art. 133, II–IV).",
                      e, anterior.value, e.estado.value)

    def _encaminhar(self, e: Eleitor, motivo: str, recurso: str) -> None:
        anterior = e.transicionar(EstadoEleitor.ENCAMINHADO, self.agora)
        e.saida = self.agora
        e.motivo_saida = motivo
        self.rastreador.ponto(
            "incidente", f"{e.id} encaminhado: {motivo}.", antes=anterior.value, depois=e.estado.value,
            animacao=f"{e.id} sai com balão explicativo", eleitor=e.id, recurso=recurso,
        )
        self._auditar("ENCAMINHADO", motivo, e, anterior.value, e.estado.value, som="alerta")

    # ----------------------------------------------------------------- urna
    def _tentar_urna(self) -> bool:
        secao = self.secao
        aguardando = secao.em_estado(EstadoEleitor.AGUARDANDO_URNA)
        if not aguardando or not secao.urna.livre:
            return False
        e = aguardando[0]
        secao.posto_identificacao.liberar(e.id, self.agora)
        secao.urna.reservar(e.id, self.agora)
        anterior = e.transicionar(EstadoEleitor.HABILITACAO, self.agora)
        self.rastreador.ponto(
            "recurso", f"Urna reservada para {e.id}; posto de identificação liberado para o próximo.",
            antes="urna livre", depois=f"urna reservada por {e.id}",
            animacao=f"1º mesário conduz a biometria de {e.id}",
            referencia=type(secao.urna).reservar, urna=secao.urna.estado.value,
        )
        dur = e.duracoes["habilitacao"]
        if e.ocorrencias.falha_biometria:
            dur += e.duracoes["biometria_extra"]
        if e.ocorrencias.celular:
            dur += e.duracoes["orientacao_celular"]
        just = "Localizado no Caderno; biometria (art. 133, V–VI)."
        if e.ocorrencias.falha_biometria:
            just += " Biometria não reconhecida: até 4 tentativas e conferência do ano de nascimento (art. 133, §§ 2º–3º; art. 135)."
        self._auditar("INICIO_HABILITACAO", just, e, anterior.value, e.estado.value)
        self.estado.agenda.agendar(self.agora + dur, TipoEvento.FIM_HABILITACAO, eleitor_id=e.id)
        return True

    def _ev_fim_habilitacao(self, ev: EventoSimulacao) -> None:
        e = self.secao.eleitores[ev.dados["eleitor_id"]]
        if e.ocorrencias.biometria_irrecuperavel:
            self.secao.urna.liberar(e.id, self.agora)
            self._encaminhar(e, "ano de nascimento não confere após nova tentativa: orientado(a) a contatar "
                                "a Justiça Eleitoral (art. 135, III)", "urna liberada sem voto")
            self._falha_pendente()
            return
        if e.ocorrencias.celular_recusa:
            self._recusa_celular(e)
            return
        anterior = e.transicionar(EstadoEleitor.VOTANDO, self.agora)
        dur = e.duracoes["votacao"] * (2.0 if e.ocorrencias.votacao_demorada else 1.0)
        if e.ocorrencias.celular:
            self._auditar("INCIDENTE_ETAPA", "Eleitor(a) ia entrar com o celular; após orientação, desligou e "
                          "deixou o aparelho com os pertences, à vista da Mesa (art. 137, § 2º).", e)
        just = "Habilitado(a); segue para a cabine. Celular e pertences guardados à vista da Mesa (art. 137, § 2º)."
        if e.ocorrencias.precisa_auxilio:
            dur += e.duracoes["auxilio_extra"]
            just += " Presidência autoriza pessoa de confiança na cabine (art. 140, § 1º); registro em ata (§ 3º)."
        self._auditar("INICIO_VOTACAO", just, e, anterior.value, e.estado.value, som="cabine",
                      auxilio=e.ocorrencias.precisa_auxilio, demorada=e.ocorrencias.votacao_demorada)
        self.estado.agenda.agendar(self.agora + dur, TipoEvento.FIM_VOTACAO, eleitor_id=e.id)

    def _recusa_celular(self, e: Eleitor) -> None:
        inc_id = self._novo_incidente("celular")
        self.estado.incidentes_ativos[inc_id]["eleitor"] = e.id
        self.secao.urna.liberar(e.id, self.agora)
        self._encaminhar(e, "recusou-se a entregar o celular antes da cabine: não autorizado(a) a votar; "
                            "detalhes consignados em ata (art. 137, § 5º)", "urna liberada sem voto")
        self._falha_pendente()
        if e.ocorrencias.celular_policia:
            self._auditar("INCIDENTE_ETAPA", "Havendo necessidade, a Presidência aciona a força policial e comunica "
                          "o Juízo Eleitoral (art. 137, § 5º).", e, som="alerta", incidente=inc_id)
            self._etapa(inc_id, "policia_chega", 6.0, local="porta", fim="policia_sai")
        else:
            self._encerrar_incidente(inc_id, "Eleitor(a) deixa a seção sem votar; ocorrência registrada em ata.")

    def _ev_fim_votacao(self, ev: EventoSimulacao) -> None:
        e = self.secao.eleitores[ev.dados["eleitor_id"]]
        urna = self.secao.urna
        urna.liberar(e.id, self.agora)
        urna.votos_registrados += 1
        e.fim_votacao = self.agora
        anterior = e.transicionar(EstadoEleitor.AGUARDANDO_COMPROVANTE, self.agora)
        self.secao.aguardando_comprovante.append(e.id)
        self.rastreador.ponto(
            "recurso", f"Urna liberada por {e.id}. Nenhuma escolha é modelada ou registrada (sigilo).",
            antes=f"urna ocupada por {e.id}", depois="urna livre",
            animacao=f"{e.id} sai da cabine; urna acende 'LIVRE'", referencia=type(urna).liberar,
            votos_contados=urna.votos_registrados,
        )
        self._auditar("FIM_VOTACAO", "Votação concluída; apenas o fato é registrado, nunca a escolha.",
                      e, anterior.value, e.estado.value, som="urna")
        self._falha_pendente()

    def _falha_pendente(self) -> None:
        if self.estado.falha_urna_pendente:
            inc_id, params = self.estado.falha_urna_pendente
            self.estado.falha_urna_pendente = None
            self._iniciar_falha_urna(inc_id, params)

    # ---------------------------------------------------------- comprovante
    def _tentar_comprovante(self) -> bool:
        secao = self.secao
        if not secao.aguardando_comprovante or not secao.posto_comprovante.livre:
            return False
        e = secao.eleitores[secao.aguardando_comprovante.pop(0)]
        secao.posto_comprovante.reservar(e.id, self.agora)
        anterior = e.transicionar(EstadoEleitor.COMPROVANTE, self.agora)
        self._auditar("INICIO_COMPROVANTE", "2º mesário devolve pertences e entrega comprovante (art. 133, IX).",
                      e, anterior.value, e.estado.value)
        self.estado.agenda.agendar(self.agora + e.duracoes["comprovante"], TipoEvento.FIM_COMPROVANTE, eleitor_id=e.id)
        return True

    def _ev_fim_comprovante(self, ev: EventoSimulacao) -> None:
        e = self.secao.eleitores[ev.dados["eleitor_id"]]
        self.secao.posto_comprovante.liberar(e.id, self.agora)
        anterior = e.transicionar(EstadoEleitor.CONCLUIDO, self.agora)
        e.saida = self.agora
        e.motivo_saida = "votou"
        self._auditar("SAIDA", f"Atendimento concluído em {e.saida - e.chegada:.1f} min no sistema.",
                      e, anterior.value, e.estado.value, espera_min=round(e.espera(self.agora), 3),
                      tempo_sistema_min=round(e.saida - e.chegada, 3))

    # ------------------------------------------------------------ incidentes
    def _novo_incidente(self, tipo: str) -> str:
        self.estado.contador_incidentes += 1
        inc_id = f"INC-{self.estado.contador_incidentes:03d}"
        self.estado.incidentes_ativos[inc_id] = {"tipo": tipo, "inicio": self.agora, "etapa": "início"}
        return inc_id

    def _etapa(self, inc_id: str, etapa: str, daqui: float, **dados) -> None:
        self.estado.agenda.agendar(self.agora + daqui, TipoEvento.ETAPA_INCIDENTE, inc=inc_id, etapa=etapa, **dados)

    def _ev_incidente(self, ev: EventoSimulacao) -> None:
        tipo, params = ev.dados["tipo_incidente"], dict(ev.dados.get("params") or {})
        getattr(self, f"_inc_{tipo}")(params)

    def _ev_etapa_incidente(self, ev: EventoSimulacao) -> None:
        inc_id = ev.dados["inc"]
        if inc_id in self.estado.incidentes_ativos:
            self.estado.incidentes_ativos[inc_id]["etapa"] = ev.dados["etapa"]
        getattr(self, f"_etapa_{ev.dados['etapa']}")(inc_id, ev.dados)

    def _ocupar_presidente(self, inc_id: str, motivo: str) -> bool:
        pres = self.secao.presidente
        posto = self.secao.posto_identificacao
        if not pres.disponivel:
            self._auditar("INCIDENTE_ETAPA", f"Presidente já ocupado(a) ({pres.ocupado_com_incidente}); "
                          "um mesário assume a ocorrência (art. 124, § 2º).", incidente=inc_id)
            return False
        pres.ocupado_com_incidente = motivo
        self.estado.presidente_em = inc_id
        if self.config.designar_substituto:
            self._auditar("INCIDENTE_ETAPA", "Presidência designa o 1º mesário para seguir identificando "
                          "(art. 126, caput: 'ou a quem ela designar').", incidente=inc_id, mitigacao=True)
        elif not posto.interrompido:
            posto.interromper(f"Presidente: {motivo}", self.agora)
            self.rastreador.ponto(
                "recurso", "Posto de identificação interrompido: ninguém novo é chamado; quem já está sendo "
                           "atendido não é expulso.", antes="disponível/ocupado", depois="interrompido",
                animacao="mesa mostra 'INTERROMPIDO'", referencia=type(posto).interromper, incidente=inc_id,
            )
            self._auditar("RECURSO_INTERROMPIDO", f"Identificação pausada: Presidente {motivo}.",
                          anterior="disponível", posterior="interrompido", incidente=inc_id, recurso=posto.nome)
        return True

    def _liberar_presidente(self, inc_id: str) -> None:
        if self.estado.presidente_em != inc_id:
            return
        self.secao.presidente.ocupado_com_incidente = ""
        self.estado.presidente_em = None
        posto = self.secao.posto_identificacao
        if posto.interrompido:
            posto.restabelecer(self.agora)
            self._auditar("RECURSO_RESTABELECIDO", "Presidente retorna à mesa; identificação retomada.",
                          anterior="interrompido", posterior="disponível", incidente=inc_id, recurso=posto.nome)

    def _encerrar_incidente(self, inc_id: str, desfecho: str, **dados) -> None:
        if inc_id not in self.estado.incidentes_ativos:
            return
        info = self.estado.incidentes_ativos.pop(inc_id)
        self.rastreador.ponto("incidente", f"{inc_id} resolvido: {desfecho}", antes=info.get("etapa", ""),
                              depois="resolvido", animacao="personagens do incidente se retiram",
                              incidente=inc_id, duracao=self.agora - info["inicio"])
        self._auditar("INCIDENTE_FIM", desfecho, incidente=inc_id, tipo=info["tipo"],
                      duracao_min=round(self.agora - info["inicio"], 3), **dados)

    def _personagem(self, pid: str, papel: str, rotulo: str, zona: str, balao: str = "") -> None:
        self.secao.apoio[pid] = PersonagemApoio(pid, papel, rotulo, zona, True, balao)

    def _remover_personagens(self, prefixo: str) -> None:
        for pid in [p for p in self.secao.apoio if p.startswith(prefixo)]:
            del self.secao.apoio[pid]

    # grupo (chegadas já estão na carga)
    def _inc_grupo(self, p: dict) -> None:
        inc_id = self._novo_incidente("grupo")
        self._auditar("INCIDENTE_INICIO", f"Chegada de grupo com {p.get('n')} pessoas "
                      f"({p.get('prioritarios')} com preferência).", incidente=inc_id, **p)
        self._encerrar_incidente(inc_id, "Grupo incorporado à fila conforme a regra vigente.")

    # falha de urna
    def _inc_falha_urna(self, p: dict) -> None:
        urna = self.secao.urna
        inc_id = self._novo_incidente("falha_urna")
        if urna.interrompido or self.estado.falha_urna_pendente:
            self._encerrar_incidente(inc_id, "Pré-condição não atendida: a urna já está em procedimento de falha.")
            return
        if urna.ocupante:
            self.estado.falha_urna_pendente = (inc_id, p)
            self._auditar("INCIDENTE_INICIO", f"Falha de urna programada; o voto em curso de {urna.ocupante} "
                          "termina antes do procedimento (simplificação: não modelamos falha no meio do voto).",
                          incidente=inc_id)
            return
        self._iniciar_falha_urna(inc_id, p)

    def _iniciar_falha_urna(self, inc_id: str, p: dict) -> None:
        urna = self.secao.urna
        urna.interromper("falha: Presidente desliga e religa (art. 147, caput)", self.agora)
        self.estado.incidentes_ativos.setdefault(inc_id, {"tipo": "falha_urna", "inicio": self.agora})
        self.rastreador.ponto(
            "incidente", "Urna interrompida. Ninguém é habilitado até o restabelecimento.",
            antes="urna livre", depois="urna interrompida", animacao="luz da urna vermelha: 'INTERROMPIDA'",
            referencia=type(urna).interromper, incidente=inc_id, persiste=p.get("persiste"),
        )
        self._auditar("RECURSO_INTERROMPIDO", "Falha na urna: Presidente desliga e religa na presença dos fiscais "
                      "(art. 147, caput).", anterior="disponível", posterior="interrompido", som="alerta",
                      incidente=inc_id, recurso="Urna")
        self._ocupar_presidente(inc_id, "religando a urna")
        self._etapa(inc_id, "urna_religada", p["religar"], persiste=p["persiste"],
                    chegada_tecnico=p["chegada_tecnico"], reparo=p["reparo"])

    def _etapa_urna_religada(self, inc_id: str, d: dict) -> None:
        self._liberar_presidente(inc_id)
        urna = self.secao.urna
        if not d["persiste"]:
            urna.restabelecer(self.agora)
            self._auditar("RECURSO_RESTABELECIDO", "Urna voltou a funcionar após religar.", anterior="interrompido",
                          posterior="disponível", incidente=inc_id, recurso="Urna")
            self._encerrar_incidente(inc_id, "Falha resolvida ao religar a urna.")
            return
        urna.motivo_interrupcao = "aguardando equipe técnica (art. 147, § 1º)"
        self._personagem(f"tec-{inc_id}", "tecnico", "Técnico(a) de urna", "a_caminho")
        self._auditar("INCIDENTE_ETAPA", "Falha persiste: Presidente solicita a equipe designada pelo Juízo "
                      "(art. 147, § 1º).", incidente=inc_id)
        self._etapa(inc_id, "tecnico_chega", d["chegada_tecnico"], reparo=d["reparo"])

    def _etapa_tecnico_chega(self, inc_id: str, d: dict) -> None:
        tec = self.secao.apoio.get(f"tec-{inc_id}")
        if tec:
            tec.zona, tec.balao = "urna", "Trocando p/ contingência"
        self._auditar("INCIDENTE_ETAPA", "Técnico(a) chega e substitui a urna por uma de contingência "
                      "(art. 147, § 1º, II); lacres repostos e assinados (§ 2º).", incidente=inc_id)
        self._etapa(inc_id, "urna_restabelecida", d["reparo"])

    def _etapa_urna_restabelecida(self, inc_id: str, d: dict) -> None:
        urna = self.secao.urna
        urna.restabelecer(self.agora)
        urna.em_contingencia = True
        self._remover_personagens(f"tec-{inc_id}")
        self._auditar("RECURSO_RESTABELECIDO", "Urna de contingência em funcionamento.", anterior="interrompido",
                      posterior="disponível", som="urna", incidente=inc_id, recurso="Urna")
        self._encerrar_incidente(inc_id, "Votação retomada com urna de contingência.")

    # discussão / furar fila
    def _inc_discussao(self, p: dict) -> None:
        fila = self.secao.fila
        inc_id = self._novo_incidente("discussao")
        if len(fila) < 2:
            self._encerrar_incidente(inc_id, "Pré-condição não atendida: fila com menos de 2 pessoas.")
            return
        ordem = fila.ordem_efetiva()
        alvo = self.secao.eleitores[ordem[min(len(ordem) - 1, max(1, int(p["posicao_relativa"] * len(ordem))))].eleitor_id]
        self.estado.incidentes_ativos[inc_id]["eleitor"] = alvo.id
        sec = self.secao.mesa[Cargo.SECRETARIO]
        sec.ocupado_com_incidente = f"orientando {alvo.id}"
        self.rastreador.ponto(
            "incidente", f"{alvo.id} tenta passar à frente; a chave na heap NÃO muda (posição por regra, não por insistência).",
            antes=f"posição de {alvo.id} na fila", depois="mesma posição", animacao="balões de discussão na fila",
            incidente=inc_id, eleitor=alvo.id, escala=p["escala"], policia=p["policia"],
        )
        self._auditar("INCIDENTE_INICIO", "Tentativa de furar fila/discussão; o secretário orienta e a posição "
                      "é mantida pela regra vigente.", alvo, som="alerta", incidente=inc_id)
        if p["escala"]:
            self._ocupar_presidente(inc_id, "mediando discussão (art. 126, VII–VIII)")
            self._etapa(inc_id, "discussao_fim", p["dur_presidente"])
            if p["policia"]:
                self._auditar("INCIDENTE_ETAPA", "Ordem não restabelecida: Presidência requisita força policial "
                              "(art. 126, VIII; art. 181, § 1º).", incidente=inc_id)
                self._etapa(inc_id, "policia_chega", p["chegada_policia"], local="porta", fim="policia_sai")
        else:
            self._etapa(inc_id, "discussao_fim", 1.5)

    def _etapa_discussao_fim(self, inc_id: str, d: dict) -> None:
        self.secao.mesa[Cargo.SECRETARIO].ocupado_com_incidente = ""
        self._liberar_presidente(inc_id)
        if not any(p.startswith(f"pol-{inc_id}") for p in self.secao.apoio) and not self._agendado(inc_id, "policia_chega"):
            self._encerrar_incidente(inc_id, "Ordem restabelecida; ocorrência consignada em ata.")
        else:
            self._auditar("INCIDENTE_ETAPA", "Discussão contida; aguarda-se a verificação policial.", incidente=inc_id)

    def _agendado(self, inc_id: str, etapa: str) -> bool:
        return any(ev.dados.get("inc") == inc_id and ev.dados.get("etapa") == etapa
                   for _, ev in self.estado.agenda._heap)

    def _etapa_policia_chega(self, inc_id: str, d: dict) -> None:
        local = d.get("local", "externo")
        for k in (1, 2):
            self._personagem(f"pol-{inc_id}-{k}", "policial", "Agente policial", f"policia_{local}",
                             "Ocorrência?" if k == 1 else "")
        self._auditar("INCIDENTE_ETAPA", f"Agentes policiais chegam ({'porta da seção' if local == 'porta' else 'área externa'}); "
                      "não circulam pela seção sem requisição da Presidência (art. 181–182).", incidente=inc_id)
        if d.get("fim") == "policia_sai":
            self._etapa(inc_id, "policia_sai", 4.0)
        else:
            self._etapa(inc_id, "boca_avaliada", d["avaliacao"], encaminhar=d["encaminhar"])

    def _etapa_policia_sai(self, inc_id: str, d: dict) -> None:
        self._remover_personagens(f"pol-{inc_id}")
        if self.estado.presidente_em == inc_id:  # discussão ainda em mediação: ela encerra o incidente
            self._auditar("INCIDENTE_ETAPA", "Agentes se retiram; Presidência segue mediando.", incidente=inc_id)
            return
        self._encerrar_incidente(inc_id, "Agentes verificam a ordem restabelecida e se retiram; registro em ata.")

    # boca de urna
    def _inc_boca_de_urna(self, p: dict) -> None:
        inc_id = self._novo_incidente("boca_de_urna")
        if p["tentativa"]:
            self._personagem(f"man-{inc_id}", "manifestante", "Pessoa abordando eleitores", "externo_boca", "Vote em…?")
            self.secao.apoio["apoio-1"].balao = "Atenção!"
            self.rastreador.ponto(
                "incidente", "Apoio logístico observa abordagem de eleitores na área externa (pedido de voto). "
                             "Isso é suspeita, não culpa.",
                antes="área externa calma", depois="suspeita em avaliação", animacao="balão 'Vote em…?' na área externa",
                incidente=inc_id, tentativa=True,
            )
            self._auditar("INCIDENTE_INICIO", "Suspeita de boca de urna: tentativa de influenciar eleitores na área externa. "
                          "A urna segue funcionando.", som="alerta", incidente=inc_id, tentativa=True)
            self._etapa(inc_id, "boca_comunicada", 0.5, chegada_policia=p["chegada_policia"],
                        avaliacao=p["avaliacao"], encaminhar=p["encaminhar"])
        else:
            self._personagem(f"man-{inc_id}", "manifestante", "Eleitor(a) com adesivo", "externo_boca", "(silêncio)")
            self._auditar("INCIDENTE_INICIO", "Manifestação individual e silenciosa (adesivo/camiseta): permitida. "
                          "Apenas observação, sem acionar polícia.", incidente=inc_id, tentativa=False)
            self._etapa(inc_id, "boca_fim_silenciosa", p["permanencia"])

    def _etapa_boca_comunicada(self, inc_id: str, d: dict) -> None:
        self.secao.apoio["apoio-1"].balao = "Avisei!"
        self._auditar("INCIDENTE_ETAPA", "Apoio comunica a Presidência; ocorrência registrada e polícia acionada "
                      "para avaliar (sem interromper a votação).", incidente=inc_id)
        self._etapa(inc_id, "policia_chega", d["chegada_policia"], local="externo",
                    avaliacao=d["avaliacao"], encaminhar=d["encaminhar"])

    def _etapa_boca_avaliada(self, inc_id: str, d: dict) -> None:
        """Desfecho visível: a pessoa vai embora a pé ou é levada pelos agentes à autoridade competente."""
        man = self.secao.apoio.get(f"man-{inc_id}")
        if d["encaminhar"]:
            if man:
                man.zona, man.balao = "viatura", "Tudo bem…"
            for pid, p in self.secao.apoio.items():
                if pid.startswith(f"pol-{inc_id}"):
                    p.zona = "policia_viatura"
            texto = ("Agentes avaliam e conduzem a pessoa à autoridade competente para registro e apuração "
                     "(a simulação não declara culpa).")
        else:
            if man:
                man.zona, man.balao = "indo_embora", "Já vou embora."
            texto = "Após orientação dos agentes, a pessoa recolhe o material e deixa o local."
        self._auditar("INCIDENTE_ETAPA", texto, incidente=inc_id, encaminhado=d["encaminhar"])
        self._etapa(inc_id, "boca_saida", 1.5, encaminhar=d["encaminhar"])

    def _etapa_boca_saida(self, inc_id: str, d: dict) -> None:
        self._remover_personagens(f"man-{inc_id}")
        self._remover_personagens(f"pol-{inc_id}")
        self.secao.apoio["apoio-1"].balao = ""
        desfecho = ("Viatura parte levando a pessoa à autoridade competente; ocorrência registrada."
                    if d["encaminhar"] else "Conduta cessou; ocorrência registrada.")
        self._encerrar_incidente(inc_id, desfecho, encaminhado=d["encaminhar"])

    def _etapa_boca_fim_silenciosa(self, inc_id: str, d: dict) -> None:
        self._remover_personagens(f"man-{inc_id}")
        self._encerrar_incidente(inc_id, "Pessoa vota/segue seu caminho; nenhuma providência necessária.")

    # encerramento
    def _ev_encerramento(self, ev: EventoSimulacao) -> None:
        secao = self.secao
        if self.estado.encerrado:
            return
        secao.recebendo_eleitores = False
        self.estado.encerrado = True
        ordem = secao.fila.ordem_efetiva()
        n = len(ordem)
        senhas: dict[str, int] = {}
        for pos, entrada in enumerate(ordem):
            senhas[entrada.eleitor_id] = n - pos  # a última da fila recebe a senha 1
            secao.eleitores[entrada.eleitor_id].senha = n - pos
        secao.fila.reconstruir(lambda eid: (-senhas[eid],))
        secao.mesa[Cargo.SECRETARIO].ocupado_com_incidente = "distribuindo senhas" if n else ""
        self.rastreador.ponto(
            "incidente", f"Recebimento encerrado. {n} senha(s) distribuída(s) do fim para o começo da fila; "
                         "chamada em ordem decrescente de senha.",
            antes="recebendo", depois="encerrado", animacao="placa 'ENCERRADO' no portão; senhas nas pessoas",
            referencia=FilaPrioridade.reconstruir, senhas=n,
        )
        self._auditar("ENCERRAMENTO", "17h: termina o recebimento; quem está na fila recebe senha "
                      "começando pelo último (art. 160, §§ 2º–3º).", som="alerta",
                      senhas=[[eid, s] for eid, s in sorted(senhas.items(), key=lambda kv: -kv[1])])

