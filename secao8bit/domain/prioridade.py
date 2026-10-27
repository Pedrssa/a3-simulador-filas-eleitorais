"""Classificação de preferência para votar.

Fonte: Resolução TSE nº 23.751/2026, art. 129, §§ 2º a 5º (consulta em 27/10/2026).

- § 2º lista os beneficiários (incisos I a XV).
- § 3º: a preferência segue a ordem de chegada, ressalvadas as pessoas com
  MAIS DE 80 anos, que têm precedência sobre as demais.
- § 4º: a preferência estende-se ao acompanhante dos titulares dos incisos VI a XV.
- § 5º: doadores de sangue votam após todos os demais beneficiados, mediante
  comprovante com validade de 120 dias.

A norma não cria precedência entre os incisos I a XIV; por isso todos caem na
mesma classe e o desempate é a chegada. Condições simultâneas não somam pontos:
vale a classe mais favorável, e todas as condições ficam registradas no fundamento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum, IntEnum

VALIDADE_COMPROVANTE_DOACAO_DIAS = 120
IDADE_PREFERENCIA = 60  # "igual ou superior a 60 anos" (inciso VI)
IDADE_PRECEDENCIA = 80  # "mais de 80 anos" (§ 3º) — comparação estrita


class Condicao(Enum):
    """Condições do art. 129, § 2º. O valor é o inciso correspondente."""

    CANDIDATO = "I"
    JUIZ_ELEITORAL = "II"
    SERVIDOR_JE = "III"
    PROMOTOR_ELEITORAL = "IV"
    SEGURANCA_EM_SERVICO = "V"
    # VI (idade) é derivado da data de nascimento, não declarado.
    DEFICIENCIA = "VII"
    MOBILIDADE_REDUZIDA = "VIII"
    ENFERMIDADE = "IX"
    TEA = "X"
    OBESIDADE = "XI"
    GESTANTE = "XII"
    LACTANTE = "XIII"
    CRIANCA_DE_COLO = "XIV"
    DOADOR_SANGUE = "XV"

    @property
    def rotulo(self) -> str:
        return _ROTULOS[self]


_ROTULOS = {
    Condicao.CANDIDATO: "candidata/candidato",
    Condicao.JUIZ_ELEITORAL: "juíza/juiz eleitoral ou auxiliar",
    Condicao.SERVIDOR_JE: "servidora/servidor da Justiça Eleitoral",
    Condicao.PROMOTOR_ELEITORAL: "promotora/promotor eleitoral ou auxiliar",
    Condicao.SEGURANCA_EM_SERVICO: "agente de segurança em serviço",
    Condicao.DEFICIENCIA: "pessoa com deficiência",
    Condicao.MOBILIDADE_REDUZIDA: "pessoa com mobilidade reduzida",
    Condicao.ENFERMIDADE: "pessoa enferma",
    Condicao.TEA: "pessoa com TEA",
    Condicao.OBESIDADE: "pessoa obesa",
    Condicao.GESTANTE: "gestante",
    Condicao.LACTANTE: "lactante",
    Condicao.CRIANCA_DE_COLO: "pessoa com criança de colo",
    Condicao.DOADOR_SANGUE: "doadora/doador de sangue",
}

# Incisos cujo titular estende a preferência ao acompanhante (§ 4º: VI a XV).
_INCISOS_COM_ACOMPANHANTE = {"VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"}


class ClassePrioridade(IntEnum):
    """Classes de atendimento. Menor valor = atendido antes."""

    MAIS_DE_80 = 0
    PREFERENCIAL = 1
    DOADOR = 2
    COMUM = 3

    @property
    def rotulo(self) -> str:
        return {
            ClassePrioridade.MAIS_DE_80: "Mais de 80 anos",
            ClassePrioridade.PREFERENCIAL: "Preferencial",
            ClassePrioridade.DOADOR: "Doador(a) de sangue",
            ClassePrioridade.COMUM: "Comum",
        }[self]

    @property
    def icone(self) -> str:
        """Ícone textual usado na cena e nas tabelas (não depende de cor)."""
        return {
            ClassePrioridade.MAIS_DE_80: "80+",
            ClassePrioridade.PREFERENCIAL: "P",
            ClassePrioridade.DOADOR: "D",
            ClassePrioridade.COMUM: "",
        }[self]


def idade_em_anos(nascimento: date, referencia: date) -> int:
    """Anos completos na data de referência."""
    anos = referencia.year - nascimento.year
    if (referencia.month, referencia.day) < (nascimento.month, nascimento.day):
        anos -= 1
    return anos


def _aniversario(nascimento: date, anos: int) -> date:
    try:
        return nascimento.replace(year=nascimento.year + anos)
    except ValueError:  # 29/02 em ano não bissexto: considera 01/03
        return date(nascimento.year + anos, 3, 1)


def tem_mais_de(nascimento: date, referencia: date, anos: int) -> bool:
    """Leitura literal de "mais de N anos": já passou do dia em que completou N.

    No próprio aniversário a pessoa tem exatamente N anos, portanto ainda não
    tem "mais de" N. A alternativa (exigir N+1 anos completos) está registrada
    em docs/regras_eleitorais.md como ponto de discussão.
    """
    return referencia > _aniversario(nascimento, anos)


def tem_ao_menos(nascimento: date, referencia: date, anos: int) -> bool:
    """Leitura de "igual ou superior a N anos"."""
    return referencia >= _aniversario(nascimento, anos)


@dataclass(frozen=True)
class ComprovanteDoacao:
    data_doacao: date

    def valido_em(self, referencia: date) -> bool:
        dias = (referencia - self.data_doacao).days
        return 0 <= dias <= VALIDADE_COMPROVANTE_DOACAO_DIAS


@dataclass(frozen=True)
class Classificacao:
    classe: ClassePrioridade
    fundamentos: tuple[str, ...]
    estende_a_acompanhante: bool

    @property
    def texto(self) -> str:
        if not self.fundamentos:
            return "Sem preferência: ordem de chegada"
        return "; ".join(self.fundamentos)


@dataclass(frozen=True)
class PerfilPrioridade:
    """Composição de condições de uma pessoa (sem subclasses por condição)."""

    nascimento: date
    condicoes: frozenset[Condicao] = field(default_factory=frozenset)
    comprovante_doacao: ComprovanteDoacao | None = None

    def classificar(self, data_eleicao: date) -> Classificacao:
        fundamentos: list[str] = []
        classes: list[ClassePrioridade] = []
        incisos: set[str] = set()
        idade = idade_em_anos(self.nascimento, data_eleicao)

        if tem_mais_de(self.nascimento, data_eleicao, IDADE_PRECEDENCIA):
            classes.append(ClassePrioridade.MAIS_DE_80)
            incisos.add("VI")
            fundamentos.append(f"mais de 80 anos ({idade} anos) — art. 129, § 3º")
        elif tem_ao_menos(self.nascimento, data_eleicao, IDADE_PREFERENCIA):
            classes.append(ClassePrioridade.PREFERENCIAL)
            incisos.add("VI")
            fundamentos.append(f"60 anos ou mais ({idade} anos) — art. 129, § 2º, VI")

        for c in sorted(self.condicoes, key=lambda c: c.name):
            if c is Condicao.DOADOR_SANGUE:
                if self.comprovante_doacao and self.comprovante_doacao.valido_em(data_eleicao):
                    classes.append(ClassePrioridade.DOADOR)
                    incisos.add("XV")
                    fundamentos.append("doador(a) com comprovante válido (≤120 dias) — art. 129, § 5º")
                else:
                    fundamentos.append("doador(a) sem comprovante válido: preferência não aplicada — art. 129, § 5º")
                continue
            classes.append(ClassePrioridade.PREFERENCIAL)
            incisos.add(c.value)
            fundamentos.append(f"{c.rotulo} — art. 129, § 2º, {c.value}")

        classe = min(classes) if classes else ClassePrioridade.COMUM
        return Classificacao(
            classe=classe,
            fundamentos=tuple(fundamentos),
            estende_a_acompanhante=bool(incisos & _INCISOS_COM_ACOMPANHANTE),
        )
