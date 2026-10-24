import unittest

from caca_sn.curva import DURACAO_VARIAVEL, duracao, motivo_subida, taxa_subida


class TesteSubida(unittest.TestCase):
    def test_taxa_por_filtro(self):
        # g sobe 1 mag em 2 dias; r está parado: vale a maior subida
        curva = [(0.0, 1, 20.0), (2.0, 1, 19.0), (0.0, 2, 19.5), (2.0, 2, 19.5)]
        self.assertAlmostEqual(taxa_subida(curva), 0.5)

    def test_nao_mistura_filtros(self):
        self.assertIsNone(taxa_subida([(0.0, 1, 20.0), (2.0, 2, 19.0)]))

    def test_mesma_noite_nao_mede(self):
        self.assertIsNone(taxa_subida([(0.0, 1, 20.0), (0.1, 1, 19.0)]))

    def test_motivos(self):
        self.assertEqual(
            motivo_subida([(0.0, 1, 20.0), (1.0, 1, 19.2)], idade=2), "subindo 0.80 mag/dia — rápido! (jovem e subindo)"
        )
        self.assertIsNone(motivo_subida([(0.0, 1, 19.0), (1.0, 1, 19.5)], idade=2))  # apagando
        self.assertIsNone(motivo_subida([], idade=2))


class TesteDuracao(unittest.TestCase):
    def test_duracao(self):
        self.assertEqual(duracao([(0.0, 1, 20.0), (148.0, 2, 19.0)]), 148.0)
        self.assertEqual(duracao([]), 0.0)
        self.assertGreater(DURACAO_VARIAVEL, 18)  # acima do mais longo reportado em julho


if __name__ == "__main__":
    unittest.main()
