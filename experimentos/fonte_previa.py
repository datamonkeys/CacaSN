"""Experimento (23/10/2026): "já havia fonte pontual na referência" separa os
candidatos que estão no TNS (quase sempre eventos reais) dos que ninguém
reportou? Resultado: não (AUC ~0.5) — por isso não entrou na nota.

Precisa de numpy/scipy (`pip install .[experimentos]`) e de um resultados.json
gerado antes por `python -m caca_sn --dias 10` com credenciais do TNS."""

import gzip
import hashlib
import os
import sys
import urllib.request

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from caca_sn.rede import HDR, gravar_json, ler_json  # noqa: E402

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ler_fits(b):
    """Leitor mínimo de FITS (imagem 2D no HDU primário)."""
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    cab, i, fim = {}, 0, False
    while not fim:
        bloco = b[i : i + 2880]
        i += 2880
        for k in range(36):
            card = bloco[k * 80 : (k + 1) * 80].decode("ascii", "replace")
            if card[:8].strip() == "END":
                fim = True
                break
            if card[8:10] == "= ":
                cab[card[:8].strip()] = card[10:].split("/")[0].strip()
    bp, nx, ny = int(cab["BITPIX"]), int(cab["NAXIS1"]), int(cab["NAXIS2"])
    tipo = {-32: ">f4", -64: ">f8", 16: ">i2", 32: ">i4"}[bp]
    a = np.frombuffer(b[i : i + nx * ny * abs(bp) // 8], tipo).reshape(ny, nx).astype(np.float32)
    return np.nan_to_num(a)


def imagem(url):
    url = url.replace("format=png", "format=fits")
    p = os.path.join(PASTA, "cache", hashlib.md5(url.encode()).hexdigest() + ".fits")
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=60) as r, open(p, "wb") as out:
            out.write(r.read())
    with open(p, "rb") as fh:
        return ler_fits(fh.read())


def medidas(it):
    out = {}
    for nome, tipo in (("ref", "template"), ("dif", "difference")):
        a = imagem(it["stamps"][tipo])
        h, w = a.shape
        lo, hi = np.percentile(a, [5, 95])
        s = max(a[(a >= lo) & (a <= hi)].std(), 1)
        c = ndimage.gaussian_filter(a, 1)[h // 2 - 3 : h // 2 + 4, w // 2 - 3 : w // 2 + 4]
        out[nome] = float((c.max() - np.median(a)) / s)
    out["razao"] = out["dif"] / (out["ref"] + 1)  # quanto do brilho é novo
    return out


def auc(v, y):
    p, n = v[y], v[~y]
    return np.mean([(a > b) + 0.5 * (a == b) for a in p for b in n])


def main():
    d = [x for x in ler_json(os.path.join(PASTA, "resultados.json"), []) if x.get("stamps")]
    if not d:
        sys.exit("rode antes: python -m caca_sn --dias 10 (com credenciais do TNS)")
    y = np.array([x["conhecido"].startswith("TNS:") for x in d])
    m = [medidas(x) for x in d]
    for k in m[0]:
        v = np.array([x[k] for x in m])
        print(f"{k:6s} AUC {auc(v, y):.2f}  (TNS mediana {np.median(v[y]):.1f} | não-TNS {np.median(v[~y]):.1f})")
    gravar_json(os.path.join(PASTA, "cache", "medidas.json"), [{**x, "oid": o["oid"]} for x, o in zip(m, d)])


if __name__ == "__main__":
    main()
