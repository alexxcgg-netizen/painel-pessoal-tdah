# Testes da faixa N1 (Fase 7) - classificador_local/regras/n1_financas.py.
# Usa a infra real (Etapa 0, ja mesclada em fase7/integracao):
# db.init_db() aplica a migracao desta faixa sozinho e
# classificador_local.casar/executar descobrem o modulo sozinhos - nao
# precisa montar banco/roteador na mao.
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import classificador_local  # noqa: E402 (precisa vir depois do patch de DB_PATH)
from classificador_local.regras import n1_financas as regra  # noqa: E402


class TestCasarAcoesCriacao(unittest.TestCase):
    def test_assinei_nome_valor_por_mes(self):
        r = regra.casar("assinei Netflix 55 por mês")
        self.assertEqual(r["acao"], "criar_assinatura")
        self.assertEqual(r["parametros"]["nome"], "Netflix")
        self.assertEqual(r["parametros"]["valor"], 55.0)

    def test_assinei_o_nome_por_valor_com_virgula(self):
        r = regra.casar("assinei o Spotify por 21,90")
        self.assertEqual(r["parametros"]["nome"], "Spotify")
        self.assertEqual(r["parametros"]["valor"], 21.90)

    def test_assinei_a_nome_por_valor(self):
        r = regra.casar("assinei a Amazon Prime por 14,90")
        self.assertEqual(r["parametros"]["nome"], "Amazon Prime")

    def test_assinei_com_rs(self):
        r = regra.casar("assinei Netflix R$ 55 por mês")
        self.assertEqual(r["parametros"]["valor"], 55.0)

    def test_assinei_com_reais(self):
        r = regra.casar("assinei Netflix 55 reais")
        self.assertEqual(r["parametros"]["valor"], 55.0)

    def test_assinei_sem_sufixo_mensal(self):
        r = regra.casar("assinei Netflix 55")
        self.assertEqual(r["acao"], "criar_assinatura")
        self.assertEqual(r["parametros"]["valor"], 55.0)

    def test_assinei_valor_grande_com_milhar(self):
        r = regra.casar("assinei academia premium por 1.200,50")
        self.assertEqual(r["parametros"]["valor"], 1200.50)

    def test_comprei_em_nx_de_valor(self):
        r = regra.casar("comprei o celular em 10x de 300")
        self.assertEqual(r["acao"], "criar_compra_parcelada")
        self.assertEqual(r["parametros"]["descricao"], "celular")
        self.assertEqual(r["parametros"]["valor_parcela"], 300.0)
        self.assertEqual(r["parametros"]["n_parcelas"], 10)
        self.assertIsNone(r["parametros"]["cartao"])

    def test_comprei_valor_em_n_vezes_no_cartao(self):
        r = regra.casar("comprei geladeira 3000 em 12 vezes no nubank")
        self.assertEqual(r["parametros"]["descricao"], "geladeira")
        self.assertEqual(r["parametros"]["valor_total"], 3000.0)
        self.assertEqual(r["parametros"]["n_parcelas"], 12)
        self.assertEqual(r["parametros"]["cartao"], "nubank")

    def test_comprei_valor_em_n_vezes_na_cartao(self):
        r = regra.casar("comprei tv 2000 em 10 vezes na conta")
        self.assertEqual(r["parametros"]["cartao"], "conta")

    def test_comprei_nx_de_valor_com_cartao(self):
        r = regra.casar("comprei o notebook em 6x de 500 no inter")
        self.assertEqual(r["parametros"]["valor_parcela"], 500.0)
        self.assertEqual(r["parametros"]["cartao"], "inter")

    def test_comprei_valor_com_virgula(self):
        r = regra.casar("comprei fone 299,90 em 3 vezes")
        self.assertEqual(r["parametros"]["valor_total"], 299.90)

    def test_cancelei_a_nome(self):
        r = regra.casar("cancelei a Netflix")
        self.assertEqual(r["acao"], "cancelar_assinatura")
        self.assertEqual(r["parametros"]["nome"], "Netflix")

    def test_cancelei_o_nome(self):
        r = regra.casar("cancelei o Spotify")
        self.assertEqual(r["parametros"]["nome"], "Spotify")

    def test_cancelei_sem_artigo(self):
        r = regra.casar("cancelei Netflix")
        self.assertEqual(r["parametros"]["nome"], "Netflix")


class TestCasarConsultas(unittest.TestCase):
    def test_quanto_tenho_de_parcelas(self):
        r = regra.casar("quanto tenho de parcelas?")
        self.assertEqual(r["acao"], "consultar_parcelas")

    def test_quantas_parcelas_eu_tenho(self):
        r = regra.casar("quantas parcelas eu tenho?")
        self.assertEqual(r["acao"], "consultar_parcelas")

    def test_quais_assinaturas_eu_tenho(self):
        r = regra.casar("quais assinaturas eu tenho")
        self.assertEqual(r["acao"], "consultar_assinaturas")

    def test_quanto_gasto_com_assinaturas(self):
        r = regra.casar("quanto gasto com assinaturas?")
        self.assertEqual(r["acao"], "consultar_assinaturas")

    def test_maiusculas_tambem_casam(self):
        r = regra.casar("QUAIS ASSINATURAS EU TENHO")
        self.assertEqual(r["acao"], "consultar_assinaturas")


class TestCasarNaoCasa(unittest.TestCase):
    def test_frase_nao_relacionada(self):
        self.assertIsNone(regra.casar("isso aqui nao deveria casar com nada"))

    def test_string_vazia(self):
        self.assertIsNone(regra.casar(""))

    def test_so_espacos(self):
        self.assertIsNone(regra.casar("    "))

    def test_none(self):
        self.assertIsNone(regra.casar(None))

    def test_numero(self):
        self.assertIsNone(regra.casar(12345))

    def test_assinei_sem_valor(self):
        self.assertIsNone(regra.casar("assinei a Netflix"))

    def test_comprei_sem_parcelas(self):
        self.assertIsNone(regra.casar("comprei um celular"))

    def test_cancelei_vazio(self):
        self.assertIsNone(regra.casar("cancelei"))

    def test_frase_parecida_mas_de_outro_dominio(self):
        self.assertIsNone(regra.casar("marquei uma reunião para amanhã"))

    def test_gasto_avulso_nao_e_assinatura(self):
        self.assertIsNone(regra.casar("gastei 50 no mercado"))


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)


class TestExecutarCriarAssinatura(_Base):
    def test_cria_e_devolve_card(self):
        resultado = regra.casar("assinei Netflix 55 por mês")
        resposta = regra.executar(self.conn, resultado["parametros"])
        self.assertEqual(len(resposta["cards"]), 1)
        card = resposta["cards"][0]
        self.assertEqual(card["type"], "assinatura")
        self.assertEqual(card["data"]["nome"], "Netflix")
        self.assertEqual(card["data"]["valor"], 55.0)
        self.assertIn("Netflix", resposta["resumo_texto"])
        self.assertEqual(len(card["actions"]), 1)
        self.assertEqual(card["actions"][0]["tipo"], "desfazer")

    def test_dia_cobranca_e_o_dia_de_hoje(self):
        from datetime import date

        hoje = date(2026, 3, 15)
        resultado = regra.casar("assinei Disney 30")
        resposta = regra.executar(self.conn, resultado["parametros"], hoje=hoje)
        card = resposta["cards"][0]
        self.assertEqual(card["data"]["dia_cobranca"], 15)


class TestExecutarCancelarAssinatura(_Base):
    def test_cancela_existente(self):
        regra.executar(self.conn, {"acao": "criar_assinatura", "nome": "Netflix", "valor": 55})
        resposta = regra.executar(self.conn, {"acao": "cancelar_assinatura", "nome": "Netflix"})
        card = resposta["cards"][0]
        self.assertFalse(card["data"]["ativa"])
        self.assertIn("cancelada", resposta["resumo_texto"])

    def test_cancela_case_insensitive(self):
        regra.executar(self.conn, {"acao": "criar_assinatura", "nome": "Netflix", "valor": 55})
        resposta = regra.executar(self.conn, {"acao": "cancelar_assinatura", "nome": "netflix"})
        self.assertEqual(len(resposta["cards"]), 1)

    def test_cancela_inexistente_nao_quebra(self):
        resposta = regra.executar(self.conn, {"acao": "cancelar_assinatura", "nome": "Nao Existe"})
        self.assertEqual(resposta["cards"], [])
        self.assertIn("Não encontrei", resposta["resumo_texto"])


class TestExecutarCriarCompraParcelada(_Base):
    def test_cria_com_valor_parcela(self):
        resultado = regra.casar("comprei o celular em 10x de 300")
        resposta = regra.executar(self.conn, resultado["parametros"])
        card = resposta["cards"][0]
        self.assertEqual(card["type"], "compra_parcelada")
        self.assertEqual(card["data"]["valor_total"], 3000.0)
        self.assertEqual(card["data"]["n_parcelas"], 10)

    def test_cria_com_valor_total(self):
        resultado = regra.casar("comprei geladeira 3000 em 12 vezes no nubank")
        resposta = regra.executar(self.conn, resultado["parametros"])
        card = resposta["cards"][0]
        self.assertEqual(card["data"]["valor_parcela"], 250.0)
        self.assertEqual(card["data"]["cartao"], "nubank")


class TestExecutarConsultas(_Base):
    def test_consultar_parcelas_vazio(self):
        resposta = regra.executar(self.conn, {"acao": "consultar_parcelas"})
        self.assertEqual(len(resposta["cards"]), 1)  # so o resumo
        self.assertIn("não tem nenhuma", resposta["resumo_texto"])

    def test_consultar_parcelas_com_dados(self):
        regra.executar(self.conn, {"acao": "criar_compra_parcelada", "descricao": "celular", "n_parcelas": 10, "valor_parcela": 300})
        resposta = regra.executar(self.conn, {"acao": "consultar_parcelas"})
        tipos = [c["type"] for c in resposta["cards"]]
        self.assertIn("resumo_financeiro_recorrente", tipos)
        self.assertIn("compra_parcelada", tipos)
        for c in resposta["cards"]:
            self.assertTrue(c["data"].get("consulta"))
            self.assertEqual(c["actions"], [])

    def test_consultar_assinaturas_vazio(self):
        resposta = regra.executar(self.conn, {"acao": "consultar_assinaturas"})
        self.assertIn("não tem nenhuma", resposta["resumo_texto"])

    def test_consultar_assinaturas_com_dados(self):
        regra.executar(self.conn, {"acao": "criar_assinatura", "nome": "Netflix", "valor": 55})
        resposta = regra.executar(self.conn, {"acao": "consultar_assinaturas"})
        tipos = [c["type"] for c in resposta["cards"]]
        self.assertIn("assinatura", tipos)

    def test_acao_desconhecida_nao_quebra(self):
        resposta = regra.executar(self.conn, {"acao": "voa_pra_lua"})
        self.assertEqual(resposta["cards"], [])


class TestIntegracaoComOClassificadorLocal(_Base):
    """Confere que o despachante generico (classificador_local/__init__.py,
    Etapa 0) acha e roda esta regra do jeito esperado - nao so a funcao
    isolada."""

    def test_casar_acha_a_regra(self):
        self.assertIn("n1_financas", classificador_local.nomes_regras())

    def test_fluxo_completo_via_despachante(self):
        resultado = classificador_local.casar("assinei Netflix 55 por mês")
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["regra"], "n1_financas")
        resposta = classificador_local.executar(self.conn, resultado)
        self.assertIsNotNone(resposta)
        self.assertEqual(len(resposta["cards"]), 1)
        self.assertEqual(resposta["cards"][0]["type"], "assinatura")

    def test_resultado_e_serializavel_em_json(self):
        """`/api/intent/classificar` (app.py) faz jsonify(resultado) sem
        alterar - parametros nunca pode ter Decimal."""
        import json

        resultado = classificador_local.casar("assinei Netflix 55,90 por mês")
        json.dumps(resultado)  # nao pode levantar TypeError

    def test_frase_de_outro_dominio_nao_casa_aqui(self):
        resultado = classificador_local.casar("tomei um copo de água")
        if resultado is not None:
            self.assertNotEqual(resultado["regra"], "n1_financas")


class TestFuzzClassificador(unittest.TestCase):
    """Regra de testes rigorosos: casar() nunca pode levantar excecao nem
    travar, seja com o que for jogado nele - 60+ entradas estranhas."""

    ENTRADAS = [
        "",
        " ",
        "\n\t",
        None,
        123,
        12.5,
        True,
        False,
        [],
        {},
        {"texto": "assinei"},
        "assinei",
        "assinei ",
        "assinei 55",
        "assinei Netflix",
        "assinei Netflix por mês",
        "assinei Netflix -55",
        "assinei Netflix 0",
        "assinei Netflix abc",
        "assinei Netflix 55,,90",
        "assinei Netflix R$",
        "assinei " + "x" * 5000,
        "assinei Netflix 55" * 200,
        "ASSINEI NETFLIX 55 POR MÊS",
        "AsSiNeI NetFlix 55 Por Mês",
        "assinei Netflix    55    por    mês",
        "assinei Netflix\t55\tpor mês",
        "assinei Nétflíx 55 por mês",
        "assinei 网飞 55 por mês",
        "assinei 😀 55 por mês",
        "assinei Netflix 55 por mês!!!",
        "assinei Netflix 55 por mês???",
        "assinei Netflix 55.90.90",
        "assinei Netflix 1.234.567,89",
        "assinei Netflix ,90",
        "assinei Netflix 90,",
        "comprei",
        "comprei celular",
        "comprei celular em",
        "comprei celular em x",
        "comprei celular em 0x de 300",
        "comprei celular em -5x de 300",
        "comprei celular em 999x de 300",
        "comprei celular em 10x de 0",
        "comprei celular em 10x de -300",
        "comprei celular em 10x de abc",
        "comprei   em 10x de 300",
        "comprei celular em 10 x de 300",
        "comprei celular em 10vezes de 300",
        "comprei celular 3000 em 10 vezes no " + "y" * 1000,
        "cancelei",
        "cancelei ",
        "cancelei a",
        "cancelei o",
        "cancelei a o",
        "quanto tenho de parcelas",
        "QUANTO TENHO DE PARCELAS???",
        "quanto tenho de parcela",
        "quantas parcela eu tenho",
        "quais assinatura eu tenho",
        "quais assinaturas eu tenho???",
        "'; DROP TABLE assinatura; --",
        "assinei Robert'); DROP TABLE assinatura;-- 55 por mês",
        "assinei <script>alert(1)</script> 55 por mês",
        "\x00\x01\x02",
        "assinei Netflix 55\x00 por mês",
        "assinei Netflix ٥٥ por mês",  # digitos arabicos
        "ASSINEI netflix 55 POR mes",
        "assineiNetflix55pormês",
        "cancelei a Netflix e o Spotify",
        "comprei celular em 10x de 300 no " + "banco " * 50,
        {"nao": "e string"},
        3.14159,
        b"assinei Netflix 55 por mes",
    ]

    def test_nunca_levanta_excecao(self):
        for entrada in self.ENTRADAS:
            with self.subTest(entrada=repr(entrada)[:80]):
                try:
                    resultado = regra.casar(entrada)
                except Exception as exc:  # nao deveria acontecer NUNCA
                    self.fail(f"casar({entrada!r}) levantou {exc!r}")
                self.assertTrue(resultado is None or isinstance(resultado, dict))
                if resultado is not None:
                    self.assertIn("acao", resultado)
                    self.assertIn("parametros", resultado)
                    self.assertIsInstance(resultado["parametros"], dict)

    def test_resultado_sempre_serializavel(self):
        import json

        for entrada in self.ENTRADAS:
            resultado = regra.casar(entrada)
            if resultado is not None:
                with self.subTest(entrada=repr(entrada)[:80]):
                    json.dumps(resultado)  # nunca Decimal/bytes/etc sobrando


if __name__ == "__main__":
    unittest.main()
