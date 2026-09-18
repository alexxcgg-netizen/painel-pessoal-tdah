import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)


def fake_usage(model="claude-haiku-4-5-20251001", cost=0.001):
    return {"model": model, "input_tokens": 100, "output_tokens": 20, "cost_usd": cost}


OFX_AMOSTRA = """
OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20250115120000[-3:BRT]
<TRNAMT>-45.90
<FITID>202501150001
<MEMO>PADARIA CENTRAL
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20250116080000[-3:BRT]
<TRNAMT>1500.00
<FITID>202501160002
<MEMO>SALARIO
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


class PainelTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.client = app.app.test_client()

    def test_captura_gasto_direto(self):
        parsed = {
            "tipo": "gasto",
            "titulo": "mercado",
            "valor": 50.0,
            "categoria": "mercado",
            "quando": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "gastei 50 no mercado"})
        self.assertEqual(res.status_code, 201)

        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0]["amount"], 50.0)

    def test_captura_ambigua_pede_esclarecimento_e_depois_grava(self):
        duvida_resp = {
            "tipo": "gasto",
            "titulo": "?",
            "valor": None,
            "categoria": None,
            "quando": None,
            "duvida": "Isso foi um gasto ou uma tarefa?",
        }
        ok_resp = {
            "tipo": "tarefa",
            "titulo": "ligar pro banco",
            "valor": None,
            "categoria": None,
            "quando": "amanha",
            "duvida": None,
        }
        with patch(
            "claude_client.classify_capture",
            side_effect=[(duvida_resp, fake_usage()), (ok_resp, fake_usage())],
        ):
            r1 = self.client.post("/api/capture", json={"text": "banco"})
            self.assertEqual(r1.status_code, 200)
            body1 = r1.get_json()
            self.assertIn("duvida", body1)
            self.assertNotIn("id", body1)

            r2 = self.client.post(
                "/api/capture",
                json={"text": "banco", "clarificacao": "e uma tarefa, preciso ligar amanha"},
            )
            self.assertEqual(r2.status_code, 201)

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "ligar pro banco")

    def test_completar_tarefa_some_da_lista_de_pendentes(self):
        parsed = {
            "tipo": "tarefa",
            "titulo": "pagar boleto",
            "valor": None,
            "categoria": None,
            "quando": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "pagar boleto"})

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 1)
        task_id = tasks[0]["id"]

        res = self.client.post(f"/api/tasks/{task_id}/complete")
        self.assertEqual(res.status_code, 200)

        tasks_depois = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks_depois), 0)

    def test_quebra_de_tarefa_grande_cria_subtarefas(self):
        parsed = {
            "tipo": "tarefa",
            "titulo": "organizar o quarto",
            "valor": None,
            "categoria": None,
            "quando": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "organizar o quarto"})

        task_id = self.client.get("/api/tasks").get_json()[0]["id"]
        passos = ["separar roupa suja", "guardar roupa limpa", "passar pano no chao"]
        with patch(
            "claude_client.break_down_task",
            return_value=(passos, fake_usage(model="claude-sonnet-5", cost=0.01)),
        ):
            res = self.client.post(f"/api/tasks/{task_id}/breakdown")
        self.assertEqual(res.status_code, 200)
        titulos = [s["title"] for s in res.get_json()["subtasks"]]
        self.assertEqual(titulos, passos)

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks[0]["subtasks"]), 3)
        self.assertFalse(tasks[0]["subtasks"][0]["completed_at"])

        subtask_id = tasks[0]["subtasks"][0]["id"]
        res = self.client.post(f"/api/subtasks/{subtask_id}/complete")
        self.assertEqual(res.status_code, 200)
        tasks = self.client.get("/api/tasks").get_json()
        self.assertTrue(tasks[0]["subtasks"][0]["completed_at"])

    def test_resumo_do_dia_e_custo_acumulado(self):
        with patch(
            "claude_client.summarize_day",
            return_value=("Hoje voce concluiu 1 tarefa e gastou R$ 0.", fake_usage(cost=0.002)),
        ):
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        self.assertIn("summary", res.get_json())

        uso = self.client.get("/api/uso/total").get_json()
        self.assertAlmostEqual(uso["custo_usd"], 0.002)

    def test_custo_acumula_entre_chamadas(self):
        parsed = {
            "tipo": "gasto",
            "titulo": "uber",
            "valor": 20.0,
            "categoria": "transporte",
            "quando": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage(cost=0.001))):
            self.client.post("/api/capture", json={"text": "uber 20"})
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage(cost=0.003))):
            self.client.post("/api/capture", json={"text": "uber 20"})

        uso = self.client.get("/api/uso/total").get_json()
        self.assertAlmostEqual(uso["custo_usd"], 0.004)

    def test_construtora_sem_configuracao_retorna_flag_falsa(self):
        res = self.client.get("/api/construtora/resumo")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"configurado": False})

    def test_importar_extrato_ofx_cria_conta_e_transacoes(self):
        res = self.client.post(
            "/api/bancos/importar",
            data={
                "banco": "nubank",
                "arquivo": (io.BytesIO(OFX_AMOSTRA.encode()), "extrato.ofx"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["encontradas"], 2)
        self.assertEqual(body["novas"], 2)
        self.assertEqual(body["duplicadas"], 0)

        contas = self.client.get("/api/bancos").get_json()
        self.assertEqual(len(contas), 1)
        self.assertEqual(contas[0]["banco"], "nubank")
        self.assertEqual(contas[0]["total_transacoes"], 2)

        transacoes = self.client.get(f"/api/bancos/{contas[0]['id']}/transacoes").get_json()
        self.assertEqual(len(transacoes), 2)
        valores = sorted(t["valor"] for t in transacoes)
        self.assertEqual(valores, [-45.9, 1500.0])

    def test_reimportar_mesmo_extrato_nao_duplica(self):
        self.client.post(
            "/api/bancos/importar",
            data={"banco": "viacredi", "arquivo": (io.BytesIO(OFX_AMOSTRA.encode()), "e.ofx")},
            content_type="multipart/form-data",
        )
        res = self.client.post(
            "/api/bancos/importar",
            data={"banco": "viacredi", "arquivo": (io.BytesIO(OFX_AMOSTRA.encode()), "e.ofx")},
            content_type="multipart/form-data",
        )
        body = res.get_json()
        self.assertEqual(body["novas"], 0)
        self.assertEqual(body["duplicadas"], 2)

        contas = self.client.get("/api/bancos").get_json()
        self.assertEqual(contas[0]["total_transacoes"], 2)

    def test_importar_sem_arquivo_da_erro(self):
        res = self.client.post(
            "/api/bancos/importar", data={"banco": "nubank"}, content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 400)

    def test_bancos_sync_status_sem_configuracao(self):
        res = self.client.get("/api/bancos/sync-status")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["sincronizacao_automatica"])

    def test_importar_com_tipo_cartao_fica_separado_da_conta(self):
        self.client.post(
            "/api/bancos/importar",
            data={
                "banco": "nubank",
                "tipo": "conta",
                "arquivo": (io.BytesIO(OFX_AMOSTRA.encode()), "e.ofx"),
            },
            content_type="multipart/form-data",
        )
        self.client.post(
            "/api/bancos/importar",
            data={
                "banco": "nubank",
                "tipo": "cartao",
                "arquivo": (io.BytesIO(OFX_AMOSTRA.encode()), "e.ofx"),
            },
            content_type="multipart/form-data",
        )
        contas = self.client.get("/api/bancos").get_json()
        self.assertEqual(len(contas), 2)
        tipos = sorted(c["tipo"] for c in contas)
        self.assertEqual(tipos, ["cartao", "conta"])

    def test_captura_meta_calcula_guardar_por_mes(self):
        from datetime import date

        hoje = date.today()
        total_meses = hoje.month - 1 + 3
        ano = hoje.year + total_meses // 12
        mes = total_meses % 12 + 1
        prazo_iso = date(ano, mes, min(hoje.day, 28)).isoformat()

        parsed = {
            "tipo": "meta",
            "titulo": "moto",
            "valor": 1200.0,
            "categoria": None,
            "quando": None,
            "prazo": prazo_iso,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post(
                "/api/capture", json={"text": "quero juntar 1200 pra uma moto em 3 meses"}
            )
        self.assertEqual(res.status_code, 201)

        metas = self.client.get("/api/metas").get_json()
        self.assertEqual(len(metas), 1)
        meta = metas[0]
        self.assertEqual(meta["titulo"], "moto")
        self.assertEqual(meta["valor_alvo"], 1200.0)
        # entre 2 e 3 meses dependendo de como o dia do mes cai - o que importa
        # e a formula bater: por_mes * meses_restantes ~= valor_alvo
        self.assertIn(meta["meses_restantes"], (2, 3))
        self.assertAlmostEqual(meta["por_mes"] * meta["meses_restantes"], meta["valor_alvo"], delta=1.0)

    def test_guardar_em_meta_atualiza_progresso(self):
        parsed = {
            "tipo": "meta",
            "titulo": "viagem",
            "valor": 1000.0,
            "categoria": None,
            "quando": None,
            "prazo": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "quero juntar 1000 pra viagem"})

        goal_id = self.client.get("/api/metas").get_json()[0]["id"]
        res = self.client.post(f"/api/metas/{goal_id}/guardar", json={"valor": 250})
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["valor_guardado"], 250)
        self.assertEqual(body["falta"], 750)
        self.assertIsNone(body["por_mes"])  # sem prazo, nao da pra calcular por mes

    def test_guardar_em_meta_invalida_rejeita_valor_nao_positivo(self):
        res = self.client.post("/api/metas/999/guardar", json={"valor": -5})
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
