"""Testes offline do CacaSN (as APIs são simuladas). python3 -m unittest discover testes"""
import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cacasn

OBJ = {"oid": "ZTF26teste", "meanra": 10.0, "meandec": -5.0, "probability": 0.8,
       "firstmjd": cacasn.mjd_agora() - 2, "ndethist": 3, "stellar": False}


def det(mjd, fid, mag, pos=1, stamp=False, drb=0.99):
    return {"mjd": mjd, "fid": fid, "magpsf": mag, "isdiffpos": pos, "has_stamp": stamp,
            "candid": f"c{mjd}", "drb": drb, "distnr": 2.0}


def falso_get_json(dets, probs=None):
    def f(url, tentativas=4):
        if url.endswith("/detections"):
            return dets
        if url.endswith("/probabilities"):
            return probs or []
        raise AssertionError(url)
    return f


class TesteBrilho(unittest.TestCase):
    def test_nao_mistura_filtros(self):
        # g 20.0 depois r 19.5: é cor, não subida
        self.assertFalse(cacasn.subindo_de_brilho([det(1, 1, 20.0), det(2, 2, 19.5)]))

    def test_subida_no_mesmo_filtro(self):
        self.assertTrue(cacasn.subindo_de_brilho([det(1, 1, 20.0), det(2, 1, 19.5)]))


class TesteAvaliar(unittest.TestCase):
    def test_so_deteccoes_negativas_nao_quebra(self):
        dets = [det(1, 1, 20.0, pos=0), det(2, 1, 19.8, pos="f")]
        with mock.patch.object(cacasn, "get_json", falso_get_json(dets)):
            self.assertIsNone(cacasn.avaliar(OBJ, None))

    def test_gaia_fora_do_ar_aparece_no_motivo(self):
        dets = [det(1, 1, 20.0, stamp=True), det(2, 1, 19.5)]
        with mock.patch.object(cacasn, "get_json", falso_get_json(dets)), \
             mock.patch.object(cacasn, "vizier", return_value=None):
            r = cacasn.avaliar(OBJ, None)
        self.assertIn("Gaia não respondeu (estrela não descartada)", r["motivos"])
        self.assertNotIn("variável", " ".join(r["motivos"]))

    def test_estrela_gaia_penaliza(self):
        dets = [det(1, 1, 20.0), det(2, 1, 19.5)]
        linha = [["123", "5.0", "0.5", "1", "1"]]  # paralaxe 10σ
        with mock.patch.object(cacasn, "get_json", falso_get_json(dets)), \
             mock.patch.object(cacasn, "vizier", return_value=[]):
            limpo = cacasn.avaliar(OBJ, None)["nota"]
        with mock.patch.object(cacasn, "get_json", falso_get_json(dets)), \
             mock.patch.object(cacasn, "vizier", return_value=linha):
            estrela = cacasn.avaliar(OBJ, None)
        self.assertAlmostEqual(limpo - estrela["nota"], 8, places=2)
        self.assertTrue(any("Gaia 123" in m for m in estrela["motivos"]))

    def test_classificador_2025_entra_na_nota(self):
        dets = [det(1, 1, 20.0), det(2, 1, 19.5)]
        sn = [{"classifier_name": "stamp_classifier_2025_beta", "class_name": "SN", "probability": 1.0}]
        agn = [{"classifier_name": "stamp_classifier_2025_beta", "class_name": "AGN", "probability": 1.0}]
        with mock.patch.object(cacasn, "vizier", return_value=[]):
            with mock.patch.object(cacasn, "get_json", falso_get_json(dets, sn)):
                a = cacasn.avaliar(OBJ, None)["nota"]
            with mock.patch.object(cacasn, "get_json", falso_get_json(dets, agn)):
                b = cacasn.avaliar(OBJ, None)["nota"]
        self.assertAlmostEqual(a - b, 15, places=2)

    def test_relatorio_e_curva(self):
        dets = [det(1, 1, 20.0, stamp=True), det(1, 1, 20.0)]  # mesma hora: t1 - t0 = 0
        with mock.patch.object(cacasn, "get_json", falso_get_json(dets)), \
             mock.patch.object(cacasn, "vizier", return_value=[]):
            r = cacasn.avaliar(OBJ, None)
        h = cacasn.relatorio([r])
        self.assertIn("ZTF26teste", h)
        self.assertIn("<svg", h)
        self.assertIn("&amp;", h)  # links com & escapado


    def test_distnr_sem_fonte_nao_vira_nucleo(self):
        dets = [dict(det(1, 1, 20.0), distnr=-999), dict(det(2, 1, 19.5), distnr=-999)]
        with mock.patch.object(cacasn, "get_json", falso_get_json(dets)), \
             mock.patch.object(cacasn, "vizier", return_value=[]):
            r = cacasn.avaliar(OBJ, None)
        self.assertNotIn("no centro", " ".join(r["motivos"]))

    def test_resultado_do_tns(self):
        dets = [det(1, 1, 20.0), det(2, 1, 19.5)]
        cfg = {"bot_id": 1, "bot_name": "b", "api_key": "k"}
        casos = [(["AT 2026abc"], "TNS: AT 2026abc"), ([], "NÃO está no TNS — dá para reportar")]
        for volta, esperado in casos:
            with mock.patch.object(cacasn, "get_json", falso_get_json(dets)), \
                 mock.patch.object(cacasn, "vizier", return_value=[]), \
                 mock.patch.object(cacasn, "tns_busca", return_value=volta):
                self.assertEqual(cacasn.avaliar(OBJ, cfg)["conhecido"], esperado)
        with mock.patch.object(cacasn, "get_json", falso_get_json(dets)), \
             mock.patch.object(cacasn, "vizier", return_value=[]), \
             mock.patch.object(cacasn, "tns_busca", side_effect=TimeoutError()):
            self.assertEqual(cacasn.avaliar(OBJ, cfg)["conhecido"], "TNS não respondeu (TimeoutError)")


class TesteArquivos(unittest.TestCase):
    def test_gravar_json_atomico(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            cacasn.gravar_json(p, [1, 2])
            self.assertEqual(cacasn.ler_json(p, None), [1, 2])
            self.assertFalse(os.path.exists(p + ".tmp"))

    def test_ler_json_corrompido_usa_padrao(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "w") as f:
                f.write("{quebrado")
            self.assertEqual(cacasn.ler_json(p, []), [])

    def test_avisar_so_uma_vez(self):
        it = {"oid": "ZTF26a", "nota": 20.0, "conhecido": "NÃO está no TNS — dá para reportar"}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(cacasn, "AQUI", d), \
             mock.patch.object(cacasn, "notificar") as n:
            cacasn.avisar_novos([it])
            cacasn.avisar_novos([it])
        self.assertEqual(n.call_count, 1)


class TesteTNS(unittest.TestCase):
    def test_429_espera_e_tenta_de_novo(self):
        import io, urllib.error
        erro = urllib.error.HTTPError("u", 429, "x", {"x-cone-rate-limit-reset": "0"}, None)
        ok = mock.MagicMock()
        ok.__enter__.return_value = io.StringIO(json.dumps({"data": [{"prefix": "AT", "objname": "2026abc"}]}))
        cfg = {"bot_id": 1, "bot_name": "b", "api_key": "k"}
        with mock.patch("urllib.request.urlopen", side_effect=[erro, ok]), \
             mock.patch.object(cacasn.time, "sleep"):
            self.assertEqual(cacasn.tns_busca(cfg, 1.0, 2.0), ["AT 2026abc"])


if __name__ == "__main__":
    unittest.main()
