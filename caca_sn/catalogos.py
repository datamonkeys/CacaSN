"""Já é conhecido? Gaia DR3 (via VizieR) e o Transient Name Server."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .rede import HDR, ler_json

SEM_RESPOSTA = object()  # o catálogo falhou: não dá para afirmar nada


class Disjuntor:
    """Depois de `limite` falhas seguidas, desiste na hora até a próxima resposta boa
    (ou a próxima rodada). Sem isso, um VizieR fora do ar custa ~90 s por candidato."""

    def __init__(self, limite: int = 3) -> None:
        self.limite = limite
        self.falhas = 0
        self._trava = threading.Lock()

    @property
    def aberto(self) -> bool:
        return self.falhas >= self.limite

    def resultado(self, ok: bool) -> None:
        with self._trava:
            self.falhas = 0 if ok else self.falhas + 1


VIZIER = Disjuntor()


def vizier(fonte: str, ra: float, dec: float, raio: float, cols: str) -> list[list[str]] | None:
    """Linhas do catálogo perto da posição, ou None se o VizieR não respondeu."""
    if VIZIER.aberto:
        return None
    url = (
        f"https://vizier.cds.unistra.fr/viz-bin/asu-tsv?-source={fonte}&-c={ra:.6f}%20{dec:+.6f}"
        f"&-c.rs={raio}&-out={cols}&-out.max=5&-sort=_r"
    )
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30) as r:
                linhas = [l.split("\t") for l in r.read().decode().splitlines() if l and not l.startswith("#")]
            VIZIER.resultado(True)
            return [l for l in linhas[3:] if len(l) == len(cols.split(","))]
        except Exception:
            if i < 2:
                time.sleep(2**i)
    VIZIER.resultado(False)
    return None


def estrela_gaia(ra: float, dec: float) -> Any:
    """Estrela do Gaia com paralaxe ou movimento significativo em 1.5": a
    'supernova' quase certamente é a estrela variando de brilho.
    Devolve o id da estrela, None, ou SEM_RESPOSTA se o catálogo falhou."""
    linhas = vizier("I/355/gaiadr3", ra, dec, 1.5, "Source,Plx,e_Plx,pmRA,pmDE")
    if linhas is None:
        return SEM_RESPOSTA
    for src, plx, eplx, pmra, pmde in linhas:
        try:
            if float(plx) > 3 * float(eplx) or (float(pmra) ** 2 + float(pmde) ** 2) ** 0.5 > 5:
                return src.strip()
        except ValueError:
            continue
    return None


def variavel_conhecida(ra: float, dec: float) -> Any:
    """Estrela variável já catalogada no VSX (AAVSO) a até 5": anãs novas, novas,
    variáveis da nossa galáxia que não vão para o TNS. Devolve "NOME (TIPO)",
    None, ou SEM_RESPOSTA se o catálogo falhou."""
    linhas = vizier("B/vsx/vsx", ra, dec, 5, "Name,Type")
    if linhas is None:
        return SEM_RESPOSTA
    for nome, tipo in linhas:
        return f"{nome.strip()} ({tipo.strip()})"
    return None


def tns_carregar(pasta: str) -> dict[str, Any] | None:
    """Credenciais do bot do TNS: variáveis TNS_BOT_ID/TNS_BOT_NAME/TNS_API_KEY
    (Docker, CI) ou o arquivo tns.json ao lado do programa (fora do git)."""
    if all(os.environ.get(k) for k in ("TNS_BOT_ID", "TNS_BOT_NAME", "TNS_API_KEY")):
        return {
            "bot_id": int(os.environ["TNS_BOT_ID"]),
            "bot_name": os.environ["TNS_BOT_NAME"],
            "api_key": os.environ["TNS_API_KEY"],
        }
    cfg = ler_json(os.path.join(pasta, "tns.json"), None)
    return cfg if isinstance(cfg, dict) else None


_tns_trava = threading.Lock()
_tns_ultima = [0.0]


def tns_busca(cfg: dict[str, Any], ra: float, dec: float, tentativas: int = 4) -> list[str]:
    """Objetos do TNS a até 3". A busca por região aceita 10 por minuto: uma por
    vez, a cada 6.5 s; no 429 espera o tempo que o cabeçalho manda, em erro de
    rede espera e tenta de novo."""
    marker = json.dumps({"tns_id": cfg["bot_id"], "type": "bot", "name": cfg["bot_name"]})
    dados = urllib.parse.urlencode(
        {
            "api_key": cfg["api_key"],
            "data": json.dumps({"ra": f"{ra:.6f}", "dec": f"{dec:.6f}", "radius": "3", "units": "arcsec"}),
        }
    ).encode()
    for i in range(tentativas):
        with _tns_trava:
            espera = 6.5 - (time.time() - _tns_ultima[0])
            if espera > 0:
                time.sleep(espera)
            try:
                req = urllib.request.Request(
                    "https://www.wis-tns.org/api/get/search", data=dados, headers={"User-Agent": "tns_marker" + marker}
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.load(r)
                return [f"{o.get('prefix', '')} {o['objname']}".strip() for o in resp.get("data", [])]
            except urllib.error.HTTPError as e:
                if e.code != 429 or i == tentativas - 1:
                    raise
                time.sleep(int(e.headers.get("x-cone-rate-limit-reset", "30")) + 1)
            except urllib.error.URLError:
                if i == tentativas - 1:
                    raise
                time.sleep(2 ** (i + 1))
            finally:
                _tns_ultima[0] = time.time()
    return []
