/* Fonte bitmap 5x7 (maiúsculas, dígitos, pontuação e acentos do português).
 * Cada glifo tem 7 linhas de 5 bits (bit 0x10 = coluna da esquerda). Desenhada com fillRect em
 * coordenadas inteiras de tela: fica nítida em qualquer escala, sem anti-aliasing.
 */
(function () {
  "use strict";
  const G = {
    A: [14, 17, 17, 31, 17, 17, 17], B: [30, 17, 17, 30, 17, 17, 30], C: [14, 17, 16, 16, 16, 17, 14],
    D: [30, 17, 17, 17, 17, 17, 30], E: [31, 16, 16, 30, 16, 16, 31], F: [31, 16, 16, 30, 16, 16, 16],
    G: [14, 17, 16, 23, 17, 17, 15], H: [17, 17, 17, 31, 17, 17, 17], I: [14, 4, 4, 4, 4, 4, 14],
    J: [7, 2, 2, 2, 2, 18, 12], K: [17, 18, 20, 24, 20, 18, 17], L: [16, 16, 16, 16, 16, 16, 31],
    M: [17, 27, 21, 21, 17, 17, 17], N: [17, 17, 25, 21, 19, 17, 17], O: [14, 17, 17, 17, 17, 17, 14],
    P: [30, 17, 17, 30, 16, 16, 16], Q: [14, 17, 17, 17, 21, 18, 13], R: [30, 17, 17, 30, 20, 18, 17],
    S: [15, 16, 16, 14, 1, 1, 30], T: [31, 4, 4, 4, 4, 4, 4], U: [17, 17, 17, 17, 17, 17, 14],
    V: [17, 17, 17, 17, 17, 10, 4], W: [17, 17, 17, 21, 21, 21, 10], X: [17, 17, 10, 4, 10, 17, 17],
    Y: [17, 17, 10, 4, 4, 4, 4], Z: [31, 1, 2, 4, 8, 16, 31],
    "0": [14, 17, 19, 21, 25, 17, 14], "1": [4, 12, 4, 4, 4, 4, 14], "2": [14, 17, 1, 2, 4, 8, 31],
    "3": [31, 2, 4, 2, 1, 17, 14], "4": [2, 6, 10, 18, 31, 2, 2], "5": [31, 16, 30, 1, 1, 17, 14],
    "6": [6, 8, 16, 30, 17, 17, 14], "7": [31, 1, 2, 4, 8, 8, 8], "8": [14, 17, 17, 14, 17, 17, 14],
    "9": [14, 17, 17, 15, 1, 2, 12],
    " ": [0, 0, 0, 0, 0, 0, 0], ".": [0, 0, 0, 0, 0, 12, 12], ",": [0, 0, 0, 0, 12, 4, 8],
    ":": [0, 12, 12, 0, 12, 12, 0], "!": [4, 4, 4, 4, 4, 0, 4], "?": [14, 17, 1, 2, 4, 0, 4],
    "-": [0, 0, 0, 31, 0, 0, 0], "+": [0, 4, 4, 31, 4, 4, 0], "#": [10, 10, 31, 10, 31, 10, 10],
    "(": [2, 4, 8, 8, 8, 4, 2], ")": [8, 4, 2, 2, 2, 4, 8], "/": [1, 2, 2, 4, 8, 8, 16],
    "'": [4, 4, 8, 0, 0, 0, 0], "º": [14, 10, 14, 0, 14, 0, 0], "ª": [14, 10, 14, 0, 14, 0, 0],
    "▶": [8, 12, 14, 15, 14, 12, 8], "▼": [0, 31, 31, 14, 14, 4, 0], "·": [0, 0, 0, 12, 12, 0, 0],
    "…": [0, 0, 0, 0, 0, 0, 21], "=": [0, 0, 31, 0, 31, 0, 0], "%": [24, 25, 2, 4, 8, 19, 3],
  };
  const MARCAS = { agudo: [2, 4], grave: [8, 4], circ: [4, 10], til: [13, 22] };
  const ACENTOS = {
    "Á": ["A", "agudo"], "À": ["A", "grave"], "Â": ["A", "circ"], "Ã": ["A", "til"],
    "É": ["E", "agudo"], "Ê": ["E", "circ"], "Í": ["I", "agudo"], "Ó": ["O", "agudo"],
    "Ô": ["O", "circ"], "Õ": ["O", "til"], "Ú": ["U", "agudo"], "Ç": ["C", "cedilha"],
  };
  const AVANCO = 6, ALTURA = 10; // 2 linhas de acento + 7 do glifo + 1 de cedilha

  /** Largura em pixels de fonte (multiplique por px para pixels de tela). */
  function largura(s) { return Math.max(0, String(s).length * AVANCO - 1); }

  /** Desenha s com o canto superior esquerdo em (x, y) PIXELS DE TELA; cada pixel da fonte = px pixels. */
  function desenhar(ctx, s, x, y, px, cor) {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = cor;
    x = Math.round(x); y = Math.round(y);
    for (const bruto of String(s).toUpperCase()) {
      let ch = bruto, marca = null;
      if (ACENTOS[ch]) { marca = ACENTOS[ch][1]; ch = ACENTOS[ch][0]; }
      const g = G[ch] || G["?"];
      for (let r = 0; r < 7; r++) {
        const bits = g[r];
        for (let c = 0; c < 5; c++) if (bits & (16 >> c)) ctx.fillRect(x + c * px, y + (r + 2) * px, px, px);
      }
      if (marca === "cedilha") ctx.fillRect(x + 2 * px, y + 9 * px, px, px);
      else if (marca) {
        MARCAS[marca].forEach((bits, r) => {
          for (let c = 0; c < 5; c++) if (bits & (16 >> c)) ctx.fillRect(x + c * px, y + r * px, px, px);
        });
      }
      x += AVANCO * px;
    }
    ctx.restore();
  }

  window.FontePixel = { desenhar, largura, ALTURA };
})();
