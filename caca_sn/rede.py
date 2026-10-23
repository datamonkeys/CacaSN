"""HTTP com novas tentativas e gravação de arquivos que não corrompe."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

from . import __version__

REPO = "https://github.com/louisperner/CacaSN"
HDR = {"User-Agent": f"CacaSN/{__version__} (+{REPO})"}


def abrir(url: str, timeout: float = 60, tentativas: int = 4) -> bytes:
    """Conteúdo da URL, com novas tentativas e espera crescente (1, 2, 4 s)."""
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=timeout) as r:
                return r.read()
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(2**i)
    raise ValueError("tentativas precisa ser >= 1")


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
