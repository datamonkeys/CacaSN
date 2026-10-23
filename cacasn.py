#!/usr/bin/env python3
"""CacaSN: caçador de supernovas nos alertas públicos do ZTF (via ALeRCE).

Busca candidatos a supernova detectados pela primeira vez nos últimos dias,
descarta o que parece estrela variável ou artefato, confere no TNS se já foi
reportado (precisa de chave, ver README) e gera report.html com os recortes
ciência/referência/diferença e a curva de brilho.

uso: python3 cacasn.py [--dias 3] [--prob 0.5]
"""
import argparse, html, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.alerce.online/ztf/v1"
STAMP = "https://avro.alerce.online/get_stamp"
AQUI = os.path.dirname(os.path.abspath(__file__))
HDR = {"User-Agent": "CacaSN/0.1"}


def get_json(url, tentativas=3):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=60) as r:
                return json.load(r)
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(2)


def mjd_agora():
    return time.time() / 86400 + 40587


def candidatos(dias, prob):
    q = urllib.parse.urlencode(dict(classifier="stamp_classifier", **{"class": "SN"}, probability=prob,
                                    firstmjd=f"{mjd_agora() - dias:.3f}", page_size=500,
                                    order_by="probability", order_mode="DESC"))
    return get_json(f"{API}/objects/?{q}")["items"]


# --- já é conhecido? ------------------------------------------------------

def vizier(fonte, ra, dec, raio, cols):
    url = (f"https://vizier.cds.unistra.fr/viz-bin/asu-tsv?-source={fonte}&-c={ra:.6f}%20{dec:+.6f}"
           f"&-c.rs={raio}&-out={cols}&-out.max=5&-sort=_r")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30) as r:
            linhas = [l.split("\t") for l in r.read().decode().splitlines() if l and not l.startswith("#")]
        return [l for l in linhas[3:] if len(l) == len(cols.split(","))]
    except Exception:
        return None


def estrela_gaia(ra, dec):
    """Estrela do Gaia com paralaxe ou movimento significativo em 1.5": a
    'supernova' quase certamente é a estrela variando de brilho."""
    for src, plx, eplx, pmra, pmde in vizier("I/355/gaiadr3", ra, dec, 1.5, "Source,Plx,e_Plx,pmRA,pmDE") or []:
        try:
            if float(plx) > 3 * float(eplx) or (float(pmra) ** 2 + float(pmde) ** 2) ** 0.5 > 5:
                return src.strip()
        except ValueError:
            continue
    return None


def tns_carregar():
    p = os.path.join(AQUI, "tns.json")
    return json.load(open(p)) if os.path.exists(p) else None


_tns_trava = __import__("threading").Lock()
_tns_ultima = [0.0]


def tns_busca(cfg, ra, dec, tentativas=4):
    """Objetos do TNS a até 3" (precisa de um bot do TNS: tns.json).
    A busca por região aceita 10 por minuto: uma por vez, a cada 6.5 s, e
    no 429 espera o tempo que o cabeçalho manda."""
    marker = json.dumps({"tns_id": cfg["bot_id"], "type": "bot", "name": cfg["bot_name"]})
    dados = urllib.parse.urlencode({"api_key": cfg["api_key"],
                                    "data": json.dumps({"ra": f"{ra:.6f}", "dec": f"{dec:.6f}",
                                                        "radius": "3", "units": "arcsec"})}).encode()
    for i in range(tentativas):
        with _tns_trava:
            espera = 6.5 - (time.time() - _tns_ultima[0])
            if espera > 0:
                time.sleep(espera)
            try:
                req = urllib.request.Request("https://www.wis-tns.org/api/get/search", data=dados,
                                             headers={"User-Agent": "tns_marker" + marker})
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.load(r)
                return [f'{o.get("prefix", "")} {o["objname"]}'.strip() for o in resp.get("data", [])]
            except urllib.error.HTTPError as e:
                if e.code != 429 or i == tentativas - 1:
                    raise
                time.sleep(int(e.headers.get("x-cone-rate-limit-reset", "30")) + 1)
            finally:
                _tns_ultima[0] = time.time()


# --- avaliação -------------------------------------------------------------

def avaliar(obj, tns):
    oid = obj["oid"]
    dets = get_json(f"{API}/objects/{oid}/detections")
    dets = [d for d in dets if d.get("isdiffpos", 1) in (1, "t")]
    ra, dec = obj["meanra"], obj["meandec"]
    drb = max([d.get("drb") or 0 for d in dets] or [0])
    noites = len({int(d["mjd"]) for d in dets})
    filtros = len({d["fid"] for d in dets})
    mags = sorted(dets, key=lambda d: d["mjd"])
    subindo = len(mags) >= 2 and mags[-1]["magpsf"] < mags[0]["magpsf"] - 0.1
    distnr = min([d.get("distnr") or 99 for d in dets] or [99])

    motivos, nota = [], obj["probability"] * 10
    nota += 5 * drb
    if noites >= 2:
        nota += 3; motivos.append(f"{noites} noites")  # asteroide não volta no mesmo lugar
    elif len(dets) >= 2:
        nota += 1; motivos.append("2+ detecções na mesma noite")
    else:
        nota -= 3; motivos.append("detecção única")
    if filtros >= 2:
        nota += 1; motivos.append("g e r")
    if subindo:
        nota += 2; motivos.append("subindo de brilho")
    if obj.get("stellar"):
        nota -= 4; motivos.append("ALeRCE acha que é estelar")
    gaia = estrela_gaia(ra, dec)
    if gaia:
        nota -= 8; motivos.append(f"em cima da estrela Gaia {gaia} (variável?)")
    if distnr < 0.5:
        motivos.append("no centro de uma fonte (núcleo de galáxia ou estrela)")

    conhecido = None
    if tns:
        try:
            nomes = tns_busca(tns, ra, dec)
            conhecido = ("TNS: " + ", ".join(nomes)) if nomes else "NÃO está no TNS — dá para reportar"
        except Exception as e:
            conhecido = f"TNS não respondeu ({e.__class__.__name__})"
    else:
        conhecido = "TNS não consultado (falta tns.json)"

    com_stamp = [d for d in mags if d.get("has_stamp")]
    stamps = {}
    if com_stamp:
        c = com_stamp[0]["candid"]
        stamps = {t: f"{STAMP}?oid={oid}&candid={c}&type={t}&format=png" for t in ("science", "template", "difference")}
    curva = [(round(d["mjd"] - mags[0]["mjd"], 2), d["fid"], round(d["magpsf"], 2)) for d in mags]
    return dict(oid=oid, ra=ra, dec=dec, nota=round(nota, 2), prob=round(obj["probability"], 2),
                drb=round(drb, 3), motivos=motivos, conhecido=conhecido, stamps=stamps, curva=curva,
                idade=round(mjd_agora() - obj["firstmjd"], 2), mag=mags[-1]["magpsf"] if mags else None)


def _seguro(obj, tns):
    try:
        return avaliar(obj, tns)
    except Exception as e:
        print(f"  erro em {obj['oid']}: {e}", file=sys.stderr)
        return None


# --- relatório -------------------------------------------------------------

def mini_curva(curva):
    """SVG pequeno da curva de brilho (g verde, r vermelho; mais alto = mais brilhante)."""
    if not curva:
        return ""
    W, H, m = 220, 90, 8
    ts = [c[0] for c in curva]; ms = [c[2] for c in curva]
    t0, t1 = min(ts), max(ts) or 1
    m0, m1 = min(ms) - 0.2, max(ms) + 0.2
    pts = []
    for t, f, mg in curva:
        x = m + (t - t0) / ((t1 - t0) or 1) * (W - 2 * m)
        y = m + (mg - m0) / ((m1 - m0) or 1) * (H - 2 * m)
        cor = "#3c3" if f == 1 else "#e44"
        pts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="4" fill="{cor}"/>')
    return (f'<svg width="{W}" height="{H}" style="background:#000;border-radius:4px">{"".join(pts)}'
            f'<text x="4" y="{H - 4}" fill="#888" font-size="10">{t1 - t0:.1f} d</text></svg>')


def relatorio(itens):
    p = ["""<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>CacaSN</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:-apple-system,system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:16px}
.c{display:flex;flex-wrap:wrap;gap:12px;align-items:center;background:#1c1c1c;border-radius:8px;padding:10px;margin:8px 0}
.c img{height:120px;width:120px;image-rendering:pixelated;border-radius:4px;background:#000}
.n{font-size:28px;font-weight:700;min-width:70px;text-align:center}a{color:#7cf}small{color:#999}
.novo{color:#5f5;font-weight:700}.velho{color:#999}</style>
<h1>CacaSN — candidatos a supernova</h1>
<p><small>Alertas do ZTF via ALeRCE. Recortes: ciência · referência · diferença. Curva: g verde, r vermelho, mais alto = mais brilhante.
Para reportar, o candidato precisa NÃO estar no TNS; veja o README.</small></p>"""]
    for it in sorted(itens, key=lambda x: -x["nota"]):
        imgs = "".join(f'<img src="{it["stamps"][t]}" loading="lazy" title="{t}">' for t in ("science", "template", "difference") if t in it["stamps"])
        cls = "novo" if it["conhecido"].startswith("NÃO") else "velho"
        p.append(
            f'<div class="c"><div class="n">{it["nota"]}</div>{imgs}{mini_curva(it["curva"])}<div>'
            f'<b>{it["oid"]}</b> · mag {it["mag"]:.2f} · {it["idade"]} dias · SN {it["prob"]} · drb {it["drb"]}<br>'
            f'<small>{html.escape(", ".join(it["motivos"]))}</small><br>'
            f'<span class="{cls}">{html.escape(it["conhecido"])}</span><br>'
            f'<small>RA {it["ra"]:.5f} Dec {it["dec"]:+.5f}</small> · '
            f'<a href="https://alerce.online/object/{it["oid"]}" target="_blank">ALeRCE</a> · '
            f'<a href="https://www.wis-tns.org/search?ra={it["ra"]:.5f}&decl={it["dec"]:.5f}&radius=5&coords_unit=arcsec" target="_blank">TNS</a> · '
            f'<a href="https://legacysurvey.org/viewer?ra={it["ra"]:.5f}&dec={it["dec"]:.5f}&layer=ls-dr10&zoom=16&mark={it["ra"]:.5f},{it["dec"]:.5f}" target="_blank">galáxia</a>'
            f'</div></div>')
    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=float, default=3, help="primeira detecção há no máximo N dias")
    ap.add_argument("--prob", type=float, default=0.5, help="probabilidade mínima de SN no stamp classifier")
    args = ap.parse_args()
    tns = tns_carregar()
    objs = candidatos(args.dias, args.prob)
    print(f"{len(objs)} candidatos nos últimos {args.dias} dias", file=sys.stderr)
    with ThreadPoolExecutor(6) as ex:
        itens = [r for r in ex.map(lambda o: _seguro(o, tns), objs) if r]
    for it in sorted(itens, key=lambda x: -x["nota"])[:5]:
        print(f'  {it["nota"]:6.2f} {it["oid"]} mag {it["mag"]:.1f} {", ".join(it["motivos"])} | {it["conhecido"]}', file=sys.stderr)
    json.dump(itens, open(os.path.join(AQUI, "resultados.json"), "w"), indent=1)
    open(os.path.join(AQUI, "report.html"), "w").write(relatorio(itens))
    print(os.path.join(AQUI, "report.html"))


if __name__ == "__main__":
    main()
