import unittest

from caca_sn.rascunho import data_tns, rascunho

ZTF = {
    "oid": "ZTF26x",
    "ra": 10.5,
    "dec": -5.25,
    "mjd0": 61330.25,
    "fonte": "ztf",
    "motivos": ["2 noites"],
    "curva": [(0.0, 1, 19.8), (1.0, 2, 19.5)],
}
RUBIN = {
    "oid": "LSST 170",
    "ra": 1.0,
    "dec": 2.0,
    "mjd0": 61218.0,
    "fonte": "rubin",
    "motivos": [],
    "curva": [(0.0, 1, 20.0), (0.5, 2, 19.9)],
}
CFG = {"reporting_groupid": 999, "reporter": "A. Pessoa"}


class TesteData(unittest.TestCase):
    def test_formato_e_virada_do_dia(self):
        self.assertEqual(data_tns(51544.5), "2000-01-01.50000")
        self.assertEqual(data_tns(61218.999999), "2026-06-28.00000")


class TesteRascunho(unittest.TestCase):
    def test_ztf(self):
        r, pend = rascunho(ZTF, CFG)
        at = r["at_report"]["0"]
        self.assertEqual(pend, [])
        self.assertEqual(at["data_source_groupid"], "48")
        self.assertEqual(at["discovery_datetime"], "2026-10-17.25000")
        self.assertEqual([p["filterid"] for p in at["photometry"].values()], ["110", "111"])
        self.assertEqual({p["instrumentid"] for p in at["photometry"].values()}, {"196"})
        self.assertEqual(at["reporting_groupid"], "999")

    def test_rubin_e_filtro_inferido(self):
        r, pend = rascunho(RUBIN, CFG)
        at = r["at_report"]["0"]
        self.assertEqual(at["data_source_groupid"], "165")
        self.assertEqual(at["internal_name"], "170")
        self.assertTrue(any("inferidos" in p for p in pend))  # usou o r do LSST

    def test_observacoes_em_ingles(self):
        at = rascunho(dict(ZTF, motivos=["subindo 0.5 mag/dia"], drb=0.99, prob=0.8), CFG)[0]["at_report"]["0"]
        self.assertIn("Real/bogus 0.99", at["remarks"])
        self.assertNotIn("subindo", at["remarks"])

    def test_pendencias_sem_config(self):
        _, pend = rascunho(ZTF, None)
        self.assertEqual(len(pend), 2)

    def test_sem_data_e_erro(self):
        with self.assertRaises(ValueError):
            rascunho({k: v for k, v in ZTF.items() if k != "mjd0"}, CFG)


if __name__ == "__main__":
    unittest.main()
