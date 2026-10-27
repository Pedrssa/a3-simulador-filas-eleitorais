"""Fila de prioridade baseada em heap binária mínima (módulo heapq).

Por que heap: a operação dominante é "inserir" e "retirar o de menor chave";
ambas custam O(log n), contra O(n) de uma lista ordenada por inserção.

| Operação                    | Complexidade | Observação                                   |
|-----------------------------|--------------|----------------------------------------------|
| inserir                     | O(log n)     | heappush                                     |
| extrair_minimo              | O(log n)     | heappop                                      |
| espiar                      | O(1)         | heap[0]                                      |
| reconstruir (aging)         | O(n)         | recalcula todas as chaves + heapify          |
| remover / extrair_onde      | O(n)         | busca linear + heapify (uso raro: cotas)     |
| ordem_efetiva               | O(n log n)   | cópia ordenada, só para exibição             |

O array interno NÃO é uma lista totalmente ordenada: só garante que cada pai
é menor ou igual aos filhos (índices 2i+1 e 2i+2).

Quando a chave depende do tempo (aging), alterar um atributo do eleitor não
reorganiza a heap sozinho: é preciso chamar `reconstruir` com as novas chaves.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Callable, Iterator

Chave = tuple


@dataclass(frozen=True, order=True)
class EntradaFila:
    chave: Chave
    ordem_insercao: int
    eleitor_id: str


class FilaPrioridade:
    def __init__(self) -> None:
        self._heap: list[EntradaFila] = []
        self._ids: set[str] = set()
        self._contador = 0

    def __len__(self) -> int:
        return len(self._heap)

    def __contains__(self, eleitor_id: str) -> bool:
        return eleitor_id in self._ids

    def __iter__(self) -> Iterator[EntradaFila]:
        return iter(list(self._heap))

    def inserir(self, eleitor_id: str, chave: Chave) -> EntradaFila:
        if eleitor_id in self._ids:
            raise ValueError(f"{eleitor_id} já está na fila")
        entrada = EntradaFila(chave, self._contador, eleitor_id)
        self._contador += 1
        heapq.heappush(self._heap, entrada)
        self._ids.add(eleitor_id)
        return entrada

    def espiar(self) -> EntradaFila | None:
        return self._heap[0] if self._heap else None

    def extrair_minimo(self) -> EntradaFila:
        if not self._heap:
            raise IndexError("fila vazia")
        entrada = heapq.heappop(self._heap)
        self._ids.discard(entrada.eleitor_id)
        return entrada

    def extrair_onde(self, predicado: Callable[[EntradaFila], bool]) -> EntradaFila | None:
        candidatos = [e for e in self._heap if predicado(e)]
        if not candidatos:
            return None
        escolhido = min(candidatos)
        self.remover(escolhido.eleitor_id)
        return escolhido

    def remover(self, eleitor_id: str) -> EntradaFila:
        for i, entrada in enumerate(self._heap):
            if entrada.eleitor_id == eleitor_id:
                ultimo = self._heap.pop()
                if i < len(self._heap):
                    self._heap[i] = ultimo
                    heapq.heapify(self._heap)
                self._ids.discard(eleitor_id)
                return entrada
        raise KeyError(eleitor_id)

    def reconstruir(self, calcular_chave: Callable[[str], Chave]) -> int:
        """Recalcula as chaves de todos e refaz a heap. Retorna quantas mudaram."""
        mudaram = 0
        novas = []
        for e in self._heap:
            chave = calcular_chave(e.eleitor_id)
            if chave != e.chave:
                mudaram += 1
            novas.append(EntradaFila(chave, e.ordem_insercao, e.eleitor_id))
        heapq.heapify(novas)
        self._heap = novas
        return mudaram

    def array_interno(self) -> list[EntradaFila]:
        return list(self._heap)

    def ordem_efetiva(self) -> list[EntradaFila]:
        return sorted(self._heap)

    def invariante_ok(self) -> bool:
        h = self._heap
        return all(
            h[i] <= h[f]
            for i in range(len(h))
            for f in (2 * i + 1, 2 * i + 2)
            if f < len(h)
        ) and len(self._ids) == len(h)
