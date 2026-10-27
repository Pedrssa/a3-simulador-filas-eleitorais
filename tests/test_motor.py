"""Motor de eventos: reprodutibilidade, exclusividade da urna, não preempção, métricas."""

from dataclasses import replace

import pytest

from secao8bit.application.carga import Carga, GeradorCarga
from secao8bit.application.comparacao import comparar
from secao8bit.application.config import CENARIOS, config_do_cenario
from secao8bit.application.metricas import servico_para
from secao8bit.application.motor import TIPOS_INCIDENTE, MotorSimulacao
from secao8bit.domain.eleitor import EstadoEleitor
from secao8bit.domain.prioridade import ClassePrioridade


def assinatura_log(motor):
    return [(r.seq, round(r.instante, 6), r.eleitor_id, r.tipo, r.estado_anterior, r.estado_posterior,
             r.justificativa) for r in motor.log]


@pytest.mark.parametrize("cenario", list(CENARIOS))
def test_mesma_seed_mesmo_resultado(cenario):
    a = MotorSimulacao(config_do_cenario(cenario))
    b = MotorSimulacao(config_do_cenario(cenario))
    a.executar_tudo()
    b.executar_tudo()
    assert assinatura_log(a) == assinatura_log(b)


def test_seed_diferente_muda_a_carga():
    a = GeradorCarga(config_do_cenario("normal", seed=1)).gerar()
    b = GeradorCarga(config_do_cenario("normal", seed=2)).gerar()
    assert [c.instante for c in a.chegadas] != [c.instante for c in b.chegadas]


@pytest.mark.parametrize("passo", [0.1, 0.7, 3.0, 25.0])
def test_velocidade_da_animacao_nao_altera_resultado(passo):
    """Avançar em fatias de tamanhos diferentes (velocidades) produz o mesmo log."""
    cfg = config_do_cenario("demo_7min")
    referencia = MotorSimulacao(cfg)
    referencia.executar_tudo()
    m = MotorSimulacao(cfg)
    t = 0.0
    while not m.concluida:
        t += passo
        m.avancar_ate(t)
    assert assinatura_log(m) == assinatura_log(referencia)


@pytest.mark.parametrize("cenario", list(CENARIOS))
@pytest.mark.parametrize("politica", ["eleitoral", "aging", "cotas"])
def test_invariantes_e_ninguem_duplicado(cenario, politica):
    m = MotorSimulacao(config_do_cenario(cenario, politica=politica))
    votando_simultaneo = 0
    while not m.concluida:
        m.passo()  # verificar_invariantes() roda dentro de cada passo
        votando_simultaneo = max(votando_simultaneo, len(m.secao.em_estado(EstadoEleitor.HABILITACAO, EstadoEleitor.VOTANDO)))
    assert votando_simultaneo == 1
    ids = [e.id for e in m.secao.eleitores.values()]
    assert len(ids) == len(set(ids))
    assert all(e.finalizado for e in m.secao.eleitores.values())
    entradas = [r.eleitor_id for r in m.log if r.tipo == "ENTRADA_FILA"]
    saidas = [r.eleitor_id for r in m.log if r.tipo == "SAIDA_FILA"]
    assert sorted(entradas) == sorted(saidas) and len(saidas) == len(set(saidas))
    concluidos = sum(1 for e in m.secao.eleitores.values() if e.estado == EstadoEleitor.CONCLUIDO)
    assert m.secao.urna.votos_registrados == concluidos


def _carga_manual(cfg, especs):
    g = GeradorCarga(cfg)
    chegadas = []
    for instante, tipo in especs:
        spec = g.especificar(instante, tipo is not None, tipo=tipo)
        spec = replace(spec, ocorrencias=replace(spec.ocorrencias, secao_errada=False, problema_documento=False,
                                                 falha_biometria=False, biometria_irrecuperavel=False,
                                                 votacao_demorada=False, precisa_auxilio=False),
                       acompanhante=None, duracoes_acompanhante=None,
                       duracoes={**spec.duracoes, "identificacao": 1.0, "habilitacao": 0.5, "votacao": 5.0,
                                 "comprovante": 0.3})
        chegadas.append(spec)
    return Carga(tuple(chegadas), ())


def test_nao_preempcao_atendimento_iniciado_nao_e_interrompido():
    cfg = config_do_cenario("normal")
    carga = _carga_manual(cfg, [(0.0, None), (0.5, "mais_de_80")])
    m = MotorSimulacao(cfg, carga=carga)
    m.avancar_ate(0.6)
    comum, idoso = m.secao.eleitores["E-0001"], m.secao.eleitores["E-0002"]
    assert comum.estado == EstadoEleitor.IDENTIFICACAO  # já começou: segue
    assert idoso.estado == EstadoEleitor.AGUARDANDO  # espera mesmo sendo prioritário
    m.executar_tudo()
    assert comum.fim_votacao < idoso.fim_votacao


def test_prioridade_aplicada_na_admissao():
    cfg = config_do_cenario("normal")
    carga = _carga_manual(cfg, [(0.0, None), (0.1, None), (0.2, "gestante"), (0.3, "mais_de_80")])
    m = MotorSimulacao(cfg, carga=carga)
    m.executar_tudo()
    chamados = [r.eleitor_id for r in m.log if r.tipo == "SAIDA_FILA"]
    assert chamados == ["E-0001", "E-0004", "E-0003", "E-0002"]


def test_falha_de_urna_interrompe_e_restabelece_sem_voto_simultaneo():
    cfg = config_do_cenario("falha_urna")
    m = MotorSimulacao(cfg)
    viu_interrompida = False
    while not m.concluida:
        m.passo()
        if m.secao.urna.interrompido:
            viu_interrompida = True
            assert m.secao.urna.ocupante is None
    assert viu_interrompida and m.secao.urna.em_contingencia
    tipos = [r.tipo for r in m.log]
    assert "RECURSO_INTERROMPIDO" in tipos and "RECURSO_RESTABELECIDO" in tipos


def test_boca_de_urna_nao_interrompe_urna_nem_prende_automaticamente():
    cfg = config_do_cenario("boca_de_urna")
    m = MotorSimulacao(cfg)
    while not m.concluida:
        m.passo()
        if any(p.papel == "manifestante" for p in m.secao.apoio.values()):
            assert not m.secao.urna.interrompido
    textos = " ".join(r.justificativa for r in m.log).lower()
    assert "prisão" not in textos and "preso" not in textos
    assert "silenciosa" in textos and "permitida" in textos


def test_encerramento_distribui_senhas_e_recusa_quem_chega_depois():
    m = MotorSimulacao(config_do_cenario("encerramento"))
    m.executar_tudo()
    enc = next(r for r in m.log if r.tipo == "ENCERRAMENTO")
    senhas = dict(enc.dados["senhas"])
    chamados_depois = [r.eleitor_id for r in m.log if r.tipo == "SAIDA_FILA" and r.seq > enc.seq]
    assert [senhas[e] for e in chamados_depois] == sorted(senhas.values(), reverse=True)
    assert all(r.instante >= enc.instante for r in m.log if r.tipo == "CHEGADA_NAO_ADMITIDA")


@pytest.mark.parametrize("tipo", list(TIPOS_INCIDENTE))
def test_incidentes_manuais_nao_quebram_invariantes(tipo):
    m = MotorSimulacao(config_do_cenario("normal"))
    m.avancar_ate(20)
    m.disparar_incidente(tipo)
    m.executar_tudo()
    assert all(e.finalizado for e in m.secao.eleitores.values())


def test_pausa_e_avanco_unitario():
    m = MotorSimulacao(config_do_cenario("normal"))
    antes = m.estado.eventos_processados
    ev = m.passo()
    assert ev is not None and m.estado.eventos_processados == antes + 1
    t = m.agora
    # "pausado" = ninguém chama passo/avancar_ate: o estado não muda sozinho
    assert m.agora == t and m.estado.eventos_processados == antes + 1


def test_metricas_incluem_quem_ainda_espera():
    cfg = config_do_cenario("starvation")
    m = MotorSimulacao(cfg)
    m.avancar_ate(140)
    met = servico_para(cfg)
    eleitores = list(m.secao.eleitores.values())
    so_atendidos = met.esperas(eleitores, m.agora, incluir_em_espera=False)
    com_espera = met.esperas(eleitores, m.agora, incluir_em_espera=True)
    assert len(com_espera) > len(so_atendidos)
    em_espera = [m.agora - e.chegada for e in eleitores if e.estado == EstadoEleitor.AGUARDANDO]
    assert em_espera and sum(com_espera) > sum(so_atendidos)  # excluir quem espera esconde espera real
    assert met.alertas_starvation(eleitores, m.agora)


def test_comparacao_usa_a_mesma_carga_e_aging_reduz_espera_dos_comuns():
    resultados = comparar(config_do_cenario("starvation"))
    assert len({r.assinatura_carga for r in resultados}) == 1
    por_nome = {r.nome: {g["grupo"]: g for g in r.grupos} for r in resultados}
    estrita = por_nome["Regras eleitorais"]["Comum"]["máximo (incl.)"]
    aging = por_nome["LAB: aging (15 min)"]["Comum"]["máximo (incl.)"]
    assert aging < estrita * 0.6


def test_politica_eleitoral_sem_promocao_mesmo_com_starvation():
    m = MotorSimulacao(config_do_cenario("starvation"))
    m.executar_tudo()
    comuns_chamados = 0
    for r in (r for r in m.log if r.tipo == "SAIDA_FILA"):
        if m.secao.eleitores[r.eleitor_id].classe == ClassePrioridade.COMUM:
            comuns_chamados += 1
            # se um comum foi chamado, ninguém com preferência estava esperando
            assert all(m.secao.eleitores[x].classe == ClassePrioridade.COMUM for x in r.dados["ordem_fila"])
    assert comuns_chamados > 0
