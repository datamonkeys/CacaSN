"""Rascunho de relatório de descoberta (AT report) para o TNS, no formato do
envio em lote (TNS 2.0, `api/set/bulk-report`). Só gera o arquivo: nunca envia.
Para testar sem afetar o registro oficial, use https://sandbox.wis-tns.org."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .rede import REPO

# IDs do TNS lidos de objetos já reportados (out/2026)
FONTE = {"ztf": "48", "rubin": "165"}  # discovery data source: ZTF, Rubin
INSTRUMENTO = {"ztf": "196", "rubin": "287"}  # ZTF-Cam, LSSTCam
FILTRO = {
    "ztf": {1: "110", 2: "111", 3: "112"},  # g, r, i do ZTF (confirmados)
    # g=161, i=163, z=164 confirmados; u=160, r=162, y=165 inferidos pela sequência
    "rubin": {0: "160", 1: "161", 2: "162", 3: "163", 4: "164", 5: "165"},
}
AB_MAG = "1"


def data_tns(mjd: float) -> str:
    """MJD -> 'AAAA-MM-DD.ddddd' (dia fracionário, como o TNS pede)."""
    arredondado = round(mjd, 5)  # arredonda antes de separar dia e fração: 23:59:59.9 vira o dia seguinte
    dia = int(arredondado // 1)
    data = datetime(1858, 11, 17, tzinfo=timezone.utc) + timedelta(days=dia)
    return f"{data:%Y-%m-%d}" + f"{arredondado - dia:.5f}"[1:]


def rascunho(it: dict[str, Any], cfg: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Relatório para um candidato e a lista do que ainda precisa de atenção."""
    cfg = cfg or {}
    fonte = it.get("fonte", "ztf")
    pendencias = []
    if it.get("mjd0") is None:
        raise ValueError("candidato sem data da primeira detecção (rode o cacasn de novo)")
    grupo = str(cfg.get("reporting_groupid", ""))
    if not grupo:
        pendencias.append("reporting_groupid: o grupo do TNS em nome de quem você reporta (ponha em tns.json)")
    reporter = cfg.get("reporter") or ""
    if not reporter:
        pendencias.append("reporter: seu nome como deve aparecer no TNS (ponha em tns.json)")
    if fonte == "rubin" and any(f in (0, 2, 5) for _, f, _ in it["curva"]):
        pendencias.append("filtros u/r/y do LSST usam IDs inferidos (160/162/165): confira no sandbox")
    fotometria = {}
    for i, (t, f, mag) in enumerate(it["curva"]):
        fotometria[str(i)] = {
            "obsdate": data_tns(it["mjd0"] + t),
            "flux": f"{mag:.2f}",
            "flux_error": "",
            "limiting_flux": "",
            "flux_unitid": AB_MAG,
            "filterid": FILTRO[fonte].get(f, ""),
            "instrumentid": INSTRUMENTO[fonte],
            "exptime": "",
            "observer": "Robot",
            "comments": "",
        }
    origem = "ZTF public alerts via ALeRCE" if fonte == "ztf" else "Rubin/LSST public alerts via Fink"
    relatorio = {
        "at_report": {
            "0": {
                "ra": {"value": f"{it['ra']:.6f}", "error": "0.5", "units": "arcsec"},
                "dec": {"value": f"{it['dec']:.6f}", "error": "0.5", "units": "arcsec"},
                "reporting_groupid": grupo,
                "data_source_groupid": FONTE[fonte],
                "reporter": reporter,
                "discovery_datetime": data_tns(it["mjd0"]),
                "at_type": "1",
                "internal_name": str(it["oid"]).replace("LSST ", ""),
                "remarks": (
                    f"Found in {origem} with CacaSN ({REPO}). "
                    f"Real/bogus {it.get('drb', '?')}, SN probability {it.get('prob', '?')}, "
                    f"{len(it['curva'])} detection(s)."
                ),
                "non_detection": {
                    "obsdate": "",
                    "limiting_flux": "",
                    "flux_unitid": "",
                    "filterid": "",
                    "instrumentid": "",
                    "exptime": "",
                    "observer": "",
                    "comments": "",
                    "archiveid": "",
                    "archival_remarks": "No source at this position in the survey reference (template) image.",
                },
                "photometry": fotometria,
            }
        }
    }
    return relatorio, pendencias
