"""Recursos de atendimento, urna e integrantes da mesa."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EstadoRecurso(Enum):
    DISPONIVEL = "disponível"
    OCUPADO = "ocupado"
    INTERROMPIDO = "interrompido"


class ErroRecurso(RuntimeError):
    """Violação de invariante: reserva dupla, liberação dupla etc."""


@dataclass
class RecursoAtendimento:
    """Recurso de capacidade 1 com contabilidade de ocupação.

    Invariantes: só reserva quando disponível; só libera quem ocupa; um recurso
    interrompido não aceita reservas, mas quem já o ocupa não é expulso.
    """

    nome: str
    ocupante: str | None = None
    interrompido: bool = False
    motivo_interrupcao: str = ""
    tempo_ocupado: float = 0.0
    tempo_interrompido: float = 0.0
    _desde_ocupado: float | None = None
    _desde_interrompido: float | None = None

    @property
    def estado(self) -> EstadoRecurso:
        if self.interrompido:
            return EstadoRecurso.INTERROMPIDO
        return EstadoRecurso.OCUPADO if self.ocupante else EstadoRecurso.DISPONIVEL

    @property
    def livre(self) -> bool:
        return self.ocupante is None and not self.interrompido

    def reservar(self, eleitor_id: str, agora: float) -> None:
        if self.interrompido:
            raise ErroRecurso(f"{self.nome} interrompido: não pode receber {eleitor_id}")
        if self.ocupante is not None:
            raise ErroRecurso(f"{self.nome} já ocupado por {self.ocupante}; recusa {eleitor_id}")
        self.ocupante = eleitor_id
        self._desde_ocupado = agora

    def liberar(self, eleitor_id: str, agora: float) -> None:
        if self.ocupante != eleitor_id:
            raise ErroRecurso(f"{self.nome}: liberação por {eleitor_id}, mas ocupante é {self.ocupante}")
        self.tempo_ocupado += agora - (self._desde_ocupado or agora)
        self.ocupante = None
        self._desde_ocupado = None

    def interromper(self, motivo: str, agora: float) -> None:
        if self.interrompido:
            raise ErroRecurso(f"{self.nome} já está interrompido")
        self.interrompido = True
        self.motivo_interrupcao = motivo
        self._desde_interrompido = agora

    def restabelecer(self, agora: float) -> None:
        if not self.interrompido:
            raise ErroRecurso(f"{self.nome} não está interrompido")
        self.tempo_interrompido += agora - (self._desde_interrompido or agora)
        self.interrompido = False
        self.motivo_interrupcao = ""
        self._desde_interrompido = None

    def ocupacao_ate(self, agora: float) -> float:
        extra = agora - self._desde_ocupado if self._desde_ocupado is not None else 0.0
        return self.tempo_ocupado + extra

    def indisponibilidade_ate(self, agora: float) -> float:
        extra = agora - self._desde_interrompido if self._desde_interrompido is not None else 0.0
        return self.tempo_interrompido + extra


@dataclass
class Urna(RecursoAtendimento):
    """A seção possui uma única urna: recurso exclusivo de votação."""

    em_contingencia: bool = False
    votos_registrados: int = 0  # apenas contagem; nenhuma escolha é modelada


class Cargo(Enum):
    PRESIDENTE = "Presidente"
    PRIMEIRO_MESARIO = "1º mesário"
    SEGUNDO_MESARIO = "2º mesário"
    SECRETARIO = "Secretário"


@dataclass
class IntegranteMesa:
    """Integrante da Mesa Receptora de Votos (Res. 23.751/2026, art. 9º).

    A divisão de tarefas entre mesários é operacional/didática: o art. 126 permite
    à Presidência designar componentes da Mesa para as atribuições.
    """

    cargo: Cargo
    apelido: str
    tarefas: tuple[str, ...]
    ocupado_com_incidente: str = ""

    @property
    def disponivel(self) -> bool:
        return not self.ocupado_com_incidente
