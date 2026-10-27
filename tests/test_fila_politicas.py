"""Heap, ordem de prioridade, desempate estável, aging e cotas."""

from datetime import date

import pytest

from secao8bit.domain.fila import FilaPrioridade
from secao8bit.domain.politicas import PoliticaAging, PoliticaCotas, PoliticaEleitoral
from secao8bit.domain.prioridade import Condicao, PerfilPrioridade

COMUM = PerfilPrioridade(date(1990, 1, 1))
GESTANTE = PerfilPrioridade(date(1990, 1, 1), frozenset({Condicao.GESTANTE}))
IDOSO_85 = PerfilPrioridade(date(1940, 1, 1))


def montar(politica, pessoas, agora=0.0):
    fila = FilaPrioridade()
    eleitores = {e.id: e for e in pessoas}
    for e in pessoas:
        fila.inserir(e.id, politica.chave(e, agora))
    return fila, eleitores


def drenar(politica, fila, eleitores, agora=0.0):
    ordem = []
    while len(fila):
        if politica.depende_do_tempo:
            fila.reconstruir(lambda eid: politica.chave(eleitores[eid], agora))
        sel = politica.selecionar(fila, eleitores, agora)
        e = eleitores[sel.entrada.eleitor_id]
        politica.ao_atender(e, fila, eleitores)
        ordem.append(e.id)
    return ordem


def test_heap_rejeita_duplicado():
    f = FilaPrioridade()
    f.inserir("A", (1,))
    with pytest.raises(ValueError):
        f.inserir("A", (0,))


def test_array_interno_nao_e_lista_ordenada_mas_ordem_efetiva_e():
    f = FilaPrioridade()
    for i, k in enumerate([5, 3, 8, 1, 9, 2, 7]):
        f.inserir(f"x{i}", (k,))
    assert f.invariante_ok()
    interno = [e.chave[0] for e in f.array_interno()]
    efetiva = [e.chave[0] for e in f.ordem_efetiva()]
    assert efetiva == sorted(efetiva)
    assert interno != efetiva  # a heap só garante pai <= filhos


def test_remover_mantem_invariante():
    f = FilaPrioridade()
    for i, k in enumerate([5, 3, 8, 1, 9, 2, 7, 4]):
        f.inserir(f"x{i}", (k,))
    f.remover("x1")
    assert f.invariante_ok() and "x1" not in f and len(f) == 7


def test_ordem_eleitoral_mais_de_80_depois_preferencia_depois_comum(novo_eleitor):
    c = novo_eleitor(COMUM, chegada=0)
    g = novo_eleitor(GESTANTE, chegada=1)
    i = novo_eleitor(IDOSO_85, chegada=2)
    pol = PoliticaEleitoral()
    fila, el = montar(pol, [c, g, i])
    assert drenar(pol, fila, el) == [i.id, g.id, c.id]


def test_desempate_estavel_por_chegada(novo_eleitor):
    pessoas = [novo_eleitor(GESTANTE, chegada=t) for t in (3.0, 1.0, 1.0, 2.0)]
    pol = PoliticaEleitoral()
    fila, el = montar(pol, pessoas)
    ordem = drenar(pol, fila, el)
    # chegada 1.0 empatada: vence quem tem seq_chegada menor (chegou primeiro na fila indiana)
    assert ordem == [pessoas[1].id, pessoas[2].id, pessoas[3].id, pessoas[0].id]


def test_politica_eleitoral_nunca_promove_comum_por_espera(novo_eleitor):
    velho_comum = novo_eleitor(COMUM, chegada=0)
    recem_pref = novo_eleitor(GESTANTE, chegada=500)
    pol = PoliticaEleitoral()
    fila, el = montar(pol, [velho_comum, recem_pref], agora=600)
    assert drenar(pol, fila, el, agora=600)[0] == recem_pref.id


def test_aging_promove_comum_apos_intervalo_e_respeita_piso(novo_eleitor):
    comum = novo_eleitor(COMUM, chegada=0)
    pref = novo_eleitor(GESTANTE, chegada=20)
    idoso = novo_eleitor(IDOSO_85, chegada=29)
    pol = PoliticaAging(intervalo_min=10)
    assert pol.nivel_efetivo(comum, 9.9) == 3
    assert pol.nivel_efetivo(comum, 10.0) == 2
    assert pol.nivel_efetivo(comum, 30.0) == 1  # piso: não passa à frente de quem tem mais de 80
    fila, el = montar(pol, [comum, pref, idoso], agora=30)
    assert drenar(pol, fila, el, agora=30) == [idoso.id, comum.id, pref.id]


def test_aging_exige_reconstruir_a_heap(novo_eleitor):
    """Mudar o tempo não reorganiza a heap sozinho: é preciso recalcular chaves."""
    comum = novo_eleitor(COMUM, chegada=0)
    pref = novo_eleitor(GESTANTE, chegada=25)
    pol = PoliticaAging(intervalo_min=10)
    fila, el = montar(pol, [comum, pref], agora=0)  # chaves calculadas em t=0
    assert fila.espiar().eleitor_id == pref.id
    mudaram = fila.reconstruir(lambda eid: pol.chave(el[eid], 30.0))
    assert mudaram == 1  # só o comum mudou de nível; a chave do preferencial não depende da espera
    assert fila.espiar().eleitor_id == comum.id
    assert fila.invariante_ok()


def test_cotas_liberam_vaga_para_comum_mas_nao_furam_mais_de_80(novo_eleitor):
    comum = novo_eleitor(COMUM, chegada=0)
    prefs = [novo_eleitor(GESTANTE, chegada=1 + k) for k in range(5)]
    idoso = novo_eleitor(IDOSO_85, chegada=10)
    pol = PoliticaCotas(k=2)
    fila, el = montar(pol, [comum, *prefs, idoso])
    ordem = drenar(pol, fila, el)
    assert ordem[0] == idoso.id  # mais de 80 primeiro
    assert ordem.index(comum.id) <= 3  # após 2 preferenciais seguidos, a cota chama o comum
