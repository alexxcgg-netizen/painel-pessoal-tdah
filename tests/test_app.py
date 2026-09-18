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


if __name__ == "__main__":
    unittest.main()
