import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from secao8bit.domain.eleitor import Eleitor, EstadoEleitor  # noqa: E402
from secao8bit.domain.prioridade import PerfilPrioridade  # noqa: E402

ELEICAO = date(2026, 10, 4)


@pytest.fixture
def novo_eleitor():
    """Fábrica de eleitores de teste já classificados."""
    contador = {"n": 0}

    def fabricar(perfil: PerfilPrioridade | None = None, chegada: float = 0.0, estado=EstadoEleitor.AGUARDANDO):
        contador["n"] += 1
        perfil = perfil or PerfilPrioridade(date(1990, 1, 1))
        e = Eleitor(id=f"T-{contador['n']:03d}", apelido="Teste", perfil=perfil,
                    classificacao=perfil.classificar(ELEICAO), chegada=chegada,
                    seq_chegada=contador["n"], duracoes={})
        e.estado = estado
        return e

    return fabricar
