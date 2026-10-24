"""Linha de comando: busca, avalia, grava resultados.json e report.html."""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from . import acompanhamento, alertas, avaliacao, catalogos, curva, registro, rubin
from .rascunho import rascunho
from .rede import gravar_json, gravar_texto, ler_json
from .relatorio import relatorio

# onde ficam resultados, relatório, log e tns.json: ao lado do programa, ou CACASN_SAIDA (ex.: Docker)
PASTA = os.environ.get("CACASN_SAIDA") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTES = ("ztf", "rubin")
# consulta ao TNS (10/min) só para os melhores do Rubin que o Fink não marcou
TOP_RUBIN_TNS = 30
# no ZTF o TNS só é consultado de 15 para cima: no teste de 30 dias (out/2026) todos os
# 6 alarmes (>= 18, fora do TNS) estavam acima disso, e as consultas caem de 447 para 159
CORTE_TNS = 15.0
# VSX (variáveis conhecidas) só para os melhores do ZTF
TOP_CONFERIR = 20


def _seguro(obj: dict[str, Any], tns: dict[str, Any] | None) -> dict[str, Any] | None:
    try:
        return avaliacao.avaliar(obj, tns)
    except Exception as e:  # um objeto quebrado não derruba a rodada
        registro.obter().warning("erro_no_objeto", oid=obj.get("oid"), erro=repr(e))
        return None


def tns_com_cache(itens: list[dict[str, Any]], tns: dict[str, Any] | None, pasta: str, corte: float) -> None:
    """Situação no TNS só para quem pode disparar o alarme (nota >= corte). Quem já tem
    nome no TNS fica no cache (tns_cache.json) e não é perguntado de novo; os não
    reportados são conferidos a cada rodada, porque alguém pode reportar no meio-tempo."""
    caminho = os.path.join(pasta, "tns_cache.json")
    cache: dict[str, str] = ler_json(caminho, {})
    for it in sorted(itens, key=lambda x: -x["nota"]):
        if it["oid"] in cache:
            it["conhecido"] = cache[it["oid"]]
        elif it["nota"] < corte:
            it["conhecido"] = "TNS não consultado (nota baixa)"
        else:
            it["conhecido"] = avaliacao.situacao_tns(tns, it["ra"], it["dec"])
            if it["conhecido"].startswith("TNS:"):
                cache[it["oid"]] = it["conhecido"]
    gravar_json(caminho, cache)


def rodar_ztf(dias: float, prob: float, tns: dict[str, Any] | None, pasta: str = PASTA) -> list[dict[str, Any]]:
    objs = avaliacao.candidatos(dias, prob)
    with ThreadPoolExecutor(6) as ex:
        itens = [r for r in ex.map(lambda o: _seguro(o, None), objs) if r]
    for i in itens:
        i.setdefault("fonte", "ztf")
    for it in sorted(itens, key=lambda x: -x["nota"])[:TOP_CONFERIR]:
        avaliacao.conferir_conhecidos(it)
    tns_com_cache(itens, tns, pasta, CORTE_TNS)
    return itens


def vigiar_fluxo_rubin(pasta: str) -> bool:
    """O Rubin está mandando alertas? Avisa uma vez quando o fluxo volta depois de parado."""
    log = registro.obter()
    caminho = os.path.join(pasta, "rubin_estado.json")
    estado = ler_json(caminho, {})
    noite = rubin.ultima_noite()
    if noite is None:
        log.warning("rubin_sem_estatistica")
        return False
    dias = (datetime.now(timezone.utc) - datetime.strptime(noite, "%Y%m%d").replace(tzinfo=timezone.utc)).days
    ativo = dias <= rubin.DIAS_PARADO
    if ativo and estado.get("parado_desde"):
        alertas.notificar(
            "CacaSN: o Rubin voltou!",
            f"Alertas do Rubin de novo (noite {noite}). Pouca concorrência agora.",
            os.path.join(pasta, "report.html"),
        )
    if not ativo:
        log.warning("rubin_parado", ultima_noite=noite, dias=dias)
    gravar_json(caminho, {"ultima_noite": noite, "parado_desde": None if ativo else (estado.get("parado_desde") or noite)})
    return ativo


def rodar_rubin(dias: float, tns: dict[str, Any] | None) -> list[dict[str, Any]]:
    itens = [rubin.objeto(oid, als) for oid, als in rubin.por_objeto(rubin.alertas(dias)).items()]
    itens.sort(key=lambda x: -x["nota"])
    for it in itens[:TOP_RUBIN_TNS]:
        completa = rubin.curva_completa(it["oid"].replace("LSST ", ""))
        if completa:
            it["mjd0"], it["curva"] = completa
            dias = curva.duracao(it["curva"])
            if dias > curva.DURACAO_VARIAVEL:
                it["nota"] = round(it["nota"] - 5, 2)
                it["motivos"].append(f"detectado há {dias:.0f} dias ({len(it['curva'])} pontos): varia há meses")
        avaliacao.conferir_conhecidos(it)
    itens.sort(key=lambda x: -x["nota"])
    for i, it in enumerate(itens):
        if it["conhecido"]:
            continue
        if tns and i < TOP_RUBIN_TNS:
            it["conhecido"] = avaliacao.situacao_tns(tns, it["ra"], it["dec"])
        else:
            it["conhecido"] = "TNS não consultado (fora do top)" if tns else "TNS não consultado (falta tns.json)"
    return itens


def rodar(dias: float, prob: float, avisar: bool, pasta: str = PASTA, fontes: tuple[str, ...] = FONTES) -> list[dict[str, Any]]:
    log = registro.obter()
    tns = catalogos.tns_carregar(pasta)
    itens: list[dict[str, Any]] = []
    if "ztf" in fontes:
        itens += rodar_ztf(dias, prob, tns, pasta)
    if "rubin" in fontes:
        vigiar_fluxo_rubin(pasta)
        itens += rodar_rubin(dias, tns)
    for it in itens:
        if (m := curva.motivo_subida(it.get("curva", []), it.get("idade", 99))) and m not in it["motivos"]:
            it["motivos"].append(m)
    gravar_json(os.path.join(pasta, "resultados.json"), itens, indent=1)
    gravar_texto(os.path.join(pasta, "report.html"), relatorio(itens))
    for fonte in fontes:
        sel = [i for i in itens if i.get("fonte") == fonte]
        log.info(
            "rodada",
            fonte=fonte,
            dias=dias,
            avaliados=len(sel),
            fora_do_tns=sum(i["conhecido"].startswith("NÃO") for i in sel),
            melhor_nota=max((i["nota"] for i in sel), default=0),
            top=[[i["oid"], i["nota"], i["conhecido"]] for i in sorted(sel, key=lambda x: -x["nota"])[:5]],
        )
    if avisar:
        alertas.avisar_novos(itens, pasta)
    acompanhamento.verificar(tns, pasta)
    return itens


def gerar_rascunho(oid: str, pasta: str = PASTA) -> int:
    """Escreve rascunhos/<oid>.json para revisar e enviar pelo site do TNS."""
    itens = ler_json(os.path.join(pasta, "resultados.json"), [])
    it = next((i for i in itens if i["oid"] == oid or i["oid"] == f"LSST {oid}"), None)
    if it is None:
        print(f"{oid} não está no último resultados.json")
        return 1
    if not it["conhecido"].startswith("NÃO"):
        print(f"atenção: {it['conhecido']}")
    relatorio, pendencias = rascunho(it, catalogos.tns_carregar(pasta))
    os.makedirs(os.path.join(pasta, "rascunhos"), exist_ok=True)
    destino = os.path.join(pasta, "rascunhos", f"{it['oid'].replace(' ', '_')}.json")
    gravar_json(destino, relatorio, indent=2, ensure_ascii=False)
    print(destino)
    for p in pendencias:
        print(f"  pendente: {p}")
    print("  nada foi enviado. Revise e envie pelo site do TNS (teste antes em https://sandbox.wis-tns.org).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="cacasn", description="Caçador de supernovas nos alertas do ZTF (ALeRCE) e do Rubin (Fink)."
    )
    ap.add_argument(
        "--dias",
        type=float,
        default=21,
        help="primeira detecção há no máximo N dias (a nota sobe com as noites: os 2 de out/2026 tinham 16-20 dias)",
    )
    ap.add_argument("--prob", type=float, default=0.5, help="ZTF: probabilidade mínima de SN no stamp classifier")
    ap.add_argument("--fonte", choices=(*FONTES, "ambas"), default="ambas", help="de onde buscar os alertas")
    ap.add_argument(
        "--avisar",
        action="store_true",
        help=f"avisa candidato fora do TNS (ZTF: nota >= {alertas.AVISO}; Rubin: >= {rubin.AVISO})",
    )
    ap.add_argument(
        "--acompanhar", metavar="NOME", help="passa a acompanhar um objeto do TNS (ex.: 2026agsv) e avisa quando for classificado"
    )
    ap.add_argument("--rascunho", metavar="OID", help="gera o relatório para o TNS de um candidato da última rodada (não envia)")
    args = ap.parse_args(argv)
    if args.rascunho:
        return gerar_rascunho(args.rascunho)
    if args.acompanhar:
        acompanhamento.adicionar(PASTA, args.acompanhar)
        acompanhamento.verificar(catalogos.tns_carregar(PASTA), PASTA)
        print(acompanhamento.ler_json(os.path.join(PASTA, acompanhamento.ARQUIVO), {}))
        return 0
    registro.configurar(os.path.join(PASTA, "cacasn.log"))
    fontes = FONTES if args.fonte == "ambas" else (args.fonte,)
    try:
        rodar(args.dias, args.prob, args.avisar, fontes=fontes)
    except Exception as e:
        registro.obter().error("rodada_falhou", erro=repr(e))
        raise
    print(os.path.join(PASTA, "report.html"))
    return 0
