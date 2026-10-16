"""IA que edita (com Desfazer) e cartoes vivos (2026-10-09).

Mesmo esquema do test_app: banco temporario, login pelo fluxo real e
claude_client.chat dublado - o duble chama os executores de verdade e a
resposta HTTP traz os cards que o front anima."""
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import viagem_compras  # noqa: E402

PIN = "246810"
HOJE = date.today().isoformat()
AMANHA = (date.today() + timedelta(days=1)).isoformat()


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class VivoTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        app._CACHE_CONSTRUTORA.clear()
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

    def chat(self, chamadas, mensagem="pedido qualquer de teste"):
        """chamadas = [(tool, entrada)]; devolve (json da resposta, resultados das tools)."""
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Feito.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": mensagem})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados

    def desfazer(self, card):
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        res = self.client.post(f"/api/desfazer/{token}")
        self.assertEqual(res.status_code, 200, res.get_json())

    # ---- edicao ---------------------------------------------------------

    def test_ajustar_tarefa_mostra_antes_depois_e_desfaz(self):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Falar com a contabilidade', ?, '09:00')", (HOJE,))
        corpo, res = self.chat([("ajustar_tarefa", {"titulo": "contabilidade", "hora": "10:30", "quando_data": AMANHA})])
        self.assertTrue(res[0]["ok"])
        card = next(c for c in corpo["cards"] if c["type"] == "edicao")
        mudancas = {m["campo"]: (m["de"], m["para"]) for m in card["data"]["itens"][0]["mudancas"]}
        self.assertEqual(mudancas["hora"], ("09:00", "10:30"))
        self.assertIn("dia", mudancas)
        self.assertEqual(self.sql("SELECT hora, due_date FROM tasks")[0][:], ("10:30", AMANHA))
        self.desfazer(card)
        self.assertEqual(tuple(self.sql("SELECT hora, due_date FROM tasks")[0]), ("09:00", HOJE))

    def test_ajustar_tarefa_concluir_e_titulo_ambiguo(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Visitar o aeroporto', ?)", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Visitar a irma', ?)", (HOJE,))
        _, res = self.chat([("ajustar_tarefa", {"titulo": "visitar", "status": "concluir"})])
        self.assertIn("erro", res[0])
        self.assertEqual(len(res[0]["candidatas"]), 2)
        _, res = self.chat([("ajustar_tarefa", {"titulo": "aeroporto", "status": "concluir"})])
        self.assertTrue(res[0]["ok"])
        self.assertIsNotNone(self.sql("SELECT completed_at FROM tasks WHERE title LIKE '%aeroporto%'")[0][0])

    def test_ajustar_tarefa_acha_nome_parecido_e_renomeia(self):
        # caso real (10/10): a IA mandou um nome diferente do titulo e recebia "nenhum registro"
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Lavar os carros por dentro', ?)", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Passar pretinho na Fiorino', ?)", (HOJE,))
        for pedido in ("lavar o carro", "Lavar carros", "lavar os carros"):
            _, res = self.chat([("ajustar_tarefa", {"titulo": pedido, "novo_titulo": f"Limpar por dentro ({pedido})"})])
            self.assertTrue(res[0].get("ok"), (pedido, res[0]))
            # 2026-10-16: devolve o titulo NOVO (com o antigo a IA achava que a troca nao pegou)
            self.assertEqual(res[0]["titulo"], f"Limpar por dentro ({pedido})")
            self.assertEqual(res[0]["titulo_antes"], "Lavar os carros por dentro")
            self.sql("UPDATE tasks SET title = 'Lavar os carros por dentro' WHERE id = 1")
        _, res = self.chat([("ajustar_tarefa", {"titulo": "comprar pao", "hora": "10:00"})])
        self.assertIn("erro", res[0])
        self.assertIn("Lavar os carros por dentro", res[0]["existentes"])

    def test_tarefa_criada_vem_com_o_dia_em_volta(self):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Date', ?, '20:30')", (HOJE,))
        corpo, _ = self.chat([("registrar_tarefa", {"titulo": "Visitar a irma", "quando_data": HOJE, "hora": "17:00"})])
        card = next(c for c in corpo["cards"] if c["type"] == "tarefas_criadas")
        agenda = card["data"]["agenda_do_dia"]
        self.assertEqual([(t["titulo"], t["nova"]) for t in agenda], [("Visitar a irma", True), ("Date", False)])

    def test_mover_tarefas_da_tarde_um_card_um_desfazer(self):
        for titulo, hora in (("manha", "09:00"), ("tarde 1", "13:00"), ("tarde 2", "16:00")):
            self.sql("INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", (titulo, HOJE, hora))
        corpo, res = self.chat([("mover_tarefas", {"para_data": AMANHA, "periodo": "tarde"})])
        self.assertEqual(res[0]["movidas"], ["tarde 1", "tarde 2"])
        cards = [c for c in corpo["cards"] if c["type"] == "edicao"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(len(cards[0]["data"]["itens"]), 2)
        self.assertEqual(self.sql("SELECT due_date FROM tasks WHERE title = 'manha'")[0][0], HOJE)
        self.desfazer(cards[0])
        self.assertEqual({r[0] for r in self.sql("SELECT due_date FROM tasks")}, {HOJE})

    def test_ajustar_gasto_corrige_valor_digitado_e_desfaz(self):
        # 2026-10-11: o Alex liberou corrigir valor que ELE digitou ("errei, foi 45")
        self.sql("INSERT INTO expenses (amount, category, description) VALUES (42.5, 'outros', 'almoco no centro')")
        corpo, res = self.chat([("ajustar_gasto", {"descricao_atual": "almoco", "categoria": "Restaurante", "valor": 45})])
        self.assertTrue(res[0]["ok"])
        self.assertEqual(tuple(self.sql("SELECT amount, category FROM expenses")[0]), (45.0, "restaurante"))
        card = next(c for c in corpo["cards"] if c["type"] == "edicao")
        self.assertIn({"campo": "valor", "de": "R$ 42,50", "para": "R$ 45,00"}, card["data"]["itens"][0]["mudancas"])
        self.desfazer(card)
        self.assertEqual(tuple(self.sql("SELECT amount, category FROM expenses")[0]), (42.5, "outros"))
        _, res = self.chat([("ajustar_gasto", {"descricao_atual": "almoco", "valor": -3})])
        self.assertIn("erro", res[0])

    def test_desfazer_so_aceita_tabela_e_coluna_da_lista(self):
        conn = db.get_db()
        try:
            # banco (Nubank) nunca entra na lista de edicao
            self.assertIsNone(db.criar_acao_desfazer(conn, [{"entidade": "edicao", "id": 1, "tabela": "bank_transactions", "antes": {"valor": 1}}]))
            self.assertIsNone(db.criar_acao_desfazer(conn, [{"entidade": "edicao", "id": 1, "tabela": "expenses", "antes": {"created_at": "x"}}]))
            self.assertIsNone(db.criar_acao_desfazer(conn, [{"entidade": "edicao", "id": 1, "tabela": "auth", "antes": {"pin": "x"}}]))
            self.assertIsNotNone(db.criar_acao_desfazer(conn, [{"entidade": "edicao", "id": 1, "tabela": "tasks", "antes": {"hora": "09:00", "x": 1}}]))
        finally:
            conn.close()

    def test_ajustar_voo_e_card_do_diario(self):
        self.sql("INSERT INTO voos (data, origem, destino, horas, funcao) VALUES ('2024-09-13', 'SSBL', 'SSBL', 1.0, 'Piloto em Instrução')")
        self.sql("INSERT INTO voos (data, origem, destino, horas, funcao) VALUES ('2024-09-12', 'SSBL', 'SSBL', 1.0, 'Piloto em Instrução Solo')")
        corpo, res = self.chat([("ajustar_voo", {"data_do_voo": "2024-09-13", "aeronave": "pr-lom"})])
        self.assertTrue(res[0]["ok"])
        self.assertEqual(self.sql("SELECT aeronave FROM voos WHERE data = '2024-09-13'")[0][0], "PR-LOM".replace("-", ""))
        tipos = [c["type"] for c in corpo["cards"]]
        self.assertIn("edicao", tipos)
        voo = next(c for c in corpo["cards"] if c["type"] == "voo_resumo")
        self.assertEqual(voo["data"]["total_min"], 120)
        self.assertEqual(voo["data"]["primeiro_solo"]["minutos"], 0)

    def test_visitante_nao_edita(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('x', ?)", (HOJE,))
        with patch("app._modo_visitante_ativo", return_value=True):
            _, res = self.chat([("ajustar_tarefa", {"titulo": "x", "hora": "10:00"})])
        self.assertIn("erro", res[0])
        self.assertIsNone(self.sql("SELECT hora FROM tasks")[0][0])

    # ---- cartoes vivos ---------------------------------------------------

    def test_viagem_em_fevereiro_traz_os_dois_cenarios(self):
        corpo, res = self.chat([("planejar_compras_viagem", {"mes": "2027-02"})])
        card = next(c for c in corpo["cards"] if c["type"] == "viagem_janelas")
        self.assertEqual(set(card["data"]["cenarios"]), {"fora", "no_feriado"})
        self.assertEqual(card["data"]["cenarios"]["no_feriado"]["alta"]["nome"], "Carnaval")
        self.assertIn("erro", self.chat([("planejar_compras_viagem", {"mes": "fev"})])[1][0])

    def test_agua_vira_card_agua_com_desfazer(self):
        corpo, _ = self.chat([("registrar_hidratacao", {})])
        card = next(c for c in corpo["cards"] if c["type"] == "agua")
        self.assertEqual((card["data"]["copos"], card["data"]["meta"]), (1, 8))
        self.desfazer(card)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM hidratacao_registros")[0][0], 0)

    def test_consultas_trazem_cards_vivos(self):
        self.sql("INSERT INTO expenses (amount, category, description) VALUES (30, 'mercado', 'pao')")
        corpo, _ = self.chat([("consultar_gastos", {}), ("consultar_agenda", {})])
        tipos = [c["type"] for c in corpo["cards"]]
        self.assertIn("gastos_resumo", tipos)
        self.assertIn("dia", tipos)
        with patch("app._modo_visitante_ativo", return_value=True):
            corpo, _ = self.chat([("consultar_agenda", {})])


class TarefasListaTestCase(VivoTestCase):
    def test_o_que_tenho_hoje_vira_card_com_anel_e_atrasadas(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Lavar os carros', ?, '14:00')", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date, completed_at) VALUES ('Contabilidade', ?, datetime('now'))", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Pagar boleto', ?)", (ontem,))
        corpo, _ = self.chat([("consultar_tarefas", {"status": "todas"})])
        card = next(c for c in corpo["cards"] if c["type"] == "tarefas_lista")
        d = card["data"]
        self.assertEqual((d["total"], d["feitas"]), (2, 1))
        self.assertEqual([t["titulo"] for t in d["itens"]], ["Lavar os carros", "Contabilidade"])
        self.assertTrue(all(isinstance(t["id"], int) for t in d["itens"]))  # caixinha conclui pelo id
        self.assertEqual([t["titulo"] for t in d["atrasadas"]], ["Pagar boleto"])


class ViagemComprasTestCase(unittest.TestCase):
    def test_carnaval_pela_pascoa(self):
        self.assertEqual(viagem_compras.pascoa(2027), date(2027, 3, 28))
        ini, fim, nome = viagem_compras.alta_temporada(date(2027, 2, 8))
        self.assertEqual((ini, fim, nome), (date(2027, 2, 6), date(2027, 2, 10), "Carnaval"))
        self.assertIsNone(viagem_compras.alta_temporada(date(2027, 2, 20)))

    def test_status_das_janelas(self):
        p = viagem_compras.planejar(ida=date(2027, 2, 6), hoje=date(2026, 10, 9))
        janelas = {j["item"]: j for j in p["cenarios"]["no_feriado"]["janelas"]}
        self.assertEqual(janelas["passagem"]["status"], "agora")
        p = viagem_compras.planejar(ida=date(2027, 2, 20), hoje=date(2026, 10, 9))
        self.assertEqual({j["status"] for j in p["cenarios"]["fora"]["janelas"]}, {"em_breve"})
        p = viagem_compras.planejar(ida=date(2026, 10, 20), hoje=date(2026, 10, 9))
        self.assertEqual({j["item"]: j["status"] for j in p["cenarios"]["fora"]["janelas"]}["passagem"], "passou")


if __name__ == "__main__":
    unittest.main()
