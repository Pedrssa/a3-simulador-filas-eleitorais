"""Auditoria SQL: transações, rollback, duplicação, exportação/importação e hash."""

import sqlite3

import pytest

from secao8bit.application.auditoria import ErroPersistencia, verificar_cadeia
from secao8bit.application.config import config_do_cenario
from secao8bit.application.motor import MotorSimulacao
from secao8bit.infrastructure.exportador_sql import exportar_logs, literal_sql, validar_importacao
from secao8bit.infrastructure.repositorio_sqlite import RepositorioAuditoria


class RepositorioQueFalha(RepositorioAuditoria):
    """Falha no meio do lote, depois de já ter inserido parte dele."""

    def __init__(self):
        super().__init__(":memory:")
        self.falhar = False

    def gravar_lote(self, eleitores, registros):
        if not self.falhar:
            return super().gravar_lote(eleitores, registros)
        with self._transacao() as cur:
            cur.execute("INSERT INTO evento_auditoria (evento_id, execucao_id, seq, instante_min, hora_simulada, "
                        "tipo, justificativa, politica_versao, dados_json, hash_anterior, hash) "
                        "VALUES ('parcial', ?, 999999, 0, '', 'X', '', '', '{}', '', '')",
                        (registros[0].execucao_id,))
            raise sqlite3.OperationalError("disco cheio (simulado)")


def test_falha_de_auditoria_desfaz_o_passo_e_nao_grava_parcial():
    repo = RepositorioQueFalha()
    m = MotorSimulacao(config_do_cenario("normal"), repo)
    m.avancar_ate(15)
    antes = (m.agora, m.estado.eventos_processados, len(m.secao.fila), m.estado.seq_auditoria,
             {e.id: e.estado for e in m.secao.eleitores.values()}, len(m.log), m.rastreador.total)
    total_db = repo.total_eventos(m.execucao_id)

    repo.falhar = True
    with pytest.raises(ErroPersistencia):
        m.avancar_ate(30)
    depois = (m.agora, m.estado.eventos_processados, len(m.secao.fila), m.estado.seq_auditoria,
              {e.id: e.estado for e in m.secao.eleitores.values()}, len(m.log), m.rastreador.total)
    assert depois == antes  # estado do motor restaurado
    assert repo.total_eventos(m.execucao_id) == total_db  # nada parcial no banco
    assert m.ultimo_erro and "Falha de auditoria" in m.ultimo_erro

    repo.falhar = False  # após corrigir, a simulação continua com a cadeia íntegra
    m.executar_tudo()
    assert repo.verificar_integridade(m.execucao_id)[0]
    assert repo.total_eventos(m.execucao_id) == len(m.log)


def test_unique_impede_duplicacao_silenciosa():
    repo = RepositorioAuditoria(":memory:")
    m = MotorSimulacao(config_do_cenario("normal"), repo)
    m.avancar_ate(5)
    with pytest.raises(sqlite3.IntegrityError):
        repo.gravar_lote([], [m.log[-1]])  # repetir um registro (ex.: rerun mal feito) é erro, não ignorado


def test_exportacao_importacao_em_banco_vazio_e_equivalencia():
    repo = RepositorioAuditoria(":memory:")
    m = MotorSimulacao(config_do_cenario("demo_7min"), repo)
    m.executar_tudo()
    sql = exportar_logs(repo, m.execucao_id)
    r = validar_importacao(repo, m.execucao_id, sql)
    assert r["ok"], r
    assert r["evento_auditoria"]["importado"] == len(m.log)
    assert sql.index("INSERT INTO execucao") < sql.index("INSERT INTO eleitor") < sql.index("INSERT INTO evento_auditoria")


def test_escaping_de_literais():
    assert literal_sql("d'água") == "'d''água'"
    assert literal_sql("'; DROP TABLE eleitor; --") == "'''; DROP TABLE eleitor; --'"
    assert literal_sql(None) == "NULL"
    assert literal_sql(1.25) == "1.25"
    with pytest.raises(ValueError):
        literal_sql("a\x00b")


def test_texto_hostil_sobrevive_ida_e_volta():
    repo = RepositorioAuditoria(":memory:")
    m = MotorSimulacao(config_do_cenario("normal"), repo)
    m._transacao(lambda: m._auditar("TESTE", "aspas ' \" ; -- e quebra\nde linha", nota="O'Brien"))
    sql = exportar_logs(repo, m.execucao_id)
    assert validar_importacao(repo, m.execucao_id, sql)["ok"]


def test_hash_encadeado_detecta_adulteracao():
    m = MotorSimulacao(config_do_cenario("normal"))
    m.executar_tudo()
    assert verificar_cadeia(m.log)[0]
    from dataclasses import replace
    adulterado = list(m.log)
    adulterado[10] = replace(adulterado[10], justificativa="texto trocado")
    ok, msg = verificar_cadeia(adulterado)
    assert not ok and "seq 11" in msg
    removido = m.log[:10] + m.log[11:]
    assert not verificar_cadeia(removido)[0]


def test_logs_nao_contem_dados_de_voto():
    m = MotorSimulacao(config_do_cenario("demo_7min"))
    m.executar_tudo()
    for r in m.log:
        chaves = {k.lower() for k in r.dados}
        assert not chaves & {"voto", "candidato_escolhido", "escolha", "cpf", "titulo"}
