import io
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import claude_client
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)


def fake_usage(model="claude-haiku-4-5-20251001", cost=0.001):
    return {"model": model, "input_tokens": 100, "output_tokens": 20, "cost_usd": cost}


def _resp(content, stop_reason="end_turn", model=claude_client.SONNET, in_tok=100, out_tok=20):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


def _text_block(texto):
    return SimpleNamespace(type="text", text=texto)


def _tool_block(nome, entrada, id_):
    return SimpleNamespace(type="tool_use", name=nome, input=entrada, id=id_)


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


PIN_TESTE = "123456"


class PainelTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        # a memoria do perfil inicial (nome, idade, profissao) e semeada em todo
        # banco novo - limpa aqui pra os testes de memoria ficarem isolados/previsiveis
        conn = db.get_db()
        conn.execute("DELETE FROM memorias")
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        # loga de verdade pelo fluxo real - assim toda a suite ja exercita o
        # gate de autenticacao (before_request) em vez de contornar ele
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

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

    def test_conectar_token_sem_configuracao_da_erro(self):
        res = self.client.post("/api/bancos/conectar/token")
        self.assertEqual(res.status_code, 400)

    def test_conectar_finalizar_sem_configuracao_da_erro(self):
        res = self.client.post("/api/bancos/conectar/finalizar", json={"item_id": "abc"})
        self.assertEqual(res.status_code, 400)

    def test_conectar_finalizar_sem_item_id_da_erro(self):
        with patch("pluggy_client.configurado", return_value=True):
            res = self.client.post("/api/bancos/conectar/finalizar", json={})
        self.assertEqual(res.status_code, 400)

    def test_conectar_token_configurado_retorna_token(self):
        with patch("pluggy_client.configurado", return_value=True), patch(
            "pluggy_client.create_connect_token", return_value="token-fake"
        ):
            res = self.client.post("/api/bancos/conectar/token")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["connect_token"], "token-fake")

    def test_conectar_finalizar_grava_contas_e_transacoes(self):
        item_fake = {"connector": {"name": "Nubank"}}
        contas_fake = [
            {"id": "conta-1", "type": "BANK"},
            {"id": "conta-2", "type": "CREDIT"},
        ]
        transacoes_fake = [
            {"id": "txn-1", "date": "2026-09-01T00:00:00.000Z", "amount": -50.0, "description": "mercado"}
        ]
        with patch("pluggy_client.configurado", return_value=True), patch(
            "pluggy_client.get_item", return_value=item_fake
        ), patch("pluggy_client.get_accounts", return_value=contas_fake), patch(
            "pluggy_client.get_transactions", return_value=transacoes_fake
        ):
            res = self.client.post("/api/bancos/conectar/finalizar", json={"item_id": "item-1"})

        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["banco"], "nubank")
        self.assertEqual(len(body["contas"]), 2)

        contas = self.client.get("/api/bancos").get_json()
        self.assertEqual(len(contas), 2)
        tipos = sorted(c["tipo"] for c in contas)
        self.assertEqual(tipos, ["cartao", "conta"])
        self.assertEqual(sum(c["total_transacoes"] for c in contas), 2)

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

    def test_guardar_em_meta_inexistente_com_valor_valido_da_404(self):
        res = self.client.post("/api/metas/999/guardar", json={"valor": 100})
        self.assertEqual(res.status_code, 404)

    def test_meta_historico_inexistente_da_404(self):
        res = self.client.get("/api/metas/999/historico")
        self.assertEqual(res.status_code, 404)

    def test_meta_historico_acumula_depositos_em_ordem(self):
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO goals (titulo, valor_alvo) VALUES (?, ?)", ("Moto", 5000)
        )
        gid = cur.lastrowid
        conn.commit()
        conn.close()

        self.client.post(f"/api/metas/{gid}/guardar", json={"valor": 200})
        self.client.post(f"/api/metas/{gid}/guardar", json={"valor": 300})

        res = self.client.get(f"/api/metas/{gid}/historico")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["valor_alvo"], 5000)
        acumulados = [p["acumulado"] for p in body["pontos"]]
        self.assertEqual(acumulados, [0.0, 200.0, 500.0])

    def test_expenses_historico_zero_preenchido(self):
        res = self.client.get("/api/expenses/historico?dias=5")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(len(body), 5)
        self.assertEqual(sum(d["total"] for d in body), 0)

    def test_expenses_historico_inclui_gasto_de_hoje(self):
        parsed = {
            "tipo": "gasto",
            "titulo": "mercado",
            "valor": 42.0,
            "categoria": "mercado",
            "quando": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "gastei 42 no mercado"})

        res = self.client.get("/api/expenses/historico?dias=7")
        body = res.get_json()
        self.assertEqual(body[-1]["data"], date.today().isoformat())
        self.assertEqual(body[-1]["total"], 42.0)

    def test_expenses_historico_limita_dias_no_intervalo_valido(self):
        res = self.client.get("/api/expenses/historico?dias=9999")
        self.assertEqual(len(res.get_json()), 90)
        res2 = self.client.get("/api/expenses/historico?dias=0")
        self.assertEqual(len(res2.get_json()), 1)

    def test_voos_historico_vazio_sem_voos(self):
        res = self.client.get("/api/voos/historico")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), [])

    def test_voos_historico_acumula_voos_realizados(self):
        self.client.post(
            "/api/voos",
            json={"data": "2026-01-10", "destino": "Blumenau", "horas": 1.5},
        )
        self.client.post(
            "/api/voos",
            json={"data": "2026-01-05", "destino": "Navegantes", "horas": 2.0},
        )
        res = self.client.get("/api/voos/historico")
        body = res.get_json()
        self.assertEqual([p["data"] for p in body], ["2026-01-05", "2026-01-10"])
        self.assertEqual([p["acumulado"] for p in body], [2.0, 3.5])

    def test_push_status_sem_configuracao(self):
        res = self.client.get("/api/push/status")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["configurado"])

    def test_push_inscrever_sem_endpoint_da_erro(self):
        res = self.client.post("/api/push/inscrever", json={})
        self.assertEqual(res.status_code, 400)

    def test_push_testar_sem_configuracao_da_erro(self):
        res = self.client.post("/api/push/testar")
        self.assertEqual(res.status_code, 400)

    def test_push_inscrever_e_testar_envia_para_inscritos(self):
        sub = {"endpoint": "https://exemplo.com/push/abc", "keys": {"p256dh": "x", "auth": "y"}}
        res = self.client.post("/api/push/inscrever", json=sub)
        self.assertEqual(res.status_code, 200)

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            res = self.client.post("/api/push/testar")

        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["enviados"], 1)
        self.assertEqual(body["total"], 1)
        mock_enviar.assert_called_once()

    def test_push_testar_remove_inscricao_morta(self):
        sub = {"endpoint": "https://exemplo.com/push/morta", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=False
        ):
            res = self.client.post("/api/push/testar")
        self.assertEqual(res.get_json()["enviados"], 0)

        # a segunda tentativa nao deve mais achar essa inscricao (foi apagada)
        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ):
            res2 = self.client.post("/api/push/testar")
        self.assertEqual(res2.get_json()["total"], 0)

    def test_calendario_hoje_sem_configuracao(self):
        res = self.client.get("/api/calendario/hoje")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertFalse(body["configurado"])
        self.assertEqual(body["eventos"], [])

    def test_calendario_hoje_configurado_retorna_eventos(self):
        eventos_fake = [
            {"titulo": "Reuniao", "inicio": "2026-09-18T14:00:00", "fim": "2026-09-18T15:00:00", "dia_inteiro": False}
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ):
            res = self.client.get("/api/calendario/hoje")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["configurado"])
        self.assertEqual(len(body["eventos"]), 1)
        self.assertEqual(body["eventos"][0]["titulo"], "Reuniao")

    def test_calendario_hoje_erro_na_conexao_nao_quebra(self):
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", side_effect=Exception("timeout")
        ):
            res = self.client.get("/api/calendario/hoje")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["configurado"])
        self.assertEqual(body["eventos"], [])
        self.assertIn("erro", body)

    def test_calendario_hoje_mostra_tarefa_com_horario_mesmo_sem_icloud(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("consulta medica", hoje, "14:00"),
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/calendario/hoje")
        body = res.get_json()
        self.assertFalse(body["configurado"])
        self.assertEqual(len(body["eventos"]), 1)
        evento = body["eventos"][0]
        self.assertEqual(evento["titulo"], "consulta medica")
        self.assertEqual(evento["origem"], "tarefa")
        self.assertEqual(evento["inicio"], f"{hoje}T14:00:00")
        self.assertEqual(evento["fim"], evento["inicio"])

    def test_calendario_hoje_combina_tarefas_e_icloud_ordenado_por_horario(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        # registrada em ordem invertida de proposito - o horario que decide a posicao final,
        # nao a ordem de cadastro (era exatamente essa a confusao que o Alex reportou)
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("academia", hoje, "22:00"),
        )
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("consulta medica", hoje, "13:00"),
        )
        conn.commit()
        conn.close()

        eventos_fake = [
            {
                "titulo": "Reuniao",
                "inicio": f"{hoje}T10:00:00",
                "fim": f"{hoje}T11:00:00",
                "dia_inteiro": False,
            }
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ):
            res = self.client.get("/api/calendario/hoje")

        body = res.get_json()
        titulos_em_ordem = [e["titulo"] for e in body["eventos"]]
        self.assertEqual(titulos_em_ordem, ["Reuniao", "consulta medica", "academia"])
        origens = {e["titulo"]: e["origem"] for e in body["eventos"]}
        self.assertEqual(origens["Reuniao"], "calendario")
        self.assertEqual(origens["consulta medica"], "tarefa")

    def test_calendario_hoje_ignora_tarefa_com_horario_de_outro_dia(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("consulta amanha", amanha, "09:00"),
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/calendario/hoje")
        self.assertEqual(res.get_json()["eventos"], [])

    def test_calendario_hoje_ignora_tarefa_concluida(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, datetime('now'))",
            ("consulta ja feita", hoje, "09:00"),
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/calendario/hoje")
        self.assertEqual(res.get_json()["eventos"], [])

    def test_fechamento_do_dia_lista_concluidas_e_pendentes_de_hoje(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, datetime('now'))",
            ("academia", hoje),
        )
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
            ("ligar pro dentista", hoje),
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/fechamento-do-dia")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["concluidas"], ["academia"])
        self.assertEqual(body["pendentes_hoje"], ["ligar pro dentista"])

    def test_fechamento_do_dia_ignora_tarefa_pendente_de_outro_dia(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("viagem", amanha))
        conn.commit()
        conn.close()

        res = self.client.get("/api/fechamento-do-dia")
        body = res.get_json()
        self.assertEqual(body["concluidas"], [])
        self.assertEqual(body["pendentes_hoje"], [])

    def test_fechamento_do_dia_vazio_sem_tarefas(self):
        res = self.client.get("/api/fechamento-do-dia")
        body = res.get_json()
        self.assertEqual(body["concluidas"], [])
        self.assertEqual(body["pendentes_hoje"], [])

    def test_gastos_resumo_semanal_endpoint(self):
        parsed = {
            "tipo": "gasto",
            "titulo": "mercado",
            "valor": 42.0,
            "categoria": "mercado",
            "quando": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "gastei 42 no mercado"})

        res = self.client.get("/api/gastos/resumo-semanal")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["total_semana"], 42.0)
        self.assertEqual(body["categoria_top"], "mercado")

    def test_gastos_resumo_semanal_ignora_gasto_planejado(self):
        parsed = {
            "tipo": "gasto",
            "titulo": "talvez compre um fone",
            "valor": 300.0,
            "categoria": "lazer",
            "status": "planejado",
            "quando": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "to pensando em comprar um fone de 300"})

        res = self.client.get("/api/gastos/resumo-semanal")
        self.assertEqual(res.get_json()["total_semana"], 0)

    def test_plano_do_dia_nao_duplica_tarefa_com_horario_hoje(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("consulta medica", hoje, "14:00"),
        )
        conn.execute("INSERT INTO tasks (title) VALUES (?)", ("tarefa sem hora",))
        conn.commit()
        conn.close()

        with patch(
            "claude_client.plano_do_dia", return_value=("1. Faca algo.", fake_usage())
        ) as mock_plano:
            res = self.client.post("/api/plano-do-dia")
        self.assertEqual(res.status_code, 200)

        args = mock_plano.call_args[0]
        tarefas_soltas, compromissos = args[0], args[1]
        self.assertEqual(tarefas_soltas, ["tarefa sem hora"])
        self.assertEqual(len(compromissos), 1)
        self.assertEqual(compromissos[0]["titulo"], "consulta medica")
        self.assertEqual(compromissos[0]["origem"], "tarefa")

    def test_resumo_do_dia_inclui_contagem_de_eventos(self):
        eventos_fake = [
            {"titulo": "Dentista", "inicio": "2026-09-18T10:00:00", "fim": "2026-09-18T11:00:00", "dia_inteiro": False}
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ), patch(
            "claude_client.summarize_day",
            return_value=("Dia com 1 compromisso.", fake_usage()),
        ) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["eventos_hoje"], 1)
        # confirma que os titulos dos eventos foram passados pro prompt
        args = mock_summarize.call_args[0]
        self.assertEqual(args[3], ["Dentista"])

    def test_resumo_do_dia_sem_calendario_configurado_nao_quebra(self):
        with patch(
            "claude_client.summarize_day",
            return_value=("Dia tranquilo.", fake_usage()),
        ):
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["eventos_hoje"], 0)

    def test_plano_do_dia_usa_tarefas_e_agenda(self):
        parsed = {
            "tipo": "tarefa",
            "titulo": "levar carro na oficina",
            "valor": None,
            "categoria": None,
            "quando": None,
            "prazo": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "levar carro na oficina"})

        eventos_fake = [
            {"titulo": "Dentista", "inicio": "2026-09-18T10:00:00", "fim": "2026-09-18T11:00:00", "dia_inteiro": False}
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ), patch(
            "claude_client.plano_do_dia",
            return_value=("1. Faca X antes do dentista.", fake_usage()),
        ) as mock_plano:
            res = self.client.post("/api/plano-do-dia")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["plano"], "1. Faca X antes do dentista.")
        args = mock_plano.call_args[0]
        self.assertEqual(args[0], ["levar carro na oficina"])
        self.assertEqual(args[1], [dict(eventos_fake[0], origem="calendario")])

    def test_viagem_status_sem_configuracao(self):
        res = self.client.get("/api/viagem/status")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["configurado"])

    def test_viagem_quando_sair_sem_configuracao_da_erro(self):
        res = self.client.post(
            "/api/viagem/quando-sair",
            json={"origem": "Casa", "destino": "Aeroporto", "chegar_ate": "2026-09-20T14:00:00"},
        )
        self.assertEqual(res.status_code, 400)

    def test_viagem_quando_sair_calcula_com_margem(self):
        resultado_fake = {
            "sair_ate": "2026-09-20T12:54:00",
            "duracao_minutos": 46,
            "distancia_km": 18.5,
            "margem_minutos": 20,
        }
        with patch("maps_client.configurado", return_value=True), patch(
            "maps_client.horario_de_saida", return_value=resultado_fake
        ) as mock_calc:
            res = self.client.post(
                "/api/viagem/quando-sair",
                json={
                    "origem": "Rua A, 100",
                    "destino": "Aeroporto",
                    "chegar_ate": "2026-09-20T14:00:00",
                    "margem_minutos": 20,
                },
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), resultado_fake)
        mock_calc.assert_called_once()

    def test_viagem_quando_sair_sem_destino_da_erro(self):
        with patch("maps_client.configurado", return_value=True):
            res = self.client.post(
                "/api/viagem/quando-sair",
                json={"origem": "Casa", "chegar_ate": "2026-09-20T14:00:00"},
            )
        self.assertEqual(res.status_code, 400)

    def test_viagem_quando_sair_data_invalida_da_erro(self):
        with patch("maps_client.configurado", return_value=True):
            res = self.client.post(
                "/api/viagem/quando-sair",
                json={"origem": "Casa", "destino": "Aeroporto", "chegar_ate": "nao-e-uma-data"},
            )
        self.assertEqual(res.status_code, 400)

    def test_captura_com_memoria_grava_e_lista(self):
        parsed = {
            "tipo": "tarefa",
            "titulo": "ligar pro dentista",
            "valor": None,
            "categoria": None,
            "quando": None,
            "duvida": None,
            "memoria": "esta enrolando pra ligar pro dentista",
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "preciso ligar pro dentista"})
        self.assertEqual(res.status_code, 201)

        memorias = self.client.get("/api/memorias").get_json()
        self.assertEqual(len(memorias), 1)
        self.assertEqual(memorias[0]["texto"], "esta enrolando pra ligar pro dentista")

    def test_captura_sem_memoria_nao_grava_nada(self):
        parsed = {
            "tipo": "gasto",
            "titulo": "mercado",
            "valor": 50.0,
            "categoria": "mercado",
            "quando": None,
            "duvida": None,
            "memoria": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "gastei 50 no mercado"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.client.get("/api/memorias").get_json(), [])

    def test_apagar_memoria_remove_da_lista(self):
        conn = db.get_db()
        memoria_id = db.create_memoria(conn, "prefere economizar pra viagem")
        conn.close()

        res = self.client.delete(f"/api/memorias/{memoria_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/memorias").get_json(), [])

    def test_resumo_do_dia_recebe_memorias(self):
        conn = db.get_db()
        db.create_memoria(conn, "trabalha home office as quartas")
        conn.close()

        with patch(
            "claude_client.summarize_day",
            return_value=("Dia tranquilo.", fake_usage()),
        ) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        args = mock_summarize.call_args[0]
        self.assertEqual(args[4], ["trabalha home office as quartas"])

    def test_plano_do_dia_recebe_memorias(self):
        conn = db.get_db()
        db.create_memoria(conn, "prefere tarefas rapidas de manha")
        conn.close()

        with patch(
            "claude_client.plano_do_dia",
            return_value=("1. Faca a tarefa rapida.", fake_usage()),
        ) as mock_plano:
            res = self.client.post("/api/plano-do-dia")
        self.assertEqual(res.status_code, 200)
        args = mock_plano.call_args[0]
        self.assertEqual(args[2], ["prefere tarefas rapidas de manha"])

    def test_seed_perfil_inicial_roda_uma_vez_em_banco_novo(self):
        tmp = tempfile.TemporaryDirectory()
        caminho_original = db.DB_PATH
        db.DB_PATH = Path(tmp.name) / "painel.db"
        try:
            db.init_db()
            conn = db.get_db()
            memorias = db.list_memorias(conn)
            self.assertEqual(len(memorias), len(db.PERFIL_INICIAL))
            self.assertTrue(all(m["source_text"] == "perfil-inicial" for m in memorias))

            # rodar de novo (ex: reiniciar o app) nao duplica
            db.init_db()
            self.assertEqual(len(db.list_memorias(conn)), len(db.PERFIL_INICIAL))
            conn.close()
        finally:
            db.DB_PATH = caminho_original
            tmp.cleanup()

    def test_saude_hoje_sem_dados(self):
        res = self.client.get("/api/saude/hoje")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.get_json()["dados"])

    def test_saude_importar_grava_e_aparece_em_hoje(self):
        res = self.client.post(
            "/api/saude/importar", json={"passos": 8000, "distancia_km": 5.5, "sono_horas": 7.0}
        )
        self.assertEqual(res.status_code, 200)

        dados = self.client.get("/api/saude/hoje").get_json()["dados"]
        self.assertEqual(dados["passos"], 8000)
        self.assertEqual(dados["distancia_km"], 5.5)
        self.assertEqual(dados["sono_horas"], 7.0)

    def test_saude_importar_so_atualiza_campos_informados(self):
        self.client.post("/api/saude/importar", json={"passos": 8000, "sono_horas": 7.0})
        self.client.post("/api/saude/importar", json={"passos": 9500})

        dados = self.client.get("/api/saude/hoje").get_json()["dados"]
        self.assertEqual(dados["passos"], 9500)
        self.assertEqual(dados["sono_horas"], 7.0)

    def test_saude_importar_sem_campos_da_erro(self):
        res = self.client.post("/api/saude/importar", json={})
        self.assertEqual(res.status_code, 400)

    def test_saude_importar_data_invalida_da_erro(self):
        res = self.client.post("/api/saude/importar", json={"passos": 100, "data": "ontem"})
        self.assertEqual(res.status_code, 400)

    def test_saude_importar_com_token_errado_da_erro(self):
        with patch.dict(os.environ, {"SAUDE_WEBHOOK_TOKEN": "segredo123"}):
            res = self.client.post("/api/saude/importar", json={"passos": 100})
            self.assertEqual(res.status_code, 401)

            res_ok = self.client.post(
                "/api/saude/importar",
                json={"passos": 100},
                headers={"X-Webhook-Token": "segredo123"},
            )
            self.assertEqual(res_ok.status_code, 200)

    def test_resumo_do_dia_recebe_contexto_de_saude(self):
        self.client.post("/api/saude/importar", json={"passos": 12000})

        with patch(
            "claude_client.summarize_day",
            return_value=("Dia ativo.", fake_usage()),
        ) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        args = mock_summarize.call_args[0]
        self.assertEqual(args[5], "12000 passos hoje")

    def test_captura_tarefa_com_prazo_grava_due_date(self):
        parsed = {
            "tipo": "tarefa",
            "titulo": "ligar pro dentista",
            "valor": None,
            "categoria": None,
            "quando": "amanha",
            "quando_data": "2026-09-19",
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "ligar pro dentista amanha"})
        self.assertEqual(res.status_code, 201)

        conn = db.get_db()
        row = conn.execute("SELECT due_at, due_date FROM tasks").fetchone()
        conn.close()
        self.assertEqual(row["due_at"], "amanha")
        self.assertEqual(row["due_date"], "2026-09-19")

    def test_captura_tarefa_com_horario_grava_hora(self):
        hoje = date.today().isoformat()
        parsed = {
            "tipo": "tarefa",
            "titulo": "consulta medica",
            "valor": None,
            "categoria": None,
            "quando": "hoje",
            "quando_data": hoje,
            "hora": "14:00",
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "hoje as 14h tenho consulta medica"})
        self.assertEqual(res.status_code, 201)

        conn = db.get_db()
        row = conn.execute("SELECT due_date, hora FROM tasks").fetchone()
        conn.close()
        self.assertEqual(row["due_date"], hoje)
        self.assertEqual(row["hora"], "14:00")

    def test_captura_tarefa_com_hora_sem_zero_a_esquerda_e_normalizada(self):
        hoje = date.today().isoformat()
        parsed = {
            "tipo": "tarefa",
            "titulo": "academia",
            "valor": None,
            "categoria": None,
            "quando": "hoje",
            "quando_data": hoje,
            "hora": "9:5",
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "hoje as 9:05 academia"})
        self.assertEqual(res.status_code, 201)

        conn = db.get_db()
        row = conn.execute("SELECT hora FROM tasks").fetchone()
        conn.close()
        self.assertEqual(row["hora"], "09:05")

    def test_captura_tarefa_com_hora_invalida_nao_quebra_e_vira_nula(self):
        parsed = {
            "tipo": "tarefa",
            "titulo": "academia",
            "valor": None,
            "categoria": None,
            "quando": None,
            "quando_data": None,
            "hora": "25:99",
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "academia"})
        self.assertEqual(res.status_code, 201)

        conn = db.get_db()
        row = conn.execute("SELECT hora FROM tasks").fetchone()
        conn.close()
        self.assertIsNone(row["hora"])

    def test_captura_tarefa_sem_horario_grava_hora_nula(self):
        parsed = {
            "tipo": "tarefa",
            "titulo": "ligar pro dentista",
            "valor": None,
            "categoria": None,
            "quando": None,
            "quando_data": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "ligar pro dentista"})
        self.assertEqual(res.status_code, 201)

        conn = db.get_db()
        row = conn.execute("SELECT hora FROM tasks").fetchone()
        conn.close()
        self.assertIsNone(row["hora"])

    def test_chat_resposta_de_texto_simples(self):
        with patch(
            "claude_client.chat", return_value=("Oi! Beleza?", [], fake_usage())
        ) as mock_chat:
            res = self.client.post("/api/chat", json={"mensagem": "oi"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["resposta"], "Oi! Beleza?")
        self.assertEqual(res.get_json()["acoes"], [])
        mock_chat.assert_called_once()

        historico = self.client.get("/api/chat/historico").get_json()
        self.assertEqual(len(historico), 2)
        self.assertEqual(historico[0]["papel"], "user")
        self.assertEqual(historico[1]["papel"], "assistant")

    def test_chat_sem_mensagem_da_erro(self):
        res = self.client.post("/api/chat", json={"mensagem": "  "})
        self.assertEqual(res.status_code, 400)

    def test_chat_usa_executor_de_tarefa_de_verdade(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_tarefa"]({"titulo": "levar carro na oficina"})
            self.assertEqual(resultado, {"ok": True})
            return "Registrei a tarefa.", ["registrar_tarefa"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "leva o carro na oficina"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_tarefa"])

        tarefas = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tarefas), 1)
        self.assertEqual(tarefas[0]["title"], "levar carro na oficina")

    def test_chat_registrar_tarefa_com_horario_grava_hora(self):
        hoje = date.today().isoformat()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_tarefa"](
                {"titulo": "consulta medica", "quando_data": hoje, "hora": "14:00"}
            )
            self.assertEqual(resultado, {"ok": True})
            return "Registrei.", ["registrar_tarefa"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "hoje as 14h tenho consulta"})
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        row = conn.execute("SELECT due_date, hora FROM tasks").fetchone()
        conn.close()
        self.assertEqual(row["due_date"], hoje)
        self.assertEqual(row["hora"], "14:00")

    def test_notificacoes_verificar_agora_sem_push_configurado(self):
        res = self.client.post("/api/notificacoes/verificar-agora")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["avisos_enviados"], 0)

    def test_notificacoes_verificar_agora_envia_e_deduplica(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta", ontem))
        conn.commit()
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            res1 = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(res1.get_json()["avisos_enviados"], 1)
            self.assertEqual(mock_enviar.call_count, 1)

            # rodar de novo no mesmo dia nao manda de novo
            res2 = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(res2.get_json()["avisos_enviados"], 0)
            self.assertEqual(mock_enviar.call_count, 1)

    def test_notificacoes_verificar_agora_inclui_tarefa_com_horario_chegado(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("colocar o lixo pra fora", hoje, "00:00"),
        )
        conn.commit()
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            res = self.client.post("/api/notificacoes/verificar-agora")
        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        corpo = mock_enviar.call_args[0][2]
        self.assertIn("colocar o lixo pra fora", corpo)

    def test_lembretes_lista_vazia(self):
        self.assertEqual(self.client.get("/api/lembretes").get_json(), [])

    def test_apagar_lembrete_remove_da_lista(self):
        conn = db.get_db()
        lembrete_id = db.create_lembrete(conn, "Validade da licenca", "2027-03-10", recorrente=True)
        conn.close()

        lembretes = self.client.get("/api/lembretes").get_json()
        self.assertEqual(len(lembretes), 1)

        res = self.client.delete(f"/api/lembretes/{lembrete_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/lembretes").get_json(), [])

    def test_criar_lembrete_manual(self):
        res = self.client.post(
            "/api/lembretes",
            json={"titulo": "Seguro do carro", "data": "2027-05-20", "recorrente": True},
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json()["ok"])

        lembretes = self.client.get("/api/lembretes").get_json()
        self.assertEqual(len(lembretes), 1)
        self.assertEqual(lembretes[0]["titulo"], "Seguro do carro")
        self.assertEqual(lembretes[0]["recorrente"], 1)

    def test_criar_lembrete_sem_titulo_rejeita(self):
        res = self.client.post("/api/lembretes", json={"titulo": "  ", "data": "2027-05-20"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get("/api/lembretes").get_json(), [])

    def test_criar_lembrete_com_data_invalida_rejeita(self):
        for data_ruim in ["31/12/2027", "2027-13-40", "", None, "amanha"]:
            res = self.client.post("/api/lembretes", json={"titulo": "X", "data": data_ruim})
            self.assertEqual(res.status_code, 400, msg=f"deveria rejeitar data={data_ruim!r}")
        self.assertEqual(self.client.get("/api/lembretes").get_json(), [])

    def test_criar_lembrete_registra_atividade_do_dia(self):
        self.client.post("/api/lembretes", json={"titulo": "X", "data": "2027-05-20"})
        streak_data = self.client.get("/api/streak").get_json()
        self.assertEqual(streak_data["dias"], 1)
        self.assertTrue(streak_data["ativo_hoje"])

    def test_chat_usa_executor_de_lembrete_de_verdade(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_lembrete"](
                {"titulo": "Validade do exame medico", "data": "2027-01-15", "recorrente": True}
            )
            self.assertEqual(resultado, {"ok": True})
            return "Beleza, vou te lembrar todo ano perto dessa data.", ["registrar_lembrete"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "meu exame medico de piloto vence dia 15 de janeiro, todo ano"}
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_lembrete"])

        lembretes = self.client.get("/api/lembretes").get_json()
        self.assertEqual(len(lembretes), 1)
        self.assertEqual(lembretes[0]["titulo"], "Validade do exame medico")
        self.assertEqual(lembretes[0]["recorrente"], 1)

    def test_notificacoes_verificar_agora_inclui_lembrete_proximo(self):
        data = (date.today() + timedelta(days=2)).isoformat()
        conn = db.get_db()
        db.create_lembrete(conn, "Renovar seguro", data, recorrente=False)
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            res = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(res.get_json()["avisos_enviados"], 1)
            mock_enviar.assert_called_once()
            titulo_notif = mock_enviar.call_args[0][1]
            self.assertEqual(titulo_notif, "Data importante chegando")

    def test_chat_tarefa_com_data_grava_due_date(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_tarefa"](
                {"titulo": "ligar pro dentista", "quando": "amanha", "quando_data": "2026-09-19"}
            )
            return "Registrei pra amanha.", ["registrar_tarefa"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "ligar pro dentista amanha"})

        conn = db.get_db()
        row = conn.execute("SELECT due_at, due_date FROM tasks").fetchone()
        conn.close()
        self.assertEqual(row["due_at"], "amanha")
        self.assertEqual(row["due_date"], "2026-09-19")

    def test_chat_usa_executor_de_memoria_de_verdade(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_memoria"](
                {"fato": "prefere resolver assuntos financeiros de manha"}
            )
            self.assertEqual(resultado, {"ok": True})
            return "Anotado.", ["registrar_memoria"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "eu prefiro resolver assuntos financeiros de manha"}
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_memoria"])

        memorias = self.client.get("/api/memorias").get_json()
        self.assertEqual(len(memorias), 1)
        self.assertEqual(memorias[0]["texto"], "prefere resolver assuntos financeiros de manha")

    def test_resumo_do_dia_recebe_contexto_da_construtora(self):
        resposta_fake = MagicMock()
        resposta_fake.raise_for_status = lambda: None
        resposta_fake.json.return_value = {
            "status": "ok",
            "tot_entradas": 100000.0,
            "tot_saidas": 40000.0,
            "lucro_liquido": 60000.0,
            "margem": 60.0,
        }
        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", return_value=resposta_fake), patch(
            "claude_client.summarize_day", return_value=("Dia ok.", fake_usage())
        ) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        args = mock_summarize.call_args[0]
        self.assertIn("lucro liquido R$ 60000.00", args[6])

    def test_resumo_do_dia_sem_construtora_configurada_nao_quebra(self):
        with patch(
            "claude_client.summarize_day", return_value=("Dia ok.", fake_usage())
        ) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        args = mock_summarize.call_args[0]
        self.assertIsNone(args[6])

    def test_chat_contexto_inclui_construtora_quando_configurada(self):
        resposta_fake = MagicMock()
        resposta_fake.raise_for_status = lambda: None
        resposta_fake.json.return_value = {
            "status": "ok",
            "tot_entradas": 100000.0,
            "tot_saidas": 40000.0,
            "lucro_liquido": 60000.0,
            "margem": 60.0,
        }

        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertIn("Construtora", contexto)
            self.assertIn("60000.00", contexto)
            return "Beleza.", [], fake_usage()

        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", return_value=resposta_fake), patch(
            "claude_client.chat", side_effect=fake_chat
        ):
            res = self.client.post("/api/chat", json={"mensagem": "como ta a construtora?"})
        self.assertEqual(res.status_code, 200)

    def test_construtora_contexto_ignora_falha_de_rede(self):
        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", side_effect=requests.RequestException("fora do ar")), patch(
            "claude_client.summarize_day", return_value=("Dia ok.", fake_usage())
        ) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        args = mock_summarize.call_args[0]
        self.assertIsNone(args[6])

    def test_streak_zero_sem_nenhuma_atividade(self):
        res = self.client.get("/api/streak")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"dias": 0, "ativo_hoje": False})

    def test_streak_sobe_ao_completar_tarefa(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('lavar o aviao')")
        conn.commit()
        task_id = conn.execute("SELECT id FROM tasks").fetchone()["id"]
        conn.close()

        self.client.post(f"/api/tasks/{task_id}/complete")
        data = self.client.get("/api/streak").get_json()
        self.assertEqual(data, {"dias": 1, "ativo_hoje": True})

    def test_streak_conta_dias_consecutivos_ja_registrados(self):
        conn = db.get_db()
        hoje = date.today()
        for i in range(3):
            db.registrar_atividade(conn, (hoje - timedelta(days=i)).isoformat())
        conn.close()

        data = self.client.get("/api/streak").get_json()
        self.assertEqual(data, {"dias": 3, "ativo_hoje": True})

    def test_streak_nao_conta_atividade_de_dias_nao_consecutivos(self):
        conn = db.get_db()
        hoje = date.today()
        db.registrar_atividade(conn, hoje.isoformat())
        db.registrar_atividade(conn, (hoje - timedelta(days=5)).isoformat())
        conn.close()

        data = self.client.get("/api/streak").get_json()
        self.assertEqual(data["dias"], 1)

    def test_criar_voo_agendado_sem_horas(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        res = self.client.post(
            "/api/voos", json={"data": amanha, "destino": "Blumenau", "origem": "Navegantes"}
        )
        self.assertEqual(res.status_code, 201)

        voos = self.client.get("/api/voos").get_json()
        self.assertEqual(len(voos), 1)
        self.assertEqual(voos[0]["destino"], "Blumenau")
        self.assertIsNone(voos[0]["horas"])

    def test_criar_voo_realizado_com_horas(self):
        hoje = date.today().isoformat()
        res = self.client.post(
            "/api/voos",
            json={"data": hoje, "destino": "Blumenau", "horas": 1.5, "observacao": "treino de pouso"},
        )
        self.assertEqual(res.status_code, 201)
        voos = self.client.get("/api/voos").get_json()
        self.assertEqual(voos[0]["horas"], 1.5)
        self.assertEqual(voos[0]["observacao"], "treino de pouso")

    def test_criar_voo_sem_destino_rejeita(self):
        res = self.client.post("/api/voos", json={"data": date.today().isoformat(), "destino": "  "})
        self.assertEqual(res.status_code, 400)

    def test_criar_voo_com_data_invalida_rejeita(self):
        res = self.client.post("/api/voos", json={"data": "31/12/2027", "destino": "Blumenau"})
        self.assertEqual(res.status_code, 400)

    def test_criar_voo_com_horas_negativa_rejeita(self):
        res = self.client.post(
            "/api/voos", json={"data": date.today().isoformat(), "destino": "Blumenau", "horas": -1}
        )
        self.assertEqual(res.status_code, 400)

    def test_criar_voo_registra_atividade(self):
        self.client.post(
            "/api/voos", json={"data": date.today().isoformat(), "destino": "Blumenau", "horas": 1.0}
        )
        streak_data = self.client.get("/api/streak").get_json()
        self.assertEqual(streak_data["dias"], 1)

    def test_apagar_voo_remove_da_lista(self):
        self.client.post(
            "/api/voos", json={"data": date.today().isoformat(), "destino": "Blumenau", "horas": 1.0}
        )
        voo_id = self.client.get("/api/voos").get_json()[0]["id"]
        res = self.client.delete(f"/api/voos/{voo_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/voos").get_json(), [])

    def test_voos_resumo_soma_horas_e_lista_proximos(self):
        hoje = date.today()
        amanha = (hoje + timedelta(days=1)).isoformat()
        self.client.post(
            "/api/voos", json={"data": hoje.isoformat(), "destino": "Blumenau", "horas": 1.5}
        )
        self.client.post("/api/voos", json={"data": amanha, "destino": "Brusque"})

        with patch("clima.previsao_para_cidade_e_data", return_value=None):
            data = self.client.get("/api/voos/resumo").get_json()

        self.assertEqual(data["horas_semana"], 1.5)
        self.assertEqual(len(data["proximos"]), 2)

    def test_voos_resumo_anexa_clima_quando_disponivel(self):
        hoje = date.today().isoformat()
        self.client.post("/api/voos", json={"data": hoje, "destino": "Blumenau"})
        previsao_fake = {"chuva_pct": 90, "temp_max": 20.0, "temp_min": 14.0, "alerta_chuva": True}
        with patch("clima.previsao_para_cidade_e_data", return_value=previsao_fake):
            data = self.client.get("/api/voos/resumo").get_json()
        self.assertEqual(data["proximos"][0]["clima"], previsao_fake)

    def test_clima_metar_devolve_dados_da_fonte(self):
        with patch(
            "metar.buscar_metar_taf",
            return_value={"metar": "SBBI 181800Z ...", "taf": "TAF SBBI ...", "erro": None},
        ):
            res = self.client.get("/api/clima/metar?icao=SBBI")
        self.assertEqual(res.status_code, 200)
        self.assertIn("SBBI", res.get_json()["metar"])

    def test_chat_usa_executor_de_voo_de_verdade(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_voo"](
                {"data": "2027-01-15", "destino": "Balneario Camboriu", "horas": 1.2}
            )
            self.assertEqual(resultado, {"ok": True})
            return "Beleza, registrei o voo.", ["registrar_voo"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "voei 1.2h hoje pra Balneario"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_voo"])

        voos = self.client.get("/api/voos").get_json()
        self.assertEqual(len(voos), 1)
        self.assertEqual(voos[0]["destino"], "Balneario Camboriu")

    def test_chat_contexto_inclui_proximos_voos(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        self.client.post("/api/voos", json={"data": amanha, "destino": "Blumenau"})

        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertIn("Blumenau", contexto)
            self.assertIn("Proximos voos", contexto)
            return "Beleza.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "e ai, como ta minha semana?"})
        self.assertEqual(res.status_code, 200)

    def test_clima_hoje_sem_cidade_padrao_configurada(self):
        res = self.client.get("/api/clima/hoje")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"configurado": False})

    def test_clima_hoje_com_cidade_configurada(self):
        resumo_fake = {
            "alerta": True,
            "chovendo_agora": False,
            "hora_inicio": 14,
            "hora_fim": 18,
            "chuva_pct_max": 80,
            "texto": "Risco de chuva entre 14h e 18h (ate 80% de chance).",
            "cidade": "Brusque",
        }
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), patch(
            "clima.resumo_chuva_hoje_para_cidade", return_value=resumo_fake
        ):
            res = self.client.get("/api/clima/hoje")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["configurado"])
        self.assertTrue(data["alerta"])
        self.assertEqual(data["cidade"], "Brusque")

    def test_clima_hoje_com_cidade_mas_previsao_falha(self):
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), patch(
            "clima.resumo_chuva_hoje_para_cidade", return_value=None
        ):
            res = self.client.get("/api/clima/hoje")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["configurado"])
        self.assertIn("erro", data)

    def test_resumo_do_dia_recebe_contexto_de_clima(self):
        resumo_fake = {"alerta": True, "texto": "Risco de chuva entre 14h e 18h (ate 80% de chance).", "cidade": "Brusque"}
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), patch(
            "clima.resumo_chuva_hoje_para_cidade", return_value=resumo_fake
        ), patch("claude_client.summarize_day", return_value=("Dia ok.", fake_usage())) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        args = mock_summarize.call_args[0]
        self.assertEqual(args[7], "Risco de chuva entre 14h e 18h (ate 80% de chance).")

    def test_resumo_do_dia_sem_cidade_padrao_nao_quebra(self):
        with patch("claude_client.summarize_day", return_value=("Dia ok.", fake_usage())) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        args = mock_summarize.call_args[0]
        self.assertIsNone(args[7])

    def test_chat_contexto_inclui_previsao_do_tempo_quando_configurada(self):
        resumo_fake = {"alerta": True, "texto": "Risco de chuva entre 14h e 18h (ate 80% de chance).", "cidade": "Brusque"}

        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertIn("Previsao do tempo hoje", contexto)
            self.assertIn("80%", contexto)
            return "Beleza.", [], fake_usage()

        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), patch(
            "clima.resumo_chuva_hoje_para_cidade", return_value=resumo_fake
        ), patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "vou sair mais tarde, vai dar?"})
        self.assertEqual(res.status_code, 200)

    def test_clima_contexto_ignora_falha_sem_quebrar_resumo(self):
        with patch.dict(os.environ, {"CIDADE_PADRAO": "CidadeQueNaoExiste"}), patch(
            "clima.resumo_chuva_hoje_para_cidade", return_value=None
        ), patch("claude_client.summarize_day", return_value=("Dia ok.", fake_usage())) as mock_summarize:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        args = mock_summarize.call_args[0]
        self.assertIsNone(args[7])

    # ---- Horario do voo + "quando sair?" ----

    def test_criar_voo_com_hora(self):
        hoje = date.today().isoformat()
        res = self.client.post(
            "/api/voos", json={"data": hoje, "destino": "Aeroporto Navegantes", "hora": "14:00"}
        )
        self.assertEqual(res.status_code, 201)
        voos = self.client.get("/api/voos").get_json()
        self.assertEqual(voos[0]["hora"], "14:00")

    def test_criar_voo_com_hora_sem_zero_a_esquerda_normaliza(self):
        hoje = date.today().isoformat()
        self.client.post("/api/voos", json={"data": hoje, "destino": "Blumenau", "hora": "9:5"})
        voos = self.client.get("/api/voos").get_json()
        self.assertEqual(voos[0]["hora"], "09:05")

    def test_criar_voo_com_hora_invalida_fica_nula(self):
        hoje = date.today().isoformat()
        self.client.post("/api/voos", json={"data": hoje, "destino": "Blumenau", "hora": "25:99"})
        voos = self.client.get("/api/voos").get_json()
        self.assertIsNone(voos[0]["hora"])

    def test_criar_voo_sem_hora_fica_nula(self):
        hoje = date.today().isoformat()
        self.client.post("/api/voos", json={"data": hoje, "destino": "Blumenau"})
        voos = self.client.get("/api/voos").get_json()
        self.assertIsNone(voos[0]["hora"])

    def test_chat_registrar_voo_com_hora(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_voo"](
                {"data": "2027-01-15", "destino": "Aeroporto", "hora": "14:00"}
            )
            return "Beleza.", ["registrar_voo"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "meu voo amanha e as 14h"})
        self.assertEqual(res.status_code, 200)
        voos = self.client.get("/api/voos").get_json()
        self.assertEqual(voos[0]["hora"], "14:00")

    # ---- Gasto real x planejado ----

    def test_captura_gasto_sem_status_vira_real(self):
        parsed = {
            "tipo": "gasto", "titulo": "mercado", "valor": 50.0, "categoria": "mercado",
            "status": None, "quando": None, "quando_data": None, "hora": None,
            "prazo": None, "duvida": None, "memoria": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": "gastei 50 no mercado"})
        self.assertEqual(res.status_code, 201)
        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(expenses[0]["tipo"], "real")

    def test_captura_gasto_planejado_marca_tipo(self):
        parsed = {
            "tipo": "gasto", "titulo": "notebook novo", "valor": 3000.0, "categoria": "outros",
            "status": "planejado", "quando": None, "quando_data": None, "hora": None,
            "prazo": None, "duvida": None, "memoria": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post(
                "/api/capture", json={"text": "penso em comprar um notebook de 3000"}
            )
        self.assertEqual(res.status_code, 201)
        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(expenses[0]["tipo"], "planejado")

    def test_gasto_planejado_nao_conta_no_resumo_do_dia(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_gasto"]({"titulo": "gasolina", "valor": 100.0, "status": "real"})
            executores["registrar_gasto"](
                {"titulo": "compra no cartao", "valor": 300.0, "status": "planejado"}
            )
            return "Beleza.", ["registrar_gasto", "registrar_gasto"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post(
                "/api/chat",
                json={"mensagem": "gastei 100 de gasolina e penso em gastar 300 no cartao"},
            )

        with patch("claude_client.summarize_day", return_value=("Dia ok.", fake_usage())):
            res = self.client.get("/api/summary/today")
        body = res.get_json()
        self.assertEqual(body["gasto_hoje"], 100.0)
        self.assertEqual(body["gasto_planejado"], 300.0)

    def test_gasto_planejado_nao_entra_no_historico_do_grafico(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_gasto"]({"titulo": "gasolina", "valor": 100.0, "status": "real"})
            executores["registrar_gasto"](
                {"titulo": "compra no cartao", "valor": 300.0, "status": "planejado"}
            )
            return "Beleza.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "..."})

        historico = self.client.get("/api/expenses/historico?dias=1").get_json()
        self.assertEqual(historico[0]["total"], 100.0)

    def test_gasto_sem_status_no_chat_vira_real(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_gasto"]({"titulo": "padaria", "valor": 15.0})
            return "Beleza.", ["registrar_gasto"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "gastei 15 na padaria"})
        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(expenses[0]["tipo"], "real")

    # ---- Push "sair em breve" antes do voo ----

    def test_verificar_notifica_voo_perto_da_hora_de_sair(self):
        hoje = date.today().isoformat()
        self.client.post("/api/voos", json={"data": hoje, "destino": "Aeroporto", "hora": "14:00"})
        sub = {"endpoint": "https://exemplo.com/push/voo", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        sair_em_breve = (datetime.now() + timedelta(minutes=10)).isoformat()
        resultado_fake = {
            "sair_ate": sair_em_breve,
            "duracao_minutos": 40,
            "distancia_km": 15.0,
            "margem_minutos": 60,
        }
        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Teste, 100"}), patch(
            "maps_client.configurado", return_value=True
        ), patch("maps_client.horario_de_saida", return_value=resultado_fake), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        corpo_notificado = mock_enviar.call_args[0][2]
        self.assertIn("Aeroporto", corpo_notificado)

    def test_verificar_nao_notifica_voo_com_hora_de_sair_distante(self):
        hoje = date.today().isoformat()
        self.client.post("/api/voos", json={"data": hoje, "destino": "Aeroporto", "hora": "22:00"})
        sub = {"endpoint": "https://exemplo.com/push/voo2", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        sair_longe = (datetime.now() + timedelta(hours=5)).isoformat()
        resultado_fake = {
            "sair_ate": sair_longe, "duracao_minutos": 40, "distancia_km": 15.0, "margem_minutos": 60,
        }
        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Teste, 100"}), patch(
            "maps_client.configurado", return_value=True
        ), patch("maps_client.horario_de_saida", return_value=resultado_fake), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_not_called()

    def test_verificar_voo_sem_endereco_casa_nao_quebra(self):
        hoje = date.today().isoformat()
        self.client.post("/api/voos", json={"data": hoje, "destino": "Aeroporto", "hora": "14:00"})
        sub = {"endpoint": "https://exemplo.com/push/voo3", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch.dict(os.environ, {"ENDERECO_CASA": ""}), patch(
            "maps_client.configurado", return_value=True
        ), patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.status_code, 200)
        mock_enviar.assert_not_called()

    def test_verificar_voo_ja_notificado_nao_repete(self):
        hoje = date.today().isoformat()
        self.client.post("/api/voos", json={"data": hoje, "destino": "Aeroporto", "hora": "14:00"})
        sub = {"endpoint": "https://exemplo.com/push/voo4", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        sair_em_breve = (datetime.now() + timedelta(minutes=10)).isoformat()
        resultado_fake = {
            "sair_ate": sair_em_breve, "duracao_minutos": 40, "distancia_km": 15.0, "margem_minutos": 60,
        }
        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Teste, 100"}), patch(
            "maps_client.configurado", return_value=True
        ), patch("maps_client.horario_de_saida", return_value=resultado_fake), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")
            res2 = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res2.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_called_once()

    def test_verificar_voo_ja_realizado_nao_e_candidato(self):
        hoje = date.today().isoformat()
        self.client.post(
            "/api/voos", json={"data": hoje, "destino": "Aeroporto", "hora": "14:00", "horas": 1.5}
        )
        sub = {"endpoint": "https://exemplo.com/push/voo5", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Teste, 100"}), patch(
            "maps_client.configurado", return_value=True
        ), patch("maps_client.horario_de_saida") as mock_horario, patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")

        mock_horario.assert_not_called()
        mock_enviar.assert_not_called()

    # ---- Push "como fica sua semana?" (domingo 20h30) ----

    def test_verificar_notifica_planejamento_semanal_na_janela(self):
        sub = {"endpoint": "https://exemplo.com/push/semanal", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("notificacoes.planejamento_semanal_devido", return_value=True), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        corpo_notificado = mock_enviar.call_args[0][2]
        self.assertIn("agenda dessa semana", corpo_notificado)

    def test_verificar_nao_notifica_planejamento_fora_da_janela(self):
        sub = {"endpoint": "https://exemplo.com/push/semanal2", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("notificacoes.planejamento_semanal_devido", return_value=False), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_not_called()

    def test_verificar_planejamento_semanal_ja_notificado_nao_repete(self):
        sub = {"endpoint": "https://exemplo.com/push/semanal3", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("notificacoes.planejamento_semanal_devido", return_value=True), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")
            res2 = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res2.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_called_once()

    # ---- Uber: agendar, estimar (com preco travado) e so pedir com confirmacao ----

    def test_agendar_uber_cria_pedido_pendente(self):
        with patch("uber_client.configurado", return_value=True):
            resultado = self._registrar_via_chat(
                "agendar_uber", {"destino": "Aeroporto", "minutos": 20}
            )
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["minutos"], 20)

        conn = db.get_db()
        pedido = conn.execute("SELECT * FROM uber_pedidos WHERE id = ?", (resultado["pedido_id"],)).fetchone()
        conn.close()
        self.assertEqual(pedido["destino"], "Aeroporto")
        self.assertEqual(pedido["status"], "aguardando")
        disparar_em = datetime.fromisoformat(pedido["disparar_em"])
        self.assertAlmostEqual(
            (disparar_em - datetime.now()).total_seconds(), 20 * 60, delta=10
        )

    def test_agendar_uber_minutos_negativo_vira_zero(self):
        with patch("uber_client.configurado", return_value=True):
            resultado = self._registrar_via_chat(
                "agendar_uber", {"destino": "Aeroporto", "minutos": -5}
            )
        self.assertEqual(resultado["minutos"], 0)

    def test_agendar_uber_sem_configurar_retorna_erro(self):
        with patch("uber_client.configurado", return_value=False):
            resultado = self._registrar_via_chat(
                "agendar_uber", {"destino": "Aeroporto", "minutos": 10}
            )
        self.assertIn("erro", resultado)

    def _criar_uber_pedido_pronto_pra_disparar(self, destino="Aeroporto", origem=None, minutos_atras=1):
        conn = db.get_db()
        disparar_em = (datetime.now() - timedelta(minutes=minutos_atras)).isoformat()
        pedido_id = db.criar_uber_pedido(conn, origem, destino, disparar_em)
        conn.close()
        return pedido_id

    def _configurar_uber_conectado(self):
        conn = db.get_db()
        db.definir_configuracao(conn, "uber_access_token", "token-valido")
        db.definir_configuracao(conn, "uber_refresh_token", "refresh-valido")
        db.definir_configuracao(
            conn, "uber_token_expira_em", (datetime.now() + timedelta(hours=1)).isoformat()
        )
        conn.close()

    def test_verificar_dispara_estimativa_uber_e_notifica_preco(self):
        pedido_id = self._criar_uber_pedido_pronto_pra_disparar()
        self._configurar_uber_conectado()
        sub = {"endpoint": "https://exemplo.com/push/uber1", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Teste, 100"}), patch(
            "uber_client.configurado", return_value=True
        ), patch("maps_client.geocodificar", side_effect=[(-27.0, -49.0), (-27.1, -49.1)]), patch(
            "uber_client.produto_padrao", return_value="uberx-id"
        ), patch(
            "uber_client.estimar_corrida",
            return_value={"fare_id": "fare-123", "preco_texto": "R$32,50", "eta_minutos": 6},
        ), patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        corpo = mock_enviar.call_args[0][2]
        self.assertIn("R$32,50", corpo)

        conn = db.get_db()
        pedido = db.uber_pedido(conn, pedido_id)
        conn.close()
        self.assertEqual(pedido["status"], "aguardando_confirmacao")
        self.assertEqual(pedido["fare_id"], "fare-123")

    def test_verificar_uber_sem_token_nao_dispara(self):
        self._criar_uber_pedido_pronto_pra_disparar()
        sub = {"endpoint": "https://exemplo.com/push/uber2", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("uber_client.configurado", return_value=True), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")

        mock_enviar.assert_not_called()

    def test_verificar_uber_pedido_no_futuro_nao_dispara_ainda(self):
        conn = db.get_db()
        disparar_em = (datetime.now() + timedelta(minutes=15)).isoformat()
        pedido_id = db.criar_uber_pedido(conn, None, "Aeroporto", disparar_em)
        conn.close()
        self._configurar_uber_conectado()
        sub = {"endpoint": "https://exemplo.com/push/uber3", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("uber_client.configurado", return_value=True), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")

        mock_enviar.assert_not_called()
        conn = db.get_db()
        pedido = db.uber_pedido(conn, pedido_id)
        conn.close()
        self.assertEqual(pedido["status"], "aguardando")

    def test_verificar_uber_erro_de_geocodificacao_marca_pedido_com_erro(self):
        pedido_id = self._criar_uber_pedido_pronto_pra_disparar()
        self._configurar_uber_conectado()
        sub = {"endpoint": "https://exemplo.com/push/uber4", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Teste, 100"}), patch(
            "uber_client.configurado", return_value=True
        ), patch("maps_client.geocodificar", side_effect=ValueError("nao encontrei o endereco")), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")

        mock_enviar.assert_not_called()
        conn = db.get_db()
        pedido = db.uber_pedido(conn, pedido_id)
        conn.close()
        self.assertEqual(pedido["status"], "erro")

    def test_verificar_uber_sem_endereco_de_origem_marca_pedido_com_erro(self):
        pedido_id = self._criar_uber_pedido_pronto_pra_disparar()
        self._configurar_uber_conectado()
        sub = {"endpoint": "https://exemplo.com/push/uber5", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch.dict(os.environ, {"ENDERECO_CASA": ""}), patch(
            "uber_client.configurado", return_value=True
        ), patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")

        mock_enviar.assert_not_called()
        conn = db.get_db()
        pedido = db.uber_pedido(conn, pedido_id)
        conn.close()
        self.assertEqual(pedido["status"], "erro")

    def test_uber_pedidos_pendentes_lista_so_aguardando_confirmacao(self):
        conn = db.get_db()
        id_pronto = db.criar_uber_pedido(conn, None, "Aeroporto", datetime.now().isoformat())
        db.atualizar_uber_pedido(conn, id_pronto, status="aguardando_confirmacao", preco_texto="R$20")
        db.criar_uber_pedido(conn, None, "Shopping", datetime.now().isoformat())  # continua 'aguardando'
        conn.close()

        res = self.client.get("/api/uber/pedidos")
        pedidos = res.get_json()
        self.assertEqual(len(pedidos), 1)
        self.assertEqual(pedidos[0]["destino"], "Aeroporto")

    def test_uber_confirmar_pede_corrida_com_fare_id_travado(self):
        conn = db.get_db()
        pedido_id = db.criar_uber_pedido(conn, None, "Aeroporto", datetime.now().isoformat())
        db.atualizar_uber_pedido(
            conn,
            pedido_id,
            status="aguardando_confirmacao",
            origem_lat=-27.0,
            origem_lng=-49.0,
            destino_lat=-27.1,
            destino_lng=-49.1,
            product_id="uberx-id",
            fare_id="fare-123",
            preco_texto="R$32,50",
        )
        conn.close()
        self._configurar_uber_conectado()

        with patch(
            "uber_client.pedir_corrida",
            return_value={"request_id": "req-789", "status": "processing"},
        ) as mock_pedir:
            res = self.client.post(f"/api/uber/pedidos/{pedido_id}/confirmar")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["request_id"], "req-789")
        mock_pedir.assert_called_once_with(-27.0, -49.0, -27.1, -49.1, "uberx-id", "fare-123", "token-valido")

        conn = db.get_db()
        pedido = db.uber_pedido(conn, pedido_id)
        conn.close()
        self.assertEqual(pedido["status"], "confirmado")
        self.assertEqual(pedido["request_id"], "req-789")

    def test_uber_confirmar_pedido_ja_tratado_devolve_404(self):
        conn = db.get_db()
        pedido_id = db.criar_uber_pedido(conn, None, "Aeroporto", datetime.now().isoformat())
        db.atualizar_uber_pedido(conn, pedido_id, status="confirmado")
        conn.close()

        res = self.client.post(f"/api/uber/pedidos/{pedido_id}/confirmar")
        self.assertEqual(res.status_code, 404)

    def test_uber_confirmar_pedido_inexistente_devolve_404(self):
        res = self.client.post("/api/uber/pedidos/9999/confirmar")
        self.assertEqual(res.status_code, 404)

    def test_uber_cancelar_marca_status_cancelado(self):
        conn = db.get_db()
        pedido_id = db.criar_uber_pedido(conn, None, "Aeroporto", datetime.now().isoformat())
        db.atualizar_uber_pedido(conn, pedido_id, status="aguardando_confirmacao")
        conn.close()

        res = self.client.post(f"/api/uber/pedidos/{pedido_id}/cancelar")
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        pedido = db.uber_pedido(conn, pedido_id)
        conn.close()
        self.assertEqual(pedido["status"], "cancelado")

    def test_uber_conectar_sem_configurar_devolve_erro(self):
        with patch("uber_client.configurado", return_value=False):
            res = self.client.get("/uber/conectar")
        self.assertEqual(res.status_code, 400)

    def test_uber_conectar_redireciona_pra_autorizacao_da_uber(self):
        with patch.dict(os.environ, {"UBER_CLIENT_ID": "meu-id"}), patch(
            "uber_client.configurado", return_value=True
        ):
            res = self.client.get("/uber/conectar", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("login.uber.com", res.headers["Location"])

    def test_uber_callback_sem_codigo_devolve_erro(self):
        res = self.client.get("/uber/callback")
        self.assertEqual(res.status_code, 400)

    def test_uber_callback_com_erro_da_uber_devolve_erro(self):
        res = self.client.get("/uber/callback?error=access_denied")
        self.assertEqual(res.status_code, 400)

    def test_uber_callback_troca_codigo_e_guarda_token(self):
        dados = {"access_token": "novo-token", "refresh_token": "novo-refresh", "expires_in": 2592000}
        with patch("uber_client.trocar_codigo_por_token", return_value=dados) as mock_trocar:
            res = self.client.get("/uber/callback?code=codigo-abc")
        self.assertEqual(res.status_code, 200)
        mock_trocar.assert_called_once()
        self.assertEqual(mock_trocar.call_args[0][0], "codigo-abc")

        conn = db.get_db()
        self.assertEqual(db.obter_configuracao(conn, "uber_access_token"), "novo-token")
        self.assertEqual(db.obter_configuracao(conn, "uber_refresh_token"), "novo-refresh")
        conn.close()

    # ---- Rotina: hora de dormir, currency de voo, rotacao de estudo ----

    def test_verificar_notifica_hora_de_dormir(self):
        sub = {"endpoint": "https://exemplo.com/push/dormir1", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("notificacoes.hora_de_dormir_devida", return_value=True), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        self.assertIn("desacelerar", mock_enviar.call_args[0][2])

    def test_verificar_hora_de_dormir_ja_notificada_nao_repete(self):
        sub = {"endpoint": "https://exemplo.com/push/dormir2", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("notificacoes.hora_de_dormir_devida", return_value=True), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")
            res2 = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res2.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_called_once()

    def test_verificar_notifica_currency_de_voo_baixa(self):
        antigo = (date.today() - timedelta(days=25)).isoformat()
        self.client.post("/api/voos", json={"data": antigo, "destino": "Navegantes", "horas": 1.0})
        sub = {"endpoint": "https://exemplo.com/push/currency1", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        self.assertIn("25 dias", mock_enviar.call_args[0][2])

    def test_voos_resumo_inclui_dias_desde_ultimo_voo(self):
        antigo = (date.today() - timedelta(days=10)).isoformat()
        self.client.post("/api/voos", json={"data": antigo, "destino": "Navegantes", "horas": 1.0})
        res = self.client.get("/api/voos/resumo")
        self.assertEqual(res.get_json()["dias_desde_ultimo_voo"], 10)

    def test_voos_resumo_dias_desde_ultimo_voo_none_sem_voos(self):
        res = self.client.get("/api/voos/resumo")
        self.assertIsNone(res.get_json()["dias_desde_ultimo_voo"])

    def test_sugerir_tema_estudo_roda_em_rodizio(self):
        r1 = self._registrar_via_chat("sugerir_tema_estudo", {})
        r2 = self._registrar_via_chat("sugerir_tema_estudo", {})
        r3 = self._registrar_via_chat("sugerir_tema_estudo", {})
        r4 = self._registrar_via_chat("sugerir_tema_estudo", {})
        self.assertEqual(r1["tema"], "Regulamentacao (RBAC/RBHA)")
        self.assertEqual(r2["tema"], "Meteorologia aeronautica")
        self.assertEqual(r3["tema"], "Navegacao")
        self.assertEqual(r4["tema"], r1["tema"])  # completou a volta, recomeca

    def test_registrar_tarefa_depende_do_tempo_grava_flag(self):
        self._registrar_via_chat(
            "registrar_tarefa", {"titulo": "limpar o quarto", "depende_do_tempo": True}
        )
        conn = db.get_db()
        row = conn.execute("SELECT depende_do_tempo FROM tasks WHERE title = ?", ("limpar o quarto",)).fetchone()
        conn.close()
        self.assertEqual(row["depende_do_tempo"], 1)

    def test_registrar_tarefa_sem_depende_do_tempo_fica_zero(self):
        self._registrar_via_chat("registrar_tarefa", {"titulo": "responder corretora"})
        conn = db.get_db()
        row = conn.execute(
            "SELECT depende_do_tempo FROM tasks WHERE title = ?", ("responder corretora",)
        ).fetchone()
        conn.close()
        self.assertEqual(row["depende_do_tempo"], 0)

    def test_verificar_notifica_tarefa_com_dia_bom_de_tempo(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, depende_do_tempo) VALUES (?, 1)", ("limpar o quarto",)
        )
        conn.commit()
        conn.close()
        sub = {"endpoint": "https://exemplo.com/push/clima1", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        previsoes = [
            {"data": date.today().isoformat(), "chuva_pct": 10, "alerta_chuva": False},
        ]
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), patch(
            "clima.geocodificar_cidade", return_value={"lat": -27.0, "lon": -49.0, "nome": "Brusque"}
        ), patch("clima.previsao_proximos_dias", return_value=previsoes), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        self.assertIn("limpar o quarto", mock_enviar.call_args[0][2])

    def test_verificar_nao_notifica_tarefa_sem_cidade_padrao_configurada(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, depende_do_tempo) VALUES (?, 1)", ("limpar o quarto",)
        )
        conn.commit()
        conn.close()
        sub = {"endpoint": "https://exemplo.com/push/clima2", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch.dict(os.environ, {"CIDADE_PADRAO": ""}), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")

        mock_enviar.assert_not_called()

    def test_verificar_tarefa_clima_ja_notificada_nao_repete(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, depende_do_tempo) VALUES (?, 1)", ("limpar o quarto",)
        )
        conn.commit()
        conn.close()
        sub = {"endpoint": "https://exemplo.com/push/clima3", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        previsoes = [{"data": date.today().isoformat(), "chuva_pct": 10, "alerta_chuva": False}]
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), patch(
            "clima.geocodificar_cidade", return_value={"lat": -27.0, "lon": -49.0, "nome": "Brusque"}
        ), patch("clima.previsao_proximos_dias", return_value=previsoes), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")
            res2 = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res2.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_called_once()

    # ---- Cenario real: mensagem corrida de manha com varias coisas juntas ----
    # (o exemplo que o Alex deu: material de obra + gravar video na obra + voo
    # as 14h + gasto ja feito de gasolina + gasto planejado de reabastecer +
    # gasto planejado no cartao - tudo numa mensagem so). Mocka a API da
    # Anthropic no nivel mais baixo (client.messages.create), entao o loop de
    # tool-use de verdade (claude_client.chat) e os executores de verdade
    # (app.py) rodam - nao e so testar se o executor isolado funciona, e se o
    # pipeline inteiro (parsing simulado -> tools -> banco -> resumo) bate.
    def test_chat_mensagem_corrida_com_obra_voo_e_gastos_mistos(self):
        hoje = date.today().isoformat()
        resposta_com_tools = _resp(
            [
                _tool_block(
                    "registrar_tarefa",
                    {
                        "titulo": "comprar material (cimento, argamassa, porta) e pegar granito",
                        "quando_data": hoje,
                        "hora": "08:00",
                    },
                    id_="t1",
                ),
                _tool_block(
                    "registrar_tarefa",
                    {"titulo": "gravar video e tirar fotos da obra", "quando_data": hoje},
                    id_="t2",
                ),
                _tool_block(
                    "registrar_voo",
                    {"data": hoje, "destino": "Aeroporto", "hora": "14:00"},
                    id_="t3",
                ),
                _tool_block(
                    "registrar_gasto",
                    {"titulo": "gasolina", "valor": 100.0, "categoria": "transporte", "status": "real"},
                    id_="t4",
                ),
                _tool_block(
                    "registrar_gasto",
                    {
                        "titulo": "abastecer o carro de novo",
                        "valor": 100.0,
                        "categoria": "transporte",
                        "status": "planejado",
                    },
                    id_="t5",
                ),
                _tool_block(
                    "registrar_gasto",
                    {
                        "titulo": "compra no cartao de credito",
                        "valor": 300.0,
                        "categoria": "outros",
                        "status": "planejado",
                    },
                    id_="t6",
                ),
            ],
            stop_reason="tool_use",
        )
        resposta_final = _resp(
            [
                _text_block(
                    "-> Tarefa: material de obra (cimento, argamassa, porta, granito) as 08:00.\n"
                    "-> Tarefa: gravar video e fotos da obra.\n"
                    "-> Voo: hoje as 14:00 pro Aeroporto.\n"
                    "-> Gasto: R$100 de gasolina.\n"
                    "-> Gasto (planejado): R$100 pra reabastecer.\n"
                    "-> Gasto (planejado): R$300 no cartao."
                )
            ]
        )

        mensagem = (
            "hoje 8h da manha eu tenho que ir comprar material pras obras, cimento, "
            "argamassa, porta, depois pegar granito, daí tenho que ir na obra gravar "
            "um video e tirar fotos, vou almoçar e à tarde tenho voo as 14h, gastei "
            "100 de gasolina mas tenho que abastecer de novo, acho que vai mais 100, "
            "e penso em comprar algo de 300 no cartao de credito"
        )
        with patch.object(
            claude_client.client.messages, "create", side_effect=[resposta_com_tools, resposta_final]
        ):
            res = self.client.post("/api/chat", json={"mensagem": mensagem})
        self.assertEqual(res.status_code, 200)
        acoes = res.get_json()["acoes"]
        self.assertEqual(
            sorted(acoes),
            sorted(
                ["registrar_tarefa", "registrar_tarefa", "registrar_voo", "registrar_gasto",
                 "registrar_gasto", "registrar_gasto"]
            ),
        )

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 2)
        titulos_tarefas = {t["title"] for t in tasks}
        self.assertIn("comprar material (cimento, argamassa, porta) e pegar granito", titulos_tarefas)
        tarefa_com_hora = next(t for t in tasks if t["hora"])
        self.assertEqual(tarefa_com_hora["hora"], "08:00")

        voos = self.client.get("/api/voos").get_json()
        self.assertEqual(len(voos), 1)
        self.assertEqual(voos[0]["hora"], "14:00")
        self.assertEqual(voos[0]["destino"], "Aeroporto")

        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(expenses), 3)
        por_tipo = {"real": 0.0, "planejado": 0.0}
        for e in expenses:
            por_tipo[e["tipo"]] += e["amount"]
        self.assertEqual(por_tipo["real"], 100.0)
        self.assertEqual(por_tipo["planejado"], 400.0)

        with patch("claude_client.summarize_day", return_value=("Dia cheio.", fake_usage())):
            resumo = self.client.get("/api/summary/today").get_json()
        self.assertEqual(resumo["gasto_hoje"], 100.0)
        self.assertEqual(resumo["gasto_planejado"], 400.0)

    # ---- Cenario real: dump de domingo a noite com a semana inteira ----
    # (o exemplo que o Alex deu pra testar a notificacao de planejamento
    # semanal: 8 itens soltos numa mensagem so - duas cotacoes com
    # fornecedores, responder a corretora, viagem amanha cedo, um dia da
    # semana reservado pra contabilidade, o lembrete de anotar duvidas no
    # papel, o projeto do quarto (com condicao de umidade) e a visita ao
    # aeroclube (condicionada ao tempo). Verifica que CADA item vira uma
    # tarefa propria, sem nada ser perdido ou juntado errado, e que nada
    # ganha due_date quando so foi dito "essa semana"/"um dia da semana".
    def test_chat_dump_semanal_de_domingo_com_varios_itens_soltos(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        resposta_com_tools = _resp(
            [
                _tool_block(
                    "registrar_tarefa",
                    {"titulo": "Cotar 36 portas com pelo menos 5 fornecedores", "quando": "essa semana"},
                    id_="t1",
                ),
                _tool_block(
                    "registrar_tarefa",
                    {
                        "titulo": "Cotar 30 vasos sanitarios com pelo menos 5 fornecedores",
                        "quando": "essa semana",
                    },
                    id_="t2",
                ),
                _tool_block(
                    "registrar_tarefa",
                    {"titulo": "Responder a corretora sobre o terreno"},
                    id_="t3",
                ),
                _tool_block(
                    "registrar_tarefa",
                    {
                        "titulo": "Ir para Balneario Camboriu",
                        "quando": "amanha cedo",
                        "quando_data": amanha,
                    },
                    id_="t4",
                ),
                _tool_block(
                    "registrar_tarefa",
                    {
                        "titulo": "Tirar um dia pra ir na contabilidade tirar duvidas",
                        "quando": "essa semana",
                    },
                    id_="t5",
                ),
                _tool_block(
                    "registrar_tarefa",
                    {"titulo": "Anotar as duvidas no papel antes de ir na contabilidade"},
                    id_="t6",
                ),
                _tool_block(
                    "registrar_tarefa",
                    {
                        "titulo": (
                            "Arrumar o quarto: limpar (se a umidade baixar, depois de terminar as "
                            "tarefas do dia), deixar organizado, montar o PC e montar a prateleira"
                        ),
                    },
                    id_="t7",
                ),
                _tool_block(
                    "registrar_tarefa",
                    {
                        "titulo": (
                            "Visitar o Aeroclube pra ver o que mudou pra voltar aos voos "
                            "(se der tempo e nao chover)"
                        ),
                        "quando": "essa semana",
                    },
                    id_="t8",
                ),
            ],
            stop_reason="tool_use",
        )
        resposta_final = _resp(
            [
                _text_block(
                    "-> Tarefa: cotar 36 portas com 5 fornecedores.\n"
                    "-> Tarefa: cotar 30 vasos sanitarios com 5 fornecedores.\n"
                    "-> Tarefa: responder a corretora sobre o terreno.\n"
                    "-> Tarefa: Balneario Camboriu amanha cedo.\n"
                    "-> Tarefa: tirar um dia essa semana pra contabilidade.\n"
                    "-> Tarefa: anotar as duvidas no papel.\n"
                    "-> Tarefa: projeto do quarto (limpar, organizar, montar PC e prateleira).\n"
                    "-> Tarefa: visitar o Aeroclube essa semana."
                )
            ]
        )

        mensagem = (
            "hoje e domingo, essa semana eu preciso comprar porta pro meu predio, preciso "
            "cotar as portas com pelo menos 5 fornecedores, sao 36 portas, tambem preciso "
            "cotar vasos sanitarios, 30 unidades, com 5 fornecedores, preciso responder a "
            "corretora sobre o terreno que ela esta vendendo pra mim, amanha cedo eu tenho "
            "que ir pra balneario camboriu, essa semana eu quero tirar um dia pra ir na "
            "contabilidade tirar duvidas, minhas duvidas vou anotar no papel entao preciso "
            "ser lembrado disso, tambem preciso continuar limpando meu quarto, se a umidade "
            "baixar eu limpo depois de terminar minhas tarefas do dia, deixar ele organizado, "
            "montar meu pc depois de limpar, montar a prateleira, e num dia da semana quero ir "
            "no aeroclube dar uma visitada se der um tempo e nao chover"
        )
        with patch.object(
            claude_client.client.messages, "create", side_effect=[resposta_com_tools, resposta_final]
        ):
            res = self.client.post("/api/chat", json={"mensagem": mensagem})
        self.assertEqual(res.status_code, 200)
        acoes = res.get_json()["acoes"]
        self.assertEqual(acoes, ["registrar_tarefa"] * 8)

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 8)
        titulos = {t["title"] for t in tasks}
        self.assertIn("Cotar 36 portas com pelo menos 5 fornecedores", titulos)
        self.assertIn("Cotar 30 vasos sanitarios com pelo menos 5 fornecedores", titulos)
        self.assertIn("Responder a corretora sobre o terreno", titulos)
        self.assertIn("Anotar as duvidas no papel antes de ir na contabilidade", titulos)

        # so a viagem de amanha cedo tem due_date concreto - "essa semana" e
        # "um dia da semana" ficam sem data, so como texto em "quando"
        por_titulo = {t["title"]: t for t in tasks}
        self.assertEqual(por_titulo["Ir para Balneario Camboriu"]["due_date"], amanha)
        self.assertIsNone(
            por_titulo["Cotar 36 portas com pelo menos 5 fornecedores"]["due_date"]
        )
        self.assertIsNone(
            por_titulo["Tirar um dia pra ir na contabilidade tirar duvidas"]["due_date"]
        )

        tarefa_quarto = por_titulo[
            "Arrumar o quarto: limpar (se a umidade baixar, depois de terminar as "
            "tarefas do dia), deixar organizado, montar o PC e montar a prateleira"
        ]
        self.assertIn("umidade", tarefa_quarto["title"])

        tarefa_aeroclube = por_titulo[
            "Visitar o Aeroclube pra ver o que mudou pra voltar aos voos (se der tempo e nao chover)"
        ]
        self.assertIn("nao chover", tarefa_aeroclube["title"])

    # ---- Sugestao de melhor dia pra tarefa sem data fixa ----

    def _registrar_via_chat(self, nome_tool, entrada):
        """Roda o executor de verdade (app.py) sem precisar simular o loop
        completo de tool-use - mocka so claude_client.chat pra chamar o
        executor direto, igual aos testes de gasto real/planejado ja
        existentes."""
        captura = {}

        def fake_chat(mensagens, contexto, memorias, executores):
            captura["resultado"] = executores[nome_tool](entrada)
            return "Beleza.", [nome_tool], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "..."})
        return captura["resultado"]

    def test_registrar_tarefa_essa_semana_sugere_dia_menos_corrido(self):
        hoje = date.today()
        if hoje.weekday() == 6:
            self.skipTest("domingo e o ultimo dia da semana, nao ha o que sugerir")
        amanha = (hoje + timedelta(days=1)).isoformat()
        conn = db.get_db()
        for _ in range(3):
            conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("coisa", amanha))
        conn.commit()
        conn.close()

        resultado = self._registrar_via_chat(
            "registrar_tarefa", {"titulo": "cotar portas", "quando": "essa semana"}
        )
        self.assertIn("sugestao_dia", resultado)
        self.assertNotEqual(resultado["sugestao_dia"]["data"], amanha)
        self.assertEqual(resultado["sugestao_dia"]["carga"], 0)

    def test_registrar_tarefa_com_data_certa_nao_sugere_dia(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        resultado = self._registrar_via_chat(
            "registrar_tarefa", {"titulo": "ir pra BC", "quando": "amanha cedo", "quando_data": amanha}
        )
        self.assertNotIn("sugestao_dia", resultado)

    def test_registrar_tarefa_sem_quando_nao_sugere_dia(self):
        resultado = self._registrar_via_chat(
            "registrar_tarefa", {"titulo": "responder a corretora"}
        )
        self.assertNotIn("sugestao_dia", resultado)

    # ---- Sugestao de horario livre no dia ----

    def test_sugerir_horario_livre_considera_compromissos_reais_do_dia(self):
        hoje = date.today().isoformat()
        eventos_fake = [
            {"titulo": "Reuniao", "inicio": f"{hoje}T08:00:00", "fim": f"{hoje}T09:00:00", "dia_inteiro": False},
            {"titulo": "Jantar", "inicio": f"{hoje}T19:00:00", "fim": f"{hoje}T20:00:00", "dia_inteiro": False},
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ):
            resultado = self._registrar_via_chat("sugerir_horario_livre", {"duracao_minutos": 60})
        self.assertTrue(resultado["encontrado"])
        self.assertEqual(resultado["inicio"], "09:00")
        self.assertEqual(resultado["fim"], "19:00")

    def test_sugerir_horario_livre_respeita_depois_das(self):
        hoje = date.today().isoformat()
        eventos_fake = [
            {"titulo": "Reuniao", "inicio": f"{hoje}T08:00:00", "fim": f"{hoje}T09:00:00", "dia_inteiro": False}
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ):
            resultado = self._registrar_via_chat(
                "sugerir_horario_livre", {"duracao_minutos": 30, "depois_das": "18:00"}
            )
        self.assertEqual(resultado["inicio"], "18:00")

    def test_sugerir_horario_livre_dia_cheio_retorna_nao_encontrado(self):
        hoje = date.today().isoformat()
        eventos_fake = [
            {"titulo": "Trabalho", "inicio": f"{hoje}T06:00:00", "fim": f"{hoje}T22:00:00", "dia_inteiro": False}
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ):
            resultado = self._registrar_via_chat("sugerir_horario_livre", {"duracao_minutos": 30})
        self.assertFalse(resultado["encontrado"])

    # ---- Calculadora de viagem + combustivel ----

    def test_calcular_gasto_viagem_usa_distancia_real_do_maps(self):
        resultado_fake = {"duracao_minutos": 480, "distancia_km": 850.0}
        with patch("maps_client.configurado", return_value=True), patch(
            "maps_client.tempo_de_viagem", return_value=resultado_fake
        ):
            resultado = self._registrar_via_chat(
                "calcular_gasto_viagem",
                {"destino": "Foz do Iguacu", "origem": "Brusque", "km_por_litro": 16.0, "preco_por_litro": 6.0},
            )
        self.assertEqual(resultado["distancia_km"], 850.0)
        self.assertEqual(resultado["duracao_minutos"], 480)
        self.assertEqual(resultado["litros_gastos"], 53.1)
        self.assertEqual(resultado["custo_combustivel"], 318.75)

    def test_calcular_gasto_viagem_usa_endereco_padrao_quando_origem_omitida(self):
        resultado_fake = {"duracao_minutos": 10, "distancia_km": 5.0}
        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Teste, 100"}), patch(
            "maps_client.configurado", return_value=True
        ), patch("maps_client.tempo_de_viagem", return_value=resultado_fake) as mock_trajeto:
            self._registrar_via_chat(
                "calcular_gasto_viagem",
                {"destino": "mercado", "km_por_litro": 10.0, "preco_por_litro": 5.0},
            )
        mock_trajeto.assert_called_once_with("Rua Teste, 100", "mercado")

    def test_calcular_gasto_viagem_sem_origem_nem_padrao_devolve_erro(self):
        with patch.dict(os.environ, {"ENDERECO_CASA": ""}), patch(
            "maps_client.configurado", return_value=True
        ):
            resultado = self._registrar_via_chat(
                "calcular_gasto_viagem",
                {"destino": "mercado", "km_por_litro": 10.0, "preco_por_litro": 5.0},
            )
        self.assertIn("erro", resultado)

    def test_calcular_gasto_viagem_sem_maps_configurado_devolve_erro(self):
        with patch("maps_client.configurado", return_value=False):
            resultado = self._registrar_via_chat(
                "calcular_gasto_viagem",
                {"destino": "mercado", "km_por_litro": 10.0, "preco_por_litro": 5.0},
            )
        self.assertIn("erro", resultado)

    # ---- Sugestao de posto no meio do caminho ----

    def test_sugerir_posto_no_caminho_retorna_posto_encontrado(self):
        posto_fake = {"nome": "Posto Graal", "endereco": "BR-101, km 100"}
        with patch("maps_client.configurado", return_value=True), patch(
            "maps_client.posto_no_meio_do_caminho", return_value=posto_fake
        ):
            resultado = self._registrar_via_chat(
                "sugerir_posto_no_caminho", {"destino": "Foz do Iguacu", "origem": "Brusque"}
            )
        self.assertEqual(resultado["nome"], "Posto Graal")
        self.assertEqual(resultado["endereco"], "BR-101, km 100")

    def test_sugerir_posto_no_caminho_sem_resultado_devolve_erro(self):
        with patch("maps_client.configurado", return_value=True), patch(
            "maps_client.posto_no_meio_do_caminho", return_value=None
        ):
            resultado = self._registrar_via_chat(
                "sugerir_posto_no_caminho", {"destino": "Foz do Iguacu", "origem": "Brusque"}
            )
        self.assertIn("erro", resultado)

    def test_sugerir_posto_no_caminho_sem_maps_configurado_devolve_erro(self):
        with patch("maps_client.configurado", return_value=False):
            resultado = self._registrar_via_chat(
                "sugerir_posto_no_caminho", {"destino": "Foz do Iguacu", "origem": "Brusque"}
            )
        self.assertIn("erro", resultado)


class AutenticacaoTestCase(unittest.TestCase):
    """Testa o gate de autenticacao no nivel HTTP - cada teste comeca de um
    banco vazio (sem PIN configurado), diferente de PainelTestCase (que ja
    loga automaticamente pra nao atrapalhar os testes de feature)."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.client = app.app.test_client()

    def test_sem_pin_configurado_redireciona_pagina_pra_configurar(self):
        res = self.client.get("/", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/configurar-pin", res.headers["Location"])

    def test_sem_pin_configurado_api_devolve_401(self):
        res = self.client.get("/api/tasks")
        self.assertEqual(res.status_code, 401)

    def test_configurar_pin_com_sucesso_ja_autentica(self):
        res = self.client.post(
            "/configurar-pin", json={"pin": "111111", "confirmacao": "111111"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["ok"])

        # a sessao aberta pelo configurar-pin ja da acesso, sem precisar logar de novo
        res2 = self.client.get("/api/tasks")
        self.assertEqual(res2.status_code, 200)

    def test_configurar_pin_rejeita_formato_invalido(self):
        res = self.client.post("/configurar-pin", json={"pin": "123", "confirmacao": "123"})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(auth.pin_configurado(db.get_db()))

    def test_configurar_pin_ja_configurado_nao_deixa_reconfigurar(self):
        self.client.post("/configurar-pin", json={"pin": "111111", "confirmacao": "111111"})
        res = self.client.post("/configurar-pin", json={"pin": "222222", "confirmacao": "222222"})
        self.assertEqual(res.status_code, 400)

    def test_login_com_pin_certo_autentica(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()

        res = self.client.post("/login", json={"pin": "123456"})
        self.assertEqual(res.status_code, 200)

        res2 = self.client.get("/api/tasks")
        self.assertEqual(res2.status_code, 200)

    def test_login_com_pin_errado_nao_autentica(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()

        res = self.client.post("/login", json={"pin": "000000"})
        self.assertEqual(res.status_code, 401)

        res2 = self.client.get("/api/tasks")
        self.assertEqual(res2.status_code, 401)

    def test_cinco_pins_errados_bloqueia_ate_o_certo(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()

        for _ in range(5):
            self.client.post("/login", json={"pin": "000000"})

        # a sexta tentativa, mesmo com o PIN CERTO, e barrada pelo bloqueio
        res = self.client.post("/login", json={"pin": "123456"})
        self.assertEqual(res.status_code, 429)

        res2 = self.client.get("/api/tasks")
        self.assertEqual(res2.status_code, 401)

    def test_logout_derruba_a_sessao(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()
        self.client.post("/login", json={"pin": "123456"})

        res_logout = self.client.post("/logout")
        self.assertEqual(res_logout.status_code, 200)

        res = self.client.get("/api/tasks")
        self.assertEqual(res.status_code, 401)

    def test_saude_importar_nao_exige_sessao_de_login(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()
        # sem logar - so o SAUDE_WEBHOOK_TOKEN (checado dentro da propria rota)
        res = self.client.post("/api/saude/importar", json={"passos": 1000})
        self.assertNotEqual(res.status_code, 401)

    def test_login_ja_autenticado_redireciona_pra_home(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()
        self.client.post("/login", json={"pin": "123456"})

        res = self.client.get("/login", follow_redirects=False)
        self.assertEqual(res.status_code, 302)


class NormalizarHoraTestCase(unittest.TestCase):
    def test_zero_preenche_hora_e_minuto(self):
        self.assertEqual(app._normalizar_hora("9:5"), "09:05")
        self.assertEqual(app._normalizar_hora("9:05"), "09:05")
        self.assertEqual(app._normalizar_hora("09:05"), "09:05")

    def test_limites_validos(self):
        self.assertEqual(app._normalizar_hora("00:00"), "00:00")
        self.assertEqual(app._normalizar_hora("23:59"), "23:59")

    def test_entradas_invalidas_viram_none_sem_quebrar(self):
        invalidas = [
            None, "", "  ", "nao e hora", "25:00", "10:60", "-1:00", "10", "10:", ":30",
            "10:00:00", "manha", "14h", 1400, 14.5, [], {}, "10:aa", "aa:10",
        ]
        for valor in invalidas:
            with self.subTest(valor=valor):
                self.assertIsNone(app._normalizar_hora(valor))


if __name__ == "__main__":
    unittest.main()
