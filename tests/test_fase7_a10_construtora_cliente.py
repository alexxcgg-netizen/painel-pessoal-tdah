"""Testes de `construtora_cliente.py` (Fase 7, faixa A10).

Cobre: mock (ativado por injecao e por env var), timeout/erro de rede,
resposta malformada, cache/throttle (por endpoint e por `dias`), e a API de
alto nivel (`gastos_do_mes`, `entradas_do_mes`, `proxima_conta`). Nenhum
teste aqui faz chamada de rede real - `requests.get` e sempre mockado ou
nem chega a ser chamado (modo mock)."""

import os
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import requests

from construtora_cliente import ClienteConstrutora


def _resp_ok(payload):
    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.json.return_value = payload
    return resp


RESUMO_OK = {
    "status": "ok",
    "tot_entradas": 100000.0,
    "tot_saidas": 40000.0,
    "lucro_liquido": 60000.0,
    "margem": 60.0,
}

CONTAS_OK = {
    "status": "ok",
    "contas": [
        {
            "vencimento": "2026-10-01",
            "valor": 500.0,
            "fornecedor": "Fornecedor X",
            "descricao": "",
            "dias_ate_vencer": 5,
        },
        {
            "vencimento": "2026-10-10",
            "valor": 200.0,
            "fornecedor": "Fornecedor Y",
            "descricao": "",
            "dias_ate_vencer": 14,
        },
    ],
}


class TestConfiguracao(unittest.TestCase):
    """Sem CONSTRUTORA_API_URL/CONSTRUTORA_API_KEY e sem mock: tudo None,
    nunca quebra, nunca chama rede."""

    def test_resumo_none_sem_configuracao(self):
        cliente = ClienteConstrutora()
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(cliente.resumo())

    def test_contas_none_sem_configuracao(self):
        cliente = ClienteConstrutora()
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(cliente.contas_a_vencer())

    def test_so_url_sem_api_key_continua_none(self):
        cliente = ClienteConstrutora()
        with patch.dict(os.environ, {"CONSTRUTORA_API_URL": "https://x.com"}, clear=True):
            self.assertIsNone(cliente.resumo())

    def test_so_api_key_sem_url_continua_none(self):
        cliente = ClienteConstrutora()
        with patch.dict(os.environ, {"CONSTRUTORA_API_KEY": "chave"}, clear=True):
            self.assertIsNone(cliente.resumo())

    def test_nunca_chama_requests_get_sem_configuracao(self):
        cliente = ClienteConstrutora()
        with patch.dict(os.environ, {}, clear=True), patch("requests.get") as mock_get:
            cliente.resumo()
            cliente.contas_a_vencer()
        mock_get.assert_not_called()

    def test_gastos_entradas_proxima_conta_none_sem_configuracao(self):
        cliente = ClienteConstrutora()
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(cliente.gastos_do_mes())
            self.assertIsNone(cliente.entradas_do_mes())
            self.assertIsNone(cliente.proxima_conta())


class TestChamadaReal(unittest.TestCase):
    def _cliente(self):
        return ClienteConstrutora(base_url="https://construtora.exemplo.com", api_key="chave-teste")

    def test_resumo_usa_header_x_api_key_e_url_certa(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(RESUMO_OK)) as mock_get:
            dados = cliente.resumo()
        self.assertEqual(dados, RESUMO_OK)
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://construtora.exemplo.com/api/resumo")
        self.assertEqual(kwargs["headers"], {"X-API-Key": "chave-teste"})
        self.assertEqual(kwargs["timeout"], 5)

    def test_contas_manda_dias_na_querystring(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(CONTAS_OK)) as mock_get:
            cliente.contas_a_vencer(dias=7)
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://construtora.exemplo.com/api/contas_a_vencer")
        self.assertEqual(kwargs["params"], {"dias": 7})

    def test_timeout_vira_none(self):
        cliente = self._cliente()
        with patch("requests.get", side_effect=requests.exceptions.Timeout("demorou")):
            self.assertIsNone(cliente.resumo())

    def test_connection_error_vira_none(self):
        cliente = self._cliente()
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("fora do ar")):
            self.assertIsNone(cliente.contas_a_vencer())

    def test_request_exception_generica_vira_none(self):
        cliente = self._cliente()
        with patch("requests.get", side_effect=requests.RequestException("erro qualquer")):
            self.assertIsNone(cliente.resumo())

    def test_http_erro_4xx_vira_none(self):
        cliente = self._cliente()
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("401")
        with patch("requests.get", return_value=resp):
            self.assertIsNone(cliente.resumo())

    def test_http_erro_5xx_vira_none(self):
        cliente = self._cliente()
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        with patch("requests.get", return_value=resp):
            self.assertIsNone(cliente.contas_a_vencer())

    def test_json_invalido_vira_none(self):
        cliente = self._cliente()
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json.side_effect = ValueError("nao e JSON")
        with patch("requests.get", return_value=resp):
            self.assertIsNone(cliente.resumo())

    def test_json_que_nao_e_objeto_vira_none(self):
        cliente = self._cliente()
        for corpo in [None, [], "texto solto", 42, True]:
            with self.subTest(corpo=corpo):
                cliente.limpar_cache()
                with patch("requests.get", return_value=_resp_ok(corpo)):
                    self.assertIsNone(cliente.resumo())

    def test_status_error_do_lado_de_la_gastos_do_mes_none(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok({"status": "error", "message": "falhou"})):
            self.assertIsNone(cliente.gastos_do_mes())
            self.assertIsNone(cliente.entradas_do_mes())


class TestCache(unittest.TestCase):
    def _cliente(self, ttl=60):
        return ClienteConstrutora(base_url="https://c.exemplo.com", api_key="k", cache_ttl=ttl)

    def test_segunda_chamada_dentro_do_ttl_nao_bate_na_rede(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(RESUMO_OK)) as mock_get:
            cliente.resumo()
            cliente.resumo()
        self.assertEqual(mock_get.call_count, 1)

    def test_chamada_apos_ttl_expirar_bate_na_rede_de_novo(self):
        cliente = self._cliente(ttl=0.05)
        with patch("requests.get", return_value=_resp_ok(RESUMO_OK)) as mock_get:
            cliente.resumo()
            import time

            time.sleep(0.08)
            cliente.resumo()
        self.assertEqual(mock_get.call_count, 2)

    def test_cache_de_resumo_e_contas_sao_independentes(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(RESUMO_OK)) as mock_get:
            cliente.resumo()
            cliente.contas_a_vencer()
        self.assertEqual(mock_get.call_count, 2)

    def test_cache_de_dias_diferentes_nao_se_mistura(self):
        cliente = self._cliente()
        respostas = {30: _resp_ok({"status": "ok", "contas": [{"dias_ate_vencer": 30}]}),
                     7: _resp_ok({"status": "ok", "contas": [{"dias_ate_vencer": 7}]})}

        def fake_get(url, headers=None, params=None, timeout=None):
            return respostas[params["dias"]]

        with patch("requests.get", side_effect=fake_get) as mock_get:
            r30 = cliente.contas_a_vencer(dias=30)
            r7 = cliente.contas_a_vencer(dias=7)
            cliente.contas_a_vencer(dias=30)
            cliente.contas_a_vencer(dias=7)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(r30["contas"][0]["dias_ate_vencer"], 30)
        self.assertEqual(r7["contas"][0]["dias_ate_vencer"], 7)

    def test_limpar_cache_forca_nova_chamada(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(RESUMO_OK)) as mock_get:
            cliente.resumo()
            cliente.limpar_cache()
            cliente.resumo()
        self.assertEqual(mock_get.call_count, 2)

    def test_falha_de_rede_nao_fica_em_cache(self):
        """Erro nunca deve ser cacheado - proxima chamada tenta de novo."""
        cliente = self._cliente()
        with patch("requests.get", side_effect=requests.exceptions.Timeout("x")) as mock_get:
            cliente.resumo()
            cliente.resumo()
        self.assertEqual(mock_get.call_count, 2)

    def test_cada_instancia_tem_cache_proprio(self):
        c1 = ClienteConstrutora(base_url="https://c.exemplo.com", api_key="k")
        c2 = ClienteConstrutora(base_url="https://c.exemplo.com", api_key="k")
        with patch("requests.get", return_value=_resp_ok(RESUMO_OK)) as mock_get:
            c1.resumo()
            c2.resumo()
        self.assertEqual(mock_get.call_count, 2)


class TestModoMockPorInjecao(unittest.TestCase):
    def test_mock_true_nunca_chama_rede(self):
        cliente = ClienteConstrutora(mock=True)
        with patch("requests.get") as mock_get:
            resumo = cliente.resumo()
            contas = cliente.contas_a_vencer()
        mock_get.assert_not_called()
        self.assertEqual(resumo["status"], "ok")
        self.assertEqual(contas["status"], "ok")

    def test_mock_true_funciona_mesmo_sem_configuracao_nenhuma(self):
        cliente = ClienteConstrutora(mock=True)
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNotNone(cliente.gastos_do_mes())
            self.assertIsNotNone(cliente.entradas_do_mes())

    def test_mock_false_explicito_ignora_env_var(self):
        cliente = ClienteConstrutora(mock=False)
        with patch.dict(os.environ, {"CONSTRUTORA_API_MOCK": "1"}, clear=True), patch("requests.get") as mock_get:
            self.assertIsNone(cliente.resumo())
        mock_get.assert_not_called()

    def test_dados_mock_sao_numericos_e_consistentes(self):
        cliente = ClienteConstrutora(mock=True)
        resumo = cliente.resumo()
        self.assertIsInstance(resumo["tot_entradas"], float)
        self.assertIsInstance(resumo["tot_saidas"], float)
        self.assertAlmostEqual(
            resumo["lucro_liquido"], resumo["tot_entradas"] - resumo["tot_saidas"], places=2
        )


class TestModoMockPorEnvVar(unittest.TestCase):
    def test_construtora_api_mock_1_ativa(self):
        cliente = ClienteConstrutora()
        with patch.dict(os.environ, {"CONSTRUTORA_API_MOCK": "1"}, clear=True), patch("requests.get") as mock_get:
            self.assertIsNotNone(cliente.resumo())
        mock_get.assert_not_called()

    def test_variacoes_de_valor_truthy(self):
        for valor in ["1", "true", "True", "TRUE", "on", "yes"]:
            with self.subTest(valor=valor):
                cliente = ClienteConstrutora()
                with patch.dict(os.environ, {"CONSTRUTORA_API_MOCK": valor}, clear=True):
                    self.assertIsNotNone(cliente.resumo())

    def test_variacoes_de_valor_falsy(self):
        for valor in ["0", "false", "False", "", "nao", "  "]:
            with self.subTest(valor=valor):
                cliente = ClienteConstrutora()
                with patch.dict(os.environ, {"CONSTRUTORA_API_MOCK": valor}, clear=True), patch("requests.get") as mock_get:
                    cliente.resumo()
                mock_get.assert_not_called()  # sem URL/key configurados, nao tenta rede de qualquer forma


class TestContasMock(unittest.TestCase):
    def test_contas_vencidas_tem_dias_negativo(self):
        cliente = ClienteConstrutora(mock=True)
        dados = cliente.contas_a_vencer(dias=30)
        vencidas = [c for c in dados["contas"] if c["dias_ate_vencer"] < 0]
        self.assertTrue(vencidas)

    def test_contas_respeitam_filtro_de_dias(self):
        cliente = ClienteConstrutora(mock=True)
        dados = cliente.contas_a_vencer(dias=3)
        for c in dados["contas"]:
            self.assertLessEqual(c["dias_ate_vencer"], 3)

    def test_contas_vem_ordenadas_por_dias_ate_vencer(self):
        cliente = ClienteConstrutora(mock=True)
        dados = cliente.contas_a_vencer(dias=365)
        dias = [c["dias_ate_vencer"] for c in dados["contas"]]
        self.assertEqual(dias, sorted(dias))

    def test_vencimento_e_data_iso_coerente_com_dias_ate_vencer(self):
        cliente = ClienteConstrutora(mock=True)
        dados = cliente.contas_a_vencer(dias=365)
        hoje = date.today()
        for c in dados["contas"]:
            esperado = (hoje + timedelta(days=c["dias_ate_vencer"])).isoformat()
            self.assertEqual(c["vencimento"], esperado)

    def test_dias_invalido_cai_no_padrao_30(self):
        cliente = ClienteConstrutora(mock=True)
        for bruto in [None, "abc", [], {}, object()]:
            with self.subTest(bruto=bruto):
                cliente.limpar_cache()
                dados = cliente.contas_a_vencer(dias=bruto)
                self.assertEqual(dados["status"], "ok")

    def test_dias_zero_ou_negativo_nao_quebra(self):
        cliente = ClienteConstrutora(mock=True)
        for bruto in [0, -1, -30]:
            with self.subTest(bruto=bruto):
                cliente.limpar_cache()
                dados = cliente.contas_a_vencer(dias=bruto)
                self.assertEqual(dados["status"], "ok")


class TestApiAltoNivel(unittest.TestCase):
    def _cliente(self):
        return ClienteConstrutora(base_url="https://c.exemplo.com", api_key="k")

    def test_gastos_do_mes_retorna_tot_saidas(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(RESUMO_OK)):
            self.assertEqual(cliente.gastos_do_mes(), 40000.0)

    def test_entradas_do_mes_retorna_tot_entradas(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(RESUMO_OK)):
            self.assertEqual(cliente.entradas_do_mes(), 100000.0)

    def test_gastos_do_mes_none_quando_campo_ausente(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok({"status": "ok"})):
            self.assertIsNone(cliente.gastos_do_mes())

    def test_gastos_do_mes_none_quando_campo_nao_numerico(self):
        cliente = self._cliente()
        payload = dict(RESUMO_OK, tot_saidas="quarenta mil")
        with patch("requests.get", return_value=_resp_ok(payload)):
            self.assertIsNone(cliente.gastos_do_mes())

    def test_proxima_conta_sem_valor_por_padrao(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(CONTAS_OK)):
            resultado = cliente.proxima_conta()
        self.assertEqual(resultado, {"nome": "Fornecedor X", "dias": 5})
        self.assertNotIn("valor", resultado)

    def test_proxima_conta_com_valor_quando_pedido(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(CONTAS_OK)):
            resultado = cliente.proxima_conta(com_valor=True)
        self.assertEqual(resultado, {"nome": "Fornecedor X", "dias": 5, "valor": 500.0})

    def test_proxima_conta_usa_a_primeira_da_lista(self):
        """A ordenacao (mais proxima/mais vencida primeiro) e responsabilidade
        da API de la (v3.99.16) - o cliente so confia na ordem que recebeu."""
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok(CONTAS_OK)):
            resultado = cliente.proxima_conta()
        self.assertEqual(resultado["nome"], "Fornecedor X")

    def test_proxima_conta_none_quando_lista_vazia(self):
        cliente = self._cliente()
        with patch("requests.get", return_value=_resp_ok({"status": "ok", "contas": []})):
            self.assertIsNone(cliente.proxima_conta())

    def test_proxima_conta_none_quando_indisponivel(self):
        cliente = self._cliente()
        with patch("requests.get", side_effect=requests.exceptions.Timeout("x")):
            self.assertIsNone(cliente.proxima_conta())

    def test_proxima_conta_usa_descricao_quando_sem_fornecedor(self):
        cliente = self._cliente()
        payload = {
            "status": "ok",
            "contas": [{"vencimento": "2026-10-01", "valor": 10.0, "fornecedor": None,
                        "descricao": "Aluguel do container", "dias_ate_vencer": 1}],
        }
        with patch("requests.get", return_value=_resp_ok(payload)):
            resultado = cliente.proxima_conta()
        self.assertEqual(resultado["nome"], "Aluguel do container")

    def test_proxima_conta_sem_fornecedor_nem_descricao_usa_texto_padrao(self):
        cliente = self._cliente()
        payload = {
            "status": "ok",
            "contas": [{"vencimento": "2026-10-01", "valor": 10.0, "fornecedor": None,
                        "descricao": None, "dias_ate_vencer": 1}],
        }
        with patch("requests.get", return_value=_resp_ok(payload)):
            resultado = cliente.proxima_conta()
        self.assertEqual(resultado["nome"], "fornecedor nao informado")

    def test_proxima_conta_com_dias_vencida_fica_negativo(self):
        cliente = self._cliente()
        payload = {
            "status": "ok",
            "contas": [{"vencimento": "2026-09-01", "valor": 10.0, "fornecedor": "F",
                        "descricao": "", "dias_ate_vencer": -4}],
        }
        with patch("requests.get", return_value=_resp_ok(payload)):
            resultado = cliente.proxima_conta()
        self.assertEqual(resultado["dias"], -4)


class TestFuncoesDeModulo(unittest.TestCase):
    """As funcoes de nivel de modulo (o que o resto do painel de fato
    importa) delegam pra uma instancia padrao - cobertas por injecao direta
    na instancia nos testes acima; aqui so confirma que a fachada existe e
    funciona ponta a ponta em modo mock (sem depender de rede nem de estado
    de outro teste)."""

    def setUp(self):
        import construtora_cliente

        construtora_cliente._padrao = ClienteConstrutora(mock=True)

    def test_gastos_do_mes_modulo(self):
        import construtora_cliente

        self.assertEqual(construtora_cliente.gastos_do_mes(), _MOCK_TOT_SAIDAS_REF())

    def test_entradas_do_mes_modulo(self):
        import construtora_cliente

        self.assertIsNotNone(construtora_cliente.entradas_do_mes())

    def test_proxima_conta_modulo(self):
        import construtora_cliente

        resultado = construtora_cliente.proxima_conta()
        self.assertIn("nome", resultado)
        self.assertIn("dias", resultado)

    def test_limpar_cache_padrao_modulo(self):
        import construtora_cliente

        construtora_cliente.gastos_do_mes()
        construtora_cliente.limpar_cache_padrao()  # nao deve levantar excecao


def _MOCK_TOT_SAIDAS_REF():
    from construtora_cliente import _MOCK_TOT_SAIDAS

    return _MOCK_TOT_SAIDAS


if __name__ == "__main__":
    unittest.main()
