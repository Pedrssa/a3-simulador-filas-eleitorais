"""Rastreamento por PONTOS INSTRUMENTADOS.

Não é um depurador linha a linha: cada chamada a `ponto()` registra o arquivo,
o método e a linha real de onde foi chamada (via frame do interpretador), junto
com variáveis escolhidas, estado anterior/posterior e o efeito esperado na cena.
A aba "Código em execução" lê o código-fonte real desses arquivos.
"""

from __future__ import annotations

import inspect
import linecache
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

RAIZ_PROJETO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ReferenciaCodigo:
    arquivo: str  # caminho absoluto
    funcao: str
    primeira_linha: int
    linha_destacada: int

    @property
    def arquivo_relativo(self) -> str:
        try:
            return Path(self.arquivo).resolve().relative_to(RAIZ_PROJETO).as_posix()
        except ValueError:
            return Path(self.arquivo).name

    def linhas_fonte(self) -> list[str]:
        linhas = linecache.getlines(self.arquivo)
        if not linhas:
            return []
        return inspect.getblock(linhas[self.primeira_linha - 1:])


def referencia_de(func: Callable) -> ReferenciaCodigo:
    func = inspect.unwrap(func)
    codigo = func.__code__
    return ReferenciaCodigo(codigo.co_filename, codigo.co_qualname, codigo.co_firstlineno, codigo.co_firstlineno)


@dataclass(frozen=True)
class PassoRastreado:
    n: int
    instante: float
    hora: str
    evento: str
    ponto: str
    codigo: ReferenciaCodigo
    explicacao: str
    antes: str
    depois: str
    animacao: str
    variaveis: dict[str, Any] = field(default_factory=dict)
    referencia: ReferenciaCodigo | None = None


PONTOS = {
    "criacao": "Criação e entrada do eleitor",
    "classificacao": "Classificação da prioridade",
    "insercao": "Inserção na fila de prioridade",
    "atualizacao_espera": "Atualização de espera / chaves (aging)",
    "selecao": "Seleção do próximo",
    "recurso": "Reserva e liberação de recurso",
    "incidente": "Resolução de evento/incidente",
    "auditoria": "Transação de auditoria",
}


class Rastreador:
    def __init__(self, limite: int = 1500) -> None:
        self.passos: list[PassoRastreado] = []
        self.limite = limite
        self.total = 0
        self.evento_atual = ""
        self.instante = 0.0
        self.hora = ""

    def contexto(self, evento: str, instante: float, hora: str) -> None:
        self.evento_atual, self.instante, self.hora = evento, instante, hora

    def ponto(self, ponto: str, explicacao: str, *, antes: str = "", depois: str = "",
              animacao: str = "", referencia: Callable | None = None, **variaveis: Any) -> None:
        if ponto not in PONTOS:
            raise ValueError(f"ponto de instrumentação desconhecido: {ponto}")
        frame = sys._getframe(1)
        codigo = frame.f_code
        ref = ReferenciaCodigo(codigo.co_filename, codigo.co_qualname, codigo.co_firstlineno, frame.f_lineno)
        self.total += 1
        self.passos.append(PassoRastreado(
            n=self.total, instante=self.instante, hora=self.hora, evento=self.evento_atual,
            ponto=ponto, codigo=ref, explicacao=explicacao, antes=antes, depois=depois,
            animacao=animacao, variaveis={k: _resumir(v) for k, v in variaveis.items()},
            referencia=referencia_de(referencia) if referencia else None,
        ))
        if len(self.passos) > self.limite:
            del self.passos[: len(self.passos) - self.limite]

    def marca(self) -> int:
        return self.total

    def desfazer_ate(self, total: int) -> None:
        """Usado no rollback: descarta passos de uma transação que falhou."""
        self.passos = [p for p in self.passos if p.n <= total]
        self.total = total


def _resumir(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 3)
    if isinstance(v, (list, tuple)) and len(v) > 12:
        return list(v[:12]) + [f"... (+{len(v) - 12})"]
    if isinstance(v, (int, str, bool, type(None), list, tuple, dict)):
        return v
    return str(v)
