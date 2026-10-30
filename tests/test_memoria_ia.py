"""Grupo D do Laboratorio v4 (2026-10-30): memoria da IA - onde guardei, o que eu falei, neste dia,
coincidencias. Banco temporario; nenhuma rede nem IA real (o chat e mockado)."""
import json
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
import cards  # noqa: E402
import coincidencias  # noqa: E402
import conversa_proativa  # noqa: E402
import guardados  # noqa: E402
import memoria  # noqa: E402
import neste_dia  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

PIN = "246813"
HOJE = date(2026, 10, 30)  # sexta


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def logado(self):
        client = app.app.test_client()
        self.assertEqual(client.post("/login", json={"pin": PIN}).status_code, 200)
        return client

    def chamar_ferramenta(self, tool, entrada):
        """Roda um executor do chat de verdade (pela rota) com a IA mockada e devolve a resposta."""
        client = self.logado()
        saida = {}

        def fake(mensagens, contexto, memorias, executores):
            saida["r"] = executores[tool](entrada)
            return "ok", [tool], {"model": "x", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}

        with patch("claude_client.chat", side_effect=fake):
            res = client.post("/api/chat", json={"mensagem": "teste"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), saida.get("r")


class GuardadosTestCase(_Base):
    def test_guardar_achar_e_atualizar_lugar(self):
        r = guardados.guardar(self.conn, "Passaporte", "gaveta azul do quarto", HOJE)
        self.assertTrue(r["novo"])
        self.assertEqual(r["lugar"], "gaveta azul do quarto")
        # acha sem acento / caixa / so o inicio da palavra
        self.assertEqual(guardados.achar(self.conn, "cadê o PASSAPORTE?", HOJE)[0]["objeto"], "Passaporte")
        r2 = guardados.guardar(self.conn, "passaporte", "mochila do voo", HOJE)
        self.assertFalse(r2["novo"])
        self.assertEqual(r2["anterior"], "gaveta azul do quarto")
        self.assertEqual(guardados.total(self.conn), 1)
        self.assertEqual(guardados.achar(self.conn, "passaporte", HOJE)[0]["lugar"], "mochila do voo")

    def test_nao_acha_e_entrada_vazia(self):
        self.assertEqual(guardados.achar(self.conn, "carregador", HOJE), [])
        self.assertIn("erro", guardados.guardar(self.conn, "", "gaveta", HOJE))
        self.assertIn("erro", guardados.guardar(self.conn, "chave", "  ", HOJE))

    def test_card_modos_e_lista_limitada(self):
        for i in range(8):
            guardados.guardar(self.conn, f"coisa {i}", f"lugar {i}", HOJE)
        item = guardados.achar(self.conn, "coisa 0", HOJE)[0]
        c = guardados.card(self.conn, {"modo": "achei", "item": item}, HOJE)
        self.assertEqual(c["type"], "guardados")
        self.assertEqual(c["data"]["modo"], "achei")
        self.assertLessEqual(len(c["data"]["itens"]), guardados.LIMITE_LISTA)
        # o destaque mais antigo entra na lista mesmo fora dos 5 recentes
        self.assertTrue(any(i["id"] == item["id"] for i in c["data"]["itens"]))
        vazio = guardados.card(self.conn, {"modo": "nao_achei", "busca": "chave"}, HOJE)
        self.assertEqual(vazio["data"]["busca"], "chave")

    def test_fluxo_pelo_chat_guarda_e_responde_com_card(self):
        resp, r = self.chamar_ferramenta("guardar_objeto", {"objeto": "passaporte", "lugar": "gaveta azul do quarto"})
        self.assertTrue(r["ok"])
        tipos = [c["type"] for c in resp["cards"]]
        self.assertIn("guardados", tipos)
        card = next(c for c in resp["cards"] if c["type"] == "guardados")
        self.assertEqual(card["data"]["modo"], "guardado")
        self.assertEqual(card["data"]["destaque"]["lugar"], "gaveta azul do quarto")
        resp2, r2 = self.chamar_ferramenta("onde_esta", {"objeto": "passaporte"})
        self.assertTrue(r2["encontrado"])
        self.assertEqual(r2["guardados"][0]["lugar"], "gaveta azul do quarto")
        card2 = next(c for c in resp2["cards"] if c["type"] == "guardados")
        self.assertEqual(card2["data"]["modo"], "achei")
        resp3, r3 = self.chamar_ferramenta("onde_esta", {"objeto": "carregador"})
        self.assertFalse(r3["encontrado"])
        self.assertIn("sem chutar", r3["obs"])
        self.assertEqual(next(c for c in resp3["cards"] if c["type"] == "guardados")["data"]["modo"], "nao_achei")

    def test_rotas_listar_e_tirar(self):
        item = guardados.guardar(self.conn, "CIV", "mochila do voo", HOJE)
        client = self.logado()
        self.assertEqual(client.get("/api/guardados").get_json()["itens"][0]["objeto"], "CIV")
        self.assertEqual(client.delete(f"/api/guardados/{item['id']}").status_code, 200)
        self.assertEqual(client.delete(f"/api/guardados/{item['id']}").status_code, 404)
        self.assertEqual(client.get("/api/guardados").get_json()["itens"], [])

    def test_visitante_nao_ve_o_lugar(self):
        c = guardados.card(self.conn, {"modo": "guardado", "item": guardados.guardar(self.conn, "CIV", "mochila", HOJE)}, HOJE)
        m = cards.mascarar_cards([c])[0]["data"]
        self.assertTrue(m["oculto"])
        self.assertNotIn("destaque", m)
        self.assertNotIn("itens", m)

    def test_prompt_e_ferramentas(self):
        nomes = {t["name"] for t in chat_mod.CHAT_TOOLS}
        for n in ("guardar_objeto", "onde_esta", "buscar_o_que_falei", "consultar_neste_dia", "consultar_coincidencias"):
            self.assertIn(n, nomes)
        self.assertIn("ONDE GUARDEI", chat_mod.CHAT_SYSTEM_PROMPT)


class FalasTestCase(_Base):
    def fala(self, texto, quando):
        self.conn.execute("INSERT INTO chat_mensagens (papel, texto, criado_em) VALUES ('user', ?, ?)", (texto, quando))
        self.conn.commit()

    def test_so_o_que_ele_disse_datado_e_sem_a_propria_pergunta(self):
        self.fala("O instrutor mandou olhar pro fim da pista no pouso", "2026-10-21 15:00:00")
        self.fala("Pouso longo de novo", "2026-10-14 15:00:00")
        self.conn.execute("INSERT INTO tasks (title, completed_at) VALUES ('Estudar pouso', '2026-10-20 12:00:00')")
        self.fala("o que eu falei sobre o pouso?", "2026-10-30 12:00:00")  # a pergunta nao conta
        self.conn.commit()
        r = memoria.buscar_falas(self.conn, "pouso", HOJE)
        self.assertEqual([f["dia"] for f in r["falas"]], ["2026-10-21", "2026-10-14"])
        self.assertTrue(all(f["onde"] == "voce falou no chat" for f in r["falas"]))
        c = memoria.card_falas(r)
        self.assertEqual(c["type"], "o_que_falei")
        self.assertEqual(c["data"]["total"], 2)
        self.assertEqual(c["data"]["itens"][0]["dia"], "2026-10-21")

    def test_sem_acerto_e_sem_assunto(self):
        self.assertIn("erro", memoria.buscar_falas(self.conn, "o a de", HOJE))
        r = memoria.buscar_falas(self.conn, "creatina", HOJE)
        self.assertEqual(r["falas"], [])
        self.assertIn("sem inventar", r["obs"])

    def test_pelo_chat_so_manda_o_trecho_e_gera_card(self):
        self.fala("Tomo creatina 5 g depois do treino", "2026-09-15 20:00:00")
        self.fala("outra coisa qualquer", "2026-09-16 20:00:00")
        resp, r = self.chamar_ferramenta("buscar_o_que_falei", {"assunto": "creatina"})
        self.assertEqual(r["total_achados"], 1)
        self.assertNotIn("outra coisa", json.dumps(r))
        self.assertIn("o_que_falei", [c["type"] for c in resp["cards"]])


class NesteDiaTestCase(_Base):
    def test_voo_de_um_ano_atras_e_carga_que_subiu(self):
        db.create_voo(self.conn, "2025-10-29", "SSBL", "SSBL", 0.8, "tremia no rádio")
        db.create_voo(self.conn, "2026-09-02", "SSBL", "SSBL", 1.0, None)  # outro dia: nao entra
        self.conn.execute(
            "INSERT INTO treino_cargas (ficha_id, exercicio, nome, carga, carga_num, data) VALUES (1, 'supino', 'Supino', '75 kg', 75, '2026-09-29')"
        )
        self.conn.execute(
            "INSERT INTO treino_cargas (ficha_id, exercicio, nome, carga, carga_num, data) VALUES (1, 'supino', 'Supino', '85 kg', 85, '2026-10-20')"
        )
        self.conn.commit()
        itens = neste_dia.marcos(self.conn, HOJE)
        rotulos = [i["rotulo"] for i in itens]
        self.assertEqual(rotulos, ["Há 1 ano", "Há 1 mês"])
        self.assertIn("Primeiro voo registrado", itens[0]["texto"])
        self.assertIn("0,8 h", itens[0]["texto"])
        self.assertEqual(itens[0]["quando"], "29/10/2025")  # a data real aparece, nao so o "há 1 ano"
        self.assertEqual(itens[1]["texto"], "Supino 75 kg. Hoje: 85 kg.")
        c = neste_dia.card(self.conn, HOJE)
        self.assertEqual(c["type"], "neste_dia")
        self.assertEqual(c["data"]["rotulo"], "30 de outubro")

    def test_dia_comum_nao_devolve_nada(self):
        self.assertEqual(neste_dia.marcos(self.conn, HOJE), [])
        self.assertIsNone(neste_dia.card(self.conn, HOJE))
        self.assertIn("sem inventar", neste_dia.executar_consulta(self.conn, HOJE)["obs"])

    def test_carga_igual_ou_menor_nao_conta(self):
        for kg, d in ((80, "2026-09-30"), (80, "2026-10-25")):
            self.conn.execute(
                "INSERT INTO treino_cargas (ficha_id, exercicio, nome, carga, carga_num, data) VALUES (1, 'remada', 'Remada', ?, ?, ?)",
                (f"{kg} kg", kg, d),
            )
        self.conn.commit()
        self.assertEqual(neste_dia.marcos(self.conn, HOJE), [])

    def test_manha_publica_uma_vez_no_chat_e_respeita_o_espaco(self):
        db.create_voo(self.conn, "2025-10-30", "SSBL", "SSBL", 1.2, None)
        agora = datetime(2026, 10, 30, 8, 0)
        self.assertEqual(neste_dia.na_manha(self.conn, agora), [])  # nunca pede push
        n = self.conn.execute("SELECT COUNT(*) n FROM chat_mensagens WHERE papel = 'assistant'").fetchone()["n"]
        self.assertEqual(n, 1)
        msg = dict(self.conn.execute("SELECT * FROM chat_mensagens WHERE papel = 'assistant'").fetchone())
        self.assertEqual(db.cards_de_mensagem_chat(msg)[0]["type"], "neste_dia")
        neste_dia.na_manha(self.conn, agora)  # mesmo dia: nada de novo
        self.assertEqual(self.conn.execute("SELECT COUNT(*) n FROM chat_mensagens WHERE papel = 'assistant'").fetchone()["n"], 1)

    def test_fora_da_janela_nao_publica(self):
        db.create_voo(self.conn, "2025-10-30", "SSBL", "SSBL", 1.2, None)
        neste_dia.na_manha(self.conn, datetime(2026, 10, 30, 22, 0))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) n FROM chat_mensagens").fetchone()["n"], 0)

    def test_entra_na_conversa_proativa(self):
        db.create_voo(self.conn, "2025-10-30", "SSBL", "SSBL", 1.2, None)
        conversa_proativa.verificar(self.conn, datetime(2026, 10, 30, 8, 0))
        tipos = [
            c["type"]
            for r in self.conn.execute("SELECT * FROM chat_mensagens WHERE papel = 'assistant'")
            for c in db.cards_de_mensagem_chat(dict(r))
        ]
        self.assertIn("neste_dia", tipos)


class CoincidenciasTestCase(_Base):
    def semear(self, curtas=4, boas=5, tarefas_curta=1, tarefas_boa=6, delivery_curta=40.0):
        """Dias de 1..N antes de HOJE: primeiro as noites curtas (4 h), depois as boas (8 h)."""
        dia = HOJE - timedelta(days=1)
        for lado, n in (("curta", curtas), ("boa", boas)):
            for _ in range(n):
                iso = dia.isoformat()
                db.upsert_saude_dia(self.conn, iso, {"sono_horas": 4.0 if lado == "curta" else 8.0})
                feitas = tarefas_curta if lado == "curta" else tarefas_boa
                for i in range(feitas):
                    # 15h UTC = 12h em Brasilia: cai no mesmo dia
                    self.conn.execute(
                        "INSERT INTO tasks (title, completed_at) VALUES (?, ?)", (f"t{iso}{i}", f"{iso} 15:00:00")
                    )
                if lado == "curta" and delivery_curta:
                    self.conn.execute(
                        "INSERT INTO expenses (amount, category, description, created_at) VALUES (?, 'Delivery', 'ifood', ?)",
                        (delivery_curta, f"{iso} 22:00:00"),
                    )
                dia -= timedelta(days=1)
        self.conn.commit()

    def test_padrao_do_sono_com_numeros_do_proprio_alex(self):
        self.semear()
        ps = coincidencias.padroes(self.conn, HOJE)
        self.assertEqual([p["tipo"] for p in ps], ["sono"])
        p = ps[0]
        self.assertEqual((p["n_bom"], p["n_ruim"]), (5, 4))
        linhas = {l["rotulo"]: l for l in p["linhas"]}
        self.assertEqual(linhas["Tarefas fechadas"]["bom"], 6.0)
        self.assertEqual(linhas["Tarefas fechadas"]["ruim"], 1.0)
        self.assertEqual(linhas["Delivery"]["ruim"], 40.0)
        self.assertEqual(linhas["Delivery"]["unidade"], "R$ ")
        self.assertIn("não prova de causa", p["aviso"])
        self.assertIn("4 noites curtas", p["aviso"])
        self.assertEqual(p["titulo"], "Noite curta pesa no teu dia.")

    def test_menos_de_3_dias_de_um_lado_nao_mostra(self):
        self.semear(curtas=2, boas=5)
        self.assertEqual(coincidencias.padroes(self.conn, HOJE), [])
        self.assertIsNone(coincidencias.card(self.conn, HOJE))

    def test_diferenca_pequena_nao_mostra(self):
        self.semear(tarefas_curta=5, tarefas_boa=5, delivery_curta=0)
        self.assertEqual(coincidencias.padroes(self.conn, HOJE), [])

    def test_titulo_neutro_quando_o_dia_nao_piora(self):
        self.semear(tarefas_curta=5, tarefas_boa=5, delivery_curta=40.0)
        p = coincidencias.padroes(self.conn, HOJE)[0]
        self.assertEqual([l["rotulo"] for l in p["linhas"]], ["Delivery"])
        self.assertEqual(p["titulo"], "O que muda no dia depois de uma noite curta.")

    def test_nao_ligo_pra_isso_esconde_pra_sempre(self):
        self.semear()
        client = self.logado()
        self.assertEqual(client.post("/api/coincidencias/ocultar", json={"tipo": "sono"}).status_code, 200)
        self.assertEqual(client.post("/api/coincidencias/ocultar", json={"tipo": "xyz"}).status_code, 400)
        self.assertEqual(coincidencias.padroes(self.conn, HOJE), [])
        self.assertEqual(len(coincidencias.padroes(self.conn, HOJE, incluir_ocultos=True)), 1)

    def test_sabado_publica_uma_vez_no_chat(self):
        self.semear()
        sabado = datetime(2026, 10, 31, 10, 0)
        coincidencias.na_semana(self.conn, sabado)
        coincidencias.na_semana(self.conn, sabado)
        n = self.conn.execute("SELECT COUNT(*) n FROM chat_mensagens WHERE papel = 'assistant'").fetchone()["n"]
        self.assertEqual(n, 1)

    def test_outro_dia_da_semana_nao_publica(self):
        self.semear()
        coincidencias.na_semana(self.conn, datetime(2026, 10, 30, 10, 0))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) n FROM chat_mensagens").fetchone()["n"], 0)

    def test_card_e_ferramenta_do_chat(self):
        self.semear()
        c = coincidencias.card(self.conn, HOJE)
        self.assertEqual(c["type"], "coincidencia")
        self.assertEqual(c["data"]["periodo"], "últimos 30 dias")
        self.assertTrue(c["data"]["detalhe"])
        m = cards.mascarar_cards([c])[0]["data"]
        self.assertTrue(m["oculto"])
        for campo in ("linhas", "detalhe", "titulo", "aviso"):
            self.assertNotIn(campo, m)
        sem = coincidencias.executar_consulta(db.get_db(), date(2020, 1, 1))
        self.assertIn("sem dados suficientes", sem["obs"])


if __name__ == "__main__":
    unittest.main()
