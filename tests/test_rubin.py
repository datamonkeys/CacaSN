import math
import unittest

from caca_sn import alertas, rubin


def alerta(
    oid=1,
    sid=10,
    mjd=61230.0,
    banda="g",
    fluxo=20000.0,
    snr=40.0,
    rel=0.95,
    ext=0.1,
    snn=0.8,
    dipolo=False,
    sso=0,
    tns=float("nan"),
    zphot=None,
    referencia=0.0,
):
    return {
        "r:diaObjectId": oid,
        "r:diaSourceId": sid,
        "r:ra": 10.0,
        "r:dec": -5.0,
        "r:midpointMjdTai": mjd,
        "r:band": banda,
        "r:psfFlux": fluxo,
        "r:snr": snr,
        "r:reliability": rel,
        "r:extendedness": ext,
        "f:clf_snnSnVsOthers_score": snn,
        "r:isDipole": dipolo,
        "r:ssObjectId": sso,
        "f:xm_tns_fullname": tns,
        "f:xm_legacydr8_zphot": zphot,
        "r:templateFlux": referencia,
    }


class TesteConversoes(unittest.TestCase):
    def test_magnitude_ab(self):
        self.assertAlmostEqual(rubin.mag_ab(3631e9), 0.0, places=2)  # 3631 Jy = mag 0
        self.assertIsNone(rubin.mag_ab(-5))

    def test_valores_vazios_do_fink(self):
        for v in (None, float("nan"), "nan", "None", "Fail", ""):
            self.assertIsNone(rubin.texto(v))
        self.assertEqual(rubin.num(float("nan"), 7), 7)


class TesteNota(unittest.TestCase):
    def test_real_e_brilhante_bate_ruido(self):
        bom = rubin.pontuar([alerta(), alerta(sid=11, mjd=61231, banda="r")])[0]
        ruim = rubin.pontuar([alerta(fluxo=-500, snr=6, rel=0.3, ext=0.9, snn=0.1, dipolo=True)])[0]
        self.assertGreater(bom, ruim + 5)

    def test_galaxia_com_redshift_soma(self):
        com = rubin.pontuar([alerta(zphot=0.3)])[0]
        sem = rubin.pontuar([alerta()])[0]
        self.assertAlmostEqual(com - sem, 1.0)

    def test_fonte_nova_bate_fonte_antiga(self):
        nova, m1 = rubin.pontuar([alerta(referencia=0)])
        antiga, m2 = rubin.pontuar([alerta(referencia=200000)])
        self.assertGreater(nova - antiga, 1.5)
        self.assertIn("fonte nova", m1)
        self.assertTrue(any("já existia" in m for m in m2))

    def test_motivos(self):
        _, m = rubin.pontuar([alerta(dipolo=True, fluxo=-10), alerta(sid=2, banda="r", dipolo=True, fluxo=-10)])
        self.assertIn("dipolo (subtração ruim?)", m)
        self.assertIn("fluxo negativo (ficou mais fraco)", m)
        self.assertIn("2 filtros", m)


class TesteObjeto(unittest.TestCase):
    def test_formato_igual_ao_do_ztf(self):
        als = [alerta(mjd=61231, sid=12), alerta(mjd=61230, sid=11)]
        it = rubin.objeto(1, als)
        for chave in ("oid", "ra", "dec", "nota", "prob", "drb", "motivos", "conhecido", "stamps", "curva", "idade", "mag"):
            self.assertIn(chave, it)
        self.assertEqual(it["fonte"], "rubin")
        self.assertIn("diaSourceId=12", it["stamps"]["difference"])  # recorte do alerta mais recente
        self.assertEqual(it["curva"][0][0], 0.0)

    def test_ja_no_tns_pelo_fink(self):
        it = rubin.objeto(1, [alerta(tns="AT 2026abc")])
        self.assertEqual(it["conhecido"], "TNS: AT 2026abc (Fink)")

    def test_asteroide_conhecido_afunda(self):
        normal = rubin.objeto(1, [alerta()])["nota"]
        asteroide = rubin.objeto(1, [alerta(sso=99)])
        self.assertAlmostEqual(normal - asteroide["nota"], 10, places=2)
        self.assertIn("asteroide conhecido", asteroide["motivos"])

    def test_agrupa_por_objeto(self):
        g = rubin.por_objeto([alerta(oid=1), alerta(oid=2), alerta(oid=1, sid=3)])
        self.assertEqual(sorted(len(v) for v in g.values()), [1, 2])


class TesteBusca(unittest.TestCase):
    def test_data_em_iso_e_deduplica(self):
        from unittest import mock

        chamadas = []

        def falso(url, tentativas=4):
            chamadas.append(url)
            return [alerta(sid=1), alerta(sid=2)]

        with mock.patch.object(rubin, "get_json", falso):
            als = rubin.alertas(3)
        self.assertEqual(len(chamadas), len(rubin.TAGS))
        self.assertRegex(chamadas[0], r"startdate=\d{4}-\d{2}-\d{2}\+\d{2}%3A")
        self.assertEqual(sorted(a["r:diaSourceId"] for a in als), [1, 2])  # o mesmo alerta em várias categorias conta uma vez


class TesteCorte(unittest.TestCase):
    def test_corte_por_fonte(self):
        self.assertEqual(alertas.corte({"fonte": "rubin"}), rubin.AVISO)
        self.assertEqual(alertas.corte({}), alertas.AVISO)
        self.assertTrue(math.isfinite(rubin.AVISO))


if __name__ == "__main__":
    unittest.main()
