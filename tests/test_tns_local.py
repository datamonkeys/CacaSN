import io
import os
import tempfile
import unittest
import zipfile

from caca_sn import tns_local

CFG = {"bot_id": 1, "bot_name": "b", "api_key": "k"}


def zipado(linhas):
    texto = "2026-10-24 00:00:00\n" + '"name_prefix","name","ra","declination"\n' + "".join(linhas)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("tns.csv", texto)
    return buf.getvalue()


ARQ = zipado(['"AT","2026agsv","41.171781","-5.379759"\n', '"SN","2026zero","359.9995","10.0"\n', '"AT","ruim","x","y"\n'])


class TesteIndice(unittest.TestCase):
    def setUp(self):
        self.idx = tns_local.IndiceTNS(tns_local.ler(ARQ))

    def test_acha_dentro_de_3_arcsec(self):
        self.assertEqual(self.idx.buscar(41.171781 + 1.5 / 3600, -5.379759), ["AT 2026agsv"])
        self.assertEqual(self.idx.buscar(41.171781 + 10 / 3600, -5.379759), [])

    def test_cruza_ra_zero(self):
        self.assertEqual(self.idx.buscar(0.0002, 10.0), ["SN 2026zero"])  # 0.0007° = 2.5" do outro lado

    def test_linha_ruim_e_ignorada(self):
        self.assertEqual(self.idx.total, 2)


class TesteCarregar(unittest.TestCase):
    def test_baixa_uma_vez_e_usa_o_cache(self):
        chamadas = []

        def obter(cfg):
            chamadas.append(1)
            return ARQ

        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(tns_local.carregar(CFG, d, obter).total, 2)
            self.assertEqual(tns_local.carregar(CFG, d, obter).total, 2)
        self.assertEqual(len(chamadas), 1)

    def test_falha_sem_cache_vira_none_com_cache_usa_o_velho(self):
        def falha(cfg):
            raise OSError("fora")

        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(tns_local.carregar(CFG, d, falha))
            tns_local.carregar(CFG, d, lambda c: ARQ)
            caminho = os.path.join(d, "cache", tns_local.ARQUIVO)
            os.utime(caminho, (0, 0))  # muito velho: tenta rebaixar, falha, usa o que tem
            self.assertEqual(tns_local.carregar(CFG, d, falha).total, 2)

    def test_sem_credenciais(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(tns_local.carregar(None, d))


if __name__ == "__main__":
    unittest.main()
