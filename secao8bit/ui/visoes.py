"""As quatro visões da interface, em ordem didática.

1. Entenda a fila      — FIFO × prioridade e um laboratório com a heap real.
2. Simulação ao vivo   — a seção eleitoral, quem é o próximo e por quê.
3. Como o algoritmo decide — chave, heap física × projeção, agenda, código real.
4. Resultados e auditoria  — métricas/SLA, starvation e políticas, SQL, documentos.

Como em `abas.py`, tudo aqui só LÊ o motor ou chama sua API pública.
"""

from __future__ import annotations

import inspect
from html import escape

import pandas as pd
import streamlit as st

from secao8bit.application.cena import montar_cena
from secao8bit.application.didatica import CLASSES, LaboratorioFila
from secao8bit.application.explicacao import Explicacao, explicar_proximo, explicar_ultima_chamada, resumo_fila
from secao8bit.domain.politicas import PoliticaEleitoral
from secao8bit.ui import abas
from secao8bit.ui.componente import cena_8bit
from secao8bit.ui.sessao import TICK_S, SessaoSimulacao

VISOES = {
    "entenda": "1 · Entenda a fila",
    "ao_vivo": "2 · Ao vivo",
    "algoritmo": "3 · Algoritmo",
    "resultados": "4 · Resultados",
}

COR_CLASSE = {0: "#ffd34d", 1: "#8fd3ff", 2: "#ffb3c1", 3: "#e8e8e8"}

ESTILO = """<style>
  .s8-h { font-size: 1.15rem; font-weight: 700; margin: .4rem 0 .2rem; color: #f4f1e8; }
  .s8-lead { color: #c9c5d8; max-width: 72ch; line-height: 1.5; margin: 0 0 .6rem; }
  .s8-fila { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 4px 0 10px; }
  .s8-pessoa { display: inline-flex; flex-direction: column; align-items: center; min-width: 74px; padding: 6px 8px;
               border: 2px solid #3a3d55; border-radius: 4px; background: #1c1e2b; }
  .s8-pessoa .n { font-weight: 700; color: #f4f1e8; }
  .s8-pessoa .c { font: 700 12px/1 Consolas, monospace; color: #14100a; padding: 2px 5px; margin-top: 4px;
                  border: 1px solid #14100a; }
  .s8-pessoa .h { font-size: 12px; color: #a9a5bd; margin-top: 3px; }
  .s8-pessoa.sai { border-color: #ffd34d; box-shadow: 0 0 0 2px #ffd34d55; }
  .s8-seta { color: #a9a5bd; font-size: 1.1rem; }
  .s8-saida { font-size: 12px; color: #ffd34d; font-weight: 700; }
  .s8-array { display: flex; gap: 4px; flex-wrap: wrap; margin: 4px 0 8px; }
  .s8-cel { min-width: 64px; border: 2px solid #3a3d55; border-radius: 3px; background: #1c1e2b; text-align: center;
            padding: 3px 4px; }
  .s8-cel .i { font: 12px Consolas, monospace; color: #a9a5bd; }
  .s8-cel .n { font-weight: 700; }
  .s8-cel .k { font: 11px Consolas, monospace; color: #c9c5d8; }
  .s8-cel.mudou { border-color: #e8772e; background: #2b2018; }
  .s8-decisao { border-left: 6px solid #2e9e4f; background: #1a2a20; padding: 10px 14px; border-radius: 3px;
                margin: 4px 0 10px; }
  .s8-decisao.lab { border-left-color: #e8772e; background: #2b2018; }
  .s8-decisao.senha { border-left-color: #8fd3ff; background: #16222e; }
  .s8-decisao .t { font-weight: 700; color: #f4f1e8; margin-bottom: 4px; }
  .s8-decisao p { margin: 0; line-height: 1.5; color: #e6e2f0; }
  .s8-decisao .r { font-size: 12px; color: #a9a5bd; margin-top: 6px; }
  .s8-lista { list-style: none; margin: 0; padding: 0; }
  .s8-lista li { display: grid; grid-template-columns: 2.2em 3.4em 1fr auto; gap: 8px; align-items: center;
                 padding: 4px 6px; border-bottom: 1px solid #2c2f42; }
  .s8-lista li:first-child { background: #2a2614; font-weight: 700; }
  .s8-lista .tag { font: 700 12px/1 Consolas, monospace; color: #14100a; padding: 3px 4px; text-align: center;
                   border: 1px solid #14100a; }
  .s8-lista .m { color: #a9a5bd; font-size: 13px; white-space: nowrap; }
  .s8-camada { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 6px 0 10px; }
  .s8-camada div { border: 1px solid #3a3d55; border-radius: 4px; padding: 8px 10px; background: #1c1e2b; }
  .s8-camada b { display: block; margin-bottom: 4px; }
  @media (max-width: 760px) { .s8-camada { grid-template-columns: 1fr; } }
</style>"""


def _pessoa_html(nome: str, classe: int, legenda: str = "", sai: bool = False) -> str:
    curto = CLASSES[classe][0]
    return (f'<div class="s8-pessoa{" sai" if sai else ""}"><span class="n">{escape(nome)}</span>'
            f'<span class="c" style="background:{COR_CLASSE[classe]}">{escape(curto if curto != "—" else "comum")}</span>'
            f'<span class="h">{escape(legenda)}</span></div>')


def _fila_html(pessoas: list[tuple[str, int, str]], rotulo_saida: str) -> str:
    partes = [f'<span class="s8-saida">{escape(rotulo_saida)} ◀</span>']
    for i, (n, c, leg) in enumerate(pessoas):
        partes.append(_pessoa_html(n, c, leg, sai=i == 0))
        if i < len(pessoas) - 1:
            partes.append('<span class="s8-seta" aria-hidden="true">·</span>')
    return '<div class="s8-fila" role="list">' + "".join(partes) + "</div>"


def cartao(exp: Explicacao | None, vazio: str = "") -> str:
    if exp is None:
        return f'<div class="s8-decisao"><p>{escape(vazio)}</p></div>'
    origem = {"eleitoral": "Regra eleitoral real (Res. TSE 23.751/2026, art. 129)",
              "lab": "Política de LABORATÓRIO — hipótese acadêmica, sem validade eleitoral",
              "senha": "Encerramento às 17h (art. 160)"}[exp.regra]
    return (f'<div class="s8-decisao {exp.regra}" role="status"><div class="t">{escape(exp.titulo)}</div>'
            f"<p>{escape(exp.texto)}</p><div class=\"r\">{escape(origem)}</div></div>")


# ============================================================ 1. Entenda a fila
def visao_entenda() -> None:
    st.html(ESTILO)
    st.html('<p class="s8-lead">Uma seção eleitoral tem <b>uma única urna</b>. Todo mundo espera numa fila, mas a lei '
            "manda algumas pessoas passarem à frente. Esta visão mostra, com poucas pessoas, como o programa decide "
            "quem é chamado — antes de ver a seção inteira funcionando.</p>")

    exemplo = [("Ana", 3, "chegou 08:00"), ("Bruno", 3, "chegou 08:01"), ("Carla", 1, "chegou 08:02 · gestante")]
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.html('<div class="s8-h">Fila comum (FIFO)</div>'
                '<p class="s8-lead">O primeiro a chegar é o primeiro a sair. A ordem de chamada é a ordem de chegada.</p>'
                + _fila_html(exemplo, "sai"))
    with c2:
        st.html('<div class="s8-h">Fila de prioridade</div>'
                '<p class="s8-lead">Cada pessoa recebe uma <b>chave</b>: primeiro o nível de prioridade, depois a hora '
                "de chegada. Sai quem tem a menor chave. Carla chegou por último, mas é gestante (preferência legal).</p>"
                + _fila_html([exemplo[2], exemplo[0], exemplo[1]], "sai"))

    st.divider()
    st.html('<div class="s8-h">Laboratório: a heap por dentro</div>'
            '<p class="s8-lead">Adicione pessoas e chame a próxima. Por trás, roda a <b>mesma classe</b> '
            "<code>FilaPrioridade</code> do simulador (heap binária mínima). Laranja marca as posições do array que "
            "mudaram na última operação.</p>")
    lab: LaboratorioFila = st.session_state.setdefault("lab_heap", LaboratorioFila.exemplo())
    b = st.columns(6)
    rotulos = [(3, "+ Sem preferência"), (1, "+ Preferência (P)"), (0, "+ Mais de 80"), (2, "+ Doador (D)")]
    for col, (classe, rot) in zip(b, rotulos):
        if col.button(rot, key=f"lab_add_{classe}", width="stretch", disabled=len(lab.fila) >= 15):
            lab.inserir(classe)
    if b[4].button("Chamar próximo", key="lab_extrair", type="primary", width="stretch", disabled=not len(lab.fila)):
        lab.extrair()
    if b[5].button("Recomeçar", key="lab_reset", width="stretch", help="Volta ao exemplo com Ana, Bruno e Carla."):
        lab = st.session_state["lab_heap"] = LaboratorioFila.exemplo()

    ultimo = lab.passos[-1] if lab.passos else None
    if ultimo:
        st.html(f'<div class="s8-decisao"><div class="t">Última operação: '
                f'{"inserir (heappush)" if ultimo.operacao == "inserir" else "chamar o próximo (heappop)"}</div>'
                f"<p>{escape(ultimo.explicacao)}</p></div>")
    if lab.atendidos_prioridade:
        st.html(f'<p class="s8-lead">Na última chamada, a fila de prioridade chamou '
                f"<b>{escape(lab.atendidos_prioridade[-1])}</b>; uma fila comum teria chamado "
                f"<b>{escape(lab.atendidos_fifo[-1])}</b>, que chegou primeiro.</p>")

    g1, g2 = st.columns([3, 2], gap="large")
    with g1:
        st.markdown("**Array interno da heap** (é assim que fica na memória)")
        mudaram = set(ultimo.mudaram) if ultimo else set()
        celulas = "".join(
            f'<div class="s8-cel{" mudou" if i in mudaram else ""}"><div class="i">[{i}]</div>'
            f'<div class="n">{escape(x.eleitor_id)}</div><div class="k">{x.chave[0]}, {x.chave[1]}</div></div>'
            for i, x in enumerate(lab.fila.array_interno()))
        st.html(f'<div class="s8-array" aria-label="Array interno da heap">{celulas or "<em>vazio</em>"}</div>')
        st.caption("Regra da heap: cada pai tem chave menor ou igual à dos filhos (índices 2i+1 e 2i+2). "
                   "Isso NÃO deixa o array inteiro em ordem — só garante que o menor está no índice 0.")
        if len(lab.fila):
            st.graphviz_chart(_dot_lab(lab, mudaram))
    with g2:
        st.markdown("**Ordem de atendimento** (cópia ordenada, só para mostrar)")
        el = lab.classes
        st.html(_fila_html([(n, el[n], "") for n in lab.ordem_prioridade()], "próximo"))
        st.markdown("**Ordem de chegada** (o que uma fila comum faria)")
        st.html(_fila_html([(n, el[n], "") for n in lab.ordem_fifo()], "próximo"))
        st.markdown("**A chave usada pelo simulador** — código real:")
        st.code(inspect.getsource(PoliticaEleitoral.chave).strip(), language="python")
        st.markdown("Inserir e chamar o próximo custam **O(log n)**: o elemento sobe ou desce no máximo a altura "
                    "da árvore, ⌊log₂ n⌋. Com 1.000 pessoas, são cerca de 10 comparações, e não 1.000.")


def _dot_lab(lab: LaboratorioFila, mudaram: set[int]) -> str:
    nos = lab.fila.array_interno()
    linhas = ["digraph heap {", 'bgcolor="transparent"; node [shape=box, style="filled", fontname="Helvetica", '
              'fontsize=11, color="#3a3d55", fontcolor="#14100a"]; edge [color="#8a86a0"];']
    for i, x in enumerate(nos):
        cor = "#e8772e" if i in mudaram else COR_CLASSE[x.chave[0]]
        linhas.append(f'n{i} [label="[{i}] {x.eleitor_id}\\nchave ({x.chave[0]}, {x.chave[1]})", fillcolor="{cor}"];')
        if i:
            linhas.append(f"n{(i - 1) // 2} -> n{i};")
    linhas.append("}")
    return "\n".join(linhas)


# ======================================================== 2. Simulação ao vivo
def barra_controle(s: SessaoSimulacao) -> None:
    m = s.motor
    c = st.columns([1, 1.4, 1, 1.4], gap="small")
    if s.rodando:
        if c[0].button("⏸ Pausar", width="stretch", key="ctl_pausar"):
            s.pausar()
            st.rerun()
    elif c[0].button("▶ Iniciar", width="stretch", key="ctl_iniciar", disabled=m.concluida, type="primary"):
        s.iniciar()
        st.rerun()
    if c[1].button("⏭ Próxima chamada", width="stretch", key="ctl_chamada", disabled=m.concluida,
                   help="Avança até o algoritmo tirar a próxima pessoa da fila e para ali."):
        s.avancar_ate_chamada()
        st.rerun()
    if c[2].button("⏭ 1 evento", width="stretch", key="ctl_evento", disabled=m.concluida,
                   help="Processa exatamente um evento da agenda (chegada, fim de etapa, incidente)."):
        s.avancar_um()
        st.rerun()
    if c[3].button("⟳ Recomeçar demo", width="stretch", key="ctl_demo",
                   help="Cenário fixo da apresentação: demo_7min, seed 2026, regras eleitorais."):
        s.carregar_demo()
        st.rerun()
    estado = "rodando" if s.rodando else ("concluída" if m.concluida else "pausada")
    st.markdown(f"Relógio simulado **{m.hora()}** ({estado}) — **{len(m.secao.fila)}** pessoa(s) na fila — "
                f"política: *{m.politica.nome}* — cenário `{m.config.cenario}`, seed `{m.config.seed}`")


def visao_ao_vivo(s: SessaoSimulacao, prefs: dict) -> None:
    st.html(ESTILO)
    m = s.motor
    barra_controle(s)
    ultima = cartao(explicar_ultima_chamada(m), "Ainda ninguém foi chamado. Use ▶ Iniciar ou ⏭ Próxima chamada.")
    proximo = cartao(explicar_proximo(m))
    if prefs.get("apresentacao"):  # projetor: cena e explicação lado a lado, numa tela só
        col_cena, col_txt = st.columns([3, 2], gap="medium")
        with col_txt:
            st.html(ultima)
            st.html(proximo)
    else:
        k1, k2 = st.columns(2, gap="medium")
        k1.html(ultima)
        k2.html(proximo)
        col_cena = st.container()
    with col_cena:
        clicado = cena_8bit(montar_cena(m, s.selecionado), som=prefs["som"], reduzido=prefs["reduzido"],
                            transicao_ms=int(TICK_S * 1000), dialogos=prefs.get("dialogos", False))
    if clicado and clicado != st.session_state.get("_ultimo_clique"):
        st.session_state["_ultimo_clique"] = clicado
        s.selecionado = clicado

    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.markdown("**Como ler a cena**")
        st.markdown("1. Quem chega entra pela rua e vai para a fila do corredor (ou senta, se tiver preferência).\n"
                    "2. O selo **▼ PRÓXIMO** fica sobre quem a política chamará quando a mesa liberar.\n"
                    "3. Ao ser chamado, aparece **CHAMADO!** — ou **PASSOU À FRENTE!** se alguém que chegou antes "
                    "ficou para trás.\n"
                    "4. Mesa (identificação) → cabine com a urna → comprovante → saída.")
    with c2:
        st.markdown(f"**Quem está esperando** — ordem em que serão chamados ({len(m.secao.fila)} no total)")
        linhas = resumo_fila(m, 8)
        if not linhas:
            st.caption("Fila vazia.")
        else:
            st.html('<ol class="s8-lista">' + "".join(
                f'<li><span>{r["pos"]}º</span><span class="tag" style="background:{COR_CLASSE[_classe(r)]}">'
                f'{escape(r["icone"] if r["icone"] != "—" else "comum")}</span><span>{escape(r["pessoa"])}</span>'
                f'<span class="m">chegou {r["chegou"]} · {r["espera"]:.0f} min</span></li>' for r in linhas) + "</ol>")
            if len(m.secao.fila) > 8:
                st.caption(f"…e mais {len(m.secao.fila) - 8}. A lista completa está na visão 3.")
        st.caption("Ordem projetada agora, sem contar quem ainda vai chegar.")

    with st.expander("Detalhes de uma pessoa e texto acessível completo da cena"):
        d1, d2 = st.columns([2, 3], gap="medium")
        with d1:
            abas._detalhes_selecionado(s)
        with d2:
            st.dataframe(abas._tabela_posicoes(m), hide_index=True, width="stretch", height=260)


def _classe(linha: dict) -> int:
    return {"80+": 0, "P": 1, "D": 2}.get(linha["icone"], 3)


# ===================================================== 3. Como o algoritmo decide
def visao_algoritmo(s: SessaoSimulacao) -> None:
    st.html(ESTILO)
    m = s.motor
    barra_controle(s)
    st.html('<div class="s8-camada" aria-label="Três estruturas, três papéis">'
            "<div><b>Fila de eleitores (heap)</b>Decide <i>quem</i> é chamado. Chave = (nível, chegada, seq).</div>"
            "<div><b>Agenda de eventos (outra heap)</b>Decide <i>quando</i> algo acontece: chegada, fim da votação, "
            "incidente.</div>"
            "<div><b>Política</b>Calcula a chave. Real: regras eleitorais. Laboratório: aging e cotas.</div></div>")
    t1, t2, t3, t4, t5 = st.tabs(["Chave e política", "Heap agora: array × atendimento", "Agenda de eventos",
                                  "Código em execução", "Complexidade"])
    with t1:
        pol = m.politica
        if pol.experimental:
            st.warning("Política de LABORATÓRIO: hipótese acadêmica para discutir starvation. "
                       "Não é procedimento eleitoral autorizado.")
        st.markdown(f"**Política ativa:** {pol.nome} · versão `{pol.versao}`")
        st.markdown(f"**Fórmula:** {pol.formula()}")
        st.code(inspect.getsource(type(pol).chave).strip(), language="python")
        st.markdown("| Nível | Quem | Base |\n|---|---|---|\n"
                    "| 0 | mais de 80 anos | art. 129, § 3º (precedência sobre as demais) |\n"
                    "| 1 | demais preferências (60+, PcD, gestante, lactante, criança de colo…) | art. 129, § 2º, I–XIV |\n"
                    "| 2 | doador(a) com comprovante ≤ 120 dias | art. 129, § 5º |\n"
                    "| 3 | sem preferência | ordem de chegada |")
        st.caption("Dentro do mesmo nível, desempata a hora de chegada e, se empatar, a sequência de chegada.")
    with t2:
        _heap_agora(m)
    with t3:
        st.markdown("A agenda é **outra** heap mínima, ordenada por (instante, tipo, sequência). Ela não escolhe "
                    "pessoas: só diz qual é o próximo acontecimento no tempo simulado.")
        st.dataframe(pd.DataFrame([{"instante": m.hora(ev.instante), "tipo": ev.tipo.name, "seq": ev.seq,
                                    "detalhe": ev.descricao()} for ev in m.estado.agenda.pendentes(12)]),
                     hide_index=True, width="stretch")
    with t4:
        abas.aba_codigo(s)
    with t5:
        st.markdown(abas._TABELA_COMPLEXIDADE)
        st.markdown("Por que O(log n): a heap é uma árvore binária completa; com n pessoas ela tem altura "
                    "⌊log₂ n⌋. Inserir sobe no máximo essa altura; extrair desce no máximo essa altura.")


def _heap_agora(m) -> None:
    fila, eleitores = m.secao.fila, m.secao.eleitores
    if not len(fila):
        st.info("A fila está vazia agora. Avance a simulação (⏭ Próxima chamada) para ver a heap com pessoas.")
        return
    st.markdown("À esquerda, o array **como está na memória**. À direita, a **ordem em que serão chamados** "
                "(uma cópia ordenada pela política, sem mexer na heap). Compare: não são a mesma lista.")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.dataframe(pd.DataFrame([
            {"índice": i, "pai": str((i - 1) // 2) if i else "— (raiz)", "eleitor": x.eleitor_id,
             "nível": eleitores[x.eleitor_id].classe.icone or "comum", "chave": str(abas._fmt_chave(x.chave))}
            for i, x in enumerate(fila.array_interno())]), hide_index=True, width="stretch", height=320)
    with c2:
        st.dataframe(pd.DataFrame([
            {"posição": i + 1, "eleitor": x.eleitor_id, "nível": eleitores[x.eleitor_id].classe.icone or "comum",
             "chegada": m.hora(eleitores[x.eleitor_id].chegada)[:5],
             "espera (min)": round(eleitores[x.eleitor_id].espera(m.agora), 1), "chave": str(abas._fmt_chave(x.chave))}
            for i, x in enumerate(m.prever_atendimento())]), hide_index=True, width="stretch", height=320)
    with st.expander("Árvore da heap (até 31 nós)", expanded=len(fila) <= 15):
        st.graphviz_chart(abas._dot_heap(fila, eleitores))


# ===================================================== 4. Resultados e auditoria
def visao_resultados(s: SessaoSimulacao) -> None:
    st.html(ESTILO)
    st.html('<div class="s8-camada" aria-label="O que é regra, o que é hipótese">'
            "<div><b>Regra eleitoral real</b>Prioridades do art. 129 (80+, preferências, doadores). É o que a "
            "simulação aplica por padrão.</div>"
            "<div><b>Hipótese acadêmica</b>Metas de espera (SLA) e limiar de starvation. Servem para medir; não são "
            "prazos legais.</div>"
            "<div><b>Laboratório</b>Aging e cotas. Mostram como reduzir a espera dos comuns; não são permitidos "
            "pela regra real.</div></div>")
    t1, t2, t3, t4 = st.tabs(["Métricas e SLA", "Starvation e políticas", "Auditoria SQL", "Regras e documentos"])
    with t1:
        abas.metricas_sla(s)
    with t2:
        abas.comparacao_politicas(s)
    with t3:
        abas.aba_auditoria(s)
    with t4:
        abas.aba_regras()
