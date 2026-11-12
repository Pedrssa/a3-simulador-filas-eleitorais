"""Conteúdo das seis abas. Tudo aqui só LÊ o motor ou chama sua API pública."""

from __future__ import annotations

import html
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from secao8bit import AVISO_ACADEMICO
from secao8bit.application.cena import montar_cena
from secao8bit.application.comparacao import comparar
from secao8bit.application.metricas import servico_para
from secao8bit.application.rastreamento import PONTOS, PassoRastreado, ReferenciaCodigo
from secao8bit.domain.eleitor import EstadoEleitor
from secao8bit.domain.fila import FilaPrioridade
from secao8bit.infrastructure.exportador_sql import exportar_logs, salvar, validar_importacao
from secao8bit.infrastructure.repositorio_sqlite import SCHEMA
from secao8bit.ui.componente import cena_8bit
from secao8bit.ui.sessao import RAIZ, TICK_S, SessaoSimulacao

DOCS = RAIZ / "docs"


def _num(v, casas=1) -> str:
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{casas}f}"


# =================================================================== A. cena
def aba_simulacao(s: SessaoSimulacao, prefs: dict) -> None:
    m = s.motor
    if prefs["apresentacao"]:
        col_cena, col_codigo = st.columns([7, 3], gap="medium")  # 7/10 da largura: Canvas em escala 2x
    else:
        col_cena, col_codigo = st.container(), None
    with col_cena:
        clicado = cena_8bit(montar_cena(m, s.selecionado), som=prefs["som"], reduzido=prefs["reduzido"],
                            transicao_ms=int(TICK_S * 1000))
        if clicado and clicado != st.session_state.get("_ultimo_clique"):
            st.session_state["_ultimo_clique"] = clicado
            s.selecionado = clicado
        st.caption("Ícones: **80+** mais de 80 anos · **P** preferência (art. 129, § 2º, I–XIV) · "
                   "**D** doador(a) com comprovante · **A** acompanhante · **#n** senha após 17h · "
                   "**!** espera acima do limiar de starvation. Clique numa pessoa para ver os detalhes.")
    if col_codigo is not None:
        with col_codigo:
            st.markdown("**Último passo do algoritmo**")
            algoritmicos = [p for p in m.rastreador.passos if p.ponto != "auditoria"]
            if algoritmicos:
                _mostrar_passo(algoritmicos[-1], compacto=True)

    c1, c2 = st.columns([2, 3], gap="medium")
    with c1:
        _detalhes_selecionado(s)
    with c2:
        st.markdown("**Quem está onde (texto acessível da cena)**")
        st.dataframe(_tabela_posicoes(m), hide_index=True, width="stretch", height=260)


def _detalhes_selecionado(s: SessaoSimulacao) -> None:
    m = s.motor
    ativos = [e for e in m.secao.eleitores.values() if not e.finalizado or e.id == s.selecionado]
    opcoes = [None] + [e.id for e in ativos]
    idx = opcoes.index(s.selecionado) if s.selecionado in opcoes else 0
    escolha = st.selectbox("Selecionar pessoa", opcoes, index=idx,
                           format_func=lambda x: "— ninguém —" if x is None else f"{x} · {m.secao.eleitores[x].apelido}")
    s.selecionado = escolha
    if not escolha:
        st.info("Selecione uma pessoa na lista ou clique nela na cena.")
        return
    e = m.secao.eleitores[escolha]
    st.markdown(f"**{e.id}** — {e.apelido} *(fictício)*")
    st.markdown(
        f"- Chegada: **{m.hora(e.chegada)}** ({e.origem})\n"
        f"- Estado: **{e.estado.value}**\n"
        f"- Espera até o atendimento: **{e.espera(m.agora):.1f} min**"
        f"{' (ainda aguardando)' if e.inicio_atendimento is None and not e.finalizado else ''}\n"
        f"- Classe: **{e.classe.rotulo}** {('[' + e.classe.icone + ']') if e.classe.icone else ''}\n"
        f"- Fundamento: {e.classificacao.texto}\n"
        f"- Ultrapassado(a) por quem chegou depois: **{e.ultrapassado_por}** vez(es)"
        + (f"\n- Saída: {e.motivo_saida}" if e.motivo_saida else "")
    )
    st.markdown(f"**Por que está nesta posição?** {_justificar_posicao(m, e)}")


def _justificar_posicao(m, e) -> str:
    if e.estado != EstadoEleitor.AGUARDANDO:
        return "Já saiu da fila de prioridade; o registro SAIDA_FILA na auditoria traz a justificativa da chamada."
    ordem = m.prever_atendimento()
    pos = next(i for i, x in enumerate(ordem) if x.eleitor_id == e.id)
    minha = ordem[pos].chave
    if m.estado.encerrado:
        return f"Recebeu a senha {e.senha}; a chamada segue a ordem decrescente das senhas (art. 160, § 3º)."
    if m.politica.experimental:
        return (f"Posição projetada **{pos + 1}º** de {len(ordem)} pela política "
                f"**{m.politica.nome}**, considerando cotas e aging no instante atual. "
                "Novas chegadas e o avanço do tempo podem alterar esta projeção.")
    melhores = sum(1 for x in ordem[:pos] if x.chave[0] < minha[0])
    mesmas = pos - melhores
    return (f"Está em **{pos + 1}º** de {len(ordem)} com chave {tuple(round(v, 1) if isinstance(v, float) else v for v in minha)}. "
            f"À frente: {melhores} pessoa(s) de nível de prioridade melhor e {mesmas} do mesmo nível que chegaram antes "
            f"({m.politica.nome}).")


def _tabela_posicoes(m) -> pd.DataFrame:
    ordem = {x.eleitor_id: i + 1 for i, x in enumerate(m.prever_atendimento())}
    linhas = []
    for e in m.secao.eleitores.values():
        if e.finalizado:
            continue
        linhas.append({"ID": e.id, "onde": e.estado.value, "posição na fila": ordem.get(e.id),
                       "prioridade": e.classe.rotulo, "chegada": m.hora(e.chegada)[:5],
                       "espera (min)": round(e.espera(m.agora), 1)})
    for cargo, integ in m.secao.mesa.items():
        linhas.append({"ID": cargo.value, "onde": integ.ocupado_com_incidente or "no posto", "posição na fila": None,
                       "prioridade": "—", "chegada": "—", "espera (min)": None})
    for p in m.secao.apoio.values():
        linhas.append({"ID": p.rotulo, "onde": p.zona, "posição na fila": None, "prioridade": "—",
                       "chegada": "—", "espera (min)": None})
    df = pd.DataFrame(linhas)
    return df.sort_values("posição na fila", na_position="first") if not df.empty else df


# ================================================================= B. código
def _bloco_codigo(ref: ReferenciaCodigo, destacar: bool = True, max_linhas: int = 40) -> str:
    linhas = ref.linhas_fonte()
    if not linhas:
        return "<em>Código-fonte indisponível.</em>"
    alvo = ref.linha_destacada - ref.primeira_linha if destacar else -1
    ini = max(0, min(alvo - max_linhas // 2, len(linhas) - max_linhas)) if alvo >= 0 else 0
    trecho = linhas[ini:ini + max_linhas]
    out = []
    for i, linha in enumerate(trecho, start=ini):
        n = ref.primeira_linha + i
        estilo = "background:#ffe58a;color:#1a1208;font-weight:bold;" if i == alvo else ""
        marca = "▶" if i == alvo else " "
        out.append(f'<div style="{estilo}white-space:pre;"><span style="opacity:.6">{marca}{n:>4} </span>'
                   f"{html.escape(linha.rstrip())}</div>")
    return ('<div role="region" aria-label="Código-fonte real" style="font-family:Consolas,monospace;font-size:12.5px;'
            'background:#15151f;color:#e8e6e0;padding:8px;border-radius:6px;overflow-x:auto;">' + "".join(out) + "</div>")


def _mostrar_passo(p: PassoRastreado, compacto: bool = False) -> None:
    st.markdown(f"`#{p.n}` · **{p.hora}** · evento **{p.evento}** → ponto *{PONTOS[p.ponto]}*")
    st.markdown(f"`{p.codigo.arquivo_relativo}:{p.codigo.linha_destacada}` · método **`{p.codigo.funcao}`**")
    st.markdown(f"**Antes:** {p.antes or '—'}  \n**Depois:** {p.depois or '—'}  \n"
                f"**Na animação:** {p.animacao or '—'}  \n**Explicação:** {p.explicacao}")
    st.html(_bloco_codigo(p.codigo, max_linhas=14 if compacto else 40))
    if not compacto:
        st.markdown("**Variáveis relevantes**")
        st.json(p.variaveis, expanded=True)
        if p.referencia:
            with st.expander(f"Método chamado: {p.referencia.funcao} ({p.referencia.arquivo_relativo})", expanded=True):
                st.html(_bloco_codigo(p.referencia, destacar=False, max_linhas=60))


def aba_codigo(s: SessaoSimulacao) -> None:
    r = s.motor.rastreador
    st.info("Rastreamento por **pontos instrumentados**: cada passo mostra o arquivo, o método e a linha real "
            "de onde `Rastreador.ponto()` foi chamado. Não é uma execução linha a linha do interpretador. "
            "O código exibido é lido dos arquivos do projeto; nada digitado aqui é executado.")
    if not r.passos:
        st.write("Nenhum passo ainda. Use **Avançar 1 evento** ou **Iniciar**.")
        return
    c1, c2 = st.columns([1, 2])
    with c1:
        filtro = st.multiselect("Filtrar pontos", list(PONTOS), format_func=PONTOS.get)
        passos = [p for p in r.passos if not filtro or p.ponto in filtro]
        if not passos:
            st.write("Nenhum passo com esse filtro.")
            return
        rotulos = {p.n: f"#{p.n} {p.hora} · {PONTOS[p.ponto]} · {p.evento}" for p in passos}
        n = st.selectbox("Passo", list(reversed(list(rotulos))), format_func=rotulos.get)
        st.caption(f"{r.total} passos registrados nesta execução (mostrando os últimos {len(r.passos)}).")
        st.dataframe(pd.DataFrame([{"#": p.n, "hora": p.hora, "ponto": PONTOS[p.ponto], "método": p.codigo.funcao}
                                   for p in reversed(passos[-30:])]), hide_index=True, width="stretch")
    with c2:
        _mostrar_passo(next(p for p in passos if p.n == n))


# ================================================================== C. filas
def aba_filas(s: SessaoSimulacao) -> None:
    m = s.motor
    pol = m.politica
    if pol.experimental:
        st.warning("Política EXPERIMENTAL de laboratório: sem validade como procedimento eleitoral.")
    st.markdown(f"**Política ativa:** {pol.nome} · versão `{pol.versao}`")
    st.markdown(f"**Fórmula:** {pol.formula()}")
    if pol.parametros():
        st.json(pol.parametros())
    fila = m.secao.fila
    eleitores = m.secao.eleitores
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Array interno da heap** (ordem física; só garante pai ≤ filhos)")
        st.dataframe(pd.DataFrame([
            {"índice": i, "pai": (i - 1) // 2 if i else None, "eleitor": x.eleitor_id,
             "classe": eleitores[x.eleitor_id].classe.rotulo, "chave": str(_fmt_chave(x.chave))}
            for i, x in enumerate(fila.array_interno())]), hide_index=True, width="stretch", height=320)
    with c2:
        st.markdown("**Projeção de atendimento** (política ativa no instante atual)")
        st.dataframe(pd.DataFrame([
            {"posição": i + 1, "eleitor": x.eleitor_id, "classe": eleitores[x.eleitor_id].classe.rotulo,
             "chegada": m.hora(eleitores[x.eleitor_id].chegada)[:8],
             "espera (min)": round(eleitores[x.eleitor_id].espera(m.agora), 1), "chave": str(_fmt_chave(x.chave))}
            for i, x in enumerate(m.prever_atendimento())]), hide_index=True, width="stretch", height=320)
    st.caption("Projeção sem novas chegadas e sem avanço de tempo; considera o estado das cotas. "
               "A heap física ao lado permanece inalterada. Cotas podem exigir O(n²) para projetar toda a fila.")
    if len(fila):
        st.markdown("**Árvore da heap** (até 31 nós)")
        st.graphviz_chart(_dot_heap(fila, eleitores))
    st.markdown("**Agenda de eventos futuros** — outra heap, ordenada por (instante, tipo, sequência). "
                "Ela decide *quando* algo acontece; a fila acima decide *quem* é chamado.")
    st.dataframe(pd.DataFrame([{"instante": m.hora(ev.instante), "tipo": ev.tipo.name, "seq": ev.seq,
                                "detalhe": ev.descricao()} for ev in m.estado.agenda.pendentes(12)]),
                 hide_index=True, width="stretch")
    st.markdown("**Complexidades** (n = pessoas na fila)")
    st.markdown(_TABELA_COMPLEXIDADE)
    st.info("Prioridade estrita não garante espera limitada: se o fluxo com preferência for maior que a capacidade "
            "da urna por tempo prolongado, quem não tem preferência pode esperar indefinidamente (starvation). "
            "No modo eleitoral isso é monitorado e mitigado operacionalmente (substituto na identificação, técnico "
            "de prontidão), sem promover ninguém acima de uma preferência legal.")


_TABELA_COMPLEXIDADE = """
| Operação | Custo | Onde |
|---|---|---|
| inserir na fila | O(log n) | `FilaPrioridade.inserir` (heappush) |
| chamar o próximo | O(log n) | `FilaPrioridade.extrair_minimo` (heappop) |
| atualizar chaves no aging | O(n) | `FilaPrioridade.reconstruir` (heapify) antes de cada chamada |
| cota (procurar comum mais antigo) | O(n) | `FilaPrioridade.extrair_onde` |
| agendar / próximo evento | O(log m) | `AgendaEventos` (m = eventos futuros) |
| ordem efetiva para exibição | O(n log n) | `FilaPrioridade.ordem_efetiva` |
"""


def _fmt_chave(chave):
    return tuple(round(v, 2) if isinstance(v, float) else v for v in chave)


def _dot_heap(fila: FilaPrioridade, eleitores) -> str:
    nos = fila.array_interno()[:31]
    linhas = ["digraph heap {", 'node [shape=box, fontname="Courier", fontsize=10];']
    for i, x in enumerate(nos):
        e = eleitores[x.eleitor_id]
        linhas.append(f'n{i} [label="[{i}] {x.eleitor_id}\\n{e.classe.icone or "comum"} {_fmt_chave(x.chave)}"];')
        if i:
            linhas.append(f"n{(i - 1) // 2} -> n{i};")
    linhas.append("}")
    return "\n".join(linhas)


# ================================================================ D. métricas
def aba_metricas(s: SessaoSimulacao) -> None:
    metricas_sla(s)
    st.divider()
    comparacao_politicas(s)


def metricas_sla(s: SessaoSimulacao) -> None:
    m, cfg = s.motor, s.motor.config
    met = servico_para(cfg)
    r = met.resumo(m)
    st.caption(f"Metas acadêmicas (HIPÓTESES, não garantias legais): espera ≤ {cfg.sla_prioritarios_min:g} min "
               f"para quem tem preferência e ≤ {cfg.sla_comuns_min:g} min para os demais; alerta de starvation a "
               f"partir de {cfg.limiar_starvation_min:g} min. Quando a carga excede a capacidade, nenhuma meta é garantida.")
    k = st.columns(6)
    k[0].metric("Na fila", r["na_fila"], help=f"Maior fila: {r['maior_fila']}")
    k[1].metric("Concluídos", r["concluidos"])
    k[2].metric("Vazão (pessoas/h)", _num(r["vazao_h"]))
    k[3].metric("Espera p95 (min)", _num(r["espera_p95"]), help="Inclui quem ainda espera (censurado)")
    k[4].metric("Violações de SLA", r["violacoes_sla"])
    k[5].metric("Alertas starvation", r["alertas_starvation"])
    with st.expander("Mais indicadores"):
        k = st.columns(3)
        k[0].metric("Espera média (min)", _num(r["espera_media"]))
        k[1].metric("Espera máxima (min)", _num(r["espera_max"]))
        k[2].metric("Tempo no sistema (min)", _num(r["tempo_sistema_medio"]))
        k = st.columns(3)
        k[0].metric("Ocupação da urna", f"{r['ocupacao_urna']:.0%}")
        k[1].metric("Urna indisponível (min)", _num(r["indisponibilidade_urna_min"]))
        k[2].metric("Encaminhados / não admitidos", f"{r['encaminhados']} / {r['nao_admitidos']}")

    eleitores = list(m.secao.eleitores.values())
    st.markdown("**Espera por grupo** (min) — colunas 'incl.' contam quem ainda espera com a espera até agora")
    st.dataframe(pd.DataFrame(met.por_grupo(eleitores, m.agora)).round(1), hide_index=True, width="stretch")
    alertas = met.alertas_starvation(eleitores, m.agora)
    if alertas:
        st.error(f"{len(alertas)} pessoa(s) esperando há mais de {cfg.limiar_starvation_min:g} min.")
        st.dataframe(pd.DataFrame(alertas), hide_index=True, width="stretch")
    if m.estado.serie_fila:
        serie = pd.DataFrame(m.estado.serie_fila, columns=["min", "fila"])
        serie["hora"] = serie["min"].map(lambda t: m.hora(t)[:5])
        st.markdown("**Tamanho da fila ao longo do tempo simulado**")
        st.line_chart(serie, x="min", y="fila", height=200)


def comparacao_politicas(s: SessaoSimulacao) -> None:
    cfg = s.motor.config
    st.markdown("### Comparação de políticas com a mesma carga")
    st.caption("Cada variante recebe exatamente as mesmas chegadas, perfis, durações e incidentes (mesmos fluxos "
               "pseudoaleatórios da seed). A assinatura da carga abaixo prova isso.")
    chave = (cfg.cenario, cfg.seed)
    if st.button("Rodar comparação", key="btn_comparar"):
        with st.spinner("Simulando variantes…"):
            s.comparacao[chave] = comparar(cfg.com(politica="eleitoral", politica_params={},
                                                   designar_substituto=False, tecnico_de_prontidao=False))
    res = s.comparacao.get(chave)
    if res:
        linhas = []
        for rr in res:
            g = {x["grupo"]: x for x in rr.grupos}
            linhas.append({
                "variante": rr.nome, "versão": rr.politica_versao,
                "comum: máx (min)": g["Comum"]["máximo (incl.)"], "comum: p95": g["Comum"]["p95 (incl.)"],
                "preferencial: máx": g["Preferencial"]["máximo (incl.)"],
                "doador: máx": g["Doador(a) de sangue"]["máximo (incl.)"],
                "80+: máx": g["Mais de 80 anos"]["máximo (incl.)"],
                "violações SLA": rr.resumo["violacoes_sla"], "concluídos": rr.resumo["concluidos"],
                "assinatura da carga": str(rr.assinatura_carga),
            })
        df = pd.DataFrame(linhas)
        st.dataframe(df.round(1), hide_index=True, width="stretch")
        st.bar_chart(df, x="variante", y=["comum: máx (min)", "preferencial: máx", "doador: máx"], stack=False,
                     height=260)
        st.info("Leitura: o aging limita a espera dos comuns às custas de mais espera para preferenciais; as cotas "
                "ajudam os comuns, mas podem deslocar a espera para doadores (não atendidos pela cota). "
                "Nenhuma política elimina starvation em qualquer carga: se a demanda total supera a capacidade da "
                "única urna, alguém espera mais. Políticas LAB não têm validade eleitoral.")


# ================================================================ E. auditoria
def aba_auditoria(s: SessaoSimulacao) -> None:
    m, repo = s.motor, s.repo
    if m.ultimo_erro:
        st.error(m.ultimo_erro)
    st.markdown(f"Execução **`{m.execucao_id}`** · banco `{Path(repo.caminho).name}` · "
                f"{repo.total_eventos(m.execucao_id)} registros persistidos (motor: {len(m.log)})")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.dataframe(pd.DataFrame(repo.contagem_por_tipo(m.execucao_id)), hide_index=True, width="stretch")
        if st.button("Verificar cadeia de hash", key="btn_hash"):
            s.resultados[("hash", m.execucao_id)] = repo.verificar_integridade(m.execucao_id)
        if ("hash", m.execucao_id) in s.resultados:
            ok, msg = s.resultados[("hash", m.execucao_id)]
            (st.success if ok else st.error)(f"Cadeia de hash: {msg}")
        st.caption("O hash encadeado detecta alteração/remoção isolada. Sozinho, não impede quem controla todo o "
                   "banco de reescrever o histórico inteiro e recalcular os hashes.")
    with c2:
        tipos = [None] + [x["tipo"] for x in repo.contagem_por_tipo(m.execucao_id)]
        f1, f2 = st.columns(2)
        tipo = f1.selectbox("Tipo", tipos, format_func=lambda x: "todos" if x is None else x)
        eleitor = f2.text_input("ID do eleitor (ex.: E-0003)", max_chars=12).strip() or None
        linhas = repo.eventos(m.execucao_id, tipo, eleitor, limite=300)  # consulta parametrizada
        df = pd.DataFrame(linhas)
        if not df.empty:
            df = df[["seq", "hora_simulada", "eleitor_id", "tipo", "estado_anterior", "estado_posterior",
                     "justificativa", "politica_versao", "dados_json", "hash"]]
        st.dataframe(df, hide_index=True, width="stretch", height=360)

    st.markdown("**Exportação**")
    sql = exportar_logs(repo, m.execucao_id)
    e1, e2, e3, e4 = st.columns(4)
    e1.download_button("Baixar logs.sql", sql, file_name="logs.sql", mime="application/sql")
    e2.download_button("Baixar schema.sql", SCHEMA.read_text(encoding="utf-8"), file_name="schema.sql",
                       mime="application/sql")
    met = servico_para(m.config)
    csv = pd.DataFrame(met.por_grupo(list(m.secao.eleitores.values()), m.agora)).to_csv(index=False)
    e3.download_button("Baixar métricas.csv", csv, file_name="metricas.csv", mime="text/csv")
    if e4.button("Validar importação", key="btn_validar"):
        s.resultados[("validacao", m.execucao_id)] = (
            validar_importacao(repo, m.execucao_id, sql), salvar(RAIZ / "exports" / "logs.sql", sql))
    if ("validacao", m.execucao_id) in s.resultados:
        r, destino = s.resultados[("validacao", m.execucao_id)]
        (st.success if r["ok"] else st.error)(
            f"Importação em banco vazio: {'OK' if r['ok'] else 'FALHOU'} — " +
            ", ".join(f"{k}: {v['importado']}/{v['original']}" for k, v in r.items() if isinstance(v, dict)) +
            f"; violações de FK: {r['violacoes_fk']}. Cópia salva em {destino.relative_to(RAIZ)} "
            "(validada no momento do clique; clique de novo após avançar a simulação).")


# ================================================================ F. regras
def aba_regras() -> None:
    st.info(AVISO_ACADEMICO)
    docs = {
        "Regras eleitorais e rastreabilidade": "regras_eleitorais.md",
        "Relatório técnico": "relatorio_tecnico.md",
        "Matriz de requisitos do enunciado": "matriz_requisitos.md",
        "Eventos e incidentes": "eventos.md",
        "Dicionário de classes e UML": "dicionario_e_uml.md",
        "Testes e evidências": "testes.md",
        "Roteiro de apresentação": "roteiro_apresentacao.md",
        "Ferramentas de desenvolvimento": "ferramentas.md",
    }
    nome = st.selectbox("Documento", list(docs))
    caminho = DOCS / docs[nome]
    if caminho.exists():
        st.markdown(caminho.read_text(encoding="utf-8"))
    else:
        st.warning(f"Arquivo {caminho.name} não encontrado em docs/.")


