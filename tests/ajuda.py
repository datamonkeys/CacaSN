"""Dados falsos comuns aos testes (as APIs nunca são chamadas de verdade)."""

from caca_sn.rede import mjd_agora

OBJ = {
    "oid": "ZTF26teste",
    "meanra": 10.0,
    "meandec": -5.0,
    "probability": 0.8,
    "firstmjd": mjd_agora() - 2,
    "ndethist": 3,
    "stellar": False,
}


def det(mjd, fid, mag, pos=1, stamp=False, drb=0.99, distnr=2.0):
    return {
        "mjd": mjd,
        "fid": fid,
        "magpsf": mag,
        "isdiffpos": pos,
        "has_stamp": stamp,
        "candid": f"c{mjd}",
        "drb": drb,
        "distnr": distnr,
    }


def falso_get_json(dets, probs=None):
    def f(url, tentativas=4):
        if url.endswith("/detections"):
            return dets
        if url.endswith("/probabilities"):
            return probs or []
        raise AssertionError(url)

    return f
