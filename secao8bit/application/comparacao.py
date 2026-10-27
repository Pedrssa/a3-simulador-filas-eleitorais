"""Comparação de políticas com a MESMA carga (chegadas, perfis, durações, incidentes)."""

from __future__ import annotations

from dataclasses import dataclass

from secao8bit.application.carga import GeradorCarga
from secao8bit.application.config import ConfiguracaoSimulacao
from secao8bit.application.metricas import servico_para
from secao8bit.application.motor import MotorSimulacao

VARIANTES_PADRAO: tuple[tuple[str, str, dict, dict], ...] = (
    ("Regras eleitorais", "eleitoral", {}, {}),
    ("Regras eleitorais + mitigação operacional", "eleitoral", {},
     {"designar_substituto": True, "tecnico_de_prontidao": True}),
    ("LAB: aging (15 min)", "aging", {"intervalo_min": 15.0}, {}),
    ("LAB: cotas (k=3)", "cotas", {"k": 3}, {}),
)


@dataclass
class ResultadoComparacao:
    nome: str
    politica_versao: str
    resumo: dict
    grupos: list[dict]
    serie_fila: list[tuple[float, int]]
    assinatura_carga: tuple


def assinatura(carga) -> tuple:
    """Impressão digital da carga, para provar que as variantes receberam a mesma entrada."""
    return (len(carga.chegadas), round(sum(c.instante for c in carga.chegadas), 6),
            round(sum(c.duracoes["votacao"] for c in carga.chegadas), 6))


def comparar(config: ConfiguracaoSimulacao, variantes=VARIANTES_PADRAO) -> list[ResultadoComparacao]:
    resultados = []
    for nome, politica, params, mitigacao in variantes:
        cfg = config.com(politica=politica, politica_params=params, **mitigacao)
        carga = GeradorCarga(cfg).gerar()  # mesmos fluxos aleatórios: mesma chegada/perfil/duração
        motor = MotorSimulacao(cfg, carga=carga)
        motor.executar_tudo()
        metricas = servico_para(cfg)
        eleitores = list(motor.secao.eleitores.values())
        resultados.append(ResultadoComparacao(
            nome, motor.politica.versao, metricas.resumo(motor), metricas.por_grupo(eleitores, motor.agora),
            list(motor.estado.serie_fila), assinatura(carga),
        ))
    return resultados
