"""Seção eleitoral: composição da mesa, recursos, fila e invariantes."""

from __future__ import annotations

from dataclasses import dataclass, field

from secao8bit.domain.eleitor import Eleitor, EstadoEleitor
from secao8bit.domain.fila import FilaPrioridade
from secao8bit.domain.recursos import Cargo, IntegranteMesa, RecursoAtendimento, Urna


class InvarianteViolada(AssertionError):
    pass


def mesa_padrao() -> dict[Cargo, IntegranteMesa]:
    """Mesa Receptora de Votos (art. 9º): Presidente, 1º e 2º mesários e secretário.

    A divisão das tarefas abaixo é uma simplificação didática apoiada no art. 133
    (sequência de identificação/habilitação) e no art. 126 (a Presidência pode
    designar componentes da Mesa). Não afirma exclusividade de cargo.
    """
    return {
        Cargo.PRESIDENTE: IntegranteMesa(
            Cargo.PRESIDENTE, "Presidente Ana",
            ("conferir documento com foto (art. 133, II)", "digitar CPF/título (art. 133, III–IV)",
             "resolver ocorrências e manter a ordem (art. 126, VII–VIII)"),
        ),
        Cargo.PRIMEIRO_MESARIO: IntegranteMesa(
            Cargo.PRIMEIRO_MESARIO, "Mesário Bruno",
            ("localizar no Caderno de Votação (art. 133, V)", "conduzir biometria e autorizar (art. 133, VI–VII)"),
        ),
        Cargo.SEGUNDO_MESARIO: IntegranteMesa(
            Cargo.SEGUNDO_MESARIO, "Mesária Carla",
            ("guarda de pertences (art. 137, §§ 2º–3º)", "entregar comprovante (art. 133, IX; art. 137, § 4º)"),
        ),
        Cargo.SECRETARIO: IntegranteMesa(
            Cargo.SECRETARIO, "Secretário Davi",
            ("organizar o acesso e a fila (art. 129, § 6º, por designação)", "distribuir senhas no encerramento (art. 160, § 2º)"),
        ),
    }


@dataclass
class PersonagemApoio:
    """Personagens que não integram a mesa: apoio logístico, fiscal, técnico, polícia."""

    id: str
    papel: str  # apoio | fiscal | tecnico | policial | manifestante
    rotulo: str
    zona: str  # onde está na cena
    presente: bool = True
    balao: str = ""


@dataclass
class SecaoEleitoral:
    numero: str = "0042"
    mesa: dict[Cargo, IntegranteMesa] = field(default_factory=mesa_padrao)
    posto_identificacao: RecursoAtendimento = field(
        default_factory=lambda: RecursoAtendimento("Mesa: identificação"))
    urna: Urna = field(default_factory=lambda: Urna("Urna"))
    posto_comprovante: RecursoAtendimento = field(
        default_factory=lambda: RecursoAtendimento("Mesa: comprovante"))
    fila: FilaPrioridade = field(default_factory=FilaPrioridade)
    eleitores: dict[str, Eleitor] = field(default_factory=dict)
    aguardando_comprovante: list[str] = field(default_factory=list)  # FIFO pós-voto, não afeta prioridade
    apoio: dict[str, PersonagemApoio] = field(default_factory=dict)
    recebendo_eleitores: bool = True
    proxima_senha: int = 1

    def __post_init__(self) -> None:
        if not self.apoio:
            for p in (
                PersonagemApoio("apoio-1", "apoio", "Apoio logístico (coord. acessibilidade)", "portao"),
                PersonagemApoio("fiscal-1", "fiscal", "Fiscal credenciado(a)", "fiscal"),
            ):
                self.apoio[p.id] = p

    @property
    def presidente(self) -> IntegranteMesa:
        return self.mesa[Cargo.PRESIDENTE]

    def registrar(self, eleitor: Eleitor) -> None:
        if eleitor.id in self.eleitores:
            raise InvarianteViolada(f"personagem duplicado: {eleitor.id}")
        self.eleitores[eleitor.id] = eleitor

    def em_estado(self, *estados: EstadoEleitor) -> list[Eleitor]:
        return [e for e in self.eleitores.values() if e.estado in estados]

    def verificar_invariantes(self) -> None:
        """Falha se a simulação chegou a um estado impossível."""
        votando = self.em_estado(EstadoEleitor.HABILITACAO, EstadoEleitor.VOTANDO)
        if len(votando) > 1:
            raise InvarianteViolada(f"mais de uma pessoa na urna: {[e.id for e in votando]}")
        if votando and self.urna.ocupante != votando[0].id:
            raise InvarianteViolada("urna não registra quem está votando")
        if not votando and self.urna.ocupante is not None:
            raise InvarianteViolada(f"urna ocupada por {self.urna.ocupante} sem ninguém votando")

        na_mesa = self.em_estado(EstadoEleitor.IDENTIFICACAO, EstadoEleitor.AGUARDANDO_URNA)
        if len(na_mesa) > 1:
            raise InvarianteViolada(f"mais de uma pessoa no posto de identificação: {[e.id for e in na_mesa]}")
        if (na_mesa[0].id if na_mesa else None) != self.posto_identificacao.ocupante:
            raise InvarianteViolada("posto de identificação inconsistente")

        aguardando = {e.id for e in self.em_estado(EstadoEleitor.AGUARDANDO)}
        ids_fila = {e.eleitor_id for e in self.fila}
        if aguardando != ids_fila:
            raise InvarianteViolada(f"fila e estados divergem: {sorted(aguardando ^ ids_fila)}")
        if not self.fila.invariante_ok():
            raise InvarianteViolada("propriedade de heap violada")

        comp = self.em_estado(EstadoEleitor.COMPROVANTE)
        if len(comp) > 1 or (comp[0].id if comp else None) != self.posto_comprovante.ocupante:
            raise InvarianteViolada("posto de comprovante inconsistente")
        esperando_comp = {e.id for e in self.em_estado(EstadoEleitor.AGUARDANDO_COMPROVANTE)}
        if esperando_comp != set(self.aguardando_comprovante) or len(self.aguardando_comprovante) != len(esperando_comp):
            raise InvarianteViolada("lista de comprovante inconsistente")
