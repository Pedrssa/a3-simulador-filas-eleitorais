"""Laboratório didático: fila comum (FIFO) × fila de prioridade, lado a lado.

Usa a MESMA classe `FilaPrioridade` do motor (heap binária mínima com heapq) e a
mesma forma de chave da regra eleitoral: (classe, ordem de chegada, sequência).
Cada operação registra o array interno antes e depois, as posições que mudaram
e quantas comparações pai/filho couberam no caminho (limite de ⌊log₂ n⌋ níveis).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from secao8bit.domain.fila import EntradaFila, FilaPrioridade

NOMES = ["Ana", "Bruno", "Carla", "Davi", "Elisa", "Fábio", "Gabi", "Hugo", "Iara", "João", "Kátia", "Lucas",
         "Marina", "Nilo", "Olga", "Paulo", "Rita", "Sérgio", "Tânia", "Vítor"]

# classe → (rótulo curto, rótulo longo). Mesma numeração de ClassePrioridade.
CLASSES = {
    0: ("80+", "mais de 80 anos"),
    1: ("P", "preferência legal"),
    2: ("D", "doador(a) com comprovante"),
    3: ("—", "sem preferência"),
}


@dataclass(frozen=True)
class Passo:
    operacao: str  # "inserir" ou "extrair"
    pessoa: str
    antes: list[EntradaFila]
    depois: list[EntradaFila]
    mudaram: list[int]  # índices do array cujo conteúdo mudou
    explicacao: str


@dataclass
class LaboratorioFila:
    fila: FilaPrioridade = field(default_factory=FilaPrioridade)
    fifo: deque = field(default_factory=deque)
    classes: dict[str, int] = field(default_factory=dict)
    chegadas: int = 0
    atendidos_prioridade: list[str] = field(default_factory=list)
    atendidos_fifo: list[str] = field(default_factory=list)
    passos: list[Passo] = field(default_factory=list)

    @classmethod
    def exemplo(cls) -> "LaboratorioFila":
        """Três pessoas: duas sem preferência e, por último, uma com preferência."""
        lab = cls()
        for classe in (3, 3, 1):
            lab.inserir(classe)
        return lab

    def proximo_nome(self) -> str:
        base = NOMES[self.chegadas % len(NOMES)]
        return base if self.chegadas < len(NOMES) else f"{base} {self.chegadas // len(NOMES) + 1}"

    def inserir(self, classe: int) -> Passo:
        nome = self.proximo_nome()
        antes = self.fila.array_interno()
        # chave igual à da PoliticaEleitoral: (classe, chegada, seq) — aqui a chegada é a ordem de entrada
        self.fila.inserir(nome, (classe, self.chegadas, self.chegadas))
        self.fifo.append(nome)
        self.classes[nome] = classe
        self.chegadas += 1
        depois = self.fila.array_interno()
        final = next(i for i, x in enumerate(depois) if x.eleitor_id == nome)
        subidas = int(math.floor(math.log2(len(antes) + 1))) - int(math.floor(math.log2(final + 1)))
        explicacao = (f"{nome} ({CLASSES[classe][1]}) entrou no fim do array, no índice {len(antes)}. "
                      + (f"Como a chave dele(a) era menor que a do pai, subiu {subidas} nível(is) e parou no "
                         f"índice {final}." if final != len(antes) else
                         "A chave não era menor que a do pai, então ficou onde entrou.")
                      + f" Custo: no máximo {_altura(len(depois))} comparações (altura da árvore), ou seja, O(log n).")
        return self._registrar("inserir", nome, antes, depois, explicacao)

    def extrair(self) -> Passo | None:
        if not len(self.fila):
            return None
        antes = self.fila.array_interno()
        entrada = self.fila.extrair_minimo()
        nome = entrada.eleitor_id
        # a fila comum (FIFO) teria chamado quem chegou primeiro entre os mesmos que esperavam
        self.atendidos_fifo.append(self.fifo[0])
        self.atendidos_prioridade.append(nome)
        self.fifo.remove(nome)
        depois = self.fila.array_interno()
        explicacao = (f"{nome} estava na raiz (índice 0): é a menor chave, {_chave(entrada)}. Saiu da heap; o último "
                      "elemento ocupou a raiz e desceu trocando com o filho de menor chave até a ordem pai ≤ filhos "
                      f"voltar a valer. Custo: no máximo {_altura(len(antes))} níveis, O(log n).")
        return self._registrar("extrair", nome, antes, depois, explicacao)

    def _registrar(self, op, nome, antes, depois, explicacao) -> Passo:
        n = max(len(antes), len(depois))
        mudaram = [i for i in range(n)
                   if (antes[i].eleitor_id if i < len(antes) else None) != (depois[i].eleitor_id if i < len(depois) else None)]
        passo = Passo(op, nome, antes, depois, mudaram, explicacao)
        self.passos.append(passo)
        return passo

    def ordem_prioridade(self) -> list[str]:
        """Sequência completa de atendimento (cópia ordenada; a heap física não muda)."""
        return [x.eleitor_id for x in self.fila.ordem_efetiva()]

    def ordem_fifo(self) -> list[str]:
        """Mesmas pessoas que estão na heap, em ordem de chegada: o que uma fila comum faria."""
        return list(self.fifo)


def _altura(n: int) -> int:
    return int(math.floor(math.log2(n))) if n > 0 else 0


def _chave(e: EntradaFila) -> str:
    c = e.chave
    return f"(classe {c[0]}, chegada {c[1]}, seq {c[2]})"
