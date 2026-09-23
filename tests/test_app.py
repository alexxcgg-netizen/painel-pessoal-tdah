import io
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import aprendizado
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
        # cache em memoria da integracao com a construtora (TTL 60s) - limpa entre
        # testes pra um teste nunca herdar a resposta mockada de outro
        app._CACHE_CONSTRUTORA.clear()
        self.client = app.app.test_client()
        # loga de verdade pelo fluxo real - assim toda a suite ja exercita o
        # gate de autenticacao (before_request) em vez de contornar ele
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()
        # "nunca silencioso" por padrao - sem isso, todo teste de
        # verificar_e_notificar ficaria dependente da hora real do relogio
        # (silencioso e 22:00-07:00 por padrao, mais de um terco do dia) e
        # falharia sempre que a suite rodasse dentro dessa janela. Testes que
        # querem testar o silencioso de verdade sobrescrevem isso com seu
        # proprio "with patch(...)" dentro do corpo do teste.
        self._silencio_patch = patch("notificacoes.dentro_do_horario_silencioso", return_value=False)
        self._silencio_patch.start()
        self.addCleanup(self._silencio_patch.stop)

    def test_smoke_pagina_principal_carrega(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        corpo = res.get_data(as_text=True)
        self.assertIn("<html", corpo.lower())
        self.assertIn("Painel Pessoal", corpo)

    def test_smoke_manifest_valido_e_icones_existem(self):
        res = self.client.get("/static/manifest.json")
        self.assertEqual(res.status_code, 200)
        manifest = json.loads(res.get_data(as_text=True))
        self.assertIn("icons", manifest)
        self.assertTrue(len(manifest["icons"]) > 0)
        for icone in manifest["icons"]:
            res_icone = self.client.get(icone["src"])
            self.assertEqual(
                res_icone.status_code, 200, f"icone {icone['src']} nao encontrado/servido"
            )

    def test_smoke_apple_touch_icon_existe(self):
        res = self.client.get("/static/icons/icon-180.png")
        self.assertEqual(res.status_code, 200)

    def test_smoke_service_worker_servido(self):
        res = self.client.get("/static/service-worker.js")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.get_data()), 0)

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

    def test_captura_com_client_id_reenviada_nao_duplica(self):
        """Fila offline (BRIEFING Fase 4, item 2): se a mesma captura for
        reenviada com o mesmo client_id (ex: a resposta da primeira tentativa
        se perdeu por queda de conexao, mas o servidor ja tinha processado),
        o segundo POST devolve a resposta ja gravada em vez de criar uma
        segunda tarefa/gasto."""
        parsed = {
            "tipo": "gasto",
            "titulo": "mercado",
            "valor": 50.0,
            "categoria": "mercado",
            "quando": None,
            "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())) as mock_classify:
            r1 = self.client.post(
                "/api/capture", json={"text": "gastei 50 no mercado", "client_id": "abc-123"}
            )
            self.assertEqual(r1.status_code, 201)
            r2 = self.client.post(
                "/api/capture", json={"text": "gastei 50 no mercado", "client_id": "abc-123"}
            )
            self.assertEqual(r2.status_code, 201)
            self.assertEqual(r1.get_json(), r2.get_json())
            # a IA so precisa ser chamada na primeira vez - o reenvio usa o cache
            mock_classify.assert_called_once()

        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(expenses), 1)

    def test_captura_sem_client_id_nao_usa_cache(self):
        """Sem client_id (uso normal, fora da fila offline) cada POST sempre
        processa e grava de novo - so a fila manda client_id."""
        parsed = {
            "tipo": "gasto", "titulo": "mercado", "valor": 50.0,
            "categoria": "mercado", "quando": None, "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "gastei 50 no mercado"})
            self.client.post("/api/capture", json={"text": "gastei 50 no mercado"})

        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(expenses), 2)

    def test_captura_client_id_diferente_nao_e_afetada(self):
        parsed = {
            "tipo": "gasto", "titulo": "mercado", "valor": 50.0,
            "categoria": "mercado", "quando": None, "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "gastei 50", "client_id": "id-1"})
            self.client.post("/api/capture", json={"text": "gastei 50 de novo", "client_id": "id-2"})

        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(expenses), 2)

    def test_checkin_reenviado_e_idempotente(self):
        """O check-in (BRIEFING Fase 4, item 2) e um upsert por dia - reenviar
        o mesmo POST (cenario de fila offline apos reconectar) nunca duplica
        nem quebra, so confirma o mesmo valor."""
        r1 = self.client.post("/api/checkin", json={"energia": "bom"})
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post("/api/checkin", json={"energia": "bom"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.get_json(), r2.get_json())

        hoje = self.client.get("/api/checkin/hoje").get_json()
        self.assertEqual(hoje["checkin"]["energia"], "bom")

    def test_exportar_csv_gastos_com_dados(self):
        parsed = {
            "tipo": "gasto", "titulo": "mercado", "valor": 50.0,
            "categoria": "mercado", "quando": None, "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            self.client.post("/api/capture", json={"text": "gastei 50 no mercado"})

        res = self.client.get("/api/expenses/exportar-csv")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "text/csv")
        self.assertIn("attachment", res.headers["Content-Disposition"])
        corpo = res.get_data(as_text=True)
        linhas = corpo.strip().split("\r\n")
        self.assertEqual(linhas[0], "data,valor,categoria,tipo,descricao")
        self.assertEqual(len(linhas), 2)
        self.assertIn("50.0", linhas[1])
        self.assertIn("mercado", linhas[1])

    def test_exportar_csv_gastos_vazio_ainda_devolve_cabecalho(self):
        res = self.client.get("/api/expenses/exportar-csv")
        self.assertEqual(res.status_code, 200)
        corpo = res.get_data(as_text=True)
        self.assertEqual(corpo.strip(), "data,valor,categoria,tipo,descricao")

    def test_exportar_csv_gastos_exige_autenticacao(self):
        self.client.post("/logout")
        res = self.client.get("/api/expenses/exportar-csv")
        self.assertEqual(res.status_code, 401)

    def test_exportar_backup_devolve_banco_sqlite_valido(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('tarefa pro backup')")
        conn.commit()
        conn.close()

        res = self.client.get("/api/backup/exportar")
        self.assertEqual(res.status_code, 200)
        self.assertIn("attachment", res.headers["Content-Disposition"])
        self.assertIn(".db", res.headers["Content-Disposition"])

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            tmp.write(res.get_data())
            tmp.flush()
            conn_verificacao = sqlite3.connect(tmp.name)
            titulo = conn_verificacao.execute("SELECT title FROM tasks").fetchone()[0]
            conn_verificacao.close()
        self.assertEqual(titulo, "tarefa pro backup")

    def test_exportar_backup_exige_autenticacao(self):
        self.client.post("/logout")
        res = self.client.get("/api/backup/exportar")
        self.assertEqual(res.status_code, 401)

    def test_exportar_backup_json_lista_tabelas_bate_com_schema(self):
        conn = db.get_db()
        tabelas_schema = set(app._listar_tabelas(conn))
        conn.close()

        res = self.client.get("/api/backup/exportar-json")
        self.assertEqual(res.status_code, 200)
        corpo = res.get_json()
        self.assertEqual(set(corpo["tabelas"].keys()), tabelas_schema)
        # nao pode ficar hardcoded vazio/curto demais - regressao contra um
        # bug onde a introspeccao devolvesse lista errada
        self.assertGreater(len(tabelas_schema), 30)

    def test_exportar_backup_json_estrutura_e_dados(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('tarefa pro export json')")
        conn.commit()
        conn.close()

        res = self.client.get("/api/backup/exportar-json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/json")
        self.assertIn("attachment", res.headers["Content-Disposition"])
        corpo = res.get_json()
        self.assertIn("versao", corpo)
        self.assertIn("exportado_em", corpo)
        self.assertIn("tabelas", corpo)
        titulos = [t["title"] for t in corpo["tabelas"]["tasks"]]
        self.assertIn("tarefa pro export json", titulos)

    def test_exportar_backup_json_exige_autenticacao(self):
        self.client.post("/logout")
        res = self.client.get("/api/backup/exportar-json")
        self.assertEqual(res.status_code, 401)

    def test_exportar_backup_csv_completo_abre_e_tem_uma_tabela_por_arquivo(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('tarefa pro zip')")
        conn.commit()
        tabelas_schema = set(app._listar_tabelas(conn))
        conn.close()

        res = self.client.get("/api/backup/exportar-csv-completo")
        self.assertEqual(res.status_code, 200)
        self.assertIn("attachment", res.headers["Content-Disposition"])
        self.assertIn(".zip", res.headers["Content-Disposition"])

        with zipfile.ZipFile(io.BytesIO(res.get_data())) as zf:
            nomes = set(zf.namelist())
            self.assertEqual(nomes, {f"{t}.csv" for t in tabelas_schema})
            conteudo_tasks = zf.read("tasks.csv").decode("utf-8")
            linhas = conteudo_tasks.strip().split("\r\n")
            self.assertIn("title", linhas[0].split(","))
            self.assertTrue(any("tarefa pro zip" in linha for linha in linhas[1:]))

    def test_exportar_backup_csv_completo_exige_autenticacao(self):
        self.client.post("/logout")
        res = self.client.get("/api/backup/exportar-csv-completo")
        self.assertEqual(res.status_code, 401)

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

    def test_list_tasks_agrupa_subtarefas_por_task_sem_misturar(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('lavar o carro')")
        conn.execute("INSERT INTO tasks (title) VALUES ('estudar meteorologia')")
        task_a, task_b = [r["id"] for r in conn.execute("SELECT id FROM tasks ORDER BY id").fetchall()]
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, 'lavar externo', 0)", (task_a,)
        )
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, 'aspirar interno', 1)", (task_a,)
        )
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, 'ler apostila', 0)", (task_b,)
        )
        conn.commit()
        conn.close()

        tasks = self.client.get("/api/tasks").get_json()
        por_id = {t["id"]: t for t in tasks}
        self.assertEqual([s["title"] for s in por_id[task_a]["subtasks"]], ["lavar externo", "aspirar interno"])
        self.assertEqual([s["title"] for s in por_id[task_b]["subtasks"]], ["ler apostila"])

    def test_list_tasks_sem_nenhuma_task_nao_quebra(self):
        res = self.client.get("/api/tasks")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), [])

    def test_tarefa_modelo_recorrente_nunca_aparece_diretamente_na_lista(self):
        # "diaria" bate hoje, entao a INSTANCIA materializada aparece - so o
        # MODELO em si (due_date NULL, recorrencia preenchida) nunca deve
        # aparecer como se fosse uma tarefa de verdade.
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, recorrencia) VALUES (?, ?)", ("Tomar remedio", "diaria")
        )
        conn.commit()
        modelo_id = conn.execute("SELECT id FROM tasks WHERE recorrencia = 'diaria'").fetchone()["id"]
        conn.close()

        tasks = self.client.get("/api/tasks").get_json()
        ids = [t["id"] for t in tasks]
        self.assertNotIn(modelo_id, ids)
        self.assertTrue(all(t["recorrencia"] is None for t in tasks))

    def test_get_tasks_materializa_instancia_de_tarefa_diaria(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, hora, recorrencia) VALUES (?, ?, ?)",
            ("Tomar remedio", "08:00", "diaria"),
        )
        conn.commit()
        conn.close()

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "Tomar remedio")
        self.assertEqual(tasks[0]["due_date"], date.today().isoformat())
        self.assertEqual(tasks[0]["hora"], "08:00")

    def test_get_tasks_nao_duplica_instancia_ja_materializada(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, recorrencia) VALUES (?, ?)", ("Tomar remedio", "diaria"))
        conn.commit()
        conn.close()

        self.client.get("/api/tasks")
        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 1)

    def test_tarefa_semanal_so_materializa_no_dia_certo(self):
        hoje = date.today()
        outro_dia = (hoje.weekday() + 1) % 7
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, recorrencia) VALUES (?, ?)",
            ("Academia", f"semanal:{outro_dia}"),
        )
        conn.commit()
        conn.close()

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(tasks, [])

    def test_completar_instancia_de_recorrente_nao_apaga_o_modelo(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, recorrencia) VALUES (?, ?)", ("Tomar remedio", "diaria"))
        conn.commit()
        conn.close()

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 1)
        self.client.post(f"/api/tasks/{tasks[0]['id']}/complete")

        conn = db.get_db()
        modelo = conn.execute(
            "SELECT completed_at FROM tasks WHERE recorrencia = 'diaria'"
        ).fetchone()
        conn.close()
        self.assertIsNone(modelo["completed_at"])
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])

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

    def test_construtora_resumo_inclui_contas_a_vencer(self):
        def fake_get(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            if url.endswith("/api/resumo"):
                resp.json.return_value = {
                    "status": "ok",
                    "tot_entradas": 100000.0,
                    "tot_saidas": 40000.0,
                    "lucro_liquido": 60000.0,
                    "margem": 60.0,
                }
            else:
                resp.json.return_value = {
                    "status": "ok",
                    "contas": [
                        {
                            "vencimento": "2026-10-01",
                            "valor": 500.0,
                            "fornecedor": "Fornecedor X",
                            "descricao": "",
                            "dias_ate_vencer": 5,
                        }
                    ],
                }
            return resp

        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", side_effect=fake_get):
            res = self.client.get("/api/construtora/resumo")

        body = res.get_json()
        self.assertTrue(body["configurado"])
        self.assertEqual(len(body["contas"]), 1)
        self.assertEqual(body["contas"][0]["fornecedor"], "Fornecedor X")

    def test_construtora_resumo_contas_none_se_endpoint_de_contas_falhar(self):
        def fake_get(url, headers=None, params=None, timeout=None):
            if url.endswith("/api/resumo"):
                resp = MagicMock()
                resp.raise_for_status = lambda: None
                resp.json.return_value = {
                    "status": "ok", "tot_entradas": 1.0, "tot_saidas": 1.0,
                    "lucro_liquido": 0.0, "margem": 0.0,
                }
                return resp
            raise requests.RequestException("fora do ar")

        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", side_effect=fake_get):
            res = self.client.get("/api/construtora/resumo")

        self.assertIsNone(res.get_json()["contas"])

    def test_construtora_resumo_cacheado_nao_bate_de_novo_na_api_externa(self):
        resposta_fake = MagicMock()
        resposta_fake.raise_for_status = lambda: None
        resposta_fake.json.return_value = {
            "status": "ok", "tot_entradas": 1.0, "tot_saidas": 1.0,
            "lucro_liquido": 0.0, "margem": 0.0,
        }
        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", return_value=resposta_fake) as mock_get:
            self.client.get("/api/construtora/resumo")
            chamadas_apos_primeira = mock_get.call_count
            self.client.get("/api/construtora/resumo")
            chamadas_apos_segunda = mock_get.call_count

        self.assertEqual(chamadas_apos_primeira, chamadas_apos_segunda)

    def test_construtora_cache_nao_mistura_dias_diferentes(self):
        chamadas = []

        def fake_get(url, headers=None, params=None, timeout=None):
            chamadas.append(dict(params or {}))
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            if url.endswith("/api/resumo"):
                resp.json.return_value = {"status": "ok", "tot_entradas": 1.0, "tot_saidas": 1.0, "lucro_liquido": 0.0, "margem": 0.0}
            else:
                resp.json.return_value = {"status": "ok", "contas": []}
            return resp

        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", side_effect=fake_get):
            app._buscar_contas_a_vencer_construtora(dias=30)
            app._buscar_contas_a_vencer_construtora(dias=7)

        dias_pedidos = [c.get("dias") for c in chamadas]
        self.assertIn(30, dias_pedidos)
        self.assertIn(7, dias_pedidos)

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

    def test_importar_extrato_categoriza_sozinho_com_historico_claro(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO expenses (amount, category, description) VALUES (?, ?, ?)",
            (18.0, "mercado", "compra na padaria central de manha"),
        )
        conn.execute(
            "INSERT INTO expenses (amount, category, description) VALUES (?, ?, ?)",
            (12.5, "mercado", "pao na padaria central"),
        )
        conn.commit()
        conn.close()

        self.client.post(
            "/api/bancos/importar",
            data={
                "banco": "nubank",
                "arquivo": (io.BytesIO(OFX_AMOSTRA.encode()), "extrato.ofx"),
            },
            content_type="multipart/form-data",
        )
        contas = self.client.get("/api/bancos").get_json()
        transacoes = self.client.get(f"/api/bancos/{contas[0]['id']}/transacoes").get_json()

        padaria = next(t for t in transacoes if t["valor"] == -45.9)
        self.assertEqual(padaria["categoria"], "mercado")

        # SALARIO nao tem nada parecido no historico - fica sem categoria em
        # vez de arriscar um palpite
        salario = next(t for t in transacoes if t["valor"] == 1500.0)
        self.assertIsNone(salario["categoria"])

    def test_importar_extrato_sem_historico_fica_sem_categoria(self):
        self.client.post(
            "/api/bancos/importar",
            data={
                "banco": "nubank",
                "arquivo": (io.BytesIO(OFX_AMOSTRA.encode()), "extrato.ofx"),
            },
            content_type="multipart/form-data",
        )
        contas = self.client.get("/api/bancos").get_json()
        transacoes = self.client.get(f"/api/bancos/{contas[0]['id']}/transacoes").get_json()
        self.assertTrue(all(t["categoria"] is None for t in transacoes))

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
        dias_esperados = (date.fromisoformat(prazo_iso) - hoje).days
        self.assertEqual(meta["dias_restantes"], dias_esperados)

    def test_meta_sem_prazo_dias_restantes_none(self):
        conn = db.get_db()
        goal_id = db.create_goal(conn, "sem prazo", 500.0, None)
        conn.close()
        metas = self.client.get("/api/metas").get_json()
        meta = next(m for m in metas if m["id"] == goal_id)
        self.assertIsNone(meta["dias_restantes"])
        self.assertIsNone(meta["meses_restantes"])

    def test_meta_com_prazo_vencido_dias_restantes_negativo(self):
        prazo_passado = (date.today() - timedelta(days=10)).isoformat()
        conn = db.get_db()
        goal_id = db.create_goal(conn, "atrasada", 500.0, prazo_passado)
        conn.close()
        metas = self.client.get("/api/metas").get_json()
        meta = next(m for m in metas if m["id"] == goal_id)
        self.assertEqual(meta["dias_restantes"], -10)

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

    def test_calendario_hoje_marca_tarefa_concluida(self):
        # A agenda precisa MOSTRAR a tarefa concluida (bolinha verde, pedido do
        # Alex) - so quem NAO pode ver isso e o plano do dia/notificacoes, que
        # usam _tarefas_com_horario_hoje (so pendentes) em vez desta rota.
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, datetime('now'))",
            ("consulta ja feita", hoje, "09:00"),
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/calendario/hoje")
        eventos = res.get_json()["eventos"]
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["titulo"], "consulta ja feita")
        self.assertTrue(eventos[0]["concluido"])

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

    def test_init_db_cria_indices_esperados_e_e_idempotente(self):
        tmp = tempfile.TemporaryDirectory()
        caminho_original = db.DB_PATH
        db.DB_PATH = Path(tmp.name) / "painel.db"
        try:
            db.init_db()
            db.init_db()  # roda 2x - nao pode dar erro (CREATE INDEX IF NOT EXISTS)
            conn = db.get_db()
            indices = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
                ).fetchall()
            }
            conn.close()
            esperados = {
                "idx_tasks_completed_at",
                "idx_tasks_due_date",
                "idx_subtasks_task_id",
                "idx_expenses_created_at",
                "idx_expenses_tipo",
                "idx_bank_transactions_bank_account_id",
                "idx_goal_deposits_goal_id",
                "idx_cotacoes_itens_cotacao_id",
                "idx_voos_data",
            }
            self.assertTrue(esperados.issubset(indices), f"faltando: {esperados - indices}")
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

    def test_hidratacao_comeca_zerada_e_incrementa(self):
        dados_inicial = self.client.get("/api/saude/hoje").get_json()
        self.assertEqual(dados_inicial["hidratacao_hoje"], 0)

        res = self.client.post("/api/hidratacao")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["total_hoje"], 1)

        self.client.post("/api/hidratacao")
        dados_depois = self.client.get("/api/saude/hoje").get_json()
        self.assertEqual(dados_depois["hidratacao_hoje"], 2)

    def test_dica_sono_null_sem_dado_suficiente(self):
        dados = self.client.get("/api/saude/hoje").get_json()
        self.assertIsNone(dados["dica_sono"])

    def test_medidas_lista_vazia(self):
        self.assertEqual(self.client.get("/api/medidas").get_json(), [])

    def test_criar_medida_peso_usa_kg_por_padrao(self):
        res = self.client.post("/api/medidas", json={"tipo": "peso", "valor": 82.5})
        self.assertEqual(res.status_code, 201)

        medidas = self.client.get("/api/medidas").get_json()
        self.assertEqual(len(medidas), 1)
        self.assertEqual(medidas[0]["tipo"], "peso")
        self.assertEqual(medidas[0]["valor"], 82.5)
        self.assertEqual(medidas[0]["unidade"], "kg")

    def test_criar_medida_nao_peso_usa_cm_por_padrao(self):
        res = self.client.post("/api/medidas", json={"tipo": "biceps", "valor": 38})
        self.assertEqual(res.status_code, 201)
        medidas = self.client.get("/api/medidas").get_json()
        self.assertEqual(medidas[0]["unidade"], "cm")

    def test_criar_medida_com_unidade_customizada(self):
        self.client.post("/api/medidas", json={"tipo": "peso", "valor": 180, "unidade": "lb"})
        medidas = self.client.get("/api/medidas").get_json()
        self.assertEqual(medidas[0]["unidade"], "lb")

    def test_medidas_filtra_por_tipo(self):
        self.client.post("/api/medidas", json={"tipo": "peso", "valor": 82})
        self.client.post("/api/medidas", json={"tipo": "biceps", "valor": 38})
        medidas = self.client.get("/api/medidas?tipo=peso").get_json()
        self.assertEqual(len(medidas), 1)
        self.assertEqual(medidas[0]["tipo"], "peso")

    def test_criar_medida_sem_tipo_rejeita(self):
        res = self.client.post("/api/medidas", json={"tipo": "  ", "valor": 82})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get("/api/medidas").get_json(), [])

    def test_criar_medida_valor_invalido_rejeita(self):
        for valor_ruim in ["oitenta", None, "", []]:
            res = self.client.post("/api/medidas", json={"tipo": "peso", "valor": valor_ruim})
            self.assertEqual(res.status_code, 400, msg=f"deveria rejeitar valor={valor_ruim!r}")
        self.assertEqual(self.client.get("/api/medidas").get_json(), [])

    def test_criar_medida_data_invalida_rejeita(self):
        res = self.client.post("/api/medidas", json={"tipo": "peso", "valor": 80, "data": "ontem"})
        self.assertEqual(res.status_code, 400)

    def test_apagar_medida_remove_da_lista(self):
        res = self.client.post("/api/medidas", json={"tipo": "peso", "valor": 82})
        medida_id = res.get_json()["medida_id"]
        res_delete = self.client.delete(f"/api/medidas/{medida_id}")
        self.assertEqual(res_delete.status_code, 200)
        self.assertEqual(self.client.get("/api/medidas").get_json(), [])

    def test_chat_usa_executor_de_hidratacao_de_verdade(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_hidratacao"]({})
            self.assertEqual(resultado["ok"], True)
            return "Anotado, +1 copo.", ["registrar_hidratacao"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "bebi agua"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/saude/hoje").get_json()["hidratacao_hoje"], 1)

    def test_chat_usa_executor_de_medida_de_verdade(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_medida"]({"tipo": "peso", "valor": 81.2})
            self.assertEqual(resultado["ok"], True)
            return "Anotado, 81.2kg.", ["registrar_medida"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "hoje to com 81.2kg"})
        self.assertEqual(res.status_code, 200)
        medidas = self.client.get("/api/medidas").get_json()
        self.assertEqual(medidas[0]["tipo"], "peso")
        self.assertEqual(medidas[0]["valor"], 81.2)

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

    def test_chat_registrar_tarefa_diaria_vira_modelo_e_materializa_hoje(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_tarefa"](
                {"titulo": "Tomar remedio", "hora": "08:00", "recorrencia": "diaria"}
            )
            self.assertEqual(resultado, {"ok": True, "recorrente": True})
            return "Beleza, vou te lembrar todo dia.", ["registrar_tarefa"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "tenho que tomar remedio todo dia as 8h"})
        self.assertEqual(res.status_code, 200)

        tarefas = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tarefas), 1)
        self.assertEqual(tarefas[0]["title"], "Tomar remedio")
        self.assertEqual(tarefas[0]["due_date"], date.today().isoformat())

        conn = db.get_db()
        modelos = conn.execute("SELECT * FROM tasks WHERE recorrencia = 'diaria'").fetchall()
        conn.close()
        self.assertEqual(len(modelos), 1)
        self.assertIsNone(modelos[0]["due_date"])

    def test_chat_registrar_tarefa_recorrencia_malformada_devolve_erro(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_tarefa"](
                {"titulo": "Academia", "recorrencia": "toda terca"}
            )
            self.assertIn("erro", resultado)
            return "Nao entendi essa rotina.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "academia toda terca"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])

    def test_chat_distribuir_tarefas_na_semana_so_propoe_nao_cria_ainda(self):
        # Pedido explicito do Alex: "eu digo se vai dar ou nao" - a proposta
        # em si NUNCA pode criar tarefa nenhuma sozinha.
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["distribuir_tarefas_na_semana"](
                {"titulos": ["lavar o carro", "estudar meteorologia", "cotar portas"]}
            )
            self.assertTrue(resultado["ok"])
            self.assertEqual(len(resultado["propostas"]), 3)
            return "Aqui esta o plano da semana.", ["distribuir_tarefas_na_semana"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "domingo: lavar o carro, estudar, cotar portas"})
        self.assertEqual(res.status_code, 200)

        tarefas = self.client.get("/api/tasks").get_json()
        self.assertEqual(tarefas, [])

        conn = db.get_db()
        pendente = db.obter_configuracao(conn, "plano_semana_pendente")
        conn.close()
        self.assertTrue(pendente)
        self.assertEqual(len(json.loads(pendente)), 3)

    def test_chat_distribuir_tarefas_sem_titulo_da_erro_pro_modelo(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["distribuir_tarefas_na_semana"]({"titulos": []})
            self.assertIn("erro", resultado)
            return "Nao entendi quais tarefas.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "distribui minhas tarefas"})
        self.assertEqual(res.status_code, 200)

    def test_chat_confirmar_plano_semana_cria_as_tarefas(self):
        def fake_propor(mensagens, contexto, memorias, executores):
            executores["distribuir_tarefas_na_semana"]({"titulos": ["lavar o carro", "estudar"]})
            return "Plano proposto.", ["distribuir_tarefas_na_semana"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_propor):
            self.client.post("/api/chat", json={"mensagem": "domingo: lavar o carro, estudar"})

        def fake_confirmar(mensagens, contexto, memorias, executores):
            resultado = executores["confirmar_plano_semana"]({})
            self.assertTrue(resultado["ok"])
            self.assertEqual(resultado["quantidade"], 2)
            return "Prontinho, criei as duas.", ["confirmar_plano_semana"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_confirmar):
            res = self.client.post("/api/chat", json={"mensagem": "pode, ta bom"})
        self.assertEqual(res.status_code, 200)

        tarefas = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tarefas), 2)
        titulos = {t["title"] for t in tarefas}
        self.assertEqual(titulos, {"lavar o carro", "estudar"})

        conn = db.get_db()
        pendente = db.obter_configuracao(conn, "plano_semana_pendente")
        conn.close()
        self.assertFalse(pendente)

    def test_chat_confirmar_plano_semana_sem_proposta_pendente_da_erro(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["confirmar_plano_semana"]({})
            self.assertIn("erro", resultado)
            return "Nao tem nada pendente.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "pode confirmar"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])

    def test_chat_cancelar_plano_semana_descarta_sem_criar(self):
        def fake_propor(mensagens, contexto, memorias, executores):
            executores["distribuir_tarefas_na_semana"]({"titulos": ["lavar o carro"]})
            return "Plano proposto.", ["distribuir_tarefas_na_semana"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_propor):
            self.client.post("/api/chat", json={"mensagem": "domingo: lavar o carro"})

        def fake_cancelar(mensagens, contexto, memorias, executores):
            resultado = executores["cancelar_plano_semana"]({})
            self.assertTrue(resultado["ok"])
            return "Esqueci o plano.", ["cancelar_plano_semana"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_cancelar):
            res = self.client.post("/api/chat", json={"mensagem": "deixa quieto"})
        self.assertEqual(res.status_code, 200)

        self.assertEqual(self.client.get("/api/tasks").get_json(), [])
        conn = db.get_db()
        pendente = db.obter_configuracao(conn, "plano_semana_pendente")
        conn.close()
        self.assertFalse(pendente)

    def test_chat_contexto_menciona_plano_semana_pendente(self):
        conn = db.get_db()
        db.definir_configuracao(
            conn,
            "plano_semana_pendente",
            json.dumps([{"titulo": "lavar o carro", "dia": "2026-09-23", "hora": "09:00"}]),
        )
        conn.close()

        contexto_capturado = {}

        def fake_chat(mensagens, contexto, memorias, executores):
            contexto_capturado["valor"] = contexto
            return "Ok.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "oi"})

        self.assertIn("lavar o carro", contexto_capturado["valor"])
        self.assertIn("aguardando", contexto_capturado["valor"].lower())

    def test_chat_sugerir_tarefa_para_agora_adianta_tarefa_futura(self):
        depois_de_amanha = (date.today() + timedelta(days=2)).isoformat()
        amanha = (date.today() + timedelta(days=1)).isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("evento depois de amanha", depois_de_amanha)
        )
        conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("limpar o quarto", amanha))
        conn.commit()
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["sugerir_tarefa_para_agora"]({})
            self.assertTrue(resultado["encontrada"])
            self.assertEqual(resultado["tipo"], "adiantada")
            self.assertEqual(resultado["titulo"], "limpar o quarto")
            self.assertEqual(resultado["dia_original"], amanha)
            return "Que tal adiantar isso?", ["sugerir_tarefa_para_agora"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "nao to fazendo nada agora"})
        self.assertEqual(res.status_code, 200)

    def test_chat_sugerir_tarefa_para_agora_sem_data_marcada_oferece_solta(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES (?)", ("responder a corretora",))
        conn.commit()
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["sugerir_tarefa_para_agora"]({})
            self.assertTrue(resultado["encontrada"])
            self.assertEqual(resultado["tipo"], "solta")
            self.assertEqual(resultado["titulo"], "responder a corretora")
            return "Que tal fazer isso agora?", ["sugerir_tarefa_para_agora"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "to sem nada pra fazer"})
        self.assertEqual(res.status_code, 200)

    def test_chat_sugerir_tarefa_para_agora_sem_nenhuma_pendente(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["sugerir_tarefa_para_agora"]({})
            self.assertEqual(resultado, {"encontrada": False})
            return "Nada pendente - aproveita pra descansar.", ["sugerir_tarefa_para_agora"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "to livre agora, que faco?"})
        self.assertEqual(res.status_code, 200)

    def test_chat_sugerir_tarefa_para_agora_ignora_tarefa_de_hoje_e_concluida(self):
        hoje = date.today().isoformat()
        amanha = (date.today() + timedelta(days=1)).isoformat()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("tarefa de hoje", hoje))
        conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, datetime('now'))",
            ("tarefa de amanha ja feita", amanha),
        )
        conn.commit()
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["sugerir_tarefa_para_agora"]({})
            # nenhuma tarefa FUTURA pendente (a de amanha ja foi concluida, a
            # de hoje nao conta como "adiantavel") - cai pro fallback de
            # tarefa solta, mas nao ha nenhuma tarefa solta tambem
            self.assertEqual(resultado, {"encontrada": False})
            return "Nada pra adiantar agora.", ["sugerir_tarefa_para_agora"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "to sem nada pra fazer"})
        self.assertEqual(res.status_code, 200)

    def test_notificacoes_verificar_agora_sem_push_configurado(self):
        res = self.client.post("/api/notificacoes/verificar-agora")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["avisos_enviados"], 0)

    def test_notificacoes_verificar_agora_envia_so_por_telegram_sem_push(self):
        """Nao precisa de nenhuma inscricao push pra funcionar - o Telegram
        sozinho ja basta como canal."""
        ontem = (date.today() - timedelta(days=1)).isoformat()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta", ontem))
        conn.commit()
        conn.close()

        with patch("push_client.configurado", return_value=False), patch(
            "telegram_bot.configurado", return_value=True
        ), patch("telegram_bot.enviar_mensagem", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        self.assertIn("tarefa atrasada", mock_enviar.call_args[0][0])

    def test_notificacoes_verificar_agora_manda_pelos_dois_canais(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta", ontem))
        conn.commit()
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_push, patch("telegram_bot.configurado", return_value=True), patch(
            "telegram_bot.enviar_mensagem", return_value=True
        ) as mock_telegram:
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_push.assert_called_once()
        mock_telegram.assert_called_once()

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

    def test_notificacoes_verificar_agora_avisa_compromisso_calendario_chegando(self):
        # Pedido explicito do Alex (TDAH): "se eu marquei alguma coisa na
        # agenda, daqui 10 minutos ja me avisa" - compromisso do iCloud
        # dentro da janela de heads-up precisa virar aviso, nao so a tarefa.
        inicio = (datetime.now() + timedelta(minutes=5)).isoformat()
        eventos_fake = [
            {"titulo": "Reuniao com fornecedor", "inicio": inicio, "fim": inicio, "dia_inteiro": False}
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ), patch("push_client.configurado", return_value=False), patch(
            "telegram_bot.configurado", return_value=True
        ), patch("telegram_bot.enviar_mensagem", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        self.assertIn("Reuniao com fornecedor", mock_enviar.call_args[0][0])

    def test_notificacoes_verificar_agora_ignora_compromisso_calendario_longe(self):
        inicio = (datetime.now() + timedelta(hours=3)).isoformat()
        eventos_fake = [
            {"titulo": "Reuniao distante", "inicio": inicio, "fim": inicio, "dia_inteiro": False}
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ), patch("push_client.configurado", return_value=False), patch(
            "telegram_bot.configurado", return_value=True
        ), patch("telegram_bot.enviar_mensagem", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_not_called()

    def test_notificacoes_verificar_agora_ignora_compromisso_dia_inteiro(self):
        eventos_fake = [
            {
                "titulo": "Feriado",
                "inicio": date.today().isoformat(),
                "fim": date.today().isoformat(),
                "dia_inteiro": True,
            }
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ), patch("push_client.configurado", return_value=False), patch(
            "telegram_bot.configurado", return_value=True
        ), patch("telegram_bot.enviar_mensagem", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_not_called()

    def test_notificacoes_verificar_agora_cobra_tarefa_parada_pelo_nome(self):
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("responder a corretora", tres_dias)
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
            # dispara os dois: o aviso generico (tarefas_atrasadas) e o check-in
            # nominal (tarefa_parada) - sao conteudos diferentes, ambos validos.
            self.assertEqual(res.get_json()["avisos_enviados"], 2)
            corpos = [c.args[2] for c in mock_enviar.call_args_list]
            self.assertTrue(
                any("responder a corretora" in c and "3 dias" in c for c in corpos),
                msg=f"nenhum push cobrou a tarefa pelo nome: {corpos}",
            )

    def test_notificacoes_tarefa_parada_nao_repete_mesmo_continuando_atrasada(self):
        """A cobranca de tarefa parada e um check-in uma vez so - diferente do
        aviso generico de tarefas atrasadas (que reseta por dia e volta a disparar
        no dia seguinte), essa nao deve voltar a mandar push so porque a tarefa
        continua sem due_date futuro nem concluida."""
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("responder a corretora", tres_dias)
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
            self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(mock_enviar.call_count, 2)

            # simula o dia seguinte apagando so o dedup do aviso generico (que e
            # por data) - o dedup de tarefa_parada (que ignora data) fica intacto,
            # simulando a tarefa continuar atrasada num dia posterior
            conn = db.get_db()
            conn.execute("DELETE FROM notificacoes_enviadas WHERE tipo = 'tarefas_atrasadas'")
            conn.commit()
            linha = conn.execute(
                "SELECT * FROM notificacoes_enviadas WHERE tipo = 'tarefa_parada'"
            ).fetchone()
            self.assertIsNotNone(linha)
            conn.close()

            res2 = self.client.post("/api/notificacoes/verificar-agora")
            # so o generico volta a disparar - o check-in nominal ja foi feito e
            # nao repete
            self.assertEqual(res2.get_json()["avisos_enviados"], 1)
            self.assertEqual(mock_enviar.call_count, 3)
            corpos_novos = [c.args[2] for c in mock_enviar.call_args_list[2:]]
            self.assertFalse(any("responder a corretora" in c for c in corpos_novos))

    def test_notificacoes_verificar_agora_cobra_espera_parada(self):
        cinco_dias = (datetime.now() - timedelta(days=5)).isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
            ("fornecedor de ferro", "preco do vergalhao", cinco_dias),
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
            self.assertIn("fornecedor de ferro", corpo)
            self.assertIn("preco do vergalhao", corpo)

    def test_notificacoes_espera_parada_nao_repete_depois_de_avisada(self):
        cinco_dias = (datetime.now() - timedelta(days=5)).isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
            ("fornecedor de ferro", "preco do vergalhao", cinco_dias),
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
            self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(mock_enviar.call_count, 1)

            res2 = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(res2.get_json()["avisos_enviados"], 0)
            self.assertEqual(mock_enviar.call_count, 1)

    def test_verificar_agora_abre_interacao_de_aprendizado_pra_tarefa_parada(self):
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("responder a corretora", tres_dias)
        )
        conn.commit()
        task_id = cur.lastrowid
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ):
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            self.client.post("/api/notificacoes/verificar-agora")

        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'tarefa_parada' AND referencia_id = ?",
            (task_id,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertIsNone(row["resolvido_em"])

    def test_completar_tarefa_depois_de_cobrada_fecha_a_interacao_com_latencia(self):
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("responder a corretora", tres_dias)
        )
        conn.commit()
        task_id = cur.lastrowid
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ):
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            self.client.post("/api/notificacoes/verificar-agora")

        res = self.client.post(f"/api/tasks/{task_id}/complete")
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'tarefa_parada' AND referencia_id = ?",
            (task_id,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row["resolvido_em"])
        self.assertIsNotNone(row["latencia_horas"])

    def test_completar_tarefa_sem_ter_sido_cobrada_nao_quebra(self):
        conn = db.get_db()
        cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", ("lavar o carro",))
        conn.commit()
        task_id = cur.lastrowid
        conn.close()

        res = self.client.post(f"/api/tasks/{task_id}/complete")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])

    def test_resolver_espera_depois_de_cobrada_fecha_a_interacao_com_latencia(self):
        cinco_dias = (datetime.now() - timedelta(days=5)).isoformat()
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
            ("fornecedor de ferro", "preco do vergalhao", cinco_dias),
        )
        conn.commit()
        espera_id = cur.lastrowid
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ):
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            self.client.post("/api/notificacoes/verificar-agora")

        res = self.client.post(f"/api/esperas/{espera_id}/resolver")
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'espera_parada' AND referencia_id = ?",
            (espera_id,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row["resolvido_em"])
        self.assertIsNotNone(row["latencia_horas"])

    def test_notificacoes_verificar_agora_inclui_gasto_dia_semana_atipico(self):
        hoje = date.today()
        conn = db.get_db()
        for i in range(1, 5):
            dia = hoje - timedelta(days=7 * i)
            conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        conn.execute(
            "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
            (500, "mercado", hoje.isoformat()),
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
            self.assertGreaterEqual(res.get_json()["avisos_enviados"], 1)
            corpos = [c.args[2] for c in mock_enviar.call_args_list]
            self.assertTrue(any("500.00" in c for c in corpos))

    def test_aprendizado_status_sem_historico_mostra_padrao(self):
        res = self.client.get("/api/aprendizado")
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertEqual(dados["tarefa_parada"]["dias_atual"], 3)
        self.assertEqual(dados["tarefa_parada"]["fonte"], "padrao")
        self.assertEqual(dados["espera_parada"]["dias_atual"], 5)
        self.assertEqual(dados["espera_parada"]["fonte"], "padrao")
        self.assertIsNone(dados["tarefa_parada"]["latencia_media_horas"])
        self.assertIsNone(dados["espera_parada"]["latencia_media_horas"])

    def test_aprendizado_status_reflete_historico_aprendido(self):
        conn = db.get_db()
        # 5 tarefas concluidas sempre com 2 dias de atraso - amostra
        # suficiente (minimo_amostras=5) pra aprender um limiar diferente do padrao
        for i in range(5):
            due = (date.today() - timedelta(days=30 + i)).isoformat()
            concluida = (date.today() - timedelta(days=28 + i)).isoformat() + " 10:00:00"
            conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                (f"tarefa {i}", due, concluida),
            )
        conn.commit()
        conn.close()

        res = self.client.get("/api/aprendizado")
        dados = res.get_json()
        self.assertEqual(dados["tarefa_parada"]["dias_atual"], 2)
        self.assertEqual(dados["tarefa_parada"]["fonte"], "aprendido_global")
        self.assertEqual(dados["tarefa_parada"]["amostras"], 5)

    def test_verificar_agora_usa_limiar_aprendido_pra_cobrar_mais_cedo(self):
        # historico ensina que o Alex sempre resolve em 1 dia - o limiar
        # aprendido fica bem abaixo do padrao de 3, entao uma tarefa parada
        # ha 2 dias (que o padrao ainda deixaria passar) ja deve ser cobrada.
        conn = db.get_db()
        for i in range(5):
            due = (date.today() - timedelta(days=30 + i)).isoformat()
            concluida = (date.today() - timedelta(days=29 + i)).isoformat() + " 10:00:00"
            conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                (f"tarefa antiga {i}", due, concluida),
            )
        dois_dias = (date.today() - timedelta(days=2)).isoformat()
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("responder a corretora", dois_dias)
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
            self.client.post("/api/notificacoes/verificar-agora")
            corpos = [c.args[2] for c in mock_enviar.call_args_list]
            self.assertTrue(
                any("responder a corretora" in c for c in corpos),
                msg=f"deveria ter cobrado com o limiar aprendido: {corpos}",
            )

    def test_verificar_agora_usa_limiar_especifico_do_titulo_quando_ha_amostra(self):
        # duas "familias" de tarefas com ritmos bem diferentes: "cotar X com
        # fornecedor" sempre atrasa MUITO (10 dias) - o limiar especifico
        # pra esse titulo devia ficar alto, sem cobrar cedo demais so por
        # causa do aprendizado GLOBAL (que teria uma mediana bem menor,
        # puxada por outra familia de tarefas rapidas).
        conn = db.get_db()
        for i in range(5):
            due_rapida = (date.today() - timedelta(days=30 + i)).isoformat()
            concluida_rapida = (date.today() - timedelta(days=29 + i)).isoformat() + " 10:00:00"
            conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                (f"lavar o carro {i}", due_rapida, concluida_rapida),  # 1 dia de atraso
            )
        for i in range(5):
            due_lenta = (date.today() - timedelta(days=60 + i)).isoformat()
            concluida_lenta = (date.today() - timedelta(days=50 + i)).isoformat() + " 10:00:00"
            conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                (f"cotar item {i} com fornecedor", due_lenta, concluida_lenta),  # 10 dias de atraso
            )
        # nova tarefa da familia "lenta", parada ha so 3 dias - o limiar
        # global (puxado pelas rapidas) cobraria; o especifico (~10 dias) nao deveria
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
            ("cotar telhas com fornecedor", tres_dias),
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
            self.client.post("/api/notificacoes/verificar-agora")
            corpos = [c.args[2] for c in mock_enviar.call_args_list]
            self.assertFalse(
                any("cotar telhas com fornecedor" in c for c in corpos),
                msg=f"nao deveria ter cobrado ainda (familia lenta, so 3 dias parada): {corpos}",
            )

    def test_obter_silencio_retorna_padrao_quando_nao_configurado(self):
        res = self.client.get("/api/configuracoes/silencio")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.get_json(),
            {"inicio": "22:00", "fim": "07:00", "agrupar": False, "agrupar_janela_min": 2},
        )

    def test_definir_silencio_valido_e_persistido(self):
        res = self.client.post("/api/configuracoes/silencio", json={"inicio": "23:00", "fim": "6:30"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"ok": True, "inicio": "23:00", "fim": "06:30"})

        res2 = self.client.get("/api/configuracoes/silencio")
        self.assertEqual(
            res2.get_json(),
            {"inicio": "23:00", "fim": "06:30", "agrupar": False, "agrupar_janela_min": 2},
        )

    def test_definir_silencio_invalido_rejeita(self):
        for corpo in [{"inicio": "25:00", "fim": "07:00"}, {"inicio": "22:00", "fim": ""}, {}]:
            res = self.client.post("/api/configuracoes/silencio", json=corpo)
            self.assertEqual(res.status_code, 400, msg=f"deveria rejeitar {corpo!r}")
        # nao alterou o padrao
        self.assertEqual(
            self.client.get("/api/configuracoes/silencio").get_json(),
            {"inicio": "22:00", "fim": "07:00", "agrupar": False, "agrupar_janela_min": 2},
        )

    def test_verificar_agora_represa_aviso_soft_no_horario_silencioso(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta", ontem))
        conn.commit()
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "notificacoes.dentro_do_horario_silencioso", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            res = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(res.get_json()["avisos_enviados"], 0)
            mock_enviar.assert_not_called()

            # nao marcou como notificado - assim que o silencio acabar, manda
            with patch("notificacoes.dentro_do_horario_silencioso", return_value=False):
                res2 = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(res2.get_json()["avisos_enviados"], 1)
            mock_enviar.assert_called_once()

    def test_verificar_agora_tarefa_com_horario_ignora_silencio(self):
        """Aviso urgente (preso a um instante) nao pode ficar represado - se
        adiar pro fim do silencio, a informacao perde a validade."""
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("colocar o lixo pra fora", hoje, "00:00"),
        )
        conn.commit()
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "notificacoes.dentro_do_horario_silencioso", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            res = self.client.post("/api/notificacoes/verificar-agora")
        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        corpo = mock_enviar.call_args[0][2]
        self.assertIn("colocar o lixo pra fora", corpo)

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

    def test_lembretes_traz_dias_restantes_e_proxima_ocorrencia(self):
        daqui_a_5_dias = (date.today() + timedelta(days=5)).isoformat()
        conn = db.get_db()
        db.create_lembrete(conn, "Seguro do carro", daqui_a_5_dias, recorrente=False)
        conn.close()

        lembretes = self.client.get("/api/lembretes").get_json()
        self.assertEqual(len(lembretes), 1)
        self.assertEqual(lembretes[0]["proxima_ocorrencia"], daqui_a_5_dias)
        self.assertEqual(lembretes[0]["dias_restantes"], 5)

    def test_lembrete_recorrente_mostra_proximo_aniversario_nao_o_ano_de_criacao(self):
        # Pedido do Alex ("datas importantes parece muito simples"): um
        # lembrete recorrente cadastrado num ano passado tem que mostrar o
        # PROXIMO aniversario da data, nunca o ano original de cadastro.
        data_original = date.today().replace(year=date.today().year - 1).isoformat()
        conn = db.get_db()
        db.create_lembrete(conn, "Exame medico anual", data_original, recorrente=True)
        conn.close()

        lembretes = self.client.get("/api/lembretes").get_json()
        proxima = date.fromisoformat(lembretes[0]["proxima_ocorrencia"])
        self.assertGreaterEqual(proxima, date.today())
        self.assertGreaterEqual(lembretes[0]["dias_restantes"], 0)

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

    def test_medicamentos_lista_vazia(self):
        self.assertEqual(self.client.get("/api/medicamentos").get_json(), [])

    def test_criar_medicamento_manual(self):
        res = self.client.post(
            "/api/medicamentos",
            json={"nome": "Losartana", "dosagem": "50mg", "horario": "08:00"},
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json()["ok"])

        medicamentos = self.client.get("/api/medicamentos").get_json()
        self.assertEqual(len(medicamentos), 1)
        self.assertEqual(medicamentos[0]["nome"], "Losartana")
        self.assertEqual(medicamentos[0]["dosagem"], "50mg")
        self.assertEqual(medicamentos[0]["horario"], "08:00")
        self.assertEqual(medicamentos[0]["recorrencia"], "diaria")

    def test_criar_medicamento_sem_dosagem(self):
        res = self.client.post("/api/medicamentos", json={"nome": "Vitamina D", "horario": "9:5"})
        self.assertEqual(res.status_code, 201)
        medicamentos = self.client.get("/api/medicamentos").get_json()
        self.assertIsNone(medicamentos[0]["dosagem"])
        self.assertEqual(medicamentos[0]["horario"], "09:05")

    def test_criar_medicamento_gera_tarefa_recorrente_vinculada_e_materializa_hoje(self):
        self.client.post(
            "/api/medicamentos",
            json={"nome": "Losartana", "dosagem": "50mg", "horario": "08:00"},
        )
        conn = db.get_db()
        hoje = date.today().isoformat()
        tarefas_hoje = conn.execute(
            "SELECT * FROM tasks WHERE due_date = ? AND recorrente_origem_id IS NOT NULL", (hoje,)
        ).fetchall()
        conn.close()
        self.assertEqual(len(tarefas_hoje), 1)
        self.assertEqual(tarefas_hoje[0]["title"], "Tomar Losartana (50mg)")
        self.assertEqual(tarefas_hoje[0]["hora"], "08:00")

    def test_criar_medicamento_sem_nome_rejeita(self):
        res = self.client.post("/api/medicamentos", json={"nome": "  ", "horario": "08:00"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get("/api/medicamentos").get_json(), [])

    def test_criar_medicamento_horario_invalido_rejeita(self):
        for horario_ruim in ["25:00", "08:70", "manha", "", None]:
            res = self.client.post(
                "/api/medicamentos", json={"nome": "X", "horario": horario_ruim}
            )
            self.assertEqual(res.status_code, 400, msg=f"deveria rejeitar horario={horario_ruim!r}")
        self.assertEqual(self.client.get("/api/medicamentos").get_json(), [])

    def test_criar_medicamento_recorrencia_invalida_rejeita(self):
        res = self.client.post(
            "/api/medicamentos",
            json={"nome": "X", "horario": "08:00", "recorrencia": "semanal:9"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get("/api/medicamentos").get_json(), [])

    def test_apagar_medicamento_remove_da_lista_e_a_tarefa_modelo(self):
        res = self.client.post(
            "/api/medicamentos", json={"nome": "Losartana", "horario": "08:00"}
        )
        medicamento_id = res.get_json()["medicamento_id"]
        conn = db.get_db()
        modelo = conn.execute(
            "SELECT id FROM medicamentos WHERE id = ?", (medicamento_id,)
        ).fetchone()
        tarefa_modelo_id = conn.execute(
            "SELECT tarefa_modelo_id FROM medicamentos WHERE id = ?", (medicamento_id,)
        ).fetchone()["tarefa_modelo_id"]
        conn.close()
        self.assertIsNotNone(modelo)

        res_delete = self.client.delete(f"/api/medicamentos/{medicamento_id}")
        self.assertEqual(res_delete.status_code, 200)
        self.assertEqual(self.client.get("/api/medicamentos").get_json(), [])

        conn = db.get_db()
        tarefa_modelo = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (tarefa_modelo_id,)
        ).fetchone()
        conn.close()
        self.assertIsNone(tarefa_modelo)

    def test_chat_usa_executor_de_medicamento_de_verdade(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_medicamento"](
                {"nome": "Losartana", "dosagem": "50mg", "horario": "08:00"}
            )
            self.assertEqual(resultado["ok"], True)
            return "Beleza, vou te lembrar de tomar todo dia as 8h.", ["registrar_medicamento"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "tenho que tomar Losartana 50mg todo dia as 8h"}
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_medicamento"])

        medicamentos = self.client.get("/api/medicamentos").get_json()
        self.assertEqual(len(medicamentos), 1)
        self.assertEqual(medicamentos[0]["nome"], "Losartana")

    def test_telegram_chat_fn_usa_o_mesmo_pipeline_do_chat_web(self):
        """O bot do Telegram nao reimplementa nada - passa pelo mesmo
        _processar_mensagem_chat que a rota HTTP usa."""

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_lembrete"](
                {"titulo": "Validade do exame medico", "data": "2027-01-15", "recorrente": True}
            )
            self.assertEqual(resultado, {"ok": True})
            return "Beleza, vou te lembrar todo ano perto dessa data.", ["registrar_lembrete"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            resposta = app._telegram_chat_fn("meu exame medico de piloto vence dia 15 de janeiro, todo ano")

        self.assertEqual(resposta, "Beleza, vou te lembrar todo ano perto dessa data.")
        lembretes = self.client.get("/api/lembretes").get_json()
        self.assertEqual(len(lembretes), 1)
        self.assertEqual(lembretes[0]["titulo"], "Validade do exame medico")

    def test_telegram_chat_fn_devolve_mensagem_de_erro_amigavel_na_falha(self):
        with patch("claude_client.chat", side_effect=ValueError("formato inesperado")):
            resposta = app._telegram_chat_fn("oi")
        self.assertEqual(resposta, app.CLAUDE_FORMAT_ERROR_MSG)

    def test_telegram_callback_fn_completa_tarefa_pendente(self):
        conn = db.get_db()
        cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", ("responder a corretora",))
        conn.commit()
        task_id = cur.lastrowid
        conn.close()

        resposta = app._telegram_callback_fn(f"completar_tarefa:{task_id}")
        self.assertIn("responder a corretora", resposta)

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(tasks, [])

    def test_telegram_callback_fn_fecha_interacao_de_aprendizado(self):
        conn = db.get_db()
        cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", ("responder a corretora",))
        conn.commit()
        task_id = cur.lastrowid
        db.registrar_interacao_aprendizado(conn, "tarefa_parada", task_id)
        conn.close()

        app._telegram_callback_fn(f"completar_tarefa:{task_id}")

        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'tarefa_parada' AND referencia_id = ?",
            (task_id,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row["resolvido_em"])

    def test_telegram_callback_fn_tarefa_ja_concluida_nao_quebra(self):
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO tasks (title, completed_at) VALUES (?, datetime('now'))", ("ja feita",)
        )
        conn.commit()
        task_id = cur.lastrowid
        conn.close()

        resposta = app._telegram_callback_fn(f"completar_tarefa:{task_id}")
        self.assertIn("Ja estava", resposta)

    def test_telegram_callback_fn_tarefa_inexistente(self):
        resposta = app._telegram_callback_fn("completar_tarefa:99999")
        self.assertIn("nao existe mais", resposta)

    def test_telegram_callback_fn_dados_desconhecidos(self):
        resposta = app._telegram_callback_fn("acao_estranha:1")
        self.assertIn("Nao reconheci", resposta)

    def test_telegram_callback_fn_id_nao_numerico_nao_quebra(self):
        resposta = app._telegram_callback_fn("completar_tarefa:abc")
        self.assertIn("Nao reconheci", resposta)

    def test_verificar_agora_manda_botao_de_acao_por_telegram_em_tarefa_parada(self):
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("responder a corretora", tres_dias)
        )
        conn.commit()
        task_id = cur.lastrowid
        conn.close()

        with patch("telegram_bot.configurado", return_value=True), patch(
            "telegram_bot.enviar_mensagem", return_value=True
        ) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")

        chamada_tarefa = next(
            c for c in mock_enviar.call_args_list if "responder a corretora" in c.args[0]
        )
        botoes = chamada_tarefa.kwargs.get("botoes")
        self.assertEqual(botoes, [("Marcar como feito", f"completar_tarefa:{task_id}")])

    def test_verificar_agora_nao_manda_botao_em_notificacao_generica(self):
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("responder a corretora", tres_dias)
        )
        conn.commit()
        conn.close()

        with patch("telegram_bot.configurado", return_value=True), patch(
            "telegram_bot.enviar_mensagem", return_value=True
        ) as mock_enviar:
            self.client.post("/api/notificacoes/verificar-agora")

        chamada_generica = next(
            c for c in mock_enviar.call_args_list if "Tarefas atrasadas" in c.args[0]
        )
        self.assertIsNone(chamada_generica.kwargs.get("botoes"))

    def test_chat_usa_executor_de_espera_de_verdade(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_espera"](
                {"quem": "fornecedor de ferro", "sobre": "preco do vergalhao"}
            )
            self.assertTrue(resultado["ok"])
            return "Beleza, vou ficar de olho nisso.", ["registrar_espera"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "to esperando resposta do fornecedor de ferro sobre o preco do vergalhao"}
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_espera"])

        esperas = self.client.get("/api/esperas").get_json()
        self.assertEqual(len(esperas), 1)
        self.assertEqual(esperas[0]["quem"], "fornecedor de ferro")
        self.assertEqual(esperas[0]["sobre"], "preco do vergalhao")

    def test_chat_resolve_espera_por_quem_aproximado(self):
        conn = db.get_db()
        db.create_espera(conn, "fornecedor de ferro", "preco do vergalhao")
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["resolver_espera"]({"quem": "o fornecedor de ferro"})
            self.assertTrue(resultado["ok"])
            return "Legal, marquei como resolvido.", ["resolver_espera"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "o fornecedor de ferro respondeu"})
        self.assertEqual(res.status_code, 200)

        esperas = self.client.get("/api/esperas").get_json()
        self.assertEqual(esperas, [])

    def test_chat_resolve_espera_inexistente_retorna_erro_pro_modelo(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["resolver_espera"]({"quem": "alguem que nao existe"})
            self.assertIn("erro", resultado)
            return "Nao achei essa espera.", ["resolver_espera"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "alguem que nao existe respondeu"})
        self.assertEqual(res.status_code, 200)

    def test_chat_registrar_feito_sem_tarefa_parecida_cria_ja_concluida(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_feito"]({"titulo": "fui na academia"})
            self.assertTrue(resultado["ok"])
            self.assertEqual(resultado["acao"], "registrada_e_concluida")
            return "Boa, ja registrei aqui.", ["registrar_feito"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat",
                json={"mensagem": "so passando pra contar que hoje eu fui na academia"},
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_feito"])

        tasks = self.client.get("/api/tasks").get_json()
        # tarefa ja nasce concluida - nao aparece na lista de pendentes
        self.assertEqual(tasks, [])
        conn = db.get_db()
        row = conn.execute("SELECT * FROM tasks WHERE title = 'fui na academia'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertIsNotNone(row["completed_at"])

    def test_chat_registrar_feito_com_tarefa_pendente_parecida_marca_concluida(self):
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
            ("pagar conta de luz", date.today().isoformat()),
        )
        conn.commit()
        task_id = cur.lastrowid
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_feito"]({"titulo": "conta de luz"})
            self.assertEqual(resultado["acao"], "marcada_concluida")
            return "Boa, marquei como feito.", ["registrar_feito"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "ja paguei a conta de luz tambem"})
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        row = conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        total = conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"]
        conn.close()
        self.assertIsNotNone(row["completed_at"])
        self.assertEqual(total, 1)

    def test_esperas_lista_vazia(self):
        self.assertEqual(self.client.get("/api/esperas").get_json(), [])

    def test_criar_espera_manual(self):
        res = self.client.post(
            "/api/esperas", json={"quem": "corretora do seguro", "sobre": "proposta nova"}
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json()["ok"])

        esperas = self.client.get("/api/esperas").get_json()
        self.assertEqual(len(esperas), 1)
        self.assertEqual(esperas[0]["quem"], "corretora do seguro")

    def test_criar_espera_sem_quem_ou_sobre_rejeita(self):
        for corpo in [{"quem": "", "sobre": "algo"}, {"quem": "alguem", "sobre": ""}, {}]:
            res = self.client.post("/api/esperas", json=corpo)
            self.assertEqual(res.status_code, 400, msg=f"deveria rejeitar {corpo!r}")
        self.assertEqual(self.client.get("/api/esperas").get_json(), [])

    def test_resolver_espera_remove_da_lista_de_pendentes(self):
        conn = db.get_db()
        espera_id = db.create_espera(conn, "corretora do seguro", "proposta nova")
        conn.close()

        res = self.client.post(f"/api/esperas/{espera_id}/resolver")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/esperas").get_json(), [])

    def test_resolver_espera_inexistente_devolve_404(self):
        res = self.client.post("/api/esperas/9999/resolver")
        self.assertEqual(res.status_code, 404)

    def test_resolver_espera_ja_resolvida_devolve_404(self):
        conn = db.get_db()
        espera_id = db.create_espera(conn, "corretora do seguro", "proposta nova")
        conn.close()
        self.client.post(f"/api/esperas/{espera_id}/resolver")

        res = self.client.post(f"/api/esperas/{espera_id}/resolver")
        self.assertEqual(res.status_code, 404)

    def test_apagar_espera_remove_da_lista(self):
        conn = db.get_db()
        espera_id = db.create_espera(conn, "corretora do seguro", "proposta nova")
        conn.close()

        res = self.client.delete(f"/api/esperas/{espera_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/esperas").get_json(), [])

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

    # ---- Renda (entradas) ----

    def test_incomes_lista_vazia(self):
        self.assertEqual(self.client.get("/api/incomes").get_json(), [])

    def test_chat_registrar_renda_entrada_generica(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_renda"]({"valor": 3000.0, "categoria": "outros"})
            self.assertTrue(resultado["ok"])
            return "Boa, registrei a entrada.", ["registrar_renda"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "entrou 3000 na conta"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_renda"])

        incomes = self.client.get("/api/incomes").get_json()
        self.assertEqual(len(incomes), 1)
        self.assertEqual(incomes[0]["amount"], 3000.0)
        self.assertEqual(incomes[0]["category"], "outros")

    def test_chat_registrar_renda_pagamento_de_cliente(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_renda"](
                {"valor": 500.0, "categoria": "cliente", "descricao": "pagamento do fulano"}
            )
            return "Boa.", ["registrar_renda"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "recebi 500 do fulano"})

        incomes = self.client.get("/api/incomes").get_json()
        self.assertEqual(incomes[0]["category"], "cliente")
        self.assertEqual(incomes[0]["description"], "pagamento do fulano")

    def test_chat_registrar_renda_venda(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_renda"]({"valor": 800.0, "categoria": "venda", "descricao": "material"})
            return "Boa.", ["registrar_renda"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "vendi um material e entrou 800"})

        incomes = self.client.get("/api/incomes").get_json()
        self.assertEqual(incomes[0]["category"], "venda")

    def test_incomes_ordenadas_mais_recente_primeiro(self):
        conn = db.get_db()
        db.create_income(conn, 100.0, "outros", None, None)
        db.create_income(conn, 200.0, "outros", None, None)
        conn.close()
        incomes = self.client.get("/api/incomes").get_json()
        self.assertEqual([i["amount"] for i in incomes], [200.0, 100.0])

    # ---- Orcamento por categoria ----

    def test_orcamentos_lista_vazia(self):
        self.assertEqual(self.client.get("/api/orcamentos").get_json(), [])

    def test_chat_definir_orcamento(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["definir_orcamento"]({"categoria": "mercado", "valor_limite": 800.0})
            self.assertTrue(resultado["ok"])
            return "Beleza, orcamento de mercado definido.", ["definir_orcamento"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "quero gastar no maximo 800 em mercado por mes"}
            )
        self.assertEqual(res.status_code, 200)

        orcamentos = self.client.get("/api/orcamentos").get_json()
        self.assertEqual(len(orcamentos), 1)
        self.assertEqual(orcamentos[0]["categoria"], "mercado")
        self.assertEqual(orcamentos[0]["valor_limite"], 800.0)
        self.assertEqual(orcamentos[0]["gasto_mes"], 0.0)

    def test_orcamentos_mostra_gasto_do_mes_atual(self):
        conn = db.get_db()
        db.definir_orcamento(conn, "mercado", 800.0)
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo) VALUES (300, 'mercado', 'real')"
        )
        conn.commit()
        conn.close()

        orcamentos = self.client.get("/api/orcamentos").get_json()
        self.assertEqual(orcamentos[0]["gasto_mes"], 300.0)

    def test_verificar_agora_avisa_orcamento_quase_no_limite(self):
        conn = db.get_db()
        db.definir_orcamento(conn, "mercado", 1000.0)
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo) VALUES (950, 'mercado', 'real')"
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
        self.assertIn("mercado", corpo)
        self.assertIn("950.00", corpo)

    def test_verificar_agora_orcamento_nao_repete_no_mesmo_mes(self):
        conn = db.get_db()
        db.definir_orcamento(conn, "mercado", 1000.0)
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo) VALUES (950, 'mercado', 'real')"
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
            self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(mock_enviar.call_count, 1)

            res2 = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(res2.get_json()["avisos_enviados"], 0)
            self.assertEqual(mock_enviar.call_count, 1)

    def test_verificar_agora_avisa_estourado_alem_de_quase(self):
        # gasta mais depois de ja ter recebido o aviso de "quase" - o nivel
        # "estourado" e uma chave de dedup diferente, entao dispara de novo.
        conn = db.get_db()
        db.definir_orcamento(conn, "mercado", 1000.0)
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo) VALUES (950, 'mercado', 'real')"
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
            self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(mock_enviar.call_count, 1)

            conn = db.get_db()
            conn.execute(
                "INSERT INTO expenses (amount, category, tipo) VALUES (200, 'mercado', 'real')"
            )
            conn.commit()
            conn.close()

            self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(mock_enviar.call_count, 2)
            corpo = mock_enviar.call_args[0][2]
            self.assertIn("passou do orcamento", corpo)

    # ---- Gastos fixos/assinaturas ----

    def test_gastos_fixos_vazio_sem_historico(self):
        res = self.client.get("/api/gastos-fixos").get_json()
        self.assertEqual(res, {"recorrentes": [], "total_mensal": 0})

    def test_gastos_fixos_detecta_assinatura_recorrente(self):
        hoje = date.today()
        mes_passado = (hoje.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        conn = db.get_db()
        conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) "
            "VALUES (39.90, 'lazer', 'Netflix', 'real', ?)",
            (f"{hoje.strftime('%Y-%m')}-05 10:00:00",),
        )
        conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) "
            "VALUES (39.90, 'lazer', 'Netflix', 'real', ?)",
            (f"{mes_passado}-05 10:00:00",),
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/gastos-fixos").get_json()
        self.assertEqual(len(res["recorrentes"]), 1)
        self.assertEqual(res["recorrentes"][0]["descricao"], "Netflix")
        self.assertEqual(res["total_mensal"], 39.90)

    def test_chat_consultar_gastos_fixos(self):
        hoje = date.today()
        mes_passado = (hoje.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        conn = db.get_db()
        conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) "
            "VALUES (100.0, 'saude', 'Academia', 'real', ?)",
            (f"{hoje.strftime('%Y-%m')}-05 10:00:00",),
        )
        conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) "
            "VALUES (100.0, 'saude', 'Academia', 'real', ?)",
            (f"{mes_passado}-05 10:00:00",),
        )
        conn.commit()
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["consultar_gastos_fixos"]({})
            self.assertEqual(resultado["total_mensal"], 100.0)
            return "Voce gasta R$100 fixo por mes (Academia).", ["consultar_gastos_fixos"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "quanto eu gasto de fixo por mes?"})
        self.assertEqual(res.status_code, 200)

    # ---- Noticias sob demanda (Google News RSS, so quando pedido) ----

    def test_chat_consultar_noticias(self):
        manchetes_fake = [
            {"titulo": "Prefeitura anuncia obra", "fonte": "Brusque Agora", "link": "https://x.com/1", "publicado_em": "..."}
        ]

        def fake_chat(mensagens, contexto, memorias, executores):
            with patch("noticias.buscar_manchetes", return_value=manchetes_fake) as mock_buscar:
                resultado = executores["consultar_noticias"]({"termo": "Brusque SC"})
            mock_buscar.assert_called_once_with("Brusque SC")
            self.assertEqual(resultado["manchetes"], manchetes_fake)
            return "Achei essa noticia de Brusque: Prefeitura anuncia obra.", ["consultar_noticias"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "tem noticia de Brusque?"})
        self.assertEqual(res.status_code, 200)

    def test_chat_consultar_noticias_sem_resultado(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            with patch("noticias.buscar_manchetes", return_value=[]):
                resultado = executores["consultar_noticias"]({"termo": "algo bem obscuro"})
            self.assertEqual(resultado["manchetes"], [])
            return "Nao achei nada sobre isso agora.", ["consultar_noticias"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "tem noticia sobre algo bem obscuro?"})
        self.assertEqual(res.status_code, 200)

    # ---- Notas ----

    def test_chat_salvar_nota(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["salvar_nota"](
                {
                    "titulo": "Viagem Portugal",
                    "corpo": "Comprar passagens\nHotel em Lisboa",
                    "tags": ["portugal", "viagem"],
                }
            )
            self.assertTrue(resultado["ok"])
            self.assertIn("nota_id", resultado)
            return "Anotado.", ["salvar_nota"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat",
                json={"mensagem": "anota isso: viagem pra Portugal, comprar passagens e hotel em Lisboa"},
            )
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        notas = db.list_notas(conn)
        conn.close()
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["titulo"], "Viagem Portugal")

    def test_chat_consultar_notas(self):
        conn = db.get_db()
        db.create_nota(conn, "Viagem Portugal", "roteiro de dezembro", ["portugal"])
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["consultar_notas"]({"termo": "Portugal"})
            self.assertEqual(len(resultado["notas"]), 1)
            return "Achei a nota de Portugal.", ["consultar_notas"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "o que eu anotei sobre Portugal?"})
        self.assertEqual(res.status_code, 200)

    def test_chat_consultar_notas_sem_resultado(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["consultar_notas"]({"termo": "nada a ver"})
            self.assertEqual(resultado["notas"], [])
            return "Nao achei nenhuma nota com isso.", ["consultar_notas"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "o que eu anotei sobre nada a ver?"})
        self.assertEqual(res.status_code, 200)

    def test_api_notas_get_e_delete(self):
        conn = db.get_db()
        nota_id = db.create_nota(conn, "Nota qualquer", "conteudo")
        conn.close()

        res = self.client.get("/api/notas")
        self.assertEqual(res.status_code, 200)
        notas = res.get_json()
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["id"], nota_id)

        res_delete = self.client.delete(f"/api/notas/{nota_id}")
        self.assertEqual(res_delete.status_code, 200)
        self.assertEqual(self.client.get("/api/notas").get_json(), [])

    # ---- Quanto sobra pra gastar ----

    def test_sobra_do_mes_sem_nenhum_dado(self):
        res = self.client.get("/api/sobra-do-mes").get_json()
        self.assertEqual(res["renda_mes"], 0)
        self.assertEqual(res["gasto_mes"], 0)
        self.assertEqual(res["sobra"], 0)

    def test_sobra_do_mes_com_renda_e_gasto(self):
        conn = db.get_db()
        db.create_income(conn, 3000.0, "outros")
        conn.execute("INSERT INTO expenses (amount, category, tipo) VALUES (1200, 'mercado', 'real')")
        conn.execute("INSERT INTO expenses (amount, category, tipo) VALUES (500, 'lazer', 'planejado')")
        conn.commit()
        conn.close()

        res = self.client.get("/api/sobra-do-mes").get_json()
        self.assertEqual(res["renda_mes"], 3000.0)
        self.assertEqual(res["gasto_mes"], 1200.0)
        self.assertEqual(res["sobra"], 1800.0)
        self.assertEqual(res["gasto_planejado_mes"], 500.0)
        self.assertEqual(res["sobra_considerando_planejado"], 1300.0)

    def test_sobra_do_mes_ignora_renda_e_gasto_de_outro_mes(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO incomes (amount, category, created_at) VALUES (3000, 'outros', '2020-01-15 10:00:00')"
        )
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo, created_at) "
            "VALUES (1200, 'mercado', 'real', '2020-01-15 10:00:00')"
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/sobra-do-mes").get_json()
        self.assertEqual(res["renda_mes"], 0)
        self.assertEqual(res["gasto_mes"], 0)

    def test_chat_consultar_sobra_do_mes(self):
        conn = db.get_db()
        db.create_income(conn, 2000.0, "outros")
        conn.execute("INSERT INTO expenses (amount, category, tipo) VALUES (500, 'mercado', 'real')")
        conn.commit()
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["consultar_sobra_do_mes"]({})
            self.assertEqual(resultado["sobra"], 1500.0)
            return "Sobrou R$1500 esse mes.", ["consultar_sobra_do_mes"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "quanto sobra pra gastar esse mes?"})
        self.assertEqual(res.status_code, 200)

    # ---- Extrato bancario entra na deteccao de recorrencia e na sobra do mes ----

    def _transacao_bancaria(self, descricao, valor, external_id):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "Nubank")
        conn.execute(
            "INSERT INTO bank_transactions (bank_account_id, data, descricao, valor, external_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (conta_id, date.today().isoformat(), descricao, valor, external_id),
        )
        conn.commit()
        conn.close()

    def test_sobra_do_mes_inclui_saida_do_extrato_bancario(self):
        conn = db.get_db()
        db.create_income(conn, 3000.0, "outros")
        conn.close()
        self._transacao_bancaria("Mercado", -800.0, "ext1")

        res = self.client.get("/api/sobra-do-mes").get_json()
        self.assertEqual(res["gasto_mes"], 800.0)
        self.assertEqual(res["sobra"], 2200.0)

    def test_sobra_do_mes_soma_expenses_e_bank_transactions_juntos(self):
        conn = db.get_db()
        db.create_income(conn, 3000.0, "outros")
        conn.execute("INSERT INTO expenses (amount, category, tipo) VALUES (200, 'lazer', 'real')")
        conn.commit()
        conn.close()
        self._transacao_bancaria("Mercado", -800.0, "ext1")

        res = self.client.get("/api/sobra-do-mes").get_json()
        self.assertEqual(res["gasto_mes"], 1000.0)

    def test_entrada_bancaria_nao_conta_como_gasto(self):
        conn = db.get_db()
        db.create_income(conn, 3000.0, "outros")
        conn.close()
        self._transacao_bancaria("Salario", 3000.0, "ext1")

        res = self.client.get("/api/sobra-do-mes").get_json()
        self.assertEqual(res["gasto_mes"], 0.0)

    def test_gastos_fixos_detecta_recorrencia_so_do_extrato_bancario(self):
        hoje = date.today()
        mes_passado = (hoje.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        self._transacao_bancaria("APPLE.COM/BILL", -14.90, "ext1")
        conn = db.get_db()
        conn.execute(
            "UPDATE bank_transactions SET data = ? WHERE external_id = 'ext1'",
            (f"{hoje.strftime('%Y-%m')}-05",),
        )
        conn.commit()
        conn.close()
        self._transacao_bancaria("APPLE.COM/BILL", -14.90, "ext2")
        conn = db.get_db()
        conn.execute(
            "UPDATE bank_transactions SET data = ? WHERE external_id = 'ext2'",
            (f"{mes_passado}-05",),
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/gastos-fixos").get_json()
        self.assertEqual(len(res["recorrentes"]), 1)
        self.assertEqual(res["recorrentes"][0]["descricao"], "APPLE.COM/BILL")
        self.assertEqual(res["total_mensal"], 14.90)

    # ---- Cobranca generica (padrao apple.com) e rotulagem pelo chat ----

    def test_verificar_agora_avisa_cobranca_generica_sem_rotulo(self):
        self._transacao_bancaria("APPLE.COM/BILL", -14.90, "ext1")

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
        self.assertIn("14.90", corpo)
        self.assertIn("qual assinatura", corpo)

    def test_verificar_agora_nao_avisa_cobranca_ja_rotulada(self):
        self._transacao_bancaria("APPLE.COM/BILL", -14.90, "ext1")
        conn = db.get_db()
        db.definir_apelido_gasto(conn, "apple.com/bill", 14.90, "iCloud 200GB")
        conn.close()

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            res = self.client.post("/api/notificacoes/verificar-agora")
        self.assertEqual(res.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_not_called()

    def test_verificar_agora_cobranca_generica_nao_repete_apos_avisar(self):
        self._transacao_bancaria("APPLE.COM/BILL", -14.90, "ext1")

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            self.client.post(
                "/api/push/inscrever",
                json={"endpoint": "https://exemplo.com/sub1", "keys": {}},
            )
            self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(mock_enviar.call_count, 1)
            res2 = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(res2.get_json()["avisos_enviados"], 0)
            self.assertEqual(mock_enviar.call_count, 1)

    def test_chat_rotular_cobranca_generica(self):
        self._transacao_bancaria("APPLE.COM/BILL", -14.90, "ext1")

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["rotular_cobranca_generica"]({"valor": 14.90, "apelido": "iCloud 200GB"})
            self.assertTrue(resultado["ok"])
            return "Beleza, guardei que essa e o iCloud.", ["rotular_cobranca_generica"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "a cobranca da apple de 14,90 e o icloud"}
            )
        self.assertEqual(res.status_code, 200)

        gastos_fixos_res = self.client.get("/api/gastos-fixos").get_json()
        # so uma ocorrencia ainda (nao e recorrente com 1 mes so), mas o
        # apelido ja deve estar salvo pra quando repetir
        conn = db.get_db()
        apelidos = db.list_apelidos_gasto(conn)
        conn.close()
        self.assertEqual(len(apelidos), 1)
        self.assertEqual(apelidos[0]["apelido"], "iCloud 200GB")

    def test_chat_rotular_cobranca_generica_sem_correspondencia_devolve_erro(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["rotular_cobranca_generica"]({"valor": 99.99, "apelido": "iCloud"})
            self.assertIn("erro", resultado)
            return "Nao achei essa cobranca.", ["rotular_cobranca_generica"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "a cobranca de 99,99 e o icloud"})
        self.assertEqual(res.status_code, 200)

    # ---- Saldo antes/depois quando o banco e citado ----

    def test_chat_registrar_gasto_com_banco_conhecido_mostra_saldo(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "conta")
        db.atualizar_saldo_conta(conn, conta_id, 1000.0)
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_gasto"](
                {"titulo": "mercado", "valor": 150.0, "banco": "Nubank"}
            )
            self.assertEqual(resultado["saldo_banco"], {"banco": "nubank", "antes": 1000.0, "depois": 850.0})
            return "Registrado. Saldo do Nubank: 1000 -> 850.", ["registrar_gasto"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "gastei 150 no mercado pelo Pix do Nubank"}
            )
        self.assertEqual(res.status_code, 200)

    def test_chat_registrar_gasto_sem_banco_citado_nao_mostra_saldo(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "conta")
        db.atualizar_saldo_conta(conn, conta_id, 1000.0)
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_gasto"]({"titulo": "mercado", "valor": 150.0})
            self.assertNotIn("saldo_banco", resultado)
            return "Registrado.", ["registrar_gasto"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "gastei 150 no mercado"})
        self.assertEqual(res.status_code, 200)

    def test_chat_registrar_gasto_banco_desconhecido_nao_mostra_saldo(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_gasto"](
                {"titulo": "mercado", "valor": 150.0, "banco": "Banco Que Nao Existe"}
            )
            self.assertNotIn("saldo_banco", resultado)
            return "Registrado.", ["registrar_gasto"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "gastei 150 no mercado pelo Banco Que Nao Existe"}
            )
        self.assertEqual(res.status_code, 200)

    def test_chat_registrar_gasto_planejado_com_banco_nao_mexe_no_saldo(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "conta")
        db.atualizar_saldo_conta(conn, conta_id, 1000.0)
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_gasto"](
                {"titulo": "talvez viagem", "valor": 300.0, "banco": "Nubank", "status": "planejado"}
            )
            self.assertNotIn("saldo_banco", resultado)
            return "Anotado como planejado.", ["registrar_gasto"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "talvez eu gaste 300 numa viagem pelo Nubank"}
            )
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        saldo = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
        conn.close()
        self.assertEqual(saldo["saldo"], 1000.0)

    def test_chat_registrar_renda_com_banco_conhecido_mostra_saldo(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "conta")
        db.atualizar_saldo_conta(conn, conta_id, 1000.0)
        conn.close()

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_renda"](
                {"valor": 500.0, "categoria": "cliente", "banco": "Nubank"}
            )
            self.assertEqual(resultado["saldo_banco"], {"banco": "nubank", "antes": 1000.0, "depois": 1500.0})
            return "Registrado.", ["registrar_renda"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post(
                "/api/chat", json={"mensagem": "recebi 500 de um cliente no Nubank"}
            )
        self.assertEqual(res.status_code, 200)

    def test_conectar_finalizar_grava_saldo_da_conta(self):
        item_fake = {"connector": {"name": "Nubank"}}
        contas_fake = [{"id": "conta-1", "type": "BANK", "balance": 16344.40}]
        with patch("pluggy_client.configurado", return_value=True), patch(
            "pluggy_client.get_item", return_value=item_fake
        ), patch("pluggy_client.get_accounts", return_value=contas_fake), patch(
            "pluggy_client.get_transactions", return_value=[]
        ):
            res = self.client.post("/api/bancos/conectar/finalizar", json={"item_id": "item-1"})
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        conta = db.buscar_conta_por_nome(conn, "nubank")
        conn.close()
        self.assertEqual(conta["saldo"], 16344.40)

    def test_conectar_finalizar_sem_balance_nao_grava_saldo(self):
        item_fake = {"connector": {"name": "Nubank"}}
        contas_fake = [{"id": "conta-1", "type": "BANK"}]
        with patch("pluggy_client.configurado", return_value=True), patch(
            "pluggy_client.get_item", return_value=item_fake
        ), patch("pluggy_client.get_accounts", return_value=contas_fake), patch(
            "pluggy_client.get_transactions", return_value=[]
        ):
            res = self.client.post("/api/bancos/conectar/finalizar", json={"item_id": "item-1"})
        self.assertEqual(res.status_code, 200)

        conn = db.get_db()
        conta = db.buscar_conta_por_nome(conn, "nubank")
        conn.close()
        self.assertIsNone(conta["saldo"])

    def test_apos_rotular_gastos_fixos_agrupa_por_apelido(self):
        hoje = date.today()
        mes_passado = (hoje.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        self._transacao_bancaria("APPLE.COM/BILL", -14.90, "ext1")
        conn = db.get_db()
        conn.execute(
            "UPDATE bank_transactions SET data = ? WHERE external_id = 'ext1'",
            (f"{hoje.strftime('%Y-%m')}-05",),
        )
        db.definir_apelido_gasto(conn, "apple.com/bill", 14.90, "iCloud 200GB")
        conn.commit()
        conn.close()
        self._transacao_bancaria("APPLE.COM/BILL", -14.90, "ext2")
        conn = db.get_db()
        conn.execute(
            "UPDATE bank_transactions SET data = ? WHERE external_id = 'ext2'",
            (f"{mes_passado}-05",),
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/gastos-fixos").get_json()
        self.assertEqual(res["recorrentes"][0]["descricao"], "iCloud 200GB")

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

    def test_verificar_notifica_fechamento_noturno(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, completed_at) VALUES (?, datetime('now'))", ("Academia",)
        )
        conn.commit()
        conn.close()

        sub = {"endpoint": "https://exemplo.com/push/fechamento1", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("notificacoes.fechamento_noturno_devido", return_value=True), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        self.assertIn("concluida hoje", mock_enviar.call_args[0][2])

    def test_verificar_fechamento_noturno_ja_notificado_nao_repete(self):
        sub = {"endpoint": "https://exemplo.com/push/fechamento2", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("notificacoes.fechamento_noturno_devido", return_value=True), patch(
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

    def _fake_get_contas_a_vencer(self, contas):
        def fake_get(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            resp.json.return_value = {"status": "ok", "contas": contas}
            return resp

        return fake_get

    def test_verificar_notifica_conta_a_vencer_proxima(self):
        sub = {"endpoint": "https://exemplo.com/push/contas1", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        contas = [
            {
                "vencimento": date.today().isoformat(),
                "valor": 1250.0,
                "fornecedor": "Topografia & Engenharia Ltda",
                "descricao": "Laudo ambiental",
                "dias_ate_vencer": 0,
            }
        ]
        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", side_effect=self._fake_get_contas_a_vencer(contas)), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        self.assertIn("Topografia", mock_enviar.call_args[0][2])
        self.assertIn("vence hoje", mock_enviar.call_args[0][2])

    def test_verificar_notifica_conta_a_vencer_vencida(self):
        sub = {"endpoint": "https://exemplo.com/push/contas2", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        contas = [
            {
                "vencimento": (date.today() - timedelta(days=2)).isoformat(),
                "valor": 800.0,
                "fornecedor": "Locadora de Retroescavadeiras",
                "descricao": "",
                "dias_ate_vencer": -2,
            }
        ]
        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", side_effect=self._fake_get_contas_a_vencer(contas)), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        self.assertIn("venceu ha 2 dia(s)", mock_enviar.call_args[0][2])

    def test_verificar_nao_notifica_conta_distante(self):
        sub = {"endpoint": "https://exemplo.com/push/contas3", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        contas = [
            {
                "vencimento": (date.today() + timedelta(days=10)).isoformat(),
                "valor": 500.0,
                "fornecedor": "Fornecedor Distante",
                "descricao": "",
                "dias_ate_vencer": 10,
            }
        ]
        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", side_effect=self._fake_get_contas_a_vencer(contas)), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_not_called()

    def test_verificar_conta_a_vencer_ja_notificada_nao_repete(self):
        sub = {"endpoint": "https://exemplo.com/push/contas4", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        contas = [
            {
                "vencimento": date.today().isoformat(),
                "valor": 300.0,
                "fornecedor": "Fornecedor Repetido",
                "descricao": "",
                "dias_ate_vencer": 0,
            }
        ]
        with patch.dict(
            os.environ,
            {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"},
        ), patch("requests.get", side_effect=self._fake_get_contas_a_vencer(contas)), patch(
            "push_client.configurado", return_value=True
        ), patch("push_client.enviar", return_value=True):
            self.client.post("/api/notificacoes/verificar-agora")
            res2 = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res2.get_json()["avisos_enviados"], 0)

    def test_verificar_sem_construtora_configurada_nao_notifica_conta(self):
        sub = {"endpoint": "https://exemplo.com/push/contas5", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar:
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 0)
        mock_enviar.assert_not_called()

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

    # ---- Cotacao de fornecedores (com leitura de PDF) ----

    def test_criar_cotacao_via_endpoint(self):
        res = self.client.post("/api/cotacoes", json={"titulo": "Portas"})
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json()["ok"])

    def test_criar_cotacao_sem_titulo_devolve_erro(self):
        res = self.client.post("/api/cotacoes", json={"titulo": ""})
        self.assertEqual(res.status_code, 400)

    def test_listar_cotacoes_inclui_total_de_itens_e_menor_valor(self):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "Ferro"}).get_json()["id"]
        self.client.post(f"/api/cotacoes/{cotacao_id}/itens", json={"fornecedor": "A", "valor": 500.0})
        self.client.post(f"/api/cotacoes/{cotacao_id}/itens", json={"fornecedor": "B", "valor": 300.0})

        res = self.client.get("/api/cotacoes")
        cotacoes = res.get_json()
        self.assertEqual(len(cotacoes), 1)
        self.assertEqual(cotacoes[0]["total_itens"], 2)
        self.assertEqual(cotacoes[0]["menor_valor"], 300.0)

    def test_ver_cotacao_lista_itens_do_mais_barato_pro_mais_caro(self):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "Vasos"}).get_json()["id"]
        self.client.post(f"/api/cotacoes/{cotacao_id}/itens", json={"fornecedor": "Caro", "valor": 900.0})
        self.client.post(f"/api/cotacoes/{cotacao_id}/itens", json={"fornecedor": "Barato", "valor": 100.0})

        res = self.client.get(f"/api/cotacoes/{cotacao_id}")
        itens = res.get_json()["itens"]
        self.assertEqual([i["fornecedor"] for i in itens], ["Barato", "Caro"])

    def test_ver_cotacao_inexistente_devolve_404(self):
        res = self.client.get("/api/cotacoes/9999")
        self.assertEqual(res.status_code, 404)

    def test_apagar_cotacao_remove_itens_tambem(self):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "Tijolo"}).get_json()["id"]
        self.client.post(f"/api/cotacoes/{cotacao_id}/itens", json={"fornecedor": "A", "valor": 50.0})

        res = self.client.delete(f"/api/cotacoes/{cotacao_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get(f"/api/cotacoes/{cotacao_id}").status_code, 404)

    def test_adicionar_item_em_cotacao_inexistente_devolve_404(self):
        res = self.client.post("/api/cotacoes/9999/itens", json={"fornecedor": "A", "valor": 10.0})
        self.assertEqual(res.status_code, 404)

    def test_apagar_item_cotacao(self):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "Areia"}).get_json()["id"]
        item_id = self.client.post(
            f"/api/cotacoes/{cotacao_id}/itens", json={"fornecedor": "A", "valor": 50.0}
        ).get_json()["id"]

        res = self.client.delete(f"/api/cotacoes/{cotacao_id}/itens/{item_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get(f"/api/cotacoes/{cotacao_id}").get_json()["itens"], [])

    def test_upload_pdf_cotacao_extrai_e_cria_item(self):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "Ferro"}).get_json()["id"]
        dados_extraidos = {
            "fornecedor": "Ferragens Silva",
            "valor": 4500.0,
            "prazo_texto": "15 dias",
            "observacao": None,
        }
        with patch(
            "claude_client.extrair_item_cotacao_pdf", return_value=(dados_extraidos, fake_usage())
        ):
            res = self.client.post(
                f"/api/cotacoes/{cotacao_id}/itens/pdf",
                data={"arquivo": (io.BytesIO(b"%PDF-1.4 fake"), "orcamento.pdf")},
                content_type="multipart/form-data",
            )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["fornecedor"], "Ferragens Silva")

        itens = self.client.get(f"/api/cotacoes/{cotacao_id}").get_json()["itens"]
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["origem"], "pdf")
        self.assertEqual(itens[0]["valor"], 4500.0)

    def test_upload_arquivo_nao_pdf_devolve_erro(self):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "Ferro"}).get_json()["id"]
        res = self.client.post(
            f"/api/cotacoes/{cotacao_id}/itens/pdf",
            data={"arquivo": (io.BytesIO(b"nao e pdf"), "orcamento.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(res.status_code, 400)

    def test_upload_sem_arquivo_devolve_erro(self):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "Ferro"}).get_json()["id"]
        res = self.client.post(f"/api/cotacoes/{cotacao_id}/itens/pdf", data={}, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)

    def test_upload_pdf_maior_que_15mb_devolve_erro(self):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "Ferro"}).get_json()["id"]
        conteudo_grande = b"0" * (16 * 1024 * 1024)
        res = self.client.post(
            f"/api/cotacoes/{cotacao_id}/itens/pdf",
            data={"arquivo": (io.BytesIO(conteudo_grande), "grande.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(res.status_code, 400)

    def test_registrar_item_cotacao_via_chat_cria_cotacao_nova(self):
        resultado = self._registrar_via_chat(
            "registrar_item_cotacao",
            {"titulo_cotacao": "portas", "fornecedor": "Madeireira X", "valor": 3000.0},
        )
        self.assertTrue(resultado["ok"])
        cotacoes = self.client.get("/api/cotacoes").get_json()
        self.assertEqual(len(cotacoes), 1)
        self.assertEqual(cotacoes[0]["titulo"], "portas")

    def test_registrar_item_cotacao_via_chat_reusa_cotacao_existente(self):
        self.client.post("/api/cotacoes", json={"titulo": "Cotacao de ferro"})
        resultado = self._registrar_via_chat(
            "registrar_item_cotacao",
            {"titulo_cotacao": "ferro", "fornecedor": "Aco Forte", "valor": 2000.0},
        )
        cotacoes = self.client.get("/api/cotacoes").get_json()
        self.assertEqual(len(cotacoes), 1)  # nao criou uma segunda
        self.assertEqual(cotacoes[0]["total_itens"], 1)
        self.assertEqual(resultado["cotacao_id"], cotacoes[0]["id"])

    def test_comparar_cotacao_via_chat_ordena_por_valor(self):
        self._registrar_via_chat(
            "registrar_item_cotacao",
            {"titulo_cotacao": "vasos", "fornecedor": "Caro Ltda", "valor": 900.0},
        )
        self._registrar_via_chat(
            "registrar_item_cotacao",
            {"titulo_cotacao": "vasos", "fornecedor": "Barato Ltda", "valor": 300.0},
        )
        resultado = self._registrar_via_chat("comparar_cotacao", {"titulo_cotacao": "vasos"})
        self.assertEqual([i["fornecedor"] for i in resultado["itens"]], ["Barato Ltda", "Caro Ltda"])

    def test_comparar_cotacao_inexistente_devolve_erro(self):
        resultado = self._registrar_via_chat("comparar_cotacao", {"titulo_cotacao": "algo que nao existe"})
        self.assertIn("erro", resultado)

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

    # ---- Colar trecho exportado do WhatsApp direto no chat ----
    # (o Alex disse que ultimamente anota tudo la, nao no painel - exemplo real
    # dele: linhas "[DD/MM/AAAA, HH:MM:SS] alex: texto", uma delas com 3 itens
    # soltos dentro da MESMA mensagem colchetada). O ponto critico: a data
    # entre colchetes e so metadado de quando ele anotou, nunca a data em que a
    # tarefa precisa ser feita - se o modelo confundisse isso, toda tarefa
    # nasceria "atrasada" do nada. Este teste simula a classificacao ideal (o
    # que o system prompt agora pede explicitamente) e confere que o app
    # cria as 7 tarefas certas, nenhuma com due_date vindo do colchete.
    def test_chat_cola_trecho_exportado_do_whatsapp(self):
        resposta_com_tools = _resp(
            [
                _tool_block("registrar_tarefa", {"titulo": "comprar 4 pacotinho de fuga cinza claro 1kg"}, id_="t1"),
                _tool_block("registrar_tarefa", {"titulo": "comprar vaso sanitario caixa acoplada"}, id_="t2"),
                _tool_block("registrar_tarefa", {"titulo": "comprar soleira da lixeira guarani"}, id_="t3"),
                _tool_block("registrar_tarefa", {"titulo": "resolver nome do predio e numeros predios"}, id_="t4"),
                _tool_block("registrar_tarefa", {"titulo": "ver vasos na internet"}, id_="t5"),
                _tool_block("registrar_tarefa", {"titulo": "pesquisar madeira poli"}, id_="t6"),
                _tool_block("registrar_tarefa", {"titulo": "fazer lista de contas com a Nina"}, id_="t7"),
            ],
            stop_reason="tool_use",
        )
        resposta_final = _resp([_text_block("Registrei os 7 itens soltos que voce colou.")])

        mensagem = (
            "[18/09/2026, 07:57:50] alex: 4 pacotinho de fuga cinza claro 1kg\n"
            "[18/09/2026, 08:14:00] alex: vaso sanitário caixa acoplada\n"
            "[18/09/2026, 08:15:24] alex: soleira da lixeira guarani\n"
            "[21/09/2026, 17:27:28] alex: resolver nome do predio e numeros predios\n"
            "ver vasos na internet\n"
            "madeira poli\n"
            "[21/09/2026, 17:28:29] alex: fazer lista contasse conversa com a nina"
        )
        with patch.object(
            claude_client.client.messages, "create", side_effect=[resposta_com_tools, resposta_final]
        ):
            res = self.client.post("/api/chat", json={"mensagem": mensagem})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["acoes"], ["registrar_tarefa"] * 7)

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 7)
        # nenhuma tarefa pode ter herdado a data do colchete (18/09 e 21/09 sao
        # passado em relacao a "hoje" no teste - se due_date tivesse sido
        # setada a partir dali, isso apareceria como atrasada sem sentido).
        self.assertTrue(all(t["due_date"] is None for t in tasks))

        msg = app.notificacoes.tarefas_atrasadas(db.get_db())
        self.assertIsNone(msg, "nenhuma das 7 tarefas coladas devia contar como atrasada")

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

    def test_sugestao_de_dia_usa_produtividade_pra_desempatar_carga_igual(self):
        hoje = date.today()
        if hoje.weekday() >= 5:
            self.skipTest("precisa de pelo menos 2 dias uteis distintos candidatos essa semana")
        dia_a = hoje + timedelta(days=1)
        dia_b = hoje + timedelta(days=2)
        conn = db.get_db()
        # historico: tarefas com prazo no dia_b da semana sempre terminam no
        # prazo; no dia_a da semana, nunca - produtividade real bem diferente
        # entre os dois dias, mesmo sem nenhuma carga JA marcada pra essa semana.
        for semanas_atras in range(1, 4):
            devido_a = (dia_a - timedelta(weeks=semanas_atras)).isoformat()
            devido_b = (dia_b - timedelta(weeks=semanas_atras)).isoformat()
            conn.execute(
                "INSERT INTO tasks (title, due_date) VALUES (?, ?)",  # nunca concluida = fora do prazo
                (f"nunca feita a {semanas_atras}", devido_a),
            )
            conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                (f"feita no prazo b {semanas_atras}", devido_b, devido_b + " 08:00:00"),
            )
        conn.commit()
        conn.close()

        resultado = self._registrar_via_chat(
            "registrar_tarefa", {"titulo": "algo novo", "quando": "essa semana"}
        )
        self.assertIn("sugestao_dia", resultado)
        # sem carga nenhuma marcada, os dois dias empatam em 0 - a produtividade
        # historica (dia_b sempre no prazo, dia_a quase nunca) deveria desempatar
        # pro dia_b, nao pro mais proximo (regra antiga de desempate).
        self.assertEqual(resultado["sugestao_dia"]["data"], dia_b.isoformat())

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


class BackupAutomaticoTestCase(unittest.TestCase):
    """Testa o job semanal do scheduler (rodar_backup_automatico_semanal) e a
    funcao de backup que ele reusa - chamados direto (sem HTTP), diferente
    dos testes de export manual em PainelTestCase."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('tarefa pro backup automatico')")
        conn.commit()
        conn.close()
        self._tmp_backup_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_backup_dir.cleanup)
        self._env_patch = patch.dict(
            os.environ, {"BACKUP_DIR": self._tmp_backup_dir.name, "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}
        )
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    def _arquivos_backup(self):
        return sorted(
            f for f in os.listdir(self._tmp_backup_dir.name) if f.startswith("painel-backup-") and f.endswith(".db")
        )

    def test_gerar_backup_arquivo_produz_db_restauravel(self):
        destino = os.path.join(self._tmp_backup_dir.name, "copia-manual.db")
        app.gerar_backup_arquivo(destino)

        conn_verificacao = sqlite3.connect(destino)
        titulo = conn_verificacao.execute("SELECT title FROM tasks").fetchone()[0]
        conn_verificacao.close()
        self.assertEqual(titulo, "tarefa pro backup automatico")

    def test_job_roda_e_produz_arquivo_restauravel_em_backup_dir(self):
        app.rodar_backup_automatico_semanal()

        arquivos = self._arquivos_backup()
        self.assertEqual(len(arquivos), 1)
        caminho = os.path.join(self._tmp_backup_dir.name, arquivos[0])
        conn_verificacao = sqlite3.connect(caminho)
        titulo = conn_verificacao.execute("SELECT title FROM tasks").fetchone()[0]
        conn_verificacao.close()
        self.assertEqual(titulo, "tarefa pro backup automatico")

    def test_job_usa_data_backups_como_padrao_sem_env(self):
        with patch.dict(os.environ, {"BACKUP_DIR": ""}):
            diretorio = app._diretorio_backups()
        self.assertTrue(diretorio.endswith(os.path.join("data", "backups")))

    def test_rotacao_mantem_so_os_ultimos_n(self):
        # pre-popula com mais backups "antigos" do que o limite de retencao -
        # nomes com carimbo cronologico crescente, igual o job real gera
        for i in range(1, app.BACKUP_AUTOMATICO_MANTER + 3):
            nome = f"painel-backup-2024-01-{i:02d}_000000.db"
            with open(os.path.join(self._tmp_backup_dir.name, nome), "wb") as f:
                f.write(b"fake")

        app.rodar_backup_automatico_semanal()

        arquivos = self._arquivos_backup()
        self.assertEqual(len(arquivos), app.BACKUP_AUTOMATICO_MANTER)
        # os mais antigos (01, 02) tem que ter sumido; os mais recentes ficam
        self.assertNotIn("painel-backup-2024-01-01_000000.db", arquivos)
        self.assertNotIn("painel-backup-2024-01-02_000000.db", arquivos)

    def test_telegram_enviado_quando_configurado(self):
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("telegram_bot.enviar_documento", return_value=True) as mock_enviar:
            app.rodar_backup_automatico_semanal()
        mock_enviar.assert_called_once()
        caminho_enviado = mock_enviar.call_args.args[0]
        self.assertTrue(os.path.exists(caminho_enviado))

    def test_telegram_pulado_quando_nao_configurado(self):
        with patch("telegram_bot.enviar_documento") as mock_enviar:
            app.rodar_backup_automatico_semanal()
        mock_enviar.assert_not_called()
        # o backup local ainda tem que acontecer normalmente mesmo sem telegram
        self.assertEqual(len(self._arquivos_backup()), 1)

    def test_falha_no_backup_nao_derruba_o_job(self):
        with patch("app.gerar_backup_arquivo", side_effect=OSError("disco cheio")):
            try:
                app.rodar_backup_automatico_semanal()
            except Exception as e:  # pragma: no cover - o teste falha e mostra o motivo
                self.fail(f"rodar_backup_automatico_semanal nao deveria propagar excecao: {e}")
        self.assertEqual(self._arquivos_backup(), [])

    def test_falha_no_envio_telegram_nao_impede_backup_local(self):
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("telegram_bot.enviar_documento", side_effect=RuntimeError("telegram fora do ar")):
            app.rodar_backup_automatico_semanal()
        self.assertEqual(len(self._arquivos_backup()), 1)


class ReclassificacaoECorrecaoTestCase(unittest.TestCase):
    """Item 4 do BRIEFING (Fase 4): correcao rapida de classificacao errada
    (tarefa <-> gasto, categoria de gasto) + aprendizado leve que injeta uma
    correcao parecida como contexto no prompt de classify_capture."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        conn.execute("DELETE FROM memorias")
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        app._CACHE_CONSTRUTORA.clear()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()
        self._silencio_patch = patch("notificacoes.dentro_do_horario_silencioso", return_value=False)
        self._silencio_patch.start()
        self.addCleanup(self._silencio_patch.stop)

    def _criar_tarefa(self, texto="ligar pro banco"):
        parsed = {
            "tipo": "tarefa", "titulo": texto, "valor": None,
            "categoria": None, "quando": None, "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": texto})
        assert res.status_code == 201, res.get_json()
        tasks = self.client.get("/api/tasks").get_json()
        return tasks[-1]

    def _criar_gasto(self, texto="netflix mensalidade", categoria="lazer", valor=39.9):
        parsed = {
            "tipo": "gasto", "titulo": texto, "valor": valor,
            "categoria": categoria, "quando": None, "duvida": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/capture", json={"text": texto})
        assert res.status_code == 201, res.get_json()
        expenses = self.client.get("/api/expenses").get_json()
        return expenses[0]

    # ---- tarefa -> gasto ----

    def test_reclassificar_tarefa_para_gasto_preserva_dado_e_limpa_subtasks(self):
        tarefa = self._criar_tarefa("comprar racao pro gato")
        conn = db.get_db()
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, ?, 0)", (tarefa["id"], "passo 1")
        )
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, ?, 1)", (tarefa["id"], "passo 2")
        )
        conn.commit()
        conn.close()

        res = self.client.post(
            f"/api/tasks/{tarefa['id']}/reclassificar", json={"valor": 85.0, "categoria": "mercado"}
        )
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["subtasks_removidas"], 2)

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 0)

        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0]["id"], body["novo_id"])
        self.assertEqual(expenses[0]["amount"], 85.0)
        self.assertEqual(expenses[0]["category"], "mercado")
        self.assertEqual(expenses[0]["description"], "comprar racao pro gato")
        self.assertIn("comprar racao pro gato", expenses[0]["source_text"])

        conn = db.get_db()
        restantes = conn.execute(
            "SELECT COUNT(*) AS n FROM subtasks WHERE task_id = ?", (tarefa["id"],)
        ).fetchone()["n"]
        conn.close()
        self.assertEqual(restantes, 0)

    def test_reclassificar_tarefa_para_gasto_sem_valor_da_erro(self):
        tarefa = self._criar_tarefa()
        res = self.client.post(f"/api/tasks/{tarefa['id']}/reclassificar", json={})
        self.assertEqual(res.status_code, 400)
        # nada foi movido
        self.assertEqual(len(self.client.get("/api/tasks").get_json()), 1)
        self.assertEqual(len(self.client.get("/api/expenses").get_json()), 0)

    def test_reclassificar_tarefa_valor_infinito_ou_bool_da_erro(self):
        # achado da revisao independente: Infinity/NaN e bool passavam pela
        # checagem antiga (isinstance(valor, (int, float)) e bool e subclasse
        # de int) e viravam expenses.amount = inf, contaminando qualquer soma.
        for valor in (float("inf"), float("-inf"), float("nan"), True, False):
            tarefa = self._criar_tarefa()
            res = self.client.post(f"/api/tasks/{tarefa['id']}/reclassificar", json={"valor": valor})
            self.assertEqual(res.status_code, 400, msg=repr(valor))
            self.assertEqual(len(self.client.get("/api/expenses").get_json()), 0, msg=repr(valor))

    def test_reclassificar_tarefa_inexistente_404(self):
        res = self.client.post("/api/tasks/9999/reclassificar", json={"valor": 10})
        self.assertEqual(res.status_code, 404)

    # ---- gasto -> tarefa ----

    def test_reclassificar_gasto_para_tarefa_preserva_dado(self):
        gasto = self._criar_gasto("academia mensalidade", categoria="saude", valor=120.0)
        res = self.client.post(
            f"/api/expenses/{gasto['id']}/reclassificar",
            json={"quando": "amanha", "quando_data": "2026-09-24"},
        )
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["ok"])

        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(expenses), 0)

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], body["novo_id"])
        self.assertEqual(tasks[0]["title"], "academia mensalidade")
        self.assertEqual(tasks[0]["due_at"], "amanha")
        self.assertEqual(tasks[0]["due_date"], "2026-09-24")
        self.assertIn("academia mensalidade", tasks[0]["source_text"])

    def test_reclassificar_gasto_inexistente_404(self):
        res = self.client.post("/api/expenses/9999/reclassificar", json={})
        self.assertEqual(res.status_code, 404)

    # ---- categoria de gasto ----

    def test_corrigir_categoria_gasto(self):
        gasto = self._criar_gasto("uber pro aeroporto", categoria="lazer", valor=45.0)
        res = self.client.post(f"/api/expenses/{gasto['id']}/categoria", json={"categoria": "transporte"})
        self.assertEqual(res.status_code, 200)

        expenses = self.client.get("/api/expenses").get_json()
        self.assertEqual(expenses[0]["category"], "transporte")

    def test_corrigir_categoria_gasto_vazia_da_erro(self):
        gasto = self._criar_gasto()
        res = self.client.post(f"/api/expenses/{gasto['id']}/categoria", json={"categoria": ""})
        self.assertEqual(res.status_code, 400)

    def test_corrigir_categoria_gasto_inexistente_404(self):
        res = self.client.post("/api/expenses/9999/categoria", json={"categoria": "mercado"})
        self.assertEqual(res.status_code, 404)

    # ---- gravacao da correcao + aprendizado leve ----

    def test_reclassificacao_grava_correcao_na_tabela_nova(self):
        tarefa = self._criar_tarefa("assinatura streaming mensal")
        self.client.post(
            f"/api/tasks/{tarefa['id']}/reclassificar", json={"valor": 39.9, "categoria": "lazer"}
        )

        conn = db.get_db()
        correcoes = db.list_correcoes_classificacao(conn)
        conn.close()
        self.assertEqual(len(correcoes), 1)
        self.assertEqual(correcoes[0]["tipo_errado"], "tarefa")
        self.assertIsNone(correcoes[0]["categoria_errada"])
        self.assertEqual(correcoes[0]["tipo_certo"], "gasto")
        self.assertEqual(correcoes[0]["categoria_certa"], "lazer")
        self.assertIn("assinatura streaming mensal", correcoes[0]["texto_original"])

    def test_correcao_categoria_grava_correcao_na_tabela_nova(self):
        gasto = self._criar_gasto("posto de gasolina", categoria="lazer", valor=200.0)
        self.client.post(f"/api/expenses/{gasto['id']}/categoria", json={"categoria": "transporte"})

        conn = db.get_db()
        correcoes = db.list_correcoes_classificacao(conn)
        conn.close()
        self.assertEqual(len(correcoes), 1)
        self.assertEqual(correcoes[0]["categoria_errada"], "lazer")
        self.assertEqual(correcoes[0]["categoria_certa"], "transporte")

    def test_aprendizado_correcao_semelhante_bate_por_tokens_em_comum(self):
        conn = db.get_db()
        db.registrar_correcao_classificacao(
            conn, "renovar spotify premium", "tarefa", None, "gasto", "lazer"
        )
        conn.close()

        conn = db.get_db()
        achada = aprendizado.correcao_semelhante(conn, "pagar spotify premium de novo")
        conn.close()
        self.assertIsNotNone(achada)
        self.assertEqual(achada["tipo_certo"], "gasto")

        conn = db.get_db()
        nao_achada = aprendizado.correcao_semelhante(conn, "levar carro na revisao")
        conn.close()
        self.assertIsNone(nao_achada)

    def test_captura_parecida_com_correcao_anterior_recebe_contexto_no_prompt(self):
        conn = db.get_db()
        db.registrar_correcao_classificacao(
            conn, "renovar spotify premium", "tarefa", None, "gasto", "lazer"
        )
        conn.close()

        capturados = {}

        def fake_classify(text, contexto_correcao=None):
            capturados["contexto_correcao"] = contexto_correcao
            return (
                {
                    "tipo": "gasto", "titulo": "spotify", "valor": 21.9,
                    "categoria": "lazer", "quando": None, "duvida": None,
                },
                fake_usage(),
            )

        with patch("claude_client.classify_capture", side_effect=fake_classify):
            res = self.client.post("/api/capture", json={"text": "pagar spotify premium de novo"})
        self.assertEqual(res.status_code, 201)
        self.assertIsNotNone(capturados["contexto_correcao"])
        self.assertIn("spotify", capturados["contexto_correcao"])
        self.assertIn("gasto", capturados["contexto_correcao"])

    def test_captura_sem_correcao_parecida_nao_recebe_contexto(self):
        capturados = {}

        def fake_classify(text, contexto_correcao=None):
            capturados["contexto_correcao"] = contexto_correcao
            return (
                {
                    "tipo": "tarefa", "titulo": "levar carro na revisao", "valor": None,
                    "categoria": None, "quando": None, "duvida": None,
                },
                fake_usage(),
            )

        with patch("claude_client.classify_capture", side_effect=fake_classify):
            res = self.client.post("/api/capture", json={"text": "levar carro na revisao"})
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(capturados["contexto_correcao"])


class FuzzingEndpointsTestCase(unittest.TestCase):
    """Fuzzing leve dos endpoints principais (POST /api/capture, POST /api/chat,
    GET /api/tasks, GET /api/expenses) - garante que corpo malformado ou tipo de
    dado inesperado nunca derruba a rota com um 500 cru (excecao nao tratada
    vazando como Internal Server Error). Nao valida o resultado de negocio de cada
    caso, so que a resposta e sempre controlada (400/401/200), nunca 500 - exceto
    onde isso e explicitamente o esperado (nenhum caso aqui e assim).

    Classe separada de PainelTestCase (em vez de herdar dela) de proposito - herdar
    faria o unittest coletar e rodar de novo todos os testes de feature dela sob
    esse nome, dobrando o tempo da suite sem nenhum ganho."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        conn.execute("DELETE FROM memorias")
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        app._CACHE_CONSTRUTORA.clear()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    CORPOS_MALFORMADOS = [
        {},
        None,
        [],
        [1, 2, 3],
        "so uma string solta",
        123,
        123.45,
        True,
        {"text": None},
        {"text": 123},
        {"text": 123.45},
        {"text": True},
        {"text": False},
        {"text": []},
        {"text": [1, 2, 3]},
        {"text": {}},
        {"text": {"aninhado": "valor"}},
        {"text": ""},
        {"text": "   "},
        {"mensagem": None},
        {"mensagem": 123},
        {"mensagem": []},
        {"mensagem": {}},
        {"text": "a" * 100000},
        {"text": "😀" * 2000},
        {"text": "<script>alert(1)</script>"},
        {"text": "' OR '1'='1"},
        {"text": "'; DROP TABLE tasks; --"},
        {"text": "texto\x00com\x00null\x00byte"},
        {"text": "линия юникода на русском"},
        {"text": "texto valido", "clarificacao": None},
        {"text": "texto valido", "clarificacao": 123},
        {"text": "texto valido", "clarificacao": []},
        {"text": "texto valido", "clarificacao": {}},
        {"text": "texto valido", "campo_desconhecido_extra": "valor qualquer"},
        {"text": "texto valido", "__proto__": "tentativa de poluicao"},
        {"outro_campo_qualquer": "sem text nem mensagem"},
        {"text": {"$ne": None}},  # tentativa de injecao estilo NoSQL, sem sentido aqui mas nao pode quebrar
    ]

    def _fuzzar(self, path, campo_chave_vazia="text"):
        with patch("claude_client.classify_capture", return_value=(
            {"tipo": "tarefa", "titulo": "fuzz", "valor": None, "categoria": None, "quando": None, "duvida": None},
            fake_usage(),
        )), patch("claude_client.chat", return_value=("ok", [], fake_usage())):
            for i, corpo in enumerate(self.CORPOS_MALFORMADOS):
                with self.subTest(endpoint=path, caso=i, corpo=corpo):
                    # Serializa na mao (em vez do kwarg json= do test client) pra
                    # cobrir de forma explicita e previsivel None/listas/escalares
                    # como corpo, nao so dicts.
                    res = self.client.post(path, data=json.dumps(corpo), content_type="application/json")
                    self.assertNotEqual(
                        res.status_code, 500, f"{path} com corpo={corpo!r} devolveu 500 cru"
                    )
                    self.assertIn(res.status_code, (200, 201, 400), f"{path} com corpo={corpo!r} -> {res.status_code}")

    def test_fuzzing_capture_nunca_da_500(self):
        self._fuzzar("/api/capture")

    def test_fuzzing_chat_nunca_da_500(self):
        self._fuzzar("/api/chat")

    def test_fuzzing_capture_corpo_nao_json_nunca_da_500(self):
        casos_nao_json = [
            "texto puro sem ser json",
            "{json quebrado sem fechar",
            "",
            "null",
            "<xml>nao é json</xml>",
            b"\xff\xfe\x00\x01binario",
        ]
        for i, corpo in enumerate(casos_nao_json):
            with self.subTest(caso=i, corpo=corpo):
                res = self.client.post(
                    "/api/capture",
                    data=corpo,
                    content_type="application/json" if i < 4 else "application/octet-stream",
                )
                self.assertNotEqual(res.status_code, 500, f"corpo bruto={corpo!r} devolveu 500 cru")

    def test_fuzzing_tasks_get_nunca_da_500(self):
        for query in ["", "?foo=bar", "?" + "x" * 5000, "?id=' OR '1'='1"]:
            with self.subTest(query=query):
                res = self.client.get(f"/api/tasks{query}")
                self.assertNotEqual(res.status_code, 500)
                self.assertEqual(res.status_code, 200)

    def test_fuzzing_expenses_get_nunca_da_500(self):
        for query in ["", "?foo=bar", "?" + "x" * 5000]:
            with self.subTest(query=query):
                res = self.client.get(f"/api/expenses{query}")
                self.assertNotEqual(res.status_code, 500)
                self.assertEqual(res.status_code, 200)


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

    def test_healthz_funciona_sem_pin_configurado(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"status": "ok"})

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

    def test_atalho_capturar_nao_exige_sessao_de_login(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()
        parsed = {
            "tipo": "tarefa", "titulo": "ligar pro dentista", "valor": None,
            "categoria": None, "status": None, "quando": None, "quando_data": None,
            "hora": None, "prazo": None, "duvida": None, "memoria": None,
        }
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/atalho/capturar", json={"text": "ligar pro dentista"})
        self.assertEqual(res.status_code, 201)

    def test_atalho_capturar_sem_texto_devolve_erro(self):
        res = self.client.post("/api/atalho/capturar", json={"text": ""})
        self.assertEqual(res.status_code, 400)

    def test_atalho_capturar_com_token_configurado_exige_token_certo(self):
        with patch.dict(os.environ, {"PAINEL_ATALHOS_TOKEN": "segredo-123"}):
            sem_token = self.client.post("/api/atalho/capturar", json={"text": "algo"})
            self.assertEqual(sem_token.status_code, 401)

            token_errado = self.client.post(
                "/api/atalho/capturar", json={"text": "algo"}, headers={"X-Webhook-Token": "errado"}
            )
            self.assertEqual(token_errado.status_code, 401)

            parsed = {
                "tipo": "tarefa", "titulo": "algo", "valor": None, "categoria": None,
                "status": None, "quando": None, "quando_data": None, "hora": None,
                "prazo": None, "duvida": None, "memoria": None,
            }
            with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
                token_certo = self.client.post(
                    "/api/atalho/capturar",
                    json={"text": "algo"},
                    headers={"X-Webhook-Token": "segredo-123"},
                )
            self.assertEqual(token_certo.status_code, 201)

    def test_atalho_cotacao_pdf_nao_exige_sessao_e_cria_cotacao(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()

        dados_extraidos = {
            "fornecedor": "Ferragens Silva", "valor": 4500.0,
            "prazo_texto": "15 dias", "observacao": None,
        }
        with patch(
            "claude_client.extrair_item_cotacao_pdf", return_value=(dados_extraidos, fake_usage())
        ):
            res = self.client.post(
                "/api/atalho/cotacao-pdf",
                data={
                    "titulo_cotacao": "ferro",
                    "arquivo": (io.BytesIO(b"%PDF-1.4 fake"), "orcamento.pdf"),
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["fornecedor"], "Ferragens Silva")

        conn = db.get_db()
        cotacoes = db.list_cotacoes(conn)
        conn.close()
        self.assertEqual(len(cotacoes), 1)
        self.assertEqual(cotacoes[0]["titulo"], "ferro")

    def test_atalho_cotacao_pdf_sem_titulo_devolve_erro(self):
        res = self.client.post(
            "/api/atalho/cotacao-pdf",
            data={"arquivo": (io.BytesIO(b"%PDF-1.4"), "orcamento.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(res.status_code, 400)

    def test_atalho_cotacao_pdf_sem_arquivo_devolve_erro(self):
        res = self.client.post(
            "/api/atalho/cotacao-pdf", data={"titulo_cotacao": "ferro"}, content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 400)

    def test_atalho_resumo_nao_exige_sessao_de_login(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.execute("INSERT INTO tasks (title) VALUES (?)", ("cotar portas",))
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo) VALUES (?, ?, 'real')", (42.0, "mercado")
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/atalho/resumo")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["tarefas_pendentes"], 1)
        self.assertEqual(body["gasto_hoje"], 42.0)
        self.assertIsNone(body["proximo_titulo"])

    def test_atalho_resumo_mostra_proximo_compromisso_do_dia(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", ("consulta", hoje, "23:59")
        )
        conn.commit()
        conn.close()

        agora_antes = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=0)
        with patch("app.datetime") as mock_dt:
            mock_dt.now.return_value = agora_antes
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.combine = datetime.combine
            res = self.client.get("/api/atalho/resumo")

        body = res.get_json()
        self.assertEqual(body["proximo_titulo"], "consulta")
        self.assertEqual(body["proximo_hora"], "23:59")

    def test_atalho_resumo_com_token_configurado_exige_token_certo(self):
        with patch.dict(os.environ, {"PAINEL_ATALHOS_TOKEN": "segredo-456"}):
            sem_token = self.client.get("/api/atalho/resumo")
            self.assertEqual(sem_token.status_code, 401)

            com_token = self.client.get("/api/atalho/resumo", headers={"X-Webhook-Token": "segredo-456"})
            self.assertEqual(com_token.status_code, 200)

    def test_atalho_resumo_traz_campos_compactos_pra_widget_de_tela_de_bloqueio(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.execute("INSERT INTO tasks (title) VALUES (?)", ("cotar portas",))
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo) VALUES (?, ?, 'real')", (42.0, "mercado")
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/atalho/resumo")
        body = res.get_json()
        self.assertEqual(body["resumo_curto"], "1 tarefa · R$ 42.00 hoje")
        self.assertIsNone(body["linha_extra"])

    def test_atalho_resumo_linha_extra_traz_proximo_compromisso(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", ("dentista", hoje, "23:59")
        )
        conn.commit()
        conn.close()

        agora_antes = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=0)
        with patch("app.datetime") as mock_dt:
            mock_dt.now.return_value = agora_antes
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.combine = datetime.combine
            res = self.client.get("/api/atalho/resumo")

        body = res.get_json()
        self.assertEqual(body["linha_extra"], "23:59 dentista")

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


class _Fase5GrupoCTestCase(unittest.TestCase):
    """Base comum pras histórias independentes do Grupo C (Fase 5)."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()
        # mesmo motivo do PainelTestCase: sem isso, todo teste que dispara
        # verificar_e_notificar ficaria dependente da hora real do relogio.
        self._silencio_patch = patch("notificacoes.dentro_do_horario_silencioso", return_value=False)
        self._silencio_patch.start()
        self.addCleanup(self._silencio_patch.stop)

    def test_smoke_secoes_novas_da_fase_5_grupo_c_estao_na_pagina(self):
        corpo = self.client.get("/").get_data(as_text=True)
        for elemento_id in (
            "diario-decisao-form",
            "lista-diario-decisoes",
            "brain-dump-form",
            "lista-brain-dump",
            "energia-botoes",
            "lista-sugestao-energia",
            "revisao-periodo-btn",
            "revisao-periodo-box",
        ):
            self.assertIn(f'id="{elemento_id}"', corpo, msg=f"elemento #{elemento_id} sumiu da pagina")


class DiarioDecisaoTestCase(_Fase5GrupoCTestCase):
    """US-C2."""

    def test_lista_vazia_no_comeco(self):
        self.assertEqual(self.client.get("/api/diario-decisoes").get_json(), [])

    def test_cria_e_lista(self):
        res = self.client.post(
            "/api/diario-decisoes",
            json={"decisao": "Trocar de corretora", "contexto": "taxa menor", "revisao_em": "2026-12-01"},
        )
        self.assertEqual(res.status_code, 201)
        decisao_id = res.get_json()["id"]

        lista = self.client.get("/api/diario-decisoes").get_json()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["id"], decisao_id)
        self.assertEqual(lista[0]["decisao"], "Trocar de corretora")
        self.assertEqual(lista[0]["contexto"], "taxa menor")
        self.assertEqual(lista[0]["revisao_em"], "2026-12-01")
        self.assertIsNone(lista[0]["resultado"])

    def test_criar_sem_decisao_da_erro(self):
        res = self.client.post("/api/diario-decisoes", json={"contexto": "sem decisao"})
        self.assertEqual(res.status_code, 400)

    def test_registra_resultado(self):
        decisao_id = self.client.post("/api/diario-decisoes", json={"decisao": "x"}).get_json()["id"]
        res = self.client.post(
            f"/api/diario-decisoes/{decisao_id}/resultado", json={"resultado": "deu certo"}
        )
        self.assertEqual(res.status_code, 200)
        lista = self.client.get("/api/diario-decisoes").get_json()
        self.assertEqual(lista[0]["resultado"], "deu certo")

    def test_registrar_resultado_sem_texto_da_erro(self):
        decisao_id = self.client.post("/api/diario-decisoes", json={"decisao": "x"}).get_json()["id"]
        res = self.client.post(f"/api/diario-decisoes/{decisao_id}/resultado", json={"resultado": ""})
        self.assertEqual(res.status_code, 400)

    def test_registrar_resultado_id_inexistente_404(self):
        res = self.client.post("/api/diario-decisoes/999/resultado", json={"resultado": "x"})
        self.assertEqual(res.status_code, 404)

    def test_apaga(self):
        decisao_id = self.client.post("/api/diario-decisoes", json={"decisao": "x"}).get_json()["id"]
        res = self.client.delete(f"/api/diario-decisoes/{decisao_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/diario-decisoes").get_json(), [])

    def test_nao_colide_com_tabela_decisoes_da_fase_1(self):
        """A tabela 'vale a pena?' (Fase 1) e o diario de decisao (Fase 5)
        sao coisas diferentes - uma nao deve afetar a outra."""
        conn = db.get_db()
        db.create_decisao(conn, "Vale a pena trocar de carro?", '{"pros": [], "contras": []}')
        conn.close()

        self.client.post("/api/diario-decisoes", json={"decisao": "Troquei de carro"})
        diario = self.client.get("/api/diario-decisoes").get_json()
        self.assertEqual(len(diario), 1)
        self.assertEqual(diario[0]["decisao"], "Troquei de carro")

        conn = db.get_db()
        antigas = db.list_decisoes(conn)
        conn.close()
        self.assertEqual(len(antigas), 1)
        self.assertEqual(antigas[0]["pergunta"], "Vale a pena trocar de carro?")

    def test_chat_tool_registrar_decisao(self):
        with patch("claude_client.client.messages.create") as mock_create:
            mock_create.return_value = _resp(
                [_tool_block("registrar_decisao", {"decisao": "Mudar de cidade", "contexto": "trabalho novo"}, "t1")],
                stop_reason="tool_use",
            )
            mock_create.side_effect = [
                _resp(
                    [_tool_block("registrar_decisao", {"decisao": "Mudar de cidade", "contexto": "trabalho novo"}, "t1")],
                    stop_reason="tool_use",
                ),
                _resp([_text_block("Registrado no diario de decisao.")]),
            ]
            res = self.client.post("/api/chat", json={"mensagem": "decidi mudar de cidade por causa do trabalho novo"})
        self.assertEqual(res.status_code, 200)
        diario = self.client.get("/api/diario-decisoes").get_json()
        self.assertEqual(len(diario), 1)
        self.assertEqual(diario[0]["decisao"], "Mudar de cidade")


class EsperaPrioridadeTestCase(_Fase5GrupoCTestCase):
    """US-C5."""

    def test_prioridade_vazia(self):
        self.assertEqual(self.client.get("/api/esperas/prioridade").get_json(), [])

    def test_ordena_por_tempo_parado_e_importancia(self):
        conn = db.get_db()
        antiga = date.today() - timedelta(days=10)
        recente = date.today() - timedelta(days=1)
        conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
            ("fornecedor antigo", "ferro", antiga.isoformat() + "T10:00:00"),
        )
        conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
            ("corretora recente", "proposta", recente.isoformat() + "T10:00:00"),
        )
        conn.commit()
        conn.close()

        resultado = self.client.get("/api/esperas/prioridade").get_json()
        self.assertEqual(resultado[0]["quem"], "fornecedor antigo")
        self.assertEqual(resultado[1]["quem"], "corretora recente")

    def test_marcar_importante_muda_prioridade(self):
        conn = db.get_db()
        antiga = date.today() - timedelta(days=5)
        recente = date.today() - timedelta(days=2)
        conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
            ("fornecedor antigo", "ferro", antiga.isoformat() + "T10:00:00"),
        )
        cur = conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
            ("corretora recente", "proposta", recente.isoformat() + "T10:00:00"),
        )
        recente_id = cur.lastrowid
        conn.commit()
        conn.close()

        res = self.client.post(f"/api/esperas/{recente_id}/importante", json={"importante": True})
        self.assertEqual(res.status_code, 200)

        resultado = self.client.get("/api/esperas/prioridade").get_json()
        self.assertEqual(resultado[0]["quem"], "corretora recente")

    def test_marcar_importante_id_inexistente_404(self):
        res = self.client.post("/api/esperas/999/importante", json={"importante": True})
        self.assertEqual(res.status_code, 404)


class BrainDumpTestCase(_Fase5GrupoCTestCase):
    """US-C6."""

    def test_captura_e_lista(self):
        res = self.client.post("/api/brain-dump", json={"texto": "ideia solta qualquer"})
        self.assertEqual(res.status_code, 201)
        lista = self.client.get("/api/brain-dump").get_json()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["texto"], "ideia solta qualquer")
        self.assertEqual(lista[0]["processado"], 0)

    def test_captura_sem_texto_da_erro(self):
        res = self.client.post("/api/brain-dump", json={"texto": "  "})
        self.assertEqual(res.status_code, 400)

    def test_converter_em_tarefa(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "levar carro na revisao"}).get_json()["id"]
        res = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "tarefa"})
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["tipo"], "tarefa")

        tarefas = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tarefas), 1)
        self.assertEqual(tarefas[0]["title"], "levar carro na revisao")

        # some da lista de pendentes depois de convertido
        self.assertEqual(self.client.get("/api/brain-dump").get_json(), [])

    def test_converter_em_nota(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "lembrar de pesquisar sobre X"}).get_json()["id"]
        res = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "nota", "titulo": "pesquisa X"})
        self.assertEqual(res.status_code, 200)
        notas = self.client.get("/api/notas").get_json()
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["titulo"], "pesquisa X")

    def test_converter_em_gasto(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "gastei uns 30 reais no mercado"}).get_json()["id"]
        res = self.client.post(
            f"/api/brain-dump/{item_id}/converter",
            json={"tipo": "gasto", "valor": 30.0, "categoria": "mercado"},
        )
        self.assertEqual(res.status_code, 200)
        gastos = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(gastos), 1)
        self.assertEqual(gastos[0]["amount"], 30.0)

    def test_converter_gasto_sem_valor_da_erro(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "x"}).get_json()["id"]
        res = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "gasto"})
        self.assertEqual(res.status_code, 400)

    def test_converter_tipo_invalido_da_erro(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "x"}).get_json()["id"]
        res = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "lixo"})
        self.assertEqual(res.status_code, 400)

    def test_converter_item_inexistente_404(self):
        res = self.client.post("/api/brain-dump/999/converter", json={"tipo": "nota"})
        self.assertEqual(res.status_code, 404)

    def test_converter_item_ja_processado_da_erro(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "x"}).get_json()["id"]
        self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "nota"})
        res = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "nota"})
        self.assertEqual(res.status_code, 400)

    def test_apaga_sem_converter(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "descartar"}).get_json()["id"]
        res = self.client.delete(f"/api/brain-dump/{item_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/brain-dump").get_json(), [])


class RevisaoPeriodoTestCase(_Fase5GrupoCTestCase):
    """US-C3."""

    def test_trimestre_atual_por_padrao(self):
        res = self.client.get("/api/revisao-periodo")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["tipo"], "trimestre")
        self.assertEqual(body["ano"], date.today().year)
        self.assertIn("tarefas_feitas", body)
        self.assertIn("gasto_total", body)
        self.assertIn("decisoes", body)

    def test_trimestre_especifico_agrega_gasto_e_tarefas(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo, created_at) VALUES (?, ?, 'real', ?)",
            (100.0, "mercado", "2026-02-10 10:00:00"),
        )
        conn.execute(
            "INSERT INTO tasks (title, completed_at) VALUES (?, ?)", ("feita no Q1", "2026-02-15 10:00:00")
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/revisao-periodo?tipo=trimestre&ano=2026&trimestre=1")
        body = res.get_json()
        self.assertEqual(body["gasto_total"], 100.0)
        self.assertEqual(body["tarefas_feitas"], 1)
        self.assertEqual(body["inicio"], "2026-01-01")
        self.assertEqual(body["fim"], "2026-03-31")

    def test_inclui_decisoes_do_diario_no_periodo(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO diario_decisoes (decisao, data) VALUES (?, ?)", ("decisao Q1", "2026-02-01")
        )
        conn.execute(
            "INSERT INTO diario_decisoes (decisao, data) VALUES (?, ?)", ("decisao Q3", "2026-08-01")
        )
        conn.commit()
        conn.close()

        res = self.client.get("/api/revisao-periodo?tipo=trimestre&ano=2026&trimestre=1")
        body = res.get_json()
        self.assertEqual(len(body["decisoes"]), 1)
        self.assertEqual(body["decisoes"][0]["decisao"], "decisao Q1")

    def test_tipo_ano(self):
        res = self.client.get("/api/revisao-periodo?tipo=ano&ano=2026")
        body = res.get_json()
        self.assertEqual(body["inicio"], "2026-01-01")
        self.assertEqual(body["fim"], "2026-12-31")
        self.assertIsNone(body["trimestre"])

    def test_tipo_invalido_da_erro(self):
        res = self.client.get("/api/revisao-periodo?tipo=semana")
        self.assertEqual(res.status_code, 400)

    def test_trimestre_invalido_da_erro(self):
        res = self.client.get("/api/revisao-periodo?tipo=trimestre&trimestre=9")
        self.assertEqual(res.status_code, 400)

    def test_ano_fora_de_faixa_da_erro(self):
        res = self.client.get("/api/revisao-periodo?tipo=ano&ano=1500")
        self.assertEqual(res.status_code, 400)


class NotificacaoAgrupadaTestCase(_Fase5GrupoCTestCase):
    """US-C4 - desligado por padrao (ver PainelTestCase/config tests pra
    confirmar que o comportamento antigo, sem agrupar, continua intacto)."""

    def _ligar_agrupamento(self, janela_min=2):
        res = self.client.post(
            "/api/configuracoes/silencio",
            json={"inicio": "22:00", "fim": "07:00", "agrupar": True, "agrupar_janela_min": janela_min},
        )
        self.assertEqual(res.status_code, 200)

    def _forcar_janela_vencida(self, minutos_atras=5):
        """Reescreve o 'inicio' guardado da fila de agrupamento pra simular
        que a janela ja passou, sem precisar mockar datetime em varios
        modulos diferentes."""
        conn = db.get_db()
        guardado = json.loads(db.obter_configuracao(conn, "notificacoes_agrupadas_fila") or "{}")
        self.assertTrue(guardado.get("itens"), msg="fila deveria ter pelo menos um item enfileirado")
        guardado["inicio"] = (datetime.now() - timedelta(minutes=minutos_atras)).isoformat()
        db.definir_configuracao(conn, "notificacoes_agrupadas_fila", json.dumps(guardado))
        conn.commit()
        conn.close()

    def _duas_condicoes_nao_urgentes(self):
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("responder a corretora", tres_dias)
        )
        conn.execute("INSERT INTO orcamentos (categoria, valor_limite) VALUES ('mercado', 100)")
        conn.execute(
            "INSERT INTO expenses (amount, category, tipo) VALUES (110, 'mercado', 'real')"
        )
        conn.commit()
        conn.close()

    def _horario_seguro(self):
        """14h de uma quarta-feira - fora de qualquer janela de horario fixo
        que o modulo dispara sozinho (rotina da manha 07:00, planejamento
        semanal so aos domingos 20:30, hora de dormir 22:00, fechamento
        21:00) - sem isso, o teste ficaria sujeito a coincidir com uma
        dessas janelas dependendo de que horas ele realmente roda."""
        return datetime(2026, 9, 23, 14, 0)

    def test_desligado_por_padrao_manda_cada_aviso_separado(self):
        self._duas_condicoes_nao_urgentes()
        sub = {"endpoint": "https://exemplo.com/agrupado-off", "keys": {"p256dh": "x", "auth": "y"}}
        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar, patch("app.datetime") as mock_dt:
            mock_dt.now.return_value = self._horario_seguro()
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.combine = datetime.combine
            self.client.post("/api/push/inscrever", json=sub)
            res = self.client.post("/api/notificacoes/verificar-agora")
        # tarefa 3 dias atrasada dispara 2 avisos (o generico + a cobranca
        # nominal) mais o orcamento estourado = 3, cada um seu proprio push.
        self.assertEqual(res.get_json()["avisos_enviados"], 3)
        self.assertEqual(mock_enviar.call_count, 3)

    def test_ligado_segura_ate_a_janela_passar_e_agrupa(self):
        self._ligar_agrupamento(janela_min=2)
        self._duas_condicoes_nao_urgentes()
        sub = {"endpoint": "https://exemplo.com/agrupado-on", "keys": {"p256dh": "x", "auth": "y"}}
        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar, patch("app.datetime") as mock_dt:
            mock_dt.now.return_value = self._horario_seguro()
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.combine = datetime.combine
            self.client.post("/api/push/inscrever", json=sub)

            primeiro = self.client.post("/api/notificacoes/verificar-agora")
            self.assertEqual(primeiro.get_json()["avisos_enviados"], 0)
            mock_enviar.assert_not_called()

            self._forcar_janela_vencida(minutos_atras=5)

            segundo = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(segundo.get_json()["avisos_enviados"], 3)
        mock_enviar.assert_called_once()
        corpo_enviado = mock_enviar.call_args[0][2]
        self.assertIn("responder a corretora", corpo_enviado)
        self.assertIn("mercado", corpo_enviado)
        titulo_enviado = mock_enviar.call_args[0][1]
        self.assertEqual(titulo_enviado, "3 avisos")

    def test_urgente_nunca_agrupa_mesmo_ligado(self):
        self._ligar_agrupamento(janela_min=2)
        hoje = date.today().isoformat()
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", ("reuniao", hoje, "00:05")
        )
        conn.commit()
        conn.close()

        sub = {"endpoint": "https://exemplo.com/agrupado-urgente", "keys": {"p256dh": "x", "auth": "y"}}
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=0, minute=0)
        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar, patch("app.datetime") as mock_dt:
            mock_dt.now.return_value = agora
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.combine = datetime.combine
            self.client.post("/api/push/inscrever", json=sub)
            res = self.client.post("/api/notificacoes/verificar-agora")

        self.assertEqual(res.get_json()["avisos_enviados"], 1)
        mock_enviar.assert_called_once()
        self.assertIn("reuniao", mock_enviar.call_args[0][2])


class SugestaoEnergiaTestCase(_Fase5GrupoCTestCase):
    """US-C7."""

    def test_definir_esforco_e_sugestao_filtra(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('tarefa leve')")
        conn.execute("INSERT INTO tasks (title) VALUES ('tarefa pesada')")
        conn.commit()
        ids = [r["id"] for r in conn.execute("SELECT id FROM tasks ORDER BY id").fetchall()]
        conn.close()
        leve_id, pesada_id = ids

        self.client.post(f"/api/tasks/{leve_id}/esforco", json={"esforco": "baixa"})
        self.client.post(f"/api/tasks/{pesada_id}/esforco", json={"esforco": "alta"})

        baixa = self.client.get("/api/tarefas/sugestao-energia?nivel=baixa").get_json()
        self.assertEqual([t["id"] for t in baixa], [leve_id])

        alta = self.client.get("/api/tarefas/sugestao-energia?nivel=alta").get_json()
        self.assertEqual(sorted(t["id"] for t in alta), sorted([leve_id, pesada_id]))

    def test_definir_esforco_invalido_da_erro(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('x')")
        conn.commit()
        task_id = conn.execute("SELECT id FROM tasks").fetchone()["id"]
        conn.close()
        res = self.client.post(f"/api/tasks/{task_id}/esforco", json={"esforco": "lixo"})
        self.assertEqual(res.status_code, 400)

    def test_definir_esforco_tarefa_inexistente_404(self):
        res = self.client.post("/api/tasks/999/esforco", json={"esforco": "baixa"})
        self.assertEqual(res.status_code, 404)

    def test_sugestao_nivel_invalido_da_erro(self):
        res = self.client.get("/api/tarefas/sugestao-energia?nivel=lixo")
        self.assertEqual(res.status_code, 400)

    def test_sugestao_sem_nivel_da_erro(self):
        res = self.client.get("/api/tarefas/sugestao-energia")
        self.assertEqual(res.status_code, 400)

    def test_tarefa_sem_esforco_definido_entra_na_media(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('sem classificacao')")
        conn.commit()
        conn.close()
        media = self.client.get("/api/tarefas/sugestao-energia?nivel=media").get_json()
        self.assertEqual(len(media), 1)
        baixa = self.client.get("/api/tarefas/sugestao-energia?nivel=baixa").get_json()
        self.assertEqual(baixa, [])


if __name__ == "__main__":
    unittest.main()
