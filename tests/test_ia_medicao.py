import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
import ia.medicao as medicao


class RegistrarUsoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _linhas_uso_ia(self):
        conn = db.get_db()
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM uso_ia ORDER BY id").fetchall()]
        finally:
            conn.close()

    def test_grava_uma_linha_com_todos_os_campos(self):
        medicao.registrar_uso(
            "chat",
            "anthropic",
            "claude-sonnet-5",
            tokens_in=100,
            tokens_out=50,
            tokens_cache_lido=10,
            tokens_cache_escrito=5,
            custo_usd=0.0123,
            latencia_ms=987,
            ok=True,
        )
        linhas = self._linhas_uso_ia()
        self.assertEqual(len(linhas), 1)
        linha = linhas[0]
        self.assertEqual(linha["funcao"], "chat")
        self.assertEqual(linha["provedor"], "anthropic")
        self.assertEqual(linha["modelo"], "claude-sonnet-5")
        self.assertEqual(linha["tokens_in"], 100)
        self.assertEqual(linha["tokens_out"], 50)
        self.assertEqual(linha["tokens_cache_lido"], 10)
        self.assertEqual(linha["tokens_cache_escrito"], 5)
        self.assertAlmostEqual(linha["custo_usd"], 0.0123)
        self.assertEqual(linha["latencia_ms"], 987)
        self.assertEqual(linha["ok"], 1)
        self.assertIsNotNone(linha["criado_em"])

    def test_valores_padrao_quando_so_funcao_provedor_modelo_sao_passados(self):
        medicao.registrar_uso("intent", "openai", "gpt-6-luna")
        linha = self._linhas_uso_ia()[0]
        self.assertEqual(linha["tokens_in"], 0)
        self.assertEqual(linha["tokens_out"], 0)
        self.assertEqual(linha["tokens_cache_lido"], 0)
        self.assertEqual(linha["tokens_cache_escrito"], 0)
        self.assertEqual(linha["custo_usd"], 0.0)
        self.assertEqual(linha["latencia_ms"], 0)
        self.assertEqual(linha["ok"], 1)

    def test_ok_false_grava_zero(self):
        medicao.registrar_uso("chat", "anthropic", "claude-sonnet-5", ok=False)
        linha = self._linhas_uso_ia()[0]
        self.assertEqual(linha["ok"], 0)

    def test_nao_grava_nenhum_conteudo_de_prompt(self):
        """Contrato explicito da tarefa: uso_ia nunca guarda texto de prompt/
        resposta - so as colunas de metadados existem."""
        medicao.registrar_uso("chat", "anthropic", "claude-sonnet-5", tokens_in=1, tokens_out=1)
        conn = db.get_db()
        try:
            colunas = {r["name"] for r in conn.execute("PRAGMA table_info(uso_ia)").fetchall()}
        finally:
            conn.close()
        esperadas = {
            "id", "criado_em", "funcao", "provedor", "modelo", "tokens_in", "tokens_out",
            "tokens_cache_lido", "tokens_cache_escrito", "custo_usd", "latencia_ms", "ok",
        }
        self.assertEqual(colunas, esperadas)

    def test_varias_chamadas_acumulam_linhas_distintas(self):
        for i in range(5):
            medicao.registrar_uso("intent", "openai", "gpt-6-luna", custo_usd=0.001)
        self.assertEqual(len(self._linhas_uso_ia()), 5)

    def test_tabela_e_criada_sozinha_sem_precisar_de_init_db_saber_dela(self):
        """garantir_tabela e chamada lazy por registrar_uso - simulando um
        banco onde a tabela uso_ia nunca foi criada (banco velho, antes desta
        faixa existir), a primeira chamada de registrar_uso ainda funciona."""
        conn = db.get_db()
        conn.execute("DROP TABLE IF EXISTS uso_ia")
        conn.commit()
        conn.close()
        medicao.registrar_uso("chat", "anthropic", "claude-sonnet-5")
        self.assertEqual(len(self._linhas_uso_ia()), 1)


class GastoMesAtualTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _inserir_uso_em(self, quando_utc: datetime, custo_usd: float):
        conn = db.get_db()
        try:
            from ia.migracao_uso_ia import garantir_tabela

            garantir_tabela(conn)
            conn.execute(
                "INSERT INTO uso_ia (criado_em, funcao, provedor, modelo, custo_usd) "
                "VALUES (?, 'chat', 'anthropic', 'claude-sonnet-5', ?)",
                (quando_utc.strftime("%Y-%m-%d %H:%M:%S"), custo_usd),
            )
            conn.commit()
        finally:
            conn.close()

    def test_sem_nenhum_uso_e_zero(self):
        self.assertEqual(medicao.gasto_mes_atual(), 0.0)

    def test_soma_so_o_que_esta_dentro_do_mes_atual(self):
        agora_utc = datetime.now(timezone.utc)
        inicio_mes_local = datetime.now().astimezone().replace(
            hour=12, minute=0, second=0, microsecond=0, day=1
        )
        antes_do_mes = (inicio_mes_local - timedelta(days=5)).astimezone(timezone.utc)

        self._inserir_uso_em(agora_utc, 1.5)
        self._inserir_uso_em(agora_utc, 2.5)
        self._inserir_uso_em(antes_do_mes, 100.0)  # mes anterior - nao deve entrar na soma

        self.assertAlmostEqual(medicao.gasto_mes_atual(), 4.0, places=6)

    def test_gasto_mes_atual_brl_usa_cambio_do_precos_json(self):
        agora_utc = datetime.now(timezone.utc)
        self._inserir_uso_em(agora_utc, 10.0)
        cambio = medicao.cambio_usd_brl()
        self.assertAlmostEqual(medicao.gasto_mes_atual_brl(), 10.0 * cambio, places=6)

    def test_registrar_uso_conta_pro_gasto_do_mes(self):
        medicao.registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=3.3)
        medicao.registrar_uso("intent", "openai", "gpt-6-luna", custo_usd=0.7)
        self.assertAlmostEqual(medicao.gasto_mes_atual(), 4.0, places=6)


class CambioUsdBrlTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_precos = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        self._caminho_original = medicao.CAMINHO_PRECOS

    def tearDown(self):
        medicao.CAMINHO_PRECOS = self._caminho_original
        self._tmp_precos.close()
        try:
            os.unlink(self._tmp_precos.name)
        except OSError:
            pass

    def _usar_precos(self, conteudo):
        if isinstance(conteudo, str):
            self._tmp_precos.write(conteudo)
        else:
            json.dump(conteudo, self._tmp_precos)
        self._tmp_precos.close()
        medicao.CAMINHO_PRECOS = Path(self._tmp_precos.name)

    def test_le_cambio_configurado(self):
        self._usar_precos({"cambio_usd_brl": 5.5})
        self.assertEqual(medicao.cambio_usd_brl(), 5.5)

    def test_arquivo_inexistente_cai_pro_padrao(self):
        medicao.CAMINHO_PRECOS = Path(self._tmp_precos.name).parent / "nao-existe-de-verdade.json"
        self.assertEqual(medicao.cambio_usd_brl(), medicao.CAMBIO_USD_BRL_PADRAO)

    def test_json_malformado_cai_pro_padrao(self):
        self._usar_precos("{ isso nao e json valido")
        self.assertEqual(medicao.cambio_usd_brl(), medicao.CAMBIO_USD_BRL_PADRAO)

    def test_cambio_zero_ou_negativo_cai_pro_padrao(self):
        self._usar_precos({"cambio_usd_brl": -1})
        self.assertEqual(medicao.cambio_usd_brl(), medicao.CAMBIO_USD_BRL_PADRAO)

    def test_cambio_nao_numerico_cai_pro_padrao(self):
        self._usar_precos({"cambio_usd_brl": "cinco e meio"})
        self.assertEqual(medicao.cambio_usd_brl(), medicao.CAMBIO_USD_BRL_PADRAO)

    def test_chave_ausente_cai_pro_padrao(self):
        self._usar_precos({"modelos": {}})
        self.assertEqual(medicao.cambio_usd_brl(), medicao.CAMBIO_USD_BRL_PADRAO)


if __name__ == "__main__":
    unittest.main()
