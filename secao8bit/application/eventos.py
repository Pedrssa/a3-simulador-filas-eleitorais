"""Agenda de eventos futuros (heap) e relógio simulado.

A agenda é uma heap DIFERENTE da fila de eleitores: ela ordena "o que acontece
quando" por (instante, prioridade do tipo, sequência). A fila de eleitores
ordena "quem é chamado" pela política de atendimento.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import Enum


class TipoEvento(Enum):
    # Valor = prioridade de processamento no mesmo instante (liberações primeiro).
    FIM_COMPROVANTE = 0
    FIM_VOTACAO = 1
    FIM_HABILITACAO = 2
    FIM_IDENTIFICACAO = 3
    ETAPA_INCIDENTE = 4
    INCIDENTE = 5
    ENCERRAMENTO = 6
    CHEGADA = 7


@dataclass(frozen=True)
class EventoSimulacao:
    instante: float
    tipo: TipoEvento
    seq: int
    dados: dict = field(default_factory=dict, compare=False)

    @property
    def chave(self) -> tuple:
        return (self.instante, self.tipo.value, self.seq)

    def descricao(self) -> str:
        alvo = self.dados.get("eleitor_id") or self.dados.get("etapa") or self.dados.get("tipo") or ""
        return f"{self.tipo.name} {alvo}".strip()


class AgendaEventos:
    def __init__(self) -> None:
        self._heap: list[tuple[tuple, EventoSimulacao]] = []
        self._seq = 0

    def __len__(self) -> int:
        return len(self._heap)

    def agendar(self, instante: float, tipo: TipoEvento, **dados) -> EventoSimulacao:
        ev = EventoSimulacao(round(instante, 6), tipo, self._seq, dados)
        self._seq += 1
        heapq.heappush(self._heap, (ev.chave, ev))
        return ev

    def proximo_instante(self) -> float | None:
        return self._heap[0][1].instante if self._heap else None

    def retirar(self) -> EventoSimulacao:
        return heapq.heappop(self._heap)[1]

    def pendentes(self, limite: int = 15) -> list[EventoSimulacao]:
        return [ev for _, ev in heapq.nsmallest(limite, self._heap)]


@dataclass
class RelogioSimulado:
    """Tempo simulado em minutos desde o início do cenário."""

    hora_inicio_min: int
    agora: float = 0.0

    def avancar_para(self, instante: float) -> None:
        if instante < self.agora - 1e-9:
            raise ValueError(f"o tempo não volta: {instante} < {self.agora}")
        self.agora = instante

    def hora(self, instante: float | None = None) -> str:
        t = self.agora if instante is None else instante
        total = self.hora_inicio_min * 60 + round(t * 60)
        h, resto = divmod(total, 3600)
        m, s = divmod(resto, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
