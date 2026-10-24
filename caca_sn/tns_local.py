"""Busca por posição no TNS feita localmente, sobre o arquivo completo de objetos
públicos (tns_public_objects.csv.zip, ~14 MB, gerado à meia-noite UTC), baixado no
máximo uma vez por dia. Troca centenas de consultas à API (uma a cada 6.5 s) por
buscas de milissegundos. O que foi reportado depois da meia-noite não está no
arquivo: por isso o "não está" de candidatos fortes ainda é confirmado pela API."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import time
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from typing import Any

URL = "https://www.wis-tns.org/system/files/tns_public_objects/tns_public_objects.csv.zip"
ARQUIVO = "tns_public_objects.csv.zip"
VALIDADE = 20 * 3600  # rebaixa quando o arquivo tem mais de 20 h


class IndiceTNS:
    """Objetos do TNS agrupados em faixas de 1° de declinação."""

    def __init__(self, linhas: list[dict[str, str]]) -> None:
        self.faixas: dict[int, list[tuple[float, float, str]]] = defaultdict(list)
        for d in linhas:
            try:
                ra, dec = float(d["ra"]), float(d["declination"])
            except (KeyError, ValueError):
                continue
            nome = f"{d.get('name_prefix', '')} {d.get('name', '')}".strip()
            self.faixas[math.floor(dec)].append((ra, dec, nome))
        self.total = sum(len(v) for v in self.faixas.values())

    def buscar(self, ra: float, dec: float, raio_arcsec: float = 3.0) -> list[str]:
        r = raio_arcsec / 3600
        achados = []
        for faixa in range(math.floor(dec - r), math.floor(dec + r) + 1):
            for ra2, dec2, nome in self.faixas.get(faixa, []):
                if abs(dec2 - dec) > r:
                    continue
                dra = (ra2 - ra + 180) % 360 - 180  # cruza RA = 0/360
                if math.hypot(dra * math.cos(math.radians(dec)), dec2 - dec) <= r:
                    achados.append(nome)
        return achados


def ler(conteudo: bytes) -> list[dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        texto = z.read(z.namelist()[0]).decode("utf-8", "replace")
    linhas = list(csv.reader(io.StringIO(texto)))
    if len(linhas) < 2:
        return []
    cabecalho = linhas[1]  # a primeira linha é a data do arquivo
    return [dict(zip(cabecalho, linha)) for linha in linhas[2:]]


def baixar(cfg: dict[str, Any]) -> bytes:
    marker = "tns_marker" + json.dumps({"tns_id": cfg["bot_id"], "type": "bot", "name": cfg["bot_name"]})
    dados = urllib.parse.urlencode({"api_key": cfg["api_key"]}).encode()
    req = urllib.request.Request(URL, data=dados, headers={"User-Agent": marker})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def carregar(cfg: dict[str, Any] | None, pasta: str, obter: Any = baixar) -> IndiceTNS | None:
    """Índice do arquivo em cache (rebaixado se velho); None se não deu para obter."""
    if not cfg:
        return None
    os.makedirs(os.path.join(pasta, "cache"), exist_ok=True)
    caminho = os.path.join(pasta, "cache", ARQUIVO)
    if not os.path.exists(caminho) or time.time() - os.path.getmtime(caminho) > VALIDADE:
        try:
            conteudo = obter(cfg)
            tmp = caminho + ".tmp"
            with open(tmp, "wb") as f:
                f.write(conteudo)
            os.replace(tmp, caminho)
        except Exception:
            if not os.path.exists(caminho):
                return None  # sem arquivo nenhum: fica só a API
    try:
        with open(caminho, "rb") as f:
            return IndiceTNS(ler(f.read()))
    except Exception:
        return None
