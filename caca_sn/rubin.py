"""Alertas do Rubin (LSST) via o broker Fink: candidatos, nota e estado do fluxo.

A nota foi medida contra o que os grupos profissionais reportaram ao TNS em
5.289 objetos do Rubin de 25/06 a 20/07/2026 (93 no TNS): AUC 0.895 numa metade
não usada para escolher a combinação (só o brilho: 0.807). O termo mais útil
depois do brilho é a fração do brilho que é nova (fluxo da diferença contra o da
referência): os grupos reportam fontes novas; o resto é variável sobre fonte antiga."""

from __future__ import annotations

import math
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .rede import get_json, mjd_agora

API = "https://api.lsst.fink-portal.org/api/v1"
TAGS = (
    "most_likely_sn",
    "sn_near_galaxy_candidate",
    "extragalactic_new_candidate",
    "extragalactic_lt20mag_candidate",
    "hostless_candidate",
)
COLUNAS = ",".join(
    [
        "r:diaObjectId",
        "r:diaSourceId",
        "r:ra",
        "r:dec",
        "r:midpointMjdTai",
        "r:band",
        "r:psfFlux",
        "r:snr",
        "r:templateFlux",
        "r:reliability",
        "r:isDipole",
        "r:ssObjectId",
        "r:extendedness",
        "f:clf_snnSnVsOthers_score",
        "f:xm_tns_fullname",
        "f:xm_legacydr8_zphot",
        "f:xm_mangrove_lum_dist",
    ]
)
# 1% mais alto dos não reportados em julho/2026 (~2-3 por dia com o fluxo ativo)
AVISO = 13.7
# sem alerta há mais que isso, o fluxo é considerado parado
DIAS_PARADO = 3


def num(v: Any, padrao: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return padrao
    return padrao if math.isnan(f) else f


def texto(v: Any) -> str | None:
    s = "" if v is None else str(v)
    return None if s in ("", "nan", "None", "Fail") else s


def mag_ab(fluxo_njy: float) -> float | None:
    """Fluxo em nJy (unidade do Rubin) -> magnitude AB."""
    return 31.4 - 2.5 * math.log10(fluxo_njy) if fluxo_njy > 0 else None


def alertas(dias: float, n: int = 2000) -> list[dict[str, Any]]:
    """Alertas das categorias de supernova do Fink com primeira data nos últimos N dias."""
    # a documentação aceita MJD, mas a API responde 500 a MJD: só ISO funciona
    inicio = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
    vistos: dict[Any, dict[str, Any]] = {}
    for tag in TAGS:
        q = urllib.parse.urlencode({"tag": tag, "n": n, "startdate": inicio, "columns": COLUNAS})
        for a in get_json(f"{API}/tags?{q}") or []:
            a["tag"] = tag
            vistos[a["r:diaSourceId"]] = a
    return list(vistos.values())


def por_objeto(lista: list[dict[str, Any]]) -> dict[Any, list[dict[str, Any]]]:
    grupos: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for a in lista:
        grupos[a["r:diaObjectId"]].append(a)
    return grupos


def pontuar(als: list[dict[str, Any]]) -> tuple[float, list[str]]:
    """Nota de um objeto a partir dos seus alertas (pesos 1-2, escolhidos à mão)."""
    brilho = max(num(a.get("r:psfFlux")) for a in als)
    snr = max(num(a.get("r:snr")) for a in als)
    confiab = max(num(a.get("r:reliability")) for a in als)
    pontual = 1 - max(num(a.get("r:extendedness")) for a in als)
    zphot = any(texto(a.get("f:xm_legacydr8_zphot")) for a in als)
    snn = max(num(a.get("f:clf_snnSnVsOthers_score"), -1) for a in als)
    positivos = sum(num(a.get("r:psfFlux")) > 0 for a in als) / len(als)
    dipolo = sum(bool(a.get("r:isDipole")) for a in als) / len(als)
    referencia = min(abs(num(a.get("r:templateFlux"))) for a in als)
    nova = max(brilho, 0) / (referencia + abs(brilho) + 1)  # 1 = não havia nada antes
    nota = (
        2 * nova
        + math.log10(max(brilho, 1))
        + math.log10(max(snr, 1))
        + 2 * confiab
        + 2 * pontual
        + float(zphot)
        + max(snn, 0)
        + positivos
        + math.log2(len(als))
        - dipolo
    )
    motivos = [
        f"confiabilidade {confiab:.2f}",
        f"S/R {snr:.0f}",
        "fonte nova" if nova > 0.7 else f"fonte já existia na referência ({nova:.0%} do brilho é novo)",
    ]
    if snn > 0:
        motivos.append(f"SuperNNova {snn:.2f}")
    if zphot:
        motivos.append("galáxia com redshift fotométrico")
    if dipolo > 0.5:
        motivos.append("dipolo (subtração ruim?)")
    if positivos < 0.5:
        motivos.append("fluxo negativo (ficou mais fraco)")
    if any(num(a.get("r:ssObjectId")) > 0 for a in als):
        motivos.append("asteroide conhecido")
    if len({a.get("r:band") for a in als}) >= 2:
        motivos.append(f"{len({a.get('r:band') for a in als})} filtros")
    return nota, motivos


def objeto(oid: Any, als: list[dict[str, Any]]) -> dict[str, Any]:
    """Mesmo formato dos itens do ZTF, para o relatório e o alarme."""
    als = sorted(als, key=lambda a: num(a.get("r:midpointMjdTai")))
    ultimo = als[-1]
    nota, motivos = pontuar(als)
    if any(num(a.get("r:ssObjectId")) > 0 for a in als):
        nota -= 10  # asteroide conhecido não é transiente
    tns = next((texto(a.get("f:xm_tns_fullname")) for a in als if texto(a.get("f:xm_tns_fullname"))), None)
    fid = {"u": 0, "g": 1, "r": 2, "i": 3, "z": 4, "y": 5}
    curva = [
        (round(num(a["r:midpointMjdTai"]) - num(als[0]["r:midpointMjdTai"]), 4), fid.get(str(a.get("r:band")), 9), round(m, 2))
        for a in als
        if (m := mag_ab(num(a.get("r:psfFlux")))) is not None
    ]
    sid = ultimo["r:diaSourceId"]
    return dict(
        mjd0=num(als[0]["r:midpointMjdTai"]),
        oid=f"LSST {oid}",
        ra=num(ultimo["r:ra"]),
        dec=num(ultimo["r:dec"]),
        nota=round(nota, 2),
        prob=round(max(num(a.get("f:clf_snnSnVsOthers_score"), 0) for a in als), 2),
        drb=round(max(num(a.get("r:reliability")) for a in als), 3),
        motivos=motivos,
        conhecido=f"TNS: {tns} (Fink)" if tns else "",
        fonte="rubin",
        stamps={
            k: f"{API}/cutouts?diaSourceId={sid}&kind={v}"
            for k, v in (("science", "Science"), ("template", "Template"), ("difference", "Difference"))
        },
        curva=curva,
        idade=round(mjd_agora() - num(als[0]["r:midpointMjdTai"]), 2),
        mag=mag_ab(max(num(a.get("r:psfFlux")) for a in als)) or 99.0,
        link=f"https://lsst.fink-portal.org/{oid}",
    )


def curva_completa(oid: Any) -> tuple[float, list[tuple[float, int, float]]] | None:
    """Todas as detecções do objeto no Fink (a categoria só traz o alerta que a disparou).
    Devolve (MJD da primeira detecção positiva, curva) ou None."""
    q = urllib.parse.urlencode({"diaObjectId": oid, "columns": "r:midpointMjdTai,r:band,r:psfFlux"})
    try:
        fontes = get_json(f"{API}/sources?{q}") or []
    except Exception:
        return None
    fid = {"u": 0, "g": 1, "r": 2, "i": 3, "z": 4, "y": 5}
    pontos = sorted(
        (num(s["r:midpointMjdTai"]), fid.get(str(s.get("r:band")), 9), m)
        for s in fontes
        if (m := mag_ab(num(s.get("r:psfFlux")))) is not None
    )
    if not pontos:
        return None
    t0 = pontos[0][0]
    return t0, [(round(t - t0, 4), f, round(m, 2)) for t, f, m in pontos]


def ultima_noite() -> str | None:
    """Última noite (AAAAMMDD) com alertas do Rubin no Fink neste ano ou no anterior."""
    from time import gmtime

    ano = gmtime().tm_year
    for a in (ano, ano - 1):
        noites = get_json(f"{API}/statistics?date={a}&columns=f:night") or []
        if noites:
            return max(x["f:night"] for x in noites)
    return None
