"""Tradução do estado do motor para a cena 8 bits.

A animação apenas desenha o que este dicionário descreve: ela não decide quem é
atendido, não altera a fila e não gera ocorrências. Posições são "zonas + vaga";
o JavaScript converte em pixels e interpola o movimento.
"""

from __future__ import annotations

from secao8bit.domain.eleitor import Eleitor, EstadoEleitor
from secao8bit.domain.prioridade import ClassePrioridade
from secao8bit.domain.recursos import Cargo, EstadoRecurso

PERMANENCIA_SAIDA_MIN = 1.5
ASSENTOS_PREFERENCIAIS = 8  # no corredor, junto à porta (art. 181: o recinto da Mesa não é sala de espera)

_ZONA_POR_ESTADO = {  # chave = nome do estado
    "IDENTIFICACAO": "identificacao",
    "AGUARDANDO_URNA": "aguardando_urna",
    "HABILITACAO": "habilitacao",
    "VOTANDO": "cabine",
    "COMPROVANTE": "comprovante",
    "CONCLUIDO": "saida",
    "ENCAMINHADO": "saida",
    "NAO_ADMITIDO": "recusado",
}

_TEXTO_RECURSO = {EstadoRecurso.DISPONIVEL: "LIVRE", EstadoRecurso.OCUPADO: "OCUPADA",
                  EstadoRecurso.INTERROMPIDO: "INTERROMPIDA"}


def paleta(eid: str) -> int:
    """Aparência sorteada pelo ID (nunca pela condição de prioridade)."""
    return sum(ord(c) * (i + 1) for i, c in enumerate(eid)) % 997


def _balao(e: Eleitor, motor) -> str:
    o, est = e.ocorrencias, e.estado
    for inc in motor.estado.incidentes_ativos.values():
        if inc.get("eleitor") == e.id and inc.get("tipo") == "discussao":
            return "Posso passar?"
    if est == EstadoEleitor.IDENTIFICACAO:
        if o.secao_errada:
            return "Seção certa?"
        if o.problema_documento:
            return "Documento?"
        return ""
    if est == EstadoEleitor.HABILITACAO:
        return "Falhou!" if o.falha_biometria else ""
    if est == EstadoEleitor.VOTANDO:
        return "Votando"
    if est == EstadoEleitor.ENCAMINHADO:
        if "cartório" in e.motivo_saida:
            return "Ir ao cartório"
        if "documento" in e.motivo_saida:
            return "Buscar documento"
        return "Procurar a JE"
    if est == EstadoEleitor.NAO_ADMITIDO:
        return "Encerrado"
    if est == EstadoEleitor.AGUARDANDO and e.espera(motor.agora) >= motor.config.limiar_starvation_min:
        return "Esperando muito!"
    return ""


def montar_cena(motor, selecionado: str | None = None) -> dict:
    secao, agora = motor.secao, motor.agora
    ordem = [x.eleitor_id for x in motor.prever_atendimento()]
    pos_fila = {eid: i for i, eid in enumerate(ordem)}
    pos_comp = {eid: i for i, eid in enumerate(secao.aguardando_comprovante)}
    pessoas: list[dict] = []
    # Quem tem preferência senta (até ASSENTOS_PREFERENCIAIS), na ordem da fila; os demais ficam em pé.
    # É só posição visual: a ordem de chamada continua sendo a da heap (campo "posicao").
    lugares: dict[str, tuple[str, int]] = {}
    sentados = em_pe = 0
    for eid in ordem:
        if secao.eleitores[eid].classe != ClassePrioridade.COMUM and sentados < ASSENTOS_PREFERENCIAIS:
            lugares[eid] = ("assento", sentados)
            sentados += 1
        else:
            lugares[eid] = ("fila", em_pe)
            em_pe += 1

    for e in secao.eleitores.values():
        if e.estado == EstadoEleitor.CHEGANDO:
            continue
        if e.finalizado and (e.saida is None or agora - e.saida > PERMANENCIA_SAIDA_MIN):
            continue
        if e.estado == EstadoEleitor.AGUARDANDO:
            zona, vaga = lugares[e.id]
        elif e.estado == EstadoEleitor.AGUARDANDO_COMPROVANTE:
            zona, vaga = "aguardando_comprovante", pos_comp[e.id]
        else:
            zona, vaga = _ZONA_POR_ESTADO[e.estado.name], 0
        icone = e.classe.icone
        if e.senha is not None and e.estado == EstadoEleitor.AGUARDANDO:
            icone = f"#{e.senha}" + (f" {icone}" if icone else "")
        pessoa = {
            "id": e.id, "tipo": "eleitor", "rotulo": e.apelido, "icone": icone,
            "classe": int(e.classe), "zona": zona, "vaga": vaga, "estado": e.estado.value,
            "posicao": pos_fila[e.id] + 1 if e.id in pos_fila else None,
            "acao": _acao(e, motor),
            "balao": _balao(e, motor), "paleta": paleta(e.id), "selecionado": e.id == selecionado,
            "starvation": e.estado == EstadoEleitor.AGUARDANDO
            and e.espera(agora) >= motor.config.limiar_starvation_min,
        }
        pessoas.append(pessoa)
        if e.acompanhante_visual:
            pessoas.append({**pessoa, "id": f"{e.id}-acomp", "tipo": "acompanhante", "rotulo": "Acompanhante",
                            "icone": "A", "balao": "", "segue": e.id, "paleta": paleta(e.id + "a"),
                            "selecionado": False, "starvation": False})

    pres = secao.presidente
    zona_pres = "mesa_presidente"
    if pres.ocupado_com_incidente:
        tipo_inc = motor.estado.incidentes_ativos.get(motor.estado.presidente_em or "", {}).get("tipo")
        zona_pres = {"falha_urna": "urna_presidente", "discussao": "fila_presidente"}.get(tipo_inc, "mesa_presidente")
    rotulos = {Cargo.PRESIDENTE: "PRES.", Cargo.PRIMEIRO_MESARIO: "1º MES", Cargo.SEGUNDO_MESARIO: "2º MES",
               Cargo.SECRETARIO: "SECRET."}
    zonas = {Cargo.PRESIDENTE: zona_pres, Cargo.PRIMEIRO_MESARIO: "mesa_m1", Cargo.SEGUNDO_MESARIO: "mesa_m2",
             Cargo.SECRETARIO: "porta_secretario"}
    alvo_discussao = next((v.get("eleitor") for v in motor.estado.incidentes_ativos.values()
                           if v.get("tipo") == "discussao"), None)
    if secao.mesa[Cargo.SECRETARIO].ocupado_com_incidente and alvo_discussao in pos_fila:
        zonas[Cargo.SECRETARIO] = "fila_secretario"
    for cargo, integrante in secao.mesa.items():
        pessoas.append({
            "id": f"mesa-{cargo.name.lower()}", "tipo": "mesa", "rotulo": rotulos[cargo], "icone": "",
            "zona": zonas[cargo], "vaga": pos_fila.get(alvo_discussao, 0) if zonas[cargo].startswith("fila_") else 0,
            "estado": integrante.ocupado_com_incidente or "em posto", "acao": _acao_mesa(cargo, integrante, motor),
            "balao": _balao_mesa(cargo, integrante, motor), "paleta": paleta(cargo.name), "selecionado": False,
        })
    for p in secao.apoio.values():
        if not p.presente:
            continue
        pessoas.append({
            "id": p.id, "tipo": p.papel, "rotulo": p.rotulo, "icone": "", "zona": p.zona, "vaga": int(p.id[-1:])
            if p.id[-1:].isdigit() else 0, "estado": p.zona, "balao": p.balao, "paleta": paleta(p.id),
            "selecionado": False, "acao": _acao_apoio(p),
        })

    def recurso(r) -> dict:
        return {"estado": r.estado.name, "texto": _TEXTO_RECURSO[r.estado], "motivo": r.motivo_interrupcao}

    proximo = None
    if ordem:
        p0 = secao.eleitores[ordem[0]]
        proximo = {"id": p0.id, "classe": p0.classe.rotulo, "icone": p0.classe.icone}

    return {
        "minuto_do_dia": motor.config.hora_inicio_min + agora,
        "portao_fechado": motor.estado.encerrado,
        "viatura": any(p.papel == "policial" for p in secao.apoio.values()),
        "estacoes": _estacoes(motor, ordem),
        "proximo": proximo,
        "narracao": [_narrar(r, motor) for r in reversed(motor.estado.recentes[-7:])],
        "hora": motor.hora(), "agora": round(agora, 4), "secao": secao.numero,
        "politica": motor.politica.nome, "experimental": motor.politica.experimental,
        "encerrado": motor.estado.encerrado, "concluida": motor.concluida,
        "urna": {**recurso(secao.urna), "contingencia": secao.urna.em_contingencia},
        "identificacao": recurso(secao.posto_identificacao),
        "comprovante": recurso(secao.posto_comprovante),
        "fila_total": len(ordem),
        "pessoas": pessoas,
        "recentes": motor.estado.recentes[-12:],
        "incidentes": [f"{k}: {v['tipo']} ({v.get('etapa', '')})" for k, v in motor.estado.incidentes_ativos.items()],
    }


def _balao_mesa(cargo: Cargo, integrante, motor) -> str:
    secao = motor.secao
    if integrante.ocupado_com_incidente:
        return {"religando a urna": "Religando urna"}.get(integrante.ocupado_com_incidente,
                                                          integrante.ocupado_com_incidente[:18].capitalize())
    if cargo == Cargo.PRESIDENTE and secao.posto_identificacao.ocupante:
        return "Documento?"
    if cargo == Cargo.PRIMEIRO_MESARIO and secao.urna.ocupante and \
            secao.eleitores[secao.urna.ocupante].estado == EstadoEleitor.HABILITACAO:
        return "Polegar"
    if cargo == Cargo.SEGUNDO_MESARIO and secao.posto_comprovante.ocupante:
        return "Comprovante"
    if cargo == Cargo.SECRETARIO and motor.estado.encerrado:
        return "Senhas"
    return ""


_FRASES = {
    "ENTRADA_FILA": "{q} chegou e entrou na fila",
    "SAIDA_FILA": "{q} foi CHAMADO(A) à mesa",
    "FIM_IDENTIFICACAO": "{q} teve o documento conferido pela Presidente",
    "INICIO_HABILITACAO": "{q} faz a biometria com o 1º mesário (urna reservada)",
    "INICIO_VOTACAO": "{q} entrou na cabine para votar",
    "FIM_VOTACAO": "{q} terminou de votar; a urna ficou livre",
    "INICIO_COMPROVANTE": "{q} recebe o comprovante do 2º mesário",
    "SAIDA": "{q} saiu da seção",
    "ENCAMINHADO": "{q} não pôde votar aqui",
    "CHEGADA_NAO_ADMITIDA": "{q} chegou depois das 17h e não foi admitido(a)",
}


def _quem(eid: str | None, motor) -> str:
    if not eid or eid not in motor.secao.eleitores:
        return ""
    e = motor.secao.eleitores[eid]
    return f"{e.id} ({e.classe.rotulo.lower()})"


def _narrar(r: dict, motor) -> dict:
    """Frase curta em português para o painel 'o que acabou de acontecer'."""
    tipo = r["tipo"]
    frase = _FRASES.get(tipo)
    if frase and r.get("eleitor"):
        texto = frase.format(q=_quem(r["eleitor"], motor))
        if tipo in ("SAIDA_FILA", "ENCAMINHADO"):
            texto += ": " + r["texto"]
    else:
        texto = r["texto"]
    nivel = "alerta" if r.get("som") == "alerta" or tipo.startswith(("RECURSO_INTERROMPIDO", "INCIDENTE")) else (
        "destaque" if tipo == "SAIDA_FILA" else "normal")
    return {"seq": r["seq"], "hora": r.get("hora", ""), "tipo": tipo, "eleitor": r.get("eleitor"),
            "texto": texto, "nivel": nivel}


def _estacoes(motor, ordem: list[str]) -> list[dict]:
    secao = motor.secao

    def quem(eid: str | None) -> str:
        return _quem(eid, motor) if eid else "—"

    urna_ocup = secao.urna.ocupante
    em_hab = urna_ocup if urna_ocup and secao.eleitores[urna_ocup].estado == EstadoEleitor.HABILITACAO else None
    votando = urna_ocup if urna_ocup and secao.eleitores[urna_ocup].estado == EstadoEleitor.VOTANDO else None
    pres = secao.presidente
    ident_status = _TEXTO_RECURSO[secao.posto_identificacao.estado]
    if pres.ocupado_com_incidente and not secao.posto_identificacao.interrompido:
        ident_status += " (mesário substituto)"
    return [
        {"n": 1, "nome": "Fila", "quem": f"{len(ordem)} aguardando", "status": "—",
         "detalhe": f"próximo: {quem(ordem[0])}" if ordem else "vazia"},
        {"n": 2, "nome": "Documento · Presidente", "quem": quem(secao.posto_identificacao.ocupante),
         "status": ident_status, "detalhe": secao.posto_identificacao.motivo_interrupcao or pres.ocupado_com_incidente},
        {"n": 3, "nome": "Biometria · 1º mesário", "quem": quem(em_hab),
         "status": "OCUPADA" if em_hab else ("INTERROMPIDA" if secao.urna.interrompido else "LIVRE"), "detalhe": ""},
        {"n": 4, "nome": "Cabine · urna", "quem": quem(votando), "status": _TEXTO_RECURSO[secao.urna.estado],
         "detalhe": secao.urna.motivo_interrupcao or ("urna de contingência" if secao.urna.em_contingencia else "")},
        {"n": 5, "nome": "Comprovante · 2º mesário", "quem": quem(secao.posto_comprovante.ocupante),
         "status": _TEXTO_RECURSO[secao.posto_comprovante.estado],
         "detalhe": f"{len(secao.aguardando_comprovante)} aguardando" if secao.aguardando_comprovante else ""},
    ]


def _acao(e: Eleitor, motor) -> str:
    """Gesto que a animação deve mostrar (derivado só do estado)."""
    o, est = e.ocorrencias, e.estado
    for inc in motor.estado.incidentes_ativos.values():
        if inc.get("eleitor") == e.id and inc.get("tipo") == "discussao":
            return "discutindo"
    if est == EstadoEleitor.IDENTIFICACAO:
        if o.impugnacao:
            return "impugnado"
        if o.secao_errada:
            return "secao_errada"
        if o.problema_documento:
            return "sem_documento"
        return "entregando_documento"
    if est == EstadoEleitor.AGUARDANDO_URNA:
        return "aguardando"
    if est == EstadoEleitor.HABILITACAO:
        if o.celular:
            return "celular_recusa" if o.celular_recusa else "celular"
        return "biometria_falha" if o.falha_biometria else "biometria"
    if est == EstadoEleitor.VOTANDO:
        return "votando"
    if est == EstadoEleitor.COMPROVANTE:
        return "recebendo"
    if est == EstadoEleitor.ENCAMINHADO:
        return "saindo_sem_votar"
    if est == EstadoEleitor.CONCLUIDO:
        return "saindo"
    return "esperando"


def _acao_mesa(cargo: Cargo, integrante, motor) -> str:
    secao = motor.secao
    oc = integrante.ocupado_com_incidente
    if oc:
        if "urna" in oc:
            return "religando"
        if "discuss" in oc:
            return "mediando"
        if "senha" in oc:
            return "senhas"
        return "orientando"
    if cargo == Cargo.PRESIDENTE and secao.posto_identificacao.ocupante:
        return "conferindo"
    if cargo == Cargo.PRIMEIRO_MESARIO and secao.urna.ocupante and             secao.eleitores[secao.urna.ocupante].estado == EstadoEleitor.HABILITACAO:
        return "biometria"
    if cargo == Cargo.SEGUNDO_MESARIO and secao.posto_comprovante.ocupante:
        return "entregando"
    return "parado"


def _acao_apoio(p) -> str:
    if p.papel == "tecnico":
        return "consertando" if p.zona == "urna" else "andando"
    if p.papel == "manifestante":
        if p.zona in ("viatura", "indo_embora"):
            return p.zona
        return "panfletando" if "Vote" in p.balao else "adesivo"
    if p.papel == "fiscal":
        return "impugnando" if p.balao else "observando"
    if p.papel == "apoio":
        return "alerta" if p.balao else "parado"
    if p.papel == "policial":
        if p.zona == "policia_viatura":
            return "conduzindo"
        return "abordando" if p.zona.endswith("externo") else "verificando"
    return "parado"

