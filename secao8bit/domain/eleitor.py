"""Eleitor fictício e sua máquina de estados."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from secao8bit.domain.prioridade import Classificacao, ClassePrioridade, PerfilPrioridade


class EstadoEleitor(Enum):
    CHEGANDO = "chegando"
    AGUARDANDO = "aguardando na fila"
    IDENTIFICACAO = "identificação"
    AGUARDANDO_URNA = "identificado, aguardando urna"
    HABILITACAO = "habilitação"
    VOTANDO = "votando"
    AGUARDANDO_COMPROVANTE = "aguardando comprovante"
    COMPROVANTE = "recebendo comprovante"
    CONCLUIDO = "concluído"
    ENCAMINHADO = "encaminhado (não votou aqui)"
    NAO_ADMITIDO = "não admitido (após encerramento)"


TRANSICOES_VALIDAS: dict[EstadoEleitor, set[EstadoEleitor]] = {
    EstadoEleitor.CHEGANDO: {EstadoEleitor.AGUARDANDO, EstadoEleitor.NAO_ADMITIDO},
    EstadoEleitor.AGUARDANDO: {EstadoEleitor.IDENTIFICACAO, EstadoEleitor.ENCAMINHADO},
    EstadoEleitor.IDENTIFICACAO: {EstadoEleitor.AGUARDANDO_URNA, EstadoEleitor.ENCAMINHADO},
    EstadoEleitor.AGUARDANDO_URNA: {EstadoEleitor.HABILITACAO},
    EstadoEleitor.HABILITACAO: {EstadoEleitor.VOTANDO, EstadoEleitor.ENCAMINHADO},
    EstadoEleitor.VOTANDO: {EstadoEleitor.AGUARDANDO_COMPROVANTE},
    EstadoEleitor.AGUARDANDO_COMPROVANTE: {EstadoEleitor.COMPROVANTE},
    EstadoEleitor.COMPROVANTE: {EstadoEleitor.CONCLUIDO},
    EstadoEleitor.CONCLUIDO: set(),
    EstadoEleitor.ENCAMINHADO: set(),
    EstadoEleitor.NAO_ADMITIDO: set(),
}

ESTADOS_FINAIS = {EstadoEleitor.CONCLUIDO, EstadoEleitor.ENCAMINHADO, EstadoEleitor.NAO_ADMITIDO}


class TransicaoInvalida(RuntimeError):
    pass


@dataclass(frozen=True)
class Ocorrencias:
    """Atributos sorteados na geração da carga (sempre fictícios)."""

    secao_errada: bool = False
    problema_documento: bool = False
    falha_biometria: bool = False
    biometria_irrecuperavel: bool = False
    precisa_auxilio: bool = False
    votacao_demorada: bool = False
    celular: bool = False  # chega à cabine com celular e precisa ser orientado (art. 137)
    celular_recusa: bool = False  # recusa-se a entregar o aparelho (art. 137, § 5º)
    celular_policia: bool = False  # a Presidência entende necessário acionar a força policial
    impugnacao: bool = False  # fiscal impugna a identidade (art. 132, § 2º)
    impugnacao_persiste: bool = False  # dúvida persiste: Juízo é acionado (art. 132, § 3º)


@dataclass
class Eleitor:
    id: str
    apelido: str
    perfil: PerfilPrioridade
    classificacao: Classificacao
    chegada: float  # minutos simulados desde a abertura do cenário
    seq_chegada: int  # desempate estável quando chegadas coincidem
    duracoes: dict[str, float]
    ocorrencias: Ocorrencias = field(default_factory=Ocorrencias)
    acompanha: str | None = None  # id do titular, se for acompanhante que também vota aqui
    acompanhante_visual: bool = False  # acompanhante que não vota nesta seção (só aparece na cena)
    origem: str = "carga"  # carga | manual | grupo
    estado: EstadoEleitor = EstadoEleitor.CHEGANDO
    inicio_atendimento: float | None = None
    fim_votacao: float | None = None
    saida: float | None = None
    senha: int | None = None
    motivo_saida: str = ""
    ultrapassado_por: int = 0  # quantos que chegaram depois foram chamados antes
    historico: list[tuple[float, str, str]] = field(default_factory=list)

    @property
    def classe(self) -> ClassePrioridade:
        return self.classificacao.classe

    def transicionar(self, novo: EstadoEleitor, agora: float) -> EstadoEleitor:
        anterior = self.estado
        if novo not in TRANSICOES_VALIDAS[anterior]:
            raise TransicaoInvalida(f"{self.id}: {anterior.value} -> {novo.value} não é permitido")
        self.estado = novo
        self.historico.append((agora, anterior.value, novo.value))
        return anterior

    def espera(self, agora: float) -> float:
        """Espera até o início do atendimento (ou até agora, se ainda aguarda)."""
        fim = self.inicio_atendimento if self.inicio_atendimento is not None else agora
        return max(0.0, fim - self.chegada)

    @property
    def finalizado(self) -> bool:
        return self.estado in ESTADOS_FINAIS
