"""report.html: recortes, curva de brilho, nota e situação no TNS."""

from __future__ import annotations

import html
from typing import Any

CABECALHO = """<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>CacaSN</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:-apple-system,system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:16px}
.c{display:flex;flex-wrap:wrap;gap:12px;align-items:center;background:#1c1c1c;border-radius:8px;
padding:10px;margin:8px 0}
.c img{height:120px;width:120px;image-rendering:pixelated;border-radius:4px;background:#000}
.n{font-size:28px;font-weight:700;min-width:70px;text-align:center}a{color:#7cf}small{color:#999}
.novo{color:#5f5;font-weight:700}.velho{color:#999}</style>
<h1>CacaSN — candidatos a supernova (ZTF e Rubin)</h1>
<p><small>Alertas do ZTF via ALeRCE. Recortes: ciência · referência · diferença.
Curva: g verde, r vermelho, mais alto = mais brilhante.
Para reportar, o candidato precisa NÃO estar no TNS; veja o README.</small></p>"""


def mini_curva(curva: list[tuple[float, int, float]]) -> str:
    """SVG pequeno da curva de brilho (g verde, r vermelho; mais alto = mais brilhante)."""
    if not curva:
        return ""
    W, H, m = 220, 90, 8
    ts = [c[0] for c in curva]
    ms = [c[2] for c in curva]
    t0, t1 = min(ts), max(ts)
    m0, m1 = min(ms) - 0.2, max(ms) + 0.2
    pts = []
    for t, f, mg in curva:
        x = m + (t - t0) / ((t1 - t0) or 1) * (W - 2 * m)
        y = m + (mg - m0) / ((m1 - m0) or 1) * (H - 2 * m)
        cor = "#3c3" if f == 1 else "#e44"
        pts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="4" fill="{cor}"/>')
    return (
        f'<svg width="{W}" height="{H}" style="background:#000;border-radius:4px">{"".join(pts)}'
        f'<text x="4" y="{H - 4}" fill="#888" font-size="10">{t1 - t0:.1f} d</text></svg>'
    )


def cartao(it: dict[str, Any]) -> str:
    imgs = "".join(
        f'<img src="{html.escape(it["stamps"][t])}" loading="lazy" title="{t}">'
        for t in ("science", "template", "difference")
        if t in it["stamps"]
    )
    cls = "novo" if it["conhecido"].startswith("NÃO") else "velho"
    ra, dec = it["ra"], it["dec"]
    tns = f"https://www.wis-tns.org/search?ra={ra:.5f}&amp;decl={dec:.5f}&amp;radius=5&amp;coords_unit=arcsec"
    galaxia = (
        f"https://legacysurvey.org/viewer?ra={ra:.5f}&amp;dec={dec:.5f}&amp;layer=ls-dr10&amp;zoom=16&amp;mark={ra:.5f},{dec:.5f}"
    )
    return (
        f'<div class="c"><div class="n">{it["nota"]}</div>{imgs}{mini_curva(it["curva"])}<div>'
        f"<b>{it['oid']}</b> · mag {it['mag']:.2f} · {it['idade']} dias · SN {it['prob']} · drb {it['drb']}<br>"
        f"<small>{html.escape(', '.join(it['motivos']))}</small><br>"
        f'<span class="{cls}">{html.escape(it["conhecido"])}</span><br>'
        f"<small>RA {ra:.5f} Dec {dec:+.5f}</small> · "
        f'<a href="{html.escape(it.get("link") or "https://alerce.online/object/" + it["oid"])}" target="_blank">'
        f"{'Fink' if it.get('fonte') == 'rubin' else 'ALeRCE'}</a> · "
        f'<a href="{tns}" target="_blank">TNS</a> · '
        f'<a href="{galaxia}" target="_blank">galáxia</a>'
        f"</div></div>"
    )


def relatorio(itens: list[dict[str, Any]]) -> str:
    return "\n".join([CABECALHO] + [cartao(it) for it in sorted(itens, key=lambda x: -x["nota"])])
