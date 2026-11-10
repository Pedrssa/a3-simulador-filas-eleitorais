"""Componente Streamlit (v1, HTML + JS puros) que hospeda o Canvas 8 bits.

O iframe persiste entre reruns (mesma key), então a animação interpola
de um estado ao próximo em vez de recomeçar a cada atualização.
"""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_PASTA = Path(__file__).resolve().parents[2] / "assets" / "cena8bit"
_cena8bit = components.declare_component("cena8bit", path=str(_PASTA))


def cena_8bit(cena: dict, *, som: bool, reduzido: bool, transicao_ms: int, dialogos: bool = False,
              key: str = "cena") -> str | None:
    """Desenha a cena e devolve o ID clicado (ou None). `dialogos` liga as conversas ilustrativas."""
    return _cena8bit(cena=cena, som=som, reduzido=reduzido, transicao_ms=transicao_ms, dialogos=dialogos,
                     key=key, default=None)
