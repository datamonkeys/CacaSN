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
            itens = cli.rodar(3, 0.5, avisar=False, pasta=d)
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
        r.assert_called_once_with(1.0, 0.7, True)


if __name__ == "__main__":
    unittest.main()
