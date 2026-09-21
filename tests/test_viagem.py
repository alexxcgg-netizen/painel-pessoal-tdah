import unittest

from viagem import custo_combustivel


class CustoCombustivelTestCase(unittest.TestCase):
    def test_calculo_basico(self):
        r = custo_combustivel(distancia_km=160.0, km_por_litro=16.0, preco_por_litro=6.0)
        self.assertEqual(r["litros"], 10.0)
        self.assertEqual(r["custo"], 60.0)

    def test_arredonda_litros_e_custo(self):
        r = custo_combustivel(distancia_km=100.0, km_por_litro=3.0, preco_por_litro=5.79)
        self.assertEqual(r["litros"], 33.3)
        self.assertEqual(r["custo"], round((100.0 / 3.0) * 5.79, 2))

    def test_distancia_grande_estilo_brusque_foz_do_iguacu(self):
        # aproximadamente a distancia real de estrada entre as duas cidades
        r = custo_combustivel(distancia_km=850.0, km_por_litro=16.0, preco_por_litro=6.0)
        self.assertEqual(r["litros"], 53.1)
        self.assertAlmostEqual(r["custo"], 318.75, delta=0.5)

    def test_distancia_zero_custa_zero(self):
        r = custo_combustivel(distancia_km=0.0, km_por_litro=16.0, preco_por_litro=6.0)
        self.assertEqual(r["litros"], 0.0)
        self.assertEqual(r["custo"], 0.0)


if __name__ == "__main__":
    unittest.main()
