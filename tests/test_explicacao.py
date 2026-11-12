"""As explicações em linguagem natural descrevem a decisão REAL do motor."""

import pytest

from secao8bit.application.config import config_do_cenario
from secao8bit.application.didatica import LaboratorioFila
from secao8bit.application.explicacao import explicar_proximo, explicar_ultima_chamada
from secao8bit.application.motor import MotorSimulacao


def _rodar_ate_chamadas(m, n):
    chamadas = []
    while len(chamadas) < n and not m.concluida:
        antes = len(m.log)
        m.passo()
        chamadas += [r for r in m.log[antes:] if r.tipo == "SAIDA_FILA"]
    return chamadas


@pytest.mark.parametrize("politica", ["eleitoral", "aging", "cotas"])
def test_ultima_chamada_corresponde_ao_registro_de_auditoria(politica):
    m = MotorSimulacao(config_do_cenario("demo_7min").com(politica=politica, politica_params={}))
    vistos = 0
    while not m.concluida and vistos < 40:
        antes = len(m.log)
        m.passo()
        for r in (r for r in m.log[antes:] if r.tipo == "SAIDA_FILA"):
            vistos += 1
            u = m.estado.ultima_chamada
            assert u["eleitor"] == r.eleitor_id and u["chave"] == r.dados["chave"]
            exp = explicar_ultima_chamada(m)
            assert exp.pessoa == r.eleitor_id
            assert exp.ultrapassou == len(u["ultrapassou"])
            # quem foi ultrapassado chegou antes e ainda está na fila
            el = m.secao.eleitores
            for i in u["ultrapassou"]:
                assert (el[i].chegada, el[i].seq_chegada) < (el[r.eleitor_id].chegada, el[r.eleitor_id].seq_chegada)
                assert i in m.secao.fila
            if politica != "eleitoral" and exp.regra != "senha":
                assert "laboratório" in exp.texto.lower()
    assert vistos > 10


def test_proximo_explicado_e_o_primeiro_da_projecao():
    m = MotorSimulacao(config_do_cenario("demo_7min"))
    _rodar_ate_chamadas(m, 12)
    ordem = m.prever_atendimento()
    exp = explicar_proximo(m)
    assert ordem and exp.pessoa == ordem[0].eleitor_id


def test_ultrapassagem_por_80_mais_cita_o_paragrafo_3():
    m = MotorSimulacao(config_do_cenario("demo_7min"))
    while not m.concluida:
        m.passo()
        u = m.estado.ultima_chamada
        if u and u["ultrapassou"] and u["chave"][0] == 0:
            texto = explicar_ultima_chamada(m).texto
            assert "mais de 80 anos" in texto and "§ 3º" in texto and "Por isso foi chamado(a) antes" in texto
            return
    pytest.fail("cenário de demonstração sem ultrapassagem por pessoa 80+")


def test_fila_vazia_tem_mensagem_de_acao():
    m = MotorSimulacao(config_do_cenario("demo_7min"))
    assert explicar_ultima_chamada(m) is None
    assert "vazia" in explicar_proximo(m).texto


def test_laboratorio_fifo_x_prioridade_e_invariante():
    lab = LaboratorioFila.exemplo()
    assert lab.ordem_fifo() == ["Ana", "Bruno", "Carla"]
    assert lab.ordem_prioridade() == ["Carla", "Ana", "Bruno"]
    for c in (0, 3, 2, 1, 3, 0):
        lab.inserir(c)
        assert lab.fila.invariante_ok()
    ordem = lab.ordem_prioridade()
    while len(lab.fila):
        p = lab.extrair()
        assert p.pessoa == ordem.pop(0)
        assert lab.fila.invariante_ok()
    assert lab.ordem_fifo() == []


def test_laboratorio_marca_posicoes_que_mudaram():
    lab = LaboratorioFila()
    lab.inserir(3)
    lab.inserir(3)
    p = lab.inserir(0)  # menor chave: sobe do índice 2 para a raiz
    assert p.mudaram == [0, 2]
    assert "subiu 1 nível" in p.explicacao
