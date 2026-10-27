"""Interface Streamlit via AppTest: abas, reruns, pausa e avanço unitário."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("secao8bit.ui.sessao.BANCO", tmp_path / "teste.sqlite3")
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def _botao(at, rotulo):
    return next(b for b in at.button if b.label.startswith(rotulo))


def test_seis_abas_e_aviso_academico(app):
    rotulos = [t.label for t in app.tabs]
    assert rotulos == ["A. Simulação 8 bits", "B. Código em execução", "C. Filas e algoritmo",
                       "D. Métricas e SLA", "E. Auditoria SQL", "F. Regras e documentação"]
    assert any("sem vínculo oficial" in c.value for c in app.sidebar.caption)


def test_reruns_nao_duplicam_nem_avancam_eventos(app):
    s = app.session_state["sessao"]
    antes = (s.motor.estado.eventos_processados, len(s.motor.log), s.motor.execucao_id)
    for _ in range(3):
        app.run()  # equivalente a interações/troca de aba: o script roda de novo
    assert not app.exception
    s = app.session_state["sessao"]
    assert (s.motor.estado.eventos_processados, len(s.motor.log), s.motor.execucao_id) == antes


def test_avancar_um_evento_processa_exatamente_um(app):
    s = app.session_state["sessao"]
    antes = s.motor.estado.eventos_processados
    _botao(app, "⏭").click().run()
    assert not app.exception
    s = app.session_state["sessao"]
    assert s.motor.estado.eventos_processados == antes + 1
    assert not s.rodando


def test_iniciar_e_pausar(app):
    _botao(app, "▶").click().run()
    assert app.session_state["sessao"].rodando
    _botao(app, "⏸").click().run()
    s = app.session_state["sessao"]
    assert not s.rodando
    parado = s.motor.estado.eventos_processados
    app.run()
    assert app.session_state["sessao"].motor.estado.eventos_processados == parado


def test_reiniciar_cria_nova_execucao(app):
    antigo = app.session_state["sessao"].motor.execucao_id
    _botao(app, "⟲").click().run()
    assert not app.exception
    assert app.session_state["sessao"].motor.execucao_id != antigo



def test_troca_politica_sincroniza_sessao_e_preserva_apos_reiniciar(app):
    next(s for s in app.selectbox if s.label == "Política").select("aging").run()
    _botao(app, "Trocar política agora").click().run()
    assert not app.exception
    s = app.session_state["sessao"]
    assert s.config == s.motor.config
    assert s.config.politica == "aging"
    assert s.config.politica_params == {"intervalo_min": 15.0}
    assert len(app.toast) == 1
    app.run()
    assert not any(b.label.startswith("Trocar política agora") for b in app.button)
    s.reiniciar()
    assert s.motor.politica.experimental and s.config.politica == "aging"


def test_troca_com_falha_nao_exibe_sucesso_nem_altera_config(app, monkeypatch):
    from secao8bit.application.auditoria import ErroPersistencia
    next(s for s in app.selectbox if s.label == "Política").select("aging").run()
    s = app.session_state["sessao"]
    antes = s.config
    total = s.repo.total_eventos(s.motor.execucao_id)

    def falhar(*args):
        raise ErroPersistencia("disco cheio (simulado)")

    monkeypatch.setattr(s.repo, "gravar_lote", falhar)
    _botao(app, "Trocar política agora").click().run()
    assert not app.exception
    assert not app.toast
    assert app.error
    assert s.erro and not s.rodando
    assert s.config == s.motor.config == antes
    assert not s.motor.politica.experimental
    assert s.repo.total_eventos(s.motor.execucao_id) == total
