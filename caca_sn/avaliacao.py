"""Candidatos da ALeRCE e a nota de cada um."""

from __future__ import annotations

import urllib.parse
from typing import Any

from . import catalogos
from .rede import get_json, mjd_agora

API = "https://api.alerce.online/ztf/v1"
STAMP = "https://avro.alerce.online/get_stamp"


def candidatos(dias: float, prob: float, a_partir: float = 0, max_paginas: int = 20) -> list[dict[str, Any]]:
    """Candidatos com primeira detecção entre `dias` e `a_partir` dias atrás. A ALeRCE
    devolve até 500 por página: percorre as páginas até acabar (ou `max_paginas`)."""
    filtros = [
        ("classifier", "stamp_classifier"),
        ("class", "SN"),
        ("probability", prob),
        ("firstmjd", f"{mjd_agora() - dias:.3f}"),
        ("page_size", 500),
        ("order_by", "probability"),
        ("order_mode", "DESC"),
    ]
    if a_partir > 0:
        filtros.append(("firstmjd", f"{mjd_agora() - a_partir:.3f}"))  # dois firstmjd = intervalo
    itens: list[dict[str, Any]] = []
    for pagina in range(1, max_paginas + 1):
        lote = get_json(f"{API}/objects/?{urllib.parse.urlencode(filtros + [('page', pagina)])}").get("items", [])
        itens += lote
        if len(lote) < 500:
            break
    return itens


def subindo_de_brilho(dets: list[dict[str, Any]]) -> bool:
    """Brilho subindo em algum filtro: compara só pontos do mesmo filtro, porque
    g e r têm magnitudes diferentes e misturar os dois inventa subida."""
    for fid in {d["fid"] for d in dets}:
        f = sorted((d for d in dets if d["fid"] == fid), key=lambda d: d["mjd"])
        if len(f) >= 2 and f[-1]["magpsf"] < f[0]["magpsf"] - 0.1:
            return True
    return False


def classificador_2025(oid: str) -> dict[str, float]:
    """Probabilidades do classificador novo da ALeRCE (vazio se falhar)."""
    try:
        return {
            p["class_name"]: p["probability"]
            for p in get_json(f"{API}/objects/{oid}/probabilities")
            if p["classifier_name"] == "stamp_classifier_2025_beta"
        }
    except Exception:
        return {}


def pontuar(obj: dict[str, Any], dets: list[dict[str, Any]], novo: dict[str, float], gaia: Any) -> tuple[float, list[str]]:
    """Nota e motivos. Medida contra o que os grupos profissionais reportaram ao
    TNS (97 candidatos, out/2026): AUC 0.96."""
    motivos: list[str] = []
    nota = obj["probability"] * 10
    # o classificador 2025 separa melhor SN de núcleo ativo (AUC 0.79 contra 0.71)
    nota += 10 * novo.get("SN", 0) - 5 * novo.get("AGN", 0)
    if novo:
        top = max(novo, key=lambda k: novo[k])
        motivos.append(f"classif. 2025: {top} {novo[top]:.2f}")
    # muito mais detecções no histórico que no alerta = fonte antiga variando
    hist = int(obj.get("ndethist") or 0)
    if hist > len(dets) + 5:
        nota -= 5
        motivos.append(f"{hist} detecções no histórico (fonte antiga)")
    nota += 5 * max(d.get("drb") or 0 for d in dets)
    noites = len({int(d["mjd"]) for d in dets})
    if noites >= 2:
        nota += 3  # asteroide não volta no mesmo lugar
        motivos.append(f"{noites} noites")
    elif len(dets) >= 2:
        nota += 1
        motivos.append("2+ detecções na mesma noite")
    else:
        nota -= 3
        motivos.append("detecção única")
    if len({d["fid"] for d in dets}) >= 2:
        nota += 1
        motivos.append("g e r")
    if subindo_de_brilho(dets):
        nota += 2
        motivos.append("subindo de brilho")
    if obj.get("stellar"):
        nota -= 4
        motivos.append("ALeRCE acha que é estelar")
    if gaia is catalogos.SEM_RESPOSTA:
        motivos.append("Gaia não respondeu (estrela não descartada)")
    elif gaia:
        nota -= 8
        motivos.append(f"em cima da estrela Gaia {gaia} (variável?)")
    # distnr = -999 no ZTF quando não há fonte por perto
    distnr = min((d["distnr"] for d in dets if d.get("distnr") is not None and d["distnr"] >= 0), default=99)
    if distnr < 0.5:
        motivos.append("no centro de uma fonte (núcleo de galáxia ou estrela)")
    return nota, motivos


def historico_ztf(ra: float, dec: float, antes_de: float) -> int:
    """Detecções do ZTF a até 2" antes de uma data (MJD): muitas = fonte antiga que varia.
    Serve para os candidatos do Rubin; -1 se a ALeRCE não respondeu."""
    q = urllib.parse.urlencode({"ra": ra, "dec": dec, "radius": 2, "page_size": 5})
    try:
        objs = get_json(f"{API}/objects/?{q}").get("items", [])
    except Exception:
        return -1
    return sum(int(o.get("ndethist") or o.get("ndet") or 0) for o in objs if (o.get("firstmjd") or 1e9) < antes_de - 1)


def conferir_conhecidos(it: dict[str, Any]) -> None:
    """Checagens externas caras, só para os candidatos do topo: VSX e, no Rubin, o histórico do ZTF."""
    vsx = catalogos.variavel_conhecida(it["ra"], it["dec"])
    if vsx is catalogos.SEM_RESPOSTA:
        it["motivos"].append("VSX não respondeu")
    elif vsx:
        it["nota"] = round(it["nota"] - 10, 2)
        it["motivos"].append(f"variável conhecida no VSX: {vsx}")
    if it.get("fonte") == "rubin":
        antes = historico_ztf(it["ra"], it["dec"], mjd_agora() - it["idade"])
        if antes > 5:
            it["nota"] = round(it["nota"] - 5, 2)
            it["motivos"].append(f"{antes} detecções do ZTF antes (fonte antiga)")


def situacao_tns(tns: dict[str, Any] | None, ra: float, dec: float) -> str:
    if not tns:
        return "TNS não consultado (falta tns.json)"
    try:
        nomes = catalogos.tns_busca(tns, ra, dec)
    except Exception as e:
        return f"TNS não respondeu ({e.__class__.__name__})"
    return ("TNS: " + ", ".join(nomes)) if nomes else "NÃO está no TNS — dá para reportar"


def avaliar(obj: dict[str, Any], tns: dict[str, Any] | None) -> dict[str, Any] | None:
    oid = obj["oid"]
    if obj.get("meanra") is None or obj.get("meandec") is None:
        return None  # sem posição não dá para checar catálogo nem reportar
    dets = get_json(f"{API}/objects/{oid}/detections") or []
    dets = [d for d in dets if d.get("isdiffpos", 1) in (1, "t") and d.get("magpsf") is not None]
    if not dets:
        return None  # só detecções negativas (o objeto ficou mais fraco): não é candidato
    ra, dec = obj["meanra"], obj["meandec"]
    nota, motivos = pontuar(obj, dets, classificador_2025(oid), catalogos.estrela_gaia(ra, dec))
    mags = sorted(dets, key=lambda d: d["mjd"])
    com_stamp = [d for d in mags if d.get("has_stamp")]
    stamps: dict[str, str] = {}
    if com_stamp:
        c = com_stamp[0]["candid"]
        stamps = {t: f"{STAMP}?oid={oid}&candid={c}&type={t}&format=png" for t in ("science", "template", "difference")}
    curva = [(round(d["mjd"] - mags[0]["mjd"], 4), d["fid"], round(d["magpsf"], 2)) for d in mags]
    return dict(
        mjd0=mags[0]["mjd"],
        oid=oid,
        ra=ra,
        dec=dec,
        nota=round(nota, 2),
        prob=round(obj["probability"], 2),
        drb=round(max(d.get("drb") or 0 for d in dets), 3),
        motivos=motivos,
        conhecido=situacao_tns(tns, ra, dec),
        stamps=stamps,
        curva=curva,
        idade=round(mjd_agora() - obj["firstmjd"], 2),
        mag=mags[-1]["magpsf"],
    )
