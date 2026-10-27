"""Gera sql/logs.sql de exemplo e imprime a comparação de políticas no cenário de starvation.

Uso:  python scripts/gerar_exemplos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from secao8bit.application.comparacao import comparar  # noqa: E402
from secao8bit.application.config import config_do_cenario  # noqa: E402
from secao8bit.application.motor import MotorSimulacao  # noqa: E402
from secao8bit.infrastructure.exportador_sql import exportar_logs, salvar, validar_importacao  # noqa: E402
from secao8bit.infrastructure.repositorio_sqlite import RepositorioAuditoria  # noqa: E402


def main() -> None:
    repo = RepositorioAuditoria(":memory:")
    motor = MotorSimulacao(config_do_cenario("demo_7min"), repo, execucao_id="EX-EXEMPLO-demo_7min-seed2026")
    motor.executar_tudo()
    sql = exportar_logs(repo, motor.execucao_id)
    destino = salvar(RAIZ / "sql" / "logs.sql", sql)
    print(f"{destino.relative_to(RAIZ)}: {len(motor.log)} eventos; validação: {validar_importacao(repo, motor.execucao_id, sql)}")

    for cenario in ("starvation", "demo_7min"):
        print(f"\nComparação no cenário '{cenario}' (mesma carga):")
        print(f"{'variante':45s} {'comum máx':>9s} {'comum p95':>9s} {'pref máx':>8s} {'doador máx':>10s} {'80+ máx':>7s} {'viol.SLA':>8s}")
        for r in comparar(config_do_cenario(cenario)):
            g = {x["grupo"]: x for x in r.grupos}
            print(f"{r.nome:45s} {g['Comum']['máximo (incl.)']:9.1f} {g['Comum']['p95 (incl.)']:9.1f} "
                  f"{g['Preferencial']['máximo (incl.)']:8.1f} {g['Doador(a) de sangue']['máximo (incl.)']:10.1f} "
                  f"{g['Mais de 80 anos']['máximo (incl.)']:7.1f} {r.resumo['violacoes_sla']:8d}   carga={r.assinatura_carga}")


if __name__ == "__main__":
    main()
