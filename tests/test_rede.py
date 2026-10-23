import os
import tempfile
import unittest
from unittest import mock

from caca_sn import rede


class TesteArquivos(unittest.TestCase):
    def test_gravar_json_atomico(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            rede.gravar_json(p, [1, 2])
            self.assertEqual(rede.ler_json(p, None), [1, 2])
            self.assertFalse(os.path.exists(p + ".tmp"))

    def test_ler_json_corrompido_usa_padrao(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "w") as f:
                f.write("{quebrado")
            self.assertEqual(rede.ler_json(p, []), [])


class TesteHttp(unittest.TestCase):
    def test_tenta_de_novo_com_espera_crescente(self):
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"a": 1}'
        with (
            mock.patch("urllib.request.urlopen", side_effect=[OSError(), OSError(), ok]),
            mock.patch.object(rede.time, "sleep") as dorme,
        ):
            self.assertEqual(rede.get_json("https://x"), {"a": 1})
        self.assertEqual([c.args[0] for c in dorme.call_args_list], [1, 2])

    def test_desiste_depois_das_tentativas(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("fora")), mock.patch.object(rede.time, "sleep"):
            with self.assertRaises(OSError):
                rede.get_json("https://x", tentativas=2)

    def test_user_agent_identifica_o_projeto(self):
        self.assertIn("github.com/louisperner/CacaSN", rede.HDR["User-Agent"])


if __name__ == "__main__":
    unittest.main()
