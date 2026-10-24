import json
import os
import tempfile
import unittest
from unittest import mock

from caca_sn import acompanhamento

CFG = {"bot_id": 1, "bot_name": "b", "api_key": "k"}
SEM_TIPO = {"name_prefix": "AT", "object_type": {"name": None}, "redshift": None}
SN_IA = {"name_prefix": "SN", "object_type": {"name": "SN Ia"}, "redshift": 0.05}


class TesteAcompanhamento(unittest.TestCase):
    def test_avisa_quando_classificam_e_so_uma_vez(self):
        respostas = [SEM_TIPO, SN_IA, SN_IA]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(acompanhamento.alertas, "notificar") as n:
            acompanhamento.adicionar(d, "AT 2026agsv")
            consultar = lambda cfg, nome: respostas.pop(0)  # noqa: E731
            self.assertEqual(acompanhamento.verificar(CFG, d, consultar), [])
            self.assertEqual(acompanhamento.verificar(CFG, d, consultar), ["AT 2026agsv -> SN 2026agsv = SN Ia (z = 0.05)"])
            self.assertEqual(acompanhamento.verificar(CFG, d, consultar), [])
            with open(os.path.join(d, acompanhamento.ARQUIVO)) as f:
                self.assertEqual(json.load(f)["2026agsv"]["tipo"], "SN Ia")
        self.assertEqual(n.call_count, 1)

    def test_primeira_consulta_ja_classificado_nao_avisa(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(acompanhamento.alertas, "notificar") as n:
            acompanhamento.adicionar(d, "2026adfo")
            self.assertEqual(acompanhamento.verificar(CFG, d, lambda c, nome: SN_IA), [])
        n.assert_not_called()

    def test_falha_do_tns_nao_quebra(self):
        def falha(cfg, nome):
            raise OSError("fora")

        with tempfile.TemporaryDirectory() as d:
            acompanhamento.adicionar(d, "2026agsv")
            self.assertEqual(acompanhamento.verificar(CFG, d, falha), [])

    def test_sem_credenciais_ou_lista(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(acompanhamento.verificar(None, d), [])
            self.assertEqual(acompanhamento.verificar(CFG, d), [])


if __name__ == "__main__":
    unittest.main()
