import unittest
from unittest.mock import MagicMock, patch

import requests

import noticias

_RSS_EXEMPLO = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>"Brusque SC" - Google News</title>
<item>
<title>Prefeitura anuncia obra na Rua Nova - Brusque Agora</title>
<link>https://exemplo.com/noticia1</link>
<pubDate>Mon, 21 Sep 2026 10:00:00 GMT</pubDate>
<source url="https://brusqueagora.com.br">Brusque Agora</source>
</item>
<item>
<title>Evento de aviacao reune pilotos na regiao - OCP News</title>
<link>https://exemplo.com/noticia2</link>
<pubDate>Mon, 21 Sep 2026 08:00:00 GMT</pubDate>
<source url="https://ocpnews.com.br">OCP News</source>
</item>
<item>
<title>Sem fonte no titulo nem elemento source</title>
<link>https://exemplo.com/noticia3</link>
<pubDate>Mon, 21 Sep 2026 07:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


def _resposta_ok(conteudo: str) -> MagicMock:
    resposta = MagicMock()
    resposta.raise_for_status = lambda: None
    resposta.content = conteudo.encode("utf-8")
    return resposta


class BuscarManchetesTestCase(unittest.TestCase):
    def test_termo_vazio_devolve_lista_vazia_sem_chamar_rede(self):
        with patch("noticias.requests.get") as mock_get:
            self.assertEqual(noticias.buscar_manchetes(""), [])
            self.assertEqual(noticias.buscar_manchetes("   "), [])
        mock_get.assert_not_called()

    def test_none_devolve_lista_vazia(self):
        self.assertEqual(noticias.buscar_manchetes(None), [])

    def test_busca_com_sucesso_devolve_manchetes(self):
        with patch("noticias.requests.get", return_value=_resposta_ok(_RSS_EXEMPLO)) as mock_get:
            manchetes = noticias.buscar_manchetes("Brusque SC")
        self.assertEqual(len(manchetes), 3)
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs["params"]["q"], "Brusque SC")

    def test_tira_sufixo_de_fonte_redundante_do_titulo(self):
        with patch("noticias.requests.get", return_value=_resposta_ok(_RSS_EXEMPLO)):
            manchetes = noticias.buscar_manchetes("Brusque SC")
        self.assertEqual(manchetes[0]["titulo"], "Prefeitura anuncia obra na Rua Nova")
        self.assertEqual(manchetes[0]["fonte"], "Brusque Agora")

    def test_mantem_titulo_intacto_quando_sem_fonte(self):
        with patch("noticias.requests.get", return_value=_resposta_ok(_RSS_EXEMPLO)):
            manchetes = noticias.buscar_manchetes("Brusque SC")
        self.assertEqual(manchetes[2]["titulo"], "Sem fonte no titulo nem elemento source")
        self.assertIsNone(manchetes[2]["fonte"])

    def test_inclui_link_e_data(self):
        with patch("noticias.requests.get", return_value=_resposta_ok(_RSS_EXEMPLO)):
            manchetes = noticias.buscar_manchetes("Brusque SC")
        self.assertEqual(manchetes[0]["link"], "https://exemplo.com/noticia1")
        self.assertIn("2026", manchetes[0]["publicado_em"])

    def test_respeita_limite(self):
        with patch("noticias.requests.get", return_value=_resposta_ok(_RSS_EXEMPLO)):
            manchetes = noticias.buscar_manchetes("Brusque SC", limite=2)
        self.assertEqual(len(manchetes), 2)

    def test_erro_de_rede_devolve_lista_vazia(self):
        with patch("noticias.requests.get", side_effect=requests.RequestException("timeout")):
            self.assertEqual(noticias.buscar_manchetes("Brusque SC"), [])

    def test_http_erro_devolve_lista_vazia(self):
        resposta = MagicMock()
        resposta.raise_for_status.side_effect = requests.HTTPError("500")
        with patch("noticias.requests.get", return_value=resposta):
            self.assertEqual(noticias.buscar_manchetes("Brusque SC"), [])

    def test_xml_malformado_devolve_lista_vazia(self):
        with patch("noticias.requests.get", return_value=_resposta_ok("nao e xml valido <<<")):
            self.assertEqual(noticias.buscar_manchetes("Brusque SC"), [])

    def test_feed_sem_itens_devolve_lista_vazia(self):
        vazio = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
        with patch("noticias.requests.get", return_value=_resposta_ok(vazio)):
            self.assertEqual(noticias.buscar_manchetes("termo qualquer"), [])

    def test_item_sem_titulo_e_ignorado(self):
        rss = """<?xml version="1.0"?><rss version="2.0"><channel>
        <item><link>https://exemplo.com/x</link></item>
        </channel></rss>"""
        with patch("noticias.requests.get", return_value=_resposta_ok(rss)):
            self.assertEqual(noticias.buscar_manchetes("termo"), [])


if __name__ == "__main__":
    unittest.main()
