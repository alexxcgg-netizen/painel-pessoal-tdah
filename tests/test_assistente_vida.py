"""Assistente de vida (2026-10-11): perfil + meta de comida calculada em codigo, rotinas fixas
(voo com briefing/debriefing), lugares com apelido ("obra"), "acordei", planejar_dia (o dia
inteiro com hora num card so, com Desfazer), apagar tarefa errada (volta no Desfazer) e
corrigir valor de renda. claude_client.chat e dublado; nenhuma rede."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import notificacoes  # noqa: E402
import vida_assistente as va  # noqa: E402

PIN = "135790"
HOJE = date.today().isoformat()


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.fetchall()
        finally:
            conn.close()

    def chat(self, chamadas, contexto_visto=None):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            if contexto_visto is not None:
                contexto_visto.append(contexto)
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Feito.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "teste"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados

    def desfazer(self, card):
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)


class MetaComidaTestCase(unittest.TestCase):
    def test_alex_62kg_169cm_20anos_ganhar_massa(self):
        m = va.metas_comida(62, 169, 20, "ganhar_massa")
        # basal 10*62 + 6,25*169 - 5*20 + 5 = 1581,25 -> x1,5 + 350 = 2721,9 -> 2700
        self.assertEqual(m["kcal"], 2700)
        self.assertEqual(m["proteina_g"], 125)  # 2 g/kg
        self.assertEqual((m["refeicoes"], m["proteina_por_refeicao_g"]), (5, 25))

    def test_manter_usa_menos_proteina(self):
        self.assertEqual(va.metas_comida(62, 169, 20, "manter")["proteina_g"], 100)

    def test_idade_pelo_nascimento(self):
        self.assertEqual(va.idade("2005-12-08", date(2026, 10, 11)), 20)
        self.assertEqual(va.idade("2005-12-08", date(2026, 12, 8)), 21)
        self.assertIsNone(va.idade("lixo", date(2026, 1, 1)))


class ApelidosTestCase(_Base):
    def test_obra_vira_endereco_em_qualquer_jeito_de_falar(self):
        conn = db.get_db()
        self.assertEqual(va.salvar_apelido(conn, "Minha obra", "Loteamento Exemplo, Bairro Teste, Brusque - SC"), "obra")
        for jeito in ("obra", "a obra", "na obra", "Minha Obra", "pra obra"):
            self.assertEqual(va.resolver_lugar(conn, jeito), "Loteamento Exemplo, Bairro Teste, Brusque - SC", jeito)
        self.assertEqual(va.resolver_lugar(conn, "Shopping Brusque"), "Shopping Brusque")
        self.assertEqual(va.resolver_lugar(conn, "SSBL"), "Aeroclube de Blumenau, Blumenau - SC")
        self.assertIsNone(va.salvar_apelido(conn, "casa", "outro lugar"))  # casa e o ENDERECO_CASA
        conn.close()

    def test_so_o_nome_procura_no_google_e_guarda_o_que_achou(self):
        # 04/11: "a oficina que eu levo o carro e a Fulano" - basta o nome, o painel acha o endereco
        achado = {"place_id": "x", "nome": "Oficina Exemplo", "endereco": "R. Teste, 10 - Centro, Brusque - SC"}
        with patch("maps_client.configurado", return_value=True), \
                patch("maps_client.resolver_lugar", return_value=achado) as procurar, \
                patch("onde_estou.garantir_coordenada", return_value=True):
            _, res = self.chat([("salvar_lugar_apelido", {"apelido": "a oficina", "endereco": "Oficina Exemplo"})])
        procurar.assert_called_once_with("Oficina Exemplo")
        self.assertEqual(res[0]["endereco"], "Oficina Exemplo, R. Teste, 10 - Centro, Brusque - SC")
        self.assertNotIn("obs", res[0])
        conn = db.get_db()
        self.assertEqual(va.resolver_lugar(conn, "oficina"), "Oficina Exemplo, R. Teste, 10 - Centro, Brusque - SC")
        conn.close()

    def test_nao_achou_guarda_como_ele_falou_e_avisa(self):
        with patch("maps_client.configurado", return_value=True), \
                patch("maps_client.resolver_lugar", return_value=None), \
                patch("onde_estou.garantir_coordenada", return_value=False):
            _, res = self.chat([("salvar_lugar_apelido", {"apelido": "academia", "endereco": "Academia Inventada"})])
        self.assertEqual(res[0]["endereco"], "Academia Inventada")
        self.assertIn("nao achei", res[0]["obs"])

    def test_esquecer_tira_da_lista(self):
        conn = db.get_db()
        va.salvar_apelido(conn, "oficina 2", "Volvo, Florianopolis - SC")
        conn.commit()
        conn.close()
        _, res = self.chat([("salvar_lugar_apelido", {"apelido": "a oficina 2", "esquecer": True}),
                            ("salvar_lugar_apelido", {"apelido": "nao existe", "esquecer": True})])
        self.assertEqual(res[0], {"ok": True, "esquecido": "oficina 2"})
        self.assertIn("erro", res[1])
        conn = db.get_db()
        self.assertNotIn("oficina 2", va.apelidos(conn))
        conn.close()

    def test_regra_de_lugar_que_ele_ensina_no_prompt(self):
        from ia.funcoes import chat as chat_mod

        p = chat_mod.CHAT_SYSTEM_PROMPT
        self.assertIn("LUGARES QUE ELE ENSINA", p)
        self.assertIn("nunca \"balada\"", p)


class ContextoTestCase(_Base):
    def test_contexto_tem_perfil_comida_rotinas_lugares_e_acordou(self):
        vistos = []
        self.chat([
            ("atualizar_perfil", {"peso_kg": 62, "altura_cm": 1.69, "objetivo": "ganhar_massa", "academia": "parado, quer voltar"}),
            ("salvar_lugar_apelido", {"apelido": "obra", "endereco": "Loteamento Exemplo, Bairro Teste, Brusque - SC"}),
            ("registrar_acordei", {}),
        ])
        conn = db.get_db()
        db.definir_configuracao(conn, "perfil_nascimento", "2005-12-08")
        conn.commit()
        conn.close()
        self.chat([], contexto_visto=vistos)
        ctx = vistos[0]
        self.assertIn("Perfil do Alex: 62 kg", ctx)
        self.assertIn("1,69 m", ctx)
        self.assertIn("objetivo: ganhar massa muscular", ctx)
        self.assertIn("academia: parado, quer voltar", ctx)
        self.assertIn("~125 g de proteina por dia", ctx)
        self.assertIn("chegar 30 min antes da hora do voo pro briefing", ctx)
        self.assertIn("30 min depois de pousar pro debriefing", ctx)
        self.assertIn("obra = Loteamento Exemplo", ctx)
        self.assertIn("Acordou hoje as", ctx)

    def test_peso_criptografado_em_repouso_e_lido_certo(self):
        from cryptography.fernet import Fernet
        import criptografia
        with patch.dict(os.environ, {"ENCRYPTION_KEY": Fernet.generate_key().decode()}):
            criptografia._fernet.cache_clear() if hasattr(criptografia._fernet, "cache_clear") else None
            conn = db.get_db()
            db.create_medida_corporal(conn, "peso", 62.0, "kg", HOJE)
            bruto = conn.execute("SELECT valor FROM medidas_corporais").fetchone()[0]
            self.assertNotEqual(str(bruto), "62.0")  # gravado cifrado
            self.assertEqual(va.perfil(conn)["peso_kg"], 62.0)
            conn.close()
        if hasattr(criptografia._fernet, "cache_clear"):
            criptografia._fernet.cache_clear()

    def test_acordei_com_hora_no_futuro_e_recusado(self):
        _, res = self.chat([("registrar_acordei", {"hora": "23:59"})])
        if datetime.now().strftime("%H:%M") < "23:59":
            self.assertIn("erro", res[0])

    def test_perfil_recusa_numero_absurdo(self):
        _, res = self.chat([("atualizar_perfil", {"peso_kg": 5}), ("atualizar_perfil", {"altura_cm": 400}),
                            ("atualizar_perfil", {"objetivo": "virar hulk"})])
        self.assertTrue(all("erro" in r for r in res))


class PlanejarDiaTestCase(_Base):
    def test_monta_o_dia_num_card_so_e_desfaz_tudo(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Pegar a CND', ?)", (HOJE,))
        corpo, res = self.chat([("planejar_dia", {"blocos": [
            {"titulo": "Comer: café da manhã - ovos, pão, banana", "hora": "8:30"},
            {"titulo": "Ver números da empresa", "hora": "09:00", "fim": "10:00"},
            {"titulo": "Pegar CND", "hora": "10:30"},
            {"titulo": "Voo - briefing", "hora": "13:30", "fim": "16:30", "local": "SSBL"},
            {"titulo": "Passar na obra", "hora": "17:15", "local": "obra"},
            {"titulo": "sem hora", "hora": ""},
        ]})])
        r = res[0]
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["criadas"], r["horario_ajustado"]), (4, 1))  # a CND ja existia: so ganhou hora
        self.assertEqual(r["ignorados_sem_hora"], ["sem hora"])
        tarefas = {t[0]: t[1:] for t in self.sql("SELECT title, hora, local FROM tasks WHERE due_date = ?", (HOJE,))}
        self.assertEqual(tarefas["Pegar a CND"][0], "10:30")
        self.assertEqual(tarefas["Ver números da empresa (até 10:00)"][0], "09:00")
        self.assertEqual(tarefas["Comer: café da manhã - ovos, pão, banana"][0], "08:30")
        self.assertEqual(tarefas["Voo - briefing (até 16:30)"][1], "Aeroclube de Blumenau, Blumenau - SC")
        tipos = [c["type"] for c in corpo["cards"]]
        self.assertIn("tarefas_criadas", tipos)
        self.assertIn("edicao", tipos)
        criadas = next(c for c in corpo["cards"] if c["type"] == "tarefas_criadas")
        self.assertEqual(len(criadas["data"]["agenda_do_dia"]), 5)  # trilha do dia inteiro
        self.desfazer(criadas)
        self.desfazer(next(c for c in corpo["cards"] if c["type"] == "edicao"))
        self.assertEqual([tuple(t) for t in self.sql("SELECT title, hora FROM tasks")], [("Pegar a CND", None)])

    def test_sem_bloco_valido_e_erro(self):
        _, res = self.chat([("planejar_dia", {"blocos": [{"titulo": "x"}]}), ("planejar_dia", {"blocos": []})])
        self.assertTrue(all("erro" in r for r in res))

    def test_nao_recria_tarefa_concluida_ha_pouco(self):
        """Caso real 2026-10-14: Mikael concluido, a IA "remarcou" pelo planejar_dia e nasceu outro."""
        dia = app._agora_brasilia().date().isoformat()
        self.sql("INSERT INTO tasks (title, due_date, hora, completed_at) "
                 "VALUES ('Enviar a compra e venda pro Mikael', ?, '09:00', datetime('now', '-1 minute'))", (dia,))
        _, res = self.chat([("planejar_dia", {"blocos": [
            {"titulo": "Consulta com tricologista", "hora": "09:30"},
            {"titulo": "enviar a compra e venda pro mikael", "hora": "08:30"},
        ]})])
        self.assertEqual(res[0]["criadas"], 1)
        self.assertEqual(res[0]["ja_feitas_nao_recriei"], ["Enviar a compra e venda pro Mikael"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks WHERE title LIKE '%Mikael%'")[0][0], 1)
        # so com o que ja ta feito: nada criado, mas nao e erro
        _, res = self.chat([("planejar_dia", {"blocos": [{"titulo": "Enviar a compra e venda pro Mikael", "hora": "8:30"}]})])
        self.assertEqual((res[0]["ok"], res[0]["criadas"]), (True, 0))


class EstadoTarefasTestCase(_Base):
    """GET /api/tasks/estado - os cards do chat acertam as caixinhas com o estado de agora."""

    def test_devolve_concluida_por_id_e_ignora_lixo(self):
        self.sql("INSERT INTO tasks (id, title) VALUES (31, 'Consulta com tricologista')")
        self.sql("INSERT INTO tasks (id, title, completed_at) VALUES (32, 'Mikael', datetime('now'))")
        res = self.client.get("/api/tasks/estado?ids=31,32,999,abc,,1;DROP")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"estados": {"31": False, "32": True}})
        self.client.post("/api/tasks/31/complete")
        self.assertEqual(self.client.get("/api/tasks/estado?ids=31").get_json()["estados"], {"31": True})
        self.assertEqual(self.client.get("/api/tasks/estado").get_json(), {"estados": {}})

    def test_exige_login(self):
        self.client.post("/logout")
        anonimo = app.app.test_client()
        self.assertIn(anonimo.get("/api/tasks/estado?ids=1").status_code, (302, 401))


class TarefaRepetidaTestCase(_Base):
    def test_mesmo_titulo_mesmo_dia_nao_duplica(self):
        _, res = self.chat([
            ("registrar_tarefa", {"titulo": "Falar com o Mikael", "quando": "hoje", "quando_data": HOJE}),
            ("registrar_tarefa", {"titulo": "falar com o  Mikael", "quando": "hoje", "quando_data": HOJE}),
        ])
        self.assertTrue(res[0]["ok"])
        self.assertTrue(res[1]["nao_criei"])
        self.assertEqual(res[1]["ja_existe"]["id"], self.sql("SELECT id FROM tasks")[0][0])
        self.assertIn("ajustar_tarefa", res[1]["aviso"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks")[0][0], 1)

    def test_assunto_diferente_ou_outro_dia_passa(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        _, res = self.chat([
            ("registrar_tarefa", {"titulo": "Falar com o Mikael", "quando_data": HOJE}),
            ("registrar_tarefa", {"titulo": "Falar com o Mikael sobre o contrato", "quando_data": HOJE}),
            ("registrar_tarefa", {"titulo": "Falar com o Mikael", "quando_data": amanha}),
        ])
        self.assertFalse(any(r.get("nao_criei") for r in res), res)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks")[0][0], 3)

    def test_concluida_ha_pouco_nao_renasce_mas_a_antiga_sim(self):
        self.sql("INSERT INTO tasks (title, due_date, completed_at) VALUES ('Pagar o boleto', ?, datetime('now', '-5 minutes'))", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date, completed_at) VALUES ('Lavar o carro', ?, datetime('now', '-2 days'))", (HOJE,))
        _, res = self.chat([
            ("registrar_tarefa", {"titulo": "Pagar o boleto", "quando_data": HOJE}),
            ("registrar_tarefa", {"titulo": "Lavar o carro", "quando_data": HOJE}),
        ])
        self.assertEqual(res[0]["ja_concluida"]["titulo"], "Pagar o boleto")
        self.assertNotIn("nao_criei", res[1])

    def test_sem_data_tambem_nao_duplica(self):
        _, res = self.chat([
            ("registrar_tarefa", {"titulo": "Ligar pro banco"}),
            ("registrar_tarefa", {"titulo": "Ligar pro banco"}),
        ])
        self.assertNotIn("_efeito", res[1])  # sem _efeito: nao vira card nem Desfazer
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks")[0][0], 1)

    def test_refeicao_nao_e_date_e_avisa_hora_de_comer(self):
        self.assertTrue(notificacoes.e_refeicao("Comer: jantar - arroz e frango"))
        self.assertFalse(notificacoes.e_compromisso_de_sair("Comer: jantar - arroz e frango"))
        self.assertTrue(notificacoes.e_compromisso_de_sair("Jantar com a Ana"))


class ApagarECorrigirTestCase(_Base):
    def test_apaga_tarefa_errada_e_desfazer_traz_de_volta_igual(self):
        self.sql("INSERT INTO tasks (title, due_date, hora, local) VALUES ('Lavar o carro', ?, '15:00', 'Posto X')", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Outra coisa', ?)", (HOJE,))
        corpo, res = self.chat([("apagar_tarefa", {"titulo": "lavar carro"})])
        self.assertEqual(res[0]["apagada"], "Lavar o carro")
        self.assertEqual([t[0] for t in self.sql("SELECT title FROM tasks")], ["Outra coisa"])
        card = next(c for c in corpo["cards"] if c["type"] == "edicao")
        self.assertEqual(card["data"]["itens"][0]["mudancas"], [{"campo": "situação", "de": "na lista", "para": "apagada"}])
        self.desfazer(card)
        self.assertEqual(tuple(self.sql("SELECT id, title, due_date, hora, local FROM tasks WHERE title = 'Lavar o carro'")[0]),
                         (1, "Lavar o carro", HOJE, "15:00", "Posto X"))

    def test_nao_apaga_o_modelo_da_rotina(self):
        # rotina num dia que NAO e hoje (senao a instancia de hoje existe e e ela que sai)
        outro_dia = (date.today().weekday() + 2) % 7
        self.sql("INSERT INTO tasks (title, recorrencia) VALUES ('Academia', ?)", (f"semanal:{outro_dia}",))
        _, res = self.chat([("apagar_tarefa", {"titulo": "Academia"})])
        self.assertIn("erro", res[0])
        self.assertEqual(len(self.sql("SELECT id FROM tasks")), 1)

    def test_corrige_valor_de_renda(self):
        self.sql("INSERT INTO incomes (amount, category, description) VALUES (1500, 'salario', 'pagamento do mes')")
        corpo, res = self.chat([("ajustar_renda", {"descricao_atual": "pagamento", "valor": 1800})])
        self.assertTrue(res[0]["ok"])
        self.assertEqual(self.sql("SELECT amount FROM incomes")[0][0], 1800)
        self.desfazer(next(c for c in corpo["cards"] if c["type"] == "edicao"))
        self.assertEqual(self.sql("SELECT amount FROM incomes")[0][0], 1500)

    def test_modo_visitante_esconde_valor_do_card_de_correcao(self):
        import cards
        card = cards.novo_card("edicao", {"itens": [{"rotulo": "Gasto", "titulo": "x", "mudancas": [
            {"campo": "valor", "de": "R$ 42,50", "para": "R$ 45,00"}, {"campo": "categoria", "de": "a", "para": "b"}]}]}, [])
        mudancas = cards.mascarar_cards([card])[0]["data"]["itens"][0]["mudancas"]
        self.assertEqual(mudancas[0], {"campo": "valor", "de": "R$ •••", "para": "R$ •••"})
        self.assertEqual(mudancas[1]["de"], "a")


class ExcluirPelaTelaTestCase(_Base):
    """Arrastar-pra-excluir da aba Tarefas: DELETE /api/tasks/<id> + Desfazer."""

    def test_exclui_sem_concluir_e_desfazer_volta_com_os_passos(self):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Organizar a garagem', ?, '10:00')", (HOJE,))
        self.sql("INSERT INTO subtasks (task_id, title, position) VALUES (1, 'tirar as caixas', 0)")
        self.sql("INSERT INTO subtasks (task_id, title, position, completed_at) VALUES (1, 'varrer', 1, '2026-10-11 09:00:00')")
        r = self.client.delete("/api/tasks/1").get_json()
        self.assertTrue(r["ok"])
        self.assertEqual(r["titulo"], "Organizar a garagem")
        self.assertFalse(r["pulada"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks")[0][0], 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM subtasks")[0][0], 0)
        self.assertEqual(self.client.post(f"/api/desfazer/{r['token']}").status_code, 200)
        self.assertEqual(tuple(self.sql("SELECT id, title, hora, completed_at FROM tasks")[0]), (1, "Organizar a garagem", "10:00", None))
        self.assertEqual([tuple(x) for x in self.sql("SELECT title, position, completed_at IS NOT NULL FROM subtasks ORDER BY position")],
                         [("tirar as caixas", 0, 0), ("varrer", 1, 1)])

    def test_dia_de_rotina_e_pulado_so_hoje_e_nao_volta_sozinho(self):
        self.sql("INSERT INTO tasks (title, recorrencia) VALUES ('Academia', 'diaria')")
        self.client.get("/api/tasks")  # materializa a de hoje
        inst = self.sql("SELECT id FROM tasks WHERE recorrente_origem_id = 1")[0][0]
        r = self.client.delete(f"/api/tasks/{inst}").get_json()
        self.assertTrue(r["pulada"])
        conn = db.get_db()
        self.assertEqual(app.materializar_tarefas_recorrentes(conn), 0)  # nao recria no proximo tick
        conn.close()
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks WHERE recorrente_origem_id = 1")[0][0], 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks WHERE id = 1")[0][0], 1)  # a rotina continua
        self.client.post(f"/api/desfazer/{r['token']}")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks WHERE recorrente_origem_id = 1")[0][0], 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tarefas_puladas")[0][0], 0)

    def test_modelo_de_rotina_inexistente_e_visitante(self):
        self.sql("INSERT INTO tasks (title, recorrencia) VALUES ('Academia', 'diaria')")
        self.assertEqual(self.client.delete("/api/tasks/1").status_code, 404)  # o modelo nao se apaga por aqui
        self.assertEqual(self.client.delete("/api/tasks/999").status_code, 404)
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('X', ?)", (HOJE,))
        with patch("app._modo_visitante_ativo", return_value=True):
            self.assertEqual(self.client.delete("/api/tasks/2").status_code, 403)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks WHERE id = 2")[0][0], 1)

    def test_ia_tambem_apaga_tarefa_com_passos_e_dia_de_rotina(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Projeto grande', ?)", (HOJE,))
        self.sql("INSERT INTO subtasks (task_id, title, position) VALUES (1, 'passo 1', 0)")
        corpo, res = self.chat([("apagar_tarefa", {"titulo": "Projeto grande"})])
        self.assertTrue(res[0]["ok"])
        self.desfazer(next(c for c in corpo["cards"] if c["type"] == "edicao"))
        self.assertEqual(self.sql("SELECT title FROM subtasks")[0][0], "passo 1")


class AvisoVooTestCase(_Base):
    def test_sai_pra_chegar_no_briefing_indo_pra_origem(self):
        conn = db.get_db()
        voo = {"data": HOJE, "hora": "14:00", "origem": "SSBL", "destino": "SBFL"}
        chamado = {}

        def fake_saida(origem, destino, chegar_ate, margem_minutos=15, modo="DRIVE", **_):
            chamado.update(destino=destino, chegar_ate=chegar_ate, margem=margem_minutos)
            return {"sair_ate": (datetime.now() + timedelta(minutes=5)).isoformat(), "duracao_minutos": 40, "distancia_km": 30, "margem_minutos": margem_minutos}

        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Exemplo, Brusque"}), \
                patch("maps_client.configurado", return_value=True), \
                patch("maps_client.horario_de_saida", side_effect=fake_saida):
            msg = app._aviso_voo_sair(voo, conn=conn)
        conn.close()
        self.assertEqual(chamado["destino"], "Aeroclube de Blumenau, Blumenau - SC")
        self.assertEqual(chamado["chegar_ate"].strftime("%H:%M"), "13:30")  # 30 min de briefing
        self.assertIn("briefing das 13:30", msg)
        self.assertIn("voo das 14:00 pra SBFL", msg)


if __name__ == "__main__":
    unittest.main()
