"""SEÇÃO 8-BIT — Simulador de Filas Eleitorais (ponto de entrada Streamlit).

Execute:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from secao8bit import AVISO_ACADEMICO
from secao8bit.application.config import CENARIOS, config_do_cenario
from secao8bit.application.motor import TIPOS_INCIDENTE
from secao8bit.domain.politicas import POLITICAS_DISPONIVEIS
from secao8bit.ui import visoes
from secao8bit.ui.sessao import TICK_S, VELOCIDADES, obter_sessao

st.set_page_config(page_title="SEÇÃO 8-BIT — Simulador de Filas Eleitorais", page_icon="🗳️", layout="wide",
                   initial_sidebar_state="auto")

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
# Só o essencial fica visível; o resto fica recolhido (divulgação progressiva).
with st.sidebar:
    st.title("SEÇÃO 8-BIT")
    st.caption(AVISO_ACADEMICO)

    if st.button("⟳ Carregar demonstração", type="primary", width="stretch",
                 help="Cenário fixo da apresentação: demo_7min, seed 2026, regras eleitorais."):
        s.carregar_demo()
        st.rerun()
    s.velocidade = st.select_slider(
        "Velocidade (× tempo real)", VELOCIDADES, value=s.velocidade if s.velocidade in VELOCIDADES else 0.25,
        format_func=lambda v: f"{v * 60:g}×",
        help="Quantas vezes mais rápido que o relógio real. 60× = 1 minuto simulado por segundo.")

    with st.expander("Cenário e política"):
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
            params["k"] = int(st.slider("Cota: 1 comum a cada k preferenciais", 1, 8,
                                        int(s.config.politica_params.get("k", 3))))
        subst = st.checkbox("Presidente designa mesário para identificar durante ocorrências (art. 126)",
                            value=s.config.designar_substituto)
        prontidao = st.checkbox("Técnico de urna de prontidão (chega em 3–6 min)", value=s.config.tecnico_de_prontidao)
        if st.button("⟲ Reiniciar com estas opções", width="stretch"):
            base = config_do_cenario(cenario)
            s.reiniciar(base.com(seed=int(seed), politica=politica, politica_params=params,
                                 designar_substituto=subst, tecnico_de_prontidao=prontidao))
            st.rerun()
        if politica != s.config.politica or params != s.config.politica_params:
            if st.button("Trocar política agora (sem reiniciar)", width="stretch"):
                if s.trocar_politica(politica, **params):
                    st.toast("Mudança registrada na auditoria (POLITICA_ALTERADA).")

    with st.expander("Provocar situações"):
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

    with st.expander("Exibição"):
        prefs = {
            "som": st.toggle("Som 8 bits", value=False),
            "reduzido": st.toggle("Movimento reduzido", value=False),
            "dialogos": st.toggle("Conversas ilustrativas na cena", value=False,
                                  help="Falas decorativas entre personagens. Não mudam a simulação."),
        }

# ------------------------------------------------------------------ painel principal
st.html("""<style>
  .block-container { padding-top: 1.4rem; max-width: 1280px; }
  .s8-topo { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; margin-bottom: 2px; }
  .s8-marca { font-family: "Source Code Pro", monospace; font-weight: 800; font-size: 1.5rem; letter-spacing: .04em;
              color: #ffd34d; }
  .s8-sub { color: #b9b5cc; font-size: .95rem; }
  [data-testid="stSidebar"] h1 { color: #ffd34d; letter-spacing: .04em; }
  :focus-visible { outline: 3px solid #ffd34d !important; outline-offset: 2px; }
</style>""")

topo1, topo2 = st.columns([5, 1.3], vertical_alignment="bottom")
with topo1:
    st.html('<div class="s8-topo"><span class="s8-marca">SEÇÃO 8-BIT</span>'
            '<span class="s8-sub">Como uma fila de prioridade decide quem vota primeiro · dados fictícios</span></div>')
    visao = st.segmented_control("Visão", list(visoes.VISOES), format_func=visoes.VISOES.get, key="visao",
                                 default="entenda", label_visibility="collapsed") or "entenda"
with topo2:
    apresentacao = st.toggle("Modo apresentação", key="modo_apresentacao",
                             help="Esconde a barra lateral e aumenta o texto, para projetor.")
prefs["apresentacao"] = apresentacao
if apresentacao:
    st.html("""<style>
      section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
      .block-container { max-width: 1500px; }
      .block-container { padding-top: .8rem; }
      .s8-decisao p, .s8-lista li { font-size: 1.1rem; }
      .s8-decisao .t { font-size: 1.2rem; }
    </style>""")


@st.fragment(run_every=TICK_S if s.rodando else None)
def painel(visao: str) -> None:
    rodava = s.rodando
    s.tick()
    if rodava and not s.rodando:  # terminou ou falhou: redesenha a página inteira (botões)
        st.rerun()
    m = s.motor
    if s.erro:
        st.error(s.erro)
    if m.politica.experimental and visao != "entenda":
        st.warning("MODO LABORATÓRIO ACADÊMICO — política experimental, sem validade como procedimento eleitoral.")
    if visao == "entenda":
        visoes.visao_entenda()
    elif visao == "ao_vivo":
        visoes.visao_ao_vivo(s, prefs)
    elif visao == "algoritmo":
        visoes.visao_algoritmo(s)
    else:
        visoes.visao_resultados(s)


painel(visao)
