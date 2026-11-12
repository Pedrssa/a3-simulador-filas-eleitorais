"""Explicações em linguagem natural das decisões da fila.

Só LÊ o estado do motor (última chamada registrada e projeção da política ativa).
Nada aqui escolhe quem é atendido: o texto descreve a escolha que o motor já fez
(ou fará, no caso da projeção) com a política que está ativa.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from secao8bit.domain.eleitor import Eleitor
from secao8bit.domain.prioridade import ClassePrioridade

NOME_NIVEL = {0: "mais de 80 anos", 1: "preferência legal", 2: "doador(a) de sangue", 3: "sem preferência"}


@dataclass(frozen=True)
class Explicacao:
    titulo: str
    texto: str
    regra: str  # "eleitoral", "lab" ou "senha": de onde vem a regra citada
    pessoa: str | None = None
    ultrapassou: int = 0


def nome(e: Eleitor) -> str:
    return f"{e.apelido} ({e.id})"


def fundamento(e: Eleitor) -> str:
    """Primeira condição que efetivamente deu preferência (sem a citação do artigo)."""
    for f in e.classificacao.fundamentos:
        if "não aplicada" not in f:
            return f.split(" — ")[0]
    return "sem preferência"


def _hora(motor, t: float) -> str:
    return motor.hora(t)[:5]


def _motivo(motor, e: Eleitor, nivel: int, outro: Eleitor, nivel_outro: int, regra: str, lab: bool) -> str:
    """Por que `e` fica à frente de `outro`, que chegou antes."""
    if regra == "cota":
        k = motor.politica.parametros().get("k", "k")
        return (f"a cota de laboratório foi acionada (após {k} pessoas com preferência seguidas, a vaga vai para "
                "quem não tem preferência e chegou primeiro)")
    if lab and nivel < int(e.classe):
        return (f"na política experimental de aging, quem espera muito sobe de nível: {e.apelido} já estava no "
                f"nível {nivel} ({NOME_NIVEL[nivel]}), melhor que o nível {nivel_outro} de {outro.apelido}")
    if e.classe == ClassePrioridade.MAIS_DE_80:
        return "tem mais de 80 anos, e esse grupo passa à frente de todas as outras preferências (art. 129, § 3º)"
    if e.classe == ClassePrioridade.PREFERENCIAL:
        alvo = "quem não tem preferência" if outro.classe == ClassePrioridade.COMUM else "doadores de sangue"
        return f"tem preferência legal ({fundamento(e)}, art. 129, § 2º), que vem antes de {alvo}"
    if e.classe == ClassePrioridade.DOADOR:
        return ("é doador(a) de sangue com comprovante válido: vota depois das demais preferências, mas antes de quem "
                "não tem preferência (art. 129, § 5º)")
    return f"o nível dele(a) na política ativa é {nivel} e o de {outro.apelido} é {nivel_outro}"


def _frase_ultrapassagem(motor, e: Eleitor, atras: list[Eleitor], motivo: str, conclusao: str) -> str:
    primeiro = atras[0]
    resto = len(atras) - 1
    mais = "" if resto == 0 else (" e mais 1 pessoa" if resto == 1 else f" e mais {resto} pessoas")
    # apelidos fictícios podem se repetir: o ID desfaz a ambiguidade
    return (f"{nome(e)} chegou às {_hora(motor, e.chegada)}, depois de {primeiro.apelido} "
            f"({primeiro.id}, {_hora(motor, primeiro.chegada)}){mais}, mas {motivo}. Por isso {conclusao}.")


def explicar_ultima_chamada(motor) -> Explicacao | None:
    """Explica a última pessoa retirada da fila, com o estado registrado no momento da chamada."""
    u = motor.estado.ultima_chamada
    if not u:
        return None
    el = motor.secao.eleitores
    e = el[u["eleitor"]]
    titulo = f"{_hora(motor, u['instante'])} · {nome(e)} foi chamado(a)"
    if u["regra"] == "senha":
        return Explicacao(titulo, f"Depois das 17h a mesa distribui senhas e chama da maior para a menor "
                                  f"(art. 160, § 3º). {e.apelido} tinha a senha {e.senha}.", "senha", e.id)
    lab = bool(u["experimental"])
    nivel = int(u["chave"][0])
    atras = [el[i] for i in u["ultrapassou"]]
    if atras:
        o = atras[0]
        nivel_o = _nivel(motor, o, u["instante"])
        texto = _frase_ultrapassagem(motor, e, atras, _motivo(motor, e, nivel, o, nivel_o, u["regra"], lab),
                                     "foi chamado(a) antes")
    elif u["regra"] == "cota":
        texto = (f"{_motivo(motor, e, nivel, e, nivel, 'cota', lab).capitalize()}. {e.apelido} era a pessoa sem "
                 "preferência que esperava havia mais tempo.")
    else:
        texto = (f"Ninguém que chegou antes ficou para trás: {e.apelido} era quem esperava havia mais tempo no "
                 f"melhor nível presente na fila ({NOME_NIVEL.get(nivel, nivel)}).")
    if lab:
        texto += " Política de laboratório: não é procedimento eleitoral."
    return Explicacao(titulo, texto, "lab" if lab else "eleitoral", e.id, len(atras))


def _nivel(motor, e: Eleitor, instante: float) -> int:
    return int(motor.politica.chave(e, instante)[0])


def explicar_proximo(motor) -> Explicacao:
    """Quem a política ativa chamaria agora e por quê (projeção sem novas chegadas)."""
    ordem = motor.prever_atendimento()
    if not ordem:
        return Explicacao("Ninguém esperando", "A fila está vazia. Quando alguém chegar, aparece aqui quem será "
                          "chamado e por quê.", "eleitoral")
    el = motor.secao.eleitores
    entrada = ordem[0]
    e = el[entrada.eleitor_id]
    titulo = f"Próximo a ser chamado: {nome(e)}"
    if motor.estado.encerrado:
        return Explicacao(titulo, f"Fila encerrada às 17h: {e.apelido} tem a maior senha restante ({e.senha}).",
                          "senha", e.id)
    lab = motor.politica.experimental
    esperando = [el[x.eleitor_id] for x in ordem[1:]]
    atras = sorted((o for o in esperando if (o.chegada, o.seq_chegada) < (e.chegada, e.seq_chegada)),
                   key=lambda o: (o.chegada, o.seq_chegada))
    nivel = int(entrada.chave[0])
    livre = motor.secao.posto_identificacao.livre
    quando = "assim que a mesa liberar" if not livre else "agora"
    regra = _regra_da_proxima_selecao(motor)
    if atras:
        o = atras[0]
        nivel_o = int(next(x.chave[0] for x in ordem if x.eleitor_id == o.id))
        texto = _frase_ultrapassagem(motor, e, atras, _motivo(motor, e, nivel, o, nivel_o, regra, lab),
                                     f"será chamado(a) antes, {quando}")
    else:
        texto = (f"{e.apelido} chegou às {_hora(motor, e.chegada)} e é quem espera há mais tempo no melhor nível "
                 f"presente ({NOME_NIVEL.get(nivel, nivel)}). Será chamado(a) {quando}.")
    if lab:
        texto += " Política de laboratório: não é procedimento eleitoral."
    return Explicacao(titulo, texto, "lab" if lab else "eleitoral", e.id, len(atras))


def _regra_da_proxima_selecao(motor) -> str:
    """Executa a seleção da política ativa sobre CÓPIAS (mesmo código do motor) e devolve a regra usada."""
    fila, politica = copy.deepcopy(motor.secao.fila), copy.deepcopy(motor.politica)
    if politica.depende_do_tempo:
        fila.reconstruir(lambda eid: politica.chave(motor.secao.eleitores[eid], motor.agora))
    return politica.selecionar(fila, motor.secao.eleitores, motor.agora).regra


def resumo_fila(motor, limite: int = 8) -> list[dict]:
    """Primeiros da fila na ordem em que serão chamados (para a lista ao lado da cena)."""
    el = motor.secao.eleitores
    linhas = []
    for i, x in enumerate(motor.prever_atendimento()[:limite]):
        e = el[x.eleitor_id]
        linhas.append({"pos": i + 1, "pessoa": nome(e), "icone": e.classe.icone or "—",
                       "prioridade": e.classe.rotulo, "chegou": _hora(motor, e.chegada),
                       "espera": round(e.espera(motor.agora), 1)})
    return linhas
