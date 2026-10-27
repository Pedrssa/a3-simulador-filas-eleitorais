"""Políticas de atendimento: quem sai da fila e por quê.

PoliticaEleitoral  — regra verificada (Res. TSE 23.751/2026, art. 129).
PoliticaAging      — LABORATÓRIO: envelhecimento temporal da prioridade.
PoliticaCotas      — LABORATÓRIO: cota rotativa para quem não tem preferência.

As políticas de laboratório não têm validade como procedimento eleitoral;
servem apenas para discutir starvation e fairness em sala.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping

from secao8bit.domain.eleitor import Eleitor
from secao8bit.domain.fila import Chave, EntradaFila, FilaPrioridade
from secao8bit.domain.prioridade import ClassePrioridade


@dataclass(frozen=True)
class Selecao:
    entrada: EntradaFila
    justificativa: str
    regra: str


class PoliticaAtendimento(ABC):
    nome: str = ""
    versao: str = ""
    experimental: bool = False
    depende_do_tempo: bool = False

    @abstractmethod
    def chave(self, eleitor: Eleitor, agora: float) -> Chave:
        """Chave de ordenação (menor = antes)."""

    @abstractmethod
    def formula(self) -> str:
        """Descrição textual da chave e dos desempates."""

    def parametros(self) -> dict:
        return {}

    def selecionar(self, fila: FilaPrioridade, eleitores: Mapping[str, Eleitor], agora: float) -> Selecao:
        entrada = fila.extrair_minimo()
        return Selecao(entrada, self._justificar(entrada, fila, eleitores, agora), "menor chave")

    def ao_atender(self, eleitor: Eleitor, fila: FilaPrioridade, eleitores: Mapping[str, Eleitor]) -> None:
        """Gancho para políticas com estado (cotas)."""

    def _justificar(self, entrada: EntradaFila, fila: FilaPrioridade, eleitores: Mapping[str, Eleitor], agora: float) -> str:
        e = eleitores[entrada.eleitor_id]
        texto = (
            f"{e.id} escolhido com chave {_fmt(entrada.chave)}: {e.classe.rotulo}, "
            f"chegada {e.chegada:.1f} min, espera {e.espera(agora):.1f} min."
        )
        seguinte = fila.espiar()
        if seguinte is not None:
            s = eleitores[seguinte.eleitor_id]
            texto += f" Próximo seria {s.id} (chave {_fmt(seguinte.chave)}, {s.classe.rotulo})."
        return texto


def _fmt(chave: Chave) -> str:
    return "(" + ", ".join(f"{v:.1f}" if isinstance(v, float) else str(int(v)) for v in chave) + ")"


class PoliticaEleitoral(PoliticaAtendimento):
    nome = "Regras eleitorais"
    versao = "ELEITORAL-1.0/Res.23751-art129"

    def chave(self, eleitor: Eleitor, agora: float) -> Chave:
        return (int(eleitor.classe), eleitor.chegada, eleitor.seq_chegada)

    def formula(self) -> str:
        return (
            "chave = (classe, chegada, seq). Classe 0 = mais de 80 anos (§3º); "
            "1 = demais preferências dos incisos I–XIV (sem precedência entre si); "
            "2 = doadores com comprovante ≤120 dias (§5º); 3 = sem preferência. "
            "Desempate estável por ordem de chegada. Sem aging: ninguém sobe de classe por esperar."
        )


class PoliticaAging(PoliticaAtendimento):
    nome = "Laboratório: aging"
    versao = "LAB-AGING-1.0"
    experimental = True
    depende_do_tempo = True

    def __init__(self, intervalo_min: float = 15.0, piso: int = int(ClassePrioridade.PREFERENCIAL)) -> None:
        self.intervalo_min = intervalo_min
        self.piso = piso

    def nivel_efetivo(self, eleitor: Eleitor, agora: float) -> int:
        base = int(eleitor.classe)
        if base <= self.piso:
            return base
        promocoes = math.floor(eleitor.espera(agora) / self.intervalo_min)
        return max(self.piso, base - promocoes)

    def chave(self, eleitor: Eleitor, agora: float) -> Chave:
        return (self.nivel_efetivo(eleitor, agora), eleitor.chegada, eleitor.seq_chegada)

    def formula(self) -> str:
        return (
            f"nível = max(piso={self.piso}, classe − ⌊espera / {self.intervalo_min:g} min⌋); "
            "chave = (nível, chegada, seq). A cada intervalo de espera a pessoa sobe um nível, "
            "até o piso (por padrão, o nível das preferências comuns: o grupo de mais de 80 "
            "continua sempre à frente). As chaves são recalculadas e a heap é reconstruída "
            "antes de cada seleção (O(n))."
        )

    def parametros(self) -> dict:
        return {"intervalo_min": self.intervalo_min, "piso": self.piso}


class PoliticaCotas(PoliticaAtendimento):
    nome = "Laboratório: cotas"
    versao = "LAB-COTAS-1.0"
    experimental = True

    def __init__(self, k: int = 3) -> None:
        self.k = k
        self.seguidos = 0  # atendimentos preferenciais seguidos com alguém comum esperando

    def chave(self, eleitor: Eleitor, agora: float) -> Chave:
        return (int(eleitor.classe), eleitor.chegada, eleitor.seq_chegada)

    def formula(self) -> str:
        return (
            f"Mesma chave da regra eleitoral, mas após {self.k} atendimentos com preferência "
            "seguidos enquanto alguém sem preferência espera, a próxima vaga vai para a pessoa "
            "sem preferência mais antiga — exceto se houver alguém com mais de 80 anos na fila."
        )

    def parametros(self) -> dict:
        return {"k": self.k, "seguidos": self.seguidos}

    def selecionar(self, fila: FilaPrioridade, eleitores: Mapping[str, Eleitor], agora: float) -> Selecao:
        topo = fila.espiar()
        if (
            topo is not None
            and self.seguidos >= self.k
            and topo.chave[0] != int(ClassePrioridade.MAIS_DE_80)
        ):
            entrada = fila.extrair_onde(lambda e: e.chave[0] == int(ClassePrioridade.COMUM))
            if entrada is not None:
                just = self._justificar(entrada, fila, eleitores, agora)
                return Selecao(entrada, f"Cota acionada após {self.seguidos} preferenciais seguidos. " + just, "cota")
        return super().selecionar(fila, eleitores, agora)

    def ao_atender(self, eleitor: Eleitor, fila: FilaPrioridade, eleitores: Mapping[str, Eleitor]) -> None:
        if eleitor.classe == ClassePrioridade.COMUM:
            self.seguidos = 0
        elif any(eleitores[e.eleitor_id].classe == ClassePrioridade.COMUM for e in fila):
            self.seguidos += 1
        else:
            self.seguidos = 0


def criar_politica(nome: str, **params) -> PoliticaAtendimento:
    if nome == "eleitoral":
        return PoliticaEleitoral()
    if nome == "aging":
        return PoliticaAging(**params)
    if nome == "cotas":
        return PoliticaCotas(**params)
    raise ValueError(f"política desconhecida: {nome}")


POLITICAS_DISPONIVEIS = {
    "eleitoral": "Regras eleitorais (Res. 23.751/2026)",
    "aging": "Laboratório — aging",
    "cotas": "Laboratório — cotas",
}
