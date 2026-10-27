"""Geração prévia e reproduzível da carga (chegadas, perfis, durações e incidentes).

Cada aspecto usa um fluxo pseudoaleatório próprio derivado da seed, então:
- a mesma seed + configuração gera exatamente a mesma carga;
- políticas diferentes recebem a mesma carga na comparação (as durações
  pertencem à pessoa, não à ordem em que ela é atendida).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from secao8bit.application.config import ConfiguracaoSimulacao, IncidenteProgramado, Tri
from secao8bit.domain.eleitor import Ocorrencias
from secao8bit.domain.prioridade import ComprovanteDoacao, Condicao, PerfilPrioridade

APELIDOS = (
    "Aurora", "Bento", "Cecília", "Dante", "Elisa", "Fábio", "Gaia", "Heitor", "Iara", "Joaquim",
    "Kaíque", "Lia", "Martim", "Nara", "Otávio", "Pietra", "Quim", "Rosa", "Saulo", "Taís",
    "Ubiratã", "Vera", "Wagner", "Xênia", "Yuri", "Zuleica", "Caetano", "Jaci", "Moema", "Raoni",
)


def rng_de(seed: int, fluxo: str) -> random.Random:
    return random.Random(f"secao8bit:{seed}:{fluxo}")


def tri(rng: random.Random, p: Tri) -> float:
    lo, moda, hi = p
    return rng.triangular(lo, hi, moda)


@dataclass(frozen=True)
class EspecAcompanhante:
    vota_aqui: bool


@dataclass(frozen=True)
class EspecChegada:
    instante: float
    apelido: str
    perfil: PerfilPrioridade
    ocorrencias: Ocorrencias
    duracoes: dict
    origem: str = "carga"
    acompanhante: EspecAcompanhante | None = None
    duracoes_acompanhante: dict | None = None


@dataclass(frozen=True)
class Carga:
    chegadas: tuple[EspecChegada, ...]
    incidentes: tuple[IncidenteProgramado, ...] = field(default_factory=tuple)


def _nascimento_para_idade(rng: random.Random, ref: date, anos_min: int, anos_max: int) -> date:
    dias = rng.randint(anos_min * 365 + 1, anos_max * 365 + 300)
    return ref - timedelta(days=dias)


class GeradorCarga:
    def __init__(self, config: ConfiguracaoSimulacao) -> None:
        self.cfg = config
        self.r_cheg = rng_de(config.seed, "chegadas")
        self.r_perf = rng_de(config.seed, "perfis")
        self.r_dur = rng_de(config.seed, "duracoes")
        self.r_inc = rng_de(config.seed, "incidentes")

    # --- perfis ---------------------------------------------------------
    def perfil(self, prioritario: bool, rng: random.Random | None = None, tipo: str | None = None) -> PerfilPrioridade:
        r = rng or self.r_perf
        ref = self.cfg.data_eleicao
        if not prioritario:
            nasc = _nascimento_para_idade(r, ref, 18, 58)
            if r.random() < self.cfg.prob_comum_doador_vencido:
                vencida = ComprovanteDoacao(ref - timedelta(days=r.randint(121, 400)))
                return PerfilPrioridade(nasc, frozenset({Condicao.DOADOR_SANGUE}), vencida)
            return PerfilPrioridade(nasc)
        pesos = self.cfg.pesos_prioridade
        tipo = tipo or r.choices(list(pesos), weights=list(pesos.values()))[0]
        nasc = _nascimento_para_idade(r, ref, 20, 58)
        cond: set[Condicao] = set()
        comprovante = None
        if tipo == "mais_de_80":
            nasc = _nascimento_para_idade(r, ref, 81, 97)
        elif tipo == "idade_60":
            nasc = _nascimento_para_idade(r, ref, 60, 79)
        elif tipo == "doador":
            cond.add(Condicao.DOADOR_SANGUE)
            comprovante = ComprovanteDoacao(ref - timedelta(days=r.randint(1, 120)))
        else:
            cond.add({
                "deficiencia": Condicao.DEFICIENCIA, "mobilidade": Condicao.MOBILIDADE_REDUZIDA,
                "gestante": Condicao.GESTANTE, "lactante": Condicao.LACTANTE,
                "crianca_colo": Condicao.CRIANCA_DE_COLO, "tea": Condicao.TEA,
                "obesidade": Condicao.OBESIDADE, "enfermidade": Condicao.ENFERMIDADE,
                "seguranca": Condicao.SEGURANCA_EM_SERVICO,
            }[tipo])
        # Condições simultâneas acontecem (ex.: 70 anos e mobilidade reduzida).
        if tipo == "idade_60" and r.random() < 0.15:
            cond.add(Condicao.MOBILIDADE_REDUZIDA)
        return PerfilPrioridade(nasc, frozenset(cond), comprovante)

    def ocorrencias(self, perfil: PerfilPrioridade, rng: random.Random | None = None, forcar: str | None = None) -> Ocorrencias:
        r = rng or self.r_perf
        c = self.cfg
        falha_bio = r.random() < c.prob_falha_biometria
        aux_possivel = bool(perfil.condicoes & {Condicao.DEFICIENCIA, Condicao.MOBILIDADE_REDUZIDA})
        o = dict(
            secao_errada=r.random() < c.prob_secao_errada,
            problema_documento=r.random() < c.prob_problema_documento,
            falha_biometria=falha_bio,
            biometria_irrecuperavel=falha_bio and r.random() < c.prob_biometria_irrecuperavel,
            precisa_auxilio=aux_possivel and r.random() < c.prob_auxilio,
            votacao_demorada=r.random() < c.prob_votacao_demorada,
        )
        cel = r.random() < c.prob_celular
        recusa = cel and r.random() < c.prob_celular_recusa
        imp = r.random() < c.prob_impugnacao
        o.update(celular=cel, celular_recusa=recusa, celular_policia=recusa and r.random() < c.prob_celular_policia,
                 impugnacao=imp, impugnacao_persiste=imp and r.random() < c.prob_impugnacao_persiste)
        if forcar:
            o[forcar] = True
            if forcar == "biometria_irrecuperavel":
                o["falha_biometria"] = True
            if forcar == "celular_recusa":
                o.update(celular=True, celular_policia=True)
        return Ocorrencias(**o)

    def duracoes(self, rng: random.Random | None = None) -> dict:
        r = rng or self.r_dur
        c = self.cfg
        return {
            "identificacao": tri(r, c.dur_identificacao),
            "habilitacao": tri(r, c.dur_habilitacao),
            "biometria_extra": tri(r, c.dur_biometria_extra),
            "votacao": tri(r, c.dur_votacao),
            "auxilio_extra": tri(r, c.dur_auxilio_extra),
            "comprovante": tri(r, c.dur_comprovante),
            "orientacao_celular": tri(r, c.dur_orientacao_celular),
            "impugnacao": tri(r, c.dur_impugnacao),
            "impugnacao_juizo": tri(r, c.dur_impugnacao_juizo),
        }

    def especificar(self, instante: float, prioritario: bool, origem: str = "carga",
                    rng: random.Random | None = None, tipo: str | None = None,
                    forcar: str | None = None) -> EspecChegada:
        r = rng or self.r_perf
        perfil = self.perfil(prioritario, r, tipo)
        ocorr = self.ocorrencias(perfil, r, forcar)
        acomp = None
        dur_acomp = None
        if prioritario and r.random() < 0.3:
            acomp = EspecAcompanhante(vota_aqui=r.random() < self.cfg.prob_acompanhante_vota)
        if ocorr.precisa_auxilio and acomp is None:
            acomp = EspecAcompanhante(vota_aqui=False)
        dur = self.duracoes(rng)
        if acomp and acomp.vota_aqui:
            dur_acomp = self.duracoes(rng)
        return EspecChegada(instante, r.choice(APELIDOS), perfil, ocorr, dur, origem, acomp, dur_acomp)

    # --- chegadas ---------------------------------------------------------
    def _multiplicador(self, t: float) -> float:
        m = 1.0
        for ini, fim, mult in self.cfg.ondas:
            if ini <= t < fim:
                m *= mult
        return m

    def _poisson(self, taxa_h: float) -> list[float]:
        """Processo de Poisson não homogêneo por afinamento (thinning)."""
        if taxa_h <= 0:
            return []
        mult_max = max([1.0] + [m for _, _, m in self.cfg.ondas])
        lam = taxa_h / 60.0 * mult_max
        t, tempos = 0.0, []
        while True:
            t += self.r_cheg.expovariate(lam)
            if t >= self.cfg.duracao_chegadas_min:
                return tempos
            if self.r_cheg.random() < self._multiplicador(t) / mult_max:
                tempos.append(t)

    def _incidentes_aleatorios(self) -> list[IncidenteProgramado]:
        c = self.cfg
        out: list[IncidenteProgramado] = []
        for tipo, taxa in (("falha_urna", c.taxa_falha_urna_h), ("discussao", c.taxa_discussao_h),
                           ("boca_de_urna", c.taxa_boca_de_urna_h), ("grupo", c.taxa_grupo_h)):
            if taxa <= 0:
                continue
            t = 0.0
            while True:
                t += self.r_inc.expovariate(taxa / 60.0)
                if t >= c.duracao_chegadas_min:
                    break
                out.append(IncidenteProgramado(round(t, 3), tipo, {}))
        return out

    def resolver_incidente(self, inc: IncidenteProgramado, rng: random.Random) -> IncidenteProgramado:
        """Sorteia de antemão os desfechos, para que a carga seja idêntica entre políticas."""
        c = self.cfg
        p = dict(inc.params)
        if inc.tipo == "falha_urna":
            p.setdefault("persiste", rng.random() < c.prob_falha_persiste)
            p.setdefault("religar", tri(rng, c.dur_religar_urna))
            chegada = (3.0, 4.0, 6.0) if c.tecnico_de_prontidao else c.dur_chegada_tecnico
            p.setdefault("chegada_tecnico", tri(rng, chegada))
            p.setdefault("reparo", tri(rng, c.dur_reparo_urna))
        elif inc.tipo == "discussao":
            p.setdefault("escala", rng.random() < c.prob_discussao_escala)
            p.setdefault("policia", p["escala"] and rng.random() < c.prob_discussao_policia)
            p.setdefault("dur_presidente", tri(rng, c.dur_discussao_presidente))
            p.setdefault("chegada_policia", tri(rng, c.dur_chegada_policia))
            p.setdefault("posicao_relativa", rng.random())
        elif inc.tipo == "boca_de_urna":
            p.setdefault("tentativa", rng.random() < c.prob_boca_tentativa)
            p.setdefault("chegada_policia", tri(rng, c.dur_chegada_policia))
            p.setdefault("avaliacao", tri(rng, c.dur_avaliacao_boca))
            p.setdefault("encaminhar", rng.random() < 0.3)
            p.setdefault("permanencia", rng.uniform(8.0, 15.0))
        elif inc.tipo == "grupo":
            p.setdefault("n", rng.randint(3, 6))
            p.setdefault("prioritarios", rng.randint(1, p["n"]))
        return IncidenteProgramado(inc.instante, inc.tipo, p)

    def gerar(self) -> Carga:
        c = self.cfg
        marcados = [(t, True) for t in self._poisson(c.taxa_prioritarios_h)]
        marcados += [(t, False) for t in self._poisson(c.taxa_comuns_h)]
        marcados.sort()
        chegadas = [self.especificar(t, prio) for t, prio in marcados]
        brutos = sorted(list(c.incidentes) + self._incidentes_aleatorios(), key=lambda i: (i.instante, i.tipo))
        incidentes = [self.resolver_incidente(i, self.r_inc) for i in brutos]
        for inc in incidentes:
            if inc.tipo == "grupo":  # o grupo chega junto, em fila indiana
                chegadas += [
                    self.especificar(inc.instante + 0.05 * k, k < inc.params["prioritarios"], "grupo")
                    for k in range(inc.params["n"])
                ]
        chegadas.sort(key=lambda e: e.instante)
        if c.encerramento_min is not None:
            incidentes.append(IncidenteProgramado(c.encerramento_min, "encerramento", {}))
        return Carga(tuple(chegadas), tuple(incidentes))
