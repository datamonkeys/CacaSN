import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

from caca_sn import catalogos


class TesteGaia(unittest.TestCase):
    def test_estrela_com_paralaxe(self):
        with mock.patch.object(catalogos, "vizier", return_value=[["123", "5.0", "0.5", "1", "1"]]):
            self.assertEqual(catalogos.estrela_gaia(1, 2), "123")

    def test_sem_estrela(self):
        with mock.patch.object(catalogos, "vizier", return_value=[["9", "0.1", "0.5", "0", "0"]]):
            self.assertIsNone(catalogos.estrela_gaia(1, 2))

    def test_catalogo_fora_do_ar(self):
        with mock.patch.object(catalogos, "vizier", return_value=None):
            self.assertIs(catalogos.estrela_gaia(1, 2), catalogos.SEM_RESPOSTA)


class TesteCredenciais(unittest.TestCase):
    def test_variaveis_de_ambiente(self):
        env = {"TNS_BOT_ID": "7", "TNS_BOT_NAME": "b", "TNS_API_KEY": "k"}
        with mock.patch.dict(os.environ, env), tempfile.TemporaryDirectory() as d:
            self.assertEqual(catalogos.tns_carregar(d), {"bot_id": 7, "bot_name": "b", "api_key": "k"})

    def test_arquivo_ou_nada(self):
        limpo = {k: v for k, v in os.environ.items() if not k.startswith("TNS_")}
        with mock.patch.dict(os.environ, limpo, clear=True), tempfile.TemporaryDirectory() as d:
            self.assertIsNone(catalogos.tns_carregar(d))
            with open(os.path.join(d, "tns.json"), "w") as f:
                json.dump({"bot_id": 1, "bot_name": "x", "api_key": "y"}, f)
            self.assertEqual(catalogos.tns_carregar(d)["bot_id"], 1)


class TesteTNS(unittest.TestCase):
    CFG = {"bot_id": 1, "bot_name": "b", "api_key": "k"}

    def resposta(self, dados):
        ok = mock.MagicMock()
        ok.__enter__.return_value = io.StringIO(json.dumps({"data": dados}))
        return ok

    def test_429_espera_e_tenta_de_novo(self):
        erro = urllib.error.HTTPError("u", 429, "x", {"x-cone-rate-limit-reset": "0"}, None)
        with (
            mock.patch("urllib.request.urlopen", side_effect=[erro, self.resposta([{"prefix": "AT", "objname": "2026abc"}])]),
            mock.patch.object(catalogos.time, "sleep"),
        ):
            self.assertEqual(catalogos.tns_busca(self.CFG, 1.0, 2.0), ["AT 2026abc"])

    def test_erro_de_rede_tenta_de_novo(self):
        with (
            mock.patch("urllib.request.urlopen", side_effect=[urllib.error.URLError("x"), self.resposta([])]),
            mock.patch.object(catalogos.time, "sleep"),
        ):
            self.assertEqual(catalogos.tns_busca(self.CFG, 1.0, 2.0), [])

    def test_outro_erro_http_sobe(self):
        erro = urllib.error.HTTPError("u", 401, "x", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=erro), mock.patch.object(catalogos.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                catalogos.tns_busca(self.CFG, 1.0, 2.0)


if __name__ == "__main__":
    unittest.main()
