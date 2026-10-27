/* SEÇÃO 8-BIT — camada de APRESENTAÇÃO (corte lateral 2D).
 * Desenha apenas o estado recebido do motor Python (args.cena): não decide quem é atendido,
 * não altera a fila e não cria ocorrências. Tempo simulado (motor) ≠ relógio da interface
 * (Streamlit) ≠ interpolação visual (este arquivo).
 */
(function () {
  "use strict";
  const W = 400, H = 225;
  const TRAS = 183, MEIO = 195, FRENTE = 207;           // faixas de profundidade (pés)
  const PORTAO_X = 83, PORTA_X = 239, SAIDA_X = 397;  // passagens entre ambientes
  const F = window.FontePixel;
  const canvas = document.getElementById("tela");
  const ctx = canvas.getContext("2d");
  const statusEl = document.getElementById("status");
  const estacoesEl = document.getElementById("estacoes");
  const listaEl = document.getElementById("lista");
  const btnSom = document.getElementById("btnSom");

  // ---------------------------------------------------------- protocolo Streamlit
  function enviar(type, extra) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, extra || {}), "*");
  }
  function ajustarAltura() { enviar("streamlit:setFrameHeight", { height: document.body.scrollHeight + 4 }); }

  let escala = 2, fundo = null, fundoMinuto = -1;
  let cena = null, somLigado = false, reduzido = false, transicaoMs = 500;
  const sprites = new Map();
  let ultimoSeqSom = -1, ultimoSeqDestaque = -1;
  const carro = { x: -70, alvo: -70 };

  window.addEventListener("message", (ev) => {
    const d = ev.data;
    if (!d || d.type !== "streamlit:render") return;
    const a = d.args || {};
    somLigado = !!a.som;
    reduzido = !!a.reduzido || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    transicaoMs = Math.max(150, a.transicao_ms || 500);
    redimensionar();
    receber(a.cena);
    btnSom.hidden = !(somLigado && (!audio || audio.state !== "running"));
    ajustarAltura();
  });
  enviar("streamlit:componentReady", { apiVersion: 1 });

  // ---------------------------------------------------------------- posições
  const POS = {
    identificacao: [272, FRENTE], aguardando_urna: [252, FRENTE], habilitacao: [300, FRENTE],
    comprovante: [326, FRENTE], cabine: [358, 192], saida: [416, MEIO], recusado: [40, MEIO],
    mesa_presidente: [276, 196], mesa_m1: [300, 196], mesa_m2: [324, 196], // sentados junto à mesa
    urna_presidente: [342, FRENTE], porta_secretario: [228, MEIO], portao: [68, MEIO],
    fiscal: [250, TRAS], a_caminho: [-12, MEIO], urna: [384, MEIO + 3],
    externo_boca: [24, MEIO], policia_externo: [36, MEIO], policia_porta: [204, MEIO],
    viatura: [30, MEIO + 6], policia_viatura: [22, MEIO + 6], indo_embora: [10, MEIO],
  };
  const NA_FILA_CORREDOR = 10, NA_CALCADA = 6;
  function vagaFila(v) {
    if (v < NA_FILA_CORREDOR) return [226 - v * 13, FRENTE];
    if (v < NA_FILA_CORREDOR + NA_CALCADA) return [72 - (v - NA_FILA_CORREDOR) * 11, MEIO + 4];
    return [-30, MEIO + 4]; // além disso, fora do quadro: aparece só no contador
  }
  function alvoDe(p, porId) {
    if (p.zona === "assento") return [226 - p.vaga * 11, TRAS];
    if (p.zona === "fila") return vagaFila(p.vaga);
    if (p.zona === "aguardando_comprovante") return [334 + p.vaga * 6, FRENTE];
    if (p.zona === "fila_presidente" || p.zona === "fila_secretario") {
      const [x] = vagaFila(p.vaga || 0);
      return [x + (p.zona === "fila_presidente" ? 9 : -9), MEIO];
    }
    if (p.zona && p.zona.indexOf("policia_") === 0) {
      const b = POS[p.zona] || POS.policia_externo;
      return [b[0] + (p.vaga || 1) * 10, b[1]];
    }
    return (POS[p.zona] || [W / 2, MEIO]).slice();
  }
  function regiao(x) { return x < PORTAO_X ? 0 : (x < PORTA_X ? 1 : 2); }
  function caminho(de, para, zona) {
    const pts = [];
    let a = regiao(de[0]);
    const b = zona === "saida" ? 3 : regiao(para[0]);
    while (a !== b) {
      if (a < b) {
        pts.push(a === 0 ? [PORTAO_X, MEIO] : a === 1 ? [PORTA_X, MEIO] : [SAIDA_X, MEIO]); a++;
      } else { pts.push(a === 2 ? [PORTA_X, MEIO] : [PORTAO_X, MEIO]); a--; }
    }
    pts.push(para);
    return pts;
  }

  // ------------------------------------------------------------- recepção
  const DESTAQUES = { SAIDA_FILA: "CHAMADO!", FIM_VOTACAO: "VOTOU!", ENCAMINHADO: "NÃO VOTOU" };
  function spawnDe(p) {
    if (["mesa", "fiscal", "apoio"].includes(p.tipo)) return null;
    if (p.tipo === "policial") return [carro.x + 28, MEIO];
    return [-10, MEIO];
  }
  function receber(nova) {
    if (!nova) return;
    cena = nova;
    carro.alvo = nova.viatura ? 4 : -70;
    const vistos = new Set();
    const porId = new Map(nova.pessoas.map((p) => [p.id, p]));
    for (const p of nova.pessoas) {
      vistos.add(p.id);
      let alvo = alvoDe(p, porId);
      if (p.segue && porId.has(p.segue)) {
        const lider = alvoDe(porId.get(p.segue), porId);
        alvo = [lider[0] - 8, lider[1] + (p.zona === "assento" ? 0 : 1)];
      }
      let s = sprites.get(p.id);
      if (!s) {
        const sp = spawnDe(p) || alvo;
        s = { x: sp[0], y: sp[1], rota: [], dados: p, saindo: false, destaque: null, dir: 1, vel: 0.05,
              aguardaCarro: p.tipo === "policial" && !reduzido };
        sprites.set(p.id, s);
      }
      s.dados = p;
      s.saindo = false;
      s.alvo = alvo;
      const fim = s.rota.length ? s.rota[s.rota.length - 1] : [s.x, s.y];
      if (!s.aguardaCarro && (Math.abs(fim[0] - alvo[0]) > 0.5 || Math.abs(fim[1] - alvo[1]) > 0.5)) {
        s.rota = caminho([s.x, s.y], alvo, p.zona);
        s.vel = Math.max(0.035, distanciaRota(s) / transicaoMs);
      }
      if (reduzido) { s.x = alvo[0]; s.y = alvo[1]; s.rota = []; s.aguardaCarro = false; }
    }
    for (const [id, s] of sprites) {
      if (vistos.has(id)) continue;
      if (reduzido) { sprites.delete(id); continue; }
      if (s.dados.zona === "saida" && s.x < W + 10) {
        s.saindo = true; if (!s.rota.length) s.rota = [[W + 16, s.y]];
      } else if (s.dados.tipo === "policial" || s.dados.zona === "viatura") {
        s.saindo = true; s.rota = caminho([s.x, s.y], [carro.x + 28, MEIO + 6], ""); s.vel = 0.045;
      } else if (s.dados.tipo === "tecnico" || s.dados.tipo === "manifestante") {
        s.saindo = true; s.rota = caminho([s.x, s.y], [-16, MEIO], ""); s.vel = 0.05;
      } else sprites.delete(id);
    }
    const agoraMs = performance.now();
    for (const r of nova.recentes || []) {
      if (r.seq <= ultimoSeqDestaque) continue;
      const rot = DESTAQUES[r.tipo];
      const s = r.eleitor && sprites.get(r.eleitor);
      if (rot && s && ultimoSeqDestaque >= 0) s.destaque = { texto: rot, ate: agoraMs + 1400, forte: r.tipo === "SAIDA_FILA" };
    }
    if ((nova.recentes || []).length) ultimoSeqDestaque = Math.max(ultimoSeqDestaque, ...nova.recentes.map((r) => r.seq));
    tocarSons(nova.recentes || []);
    atualizarPainel(nova);
  }
  function distanciaRota(s) {
    let d = 0, x = s.x, y = s.y;
    for (const [px, py] of s.rota) { d += Math.hypot(px - x, py - y); x = px; y = py; }
    return d;
  }

  // ------------------------------------------------------- painel HTML
  function el(tag, cls, texto) { const e = document.createElement(tag); if (cls) e.className = cls; if (texto != null) e.textContent = texto; return e; }
  function atualizarPainel(c) {
    estacoesEl.replaceChildren(...(c.estacoes || []).map((e) => {
      const card = el("div", "est");
      const h = el("h3"); h.append(el("span", "num", String(e.n)), el("span", null, e.nome));
      card.append(h, el("div", "quem", e.quem));
      if (e.status && e.status !== "—") card.append(el("div", "status st-" + e.status.split(" ")[0], e.status));
      if (e.detalhe) card.append(el("div", "det", e.detalhe));
      card.title = [e.nome, e.quem, e.status, e.detalhe].filter(Boolean).join(" · ");
      return card;
    }));
    listaEl.replaceChildren(...(c.narracao || []).map((n) => {
      const li = el("li", n.nivel);
      li.append(el("span", "h", n.hora), document.createTextNode(n.texto));
      return li;
    }));
    statusEl.textContent = `${c.hora} · ${c.politica}${c.experimental ? " (LABORATÓRIO)" : ""}`;
  }

  // ------------------------------------------------------------------ som
  let audio = null;
  btnSom.addEventListener("click", () => {
    try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); audio.resume(); } catch (e) { audio = null; }
    btnSom.hidden = true;
  });
  function bip(freq, dur, quando) {
    if (!audio || audio.state !== "running") return;
    const o = audio.createOscillator(), g = audio.createGain();
    o.type = "square"; o.frequency.value = freq; g.gain.value = 0.04;
    o.connect(g); g.connect(audio.destination);
    const t = audio.currentTime + (quando || 0);
    o.start(t); o.stop(t + dur);
  }
  function tocarSons(recentes) {
    const novos = recentes.filter((r) => r.seq > ultimoSeqSom);
    const primeiro = ultimoSeqSom < 0;
    if (recentes.length) ultimoSeqSom = Math.max(ultimoSeqSom, ...recentes.map((r) => r.seq));
    if (!somLigado || primeiro) return;
    const tipos = new Set(novos.map((r) => r.som).filter(Boolean));
    if (tipos.has("alerta")) { bip(220, 0.12); bip(180, 0.12, 0.14); }
    if (tipos.has("chamada")) { bip(660, 0.06); bip(880, 0.06, 0.08); }
    if (tipos.has("urna")) { for (let i = 0; i < 5; i++) bip(1200 + (i % 2) * 300, 0.05, i * 0.06); }
    if (tipos.has("chegada")) bip(520, 0.04);
  }

  // ------------------------------------------------------------ utilidades
  function redimensionar() {
    const larg = Math.max(W, document.body.clientWidth - 8);
    const nova = Math.max(1, Math.min(4, Math.floor(larg / W)));
    if (nova === escala && fundo) return;
    escala = nova;
    canvas.width = W * escala; canvas.height = H * escala;
    canvas.style.width = W * escala + "px"; canvas.style.height = H * escala + "px";
    document.documentElement.style.setProperty("--largura", W * escala + "px");
    fundo = null;
  }
  window.addEventListener("resize", () => { redimensionar(); ajustarAltura(); });

  function r(c, x, y, w, h, cor) { c.fillStyle = cor; c.fillRect(Math.round(x), Math.round(y), w, h); }
  function retTela(c, x, y, w, h, cor) {
    c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = cor;
    c.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); c.restore();
  }
  function pxFonte(tam) { return tam === "g" ? escala : Math.max(1, Math.floor(escala / 2)); }
  function medirCaixa(s, tam) {
    const px = pxFonte(tam || "p");
    return { w: (F.largura(s) * px + px * 4) / escala + 2 * px / escala, h: ((F.ALTURA - 1) * px + px * 2) / escala + 2 * px / escala };
  }
  let ocupados = []; // retângulos de balões já desenhados neste quadro
  function posicaoLivre(x, y, w, h) {
    let yy = y;
    for (let tent = 0; tent < 6; tent++) {
      const colide = ocupados.some((b) => x - w / 2 < b.x + b.w / 2 && x + w / 2 > b.x - b.w / 2 && yy < b.y + b.h && yy + h > b.y);
      if (!colide) break;
      yy -= h + 1;
    }
    ocupados.push({ x, y: yy, w, h });
    return yy;
  }
  function caixa(c, s, x, y, o) {
    o = o || {};
    const px = pxFonte(o.tam || "p");
    const pad = px * 2;
    const w = F.largura(s) * px + pad * 2, h = (F.ALTURA - 1) * px + pad;
    let dx = Math.round(x * escala), dy = Math.round(y * escala);
    if (o.centro) dx -= Math.round(w / 2);
    dx = Math.max(1, Math.min(canvas.width - w - 1, dx));
    if (o.fundo) {
      retTela(c, dx - px, dy - px, w + 2 * px, h + 2 * px, o.borda || "#14100a");
      retTela(c, dx, dy, w, h, o.fundo);
      if (o.rabo) retTela(c, Math.round(x * escala) - px, dy + h, 2 * px, 2 * px, o.fundo);
    }
    F.desenhar(c, s, dx + pad, dy + Math.round(pad / 2) - px, px, o.cor || "#14100a");
    return { w: w / escala, h: h / escala };
  }
  function mistura(a, b, t) {
    const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
    const c = [16, 8, 0].map((s) => Math.round(((pa >> s) & 255) * (1 - t) + ((pb >> s) & 255) * t));
    return "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
  }
  function corCeu(min) {
    const pts = [[420, "#f6c78a"], [510, "#9fd4f5"], [720, "#7cc4f2"], [930, "#9cc9e8"], [1020, "#f0a36b"], [1080, "#5a4a7a"]];
    for (let i = 1; i < pts.length; i++) {
      if (min <= pts[i][0]) { const t = (min - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0]); return mistura(pts[i - 1][1], pts[i][1], Math.max(0, t)); }
    }
    return pts[pts.length - 1][1];
  }

  // ------------------------------------------------------------- cenário fixo
  /** Piso com faixas que se alargam em direção ao observador (profundidade) e juntas convergindo ao fundo. */
  function pisoPerspectiva(c, x, w, tons, junta, fuga, base) {
    const fim = base || 215;
    const ys = [170, 175, 181, 188, 196, fim];
    for (let i = 0; i < 5; i++) {
      if (ys[i] >= fim) break;
      r(c, x, ys[i], w, Math.min(ys[i + 1], fim) - ys[i], tons[i]);
      r(c, x, ys[i], w, 1, junta);
    }
    for (let k = -8; k <= 8; k++) { // juntas convergindo para um ponto de fuga
      const x0 = fuga + k * 9;
      for (let y = 170; y < fim; y++) {
        const xx = Math.round(x0 + (x0 - fuga) * ((y - 170) / 45) * 1.6);
        if (xx >= x && xx < x + w) r(c, xx, y, 1, 1, junta);
      }
    }
    if (!base) r(c, x, 167, w, 3, "#5b4030"); // rodapé (só em ambiente interno)
  }
  /** Parede em corte, do teto ao chão, com vão de porta, batentes, folha aberta e soleira. */
  function parede(c, x, cor, folhaParaDentro) {
    r(c, x, 26, 6, 102, cor); r(c, x + 1, 26, 1, 102, mistura(cor, "#ffffff", 0.15));
    r(c, x - 2, 126, 10, 3, "#3b2a1c");                       // verga
    r(c, x - 1, 129, 2, 41, "#3b2a1c"); r(c, x + 5, 129, 2, 41, "#3b2a1c"); // batentes
    const fx = folhaParaDentro ? x - 7 : x + 7; // folha aberta, sempre dentro do quadro
    r(c, fx, 130, 6, 38, "#b07a45"); r(c, folhaParaDentro ? fx + 5 : fx, 130, 1, 38, "#7a5332"); r(c, fx + 2, 148, 1, 2, "#e3b341");
    r(c, x - 1, 170, 8, 45, mistura(cor, "#000000", 0.25));   // soleira atravessando o piso
    r(c, x, 170, 6, 1, "#2a1d14");
    r(c, x, 215, 6, 10, "#3b2a1c");
  }
  function desenharFundo(minuto) {
    const off = document.createElement("canvas");
    off.width = W * escala; off.height = H * escala;
    const c = off.getContext("2d");
    c.imageSmoothingEnabled = false;
    c.setTransform(escala, 0, 0, escala, 0, 0);
    const ceu = corCeu(minuto);
    // céu, sol e nuvens
    r(c, 0, 0, W, 40, ceu); r(c, 0, 40, 80, 130, ceu);
    const sx = 10 + Math.max(0, Math.min(1, (minuto - 480) / 600)) * 52;
    r(c, sx, 10, 8, 8, "#fff3b0"); r(c, sx + 1, 9, 6, 10, "#fff3b0"); r(c, sx - 1, 11, 10, 6, "#fff3b0");
    for (const [x, y] of [[40, 50], [120, 12], [250, 8], [330, 16]]) {
      r(c, x, y, 18, 4, "#ffffff"); r(c, x + 4, y - 3, 9, 3, "#ffffff"); r(c, x - 2, y + 1, 22, 2, "#eef6fb");
    }
    // árvore
    r(c, 22, 112, 6, 60, "#6b4423"); r(c, 24, 112, 2, 60, "#7d5330");
    for (const [x, y, w, h] of [[6, 80, 38, 22], [2, 92, 46, 18], [10, 70, 28, 12], [12, 106, 30, 8]]) r(c, x, y, w, h, "#2f7a35");
    for (let i = 0; i < 26; i++) r(c, 6 + (i * 37) % 40, 74 + (i * 23) % 36, 3, 2, "#3f9445");
    // poste
    r(c, 60, 92, 2, 80, "#55595e"); r(c, 56, 90, 10, 3, "#55595e"); r(c, 56, 93, 4, 2, "#ffe9a8");
    // calçada e rua
    pisoPerspectiva(c, 0, 80, ["#a9a397", "#b3ada2", "#bdb7ac", "#c6c0b5", "#cfc9be"], "#9a9488", 40, 199);
    r(c, 0, 199, 86, 3, "#d8d3c9");
    r(c, 0, 202, 86, 23, "#3b3d42");
    for (let x = 4; x < 86; x += 18) r(c, x, 213, 9, 2, "#e8d36a");
    // telhado e laje
    r(c, 80, 26, 320, 4, "#8a4b2f"); r(c, 80, 30, 320, 10, "#a9a39a");
    for (let x = 80; x < 400; x += 8) r(c, x, 26, 4, 2, "#a65a38");
    // corredor: parede com barrado verde
    r(c, 86, 40, 150, 130, "#efe6cf"); r(c, 86, 136, 150, 34, "#5f9e7a"); r(c, 86, 135, 150, 1, "#3f7a5a");
    for (const x of [96, 166]) { // janelas
      r(c, x, 52, 40, 30, "#6b4f3a"); r(c, x + 2, 54, 36, 26, ceu); r(c, x + 19, 54, 2, 26, "#6b4f3a"); r(c, x + 2, 66, 36, 2, "#6b4f3a");
    }
    // painel de chamada (texto dinâmico desenhado depois)
    r(c, 110, 90, 70, 38, "#2b2b2b"); r(c, 112, 92, 66, 34, "#0e1a12"); r(c, 143, 128, 4, 6, "#2b2b2b");
    // mural
    r(c, 190, 92, 36, 34, "#9c6b3f"); r(c, 192, 94, 32, 30, "#c99a62");
    for (const [x, y, cor] of [[195, 97, "#ffffff"], [207, 99, "#ffe98a"], [196, 110, "#bfe3ff"], [210, 112, "#ffffff"]]) r(c, x, y, 10, 9, cor);
    // extintor e bebedouro
    r(c, 90, 150, 5, 12, "#d6342c"); r(c, 91, 147, 3, 3, "#222"); r(c, 89, 139, 7, 6, "#ffffff");
    caixa(c, "EXT", 92.5, 139.5, { centro: true, cor: "#d6342c" });
    // placa dos assentos
    r(c, 150, 143, 78, 10, "#1f5fa8");
    caixa(c, "ASSENTOS PREFERENCIAIS", 189, 144, { centro: true, cor: "#ffffff" });
    // piso do corredor: granilite em perspectiva (mais escuro ao fundo, faixas que se alargam à frente)
    pisoPerspectiva(c, 86, 150, ["#bdb8ad", "#c9c4b9", "#d4cfc4", "#dedad0", "#e6e2d9"], "#aaa498", 118);
    // parede externa (fachada) com portão
    parede(c, 80, "#8f7556");
    r(c, 66, 30, 80, 10, "#1f5fa8");
    caixa(c, "LOCAL DE VOTAÇÃO", 106, 31, { centro: true, cor: "#ffffff" });
    // parede interna com porta da seção

    // sala: parede, barrado de madeira
    r(c, 242, 40, 158, 130, "#f3ead2"); r(c, 242, 140, 158, 30, "#a8784f"); r(c, 242, 139, 158, 1, "#7a5332");
    for (let x = 246; x < 400; x += 12) r(c, x, 141, 1, 28, "#956a44");
    // lousa
    r(c, 266, 62, 76, 40, "#7a5a3a"); r(c, 268, 64, 72, 36, "#2b5a3f"); r(c, 268, 100, 72, 3, "#8b6b4a");
    caixa(c, "SEÇÃO 0042", 304, 66, { centro: true, cor: "#e8f0e0" });
    caixa(c, "ZONA 001 (FICTÍCIA)", 304, 76, { centro: true, cor: "#bfe0c8" });
    caixa(c, "BOM DIA, ELEITOR!", 304, 87, { centro: true, cor: "#ffe98a" });
    // janela da sala
    r(c, 248, 56, 14, 26, "#6b4f3a"); r(c, 250, 58, 10, 22, ceu);
    // pertences (prateleira)
    r(c, 318, 148, 22, 2, "#6b4f3a"); r(c, 320, 141, 6, 7, "#8e5a9e"); r(c, 328, 143, 7, 5, "#2b2b2b"); r(c, 330, 144, 2, 3, "#3d7bd9");
    caixa(c, "PERTENCES", 329, 132, { centro: true, cor: "#5b4030" });
    // piso de madeira em perspectiva
    pisoPerspectiva(c, 242, 152, ["#9c6a3e", "#ad7647", "#bb8250", "#c78e5a", "#d29a63"], "#8e5f36", 320);
    // saída
    parede(c, 236, "#6e5236"); parede(c, 394, "#6e5236", true);
    // saída bem sinalizada: placa luminosa, seta e faixa no piso
    r(c, 366, 112, 30, 11, "#14100a"); r(c, 367, 113, 28, 9, "#1f9e55");
    caixa(c, "SAÍDA ▶", 381, 113, { centro: true, cor: "#ffffff" });
    for (let i = 0; i < 4; i++) r(c, 372 + i * 6, 210, 4, 2, "#1f9e55");
    r(c, 394, 208, 2, 6, "#1f9e55"); r(c, 396, 209, 1, 4, "#1f9e55");
    // nomes dos ambientes
    caixa(c, "RUA", 66, 216, { centro: true, fundo: "#ffffff" });
    caixa(c, "CORREDOR", 161, 44, { centro: true, fundo: "#efe6cf", cor: "#5b4030" });
    caixa(c, "SALA DA SEÇÃO", 318, 44, { centro: true, fundo: "#f3ead2", cor: "#5b4030" });
    // placa sobre a porta da seção (depois das paredes, para não ser coberta)
    r(c, 224, 100, 30, 9, "#234d34");
    caixa(c, "SEÇÃO 42", 239, 101, { centro: true, cor: "#e8f0e0" });
    // fundação
    r(c, 80, 215, 320, 10, "#6e665b"); r(c, 80, 215, 320, 1, "#5a5348");
    // entrada (placa no muro)
    r(c, 58, 120, 24, 9, "#ffd34d");
    caixa(c, "ENTRADA", 70, 121, { centro: true });
    return off;
  }

  // ----------------------------------------------------------- props dinâmicos
  function desenharPainelChamada() {
    if (!cena) return;
    caixa(ctx, "PAINEL DE CHAMADA", 145, 94, { centro: true, cor: "#7fe0a0" });
    const p = cena.proximo;
    const linha = cena.encerrado && !p ? "ENCERRADO" : p ? `${p.id} ${p.icone || ""}`.trim() : "FILA VAZIA";
    caixa(ctx, linha, 145, 103, { centro: true, tam: "g", cor: "#ffd34d" });
    caixa(ctx, `NA FILA: ${cena.fila_total}`, 145, 117, { centro: true, cor: "#bfe0c8" });
  }
  function desenharRelogio(min) {
    const cx = 362, cy = 72;
    r(ctx, cx - 7, cy - 6, 15, 13, "#5b4030"); r(ctx, cx - 6, cy - 7, 13, 15, "#5b4030");
    r(ctx, cx - 6, cy - 5, 13, 11, "#fbf6e8"); r(ctx, cx - 5, cy - 6, 11, 13, "#fbf6e8");
    for (let k = 0; k < 12; k += 3) { const a = k / 12 * 2 * Math.PI; r(ctx, cx + Math.round(Math.sin(a) * 5), cy - Math.round(Math.cos(a) * 5), 1, 1, "#5b4030"); }
    const ponteiro = (ang, len, cor) => { for (let i = 0; i <= len; i++) r(ctx, cx + Math.round(Math.sin(ang) * i), cy - Math.round(Math.cos(ang) * i), 1, 1, cor); };
    ponteiro(((min / 60) % 12) / 12 * 2 * Math.PI, 3, "#1a1208");
    ponteiro((min % 60) / 60 * 2 * Math.PI, 5, "#c0392b");
  }
  function desenharVentilador(t) {
    r(ctx, 319, 40, 2, 6, "#55595e"); r(ctx, 315, 46, 10, 3, "#55595e");
    const fase = reduzido ? 0 : Math.floor(t / 90) % 3;
    if (fase === 0) { r(ctx, 296, 47, 48, 2, "#7d8288"); }
    else if (fase === 1) { r(ctx, 302, 47, 36, 2, "#7d8288"); r(ctx, 318, 45, 4, 6, "#7d8288"); }
    else { r(ctx, 308, 47, 24, 2, "#7d8288"); r(ctx, 318, 44, 4, 8, "#7d8288"); }
  }
  /** Cadeira inteira: encosto ligado ao assento por duas colunas, assento com espessura e quatro pés. */
  function cadeira(x, piso, cor, escura) {
    const assento = piso - 7;
    r(ctx, x - 5, assento - 12, 10, 8, cor);                 // encosto (atrás das costas)
    r(ctx, x - 5, assento - 12, 10, 1, mistura(cor, "#ffffff", 0.25));
    r(ctx, x - 5, assento - 4, 1, 4, escura); r(ctx, x + 4, assento - 4, 1, 4, escura); // colunas
    r(ctx, x - 6, assento, 12, 2, cor); r(ctx, x - 6, assento + 2, 12, 1, escura);     // assento
    r(ctx, x - 5, assento + 3, 1, 4, escura); r(ctx, x + 4, assento + 3, 1, 4, escura); // pés
    r(ctx, x - 3, assento + 3, 1, 3, escura); r(ctx, x + 2, assento + 3, 1, 3, escura);
  }
  /** Cadeira de perfil voltada para a direita: encosto atrás, assento, pés. */
  function cadeiraPerfil(x, piso, cor, escura) {
    r(ctx, x - 4, piso - 21, 2, 15, cor); r(ctx, x - 4, piso - 21, 2, 1, mistura(cor, "#ffffff", 0.3)); // encosto
    r(ctx, x - 4, piso - 7, 10, 2, cor); r(ctx, x - 4, piso - 5, 10, 1, escura);                      // assento
    r(ctx, x - 4, piso - 4, 1, 4, escura); r(ctx, x + 5, piso - 4, 1, 4, escura);                      // pés
  }
  function desenharBanco() {
    for (let k = 0; k < 8; k++) cadeiraPerfil(226 - k * 11, TRAS, "#4a83bb", "#2b4f75");
    cadeiraPerfil(250, TRAS, "#8b5a2b", "#5a3a1a"); // fiscal
  }
  function desenharCadeirasMesa() {
    for (const x of [276, 300, 324]) cadeira(x, 196, "#3b3b46", "#22222a");
  }
  function desenharMesa(t) {
    r(ctx, 262, 183, 80, 3, "#8b5a2b"); r(ctx, 262, 182, 80, 1, "#a8703f");
    r(ctx, 264, 186, 76, 12, "#7a4a24"); r(ctx, 264, 186, 76, 1, "#5a3a1a");
    r(ctx, 264, 198, 3, 9, "#5a3a1a"); r(ctx, 337, 198, 3, 9, "#5a3a1a");
    r(ctx, 278, 179, 8, 4, "#f5efd8"); r(ctx, 281, 179, 1, 4, "#c9bfa0"); // caderno
    r(ctx, 288, 174, 10, 9, "#2b2b2b"); r(ctx, 289, 175, 8, 5, "#5ee08a"); // terminal do mesário
    const bio = cena && cena.pessoas.some((p) => p.acao === "biometria_falha");
    const ocupado = cena && cena.pessoas.some((p) => p.acao === "biometria" || p.acao === "biometria_falha");
    r(ctx, 304, 179, 7, 4, "#3a3a3a");
    r(ctx, 306, 180, 3, 2, ocupado ? (bio && Math.floor(t / 250) % 2 ? "#ff4d4d" : "#4dff88") : "#1d5d32"); // leitor biométrico
    r(ctx, 328, 179, 6, 4, "#ffffff"); r(ctx, 329, 178, 6, 4, "#f4f4f4"); // comprovantes
    caixa(ctx, "1", 268, 189, { fundo: "#ffd34d" }); caixa(ctx, "2", 292, 189, { fundo: "#ffd34d" }); caixa(ctx, "3", 316, 189, { fundo: "#ffd34d" });
  }
  // Cabine: estrutura com teto, biombo baixo na frente (vê-se o eleitor de costas) e a urna na mesinha.
  function desenharUrnaFundo() {
    r(ctx, 348, 148, 34, 3, "#3d4a5c"); r(ctx, 348, 151, 34, 1, "#2a3340");                 // teto
    r(ctx, 348, 151, 2, 46, "#3d4a5c"); r(ctx, 380, 151, 2, 46, "#3d4a5c");                // colunas
    r(ctx, 350, 151, 30, 26, "#c9d3df");                                                  // fundo claro
    r(ctx, 367, 182, 12, 2, "#5a5f66"); r(ctx, 368, 184, 1, 10, "#3a3f46"); r(ctx, 377, 184, 1, 10, "#3a3f46"); // mesinha
    r(ctx, 368, 174, 10, 8, "#e2e2e2"); r(ctx, 368, 174, 10, 1, "#ffffff"); r(ctx, 369, 177, 8, 1, "#b7b7b7"); // urna (por trás)
    if (cena) {
      const u = cena.urna;
      const cor = u.estado === "DISPONIVEL" ? "#3ddc6a" : u.estado === "OCUPADO" ? "#ffd34d" : "#ff3b3b";
      r(ctx, 352, 140, 26, 8, "#14100a"); r(ctx, 353, 141, 5, 6, cor);
      caixa(ctx, u.estado === "DISPONIVEL" ? "LIVRE" : u.estado === "OCUPADO" ? "EM USO" : "PARADA", 368, 140.5, { centro: true, cor: "#ffffff" });
    }
  }
  function desenharBiombo() {
    r(ctx, 348, 184, 34, 14, "#56677d"); r(ctx, 348, 184, 34, 1, "#7a8ca3"); r(ctx, 348, 197, 34, 1, "#3d4a5c");
    caixa(ctx, "CABINE", 365, 187, { centro: true, cor: "#e8eef6" });
    caixa(ctx, "4", 341, 186, { fundo: "#ffd34d" });
    if (cena && cena.urna.contingencia) caixa(ctx, "CONTINGÊNCIA", 365, 128, { centro: true, fundo: "#ffd34d" });
  }
  function desenharViatura(t) {
    if (carro.x < -60) return;
    const x = Math.round(carro.x), y = 221;
    r(ctx, x, y - 12, 48, 8, "#f4f4f4"); r(ctx, x + 2, y - 13, 44, 1, "#f4f4f4");
    r(ctx, x + 12, y - 19, 22, 7, "#f4f4f4"); r(ctx, x + 14, y - 18, 8, 5, "#7fb6d9"); r(ctx, x + 24, y - 18, 8, 5, "#7fb6d9");
    r(ctx, x, y - 8, 48, 2, "#1f4fa8");
    const pisca = reduzido ? 0 : Math.floor(t / 200) % 2;
    r(ctx, x + 18, y - 22, 5, 3, pisca ? "#ff3b3b" : "#7a1a1a"); r(ctx, x + 23, y - 22, 5, 3, pisca ? "#1a2a7a" : "#3b6bff");
    r(ctx, x + 6, y - 5, 8, 6, "#151515"); r(ctx, x + 9, y - 3, 2, 2, "#9a9a9a");
    r(ctx, x + 34, y - 5, 8, 6, "#151515"); r(ctx, x + 37, y - 3, 2, 2, "#9a9a9a");
    r(ctx, x + 46, y - 11, 2, 2, "#ffe98a");
    caixa(ctx, "POLÍCIA", x + 24, y - 12, { centro: true, cor: "#1f4fa8" });
  }
  function desenharPortao() {
    if (!cena || !cena.portao_fechado) return;
    for (let x = 80; x <= 86; x += 2) r(ctx, x, 131, 1, 39, "#3a3a3a");
    r(ctx, 79, 131, 9, 2, "#3a3a3a");
    caixa(ctx, "ENCERRADO 17H", 60, 150, { centro: true, fundo: "#ff7a7a" });
  }

  // -------------------------------------------------------------- personagens
  const PELES = ["#ffdbac", "#f1c27d", "#e0ac69", "#c68642", "#8d5524", "#5c3a21"];
  const CABELOS = ["#2b1b0e", "#4a2f1b", "#111111", "#a0522d", "#d8c38a", "#6e4b2a", "#2e2e2e", "#8a8a8a"];
  const ROUPAS = ["#d9534f", "#5bc0de", "#5cb85c", "#f0ad4e", "#9b59b6", "#3b6ea5", "#e67e22", "#16a085", "#c0392b", "#e84393", "#f5f5f5", "#2d3436"];
  const CALCAS = ["#2c3e50", "#34495e", "#4b3621", "#1f3a5f", "#5d4037", "#7f8c8d", "#2d3436"];
  const ESTILOS = ["curto", "longo", "coque", "crespo", "bone", "raspado", "longo", "curto"];
  function visual(p) {
    const i = p.paleta || 0;
    const v = {
      pele: PELES[(i >> 2) % PELES.length], cabelo: CABELOS[i % CABELOS.length], estilo: ESTILOS[(i >> 3) % ESTILOS.length],
      roupa: ROUPAS[(i >> 1) % ROUPAS.length], calca: CALCAS[(i >> 4) % CALCAS.length], saia: (i >> 5) % 5 === 0,
      sapato: (i >> 6) % 2 ? "#2b2b2b" : "#6b3b1b", bone: ROUPAS[(i >> 2) % ROUPAS.length], colete: null, faixa: null,
    };
    if (p.tipo === "mesa") Object.assign(v, { roupa: "#f4f4f4", colete: "#1f5fa8", calca: "#2c3e50", saia: false });
    if (p.tipo === "policial") Object.assign(v, { roupa: "#1e2b48", calca: "#1e2b48", estilo: "quepe", bone: "#121a2e", saia: false, sapato: "#111" });
    if (p.tipo === "tecnico") Object.assign(v, { roupa: "#3a3a3a", colete: "#ff8c1a", faixa: "#e8e8e8", estilo: "bone", bone: "#ff8c1a", saia: false });
    if (p.tipo === "apoio") Object.assign(v, { colete: "#ffd34d", faixa: "#ffffff" });
    return v;
  }

  /** Personagem 2D: pés em (x, y). dir: f frente, b costas, l/r perfil. */
  /** Sentado de perfil: tronco ereto, coxa horizontal no assento, canela vertical, pés no chão. */
  function sentadoPerfil(c, X, Y, v, o) {
    const d = o.dir === "l" ? -1 : 1;
    const px = (dx, yy, w, h, cor) => r(c, d > 0 ? X + dx : X - dx - w + 1, yy, w, h, cor);
    // canela e pé (à frente)
    px(4, Y - 6, 2, 5, v.calca); px(4, Y - 1, 4, 1, v.sapato); px(4, Y - 2, 3, 1, v.sapato);
    // coxa sobre o assento
    px(-2, Y - 9, 8, 3, v.calca);
    // tronco ereto
    px(-2, Y - 17, 5, 8, v.roupa); px(-2, Y - 10, 5, 1, "#1a1208");
    if (v.colete) { px(-2, Y - 17, 5, 8, v.colete); }
    if (o.papel === "fiscal") { px(1, Y - 16, 1, 3, "#2e9e4f"); px(1, Y - 14, 2, 2, "#bff0c9"); }
    // braço apoiado na coxa
    px(0, Y - 16, 2, 5, v.roupa); px(2, Y - 11, 3, 2, v.pele);
    // pescoço e cabeça de perfil
    px(-1, Y - 18, 3, 1, v.pele);
    px(-2, Y - 25, 5, 7, v.pele);
    px(1, Y - 22, 1, 1, "#1a1208"); px(3, Y - 21, 1, 1, v.pele);
    const cab = v.cabelo;
    if (v.estilo === "bone" || v.estilo === "quepe") { px(-2, Y - 27, 5, 3, v.bone); px(3, Y - 25, 2, 1, v.bone); }
    else if (v.estilo === "crespo") { px(-3, Y - 28, 7, 4, cab); px(-3, Y - 24, 2, 3, cab); }
    else if (v.estilo === "coque") { px(-2, Y - 26, 5, 2, cab); px(-4, Y - 26, 2, 3, cab); px(-2, Y - 24, 1, 3, cab); }
    else { px(-2, Y - 26, 5, 2, cab); px(-2, Y - 24, 1, v.estilo === "longo" ? 7 : 3, cab); }
    return { topo: Y - 28 };
  }

  function pessoa(c, x, y, v, o) {
    const X = Math.round(x), Y = Math.round(y);
    const dir = o.dir, pose = o.pose, q = o.quadro || 0;
    if (pose === "sentado" && (dir === "l" || dir === "r")) return sentadoPerfil(c, X, Y, v, o);
    const sent = pose === "sentado" || pose === "atras_mesa";
    const ag = pose === "agachado";
    const dy = pose === "atras_mesa" ? 5 : pose === "sentado" ? -3 : ag ? 7 : 0;
    const escuro = "#1a1208";
    // pernas
    if (pose !== "atras_mesa") {
      if (dir === "l" || dir === "r") {
        const d = dir === "r" ? 1 : -1;
        const passos = [[0, 0], [2, -2], [0, 0], [-2, 2]][q % 4];
        if (ag) { r(c, X - 2, Y - 4, 5, 2, v.calca); r(c, X - 2 + 2 * d, Y - 2, 3, 2, v.sapato); }
        else {
          r(c, X - 1 + passos[1] * d, Y - 9, 2, 7, mistura(v.calca, "#000000", 0.25)); r(c, X - 1 + passos[1] * d, Y - 2, 3, 2, v.sapato);
          r(c, X - 1 + passos[0] * d, Y - 9, 2, 7, v.calca); r(c, X - 1 + passos[0] * d + (d > 0 ? 0 : -1), Y - 2, 3, 2, v.sapato);
        }
      } else if (sent) {
        r(c, X - 3, Y - 6, 7, 2, v.calca); r(c, X - 3, Y - 4, 3, 3, v.calca); r(c, X + 1, Y - 4, 3, 3, v.calca);
        r(c, X - 3, Y - 1, 3, 1, v.sapato); r(c, X + 1, Y - 1, 3, 1, v.sapato);
      } else if (ag) {
        r(c, X - 4, Y - 5, 9, 3, v.calca); r(c, X - 4, Y - 2, 3, 2, v.sapato); r(c, X + 2, Y - 2, 3, 2, v.sapato);
      } else if (v.saia) {
        r(c, X - 4, Y - 10, 9, 5, v.calca); r(c, X - 2, Y - 5, 2, 3, v.pele); r(c, X + 1, Y - 5, 2, 3, v.pele);
        r(c, X - 3, Y - 2, 3, 2, v.sapato); r(c, X + 1, Y - 2, 3, 2, v.sapato);
      } else {
        r(c, X - 3, Y - 9, 3, 7, v.calca); r(c, X + 1, Y - 9, 3, 7, v.calca); r(c, X, Y - 9, 1, 2, v.calca);
        r(c, X - 3, Y - 2, 3, 2, v.sapato); r(c, X + 1, Y - 2, 3, 2, v.sapato);
      }
    }
    const T = Y - dy; // base do tronco
    // tronco
    const lateral = dir === "l" || dir === "r";
    const tx = lateral ? X - 2 : X - 3, tw = lateral ? 5 : 7;
    r(c, tx, T - 17, tw, 7, v.roupa);
    r(c, tx, T - 10, tw, 1, escuro);
    if (v.colete) { r(c, tx, T - 17, 2, 7, v.colete); r(c, tx + tw - 2, T - 17, 2, 7, v.colete); if (lateral) r(c, tx, T - 17, tw, 7, v.colete); }
    if (v.faixa) r(c, tx, T - 13, tw, 1, v.faixa);
    if (o.papel === "mesa" && dir !== "b") r(c, X + 1, T - 16, 2, 2, "#ffffff");
    if (o.papel === "policial" && dir !== "b") { r(c, X + 1, T - 16, 1, 1, "#e3b341"); r(c, tx, T - 11, tw, 1, "#111"); }
    if (o.papel === "fiscal" && dir !== "b") { r(c, X - 1, T - 17, 1, 3, "#2e9e4f"); r(c, X - 2, T - 14, 3, 2, "#bff0c9"); }
    if (o.adesivo && dir !== "b") r(c, X + 1, T - 15, 2, 2, "#ffffff");
    // braços
    const mao = (bx, by) => r(c, bx, by, lateral ? 2 : 1, 2, v.pele);
    const bracoBaixo = (bx) => { r(c, bx, T - 17, lateral ? 2 : 1, 4, v.roupa); mao(bx, T - 13); };
    if (lateral) {
      const d = dir === "r" ? 1 : -1;
      if (pose === "panfletando" || pose === "apontando") {
        r(c, X + 2 * d, T - 16, 4 * d > 0 ? 4 : 4, 2, v.roupa); r(c, d > 0 ? X + 6 : X - 7, T - 16, 2, 2, v.pele);
        if (pose === "panfletando") { r(c, d > 0 ? X + 7 : X - 9, T - 19, 3, 4, "#ffffff"); r(c, d > 0 ? X + 8 : X - 8, T - 18, 1, 2, "#c9c9c9"); }
      } else if (ag) {
        r(c, X + 2 * d, T - 14, 4, 2, v.roupa); r(c, d > 0 ? X + 6 : X - 7, T - 14, 2, 2, v.pele);
        if (o.faisca) { r(c, d > 0 ? X + 9 : X - 10, T - 16, 1, 1, "#fff36b"); r(c, d > 0 ? X + 10 : X - 11, T - 14, 1, 1, "#fff36b"); }
      } else {
        const balanco = pose === "andando" ? [0, 1, 0, -1][q % 4] : 0;
        bracoBaixo(X + balanco * d - (d > 0 ? 0 : 1));
      }
    } else {
      const esq = X - 4, dir_ = X + 4;
      if (pose === "discutindo") {
        const alt = q % 2;
        r(c, esq, T - 21 + alt, 1, 5, v.roupa); mao(esq, T - 23 + alt);
        r(c, dir_, T - 21 + (1 - alt), 1, 5, v.roupa); mao(dir_, T - 23 + (1 - alt));
      } else if (pose === "braco" || pose === "braco_cima") {
        bracoBaixo(esq); r(c, dir_, T - 21, 1, 5, v.roupa); mao(dir_, T - 23);
        if (o.item === "documento") { r(c, dir_ - 1, T - 26, 4, 3, "#ffffff"); r(c, dir_ - 1, T - 25, 4, 1, "#3b6ea5"); }
        if (o.item === "comprovante") { r(c, dir_ - 1, T - 27, 3, 4, "#ffffff"); r(c, dir_, T - 26, 1, 2, "#bdbdbd"); }
        if (o.item === "celular") { r(c, dir_ - 1, T - 26, 2, 3, "#111111"); r(c, dir_ - 1, T - 26, 2, 1, "#3d7bd9"); }
      } else if (pose === "dedo") {
        bracoBaixo(esq); r(c, dir_, T - 17, 1, 3, v.roupa); r(c, dir_ + 1, T - 15, 2, 1, v.pele);
      } else {
        bracoBaixo(esq); bracoBaixo(dir_);
        if (o.item === "documento" && dir !== "b") { r(c, X - 1, T - 14, 4, 3, "#ffffff"); r(c, X - 1, T - 13, 4, 1, "#3b6ea5"); }
        if (o.item === "comprovante" && dir !== "b") { r(c, X + 4, T - 15, 3, 4, "#ffffff"); }
        if (o.item === "senhas") { r(c, X + 4, T - 15, 3, 3, "#ffd34d"); }
        if (o.item === "caixa") { r(c, X + 4, T - 12, 5, 3, "#c0392b"); r(c, X + 5, T - 13, 3, 1, "#7a1a1a"); }
      }
    }
    // pescoço e cabeça
    r(c, X - 1, T - 18, 3, 1, v.pele);
    const hx = lateral ? X - 2 : X - 3, hw = lateral ? 5 : 7, H0 = T - 25;
    r(c, hx, H0, hw, 7, v.pele);
    if (dir === "b") r(c, hx, H0, hw, 6, v.cabelo);
    else if (lateral) {
      const d = dir === "r" ? 1 : -1;
      r(c, d > 0 ? X + 1 : X - 1, H0 + 3, 1, 1, "#1a1208"); r(c, d > 0 ? X + 3 : X - 3, H0 + 4, 1, 1, v.pele);
      r(c, hx, H0 - 1, hw, 2, v.cabelo); r(c, d > 0 ? hx : hx + hw - 1, H0, 1, v.estilo === "longo" ? 8 : 4, v.cabelo);
    } else {
      r(c, X - 2, H0 + 3, 1, 1, "#1a1208"); r(c, X + 2, H0 + 3, 1, 1, "#1a1208");
      r(c, X, H0 + 5, 1, 1, o.bravo ? "#7a1a1a" : "#9a4a3a");
      if (o.bravo) { r(c, X - 3, H0 + 2, 2, 1, "#1a1208"); r(c, X + 2, H0 + 2, 2, 1, "#1a1208"); }
    }
    // cabelos e chapéus
    const cab = v.cabelo;
    switch (v.estilo) {
      case "longo": r(c, hx, H0 - 1, hw, 2, cab); if (!lateral) { r(c, hx - 1, H0, 1, 9, cab); r(c, hx + hw, H0, 1, 9, cab); } break;
      case "coque": r(c, hx, H0 - 1, hw, 2, cab); r(c, X - 1, H0 - 3, 3, 2, cab); break;
      case "crespo": r(c, hx - 1, H0 - 3, hw + 2, 4, cab); if (!lateral) { r(c, hx - 1, H0 + 1, 1, 2, cab); r(c, hx + hw, H0 + 1, 1, 2, cab); } break;
      case "bone": r(c, hx, H0 - 2, hw, 3, v.bone); if (lateral) r(c, dir === "r" ? hx + hw : hx - 3, H0, 3, 1, v.bone); else r(c, hx - 1, H0, hw + 2, 1, v.bone); break;
      case "quepe": r(c, hx - 1, H0 - 3, hw + 2, 3, v.bone); r(c, hx - 1, H0, hw + 2, 1, "#0a0f1c"); r(c, X, H0 - 2, 1, 1, "#e3b341"); break;
      case "raspado": r(c, hx, H0 - 1, hw, 1, cab); break;
      default: r(c, hx, H0 - 1, hw, 2, cab); if (!lateral && dir !== "b") { r(c, hx, H0 + 1, 1, 2, cab); r(c, hx + hw - 1, H0 + 1, 1, 2, cab); }
    }
    return { topo: H0 - 3 };
  }

  function poseDe(s, t) {
    const p = s.dados;
    const andando = s.rota.length > 0 && !reduzido;
    const quadro = Math.floor(t / 130) % 4;
    if (andando) return { dir: s.dir > 0 ? "r" : "l", pose: "andando", quadro, item: p.tipo === "tecnico" ? "caixa" : null };
    const a = p.acao || "";
    switch (p.tipo) {
      case "eleitor":
      case "acompanhante":
        if (p.zona === "assento") return { dir: "r", pose: "sentado" };
        if (a === "discutindo") return { dir: "f", pose: "discutindo", quadro: Math.floor(t / 200), bravo: true };
        if (a === "entregando_documento" || a === "impugnado" || a === "secao_errada") return { dir: "b", pose: "braco", item: "documento" };
        if (a === "sem_documento") return { dir: "b", pose: "em_pe" };
        if (a === "biometria" || a === "biometria_falha") return { dir: "b", pose: "dedo" };
        if (a === "celular" || a === "celular_recusa") return { dir: "b", pose: "braco", item: "celular" };
        if (a === "recebendo") return { dir: "b", pose: "braco", item: "comprovante" };
        if (a === "votando" || p.zona === "cabine" || p.zona === "aguardando_urna") return { dir: "b", pose: "em_pe" };
        return { dir: "f", pose: "em_pe" };
      case "mesa":
        if (p.zona.indexOf("mesa_") === 0) {
          if (a === "conferindo") return { dir: "f", pose: "atras_mesa", item: "documento", papel: "mesa" };
          if (a === "entregando") return { dir: "f", pose: "atras_mesa", item: "comprovante", papel: "mesa" };
          return { dir: "f", pose: "atras_mesa", papel: "mesa" };
        }
        if (p.zona === "urna_presidente") return { dir: "r", pose: "apontando", papel: "mesa" };
        if (a === "senhas") return { dir: "f", pose: "em_pe", item: "senhas", papel: "mesa" };
        if (a === "mediando") return { dir: "f", pose: "braco_cima", papel: "mesa" };
        return { dir: "f", pose: "em_pe", papel: "mesa" };
      case "fiscal": return a === "impugnando" ? { dir: "f", pose: "braco_cima", papel: "fiscal" } : { dir: "r", pose: "sentado", papel: "fiscal" };
      case "apoio": return { dir: a === "alerta" ? "l" : "f", pose: a === "alerta" ? "apontando" : "em_pe", papel: "apoio" };
      case "policial": return { dir: a === "abordando" ? "l" : a === "conduzindo" ? "r" : "f", pose: a === "abordando" ? "apontando" : "em_pe", papel: "policial" };
      case "tecnico": return { dir: "r", pose: a === "consertando" ? "agachado" : "em_pe", faisca: Math.floor(t / 180) % 3 === 0, item: "caixa" };
      case "manifestante":
        if (a === "panfletando") return { dir: "r", pose: "panfletando" };
        if (a === "viatura") return { dir: "l", pose: "em_pe" };
        return { dir: "f", pose: "em_pe", adesivo: true };
    }
    return { dir: "f", pose: "em_pe" };
  }

  const ROTULO_PAPEL = { fiscal: "FISCAL", apoio: "APOIO", tecnico: "TÉC.", policial: "POL." };
  const COR_CLASSE = ["#ffd34d", "#8fd3ff", "#ffb3c1", "#e8e8e8"];

  function desenharSprite(s, t) {
    const p = s.dados;
    const o = poseDe(s, t);
    o.papel = o.papel || p.tipo;
    const v = visual(p);
    if (o.pose === "atras_mesa") o.papel = "mesa";
    const sacode = p.acao === "discutindo" && !reduzido ? (Math.floor(t / 90) % 2) : 0;
    ctx.fillStyle = "rgba(20,12,6,0.28)";
    ctx.fillRect(Math.round(s.x) - 4, Math.round(s.y) - 1, 9, 2);
    ctx.fillRect(Math.round(s.x) - 3, Math.round(s.y), 7, 1);
    s.topo = pessoa(ctx, s.x + sacode, s.y, v, o).topo;
    if (p.selecionado) {
      ctx.strokeStyle = Math.floor(t / 300) % 2 ? "#ffd34d" : "#ffffff"; ctx.lineWidth = 1;
      ctx.strokeRect(Math.round(s.x) - 6.5, s.topo - 1.5, 14, s.y - s.topo + 2);
    }
  }
  function desenharRotulo(s) {
    const p = s.dados;
    // vizinhos na fila ou nos assentos alternam a altura da etiqueta para não se sobreporem
    const alterna = (p.zona === "fila" || p.zona === "assento") && p.vaga % 2 === 1 && s.rota.length === 0 ? 9 : 0;
    const y = s.topo - 9 - alterna;
    if (p.tipo === "mesa") return caixa(ctx, p.rotulo, s.x, y, { centro: true, fundo: "#1f5fa8", cor: "#ffffff" });
    if (ROTULO_PAPEL[p.tipo]) return caixa(ctx, ROTULO_PAPEL[p.tipo], s.x, y, { centro: true, fundo: p.tipo === "policial" ? "#1e2b48" : (visual(p).colete || "#6ab04c"), cor: p.tipo === "policial" ? "#ffffff" : "#14100a" });
    if (p.tipo !== "eleitor" || p.zona === "cabine") return;
    const naEspera = p.zona === "fila" || p.zona === "assento";
    if (naEspera && !(p.posicao <= 3 || p.classe === 0 || p.starvation || p.selecionado)) return;
    if (!naEspera && !p.icone && !p.selecionado) return;
    let etiqueta = p.icone || "";
    if (p.posicao) etiqueta = `${p.posicao}${etiqueta ? " " + etiqueta : ""}`;
    if (etiqueta) caixa(ctx, etiqueta, s.x, y, { centro: true, fundo: COR_CLASSE[p.classe] || "#e8e8e8" });
    if (p.starvation) caixa(ctx, "!", s.x + 7, s.topo, { fundo: "#ff3b3b", cor: "#ffffff" });
  }
  function desenharBalao(s, t, fala) {
    const p = s.dados;
    const y = s.topo - 20;
    if (fala) {
      const [texto, atual] = fala;
      const m = medirCaixa(texto);
      return caixa(ctx, texto, s.x, posicaoLivre(s.x, y, m.w, m.h), { centro: true, rabo: true, fundo: atual ? "#ffffff" : "#d9d6cc",
        cor: atual ? "#14100a" : "#5b5548", borda: atual ? "#14100a" : "#8a8476" });
    }
    if (s.destaque && t < s.destaque.ate) {
      const pisca = s.destaque.forte && Math.floor(t / 250) % 2;
      return caixa(ctx, s.destaque.texto, s.x, y, { centro: true, rabo: true, fundo: pisca ? "#ffffff" : "#ffd34d" });
    }
    if (!p.balao || s.rota.length > 1) return;
    if (p.tipo !== "eleitor" || p.zona === "cabine") return; // mesa, apoio e polícia falam pelos roteiros
    if (p.zona === "fila" || p.zona === "assento") {
      if (p.balao !== "Posso passar?" && p.balao !== "Esperando muito!") return;
    }
    const alerta = /passar|muito|Vote|Impugno|Ocorr/.test(p.balao);
    caixa(ctx, p.balao, s.x, y, { centro: true, rabo: true, fundo: alerta ? "#ffe0e0" : "#ffffff" });
  }

  // ------------------------------------------------------------- diálogos
  // Falas ilustrativas, escolhidas a partir do estado recebido do motor. Não alteram a simulação.
  const PRES = "mesa-presidente", M1 = "mesa-primeiro_mesario", M2 = "mesa-segundo_mesario", SEC = "mesa-secretario";
  const ROTEIROS = {
    entregando_documento: [[PRES, "Bom dia! Documento com foto?"], ["E", "Aqui está."], [PRES, "Confere. CPF digitado."], [PRES, "Aguarde a urna liberar."]],
    impugnado: [["fiscal-1", "Impugno a identidade!"], [PRES, "Vou conferir os dados."], [PRES, "Assine aqui, por favor."], ["E", "Pronto."], [PRES, "Tudo registrado em ata."]],
    secao_errada: [[PRES, "Bom dia! Documento?"], ["E", "Aqui."], [PRES, "Não consta nesta urna."], ["E", "E agora?"], [PRES, "Procure o cartório."]],
    sem_documento: [[PRES, "Documento com foto?"], ["E", "Só tenho a certidão."], [PRES, "Certidão não vale."], [PRES, "Traga RG, CNH ou e-Título."]],
    aguardando: [["E", "Aguardo a urna liberar."]],
    biometria: [[M1, "Polegar no leitor."], ["E", "Assim?"], [M1, "Reconhecido! Pode votar."]],
    biometria_falha: [[M1, "Polegar no leitor."], [M1, "Não reconheceu. De novo."], ["E", "Tento o indicador?"], [M1, "Qual seu ano de nascimento?"], ["E", "Mil novecentos e…"], [M1, "Confere. Pode votar."]],
    celular: [[M1, "O celular não entra na cabine."], ["E", "Ah, desculpa!"], [M1, "Desligue e deixe nos pertences."], ["E", "Pronto, desliguei."]],
    celular_recusa: [[M1, "O celular fica nos pertences."], ["E", "Não, fica comigo!"], [PRES, "Sem entregar, não pode votar."], ["E", "Não vou entregar."], [PRES, "Fica registrado em ata."]],
    recebendo: [[M2, "Seu comprovante e seus pertences."], ["E", "Obrigado!"], [M2, "Bom dia!"]],
    discutindo: [["E", "Posso passar? Tenho pressa!"], [SEC, "Respeite a ordem, por favor."], ["E", "Mas é rapidinho!"], [SEC, "A ordem segue a lei."], [PRES, "Calma, vamos resolver."]],
  };
  const CONVERSA_FILA = [["Bom dia!", "Bom dia!"], ["Demora muito?", "Está andando."], ["Trouxe o documento?", "Trouxe sim."],
                         ["Que calor, hein?", "Nem fala!"], ["É a seção 42?", "É sim, aqui."], ["Primeira vez votando?", "Sim!"]];
  const inicioConversa = new Map();

  function falas(t) {
    const out = new Map(); // id → [texto, falaAtual]
    if (!cena) return out;
    const vivos = new Map([...sprites].filter(([, s]) => !s.aguardaCarro));
    const parado = (id) => vivos.has(id) && vivos.get(id).rota.length === 0;
    const dizer = (id, texto, atual) => { if (vivos.has(id) && (atual || !out.has(id))) out.set(id, [texto, atual]); };
    const ativos = new Set();
    const roteiro = (chave, linhas, eleitor, passo) => {
      ativos.add(chave);
      if (!inicioConversa.has(chave)) inicioConversa.set(chave, t);
      const i = Math.min(linhas.length - 1, Math.floor((t - inicioConversa.get(chave)) / (passo || 1700)));
      const [quem, texto] = linhas[i];
      if (i > 0) { const [qa, ta] = linhas[i - 1]; dizer(qa === "E" ? eleitor : qa, ta, false); }
      dizer(quem === "E" ? eleitor : quem, texto, true);
    };
    const policialAbordando = () => [...vivos.keys()].find((k) => k.startsWith("pol-") && parado(k) &&
                                                                 vivos.get(k).dados.zona === "policia_externo");
    for (const p of cena.pessoas) {
      if (!parado(p.id)) continue;
      if (p.tipo === "eleitor") {
        if (p.acao === "discutindo") roteiro(p.id + ":disc", ROTEIROS.discutindo, p.id, 1500);
        else if (ROTEIROS[p.acao] && p.zona !== "fila" && p.zona !== "assento") roteiro(p.id + ":" + p.acao, ROTEIROS[p.acao], p.id);
      } else if (p.tipo === "manifestante") {
        const pol = policialAbordando();
        if (p.acao === "panfletando") {
          const linhas = [[p.id, "Vote em… !"], ["apoio-1", "Pedir voto aqui não pode!"], [p.id, "Só estou conversando."], ["apoio-1", "Vou avisar a Presidência."]];
          if (pol) linhas.push([pol, "Bom dia. Vamos conversar aqui."], [p.id, "Não fiz nada demais."], [pol, "Pedir voto hoje é proibido."], [pol, "Recolha o material, por favor."]);
          roteiro(p.id + (pol ? ":pol" : ""), linhas, p.id, 1800);
        } else if (p.acao === "adesivo") {
          roteiro(p.id + ":ades", [[p.id, "(adesivo, em silêncio)"], ["apoio-1", "Adesivo pode, sem pedir voto."]], p.id, 2000);
        } else if (p.acao === "indo_embora") {
          roteiro(p.id + ":fim", [[pol || "apoio-1", "Pode seguir. Fica o registro."], [p.id, "Já vou embora."]], p.id, 1600);
        } else if (p.acao === "viatura") {
          const agente = [...vivos.keys()].find((k) => k.startsWith("pol-"));
          roteiro(p.id + ":vtr", [[agente || p.id, "Vamos registrar na delegacia."], [p.id, "Tudo bem…"], [agente || p.id, "Entre na viatura, por favor."]], p.id, 1500);
        }
      } else if (p.tipo === "tecnico") {
        roteiro(p.id + ":" + p.acao, p.acao === "consertando"
          ? [[p.id, "Vou trocar pela contingência."], [PRES, "Os fiscais acompanham."], [p.id, "Lacres repostos e assinados."]]
          : [[p.id, "Técnico a caminho!"]], p.id, 2000);
      } else if (p.tipo === "policial" && p.zona === "policia_porta") {
        roteiro("porta:" + p.id, [[p.id, "Chamaram a polícia?"], [PRES, "Sim, houve uma ocorrência."], [p.id, "Tudo em ordem agora?"], [SEC, "Agora sim, obrigado."]], p.id, 1900);
      } else if (p.tipo === "mesa" && p.acao === "religando") {
        roteiro(p.id + ":relig", [[PRES, "A urna travou. Vou desligar…"], [PRES, "…e religar com os fiscais."], ["fiscal-1", "Acompanhando."]], p.id, 1800);
      } else if (p.tipo === "mesa" && p.acao === "senhas") {
        roteiro("senhas", [[SEC, "17h! Senha para quem está na fila."], [SEC, "Ninguém mais entra."]], p.id, 2200);
      }
    }
    for (const k of [...inicioConversa.keys()]) if (!ativos.has(k)) inicioConversa.delete(k);
    if (reduzido) return out;
    // conversa leve na fila: só ambientação, sem tema político
    const naFila = cena.pessoas.filter((p) => p.zona === "fila" && p.vaga < 9 && parado(p.id));
    if (naFila.length >= 2) {
      const ciclo = Math.floor(t / 5200), fase = (t % 5200) / 5200;
      const a = naFila[ciclo % (naFila.length - 1)], b = naFila.find((q) => q.vaga === a.vaga + 1);
      const [pergunta, resposta] = CONVERSA_FILA[ciclo % CONVERSA_FILA.length];
      if (b && fase < 0.85) { dizer(a.id, pergunta, fase < 0.45); if (fase >= 0.45) dizer(b.id, resposta, true); }
    }
    const sentados = cena.pessoas.filter((p) => p.zona === "assento" && parado(p.id));
    if (sentados.length && (t % 9000) < 2500) dizer(sentados[Math.floor(t / 9000) % sentados.length].id, "Que bom ter assento!", true);
    return out;
  }

  // ------------------------------------------------------------- animação
  function atualizar(dt) {
    const parado = Math.abs(carro.x - carro.alvo) < 0.5;
    if (!parado) {
      const passo = (reduzido ? 999 : 0.09) * dt;
      carro.x += Math.sign(carro.alvo - carro.x) * Math.min(passo, Math.abs(carro.alvo - carro.x));
    }
    const policiaVisivel = [...sprites.values()].some((s) => s.dados.tipo === "policial");
    if (!policiaVisivel && !(cena && cena.viatura)) carro.alvo = -70;
    for (const [id, s] of sprites) {
      if (s.aguardaCarro) {
        if (Math.abs(carro.x - carro.alvo) < 0.5 && carro.alvo > 0) {
          s.aguardaCarro = false; s.x = carro.x + 28; s.y = MEIO;
          s.rota = caminho([s.x, s.y], s.alvo, s.dados.zona); s.vel = 0.04;
        }
        continue;
      }
      if (!s.rota.length) { if (s.saindo) sprites.delete(id); continue; }
      let passo = (s.vel || 0.05) * dt;
      while (passo > 0 && s.rota.length) {
        const [tx, ty] = s.rota[0];
        const d = Math.hypot(tx - s.x, ty - s.y);
        if (Math.abs(tx - s.x) > 0.3) s.dir = tx > s.x ? 1 : -1;
        if (d <= passo) { s.x = tx; s.y = ty; s.rota.shift(); passo -= d; }
        else { s.x += (tx - s.x) / d * passo; s.y += (ty - s.y) / d * passo; passo = 0; }
      }
    }
  }

  let anterior = performance.now();
  function quadro(t) {
    const dt = Math.min(100, t - anterior); anterior = t;
    atualizar(dt);
    const minuto = cena ? Math.floor(cena.minuto_do_dia / 10) * 10 : 480;
    if (!fundo || minuto !== fundoMinuto) { fundo = desenharFundo(minuto); fundoMinuto = minuto; }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(fundo, 0, 0);
    ctx.setTransform(escala, 0, 0, escala, 0, 0);
    desenharPainelChamada();
    if (cena) desenharRelogio(cena.minuto_do_dia);
    desenharVentilador(t);
    desenharViatura(t);
    // camadas com profundidade: props e pessoas ordenados pelo y dos pés
    const camadas = [
      { y: TRAS - 0.5, f: desenharBanco }, { y: 195.5, f: desenharCadeirasMesa }, { y: 197, f: () => desenharMesa(t) },
      { y: 186, f: desenharUrnaFundo }, { y: 198, f: desenharBiombo },
    ];
    const visiveis = [...sprites.values()].filter((s) => !s.aguardaCarro);
    for (const s of visiveis) camadas.push({ y: s.y, f: () => desenharSprite(s, t) });
    camadas.sort((a, b) => a.y - b.y);
    for (const c of camadas) c.f();
    desenharPortao();
    for (const s of visiveis) desenharRotulo(s);
    ocupados = [];
    const dialogo = falas(t);
    const ordem = [...visiveis].sort((a, b) => Number((dialogo.get(a.dados.id) || [0, false])[1]) -
                                              Number((dialogo.get(b.dados.id) || [0, false])[1]));
    for (const s of ordem) desenharBalao(s, t, dialogo.get(s.dados.id));
    const fora = cena ? cena.fila_total - NA_FILA_CORREDOR - NA_CALCADA - cena.pessoas.filter((p) => p.zona === "assento").length : 0;
    if (fora > 0) caixa(ctx, `+${fora} AGUARDANDO`, 40, 156, { centro: true, fundo: "#ffd34d" });
    if (cena && cena.identificacao.estado === "INTERROMPIDO") caixa(ctx, "MESA PAUSADA", 300, 166, { centro: true, fundo: "#ff7a7a" });
    if (cena && cena.urna.estado === "INTERROMPIDO") caixa(ctx, "URNA PARADA", 365, 128, { centro: true, fundo: "#ff7a7a" });
    requestAnimationFrame(quadro);
  }
  requestAnimationFrame(quadro);

  canvas.addEventListener("click", (ev) => {
    const b = canvas.getBoundingClientRect();
    const x = (ev.clientX - b.left) / b.width * W, y = (ev.clientY - b.top) / b.height * H;
    let melhor = null, dmin = 12;
    for (const s of sprites.values()) {
      if (s.dados.tipo !== "eleitor") continue;
      const d = Math.hypot(s.x - x, s.y - 12 - y);
      if (d < dmin) { dmin = d; melhor = s.dados.id; }
    }
    if (melhor) enviar("streamlit:setComponentValue", { value: melhor, dataType: "json" });
  });

  redimensionar();
  ajustarAltura();
})();
