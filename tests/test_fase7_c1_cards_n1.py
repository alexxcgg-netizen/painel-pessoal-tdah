"""Fase 7 / C1 - historia 7: cards de assinatura/parcela (N1) cadastrados em
cards.py e o Desfazer geral (POST /api/desfazer/<token>) entendendo os tokens
da N1. Tudo local (classificador_local da N1, sem IA); banco temporario."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import cards  # noqa: E402
import financas_recorrentes as fr  # noqa: E402

PIN_TESTE = "123456"
HOJE = date(2026, 9, 24)


class _Base(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        assert self.client.post("/login", json={"pin": PIN_TESTE}).status_code == 200

    def _chat(self, texto):
        with patch("claude_client.chat", side_effect=AssertionError("N1 e local, sem IA")):
            res = self.client.post("/api/chat", json={"mensagem": texto})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json()

    def _token(self, corpo, tipo):
        card = next(c for c in corpo["cards"] if c["type"] == tipo)
        return next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")

    def _contar(self, tabela):
        conn = db.get_db()
        try:
            return conn.execute(f"SELECT COUNT(*) AS n FROM {tabela}").fetchone()["n"]
        finally:
            conn.close()


class RegistroEmCardsTestCase(unittest.TestCase):
    def test_tipos_cadastrados(self):
        for tipo in ("assinatura", "compra_parcelada", "resumo_financeiro_recorrente"):
            self.assertIn(tipo, cards.TIPOS_CARD)
            self.assertIn(tipo, cards.CAMPOS_SENSIVEIS)
        self.assertEqual(cards.ABA_POR_ENTIDADE["assinatura"][0], "gastos")

    def test_builders_levam_contrato_n1_e_nomes_do_renderizador(self):
        a = {"id": 1, "nome": "Streaming Sintetico", "valor": 21.9, "dia_cobranca": 30, "cartao_ou_forma": "nubank",
             "categoria": None, "ativa": 1, "inicio": "2026-09-01", "cancelada_em": None}
        data = cards.assinatura_para_card(a, HOJE)["data"]
        self.assertEqual(data["proxima_cobranca"], "2026-09-30")
        self.assertEqual((data["cartao"], data["em_dias"]), ("nubank", 6))
        c = {"id": 2, "descricao": "geladeira", "valor_total": 3000.0, "n_parcelas": 12, "valor_parcela": 250.0,
             "cartao": None, "primeira_parcela": "2026-09-24", "categoria": None}
        data = cards.compra_parcelada_para_card(c, HOJE)["data"]
        self.assertEqual((data["parcela_atual"], data["parcelas_restantes"], data["restantes"]), (1, 12, 12))
        self.assertEqual((data["mes_termino"], data["termina_em"]), ("2027-08", "2027-08-24"))
        resumo = cards.resumo_recorrente_para_card({
            "mes": "2026-09", "total_mensal": 271.9, "assinaturas_total": 21.9, "parcelas_total": 250.0,
            "n_assinaturas_ativas": 1, "n_compras_em_andamento": 1,
            "proximas_cobrancas": [{"tipo": "assinatura", "id": 1, "nome": "X", "valor": 21.9, "data": "2026-09-30"}],
        })["data"]
        self.assertEqual((resumo["total_mes"], resumo["n_assinaturas"], resumo["n_parcelas"]), (271.9, 1, 1))
        self.assertEqual(resumo["proxima_cobranca"], {"nome": "X", "data": "2026-09-30"})
        vazio = cards.resumo_recorrente_para_card({"proximas_cobrancas": []})["data"]
        self.assertIsNone(vazio["proxima_cobranca"])

    def test_modo_visitante_esconde_dinheiro_dos_3_tipos(self):
        lista = [
            cards.novo_card("assinatura", {"nome": "X", "valor": 10.0}, [{"tipo": "desfazer", "token": "t"}]),
            cards.novo_card("compra_parcelada", {"descricao": "Y", "valor_total": 30.0, "valor_parcela": 10.0}),
            cards.novo_card("resumo_financeiro_recorrente", {"total_mensal": 40.0, "total_mes": 40.0,
                                                             "proximas_cobrancas": [{"valor": 1}],
                                                             "proxima_cobranca": {"nome": "Z"}}),
        ]
        mascarados = cards.mascarar_cards(lista)
        texto = str(mascarados)
        for valor in ("10.0", "30.0", "40.0", "'valor'"):
            self.assertNotIn(valor, texto)
        self.assertTrue(all(c["data"]["oculto"] for c in mascarados))
        self.assertEqual(mascarados[0]["actions"], [])


class DesfazerGeralEntendeN1TestCase(_Base):
    def test_criar_assinatura_desfaz_pela_rota_geral(self):
        corpo = self._chat("assinei Netflix 55 por mês")
        self.assertEqual(self._contar("assinatura"), 1)
        token = self._token(corpo, "assinatura")
        res = self.client.post(f"/api/desfazer/{token}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"ok": True, "desfeitos": 1})
        self.assertEqual(self._contar("assinatura"), 0)
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 409)
        # a rota propria da N1 tambem ve o token como ja desfeito
        self.assertEqual(self.client.post(f"/api/financas/desfazer/{token}").status_code, 409)

    def test_cancelar_assinatura_desfaz_reativando(self):
        self._chat("assinei o Spotify por 21,90")
        corpo = self._chat("cancelei o Spotify")
        token = self._token(corpo, "assinatura")
        res = self.client.post(f"/api/desfazer/{token}")
        self.assertEqual(res.get_json()["desfeitos"], 1)
        conn = db.get_db()
        ativa = conn.execute("SELECT ativa, cancelada_em FROM assinatura").fetchone()
        conn.close()
        self.assertEqual((ativa["ativa"], ativa["cancelada_em"]), (1, None))

    def test_compra_parcelada_desfaz_pela_rota_geral(self):
        corpo = self._chat("comprei geladeira 3000 em 12 vezes no nubank")
        token = self._token(corpo, "compra_parcelada")
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").get_json()["desfeitos"], 1)
        self.assertEqual(self._contar("compra_parcelada"), 0)

    def test_rota_propria_da_n1_continua_valendo(self):
        corpo = self._chat("assinei Netflix 55 por mês")
        token = self._token(corpo, "assinatura")
        self.assertEqual(self.client.post(f"/api/financas/desfazer/{token}").status_code, 200)
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 409)

    def test_consulta_vem_com_aliases_do_renderizador(self):
        self._chat("assinei Netflix 55 por mês")
        corpo = self._chat("quais assinaturas eu tenho")
        tipos = [c["type"] for c in corpo["cards"]]
        self.assertIn("assinatura", tipos)
        card = next(c for c in corpo["cards"] if c["type"] == "assinatura")
        self.assertIn("em_dias", card["data"])
        self.assertTrue(card["data"]["consulta"])

    def test_efeito_de_modulo_vira_card(self):
        conn = db.get_db()
        try:
            aid = fr.criar_assinatura(conn, "Musica Sintetica", 9.9, 5)
            lista = cards.cards_dos_efeitos(conn, [{"entidade": "assinatura", "id": aid}])
        finally:
            conn.close()
        self.assertEqual(lista[0]["type"], "assinatura")
        self.assertEqual(lista[0]["actions"][-1]["aba"], "gastos")


if __name__ == "__main__":
    unittest.main()
