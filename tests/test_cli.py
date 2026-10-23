import json
import os
import tempfile
import unittest
from unittest import mock

from caca_sn import avaliacao, catalogos, cli
from tests.ajuda import OBJ, det, falso_get_json


class TesteRodada(unittest.TestCase):
    def test_rodada_completa_grava_tudo(self):
        dets = [det(1, 1, 20.0, stamp=True), det(2, 1, 19.5)]
        with (
            tempfile.TemporaryDirectory() as d,
            mock.patch.object(avaliacao, "candidatos", return_value=[OBJ, dict(OBJ, oid="ZTF26quebrado", meanra=None)]),
            mock.patch.object(avaliacao, "get_json", falso_get_json(dets)),
            mock.patch.object(catalogos, "vizier", return_value=[]),
            mock.patch.object(catalogos, "tns_carregar", return_value=None),
        ):
            itens = cli.rodar(3, 0.5, avisar=False, pasta=d, fontes=("ztf",))
            with open(os.path.join(d, "resultados.json")) as f:
                salvos = json.load(f)
            with open(os.path.join(d, "report.html")) as f:
                html = f.read()
        self.assertEqual([i["oid"] for i in itens], ["ZTF26teste"])  # o quebrado não derruba a rodada
        self.assertEqual(salvos[0]["oid"], "ZTF26teste")
        self.assertIn("ZTF26teste", html)

    def test_argumentos(self):
        with mock.patch.object(cli, "rodar") as r, mock.patch.object(cli.registro, "configurar"), mock.patch("builtins.print"):
            self.assertEqual(cli.main(["--dias", "1", "--prob", "0.7", "--avisar"]), 0)
        r.assert_called_once_with(1.0, 0.7, True, fontes=("ztf", "rubin"))


class TesteRubinNaRodada(unittest.TestCase):
    def test_so_rubin_e_escolha_da_fonte(self):
        it = {
            "oid": "LSST 1",
            "nota": 14.0,
            "ra": 1.0,
            "dec": 2.0,
            "conhecido": "",
            "fonte": "rubin",
            "mag": 20.0,
            "idade": 1.0,
            "prob": 0.9,
            "drb": 0.99,
            "motivos": [],
            "stamps": {},
            "curva": [],
        }
        with (
            tempfile.TemporaryDirectory() as d,
            mock.patch.object(cli.rubin, "alertas", return_value=[]),
            mock.patch.object(cli.rubin, "por_objeto", return_value={1: []}),
            mock.patch.object(cli.rubin, "objeto", return_value=dict(it)),
            mock.patch.object(cli, "vigiar_fluxo_rubin", return_value=True),
            mock.patch.object(cli.avaliacao, "candidatos") as ztf,
            mock.patch.object(catalogos, "tns_carregar", return_value={"bot_id": 1, "bot_name": "b", "api_key": "k"}),
            mock.patch.object(cli.avaliacao, "conferir_conhecidos"),
            mock.patch.object(cli.avaliacao, "situacao_tns", return_value="NÃO está no TNS — dá para reportar"),
        ):
            itens = cli.rodar(3, 0.5, avisar=False, pasta=d, fontes=("rubin",))
        ztf.assert_not_called()
        self.assertEqual(itens[0]["conhecido"], "NÃO está no TNS — dá para reportar")

    def test_fonte_na_linha_de_comando(self):
        with mock.patch.object(cli, "rodar") as r, mock.patch.object(cli.registro, "configurar"), mock.patch("builtins.print"):
            cli.main(["--fonte", "rubin"])
        self.assertEqual(r.call_args.kwargs["fontes"], ("rubin",))


class TesteFluxoRubin(unittest.TestCase):
    def test_avisa_uma_vez_quando_volta(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(cli.alertas, "notificar") as n:
            with mock.patch.object(cli.rubin, "ultima_noite", return_value="20260714"):
                self.assertFalse(cli.vigiar_fluxo_rubin(d))
            hoje = cli.datetime.now(cli.timezone.utc).strftime("%Y%m%d")
            with mock.patch.object(cli.rubin, "ultima_noite", return_value=hoje):
                self.assertTrue(cli.vigiar_fluxo_rubin(d))
                self.assertTrue(cli.vigiar_fluxo_rubin(d))
        self.assertEqual(n.call_count, 1)
        self.assertIn("Rubin voltou", n.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
