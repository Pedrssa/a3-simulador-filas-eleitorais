"""Registros de auditoria (modelo) e porta de persistência.

O hash encadeado (SHA-256 do registro + hash anterior) detecta alteração ou
remoção isolada de um registro. LIMITE: sozinho, não impede que alguém com
controle total do banco reescreva TODO o histórico e recalcule os hashes;
para isso seria preciso ancorar o último hash fora do sistema (ex.: publicado
ou assinado por terceiro).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Protocol

HASH_INICIAL = "0" * 64


@dataclass(frozen=True)
class RegistroAuditoria:
    execucao_id: str
    seq: int
    instante: float
    hora_simulada: str
    eleitor_id: str | None
    tipo: str
    estado_anterior: str | None
    estado_posterior: str | None
    justificativa: str
    politica_versao: str
    dados: dict
    hash_anterior: str
    hash: str

    @property
    def evento_id(self) -> str:
        return f"{self.execucao_id}:{self.seq:06d}"

    @property
    def dados_json(self) -> str:
        return json.dumps(self.dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def calcular_hash(execucao_id: str, seq: int, instante: float, eleitor_id: str | None, tipo: str,
                  anterior: str | None, posterior: str | None, justificativa: str,
                  politica_versao: str, dados_json: str, hash_anterior: str) -> str:
    canonico = json.dumps(
        [execucao_id, seq, round(instante, 6), eleitor_id, tipo, anterior, posterior,
         justificativa, politica_versao, dados_json, hash_anterior],
        ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def verificar_cadeia(registros: list[RegistroAuditoria]) -> tuple[bool, str]:
    anterior = HASH_INICIAL
    for r in sorted(registros, key=lambda r: r.seq):
        if r.hash_anterior != anterior:
            return False, f"seq {r.seq}: hash_anterior não confere"
        esperado = calcular_hash(r.execucao_id, r.seq, r.instante, r.eleitor_id, r.tipo,
                                 r.estado_anterior, r.estado_posterior, r.justificativa,
                                 r.politica_versao, r.dados_json, r.hash_anterior)
        if esperado != r.hash:
            return False, f"seq {r.seq}: conteúdo alterado (hash difere)"
        anterior = r.hash
    return True, f"{len(registros)} registros íntegros"


@dataclass(frozen=True)
class RegistroEleitor:
    execucao_id: str
    eleitor_id: str
    apelido: str
    chegada: float
    classe: str
    fundamento: str
    origem: str
    acompanha: str | None


@dataclass(frozen=True)
class RegistroExecucao:
    execucao_id: str
    criada_em: str
    seed: int
    cenario: str
    politica: str
    politica_versao: str
    config_json: str


class ErroPersistencia(RuntimeError):
    """A auditoria falhou: o passo da simulação deve ser desfeito."""


class PortaAuditoria(Protocol):
    def registrar_execucao(self, execucao: RegistroExecucao) -> None: ...

    def gravar_lote(self, eleitores: list[RegistroEleitor], registros: list[RegistroAuditoria]) -> None: ...


class AuditoriaEmMemoria:
    """Implementação sem banco, usada na comparação de políticas e em testes."""

    def __init__(self) -> None:
        self.execucoes: list[RegistroExecucao] = []
        self.eleitores: list[RegistroEleitor] = []
        self.registros: list[RegistroAuditoria] = []

    def registrar_execucao(self, execucao: RegistroExecucao) -> None:
        self.execucoes.append(execucao)

    def gravar_lote(self, eleitores: list[RegistroEleitor], registros: list[RegistroAuditoria]) -> None:
        self.eleitores.extend(eleitores)
        self.registros.extend(registros)


def como_linha(r: RegistroAuditoria) -> dict:
    d = asdict(r)
    d["evento_id"] = r.evento_id
    d["dados_json"] = r.dados_json
    d.pop("dados")
    return d
