"""Sessão de simulação compartilhada por todas as abas.

O motor vive em st.session_state: reruns e trocas de aba reutilizam o mesmo
objeto, então nada é reiniciado nem processado duas vezes. O tempo simulado só
avança por ação explícita (avançar um evento) ou pelo relógio da interface
enquanto "rodando", proporcional ao tempo real decorrido.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from secao8bit.application.auditoria import ErroPersistencia
from secao8bit.application.config import ConfiguracaoSimulacao, config_do_cenario
from secao8bit.application.motor import MotorSimulacao
from secao8bit.infrastructure.repositorio_sqlite import RepositorioAuditoria

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "dados" / "auditoria.sqlite3"
TICK_S = 0.5
# minutos simulados por segundo real (exibidos como múltiplos do tempo real: 0,05 = 3×, 1 = 60×)
VELOCIDADES = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0]
MAX_ATRASO_S = 1.5  # se o navegador ficar parado, não "pula" mais que isso de tempo real


@dataclass
class SessaoSimulacao:
    config: ConfiguracaoSimulacao
    repo: RepositorioAuditoria
    motor: MotorSimulacao
    rodando: bool = False
    velocidade: float = 0.25  # minutos simulados por segundo real (15× o tempo real)
    ultimo_tick: float | None = None
    selecionado: str | None = None
    erro: str | None = None
    comparacao: dict = field(default_factory=dict)
    resultados: dict = field(default_factory=dict)  # resultados de botões, persistem entre ticks

    @classmethod
    def nova(cls, config: ConfiguracaoSimulacao, caminho_banco: Path | str | None = None) -> "SessaoSimulacao":
        repo = RepositorioAuditoria(BANCO if caminho_banco is None else caminho_banco)
        return cls(config=config, repo=repo, motor=MotorSimulacao(config, repo))

    def reiniciar(self, config: ConfiguracaoSimulacao | None = None) -> None:
        self.config = config or self.config
        self.motor = MotorSimulacao(self.config, self.repo)
        self.rodando, self.ultimo_tick, self.selecionado, self.erro = False, None, None, None

    def trocar_politica(self, nome: str, **params) -> bool:
        def acao():
            self.motor.trocar_politica(nome, **params)
            self.config = self.motor.config
            return True
        return self.executar(acao) is True

    def iniciar(self) -> None:
        self.rodando, self.ultimo_tick = True, time.monotonic()

    def pausar(self) -> None:
        self.rodando, self.ultimo_tick = False, None

    def avancar_um(self) -> None:
        self.pausar()
        self.executar(self.motor.passo)

    def tick(self, agora_real: float | None = None) -> int:
        """Avança o tempo simulado proporcionalmente ao tempo real desde o último tick."""
        if not self.rodando:
            return 0
        agora_real = time.monotonic() if agora_real is None else agora_real
        decorrido = min(MAX_ATRASO_S, agora_real - (self.ultimo_tick or agora_real))
        self.ultimo_tick = agora_real
        if decorrido <= 0:
            return 0
        alvo = self.motor.agora + decorrido * self.velocidade
        n = self.executar(lambda: self.motor.avancar_ate(alvo)) or 0
        if self.motor.concluida:
            self.pausar()
        return n

    def executar(self, acao):
        try:
            self.erro = None
            return acao()
        except ErroPersistencia as exc:
            self.pausar()
            self.erro = str(self.motor.ultimo_erro or exc)
            return None


def obter_sessao(st) -> SessaoSimulacao:
    if "sessao" not in st.session_state:
        st.session_state["sessao"] = SessaoSimulacao.nova(config_do_cenario("demo_7min"))
    return st.session_state["sessao"]

