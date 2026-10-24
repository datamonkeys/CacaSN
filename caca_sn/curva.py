"""Medidas da curva de luz: velocidade de subida do brilho."""

from __future__ import annotations


def taxa_subida(curva: list[tuple[float, int, float]], minimo_dias: float = 0.3) -> float | None:
    """Maior subida de brilho em magnitudes por dia, olhando cada filtro separado
    (+ = ficando mais brilhante). None se nenhum filtro tem 2 pontos separados
    por pelo menos `minimo_dias`."""
    melhor = None
    for fid in {f for _, f, _ in curva}:
        pontos = sorted((t, m) for t, f, m in curva if f == fid)
        dt = pontos[-1][0] - pontos[0][0] if len(pontos) >= 2 else 0
        if dt >= minimo_dias:
            taxa = (pontos[0][1] - pontos[-1][1]) / dt
            melhor = taxa if melhor is None else max(melhor, taxa)
    return melhor


def motivo_subida(curva: list[tuple[float, int, float]], idade: float) -> str | None:
    """Texto para o relatório. Supernova jovem sobe ~0.1-0.3 mag/dia; > 0.5 é rápido."""
    taxa = taxa_subida(curva)
    if taxa is None or taxa <= 0.02:
        return None
    rapido = " — rápido!" if taxa > 0.5 else ""
    jovem = " (jovem e subindo)" if idade < 5 else ""
    return f"subindo {taxa:.2f} mag/dia{rapido}{jovem}"


# os objetos do Rubin reportados ao TNS (julho/2026) tinham a curva em até 18 dias;
# os não reportados com 145-248 dias eram fontes que variam há meses (núcleos ativos)
DURACAO_VARIAVEL = 60


def duracao(curva: list[tuple[float, int, float]]) -> float:
    return max((t for t, _, _ in curva), default=0.0) - min((t for t, _, _ in curva), default=0.0)
