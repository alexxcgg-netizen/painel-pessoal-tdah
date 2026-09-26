import os
import unittest
from unittest.mock import MagicMock, patch

import uber_client


def _resposta(dados):
    r = MagicMock()
    r.raise_for_status = lambda: None
    r.json.return_value = dados
    return r


class ConfiguradoTestCase(unittest.TestCase):
    def test_sem_variaveis_de_ambiente_nao_configurado(self):
        with patch.dict(os.environ, {"UBER_CLIENT_ID": "", "UBER_CLIENT_SECRET": ""}):
            self.assertFalse(uber_client.configurado())

    def test_com_variaveis_configurado(self):
        with patch.dict(os.environ, {"UBER_CLIENT_ID": "abc", "UBER_CLIENT_SECRET": "def"}):
            self.assertTrue(uber_client.configurado())

    def test_so_client_id_nao_e_suficiente(self):
        with patch.dict(os.environ, {"UBER_CLIENT_ID": "abc", "UBER_CLIENT_SECRET": ""}):
            self.assertFalse(uber_client.configurado())


class UrlAutorizacaoTestCase(unittest.TestCase):
    def test_url_contem_client_id_e_redirect_uri(self):
        with patch.dict(os.environ, {"UBER_CLIENT_ID": "meu-client-id"}):
            url = uber_client.url_autorizacao("https://painel.exemplo.com/uber/callback")
        self.assertIn("client_id=meu-client-id", url)
        self.assertIn("response_type=code", url)
        self.assertIn("scope=request", url)
        self.assertIn("redirect_uri=https%3A%2F%2Fpainel.exemplo.com%2Fuber%2Fcallback", url)

    def test_url_comeca_com_o_endpoint_de_autorizacao(self):
        with patch.dict(os.environ, {"UBER_CLIENT_ID": "x"}):
            url = uber_client.url_autorizacao("https://painel.exemplo.com/uber/callback")
        self.assertTrue(url.startswith(uber_client.AUTHORIZE_URL))


class TrocarCodigoPorTokenTestCase(unittest.TestCase):
    def test_devolve_o_json_da_resposta(self):
        dados = {"access_token": "tok123", "refresh_token": "ref456", "expires_in": 2592000}
        with patch.dict(os.environ, {"UBER_CLIENT_ID": "x", "UBER_CLIENT_SECRET": "y"}), patch(
            "uber_client.requests.post", return_value=_resposta(dados)
        ) as mock_post:
            r = uber_client.trocar_codigo_por_token("codigo-abc", "https://x.com/callback")
        self.assertEqual(r, dados)
        mock_post.assert_called_once()
        corpo = mock_post.call_args.kwargs["data"]
        self.assertEqual(corpo["grant_type"], "authorization_code")
        self.assertEqual(corpo["code"], "codigo-abc")


class RenovarTokenTestCase(unittest.TestCase):
    def test_usa_grant_type_refresh_token(self):
        dados = {"access_token": "novo-token", "expires_in": 2592000}
        with patch.dict(os.environ, {"UBER_CLIENT_ID": "x", "UBER_CLIENT_SECRET": "y"}), patch(
            "uber_client.requests.post", return_value=_resposta(dados)
        ) as mock_post:
            r = uber_client.renovar_token("ref-antigo")
        self.assertEqual(r["access_token"], "novo-token")
        corpo = mock_post.call_args.kwargs["data"]
        self.assertEqual(corpo["grant_type"], "refresh_token")
        self.assertEqual(corpo["refresh_token"], "ref-antigo")


class ProdutoPadraoTestCase(unittest.TestCase):
    def test_devolve_o_primeiro_produto(self):
        dados = {"products": [{"product_id": "uberx-id", "display_name": "UberX"}, {"product_id": "outro"}]}
        with patch("uber_client.requests.get", return_value=_resposta(dados)):
            r = uber_client.produto_padrao(-27.0, -49.0, "token-x")
        self.assertEqual(r, "uberx-id")

    def test_sem_produto_disponivel_levanta_erro(self):
        with patch("uber_client.requests.get", return_value=_resposta({"products": []})):
            with self.assertRaises(ValueError):
                uber_client.produto_padrao(-27.0, -49.0, "token-x")


class EstimarCorridaTestCase(unittest.TestCase):
    def test_devolve_fare_id_preco_e_eta(self):
        dados = {
            "fare": {"fare_id": "fare-123", "display": "R$32,50"},
            "pickup_estimate": 6,
        }
        with patch("uber_client.requests.post", return_value=_resposta(dados)) as mock_post:
            r = uber_client.estimar_corrida(-27.0, -49.0, -27.1, -49.1, "uberx-id", "token-x")
        self.assertEqual(r, {"fare_id": "fare-123", "preco_texto": "R$32,50", "eta_minutos": 6})
        corpo = mock_post.call_args.kwargs["json"]
        self.assertEqual(corpo["product_id"], "uberx-id")
        self.assertEqual(corpo["start_latitude"], -27.0)

    def test_sem_fare_na_resposta_nao_quebra(self):
        with patch("uber_client.requests.post", return_value=_resposta({"pickup_estimate": 3})):
            r = uber_client.estimar_corrida(-27.0, -49.0, -27.1, -49.1, "uberx-id", "token-x")
        self.assertIsNone(r["fare_id"])
        self.assertEqual(r["preco_texto"], "preço não informado")


class PedirCorridaTestCase(unittest.TestCase):
    def test_devolve_request_id_e_status(self):
        dados = {"request_id": "req-789", "status": "processing"}
        with patch("uber_client.requests.post", return_value=_resposta(dados)) as mock_post:
            r = uber_client.pedir_corrida(-27.0, -49.0, -27.1, -49.1, "uberx-id", "fare-123", "token-x")
        self.assertEqual(r, {"request_id": "req-789", "status": "processing"})
        corpo = mock_post.call_args.kwargs["json"]
        self.assertEqual(corpo["fare_id"], "fare-123")


if __name__ == "__main__":
    unittest.main()
