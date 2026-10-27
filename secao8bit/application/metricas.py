"""Métricas de espera, SLA acadêmico, vazão, ocupação e starvation.

Quem ainda espera entra nas estatísticas "com censura": usamos a espera
observada até agora (um limite inferior da espera real). Excluir essas pessoas
deixaria os números artificialmente bons justamente quando há starvation.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from secao8bit.domain.eleitor import Eleitor, EstadoEleitor
from secao8bit.domain.prioridade import ClassePrioridade

ESPERANDO = {EstadoEleitor.AGUARDANDO}


def percentil(valores: list[float], p: float) -> float:
    """Percentil pelo método do posto mais próximo (nearest-rank)."""
    if not valores:
        return float("nan")
    ordenados = sorted(valores)
    k = max(1, math.ceil(p / 100 * len(ordenados)))
    return ordenados[k - 1]


@dataclass(frozen=True)
class Estatistica:
    n: int
    media: float
    mediana: float
    p95: float
    maximo: float

    @staticmethod
    def de(valores: list[float]) -> "Estatistica":
        if not valores:
            nan = float("nan")
            return Estatistica(0, nan, nan, nan, nan)
        return Estatistica(len(valores), statistics.fmean(valores), statistics.median(valores),
                           percentil(valores, 95), max(valores))


def eh_prioritario(e: Eleitor) -> bool:
    return e.classe != ClassePrioridade.COMUM


class ServicoMetricas:
    def __init__(self, sla_prioritarios: float, sla_comuns: float, limiar_starvation: float) -> None:
        self.sla_prioritarios = sla_prioritarios
        self.sla_comuns = sla_comuns
        self.limiar_starvation = limiar_starvation

    def meta(self, e: Eleitor) -> float:
        return self.sla_prioritarios if eh_prioritario(e) else self.sla_comuns

    def _relevantes(self, eleitores: list[Eleitor]) -> list[Eleitor]:
        """Pessoas que entraram na fila (exclui quem chegou após o encerramento)."""
        return [e for e in eleitores if e.estado not in (EstadoEleitor.CHEGANDO, EstadoEleitor.NAO_ADMITIDO)]

    def esperas(self, eleitores: list[Eleitor], agora: float, incluir_em_espera: bool = True) -> list[float]:
        out = []
        for e in self._relevantes(eleitores):
            if e.inicio_atendimento is not None:
                out.append(e.inicio_atendimento - e.chegada)
            elif incluir_em_espera and e.estado in ESPERANDO:
                out.append(agora - e.chegada)
        return out

    def por_grupo(self, eleitores: list[Eleitor], agora: float) -> list[dict]:
        linhas = []
        grupos = [(c.rotulo, [e for e in eleitores if e.classe == c]) for c in ClassePrioridade]
        grupos.append(("Todos", list(eleitores)))
        for nome, membros in grupos:
            atendidos = Estatistica.de(self.esperas(membros, agora, incluir_em_espera=False))
            com_espera = Estatistica.de(self.esperas(membros, agora, incluir_em_espera=True))
            linhas.append({
                "grupo": nome,
                "atendidos": atendidos.n,
                "aguardando": sum(1 for e in membros if e.estado in ESPERANDO),
                "média (atendidos)": atendidos.media,
                "média (incl. em espera)": com_espera.media,
                "mediana (incl.)": com_espera.mediana,
                "p95 (incl.)": com_espera.p95,
                "máximo (incl.)": com_espera.maximo,
                "violações SLA": self.violacoes(membros, agora),
            })
        return linhas

    def violacoes(self, eleitores: list[Eleitor], agora: float) -> int:
        n = 0
        for e in self._relevantes(eleitores):
            if e.inicio_atendimento is None and e.estado not in ESPERANDO:
                continue
            if e.espera(agora) > self.meta(e):
                n += 1
        return n

    def alertas_starvation(self, eleitores: list[Eleitor], agora: float) -> list[dict]:
        alertas = []
        for e in eleitores:
            if e.estado in ESPERANDO and e.espera(agora) >= self.limiar_starvation:
                alertas.append({
                    "eleitor": e.id, "classe": e.classe.rotulo, "espera (min)": round(e.espera(agora), 1),
                    "ultrapassado por": e.ultrapassado_por,
                })
        return sorted(alertas, key=lambda a: -a["espera (min)"])

    def resumo(self, motor) -> dict:
        secao, agora = motor.secao, motor.agora
        eleitores = list(secao.eleitores.values())
        concluidos = [e for e in eleitores if e.estado == EstadoEleitor.CONCLUIDO]
        sistema = [e.saida - e.chegada for e in concluidos]
        todas = Estatistica.de(self.esperas(eleitores, agora))
        horas = max(agora, 1e-9) / 60.0
        return {
            "agora": agora,
            "chegadas": len(eleitores),
            "na_fila": len(secao.fila),
            "maior_fila": motor.estado.maior_fila,
            "concluidos": len(concluidos),
            "encaminhados": sum(1 for e in eleitores if e.estado == EstadoEleitor.ENCAMINHADO),
            "nao_admitidos": sum(1 for e in eleitores if e.estado == EstadoEleitor.NAO_ADMITIDO),
            "vazao_h": len(concluidos) / horas if agora > 0 else 0.0,
            "espera_media": todas.media,
            "espera_p95": todas.p95,
            "espera_max": todas.maximo,
            "tempo_sistema_medio": statistics.fmean(sistema) if sistema else float("nan"),
            "ocupacao_urna": secao.urna.ocupacao_ate(agora) / agora if agora > 0 else 0.0,
            "ocupacao_identificacao": secao.posto_identificacao.ocupacao_ate(agora) / agora if agora > 0 else 0.0,
            "indisponibilidade_urna_min": secao.urna.indisponibilidade_ate(agora),
            "indisponibilidade_identificacao_min": secao.posto_identificacao.indisponibilidade_ate(agora),
            "violacoes_sla": self.violacoes(eleitores, agora),
            "alertas_starvation": len(self.alertas_starvation(eleitores, agora)),
            "max_ultrapassagens": max((e.ultrapassado_por for e in eleitores), default=0),
        }


def servico_para(config) -> ServicoMetricas:
    return ServicoMetricas(config.sla_prioritarios_min, config.sla_comuns_min, config.limiar_starvation_min)
