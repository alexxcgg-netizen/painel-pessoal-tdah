from unittest.mock import patch
# Testes da faixa N1 (Fase 7) - rotas/n1_financas.py, via app.py de
# verdade (registrado automaticamente por rotas.registrar_todas na
# subida - infra da Etapa 0, ja mesclada em fase7/integracao). Mesmo
# padrao de tests/test_app.py: DB_PATH temporario + login por PIN de
# verdade, exercitando o gate de autenticacao real.
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402 (precisa vir depois do patch de DB_PATH)

PIN_TESTE = "123456"


class _Base(unittest.TestCase):
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


class TestRotaExigeLogin(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()

    def test_sem_sessao_401(self):
        client = app.app.test_client()
        res = client.get("/api/financas/assinaturas")
        self.assertEqual(res.status_code, 401)

    def test_sem_sessao_bloqueia_escrita_tambem(self):
        client = app.app.test_client()
        res = client.post("/api/financas/assinaturas", json={"nome": "X", "valor": 10, "dia_cobranca": 5})
        self.assertEqual(res.status_code, 401)


class TestCrudAssinaturas(_Base):
    def test_criar_e_listar(self):
        res = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24}
        )
        self.assertEqual(res.status_code, 201)
        corpo = res.get_json()
        self.assertEqual(corpo["nome"], "Netflix")
        self.assertEqual(corpo["valor"], 55.0)

        res = self.client.get("/api/financas/assinaturas")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()["assinaturas"]), 1)

    def test_criar_sem_nome_400(self):
        res = self.client.post("/api/financas/assinaturas", json={"valor": 10, "dia_cobranca": 5})
        self.assertEqual(res.status_code, 400)

    def test_criar_sem_valor_400(self):
        res = self.client.post("/api/financas/assinaturas", json={"nome": "X", "dia_cobranca": 5})
        self.assertEqual(res.status_code, 400)

    def test_criar_dia_cobranca_invalido_400(self):
        res = self.client.post(
            "/api/financas/assinaturas", json={"nome": "X", "valor": 10, "dia_cobranca": 40}
        )
        self.assertEqual(res.status_code, 400)

    def test_criar_corpo_vazio_400(self):
        res = self.client.post("/api/financas/assinaturas", data="nao e json", content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_obter_inexistente_404(self):
        res = self.client.get("/api/financas/assinaturas/99999")
        self.assertEqual(res.status_code, 404)

    def test_obter_existente(self):
        criada = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24}
        ).get_json()
        res = self.client.get(f"/api/financas/assinaturas/{criada['id']}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["nome"], "Netflix")

    def test_atualizar(self):
        criada = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24}
        ).get_json()
        res = self.client.patch(f"/api/financas/assinaturas/{criada['id']}", json={"valor": 60})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["valor"], 60.0)

    def test_atualizar_inexistente_404(self):
        res = self.client.patch("/api/financas/assinaturas/99999", json={"valor": 60})
        self.assertEqual(res.status_code, 404)

    def test_cancelar(self):
        criada = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24}
        ).get_json()
        res = self.client.post(f"/api/financas/assinaturas/{criada['id']}/cancelar")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["ativa"], 0)

    def test_cancelar_duas_vezes_segunda_404(self):
        criada = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24}
        ).get_json()
        self.client.post(f"/api/financas/assinaturas/{criada['id']}/cancelar")
        res = self.client.post(f"/api/financas/assinaturas/{criada['id']}/cancelar")
        self.assertEqual(res.status_code, 404)

    def test_excluir(self):
        criada = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24}
        ).get_json()
        res = self.client.delete(f"/api/financas/assinaturas/{criada['id']}")
        self.assertEqual(res.status_code, 200)
        res = self.client.get(f"/api/financas/assinaturas/{criada['id']}")
        self.assertEqual(res.status_code, 404)

    def test_excluir_inexistente_404(self):
        res = self.client.delete("/api/financas/assinaturas/99999")
        self.assertEqual(res.status_code, 404)

    def test_listar_apenas_ativas(self):
        a = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Ativa", "valor": 10, "dia_cobranca": 5}
        ).get_json()
        b = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Cancelada", "valor": 10, "dia_cobranca": 5}
        ).get_json()
        self.client.post(f"/api/financas/assinaturas/{b['id']}/cancelar")
        res = self.client.get("/api/financas/assinaturas?ativas=1")
        nomes = [x["nome"] for x in res.get_json()["assinaturas"]]
        self.assertIn("Ativa", nomes)
        self.assertNotIn("Cancelada", nomes)


class TestCrudParcelas(_Base):
    def test_criar_com_valor_parcela(self):
        res = self.client.post(
            "/api/financas/parcelas",
            json={"descricao": "celular", "n_parcelas": 10, "valor_parcela": 300},
        )
        self.assertEqual(res.status_code, 201)
        corpo = res.get_json()
        self.assertEqual(corpo["valor_total"], 3000.0)
        self.assertIn("parcelas_restantes", corpo)

    def test_criar_sem_valor_nenhum_400(self):
        res = self.client.post("/api/financas/parcelas", json={"descricao": "celular", "n_parcelas": 10})
        self.assertEqual(res.status_code, 400)

    def test_criar_n_parcelas_invalido_400(self):
        res = self.client.post(
            "/api/financas/parcelas", json={"descricao": "celular", "n_parcelas": 0, "valor_total": 100}
        )
        self.assertEqual(res.status_code, 400)

    def test_listar(self):
        self.client.post(
            "/api/financas/parcelas", json={"descricao": "celular", "n_parcelas": 10, "valor_parcela": 300}
        )
        res = self.client.get("/api/financas/parcelas")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()["parcelas"]), 1)

    def test_obter_inexistente_404(self):
        res = self.client.get("/api/financas/parcelas/99999")
        self.assertEqual(res.status_code, 404)

    def test_excluir(self):
        criada = self.client.post(
            "/api/financas/parcelas", json={"descricao": "celular", "n_parcelas": 10, "valor_parcela": 300}
        ).get_json()
        res = self.client.delete(f"/api/financas/parcelas/{criada['id']}")
        self.assertEqual(res.status_code, 200)
        res = self.client.get(f"/api/financas/parcelas/{criada['id']}")
        self.assertEqual(res.status_code, 404)


class TestComprometido(_Base):
    @patch("rotas.n1_financas.date")
    def test_formato_da_resposta(self, mock_date):
        from datetime import date
        mock_date.today.return_value = date(2026, 9, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24, "inicio": "2026-09-01"}
        )
        self.client.post(
            "/api/financas/parcelas", json={"descricao": "celular", "n_parcelas": 10, "valor_parcela": 300, "primeira_parcela": "2026-09-01"}
        )
        res = self.client.get("/api/financas/comprometido")
        self.assertEqual(res.status_code, 200)
        corpo = res.get_json()
        self.assertIn("total_mensal", corpo)
        self.assertIn("proximas_cobrancas", corpo)
        self.assertIn("impacto_limite_cartao", corpo)
        self.assertAlmostEqual(corpo["total_mensal"]["total"], 355.0, places=2)

    def test_vazio_nao_quebra(self):
        res = self.client.get("/api/financas/comprometido")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["total_mensal"]["total"], 0.0)


class TestDesfazer(_Base):
    def test_desfaz_criacao_via_desfazer_local(self):
        import financas_recorrentes as fr

        criada = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24}
        ).get_json()
        conn = db.get_db()
        token = fr.criar_token_desfazer(conn, "assinatura", "criar", criada["id"])
        conn.close()

        res = self.client.post(f"/api/financas/desfazer/{token}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["desfeitos"], 1)

        res = self.client.get(f"/api/financas/assinaturas/{criada['id']}")
        self.assertEqual(res.status_code, 404)

    def test_token_invalido_404(self):
        res = self.client.post("/api/financas/desfazer/token-que-nao-existe")
        self.assertEqual(res.status_code, 404)

    def test_token_usado_duas_vezes_409(self):
        import financas_recorrentes as fr

        criada = self.client.post(
            "/api/financas/assinaturas", json={"nome": "Netflix", "valor": 55, "dia_cobranca": 24}
        ).get_json()
        conn = db.get_db()
        token = fr.criar_token_desfazer(conn, "assinatura", "criar", criada["id"])
        conn.close()
        self.client.post(f"/api/financas/desfazer/{token}")
        res = self.client.post(f"/api/financas/desfazer/{token}")
        self.assertEqual(res.status_code, 409)


class TestChatUsaClassificadorLocalSemIA(_Base):
    """Confere a integracao completa via /api/chat: a regra local resolve
    sozinha, sem chamar a IA (Claude) - mesmo padrao descrito no README de
    classificador_local/."""

    def test_assinar_via_chat_nao_chama_ia(self):
        from unittest.mock import patch

        with patch("claude_client.chat") as chat_mock:
            res = self.client.post("/api/chat", json={"mensagem": "assinei Netflix 55 por mês"})
            self.assertEqual(res.status_code, 200)
            chat_mock.assert_not_called()
        corpo = res.get_json()
        self.assertIn("cards", corpo)
        tipos = [c["type"] for c in corpo["cards"]]
        self.assertIn("assinatura", tipos)


if __name__ == "__main__":
    unittest.main()
