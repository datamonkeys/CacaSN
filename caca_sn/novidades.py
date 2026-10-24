"""Novidades do TNS sem depender de email: o arquivo diário de mudanças
(tns_public_objects_AAAAMMDD.csv.zip) traz os transientes reportados e as
classificações por espectro de cada dia — o conteúdo dos boletins de AstroNotes."""

from __future__ import annotations

import csv
import io
import json
import os
import urllib.parse
import urllib.request
import zipfile
from datetime import date, timedelta
from typing import Any

from . import alertas, registro
from .rede import gravar_json, ler_json

URL = "https://www.wis-tns.org/system/files/tns_public_objects/tns_public_objects_{}.csv.zip"
ESTADO = "novidades_estado.json"
RESUMO = "novidades.md"
# tipos raros: valem aviso mesmo que o CacaSN não tenha visto o objeto
RAROS = ("SLSN", "TDE", "Kilonova", "FBOT", "Ic-BL", "IIn", "Ibn", "Icn", "Ca-rich", "LRN", "LBV")
MAX_DIAS = 7


def baixar_dia(cfg: dict[str, Any], dia: date) -> list[dict[str, str]]:
    """Objetos que mudaram no TNS num dia (UTC)."""
    marker = json.dumps({"tns_id": cfg["bot_id"], "type": "bot", "name": cfg["bot_name"]})
    dados = urllib.parse.urlencode({"api_key": cfg["api_key"]}).encode()
    req = urllib.request.Request(URL.format(dia.strftime("%Y%m%d")), data=dados, headers={"User-Agent": "tns_marker" + marker})
    with urllib.request.urlopen(req, timeout=120) as r:
        conteudo = r.read()
    return ler_csv(conteudo)


def ler_csv(conteudo: bytes) -> list[dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        texto = z.read(z.namelist()[0]).decode("utf-8", "replace")
    linhas = list(csv.reader(io.StringIO(texto)))
    if len(linhas) < 2:
        return []
    cabecalho = linhas[1]  # a primeira linha é o intervalo de datas
    return [dict(zip(cabecalho, linha)) for linha in linhas[2:]]


def resumir(dados: list[dict[str, str]], vistos: set[str]) -> dict[str, Any]:
    """Classificados do dia; destaca os que o CacaSN viu e os de tipo raro."""
    classificados = [d for d in dados if d.get("type")]
    novos = [d for d in dados if not d.get("type")]
    destaques = []
    for d in classificados:
        internos = {n.strip() for n in d.get("internal_names", "").split(",") if n.strip()}
        if internos & vistos:
            destaques.append(
                f"{d['name_prefix']} {d['name']} = {d['type']}: o CacaSN tinha visto ({', '.join(internos & vistos)})"
            )
        elif any(r in d["type"] for r in RAROS):
            destaques.append(f"{d['name_prefix']} {d['name']} = {d['type']} (raro, z = {d.get('redshift') or '?'})")
    return {"novos": len(novos), "classificados": classificados, "destaques": destaques}


def markdown(dia: date, r: dict[str, Any]) -> str:
    linhas = [f"## {dia.isoformat()}", "", f"{r['novos']} transientes reportados, {len(r['classificados'])} classificados.", ""]
    for d in r["classificados"]:
        linhas.append(
            f"- {d['name_prefix']} {d['name']} — {d['type']}, z = {d.get('redshift') or '?'}"
            f" ({d.get('internal_names', '').strip(', ')[:60]})"
        )
    for x in r["destaques"]:
        linhas.append(f"- **destaque:** {x}")
    return "\n".join(linhas) + "\n\n"


def verificar(
    cfg: dict[str, Any] | None, pasta: str, vistos: set[str], hoje: date | None = None, baixar: Any = baixar_dia
) -> list[str]:
    """Processa os dias completos desde a última verificação (no máximo MAX_DIAS)."""
    if not cfg:
        return []
    hoje = hoje or date.today()
    estado = ler_json(os.path.join(pasta, ESTADO), {})
    ultimo = date.fromisoformat(estado["ultimo_dia"]) if estado.get("ultimo_dia") else hoje - timedelta(days=2)
    dia = max(ultimo + timedelta(days=1), hoje - timedelta(days=MAX_DIAS))
    destaques: list[str] = []
    log = registro.obter()
    while dia < hoje:  # o dia de hoje ainda não fechou
        try:
            r = resumir(baixar(cfg, dia), vistos)
        except Exception as e:
            log.warning("novidades_falhou", dia=dia.isoformat(), erro=repr(e))
            break
        with open(os.path.join(pasta, RESUMO), "a", encoding="utf-8") as f:
            f.write(markdown(dia, r))
        log.info("novidades", dia=dia.isoformat(), novos=r["novos"], classificados=len(r["classificados"]))
        destaques += r["destaques"]
        estado["ultimo_dia"] = dia.isoformat()
        dia += timedelta(days=1)
    gravar_json(os.path.join(pasta, ESTADO), estado)
    if destaques:
        alertas.notificar("CacaSN: novidades no TNS", "; ".join(destaques)[:250], os.path.join(pasta, RESUMO))
    return destaques
