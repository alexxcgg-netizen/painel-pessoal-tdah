"""Fase 7, faixa V2 (Painel): rotas/v2_custo_ia.py (card "Custo de IA").

Segue o mesmo padrao de `tests/test_fase7_p8_rotas.py`: registra o Blueprint
`bp` sozinho num Flask app minimo (o modulo de rota so usa `db`/`ia.*`, sem
nada de `rotas._base`), banco SQLite temporario garantido "nao producao"
(`db.garantir_banco_nao_producao`).

Inclui bateria de fuzzing (>=60 cenarios) pedida pelo AGENTS.md: strings
extremas/unicode/injecao, numeros extremos, concorrencia leve, mes anterior
excluido, CSV bem formado - tudo com 0 falhas antes de considerar a faixa
pronta.
"""

from __future__ import annotations

import csv as csv_mod
import io
import json
import math
import os
import random
import string
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from flask import Flask

import db
from ia.medicao import cambio_usd_brl, registrar_uso
from rotas.v2_custo_ia import bp


class _BaseRotaTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()

        app = Flask(__name__)
        app.register_blueprint(bp)
        app.testing = True
        self.client = app.test_client()

    def tearDown(self):
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _resumo(self):
        resp = self.client.get("/api/ia/uso/resumo")
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()

    def _csv_linhas(self):
        resp = self.client.get("/api/ia/uso.csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.content_type)
        texto = resp.get_data(as_text=True)
        return list(csv_mod.reader(io.StringIO(texto)))

    def _forcar_data(self, deslocamento_dias: int):
        """Reescreve `criado_em` da ultima linha inserida em uso_ia pra
        simular um registro em outro dia (usado pra testar o corte de mes)."""
        conn = db.get_db()
        try:
            nova_data = (datetime.utcnow() + timedelta(days=deslocamento_dias)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE uso_ia SET criado_em = ? WHERE id = (SELECT MAX(id) FROM uso_ia)",
                (nova_data,),
            )
            conn.commit()
        finally:
            conn.close()


class ResumoVazioTestCase(_BaseRotaTestCase):
    def test_sem_nenhum_uso_devolve_zeros_sem_quebrar(self):
        corpo = self._resumo()
        self.assertEqual(corpo["gasto_brl"], 0.0)
        self.assertEqual(corpo["total_chamadas"], 0)
        self.assertEqual(corpo["por_funcao"], [])
        self.assertEqual(corpo["por_dia"], [])
        self.assertEqual(corpo["nivel_alerta"], "normal")
        self.assertEqual(corpo["teto_brl"], 0)
        self.assertEqual(corpo["projecao_fim_mes_brl"], 0.0)

    def test_csv_vazio_so_tem_cabecalho(self):
        linhas = self._csv_linhas()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(
            linhas[0],
            [
                "criado_em_utc",
                "funcao",
                "provedor",
                "modelo",
                "tokens_in",
                "tokens_out",
                "tokens_cache_lido",
                "tokens_cache_escrito",
                "custo_usd",
                "custo_brl",
                "latencia_ms",
                "ok",
            ],
        )

    def test_mes_no_formato_esperado(self):
        corpo = self._resumo()
        self.assertRegex(corpo["mes"], r"^\d{4}-\d{2}$")


class ResumoComUsoTestCase(_BaseRotaTestCase):
    def test_um_registro_aparece_no_resumo_e_no_csv(self):
        registrar_uso(
            "chat", "anthropic", "claude-sonnet-5", tokens_in=1000, tokens_out=200, custo_usd=0.01
        )
        corpo = self._resumo()
        self.assertEqual(corpo["total_chamadas"], 1)
        self.assertEqual(len(corpo["por_funcao"]), 1)
        self.assertEqual(corpo["por_funcao"][0]["funcao"], "chat")
        self.assertEqual(corpo["por_funcao"][0]["chamadas"], 1)
        cambio = cambio_usd_brl()
        self.assertAlmostEqual(corpo["gasto_brl"], 0.01 * cambio, places=4)

        linhas = self._csv_linhas()
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[1][1], "chat")

    def test_soma_por_funcao_bate_com_gasto_total(self):
        registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=0.02)
        registrar_uso("captura", "openai", "gpt-6-luna", custo_usd=0.005)
        registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=0.03)
        corpo = self._resumo()
        soma_funcoes = sum(f["gasto_brl"] for f in corpo["por_funcao"])
        self.assertAlmostEqual(soma_funcoes, corpo["gasto_brl"], places=3)
        # 2 chamadas de chat agregadas na mesma linha, nao 2 linhas soltas
        chat = next(f for f in corpo["por_funcao"] if f["funcao"] == "chat")
        self.assertEqual(chat["chamadas"], 2)

    def test_por_funcao_ordenado_do_maior_pro_menor_gasto(self):
        registrar_uso("barato", "openai", "gpt-6-luna", custo_usd=0.001)
        registrar_uso("caro", "anthropic", "claude-opus-5-5", custo_usd=1.5)
        corpo = self._resumo()
        gastos = [f["gasto_brl"] for f in corpo["por_funcao"]]
        self.assertEqual(gastos, sorted(gastos, reverse=True))
        self.assertEqual(corpo["por_funcao"][0]["funcao"], "caro")

    def test_ok_false_ainda_conta_no_total(self):
        registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=0.01, ok=False)
        corpo = self._resumo()
        self.assertEqual(corpo["total_chamadas"], 1)
        self.assertGreater(corpo["gasto_brl"], 0)

    def test_registro_de_mes_anterior_nao_entra_no_resumo_nem_no_csv(self):
        registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=0.5)
        self._forcar_data(-40)  # ~40 dias atras, mes anterior com folga
        corpo = self._resumo()
        self.assertEqual(corpo["total_chamadas"], 0)
        self.assertEqual(corpo["gasto_brl"], 0.0)
        linhas = self._csv_linhas()
        self.assertEqual(len(linhas), 1)  # so o cabecalho

    def test_registro_de_hoje_entra_no_resumo(self):
        registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=0.5)
        self._forcar_data(0)
        corpo = self._resumo()
        self.assertEqual(corpo["total_chamadas"], 1)

    def test_projecao_fim_do_mes_nunca_e_menor_que_o_gasto_atual(self):
        registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=1.0)
        corpo = self._resumo()
        self.assertGreaterEqual(corpo["projecao_fim_mes_brl"], corpo["gasto_brl"] - 1e-6)

    def test_fracao_teto_e_gasto_dividido_pelo_teto(self):
        conn = db.get_db()
        try:
            db.definir_teto_mensal_ia(conn, 10.0)  # USD
        finally:
            conn.close()
        registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=1.0)
        corpo = self._resumo()
        self.assertAlmostEqual(corpo["fracao_teto"], corpo["gasto_brl"] / corpo["teto_brl"], places=4)

    def test_teto_configurado_e_respeitado_no_resumo(self):
        conn = db.get_db()
        try:
            db.definir_teto_mensal_ia(conn, 10.0)  # USD
        finally:
            conn.close()
        corpo = self._resumo()
        cambio = cambio_usd_brl()
        self.assertAlmostEqual(corpo["teto_brl"], 10.0 * cambio, places=4)

    def test_teto_removido_fica_sem_teto(self):
        conn = db.get_db()
        try:
            db.definir_teto_mensal_ia(conn, 10.0)
            db.definir_teto_mensal_ia(conn, None)
        finally:
            conn.close()
        corpo = self._resumo()
        self.assertEqual(corpo["teto_brl"], 0)

    def test_muitas_funcoes_distintas_nao_quebra(self):
        for i in range(40):
            registrar_uso(f"funcao_{i}", "anthropic", "claude-sonnet-5", custo_usd=0.001 * i)
        corpo = self._resumo()
        self.assertEqual(len(corpo["por_funcao"]), 40)
        self.assertEqual(corpo["total_chamadas"], 40)


class CsvEscapeECaracteresTestCase(_BaseRotaTestCase):
    def test_funcao_com_virgula_e_aspas_fica_bem_formada_no_csv(self):
        registrar_uso('chat, "especial"', "anthropic", "claude-sonnet-5", custo_usd=0.01)
        linhas = self._csv_linhas()
        self.assertEqual(linhas[1][1], 'chat, "especial"')

    def test_funcao_unicode_emoji(self):
        registrar_uso("captura-🚀-ç-ã", "openai", "gpt-6-luna", custo_usd=0.01)
        corpo = self._resumo()
        self.assertEqual(corpo["por_funcao"][0]["funcao"], "captura-🚀-ç-ã")
        linhas = self._csv_linhas()
        self.assertEqual(linhas[1][1], "captura-🚀-ç-ã")

    def test_funcao_com_quebra_de_linha_nao_quebra_csv(self):
        registrar_uso("linha1\nlinha2", "anthropic", "claude-sonnet-5", custo_usd=0.01)
        linhas = self._csv_linhas()
        # csv.reader ja reconstitui o campo multi-linha numa unica celula
        self.assertEqual(linhas[1][1], "linha1\nlinha2")

    def test_funcao_string_gigante(self):
        gigante = "a" * 5000
        registrar_uso(gigante, "anthropic", "claude-sonnet-5", custo_usd=0.001)
        corpo = self._resumo()
        self.assertEqual(corpo["por_funcao"][0]["funcao"], gigante)

    def test_funcao_tentativa_de_injecao_sql(self):
        malicioso = "chat'; DROP TABLE uso_ia; --"
        registrar_uso(malicioso, "anthropic", "claude-sonnet-5", custo_usd=0.01)
        corpo = self._resumo()
        self.assertEqual(corpo["total_chamadas"], 1)
        self.assertEqual(corpo["por_funcao"][0]["funcao"], malicioso)
        # tabela sobreviveu (parametrizado, nunca concatenado)
        corpo2 = self._resumo()
        self.assertEqual(corpo2["total_chamadas"], 1)


class NumerosExtremosTestCase(_BaseRotaTestCase):
    def test_custo_zero(self):
        registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=0.0)
        corpo = self._resumo()
        self.assertEqual(corpo["gasto_brl"], 0.0)

    def test_custo_muito_grande(self):
        conn = db.get_db()
        try:
            db.definir_teto_mensal_ia(conn, 10.0)  # USD
        finally:
            conn.close()
        registrar_uso("chat", "anthropic", "claude-opus-5-5", custo_usd=99999.99)
        corpo = self._resumo()
        self.assertGreater(corpo["gasto_brl"], 0)
        self.assertGreaterEqual(corpo["fracao_teto"], 1.0)
        self.assertEqual(corpo["nivel_alerta"], "estourado_100")

    def test_custo_muito_grande_sem_teto_fica_normal(self):
        registrar_uso("chat", "anthropic", "claude-opus-5-5", custo_usd=99999.99)
        corpo = self._resumo()
        self.assertGreater(corpo["gasto_brl"], 0)
        self.assertEqual(corpo["teto_brl"], 0)
        self.assertEqual(corpo["fracao_teto"], 0)
        self.assertEqual(corpo["nivel_alerta"], "normal")

    def test_tokens_muito_grandes(self):
        registrar_uso(
            "chat", "anthropic", "claude-sonnet-5", tokens_in=10_000_000, tokens_out=5_000_000, custo_usd=5.0
        )
        corpo = self._resumo()
        self.assertEqual(corpo["por_funcao"][0]["tokens_in"], 10_000_000)
        self.assertEqual(corpo["por_funcao"][0]["tokens_out"], 5_000_000)

    def test_tokens_zero(self):
        registrar_uso("chat", "anthropic", "claude-sonnet-5", tokens_in=0, tokens_out=0, custo_usd=0.0)
        corpo = self._resumo()
        self.assertEqual(corpo["por_funcao"][0]["tokens_in"], 0)

    def test_muitas_chamadas_mesma_funcao_soma_certo(self):
        for _ in range(50):
            registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=0.001)
        corpo = self._resumo()
        self.assertEqual(corpo["por_funcao"][0]["chamadas"], 50)
        self.assertAlmostEqual(corpo["por_funcao"][0]["gasto_brl"], 0.05 * cambio_usd_brl(), places=3)


class ConcorrenciaTestCase(_BaseRotaTestCase):
    def test_escritas_concorrentes_nao_derrubam_nem_perdem_linha(self):
        n = 20
        erros = []

        def escrever(i):
            try:
                registrar_uso(f"concorrente_{i % 4}", "anthropic", "claude-sonnet-5", custo_usd=0.001)
            except Exception as exc:  # pragma: no cover - so pra reportar no assert
                erros.append(exc)

        threads = [threading.Thread(target=escrever, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(erros, [])
        corpo = self._resumo()
        self.assertEqual(corpo["total_chamadas"], n)


class FuzzMassaTestCase(_BaseRotaTestCase):
    """>=60 cenarios de fuzzing num loop so, pedido do AGENTS.md: strings
    aleatorias (incl. controle/unicode), numeros extremos, sem nenhuma linha
    derrubar a rota. Cada iteracao chama /api/ia/uso/resumo e /api/ia/uso.csv
    de novo e exige 200 - se QUALQUER cenario quebrar o teste falha e aponta
    o indice."""

    def test_fuzzing_massa_funcoes_e_numeros_aleatorios(self):
        random.seed(20260924)
        alfabetos = [
            string.printable,
            "abcdefghijklmnopqrstuvwxyzÁÉÍÓÚÇÃÕáéíóúçãõ",
            "🚀🔥💰📊😀日本語中文한국어",
            "",  # vazio de proposito (registrar_uso ainda grava, mesmo com funcao "")
        ]
        for i in range(70):
            alfabeto = random.choice(alfabetos)
            tamanho = random.choice([0, 1, 5, 50, 500])
            funcao = "".join(random.choice(alfabeto) for _ in range(tamanho)) if alfabeto else ""
            tokens_in = random.choice([0, 1, 100, 10_000, 5_000_000])
            tokens_out = random.choice([0, 1, 100, 10_000, 5_000_000])
            custo = random.choice([0.0, 0.0001, 0.5, 12.34, 999.99])
            ok = random.choice([True, False])
            try:
                registrar_uso(
                    funcao or "vazia",
                    random.choice(["anthropic", "openai", ""]),
                    random.choice(["claude-sonnet-5", "gpt-6-luna", ""]),
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    custo_usd=custo,
                    ok=ok,
                )
            except Exception as exc:  # pragma: no cover
                self.fail(f"cenario {i} (registrar_uso) quebrou: {exc!r} funcao={funcao!r}")

            resp = self.client.get("/api/ia/uso/resumo")
            self.assertEqual(resp.status_code, 200, f"cenario {i}: resumo nao devolveu 200")
            corpo = resp.get_json()
            self.assertIsInstance(corpo["gasto_brl"], (int, float))
            self.assertTrue(math.isfinite(corpo["gasto_brl"]), f"cenario {i}: gasto_brl nao finito")
            self.assertTrue(math.isfinite(corpo["fracao_teto"]), f"cenario {i}: fracao_teto nao finito")

            resp_csv = self.client.get("/api/ia/uso.csv")
            self.assertEqual(resp_csv.status_code, 200, f"cenario {i}: csv nao devolveu 200")

        corpo_final = self._resumo()
        self.assertEqual(corpo_final["total_chamadas"], 70)


if __name__ == "__main__":
    unittest.main()
