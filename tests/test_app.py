import io
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

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
        # a memoria do perfil inicial (nome, idade, profissao) e semeada em todo
        # banco novo - limpa aqui pra os testes de memoria ficarem isolados/previsiveis
        conn = db.get_db()
        conn.execute("DELETE FROM memorias")
        conn.commit()
        conn.close()
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
        self.assertEqual(args[1], eventos_fake)

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


if __name__ == "__main__":
    unittest.main()
