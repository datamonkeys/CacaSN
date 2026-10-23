"""Linha de comando: busca, avalia, grava resultados.json e report.html."""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import alertas, avaliacao, catalogos, registro
from .rede import gravar_json, gravar_texto
from .relatorio import relatorio

# onde ficam resultados, relatório, log e tns.json: ao lado do programa, ou CACASN_SAIDA (ex.: Docker)
PASTA = os.environ.get("CACASN_SAIDA") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _seguro(obj: dict[str, Any], tns: dict[str, Any] | None) -> dict[str, Any] | None:
    try:
        return avaliacao.avaliar(obj, tns)
    except Exception as e:  # um objeto quebrado não derruba a rodada
        registro.obter().warning("erro_no_objeto", oid=obj.get("oid"), erro=repr(e))
        return None


def rodar(dias: float, prob: float, avisar: bool, pasta: str = PASTA) -> list[dict[str, Any]]:
    log = registro.obter()
    tns = catalogos.tns_carregar(pasta)
    objs = avaliacao.candidatos(dias, prob)
    with ThreadPoolExecutor(6) as ex:
        itens = [r for r in ex.map(lambda o: _seguro(o, tns), objs) if r]
    gravar_json(os.path.join(pasta, "resultados.json"), itens, indent=1)
    gravar_texto(os.path.join(pasta, "report.html"), relatorio(itens))
    log.info(
        "rodada",
        dias=dias,
        candidatos=len(objs),
        avaliados=len(itens),
        fora_do_tns=sum(i["conhecido"].startswith("NÃO") for i in itens),
        melhor_nota=max((i["nota"] for i in itens), default=0),
        top=[[i["oid"], i["nota"], i["conhecido"]] for i in sorted(itens, key=lambda x: -x["nota"])[:5]],
    )
    if avisar:
        alertas.avisar_novos(itens, pasta)
    return itens


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cacasn", description="Caçador de supernovas nos alertas do ZTF (ALeRCE + TNS).")
    ap.add_argument("--dias", type=float, default=3, help="primeira detecção há no máximo N dias")
    ap.add_argument("--prob", type=float, default=0.5, help="probabilidade mínima de SN no stamp classifier")
    ap.add_argument("--avisar", action="store_true", help=f"avisa candidato fora do TNS com nota >= {alertas.AVISO}")
    args = ap.parse_args(argv)
    registro.configurar(os.path.join(PASTA, "cacasn.log"))
    try:
        rodar(args.dias, args.prob, args.avisar)
    except Exception as e:
        registro.obter().error("rodada_falhou", erro=repr(e))
        raise
    print(os.path.join(PASTA, "report.html"))
    return 0
