"""Interface Streamlit via AppTest: visões, reruns, pausa, avanço unitário e modo apresentação."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("secao8bit.ui.sessao.BANCO", tmp_path / "teste.sqlite3")
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["visao"] = "ao_vivo"
    at.run()
    assert not at.exception, at.exception
    return at


def _botao(at, rotulo):
    return next(b for b in at.button if b.label.startswith(rotulo))


@pytest.mark.parametrize("visao", ["entenda", "ao_vivo", "algoritmo", "resultados"])
def test_cada_visao_renderiza_sem_erro(app, visao):
    app.session_state["visao"] = visao
    app.run()
    assert not app.exception, app.exception
    assert any("sem vínculo oficial" in c.value for c in app.sidebar.caption)


def test_visoes_preservam_a_simulacao(app):
    s = app.session_state["sessao"]
    s.avancar_ate_chamada()
    antes = (s.motor.estado.eventos_processados, s.motor.execucao_id)
    for v in ["entenda", "algoritmo", "resultados", "ao_vivo"]:
        app.session_state["visao"] = v
        app.run()
    s = app.session_state["sessao"]
    assert (s.motor.estado.eventos_processados, s.motor.execucao_id) == antes


def test_proxima_chamada_para_logo_apos_uma_saida_da_fila(app):
    s = app.session_state["sessao"]
    _botao(app, "⏭ Próxima chamada").click().run()
    assert not app.exception
    s = app.session_state["sessao"]
    saidas = [r for r in s.motor.log if r.tipo == "SAIDA_FILA"]
    assert len(saidas) == 1 and s.motor.estado.ultima_chamada["eleitor"] == saidas[0].eleitor_id
    assert not s.rodando


def test_recomecar_demo_usa_cenario_fixo(app):
    _botao(app, "⟳ Recomeçar demo").click().run()
    cfg = app.session_state["sessao"].config
    assert (cfg.cenario, cfg.seed, cfg.politica) == ("demo_7min", 2026, "eleitoral")


def test_laboratorio_da_visao_1_usa_a_heap_real(app):
    app.session_state["visao"] = "entenda"
    app.run()
    _botao(app, "+ Mais de 80").click().run()
    lab = app.session_state["lab_heap"]
    assert lab.ordem_prioridade()[0] == "Davi" and lab.fila.invariante_ok()
    _botao(app, "Chamar próximo").click().run()
    assert app.session_state["lab_heap"].atendidos_prioridade == ["Davi"]
    assert app.session_state["lab_heap"].atendidos_fifo == ["Ana"]


def test_modo_apresentacao_nao_quebra(app):
    app.toggle(key="modo_apresentacao").set_value(True).run()
    assert not app.exception
    assert any("Próximo a ser chamado" in h.body or "Ninguém esperando" in h.body for h in app.get("html"))


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
    _botao(app, "⏭ 1 evento").click().run()
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
