"""Configuração da simulação e cenários reproduzíveis.

Todos os tempos estão em minutos simulados. Taxas estão em pessoas por hora.
Valores de duração, taxas e metas de SLA são HIPÓTESES ACADÊMICAS, não dados oficiais.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date

Tri = tuple[float, float, float]  # (mínimo, moda, máximo) de distribuição triangular


@dataclass(frozen=True)
class IncidenteProgramado:
    instante: float
    tipo: str  # falha_urna | discussao | boca_de_urna | grupo
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConfiguracaoSimulacao:
    seed: int = 2026
    cenario: str = "normal"
    data_eleicao: date = date(2026, 10, 4)
    hora_inicio_min: int = 8 * 60
    duracao_chegadas_min: float = 120.0
    encerramento_min: float | None = None  # instante simulado do fim do recebimento (17h)

    # Chegadas: dois fluxos de Poisson independentes.
    taxa_comuns_h: float = 13.0
    taxa_prioritarios_h: float = 6.0
    ondas: tuple[tuple[float, float, float], ...] = ()  # (início, fim, multiplicador)
    pesos_prioridade: dict = field(default_factory=lambda: {
        "mais_de_80": 0.12, "idade_60": 0.38, "deficiencia": 0.08, "mobilidade": 0.07,
        "gestante": 0.06, "lactante": 0.03, "crianca_colo": 0.08, "tea": 0.03,
        "obesidade": 0.03, "enfermidade": 0.03, "seguranca": 0.02, "doador": 0.07,
    })
    prob_comum_doador_vencido: float = 0.02
    prob_acompanhante_vota: float = 0.25

    # Ocorrências individuais (sorteadas por pessoa na carga).
    prob_secao_errada: float = 0.03
    prob_problema_documento: float = 0.025
    prob_falha_biometria: float = 0.10
    prob_biometria_irrecuperavel: float = 0.1  # condicional a falha
    prob_auxilio: float = 0.5  # condicional a deficiência/mobilidade reduzida
    prob_votacao_demorada: float = 0.07
    prob_celular: float = 0.06
    prob_celular_recusa: float = 0.35  # condicional
    prob_celular_policia: float = 0.6  # condicional à recusa
    prob_impugnacao: float = 0.025
    prob_impugnacao_persiste: float = 0.3  # condicional

    # Incidentes aleatórios (processo de Poisson, por hora) + programados.
    taxa_falha_urna_h: float = 0.25
    taxa_discussao_h: float = 0.8
    taxa_boca_de_urna_h: float = 0.8
    taxa_grupo_h: float = 1.0
    incidentes: tuple[IncidenteProgramado, ...] = ()

    # Durações (minutos, triangulares).
    dur_identificacao: Tri = (0.5, 0.8, 1.8)
    dur_habilitacao: Tri = (0.3, 0.5, 1.0)
    dur_biometria_extra: Tri = (0.8, 1.5, 3.0)
    dur_votacao: Tri = (0.8, 1.2, 2.5)
    dur_auxilio_extra: Tri = (0.5, 1.0, 2.0)
    dur_comprovante: Tri = (0.2, 0.3, 0.6)
    dur_orientacao_celular: Tri = (0.5, 0.8, 1.5)
    dur_impugnacao: Tri = (2.0, 3.0, 5.0)
    dur_impugnacao_juizo: Tri = (6.0, 9.0, 14.0)
    dur_religar_urna: Tri = (1.0, 1.5, 2.5)
    prob_falha_persiste: float = 0.7
    dur_chegada_tecnico: Tri = (10.0, 15.0, 25.0)
    dur_reparo_urna: Tri = (4.0, 6.0, 10.0)
    dur_discussao_presidente: Tri = (2.0, 3.5, 6.0)
    prob_discussao_escala: float = 0.6
    prob_discussao_policia: float = 0.4
    dur_chegada_policia: Tri = (5.0, 8.0, 15.0)
    dur_avaliacao_boca: Tri = (3.0, 5.0, 8.0)
    prob_boca_tentativa: float = 0.6

    # Mitigação operacional (modo eleitoral).
    designar_substituto: bool = False  # Presidente designa mesário para identificar (art. 126, caput)
    tecnico_de_prontidao: bool = False  # técnico mais próximo: chegada em 3–6 min

    # Metas acadêmicas (hipóteses, não garantias legais).
    sla_prioritarios_min: float = 15.0
    sla_comuns_min: float = 30.0
    limiar_starvation_min: float = 45.0

    politica: str = "eleitoral"
    politica_params: dict = field(default_factory=dict)

    def com(self, **mudancas) -> "ConfiguracaoSimulacao":
        return replace(self, **mudancas)

    def como_dict(self) -> dict:
        d = asdict(self)
        d["data_eleicao"] = self.data_eleicao.isoformat()
        return d


CENARIOS: dict[str, tuple[str, ConfiguracaoSimulacao]] = {
    "normal": (
        "Funcionamento normal com eventos aleatórios moderados.",
        ConfiguracaoSimulacao(cenario="normal"),
    ),
    "demo_7min": (
        "Roteiro da apresentação: boca de urna com polícia, grupo de prioridades, discussão, falha de urna e eventos aleatórios.",
        ConfiguracaoSimulacao(
            cenario="demo_7min", duracao_chegadas_min=90.0,
            incidentes=(
                IncidenteProgramado(4.0, "boca_de_urna", {"tentativa": True}),
                IncidenteProgramado(12.0, "grupo", {"n": 5, "prioritarios": 4}),
                IncidenteProgramado(24.0, "discussao", {"escala": True, "policia": True}),
                IncidenteProgramado(40.0, "falha_urna", {"persiste": True}),
            ),
        ),
    ),
    "starvation": (
        "Fluxo preferencial acima da capacidade da urna, sem incidentes (para comparar políticas).",
        ConfiguracaoSimulacao(
            cenario="starvation", seed=7, duracao_chegadas_min=150.0,
            taxa_comuns_h=8.0, taxa_prioritarios_h=30.0,
            prob_secao_errada=0.0, prob_problema_documento=0.0, prob_votacao_demorada=0.0,
            prob_celular=0.0, prob_impugnacao=0.0,
            taxa_falha_urna_h=0.0, taxa_discussao_h=0.0, taxa_boca_de_urna_h=0.0, taxa_grupo_h=0.0,
        ),
    ),
    "falha_urna": (
        "Urna falha às 08:25; religar não resolve; técnico substitui por urna de contingência.",
        ConfiguracaoSimulacao(
            cenario="falha_urna", taxa_comuns_h=16.0,
            incidentes=(IncidenteProgramado(25.0, "falha_urna", {"persiste": True}),),
        ),
    ),
    "boca_de_urna": (
        "Ocorrências na área externa: manifestação silenciosa (permitida) e tentativa de influenciar.",
        ConfiguracaoSimulacao(
            cenario="boca_de_urna",
            incidentes=(
                IncidenteProgramado(10.0, "boca_de_urna", {"tentativa": False}),
                IncidenteProgramado(35.0, "boca_de_urna", {"tentativa": True}),
            ),
        ),
    ),
    "encerramento": (
        "Fim do dia: fila cheia às 16:30, recebimento encerrado às 17:00 com distribuição de senhas.",
        ConfiguracaoSimulacao(
            cenario="encerramento", hora_inicio_min=16 * 60 + 30, duracao_chegadas_min=45.0,
            encerramento_min=30.0, taxa_comuns_h=30.0, taxa_prioritarios_h=8.0,
        ),
    ),
    "aleatorio": (
        "Dia agitado: muitos eventos aleatórios (falhas, discussões, boca de urna, celular, impugnações).",
        ConfiguracaoSimulacao(
            cenario="aleatorio", duracao_chegadas_min=180.0, taxa_comuns_h=16.0,
            taxa_falha_urna_h=0.5, taxa_discussao_h=1.5, taxa_boca_de_urna_h=1.2, taxa_grupo_h=1.5,
            prob_celular=0.10, prob_impugnacao=0.05,
        ),
    ),
}


def config_do_cenario(nome: str, **mudancas) -> ConfiguracaoSimulacao:
    return CENARIOS[nome][1].com(**mudancas) if mudancas else CENARIOS[nome][1]
