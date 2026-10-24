"""Acompanha objetos no TNS (por exemplo, os que você descobriu) e avisa quando
alguém os classifica por espectro — a mesma informação dos emails de AstroNotes,
lida direto da API do TNS a cada rodada."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from . import alertas, registro
from .rede import gravar_json, ler_json

ARQUIVO = "acompanhar.json"


def tns_objeto(cfg: dict[str, Any], nome: str) -> dict[str, Any]:
    """Registro do objeto no TNS (api/get/object)."""
    marker = json.dumps({"tns_id": cfg["bot_id"], "type": "bot", "name": cfg["bot_name"]})
    dados = urllib.parse.urlencode({"api_key": cfg["api_key"], "data": json.dumps({"objname": nome})}).encode()
    req = urllib.request.Request(
        "https://www.wis-tns.org/api/get/object", data=dados, headers={"User-Agent": "tns_marker" + marker}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("data") or {}


def situacao(obj: dict[str, Any]) -> dict[str, Any]:
    tipo = (obj.get("object_type") or {}).get("name")
    return {"prefixo": obj.get("name_prefix"), "tipo": tipo, "redshift": obj.get("redshift")}


def descrever(nome: str, s: dict[str, Any]) -> str:
    texto = f"{s.get('prefixo') or 'AT'} {nome}"
    if s.get("tipo"):
        texto += f" = {s['tipo']}"
    if s.get("redshift"):
        texto += f" (z = {s['redshift']})"
    return texto


def adicionar(pasta: str, nome: str) -> None:
    caminho = os.path.join(pasta, ARQUIVO)
    lista = ler_json(caminho, {})
    lista.setdefault(nome.replace("AT ", "").replace("SN ", "").strip(), {})
    gravar_json(caminho, lista, indent=1)


def verificar(cfg: dict[str, Any] | None, pasta: str, consultar: Any = tns_objeto) -> list[str]:
    """Confere cada objeto acompanhado; devolve (e notifica) o que mudou."""
    caminho = os.path.join(pasta, ARQUIVO)
    lista: dict[str, dict[str, Any]] = ler_json(caminho, {})
    if not cfg or not lista:
        return []
    log = registro.obter()
    mudancas = []
    for nome, antes in lista.items():
        try:
            agora = situacao(consultar(cfg, nome))
        except Exception as e:
            log.warning("acompanhamento_falhou", objeto=nome, erro=repr(e))
            continue
        if antes and agora.get("tipo") and agora.get("tipo") != antes.get("tipo"):
            mudancas.append(f"{descrever(nome, antes)} -> {descrever(nome, agora)}")
        lista[nome] = agora
    gravar_json(caminho, lista, indent=1)
    if mudancas:
        log.info("classificado", mudancas=mudancas)
        alertas.notificar("CacaSN: classificaram sua descoberta!", "; ".join(mudancas), os.path.join(pasta, "report.html"))
    return mudancas
