"""Coerência entre motor, código destacado e cena 8 bits."""

import pytest

from secao8bit.application.cena import montar_cena
from secao8bit.application.config import config_do_cenario
from secao8bit.application.motor import MotorSimulacao
from secao8bit.application.rastreamento import PONTOS
from secao8bit.domain.eleitor import EstadoEleitor


@pytest.mark.parametrize("cenario", ["demo_7min", "encerramento", "aleatorio"])
def test_cena_reflete_exatamente_o_estado_do_motor(cenario):
    m = MotorSimulacao(config_do_cenario(cenario))
    while not m.concluida:
        m.passo()
        cena = montar_cena(m)
        pessoas = {p["id"]: p for p in cena["pessoas"] if p["tipo"] == "eleitor"}
        ordem = [x.eleitor_id for x in m.secao.fila.ordem_efetiva()]
        # fila na cena = ordem efetiva da heap, vaga por vaga
        aguardando = [(p["posicao"], pid) for pid, p in pessoas.items() if p["zona"] in ("fila", "assento")]
        assert [pid for _, pid in sorted(aguardando)] == ordem
        # assentos só para quem tem preferência
        assert all(pessoas[pid]["classe"] < 3 for pid in pessoas if pessoas[pid]["zona"] == "assento")
        # cabine: no máximo uma pessoa, a mesma que ocupa a urna
        na_cabine = [pid for pid, p in pessoas.items() if p["zona"] in ("cabine", "habilitacao")]
        assert na_cabine == ([m.secao.urna.ocupante] if m.secao.urna.ocupante else [])
        assert cena["urna"]["estado"] == m.secao.urna.estado.name
        assert cena["fila_total"] == len(m.secao.fila)
        # a cena nunca mostra escolha de voto
        assert not any("voto em" in (p["balao"] or "").lower() for p in pessoas.values())


def test_codigo_destacado_e_a_linha_real_da_instrumentacao():
    m = MotorSimulacao(config_do_cenario("demo_7min", politica="aging"))
    m.executar_tudo()
    vistos = set()
    for passo in m.rastreador.passos:
        vistos.add(passo.ponto)
        linhas = passo.codigo.linhas_fonte()
        assert linhas, passo.codigo
        destacada = linhas[passo.codigo.linha_destacada - passo.codigo.primeira_linha]
        assert "rastreador.ponto(" in destacada, (passo.codigo.funcao, destacada)
        if passo.referencia:
            assert passo.referencia.linhas_fonte()[0].lstrip().startswith("def ")
    assert vistos == set(PONTOS)  # todos os pontos instrumentados foram exercitados


def test_selecao_no_rastreamento_bate_com_a_auditoria():
    m = MotorSimulacao(config_do_cenario("demo_7min"))
    m.executar_tudo()
    selecoes = [p.depois.removeprefix("chamado: ") for p in m.rastreador.passos if p.ponto == "selecao"]
    saidas = [r.eleitor_id for r in m.log if r.tipo == "SAIDA_FILA"]
    assert selecoes and selecoes == saidas[-len(selecoes):]  # o rastreador guarda só os últimos passos


def test_encaminhado_sai_pela_porta_na_cena():
    m = MotorSimulacao(config_do_cenario("normal"))
    while not m.concluida:
        m.passo()
        for p in montar_cena(m)["pessoas"]:
            if p["tipo"] == "eleitor" and p["estado"] == EstadoEleitor.ENCAMINHADO.value:
                assert p["zona"] == "saida" and p["balao"]
