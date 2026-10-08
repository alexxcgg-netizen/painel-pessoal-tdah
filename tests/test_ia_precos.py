import unittest

from ia import precos


class TestCustoComArquivoReal(unittest.TestCase):
    def test_luna_um_milhao_de_cada(self):
        self.assertAlmostEqual(precos.custo_usd("gpt-6-luna", 1_000_000, 1_000_000), 0.60)

    def test_cache_da_luna(self):
        self.assertAlmostEqual(precos.custo_usd("gpt-6-luna", 0, 0, 1_000_000, 1_000_000), 0.135)

    def test_sol_acima_do_limiar_dobra_entrada_e_multiplica_saida(self):
        abaixo = precos.custo_usd("gpt-6-sol", 272_000, 1_000_000)
        acima = precos.custo_usd("gpt-6-sol", 272_001, 1_000_000)
        self.assertAlmostEqual(abaixo, 0.544 + 10.0)
        self.assertAlmostEqual(acima, 272_001 * 4.0 / 1e6 + 15.0, places=6)

    def test_sonnet_cache_escrita_por_ttl(self):
        self.assertAlmostEqual(precos.custo_usd("claude-sonnet-5", 0, 0, 0, 1_000_000), 2.50)
        self.assertAlmostEqual(precos.custo_usd("claude-sonnet-5", 0, 0, 0, 1_000_000, ttl_cache="1h"), 4.00)

    def test_haiku_tem_preco(self):
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-4-5-20251001", 1_000_000, 0), 1.00)

    def test_modelo_desconhecido_e_arquivo_quebrado_nao_quebram(self):
        self.assertEqual(precos.custo_usd("modelo-que-nao-existe", 10, 10), 0.0)
        self.assertEqual(precos.custo_usd("gpt-6-luna", 10, 10, precos={"modelos": "lixo"}), 0.0)
        self.assertEqual(precos.custo_usd("gpt-6-luna", 10, 10, precos={}), 0.0)

    def test_adapters_usam_a_mesma_fonte(self):
        from ia.adapters import anthropic as ad_anthropic
        from ia.adapters import openai as ad_openai
        self.assertAlmostEqual(ad_anthropic._calcular_custo_usd("claude-sonnet-5", 1_000_000, 0, 0, 0), 2.0)
        self.assertAlmostEqual(ad_openai.AdapterOpenAI._calcular_custo("gpt-6-luna", 1_000_000, 0, 0, 0), 0.10)


if __name__ == "__main__":
    unittest.main()


class TestChavesBatemComIdsDosModelos(unittest.TestCase):
    def test_gemini_flash_lite_tem_preco(self):
        self.assertGreater(precos.custo_usd("gemini-3.5-flash-lite", 1_000_000, 0), 0)


class TestHaiku55(unittest.TestCase):
    """Tabela oficial: ate 100 mil tokens 0,10/0,50 (cache 0,125 5min, 0,20 1h, leitura 0,01);
    acima, 0,50/2,50 (0,625, 1,00, 0,05)."""

    def test_faixa_ate_100_mil(self):
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-5-5", 100_000, 0), 0.01)
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-5-5", 0, 1_000_000), 0.50)
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-5-5", 0, 0, 1_000_000, 0), 0.01)
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-5-5", 0, 0, 0, 1_000_000, "5m"), 0.125)
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-5-5", 0, 0, 0, 1_000_000, "1h"), 0.20)

    def test_faixa_acima_de_100_mil(self):
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-5-5", 200_000, 1_000_000), 0.10 + 2.50)
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-5-5", 100_001, 0, 1_000_000, 0), 0.05 + 0.050005, places=3)
        self.assertAlmostEqual(precos.custo_usd("claude-haiku-5-5", 100_001, 0, 0, 1_000_000, "1h"), 1.0 + 0.050005, places=3)
