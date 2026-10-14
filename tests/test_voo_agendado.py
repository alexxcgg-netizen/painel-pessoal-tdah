"""Card do voo agendado (2026-10-14, docs/CARDS.md "Linguagem visual dos cards").

Pedido do Alex: voo sem origem dita sai de Blumenau (SSBL); navegacao com escalas mostra as
pernas em milhas nauticas; o card diz a hora de chegar (antecedencia das "Rotinas fixas") e a
de sair de casa. Mesmo esquema do test_vivo_edicao: banco temporario, login real e
claude_client.chat dublado chamando os executores de verdade."""
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
import rota_voo  # noqa: E402

PIN = "246810"
SABADO = (date.today() + timedelta(days=3)).isoformat()


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class RotaVooTestCase(unittest.TestCase):
    def test_navegacao_com_escalas_mede_cada_perna_e_estima_os_horarios(self):
        r = rota_voo.montar("SSBL", "SBNF,SBFL", "SSBL", "14:00")
        self.assertEqual([p["icao"] for p in r["paradas"]], ["SSBL", "SBNF", "SBFL", "SSBL"])
        self.assertEqual([p["nm"] for p in r["pernas"]], [24, 48, 58])
        self.assertEqual(r["total_nm"], 130)
        self.assertEqual(r["paradas"][1]["pousa"], "14:22")
        self.assertEqual(r["paradas"][1]["decola"], "14:37")
        self.assertEqual(r["pouso"], "16:15")
        self.assertFalse(r["local"])

    def test_voo_local_nao_tem_pernas(self):
        r = rota_voo.montar("SSBL", None, "SSBL", "09:30")
        self.assertTrue(r["local"])
        self.assertEqual(r["pernas"], [])
        self.assertIsNone(r["total_nm"])

    def test_aerodromo_desconhecido_fica_sem_nm_e_sem_total(self):
        r = rota_voo.montar("SSBL", "SJVL", "SSBL", "14:00")
        self.assertIsNone(r["pernas"][0]["nm"])
        self.assertIsNone(r["total_nm"])
        self.assertIsNone(r["pouso"])

    def test_nome_falado_vira_icao(self):
        self.assertEqual(rota_voo.aerodromo("Navegantes"), "SBNF")
        self.assertEqual(rota_voo.aerodromo("florianópolis"), "SBFL")
        self.assertEqual(rota_voo.aerodromo("sbnf"), "SBNF")
        self.assertIsNone(rota_voo.aerodromo("  "))
        self.assertEqual(rota_voo.escalas_texto(["Navegantes", "Floripa", 3]), "SBNF,SBFL")


class VooAgendadoChatTestCase(unittest.TestCase):
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

    def chat(self, chamadas):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Feito.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "sabado voo as 14h"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados

    def test_voo_sem_origem_sai_de_blumenau_e_vira_cartao_de_embarque(self):
        self.sql("INSERT INTO configuracoes (chave, valor) VALUES ('voo_briefing_min', '45')")
        self.sql("INSERT INTO voos (data, origem, destino, horas) VALUES ('2026-01-10', 'SSBL', 'SSBL', 2.5)")
        corpo, res = self.chat([("registrar_voo", {
            "data": SABADO, "destino": "SSBL", "escalas": ["Navegantes", "SBFL"], "hora": "14:00",
        })])
        self.assertEqual(res[0]["rota"], "SSBL -> SBNF -> SBFL -> SSBL")
        self.assertEqual(res[0]["milhas_nauticas"], 130)
        self.assertEqual(res[0]["chegar_no_aeroclube"], "13:15")
        linha = self.sql("SELECT origem, destino, escalas, horas FROM voos WHERE data = ?", (SABADO,))[0]
        self.assertEqual(tuple(linha), ("SSBL", "SSBL", "SBNF,SBFL", None))

        card = next(c for c in corpo["cards"] if c["type"] == "voo_agendado")
        d = card["data"]
        self.assertEqual(d["chegar"], "13:15")
        self.assertEqual(d["antecedencia_min"], 45)
        self.assertEqual(d["total_nm"], 130)
        self.assertEqual(d["horas_min"], 150)
        self.assertEqual(d["meta_horas"], 150)
        self.assertIsNone(d["sair_casa"])  # sem Maps no teste: so a hora de chegar
        tipos = [a["tipo"] for a in card["actions"]]
        self.assertIn("desfazer", tipos)
        self.assertIn("abrir_aba", tipos)

        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM voos WHERE data = ?", (SABADO,))[0][0], 0)

    def test_hora_de_sair_vem_do_maps_quando_configurado(self):
        with patch.dict(os.environ, {"ENDERECO_CASA": "casa de teste"}), \
             patch("maps_client.configurado", return_value=True), \
             patch("maps_client.horario_de_saida",
                   return_value={"sair_ate": f"{SABADO}T12:10:00", "duracao_minutos": 65}) as maps:
            corpo, res = self.chat([("registrar_voo", {"data": SABADO, "destino": "SBNF", "hora": "14:00"})])
        self.assertEqual(maps.call_args[0][0], "casa de teste")
        self.assertEqual(res[0]["sair_de_casa"], "12:10")
        d = next(c for c in corpo["cards"] if c["type"] == "voo_agendado")["data"]
        self.assertEqual((d["sair_casa"], d["trajeto_min"]), ("12:10", 65))

    def test_maps_fora_do_ar_nao_derruba_o_registro(self):
        with patch.dict(os.environ, {"ENDERECO_CASA": "casa de teste"}), \
             patch("maps_client.configurado", return_value=True), \
             patch("maps_client.horario_de_saida", side_effect=RuntimeError("sem rede")):
            corpo, res = self.chat([("registrar_voo", {"data": SABADO, "destino": "SBNF", "hora": "14:00"})])
        self.assertTrue(res[0]["ok"])
        self.assertNotIn("sair_de_casa", res[0])
        self.assertTrue(any(c["type"] == "voo_agendado" for c in corpo["cards"]))

    def test_voo_ja_voado_continua_no_resumo_de_horas(self):
        corpo, _ = self.chat([("registrar_voo", {"data": "2026-01-10", "destino": "SSBL", "horas": 1.2})])
        self.assertEqual([c["type"] for c in corpo["cards"]], ["voo_resumo"])

    def test_desfazer_nao_apaga_voo_que_ja_ganhou_horas(self):
        corpo, _ = self.chat([("registrar_voo", {"data": SABADO, "destino": "SSBL", "hora": "09:00"})])
        card = next(c for c in corpo["cards"] if c["type"] == "voo_agendado")
        self.sql("UPDATE voos SET horas = 1.1 WHERE data = ?", (SABADO,))
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.client.post(f"/api/desfazer/{token}")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM voos WHERE data = ?", (SABADO,))[0][0], 1)

    def test_ajustar_antecedencia_do_voo(self):
        _, res = self.chat([("ajustar_antecedencia_voo", {"minutos": 45})])
        self.assertEqual(res[0], {"ok": True, "minutos": 45})
        self.assertEqual(self.sql("SELECT valor FROM configuracoes WHERE chave = 'voo_briefing_min'")[0][0], "45")
        _, res = self.chat([("ajustar_antecedencia_voo", {"minutos": 500})])
        self.assertIn("erro", res[0])


if __name__ == "__main__":
    unittest.main()
