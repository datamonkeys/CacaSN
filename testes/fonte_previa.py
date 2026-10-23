"""Experimento: mede se 'já havia fonte pontual na referência' separa os
candidatos que estão no TNS (quase sempre eventos reais) dos que ninguém
reportou. Resultado em 23/10/2026: não separa (AUC ~0.5). Precisa de um
resultados.json gerado antes por `python3 cacasn.py` com tns.json."""
import json, os, sys, urllib.request
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cacasn

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import gzip, hashlib

def ler_fits(b):
    """Leitor mínimo de FITS (imagem 2D no HDU primário)."""
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    cab, i = {}, 0
    while True:
        bloco = b[i:i + 2880]; i += 2880
        fim = False
        for k in range(36):
            card = bloco[k * 80:(k + 1) * 80].decode("ascii", "replace")
            chave = card[:8].strip()
            if chave == "END":
                fim = True; break
            if card[8:10] == "= ":
                cab[chave] = card[10:].split("/")[0].strip()
        if fim:
            break
    bp, nx, ny = int(cab["BITPIX"]), int(cab["NAXIS1"]), int(cab["NAXIS2"])
    tipo = {-32: ">f4", -64: ">f8", 16: ">i2", 32: ">i4"}[bp]
    a = np.frombuffer(b[i:i + nx * ny * abs(bp) // 8], tipo).reshape(ny, nx).astype(np.float32)
    return np.nan_to_num(a)

def img(url):
    url = url.replace("format=png", "format=fits")
    p = os.path.join(AQUI, "cache", hashlib.md5(url.encode()).hexdigest() + ".fits")
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        req = urllib.request.Request(url, headers=cacasn.HDR)
        with urllib.request.urlopen(req, timeout=60) as r, open(p, "wb") as out:
            out.write(r.read())
    with open(p, "rb") as fh:
        return ler_fits(fh.read())

def medidas(it):
    t, d = img(it["stamps"]["template"]), img(it["stamps"]["difference"])
    out = {}
    for nome, a in (("ref", t), ("dif", d)):
        h, w = a.shape
        lo, hi = np.percentile(a, [5, 95]); s = max(a[(a >= lo) & (a <= hi)].std(), 1)
        c = ndimage.gaussian_filter(a, 1)[h//2-3:h//2+4, w//2-3:w//2+4]
        out[nome] = float((c.max() - np.median(a)) / s)
    out["razao"] = out["dif"] / (out["ref"] + 1)  # quanto do brilho é novo
    return out

d = [x for x in cacasn.ler_json(os.path.join(AQUI, "resultados.json"), []) if x.get("stamps")]
if not d:
    sys.exit("rode antes: python3 cacasn.py --dias 10 (com tns.json)")
y = np.array([x["conhecido"].startswith("TNS:") for x in d])
M = [medidas(x) for x in d]
def auc(v):
    p, n = v[y], v[~y]; return np.mean([(a > b) + .5 * (a == b) for a in p for b in n])
for k in M[0]:
    v = np.array([m[k] for m in M]); a = auc(v)
    print(f"{k:6s} AUC {a:.2f}  (TNS mediana {np.median(v[y]):.1f} | não-TNS {np.median(v[~y]):.1f})")
cacasn.gravar_json(os.path.join(AQUI, "cache", "medidas.json"),
                   [{**m, "oid": x["oid"], "tns": bool(t)} for m, x, t in zip(M, d, y)])
