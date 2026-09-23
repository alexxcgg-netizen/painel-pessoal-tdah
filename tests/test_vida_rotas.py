"""Rotas, scheduler e chat das funcionalidades do BRIEFING.md (Fase 1)."""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
_CAMINHO_TESTE = Path(_tmp_dir.name) / "vida.db"
db.DB_PATH = _CAMINHO_TESTE

import app  # noqa: E402
import claude_client  # noqa: E402
import vida  # noqa: E402

PIN = "123456"


def fake_usage(model=claude_client.HAIKU):
    return {"model": model, "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0001}


class VidaBaseTestCase(unittest.TestCase):
    def setUp(self):
        self._caminho_original = db.DB_PATH
        db.DB_PATH = _CAMINHO_TESTE
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        app._CACHE_CONSTRUTORA.clear()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN})
        assert res.status_code == 200, res.get_json()
        silencio = patch("notificacoes.dentro_do_horario_silencioso", return_value=False)
        silencio.start()
        self.addCleanup(silencio.stop)
        self.addCleanup(self._restaurar_db)

    def _restaurar_db(self):
        db.DB_PATH = self._caminho_original

    def _conn(self):
        conn = db.get_db()
        self.addCleanup(conn.close)
        return conn

    def _tarefa(self, titulo, due=None, hora=None, criado=None):
        conn = self._conn()
        if criado:
            cur = conn.execute(
                "INSERT INTO tasks (title, due_date, hora, created_at) VALUES (?, ?, ?, ?)",
                (titulo, due, hora, criado),
            )
        else:
            cur = conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", (titulo, due, hora))
        conn.commit()
        return cur.lastrowid

    def _notificar(self):
        """Roda o scheduler com um canal de push fake e devolve os corpos enviados."""
        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as enviar:
            self.client.post("/api/push/inscrever", json={"endpoint": "https://exemplo.com/sub", "keys": {}})
            self.client.post("/api/notificacoes/verificar-agora")
        return [c.args[2] for c in enviar.call_args_list]


class CheckinTestCase(VidaBaseTestCase):
    def test_hoje_comeca_vazio(self):
        self.assertIsNone(self.client.get("/api/checkin/hoje").get_json()["checkin"])

    def test_um_toque_de_cada_vez(self):
        r = self.client.post("/api/checkin", json={"energia": "ruim"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["checkin"], {"energia": "ruim", "sono": None, "humor": None})
        self.client.post("/api/checkin", json={"humor": "bom"})
        self.client.post("/api/checkin", json={"energia": "ok"})
        self.assertEqual(
            self.client.get("/api/checkin/hoje").get_json()["checkin"],
            {"energia": "ok", "sono": None, "humor": "bom"},
        )

    def test_rejeita_entrada_invalida(self):
        for corpo in [{}, {"energia": "otimo"}, {"sono": 7}, {"humor": True}, {"outra": "bom"}, [], "x"]:
            r = self.client.post("/api/checkin", json=corpo)
            self.assertEqual(r.status_code, 400, msg=repr(corpo))
        self.assertIsNone(self.client.get("/api/checkin/hoje").get_json()["checkin"])

    def test_chat_registra_checkin(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertEqual(executores["registrar_checkin"]({"sono": "ruim", "energia": "ruim"}), {"ok": True})
            self.assertIn("erro", executores["registrar_checkin"]({"sono": "pessimo"}))
            return "Anotado.", ["registrar_checkin"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "dormi mal e to sem energia"})
        self.assertEqual(self.client.get("/api/checkin/hoje").get_json()["checkin"]["sono"], "ruim")


class RotinaTestCase(VidaBaseTestCase):
    def test_itens_padrao_semeados(self):
        manha = self.client.get("/api/rotina?momento=manha").get_json()
        noite = self.client.get("/api/rotina?momento=noite").get_json()
        self.assertEqual(manha["total"], 4)
        self.assertEqual(noite["total"], 3)
        self.assertEqual(manha["feitos"], 0)

    def test_marcar_e_desmarcar(self):
        item = self.client.get("/api/rotina?momento=manha").get_json()["itens"][0]
        self.assertTrue(self.client.post(f"/api/rotina/{item['id']}/alternar").get_json()["feito"])
        self.assertEqual(self.client.get("/api/rotina?momento=manha").get_json()["feitos"], 1)
        self.assertFalse(self.client.post(f"/api/rotina/{item['id']}/alternar").get_json()["feito"])
        self.assertEqual(self.client.get("/api/rotina?momento=manha").get_json()["feitos"], 0)

    def test_criar_e_apagar_item(self):
        r = self.client.post("/api/rotina/itens", json={"momento": "noite", "texto": "Separar a roupa"})
        self.assertEqual(r.status_code, 201)
        textos = [i["texto"] for i in self.client.get("/api/rotina?momento=noite").get_json()["itens"]]
        self.assertEqual(textos[-1], "Separar a roupa")
        self.client.delete(f"/api/rotina/itens/{r.get_json()['id']}")
        self.assertEqual(self.client.get("/api/rotina?momento=noite").get_json()["total"], 3)

    def test_validacoes(self):
        self.assertEqual(self.client.get("/api/rotina?momento=tarde").status_code, 400)
        self.assertEqual(self.client.post("/api/rotina/999/alternar").status_code, 404)
        for corpo in [{"momento": "tarde", "texto": "x"}, {"momento": "manha", "texto": "  "},
                      {"momento": "manha", "texto": "x" * 121}, {}]:
            self.assertEqual(self.client.post("/api/rotina/itens", json=corpo).status_code, 400, msg=repr(corpo))

    def test_push_da_manha_lista_os_itens(self):
        with patch("vida.rotina_manha_devida", return_value=True):
            corpos = self._notificar()
        manha = [c for c in corpos if c.startswith("Bom dia")]
        self.assertEqual(len(manha), 1)
        self.assertIn("beber um copo de agua", manha[0])
        with patch("vida.rotina_manha_devida", return_value=True):
            self.assertFalse([c for c in self._notificar() if c.startswith("Bom dia")])

    def test_push_das_22h_inclui_rotina_da_noite(self):
        with patch("notificacoes.hora_de_dormir_devida", return_value=True):
            corpos = self._notificar()
        noite = [c for c in corpos if c.startswith("22h")]
        self.assertEqual(len(noite), 1)
        self.assertIn("celular longe da cama", noite[0])


class HiperfocoTestCase(VidaBaseTestCase):
    def test_liga_consulta_e_encerra(self):
        self.assertFalse(self.client.get("/api/hiperfoco").get_json()["ativo"])
        estado = self.client.post("/api/hiperfoco", json={"minutos": 50}).get_json()
        self.assertTrue(estado["ativo"])
        self.assertIn(estado["minutos_restantes"], (49, 50))
        self.assertFalse(self.client.delete("/api/hiperfoco").get_json()["ativo"])
        self.assertFalse(self.client.get("/api/hiperfoco").get_json()["ativo"])

    def test_duracao_invalida(self):
        for minutos in [0, 10, 60, "50", None, True, 50.5]:
            self.assertEqual(self.client.post("/api/hiperfoco", json={"minutos": minutos}).status_code, 400)

    def test_segura_aviso_nao_critico_e_deixa_passar_critico(self):
        conn = self._conn()
        amanha = (date.today() + timedelta(days=1)).day
        db.create_conta_pessoal(conn, "Internet", amanha, 100.0)
        self.client.post("/api/hiperfoco", json={"minutos": 90})
        with patch("notificacoes.tarefas_com_horario_chegando", return_value=[(77, "Remedio agora")]):
            corpos = self._notificar()
        self.assertIn("Remedio agora", corpos)
        self.assertFalse([c for c in corpos if "Internet" in c])
        # acabou o foco: o aviso segurado sai na proxima rodada (nao foi perdido)
        self.client.delete("/api/hiperfoco")
        self.assertTrue([c for c in self._notificar() if "Internet" in c])

    def test_avisa_quando_o_bloco_acaba_uma_vez(self):
        conn = self._conn()
        passou = (datetime.now() - timedelta(minutes=2)).isoformat(timespec="seconds")
        db.definir_configuracao(conn, "hiperfoco_ate", passou)
        db.definir_configuracao(conn, "hiperfoco_minutos", "25")
        corpos = self._notificar()
        self.assertTrue([c for c in corpos if "bloco de foco de 25 min acabou" in c])
        self.assertFalse([c for c in self._notificar() if "bloco de foco" in c])

    def test_fim_muito_antigo_nao_avisa(self):
        conn = self._conn()
        db.definir_configuracao(conn, "hiperfoco_ate", (datetime.now() - timedelta(hours=5)).isoformat())
        self.assertFalse([c for c in self._notificar() if "bloco de foco" in c])

    def test_chat_liga_hiperfoco(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            r = executores["iniciar_hiperfoco"]({"minutos": 25})
            self.assertTrue(r["ok"])
            return "Foco ligado.", ["iniciar_hiperfoco"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "vou focar 25 minutos"})
        self.assertTrue(self.client.get("/api/hiperfoco").get_json()["ativo"])


class EssencialTestCase(VidaBaseTestCase):
    def test_ia_escolhe_e_fica_estavel_no_dia(self):
        hoje = date.today().isoformat()
        a = self._tarefa("Pagar IPVA", due=hoje)
        b = self._tarefa("Organizar garagem")
        with patch("claude_client.escolher_essencial", return_value=([{"id": b, "motivo": "ta travando"}, {"id": a}], fake_usage())) as ia:
            r1 = self.client.get("/api/essencial").get_json()
            r2 = self.client.get("/api/essencial").get_json()
        self.assertEqual(ia.call_count, 1)
        self.assertEqual([t["id"] for t in r1["tarefas"]], [b, a])
        self.assertEqual(r1["tarefas"][0]["motivo"], "ta travando")
        self.assertEqual(r1, r2)

    def test_ia_falha_ou_inventa_id_cai_na_heuristica(self):
        hoje = date.today().isoformat()
        a = self._tarefa("Hoje com hora", due=hoje, hora="15:00")
        self._tarefa("Sem prazo")
        with patch("claude_client.escolher_essencial", side_effect=ValueError("json ruim")):
            r = self.client.get("/api/essencial").get_json()
        self.assertEqual(r["tarefas"][0]["id"], a)
        with patch("claude_client.escolher_essencial", return_value=([{"id": 99999}, "lixo", {"motivo": "x"}], fake_usage())):
            r = self.client.post("/api/essencial/gerar").get_json()
        self.assertEqual(r["tarefas"][0]["id"], a)

    def test_ia_nunca_passa_de_3(self):
        ids = [self._tarefa(f"t{i}") for i in range(6)]
        with patch("claude_client.escolher_essencial", return_value=([{"id": i} for i in ids], fake_usage())):
            r = self.client.get("/api/essencial").get_json()
        self.assertEqual(len(r["tarefas"]), 3)

    def test_sem_tarefa_lista_vazia(self):
        with patch("claude_client.escolher_essencial") as ia:
            self.assertEqual(self.client.get("/api/essencial").get_json()["tarefas"], [])
        ia.assert_not_called()

    def test_trocar_repoe_com_proxima(self):
        ids = [self._tarefa(f"t{i}") for i in range(4)]
        with patch("claude_client.escolher_essencial", side_effect=ValueError):
            escolhidas = [t["id"] for t in self.client.get("/api/essencial").get_json()["tarefas"]]
        r = self.client.post("/api/essencial/trocar", json={"task_id": escolhidas[0]}).get_json()
        novas = [t["id"] for t in r["tarefas"]]
        self.assertNotIn(escolhidas[0], novas)
        self.assertEqual(len(novas), 3)
        self.assertEqual(set(novas) | {escolhidas[0]}, set(ids))
        for ruim in [{"task_id": 424242}, {"task_id": True}, {}, {"task_id": "1"}]:
            self.assertEqual(self.client.post("/api/essencial/trocar", json=ruim).status_code, 400)

    def test_concluida_aparece_como_feita(self):
        a = self._tarefa("Pagar IPVA", due=date.today().isoformat())
        with patch("claude_client.escolher_essencial", side_effect=ValueError):
            self.client.get("/api/essencial")
        self.client.post(f"/api/tasks/{a}/complete")
        t = self.client.get("/api/essencial").get_json()["tarefas"][0]
        self.assertTrue(t["feita"])

    def test_modo_foco_vale_so_pro_dia(self):
        with patch("claude_client.escolher_essencial", side_effect=ValueError):
            self.assertFalse(self.client.get("/api/essencial").get_json()["modo_ativo"])
            self.assertTrue(self.client.post("/api/essencial/modo", json={"ativo": True}).get_json()["modo_ativo"])
            self.assertTrue(self.client.get("/api/essencial").get_json()["modo_ativo"])
            conn = self._conn()
            db.definir_configuracao(conn, "modo_essencial_data", "2020-01-01")
            self.assertFalse(self.client.get("/api/essencial").get_json()["modo_ativo"])
            self.assertFalse(self.client.post("/api/essencial/modo", json={"ativo": "sim"}).get_json()["modo_ativo"])


class TarefaEmpacadaTestCase(VidaBaseTestCase):
    def test_listagem_marca_travada(self):
        velha = (date.today() - timedelta(days=5)).isoformat()
        a = self._tarefa("Renovar seguro", due=velha)
        b = self._tarefa("Nova")
        por_id = {t["id"]: t for t in self.client.get("/api/tasks").get_json()}
        self.assertEqual(por_id[a]["empacada_dias"], 5)
        self.assertIsNone(por_id[b]["empacada_dias"])

    def test_requebrar_troca_so_os_passos_nao_feitos(self):
        velha = (date.today() - timedelta(days=5)).isoformat()
        a = self._tarefa("Renovar seguro", due=velha)
        conn = self._conn()
        conn.execute("INSERT INTO subtasks (task_id, title, position, completed_at) VALUES (?, 'feito', 0, datetime('now'))", (a,))
        conn.execute("INSERT INTO subtasks (task_id, title, position) VALUES (?, 'velho', 1)", (a,))
        conn.commit()
        with patch("claude_client.requebrar_tarefa", return_value=(["Abrir o site (2 min)", " ", "Ligar"], fake_usage())) as ia:
            r = self.client.post(f"/api/tasks/{a}/requebrar")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ia.call_args.args, ("Renovar seguro", 5, ["velho"]))
        self.assertEqual([s["title"] for s in r.get_json()["subtasks"]], ["feito", "Abrir o site (2 min)", "Ligar"])

    def test_requebrar_erros(self):
        self.assertEqual(self.client.post("/api/tasks/999/requebrar").status_code, 404)
        a = self._tarefa("x")
        with patch("claude_client.requebrar_tarefa", return_value=({"nao": "lista"}, fake_usage())):
            self.assertEqual(self.client.post(f"/api/tasks/{a}/requebrar").status_code, 502)
        with patch("claude_client.requebrar_tarefa", side_effect=ValueError):
            self.assertEqual(self.client.post(f"/api/tasks/{a}/requebrar").status_code, 502)

    def test_push_de_tarefa_parada_oferece_quebrar(self):
        self._tarefa("Renovar seguro", due=(date.today() - timedelta(days=10)).isoformat())
        corpos = self._notificar()
        self.assertTrue([c for c in corpos if "quebrar de outro jeito" in c])


class ContasPessoaisTestCase(VidaBaseTestCase):
    def test_crud_e_status(self):
        dia = (date.today() + timedelta(days=2)).day
        r = self.client.post("/api/contas-pessoais", json={"nome": "Internet", "dia_vencimento": dia, "valor": 119.9})
        self.assertEqual(r.status_code, 201)
        conta = self.client.get("/api/contas-pessoais").get_json()[0]
        self.assertEqual(conta["nome"], "Internet")
        self.assertFalse(conta["paga"])
        self.assertEqual(conta["proximo_vencimento"], vida.proximo_vencimento(dia, date.today()).isoformat())
        self.client.post(f"/api/contas-pessoais/{conta['id']}/paga")
        self.assertTrue(self.client.get("/api/contas-pessoais").get_json()[0]["paga"])
        self.client.delete(f"/api/contas-pessoais/{conta['id']}")
        self.assertEqual(self.client.get("/api/contas-pessoais").get_json(), [])

    def test_validacoes(self):
        ruins = [
            {"nome": "", "dia_vencimento": 5},
            {"nome": "Luz", "dia_vencimento": 0},
            {"nome": "Luz", "dia_vencimento": 32},
            {"nome": "Luz", "dia_vencimento": "dez"},
            {"nome": "Luz", "dia_vencimento": True},
            {"nome": "Luz", "dia_vencimento": 5.5},
            {"nome": "Luz", "dia_vencimento": 5, "valor": "muito"},
            {"nome": "Luz", "dia_vencimento": 5, "valor": -10},
            {"nome": "Luz", "dia_vencimento": 5, "valor": True},
            {"nome": "x" * 81, "dia_vencimento": 5},
        ]
        for corpo in ruins:
            self.assertEqual(self.client.post("/api/contas-pessoais", json=corpo).status_code, 400, msg=repr(corpo))
        self.assertEqual(self.client.post("/api/contas-pessoais/999/paga").status_code, 404)
        ok = self.client.post("/api/contas-pessoais", json={"nome": "Luz", "dia_vencimento": "10", "valor": ""})
        self.assertEqual(ok.status_code, 201)

    def test_avisa_3_dias_antes_e_no_dia_uma_vez_cada(self):
        conn = self._conn()
        em_3 = date.today() + timedelta(days=3)
        conta_id = db.create_conta_pessoal(conn, "Luz", em_3.day, None)
        corpos = self._notificar()
        self.assertTrue([c for c in corpos if c.startswith("Luz vence em 3 dia(s)")])
        self.assertFalse([c for c in self._notificar() if c.startswith("Luz")])
        db.marcar_conta_paga(conn, conta_id, vida.proximo_vencimento(em_3.day, date.today()).isoformat())
        conn.execute("DELETE FROM notificacoes_enviadas")
        conn.commit()
        self.assertFalse([c for c in self._notificar() if c.startswith("Luz")])

    def test_chat_cadastra_conta(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertTrue(executores["registrar_conta_pessoal"]({"nome": "Cartao", "dia_vencimento": 15})["ok"])
            self.assertIn("erro", executores["registrar_conta_pessoal"]({"nome": "Cartao", "dia_vencimento": 40}))
            return "Anotado.", ["registrar_conta_pessoal"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "meu cartao vence todo dia 15"})
        self.assertEqual([c["nome"] for c in self.client.get("/api/contas-pessoais").get_json()], ["Cartao"])


class AssinaturasTestCase(VidaBaseTestCase):
    def _netflix(self):
        conn = self._conn()
        hoje = date.today()
        for meses in (1, 2):
            dia = (hoje.replace(day=5) - timedelta(days=31 * meses)).isoformat()
            conn.execute(
                "INSERT INTO expenses (amount, category, description, created_at, tipo) "
                "VALUES (39.9, 'lazer', 'Netflix', ?, 'real')",
                (dia + " 10:00:00",),
            )
        conn.commit()

    def test_pergunta_uma_vez_por_mes(self):
        self._netflix()
        pendentes = self.client.get("/api/assinaturas/revisao").get_json()
        self.assertEqual([p["descricao"] for p in pendentes], ["Netflix"])
        r = self.client.post("/api/assinaturas/revisao", json={"descricao": "Netflix", "valor": 39.9, "resposta": "usa"})
        self.assertIsNone(r.get_json()["tarefa_id"])
        self.assertEqual(self.client.get("/api/assinaturas/revisao").get_json(), [])

    def test_nao_uso_cria_tarefa_e_nunca_mais_pergunta(self):
        self._netflix()
        r = self.client.post("/api/assinaturas/revisao", json={"descricao": "Netflix", "resposta": "nao_usa"})
        tarefa_id = r.get_json()["tarefa_id"]
        titulos = {t["id"]: t["title"] for t in self.client.get("/api/tasks").get_json()}
        self.assertEqual(titulos[tarefa_id], "Cancelar assinatura: Netflix")
        conn = self._conn()
        conn.execute("UPDATE assinaturas_revisao SET ano_mes = '2000-01'")
        conn.commit()
        self.assertEqual(self.client.get("/api/assinaturas/revisao").get_json(), [])

    def test_validacoes(self):
        for corpo in [{}, {"descricao": "Netflix"}, {"descricao": "Netflix", "resposta": "talvez"},
                      {"descricao": "", "resposta": "usa"}, {"descricao": 5, "resposta": "usa"},
                      {"descricao": "x" * 201, "resposta": "usa"}]:
            self.assertEqual(self.client.post("/api/assinaturas/revisao", json=corpo).status_code, 400, msg=repr(corpo))

    def test_push_mensal_com_contagem(self):
        self._netflix()
        with patch("app.datetime") as dt:
            dt.now.return_value = datetime.combine(date.today(), datetime.min.time()).replace(hour=11)
            dt.fromisoformat = datetime.fromisoformat
            corpos = self._notificar()
        self.assertTrue([c for c in corpos if c.startswith("1 assinatura(s) pra confirmar")])


class PessoasTestCase(VidaBaseTestCase):
    def test_crud_e_falei_hoje(self):
        r = self.client.post("/api/pessoas", json={"nome": "Mae", "frequencia_dias": 7})
        self.assertEqual(r.status_code, 201)
        pid = r.get_json()["id"]
        p = self.client.get("/api/pessoas").get_json()[0]
        self.assertIsNone(p["dias_sem_falar"])
        self.client.post(f"/api/pessoas/{pid}/falei", json={"sobre": "almoco de domingo"})
        p = self.client.get("/api/pessoas").get_json()[0]
        self.assertEqual(p["dias_sem_falar"], 0)
        self.assertEqual(p["ultima_conversa"], "almoco de domingo")
        self.assertEqual(len(self.client.get(f"/api/conversas?pessoa_id={pid}").get_json()), 1)
        self.client.delete(f"/api/pessoas/{pid}")
        self.assertEqual(self.client.get("/api/pessoas").get_json(), [])
        self.assertEqual(len(self.client.get("/api/conversas").get_json()), 1)

    def test_validacoes(self):
        for corpo in [{"nome": ""}, {"nome": "x" * 61}, {"nome": "Mae", "frequencia_dias": 0},
                      {"nome": "Mae", "frequencia_dias": 400}, {"nome": "Mae", "frequencia_dias": "semana"},
                      {"nome": 7}, {}]:
            self.assertEqual(self.client.post("/api/pessoas", json=corpo).status_code, 400, msg=repr(corpo))
        self.assertEqual(self.client.post("/api/pessoas/999/falei", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/pessoas", json={"nome": "Joao"}).status_code, 201)
        self.assertEqual(self.client.get("/api/pessoas").get_json()[0]["frequencia_dias"], 14)

    def test_avisa_faz_tempo_uma_vez_por_ciclo(self):
        conn = self._conn()
        pid = db.create_pessoa(conn, "Mae", 7)
        db.registrar_conversa(conn, pid, "Mae", None, (date.today() - timedelta(days=9)).isoformat())
        self.assertTrue([c for c in self._notificar() if c == "Faz 9 dias que voce nao fala com Mae."])
        self.assertFalse([c for c in self._notificar() if "Mae" in c])
        self.client.post(f"/api/pessoas/{pid}/falei", json={})
        self.assertFalse([c for c in self._notificar() if "Mae" in c])

    def test_chat_registra_conversa_e_cadastra(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertEqual(executores["cadastrar_pessoa"]({"nome": "Mãe", "frequencia_dias": 7}), {"ok": True, "atualizada": False, "frequencia_dias": 7})
            self.assertTrue(executores["cadastrar_pessoa"]({"nome": "mae", "frequencia_dias": 5})["atualizada"])
            r = executores["registrar_conversa"]({"pessoa": "mae", "sobre": "viagem"})
            self.assertEqual(r["pessoa_da_lista"], "Mãe")
            r = executores["registrar_conversa"]({"pessoa": "Carlos"})
            self.assertIsNone(r["pessoa_da_lista"])
            self.assertIn("erro", executores["registrar_conversa"]({"pessoa": " "}))
            return "Anotado.", ["registrar_conversa"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "falei com a mae sobre a viagem"})
        pessoas = self.client.get("/api/pessoas").get_json()
        self.assertEqual(len(pessoas), 1)
        self.assertEqual(pessoas[0]["frequencia_dias"], 5)
        self.assertEqual(pessoas[0]["dias_sem_falar"], 0)
        self.assertEqual(len(self.client.get("/api/conversas").get_json()), 2)


class DataImportanteTestCase(VidaBaseTestCase):
    def test_aniversario_ganha_sugestao(self):
        conn = self._conn()
        em_2 = (date.today() + timedelta(days=2)).isoformat()
        db.create_lembrete(conn, "Aniversario da Mae", em_2, recorrente=True)
        db.create_lembrete(conn, "Seguro do carro", em_2)
        por_titulo = {l["titulo"]: l for l in self.client.get("/api/lembretes").get_json()}
        self.assertIsNotNone(por_titulo["Aniversario da Mae"]["sugestao"])
        self.assertIsNone(por_titulo["Seguro do carro"]["sugestao"])
        corpos = self._notificar()
        self.assertTrue([c for c in corpos if "Aniversario" in c and "mandar uma mensagem" in c])
        self.assertTrue([c for c in corpos if "Seguro" in c and "mandar" not in c])


class DecisaoTestCase(VidaBaseTestCase):
    def test_analisa_e_guarda(self):
        analise = {"resumo": "Trocar o celular", "pros": ["camera"], "contras": ["preco"],
                   "perguntas_chave": [], "inclinacao": "depende", "porque": "x"}
        with patch("claude_client.analisar_decisao", return_value=(analise, fake_usage(claude_client.SONNET))):
            r = self.client.post("/api/decisao", json={"pergunta": "vale a pena trocar o celular?"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["analise"], analise)
        historico = self.client.get("/api/decisoes").get_json()
        self.assertEqual(historico[0]["pergunta"], "vale a pena trocar o celular?")

    def test_erros(self):
        for corpo in [{}, {"pergunta": " "}, {"pergunta": "x" * 1001}, {"pergunta": 3}]:
            self.assertEqual(self.client.post("/api/decisao", json=corpo).status_code, 400, msg=repr(corpo))
        with patch("claude_client.analisar_decisao", return_value=(["lista"], fake_usage())):
            self.assertEqual(self.client.post("/api/decisao", json={"pergunta": "x?"}).status_code, 502)
        with patch("claude_client.analisar_decisao", side_effect=ValueError):
            self.assertEqual(self.client.post("/api/decisao", json={"pergunta": "x?"}).status_code, 502)
        self.assertEqual(self.client.get("/api/decisoes").get_json(), [])


if __name__ == "__main__":
    unittest.main()
