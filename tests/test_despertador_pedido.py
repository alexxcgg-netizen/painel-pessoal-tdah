"""2026-10-16: "amanha quero acordar as 7" -> `definir_despertador` guarda o pedido, o card traz o botao
que abre o Atalho "Despertador do Painel" e GET /api/atalho/despertador devolve a hora (o mais cedo
entre o pedido e o que um compromisso exige). Banco temporario; nenhuma rede."""
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import despertador  # noqa: E402

PIN = "135790"
BASE = date(2030, 3, 11)
NOITE = datetime.combine(BASE, time(22, 0))
AMANHA = (BASE + timedelta(days=1)).isoformat()


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class DespertadorPedidoTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        db.definir_configuracao(conn, "voo_briefing_min", "45")
        db.definir_configuracao(conn, "tempo_se_arrumar_min", "45")
        conn.commit()
        conn.close()
        for p in (patch.dict(os.environ, {"ENDERECO_CASA": "", "CIDADE_PADRAO": "", "PAINEL_ATALHOS_TOKEN": ""}),
                  patch("maps_client.configurado", return_value=False),
                  patch("app._clima_contexto_resumo", return_value=None),
                  patch("app._agora_brasilia", return_value=NOITE)):
            p.start()
            self.addCleanup(p.stop)
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            linhas = conn.execute(query, params).fetchall()
            conn.commit()
            return linhas
        finally:
            conn.close()

    def chat(self, entrada):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            resultados.append(executores["definir_despertador"](entrada))
            return "Anotei.", ["definir_despertador"], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "amanha quero acordar as 7"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados[0]

    def endpoint(self, query="", quando=NOITE):
        with patch("app._agora_brasilia", return_value=quando):
            return self.client.get(f"/api/atalho/despertador{query}").get_json()

    def test_pedido_vira_card_com_botao_do_atalho_e_endpoint_devolve(self):
        corpo, res = self.chat({"hora": "7h"})
        self.assertTrue(res["ok"], res)
        self.assertEqual((res["hora"], res["data"]), ("07:00", AMANHA))
        card = next(c for c in corpo["cards"] if c["type"] == "despertador")
        self.assertEqual((card["data"]["hora"], card["data"]["data"], card["data"]["pedida"]), ("07:00", AMANHA, None))
        link = card["actions"][0]
        self.assertEqual(link["tipo"], "abrir_link")
        self.assertEqual(link["url"], "shortcuts://run-shortcut?name=Despertador%20do%20Painel")
        r = self.endpoint("?ate=06:00")  # o `ate` nao barra um pedido explicito
        self.assertEqual((r["tem"], r["acordar"], r["titulo"]), (True, "07:00", "pedido"))
        self.assertEqual(r["acordar_iso"], f"{AMANHA}T07:00:00")
        self.assertIn("você pediu", r["mensagem"])

    def test_compromisso_que_exige_antes_ganha_e_a_ia_e_avisada(self):
        self.sql("INSERT INTO voos (data, origem, destino, hora) VALUES (?, 'SSBL', 'SSBL', '08:00')", (AMANHA,))
        corpo, res = self.chat({"hora": "07:00"})
        self.assertIn("06:15", res["aviso_compromisso"])
        card = next(c for c in corpo["cards"] if c["type"] == "despertador")
        self.assertEqual((card["data"]["hora"], card["data"]["pedida"]), ("06:15", "07:00"))
        r = self.endpoint()
        self.assertEqual((r["acordar"], r["titulo"], r["hora"]), ("06:15", "voo", "08:00"))
        self.assertIn("pede antes das 07:00", r["mensagem"])

    def test_pedido_mais_cedo_que_o_compromisso_vale_o_pedido(self):
        self.sql("INSERT INTO voos (data, origem, destino, hora) VALUES (?, 'SSBL', 'SSBL', '08:00')", (AMANHA,))
        _, res = self.chat({"hora": "05:30"})
        self.assertNotIn("aviso_compromisso", res)
        self.assertEqual(self.endpoint()["acordar"], "05:30")

    def test_so_vale_pra_data_pedida(self):
        self.chat({"hora": "07:00"})
        depois = datetime.combine(BASE + timedelta(days=1), time(22, 0))
        self.assertFalse(self.endpoint(quando=depois)["tem"])  # dia seguinte ao do pedido: nada
        # madrugada do proprio dia (1h): "acordar as 7" e hoje
        r = self.endpoint(quando=datetime.combine(BASE + timedelta(days=1), time(1, 0)))
        self.assertEqual((r["tem"], r["acordar"]), (True, "07:00"))

    def test_hora_invalida_hora_que_passou_e_cancelar(self):
        self.assertIn("erro", self.chat({"hora": "banana"})[1])
        _, passou = self.chat({"hora": "21:00", "quando_data": BASE.isoformat()})
        self.assertIn("ja passou", passou["erro"])
        self.assertIn("erro", self.chat({"hora": "07:00", "quando_data": "2030-02-01"})[1])
        self.chat({"hora": "07:00"})
        self.assertTrue(self.endpoint()["tem"])
        _, cancelado = self.chat({"cancelar": True})
        self.assertEqual(cancelado, {"ok": True, "cancelado": True})
        self.assertFalse(self.endpoint()["tem"])

    def test_modulo_pedido_ignora_lixo_na_configuracao(self):
        conn = db.get_db()
        try:
            for lixo in ("", "nao e json", "[]", '{"data": "x"}', '{"data": "%s", "hora": 7}' % AMANHA):
                db.definir_configuracao(conn, despertador.CHAVE, lixo)
                self.assertIsNone(despertador.pedido(conn, AMANHA), lixo)
        finally:
            conn.close()

    def test_aceita_7h_7h30_e_nada_estranho(self):
        for texto, esperado in (("07:00", "07:00"), ("7:5x", None), ("7h", "07:00"), ("7h30", "07:30"), ("7", "07:00"),
                                ("6 horas", "06:00"), ("24h", None), ("7h61", None), ("banana", None), (None, None), (7, None)):
            self.assertEqual(despertador.normalizar_hora(texto), esperado, texto)

    def test_ferramenta_no_prompt_e_no_dispatch(self):
        from ia.funcoes import chat as chat_mod

        self.assertIn("DESPERTADOR:", chat_mod.CHAT_SYSTEM_PROMPT)
        self.assertIn("definir_despertador", {t["name"] for t in chat_mod.CHAT_TOOLS})

    def test_regra_baixa_pelo_que_ele_conta(self):
        # "estou no banco agora" tem que dar baixa sozinho; atrasada que a fala nao cobre vira pergunta
        from ia.funcoes import chat as chat_mod

        p = chat_mod.CHAT_SYSTEM_PROMPT
        self.assertIn("BAIXA PELO QUE ELE CONTA", p)
        self.assertIn('status "concluir" NA MESMA', p)
        self.assertIn("ajustar_tarefa", {t["name"] for t in chat_mod.CHAT_TOOLS})


if __name__ == "__main__":
    unittest.main()
