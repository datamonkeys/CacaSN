"""HTTP com novas tentativas e gravação de arquivos que não corrompe."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from . import __version__

REPO = "https://github.com/louisperner/CacaSN"
HDR = {"User-Agent": f"CacaSN/{__version__} (+{REPO})"}


def espera_429(erro: urllib.error.HTTPError, tentativa: int) -> float:
    """Quanto esperar quando o servidor diz 'requisições demais': o Retry-After, se vier,
    senão 15, 30, 60... s. Esperar pouco só faz o servidor recusar de novo."""
    try:
        return float(erro.headers.get("Retry-After", ""))
    except (TypeError, ValueError):
        return 15.0 * 2**tentativa


def abrir(url: str, timeout: float = 60, tentativas: int = 4) -> bytes:
    """Conteúdo da URL, com novas tentativas e espera crescente (1, 2, 4 s); no 429
    (limite do servidor) espera bem mais e tenta até 6 vezes."""
    if tentativas < 1:
        raise ValueError("tentativas precisa ser >= 1")
    i = falhas_429 = 0
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and falhas_429 < 6:
                time.sleep(espera_429(e, falhas_429))
                falhas_429 += 1
                continue
            i += 1
            if i >= tentativas:
                raise
            time.sleep(2 ** (i - 1))
        except Exception:
            i += 1
            if i >= tentativas:
                raise
            time.sleep(2 ** (i - 1))


def get_json(url: str, tentativas: int = 4) -> Any:
    return json.loads(abrir(url, 60, tentativas))


def gravar_texto(caminho: str, texto: str) -> None:
    """Grava num temporário e troca no fim: um crash não corrompe o anterior."""
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, caminho)


def gravar_json(caminho: str, dados: Any, **kw: Any) -> None:
    gravar_texto(caminho, json.dumps(dados, **kw))


def ler_json(caminho: str, padrao: Any) -> Any:
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def mjd_agora() -> float:
    return time.time() / 86400 + 40587
