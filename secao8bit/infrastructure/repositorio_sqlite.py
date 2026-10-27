"""Repositório de auditoria em SQLite.

- Cada lote é gravado numa única transação (tudo ou nada).
- Chaves estrangeiras ligadas (PRAGMA foreign_keys = ON).
- Somente consultas parametrizadas (placeholders "?").
- UNIQUE(execucao_id, seq) impede duplicação; não usamos INSERT OR IGNORE para
  que uma tentativa de duplicar apareça como erro, e não seja escondida.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from secao8bit.application.auditoria import (
    RegistroAuditoria, RegistroEleitor, RegistroExecucao, verificar_cadeia,
)

SCHEMA = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

COLUNAS_EVENTO = ("evento_id", "execucao_id", "seq", "instante_min", "hora_simulada", "eleitor_id", "tipo",
                  "estado_anterior", "estado_posterior", "justificativa", "politica_versao", "dados_json",
                  "hash_anterior", "hash")
COLUNAS_ELEITOR = ("execucao_id", "eleitor_id", "apelido", "chegada_min", "classe", "fundamento", "origem", "acompanha")
COLUNAS_EXECUCAO = ("execucao_id", "criada_em", "seed", "cenario", "politica", "politica_versao", "config_json")


def conectar(caminho: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(caminho), check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def aplicar_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))


class RepositorioAuditoria:
    def __init__(self, caminho: str | Path = ":memory:") -> None:
        self.caminho = str(caminho)
        if self.caminho != ":memory:":
            Path(self.caminho).parent.mkdir(parents=True, exist_ok=True)
        self.conn = conectar(self.caminho)
        aplicar_schema(self.conn)

    def registrar_execucao(self, execucao: RegistroExecucao) -> None:
        with self._transacao() as cur:
            cur.execute(
                f"INSERT INTO execucao ({', '.join(COLUNAS_EXECUCAO)}) VALUES ({', '.join('?' * len(COLUNAS_EXECUCAO))})",
                (execucao.execucao_id, execucao.criada_em, execucao.seed, execucao.cenario,
                 execucao.politica, execucao.politica_versao, execucao.config_json),
            )

    def gravar_lote(self, eleitores: list[RegistroEleitor], registros: list[RegistroAuditoria]) -> None:
        """Grava eleitores novos e registros de auditoria numa única transação."""
        with self._transacao() as cur:
            cur.executemany(
                f"INSERT INTO eleitor ({', '.join(COLUNAS_ELEITOR)}) VALUES ({', '.join('?' * len(COLUNAS_ELEITOR))})",
                [(e.execucao_id, e.eleitor_id, e.apelido, e.chegada, e.classe, e.fundamento, e.origem, e.acompanha)
                 for e in eleitores],
            )
            cur.executemany(
                f"INSERT INTO evento_auditoria ({', '.join(COLUNAS_EVENTO)}) VALUES ({', '.join('?' * len(COLUNAS_EVENTO))})",
                [(r.evento_id, r.execucao_id, r.seq, r.instante, r.hora_simulada, r.eleitor_id, r.tipo,
                  r.estado_anterior, r.estado_posterior, r.justificativa, r.politica_versao, r.dados_json,
                  r.hash_anterior, r.hash) for r in registros],
            )

    @contextmanager
    def _transacao(self) -> Iterator[sqlite3.Cursor]:
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            yield cur
        except BaseException:
            cur.execute("ROLLBACK")
            raise
        cur.execute("COMMIT")

    # ---------------------------------------------------------------- consultas
    def eventos(self, execucao_id: str, tipo: str | None = None, eleitor_id: str | None = None,
                limite: int = 500) -> list[dict]:
        sql = "SELECT * FROM evento_auditoria WHERE execucao_id = ?"
        params: list = [execucao_id]
        if tipo:
            sql += " AND tipo = ?"
            params.append(tipo)
        if eleitor_id:
            sql += " AND eleitor_id = ?"
            params.append(eleitor_id)
        sql += " ORDER BY seq DESC LIMIT ?"
        params.append(int(limite))
        return [dict(r) for r in self.conn.execute(sql, params)]

    def contagem_por_tipo(self, execucao_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT tipo, COUNT(*) AS total FROM evento_auditoria WHERE execucao_id = ? GROUP BY tipo ORDER BY total DESC",
            (execucao_id,))]

    def total_eventos(self, execucao_id: str) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM evento_auditoria WHERE execucao_id = ?",
                                 (execucao_id,)).fetchone()[0]

    def registros(self, execucao_id: str) -> list[RegistroAuditoria]:
        linhas = self.conn.execute("SELECT * FROM evento_auditoria WHERE execucao_id = ? ORDER BY seq", (execucao_id,))
        return [RegistroAuditoria(r["execucao_id"], r["seq"], r["instante_min"], r["hora_simulada"], r["eleitor_id"],
                                  r["tipo"], r["estado_anterior"], r["estado_posterior"], r["justificativa"],
                                  r["politica_versao"], json.loads(r["dados_json"]), r["hash_anterior"], r["hash"])
                for r in linhas]

    def verificar_integridade(self, execucao_id: str) -> tuple[bool, str]:
        return verificar_cadeia(self.registros(execucao_id))

    def linhas(self, tabela: str, execucao_id: str) -> list[tuple]:
        colunas = {"execucao": COLUNAS_EXECUCAO, "eleitor": COLUNAS_ELEITOR, "evento_auditoria": COLUNAS_EVENTO}[tabela]
        ordem = {"execucao": "execucao_id", "eleitor": "chegada_min, eleitor_id", "evento_auditoria": "seq"}[tabela]
        return [tuple(r) for r in self.conn.execute(
            f"SELECT {', '.join(colunas)} FROM {tabela} WHERE execucao_id = ? ORDER BY {ordem}", (execucao_id,))]

    def fechar(self) -> None:
        self.conn.close()
