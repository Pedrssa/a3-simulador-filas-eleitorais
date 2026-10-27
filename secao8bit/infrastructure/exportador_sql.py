"""Exportação dos logs de auditoria para um arquivo .sql executável.

Ordem de inserção: execucao → eleitor → evento_auditoria (respeita as FKs).
Literais: NULL, inteiros, reais com repr exato, textos entre aspas simples
com aspas internas duplicadas (padrão SQL). O caractere NUL é rejeitado.
"""

from __future__ import annotations

from pathlib import Path

from secao8bit.infrastructure.repositorio_sqlite import (
    COLUNAS_ELEITOR, COLUNAS_EVENTO, COLUNAS_EXECUCAO, SCHEMA, RepositorioAuditoria, conectar,
)


def literal_sql(valor) -> str:
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        return repr(valor)
    texto = str(valor)
    if "\x00" in texto:
        raise ValueError("texto com caractere NUL não pode ser exportado")
    return "'" + texto.replace("'", "''") + "'"


def _inserts(tabela: str, colunas: tuple[str, ...], linhas: list[tuple]) -> list[str]:
    cab = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES "
    return [cab + "(" + ", ".join(literal_sql(v) for v in linha) + ");" for linha in linhas]


def exportar_logs(repo: RepositorioAuditoria, execucao_id: str) -> str:
    partes = [
        "-- SEÇÃO 8-BIT — logs de auditoria (simulação acadêmica, dados fictícios)",
        f"-- execução: {execucao_id}",
        "-- Execute após sql/schema.sql:  sqlite3 banco.db < schema.sql && sqlite3 banco.db < logs.sql",
        "PRAGMA foreign_keys = ON;",
        "BEGIN TRANSACTION;",
    ]
    partes += _inserts("execucao", COLUNAS_EXECUCAO, repo.linhas("execucao", execucao_id))
    partes += _inserts("eleitor", COLUNAS_ELEITOR, repo.linhas("eleitor", execucao_id))
    partes += _inserts("evento_auditoria", COLUNAS_EVENTO, repo.linhas("evento_auditoria", execucao_id))
    partes.append("COMMIT;")
    return "\n".join(partes) + "\n"


def validar_importacao(repo: RepositorioAuditoria, execucao_id: str, sql_logs: str) -> dict:
    """Importa schema + logs num banco vazio e compara todas as linhas."""
    destino = conectar(":memory:")
    destino.executescript(SCHEMA.read_text(encoding="utf-8"))
    destino.executescript(sql_logs)
    resultado = {}
    for tabela, colunas, ordem in (
        ("execucao", COLUNAS_EXECUCAO, "execucao_id"),
        ("eleitor", COLUNAS_ELEITOR, "chegada_min, eleitor_id"),
        ("evento_auditoria", COLUNAS_EVENTO, "seq"),
    ):
        original = repo.linhas(tabela, execucao_id)
        importado = [tuple(r) for r in destino.execute(
            f"SELECT {', '.join(colunas)} FROM {tabela} WHERE execucao_id = ? ORDER BY {ordem}", (execucao_id,))]
        resultado[tabela] = {"original": len(original), "importado": len(importado), "iguais": original == importado}
    fk = destino.execute("PRAGMA foreign_key_check").fetchall()
    resultado["violacoes_fk"] = len(fk)
    resultado["ok"] = all(v["iguais"] for k, v in resultado.items() if isinstance(v, dict)) and not fk
    destino.close()
    return resultado


def salvar(caminho: str | Path, conteudo: str) -> Path:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(conteudo, encoding="utf-8", newline="\n")
    return p

