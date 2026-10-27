"""Regras do art. 129 da Res. TSE 23.751/2026 — limites lidos literalmente."""

from datetime import date, timedelta

import pytest

from secao8bit.domain.prioridade import (
    ClassePrioridade, ComprovanteDoacao, Condicao, PerfilPrioridade, tem_mais_de,
)

ELEICAO = date(2026, 10, 4)


def classe(nascimento, condicoes=(), doacao=None):
    comp = ComprovanteDoacao(doacao) if doacao else None
    return PerfilPrioridade(nascimento, frozenset(condicoes), comp).classificar(ELEICAO).classe


class TestLimitesEtarios:
    def test_exatamente_80_anos_nao_tem_mais_de_80(self):
        # Completa 80 anos no próprio dia da eleição: tem 80, não "mais de 80".
        assert classe(date(1946, 10, 4)) == ClassePrioridade.PREFERENCIAL

    def test_80_anos_e_um_dia_tem_mais_de_80(self):
        assert classe(date(1946, 10, 3)) == ClassePrioridade.MAIS_DE_80

    def test_vespera_dos_80_anos_e_preferencial_por_idade(self):
        assert classe(date(1946, 10, 5)) == ClassePrioridade.PREFERENCIAL

    def test_exatamente_60_anos_tem_preferencia(self):
        # "igual ou superior a 60" inclui o dia do aniversário.
        assert classe(date(1966, 10, 4)) == ClassePrioridade.PREFERENCIAL

    def test_um_dia_antes_dos_60_nao_tem_preferencia(self):
        assert classe(date(1966, 10, 5)) == ClassePrioridade.COMUM

    def test_nascido_em_29_de_fevereiro(self):
        # 2025 não é bissexto: o 81º aniversário é considerado em 01/03.
        assert tem_mais_de(date(1944, 2, 29), date(2025, 3, 1), 81) is False
        assert tem_mais_de(date(1944, 2, 29), date(2025, 3, 2), 81) is True


class TestDoadores:
    def test_comprovante_com_120_dias_e_valido(self):
        assert classe(date(1990, 1, 1), {Condicao.DOADOR_SANGUE}, ELEICAO - timedelta(days=120)) == ClassePrioridade.DOADOR

    def test_comprovante_com_121_dias_nao_vale(self):
        assert classe(date(1990, 1, 1), {Condicao.DOADOR_SANGUE}, ELEICAO - timedelta(days=121)) == ClassePrioridade.COMUM

    def test_doador_sem_comprovante_nao_tem_preferencia(self):
        assert classe(date(1990, 1, 1), {Condicao.DOADOR_SANGUE}) == ClassePrioridade.COMUM

    def test_doador_vem_depois_dos_demais_beneficiarios(self):
        assert ClassePrioridade.DOADOR > ClassePrioridade.PREFERENCIAL


class TestMultiplasCondicoes:
    def test_vale_a_classe_mais_favoravel_sem_somar_pontos(self):
        perfil = PerfilPrioridade(date(1990, 1, 1), frozenset({Condicao.GESTANTE, Condicao.DOADOR_SANGUE}),
                                  ComprovanteDoacao(ELEICAO - timedelta(days=10)))
        c = perfil.classificar(ELEICAO)
        assert c.classe == ClassePrioridade.PREFERENCIAL
        assert len(c.fundamentos) == 2  # ambas registradas no fundamento

    def test_mais_de_80_com_deficiencia_continua_mais_de_80(self):
        assert classe(date(1940, 1, 1), {Condicao.DEFICIENCIA}) == ClassePrioridade.MAIS_DE_80

    @pytest.mark.parametrize("cond", [c for c in Condicao if c is not Condicao.DOADOR_SANGUE])
    def test_incisos_i_a_xiv_tem_mesma_classe(self, cond):
        # A norma não cria precedência entre esses grupos.
        assert classe(date(1990, 1, 1), {cond}) == ClassePrioridade.PREFERENCIAL

    def test_extensao_ao_acompanhante_so_para_incisos_vi_a_xv(self):
        candidato = PerfilPrioridade(date(1990, 1, 1), frozenset({Condicao.CANDIDATO})).classificar(ELEICAO)
        gestante = PerfilPrioridade(date(1990, 1, 1), frozenset({Condicao.GESTANTE})).classificar(ELEICAO)
        assert not candidato.estende_a_acompanhante
        assert gestante.estende_a_acompanhante


def test_mesa_tem_quatro_integrantes_e_uma_urna():
    """Res. 23.751/2026, art. 9º: Presidente, 1º e 2º mesários e secretário; apoio não integra a mesa."""
    from secao8bit.domain.recursos import Cargo
    from secao8bit.domain.secao import SecaoEleitoral

    s = SecaoEleitoral()
    assert set(s.mesa) == set(Cargo) and len(s.mesa) == 4
    assert all(p.papel != "mesa" for p in s.apoio.values())
    assert s.urna.nome == "Urna"  # um único recurso de votação
