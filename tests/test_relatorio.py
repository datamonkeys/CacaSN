import unittest

from caca_sn.relatorio import mini_curva, relatorio

IT = {
    "oid": "ZTF26x",
    "nota": 9.5,
    "mag": 19.2,
    "idade": 1.0,
    "prob": 0.8,
    "drb": 0.99,
    "ra": 1.0,
    "dec": -2.0,
    "motivos": ["<b>x</b>"],
    "conhecido": "NÃO está no TNS — dá para reportar",
    "stamps": {"science": "https://s?a=1&b=2"},
    "curva": [(0.0, 1, 20.0), (0.0, 2, 19.9)],
}


class TesteRelatorio(unittest.TestCase):
    def test_escapa_e_marca_novo(self):
        h = relatorio([IT])
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", h)
        self.assertIn("a=1&amp;b=2", h)
        self.assertIn('class="novo"', h)

    def test_ordena_pela_nota(self):
        h = relatorio([dict(IT, oid="baixo", nota=1.0), dict(IT, oid="alto", nota=30.0)])
        self.assertLess(h.index("alto"), h.index("baixo"))

    def test_curva_com_um_instante_so(self):
        self.assertIn("<svg", mini_curva(IT["curva"]))
        self.assertEqual(mini_curva([]), "")


if __name__ == "__main__":
    unittest.main()
