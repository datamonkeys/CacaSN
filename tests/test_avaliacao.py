import unittest
from unittest import mock

from caca_sn import avaliacao, catalogos
from tests.ajuda import OBJ, det, falso_get_json


def avaliar(dets, probs=None, vizier=(), tns=None, tns_busca=None):
    with (
        mock.patch.object(avaliacao, "get_json", falso_get_json(dets, probs)),
        mock.patch.object(catalogos, "vizier", return_value=None if vizier is None else list(vizier)),
        mock.patch.object(catalogos, "tns_busca", tns_busca or mock.Mock(return_value=[])),
    ):
        return avaliacao.avaliar(OBJ, tns)


class TesteBrilho(unittest.TestCase):
    def test_nao_mistura_filtros(self):
        self.assertFalse(avaliacao.subindo_de_brilho([det(1, 1, 20.0), det(2, 2, 19.5)]))

    def test_subida_no_mesmo_filtro(self):
        self.assertTrue(avaliacao.subindo_de_brilho([det(1, 1, 20.0), det(2, 1, 19.5)]))


class TesteAvaliar(unittest.TestCase):
    DUAS = [det(1, 1, 20.0, stamp=True), det(2, 1, 19.5)]

    def test_so_deteccoes_negativas_nao_quebra(self):
        self.assertIsNone(avaliar([det(1, 1, 20.0, pos=0), det(2, 1, 19.8, pos="f")]))

    def test_gaia_fora_do_ar_aparece_no_motivo(self):
        r = avaliar(self.DUAS, vizier=None)
        self.assertIn("Gaia não respondeu (estrela não descartada)", r["motivos"])

    def test_estrela_gaia_penaliza_8(self):
        limpo = avaliar(self.DUAS)["nota"]
        estrela = avaliar(self.DUAS, vizier=[["123", "5.0", "0.5", "1", "1"]])
        self.assertAlmostEqual(limpo - estrela["nota"], 8, places=2)

    def test_classificador_2025_entra_na_nota(self):
        sn = [{"classifier_name": "stamp_classifier_2025_beta", "class_name": "SN", "probability": 1.0}]
        agn = [{"classifier_name": "stamp_classifier_2025_beta", "class_name": "AGN", "probability": 1.0}]
        self.assertAlmostEqual(avaliar(self.DUAS, sn)["nota"] - avaliar(self.DUAS, agn)["nota"], 15, places=2)

    def test_distnr_sem_fonte_nao_vira_nucleo(self):
        r = avaliar([det(1, 1, 20.0, distnr=-999), det(2, 1, 19.5, distnr=-999)])
        self.assertNotIn("no centro", " ".join(r["motivos"]))

    def test_distnr_perto_vira_nucleo(self):
        r = avaliar([det(1, 1, 20.0, distnr=0.2), det(2, 1, 19.5)])
        self.assertIn("no centro", " ".join(r["motivos"]))

    def test_historico_longo_penaliza(self):
        antigo = dict(OBJ, ndethist=80)
        with (
            mock.patch.object(avaliacao, "get_json", falso_get_json(self.DUAS)),
            mock.patch.object(catalogos, "vizier", return_value=[]),
        ):
            r = avaliacao.avaliar(antigo, None)
        self.assertIn("80 detecções no histórico (fonte antiga)", r["motivos"])

    def test_resultado_do_tns(self):
        cfg = {"bot_id": 1, "bot_name": "b", "api_key": "k"}
        self.assertEqual(
            avaliar(self.DUAS, tns=cfg, tns_busca=mock.Mock(return_value=["AT 2026abc"]))["conhecido"], "TNS: AT 2026abc"
        )
        self.assertEqual(avaliar(self.DUAS, tns=cfg)["conhecido"], "NÃO está no TNS — dá para reportar")
        self.assertEqual(
            avaliar(self.DUAS, tns=cfg, tns_busca=mock.Mock(side_effect=TimeoutError()))["conhecido"],
            "TNS não respondeu (TimeoutError)",
        )
        self.assertEqual(avaliar(self.DUAS)["conhecido"], "TNS não consultado (falta tns.json)")

    def test_recortes_da_primeira_deteccao_com_imagem(self):
        r = avaliar([det(1, 1, 20.0), det(2, 1, 19.5, stamp=True)])
        self.assertIn("candid=c2", r["stamps"]["difference"])


if __name__ == "__main__":
    unittest.main()
