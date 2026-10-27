"""SEÇÃO 8-BIT — Simulador de Filas Eleitorais (ponto de entrada Streamlit).

Execute:  streamlit run app.py
"""

from __future__ import annotations

from html import escape

import streamlit as st

from secao8bit import AVISO_ACADEMICO
from secao8bit.application.config import CENARIOS, config_do_cenario
from secao8bit.application.motor import TIPOS_INCIDENTE
from secao8bit.domain.politicas import POLITICAS_DISPONIVEIS
from secao8bit.ui import abas
from secao8bit.ui.sessao import TICK_S, obter_sessao

st.set_page_config(page_title="SEÇÃO 8-BIT — Simulador de Filas Eleitorais", page_icon="🗳️", layout="wide",
                   initial_sidebar_state="expanded")

s = obter_sessao(st)
m = s.motor

TIPOS_ELEITOR = {
    "comum": "Sem preferência", "mais_de_80": "Mais de 80 anos", "idade_60": "60 anos ou mais",
    "deficiencia": "Pessoa com deficiência", "mobilidade": "Mobilidade reduzida", "gestante": "Gestante",
    "lactante": "Lactante", "crianca_colo": "Com criança de colo", "tea": "Pessoa com TEA",
    "obesidade": "Pessoa obesa", "enfermidade": "Pessoa enferma", "seguranca": "Agente de segurança em serviço",
    "doador": "Doador(a) com comprovante",
}

# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.title("SEÇÃO 8-BIT")
    st.caption(AVISO_ACADEMICO)

    st.subheader("Execução")
    c1, c2 = st.columns(2)
    if s.rodando:
        if c1.button("⏸ Pausar", width="stretch"):
            s.pausar()
            st.rerun()
    elif c1.button("▶ Iniciar", width="stretch", disabled=m.concluida):
        s.iniciar()
        st.rerun()
    if c2.button("⏭ Avançar 1 evento", width="stretch", disabled=m.concluida):
        s.avancar_um()
    s.velocidade = st.select_slider("Velocidade (min simulados por segundo)", [0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0],
                                    value=s.velocidade)

    st.subheader("Cenário")
    cenario = st.selectbox("Cenário", list(CENARIOS), index=list(CENARIOS).index(s.config.cenario),
                           help="\n".join(f"{k}: {v[0]}" for k, v in CENARIOS.items()))
    st.caption(CENARIOS[cenario][0])
    seed_padrao = s.config.seed if cenario == s.config.cenario else CENARIOS[cenario][1].seed
    seed = st.number_input("Seed", min_value=0, max_value=10**9, value=int(seed_padrao), step=1,
                           key=f"seed_{cenario}")
    politica = st.selectbox("Política", list(POLITICAS_DISPONIVEIS), format_func=POLITICAS_DISPONIVEIS.get,
                            index=list(POLITICAS_DISPONIVEIS).index(s.config.politica))
    params: dict = {}
    if politica == "aging":
        params["intervalo_min"] = float(st.slider("Intervalo de aging (min)", 5, 40,
                                                  int(s.config.politica_params.get("intervalo_min", 15))))
    elif politica == "cotas":
        params["k"] = int(st.slider("Cota: 1 comum a cada k preferenciais", 1, 8, int(s.config.politica_params.get("k", 3))))
    with st.expander("Mitigação operacional (modo eleitoral)"):
        subst = st.checkbox("Presidente designa mesário para identificar durante ocorrências (art. 126)",
                            value=s.config.designar_substituto)
        prontidao = st.checkbox("Técnico de urna de prontidão (chega em 3–6 min)", value=s.config.tecnico_de_prontidao)
    if st.button("⟲ Reiniciar com estas opções", type="primary", width="stretch"):
        base = config_do_cenario(cenario)
        s.reiniciar(base.com(seed=int(seed), politica=politica, politica_params=params,
                             designar_substituto=subst, tecnico_de_prontidao=prontidao))
        st.rerun()
    if politica != s.config.politica or params != s.config.politica_params:
        if st.button("Trocar política agora (sem reiniciar)", width="stretch"):
            s.executar(lambda: s.motor.trocar_politica(politica, **params))
            st.toast("Mudança registrada na auditoria (POLITICA_ALTERADA).")

    st.subheader("Interações")
    with st.form("inserir", border=False):
        tipo = st.selectbox("Inserir eleitor fictício", list(TIPOS_ELEITOR), format_func=TIPOS_ELEITOR.get)
        if st.form_submit_button("Inserir agora", width="stretch"):
            s.executar(lambda: s.motor.inserir_manual(None if tipo == "comum" else tipo))
    n_cheg = st.number_input("Gerar chegadas (quantidade)", 1, 40, 8)
    if st.button("Gerar chegadas nos próximos 10 min", width="stretch"):
        s.executar(lambda: s.motor.gerar_chegadas(int(n_cheg), 0.3, janela_min=10.0))
    incidente = st.selectbox("Disparar incidente", list(TIPOS_INCIDENTE), format_func=TIPOS_INCIDENTE.get)
    if st.button("Disparar", width="stretch"):
        s.executar(lambda: s.motor.disparar_incidente(incidente))

    st.subheader("Exibição")
    prefs = {
        "apresentacao": st.toggle("Modo apresentação (cena + código lado a lado)", value=False),
        "som": st.toggle("Som 8 bits", value=False),
        "reduzido": st.toggle("Movimento reduzido", value=False),
    }

# ------------------------------------------------------------------ painel principal
st.html("""<style>
  .block-container { padding-top: 1.6rem; max-width: 1280px; }
  .s8-topo { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; margin-bottom: 2px; }
  .s8-marca { font-family: "Source Code Pro", monospace; font-weight: 800; font-size: 1.55rem; letter-spacing: .04em;
              color: #ffd34d; }
  .s8-sub { color: #a9a5bd; font-size: .95rem; }
  .s8-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 2px; }
  .s8-chip { font: 600 .82rem/1 "Source Code Pro", monospace; padding: 5px 9px; border-radius: 999px;
             background: #1c1e2b; border: 1px solid #2c2f42; color: #ece9df; }
  .s8-chip b { color: #ffd34d; font-weight: 700; }
  .s8-chip.run { border-color: #3e8f5a; color: #7ee0a0; } .s8-chip.lab { border-color: #a0485a; color: #ff8fa3; }
  .s8-ultimo { color: #a9a5bd; font-size: .85rem; margin: 2px 0 6px; }
  [data-testid="stSidebar"] h1 { color: #ffd34d; letter-spacing: .04em; }
  [data-testid="stSidebar"] h3 { font-size: .85rem; text-transform: uppercase; letter-spacing: .08em; color: #a9a5bd;
                                 margin-top: .6rem; }
  [data-baseweb="tab-list"] button p { font-family: "Source Code Pro", monospace; font-size: .86rem; }
</style>""")


@st.fragment(run_every=TICK_S if s.rodando else None)
def painel() -> None:
    rodava = s.rodando
    s.tick()
    if rodava and not s.rodando:  # terminou ou falhou: redesenha a barra lateral (botões)
        st.rerun()
    m = s.motor
    if s.erro:
        st.error(s.erro)
    if m.politica.experimental:
        st.warning("MODO LABORATÓRIO ACADÊMICO — política experimental, sem validade como procedimento eleitoral.")
    estado = "▶ rodando" if s.rodando else ("✔ concluída" if m.concluida else "⏸ pausada")
    chips = [
        ("run" if s.rodando else "", f"<b>{escape(m.hora())}</b> {estado}"),
        ("", f"cenário <b>{escape(m.config.cenario)}</b>"),
        ("", f"seed <b>{m.config.seed}</b>"),
        ("lab" if m.politica.experimental else "", f"política <b>{escape(m.politica.nome)}</b>"),
        ("", f"eventos <b>{m.estado.eventos_processados}</b>"),
        ("", f"fila <b>{len(m.secao.fila)}</b>"),
    ]
    st.html(
        '<div class="s8-topo"><span class="s8-marca">SEÇÃO 8-BIT</span>'
        '<span class="s8-sub">Simulador de filas eleitorais · projeto acadêmico, dados fictícios</span></div>'
        '<div class="s8-chips">' + "".join(f'<span class="s8-chip {c}">{t}</span>' for c, t in chips) + "</div>"
        f'<div class="s8-ultimo">Último evento: {escape(m.estado.ultimo_evento or "—")}</div>')
    a, b, c, d, e, f = st.tabs(["A. Simulação 8 bits", "B. Código em execução", "C. Filas e algoritmo",
                                "D. Métricas e SLA", "E. Auditoria SQL", "F. Regras e documentação"])
    with a:
        abas.aba_simulacao(s, prefs)
    with b:
        abas.aba_codigo(s)
    with c:
        abas.aba_filas(s)
    with d:
        abas.aba_metricas(s)
    with e:
        abas.aba_auditoria(s)
    with f:
        abas.aba_regras()


painel()
