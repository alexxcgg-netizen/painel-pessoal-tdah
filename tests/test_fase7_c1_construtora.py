"""Fase 7 / C1 - historia 4: app.py le a construtora so pelo
construtora_cliente.py (A10). O painel pessoal mostra so gastos, entradas e o
tempo ate a proxima conta - nunca lucro, margem nem VGV - e o modo mock
(CONSTRUTORA_API_MOCK=1) funciona na rota real. Nenhuma chamada de rede real:
requests.get e sempre mockado (ou o modo mock nem chama rede)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import construtora_cliente  # noqa: E402

PIN_TESTE = "123456"
ENV_REAL = {"CONSTRUTORA_API_URL": "https://construtora.exemplo.com", "CONSTRUTORA_API_KEY": "chave"}
# Decisao do Alex 10/10: o "lucro das obras prontas" (pronto da construtora) pode aparecer;
# o lucro_liquido/margem GERAIS e o vgv continuam fora (52500/61234 = lucro_liquido dos dubles).
PROIBIDOS = ("margem", "vgv", "52500", "61234", "999999")

RESUMO_COM_TUDO = {
    "status": "ok", "tot_entradas": 100000.0, "tot_saidas": 40000.0,
    "lucro_liquido": 61234.0, "margem": 60.0, "vgv": 999999.0,
    "saldo_caixa": 48915.81, "a_receber": 1258000.0, "lucro_obras_fechadas": 371009.45,
    "obras_fechadas": 1, "estoque_a_venda": 1160000.0, "unidades_a_venda": 4,
    "vendido": 2330000.0,
}


def _fake_get(resumo=None, contas=None):
    def fake(url, headers=None, params=None, timeout=None):
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        if url.endswith("/api/resumo"):
            resp.json.return_value = resumo if resumo is not None else RESUMO_COM_TUDO
        else:
            resp.json.return_value = {"status": "ok", "contas": contas if contas is not None else []}
        return resp
    return fake


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
        app._CACHE_CONSTRUTORA.clear()
        self.addCleanup(app._CACHE_CONSTRUTORA.clear)
        p = patch.dict(os.environ, {})  # restaura o ambiente no fim
        p.start()
        self.addCleanup(p.stop)
        for var in ("CONSTRUTORA_API_URL", "CONSTRUTORA_API_KEY", "CONSTRUTORA_API_MOCK"):
            os.environ.pop(var, None)
        self.client = app.app.test_client()
        assert self.client.post("/login", json={"pin": PIN_TESTE}).status_code == 200

    def assertSemProibidos(self, texto):
        baixo = str(texto).lower()
        for palavra in PROIBIDOS:
            self.assertNotIn(palavra, baixo)


class UsaOClienteA10TestCase(_Base):
    def test_app_usa_a_instancia_padrao_do_cliente(self):
        self.assertIs(app._cliente_construtora(), construtora_cliente.cliente_padrao())
        # clear() dos testes antigos limpa o cache do cliente padrao
        cliente = construtora_cliente.cliente_padrao()
        cliente._cache_set("resumo", {"status": "ok"})
        app._CACHE_CONSTRUTORA.clear()
        self.assertIsNone(cliente._cache_get("resumo"))

    def test_app_nao_chama_requests_direto_pra_construtora(self):
        import inspect
        fonte = inspect.getsource(app._buscar_resumo_construtora) + inspect.getsource(
            app._buscar_contas_a_vencer_construtora)
        self.assertNotIn("requests.get", fonte)

    def test_rota_sem_configuracao(self):
        res = self.client.get("/api/construtora/resumo")
        self.assertEqual(res.get_json(), {"configurado": False})

    def test_rota_real_filtra_lucro_margem_vgv(self):
        contas = [{"vencimento": "2026-10-01", "valor": 500.0, "fornecedor": "Fornecedor X",
                   "descricao": "", "dias_ate_vencer": 5, "obra": "Residencial Segredo"}]
        with patch.dict(os.environ, ENV_REAL), patch("requests.get", side_effect=_fake_get(contas=contas)):
            res = self.client.get("/api/construtora/resumo")
        corpo = res.get_json()
        self.assertTrue(corpo["configurado"])
        self.assertEqual(corpo["dados"], {
            "status": "ok", "tot_entradas": 100000.0, "tot_saidas": 40000.0,
            "saldo_caixa": 48915.81, "a_receber": 1258000.0, "lucro_obras_fechadas": 371009.45,
            "obras_fechadas": 1, "estoque_a_venda": 1160000.0, "unidades_a_venda": 4,
        })  # lucro_liquido/margem/vgv/vendido nunca passam
        self.assertEqual(corpo["contas"][0]["fornecedor"], "Fornecedor X")
        self.assertNotIn("obra", corpo["contas"][0])
        self.assertSemProibidos(res.get_data(as_text=True))

    def test_rota_com_falha_de_rede_502(self):
        import requests
        with patch.dict(os.environ, ENV_REAL), \
                patch("requests.get", side_effect=requests.RequestException("fora do ar")):
            res = self.client.get("/api/construtora/resumo")
        self.assertEqual(res.status_code, 502)

    def test_resposta_estranha_da_api_nao_quebra(self):
        for resumo in ([], "texto", {"status": "ok", "tot_entradas": "muito", "tot_saidas": None}):
            with self.subTest(resumo=resumo), patch.dict(os.environ, ENV_REAL), \
                    patch("requests.get", side_effect=_fake_get(resumo=resumo, contas=[{"x": 1}, "lixo"])):
                app._CACHE_CONSTRUTORA.clear()
                res = self.client.get("/api/construtora/resumo")
                self.assertIn(res.status_code, (200, 502))
                self.assertIsNone(app._construtora_contexto_resumo())


class ModoMockNaRotaRealTestCase(_Base):
    def test_mock_funciona_sem_url_nem_chave_e_sem_rede(self):
        with patch.dict(os.environ, {"CONSTRUTORA_API_MOCK": "1"}), \
                patch("requests.get", side_effect=AssertionError("mock nao usa rede")):
            res = self.client.get("/api/construtora/resumo")
        self.assertEqual(res.status_code, 200)
        corpo = res.get_json()
        self.assertTrue(corpo["configurado"])
        self.assertEqual(set(corpo["dados"]), set(app.CAMPOS_RESUMO_CONSTRUTORA_PERMITIDOS))
        self.assertGreater(len(corpo["contas"]), 0)
        self.assertTrue(any(c["dias_ate_vencer"] < 0 for c in corpo["contas"]))  # mock tem uma vencida
        self.assertSemProibidos(res.get_data(as_text=True))

    def test_mock_alimenta_o_contexto_do_resumo_do_dia(self):
        with patch.dict(os.environ, {"CONSTRUTORA_API_MOCK": "1"}), \
                patch("requests.get", side_effect=AssertionError("mock nao usa rede")):
            texto = app._construtora_contexto_resumo()
        self.assertIn("dinheiro em caixa hoje R$", texto)
        self.assertIn("a receber das vendas", texto)
        self.assertIn("próxima conta a pagar da construtora", texto)
        self.assertSemProibidos(texto)


class ContextoEPushTestCase(_Base):
    def test_contexto_so_gastos_entradas_e_tempo_da_proxima_conta(self):
        contas = [{"vencimento": "2026-10-01", "valor": 1234.56, "fornecedor": "Areia & Cia",
                   "descricao": "", "dias_ate_vencer": 3}]
        with patch.dict(os.environ, ENV_REAL), patch("requests.get", side_effect=_fake_get(contas=contas)):
            texto = app._construtora_contexto_resumo()
        self.assertEqual(texto, "dinheiro em caixa hoje R$ 48915.81, a receber das vendas ja feitas R$ 1258000.00, "
                                "lucro das obras prontas R$ 371009.45, a venda R$ 1160000.00 (4 unidades) "
                                "(numeros prontos da construtora, nao recalcule); "
                                "próxima conta a pagar da construtora: Areia & Cia, vence em 3 dia(s)")
        self.assertNotIn("1234", texto)  # valor da conta nunca de bandeja
        self.assertSemProibidos(texto)

    def test_campo_novo_faltando_nao_quebra_e_socio_nao_e_a_proxima_do_caixa(self):
        contas = [
            {"vencimento": "2026-10-12", "valor": 5000.0, "fornecedor": "Terreno", "descricao": "",
             "dias_ate_vencer": 2, "pagador": "socio"},
            {"vencimento": "2026-10-15", "valor": 900.0, "fornecedor": "Brita Norte", "descricao": "",
             "dias_ate_vencer": 5, "pagador": "empresa"},
        ]
        so_antigos = {"status": "ok", "tot_entradas": 1.0, "tot_saidas": 2.0}
        with patch.dict(os.environ, ENV_REAL), patch("requests.get", side_effect=_fake_get(resumo=so_antigos, contas=contas)):
            texto = app._construtora_contexto_resumo()
            res = self.client.get("/api/construtora/resumo")
        # sem os numeros novos: nada de entradas x gastos, so a proxima conta QUE SAI DO CAIXA
        self.assertEqual(texto, "próxima conta a pagar da construtora: Brita Norte, vence em 5 dia(s), "
                                "mais 1 outra(s) conta(s) em aberto")
        self.assertEqual(res.get_json()["contas"][0]["pagador"], "socio")

    def test_push_de_conta_a_vencer_sem_valor(self):
        self.client.post("/api/push/inscrever",
                         json={"endpoint": "https://exemplo.com/push/c1c", "keys": {"p256dh": "x", "auth": "y"}})
        contas = [{"vencimento": "2026-10-01", "valor": 777.0, "fornecedor": "Brita Norte",
                   "descricao": "", "dias_ate_vencer": 0}]
        with patch.dict(os.environ, ENV_REAL), patch("requests.get", side_effect=_fake_get(contas=contas)), \
                patch("notificacoes.dentro_do_horario_silencioso", return_value=False), \
                patch("push_client.configurado", return_value=True), \
                patch("push_client.enviar", return_value=True) as enviar:
            self.client.post("/api/notificacoes/verificar-agora")
        corpos = [c.args[2] for c in enviar.call_args_list if c.args[1] == "Conta a pagar (construtora)"]
        self.assertEqual(corpos, ["Brita Norte - vence hoje."])


if __name__ == "__main__":
    unittest.main()
