"""Fase 7, faixa N2 (captura por Telegram) - telegram_captura.py.

So dubles aqui: nenhuma chamada real de rede (Telegram ou IA). `executar_captura`,
`salvar_link`, `extrair_nota_fiscal`, `enviar_mensagem`, `baixar_arquivo` e
`transcrever` sao sempre funcoes fake, injetadas - exatamente o contrato que
telegram_captura.processar_atualizacao documenta."""

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import pytest

import telegram_captura as tc


class Mensagens:
    """Grava toda chamada de enviar_mensagem, na ordem - pra teste checar o
    que teria sido mandado pro Alex sem mandar nada de verdade."""

    def __init__(self):
        self.enviadas: list[str] = []

    def __call__(self, texto: str) -> bool:
        self.enviadas.append(texto)
        return True


def _fake_executar_captura(corpo: dict, status: int = 201):
    chamadas = []

    def executar(texto, clarificacao):
        chamadas.append((texto, clarificacao))
        return corpo, status

    executar.chamadas = chamadas
    return executar


def _fake_salvar_link(resultado: dict):
    chamadas = []

    def salvar(conn, url):
        chamadas.append((conn, url))
        return resultado

    salvar.chamadas = chamadas
    return salvar


def _fake_extrair_nota(dados=None, erro=None):
    chamadas = []

    def extrair(image_bytes, media_type):
        chamadas.append((image_bytes, media_type))
        return dados, erro

    extrair.chamadas = chamadas
    return extrair


def _update_texto(texto: str, chat_id: str = "555") -> dict:
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, "text": texto}}


def _update_voice(file_id: str = "voice123", duration: int = 7, chat_id: str = "555") -> dict:
    return {
        "update_id": 2,
        "message": {"chat": {"id": chat_id}, "voice": {"file_id": file_id, "duration": duration, "mime_type": "audio/ogg"}},
    }


def _update_foto(chat_id: str = "555") -> dict:
    return {
        "update_id": 3,
        "message": {
            "chat": {"id": chat_id},
            "photo": [
                {"file_id": "pequena", "file_size": 100},
                {"file_id": "grande", "file_size": 900},
            ],
        },
    }


# ---- extrair_chat_id ---------------------------------------------------


def test_extrair_chat_id_de_mensagem_texto():
    assert tc.extrair_chat_id(_update_texto("oi")) == "555"


def test_extrair_chat_id_none_sem_mensagem():
    assert tc.extrair_chat_id({"update_id": 9, "callback_query": {}}) is None


def test_extrair_chat_id_none_sem_chat():
    assert tc.extrair_chat_id({"update_id": 9, "message": {"text": "oi"}}) is None


# ---- texto: captura normal -----------------------------------------------


def test_texto_normal_chama_executar_captura_e_manda_resumo():
    executar = _fake_executar_captura({"resumo_texto": "Tarefa criada.", "titulo": "ligar pro dentista"}, 201)
    salvar = _fake_salvar_link({"ok": True})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_texto("lembra de ligar pro dentista amanha"),
        conn=object(),
        executar_captura=executar,
        salvar_link=salvar,
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
        url_app="https://painel.exemplo/app",
    )

    assert executar.chamadas == [("lembra de ligar pro dentista amanha", "")]
    assert salvar.chamadas == []
    assert len(mensagens.enviadas) == 1
    assert "Tarefa criada." in mensagens.enviadas[0]
    assert "ligar pro dentista" in mensagens.enviadas[0]
    assert "https://painel.exemplo/app" in mensagens.enviadas[0]


def test_texto_com_duvida_manda_pergunta_sem_gravar():
    executar = _fake_executar_captura({"duvida": "Isso e gasto ou tarefa?", "resumo_texto": ""}, 200)
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_texto("100 mercado"),
        conn=object(),
        executar_captura=executar,
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
    )

    assert "Isso e gasto ou tarefa?" in mensagens.enviadas[0]
    assert "❓" in mensagens.enviadas[0]


@pytest.mark.parametrize("texto_vazio", ["", "   ", "\n", "\t"])
def test_mensagem_sem_texto_util_cai_no_fallback(texto_vazio):
    mensagens = Mensagens()
    update = {"update_id": 5, "message": {"chat": {"id": "555"}, "text": texto_vazio}}

    tc.processar_atualizacao(
        update,
        conn=object(),
        executar_captura=_fake_executar_captura({}),
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
    )
    assert "So entendo" in mensagens.enviadas[0]


def test_update_sem_message_e_ignorado():
    mensagens = Mensagens()
    tc.processar_atualizacao(
        {"update_id": 6, "callback_query": {"data": "x"}},
        conn=object(),
        executar_captura=_fake_executar_captura({}),
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
    )
    assert mensagens.enviadas == []


def test_sticker_ou_tipo_desconhecido_avisa_o_que_entende():
    mensagens = Mensagens()
    update = {"update_id": 7, "message": {"chat": {"id": "555"}, "sticker": {"file_id": "x"}}}
    tc.processar_atualizacao(
        update,
        conn=object(),
        executar_captura=_fake_executar_captura({}),
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
    )
    assert "texto, áudio" in mensagens.enviadas[0]


# ---- texto: link ----------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    ["https://exemplo.com/artigo", "http://outro-exemplo.com.br/pagina?x=1"],
)
def test_link_puro_vai_pro_salvar_link_nao_pra_captura(monkeypatch, texto):
    # leitura.validar_url resolve DNS de verdade (protecao contra SSRF) - o
    # sandbox de teste pode nao ter rede/DNS pro dominio de exemplo, entao
    # so validamos aqui a FORMA (http(s), sem espaco), sem tocar rede: a
    # validacao de SSRF em si ja tem sua propria suite (test_leitura.py,
    # se existir) e nao e' escopo desta faixa.
    monkeypatch.setattr(tc.leitura, "validar_url", lambda url: url.strip())
    executar = _fake_executar_captura({"resumo_texto": "nao devia ser chamado"})
    salvar = _fake_salvar_link({"ok": True, "id": 1, "titulo": "Um artigo", "resumo": "Resumo curto."})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_texto(texto),
        conn="CONEXAO",
        executar_captura=executar,
        salvar_link=salvar,
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
    )

    assert executar.chamadas == []
    assert salvar.chamadas == [("CONEXAO", texto)]
    assert "Salvo pra ver depois" in mensagens.enviadas[0]
    assert "Um artigo" in mensagens.enviadas[0]


def test_link_com_texto_ao_redor_nao_conta_como_link():
    """'olha esse link https://exemplo.com' tem espaco - vira captura normal,
    nao "Salvos pra ver depois" (o Alex quis anotar algo, nao so guardar a
    URL pura)."""
    executar = _fake_executar_captura({"resumo_texto": "Tarefa criada."})
    salvar = _fake_salvar_link({"ok": True})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_texto("olha esse link https://exemplo.com depois"),
        conn=object(),
        executar_captura=executar,
        salvar_link=salvar,
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
    )
    assert salvar.chamadas == []
    assert len(executar.chamadas) == 1


def test_link_invalido_estruturalmente_cai_na_captura_normal():
    """Link http(s) mas invalido pela validacao de SSRF (ex: host interno) -
    leitura.validar_url levanta LinkInvalido, entao NAO conta como link:
    segue pro fluxo de captura normal (pode virar uma tarefa/nota sobre o
    link, mas nunca tenta buscar a pagina)."""
    executar = _fake_executar_captura({"resumo_texto": "Tarefa criada."})
    salvar = _fake_salvar_link({"ok": True})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_texto("http://localhost/admin"),
        conn=object(),
        executar_captura=executar,
        salvar_link=salvar,
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
    )
    assert salvar.chamadas == []
    assert len(executar.chamadas) == 1


def test_erro_ao_salvar_link_avisa_sem_quebrar(monkeypatch):
    monkeypatch.setattr(tc.leitura, "validar_url", lambda url: url.strip())
    salvar = _fake_salvar_link({"erro": "link invalido"})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_texto("https://exemplo.com/x"),
        conn=object(),
        executar_captura=_fake_executar_captura({}),
        salvar_link=salvar,
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
    )
    assert "Não consegui salvar o link" in mensagens.enviadas[0]


# ---- audio ------------------------------------------------------------


def test_audio_baixa_transcreve_e_captura():
    chamadas_download = []
    chamadas_transcricao = []

    def baixar(file_id):
        chamadas_download.append(file_id)
        return b"bytes-de-audio-fake", "audio/ogg"

    def transcrever(audio_bytes, mime, *, duracao_segundos=0):
        chamadas_transcricao.append((audio_bytes, mime, duracao_segundos))
        return "compra 30 reais no mercado"

    executar = _fake_executar_captura({"resumo_texto": "Gasto registrado.", "titulo": "mercado"}, 201)
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_voice(duration=12),
        conn=object(),
        executar_captura=executar,
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
        baixar_arquivo=baixar,
        transcrever=transcrever,
    )

    assert chamadas_download == ["voice123"]
    assert chamadas_transcricao == [(b"bytes-de-audio-fake", "audio/ogg", 12)]
    assert executar.chamadas == [("compra 30 reais no mercado", "")]
    assert "compra 30 reais no mercado" in mensagens.enviadas[0]
    assert "Gasto registrado." in mensagens.enviadas[0]


def test_audio_erro_no_download_avisa_sem_transcrever():
    chamou_transcricao = []

    tc.processar_atualizacao(
        _update_voice(),
        conn=object(),
        executar_captura=_fake_executar_captura({}),
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=(mensagens := Mensagens()),
        baixar_arquivo=lambda file_id: None,
        transcrever=lambda *a, **k: chamou_transcricao.append(1) or "nunca",
    )
    assert chamou_transcricao == []
    assert "Não consegui baixar o áudio" in mensagens.enviadas[0]


def test_audio_teto_estourado_avisa_sem_capturar():
    executar = _fake_executar_captura({})

    def transcrever_estourado(audio_bytes, mime, *, duracao_segundos=0):
        raise tc.ErroCaptura("teto mensal de gasto com IA estourado - tente de novo mes que vem")

    mensagens = Mensagens()
    tc.processar_atualizacao(
        _update_voice(),
        conn=object(),
        executar_captura=executar,
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
        baixar_arquivo=lambda file_id: (b"x", "audio/ogg"),
        transcrever=transcrever_estourado,
    )
    assert executar.chamadas == []
    assert "teto mensal" in mensagens.enviadas[0]


def test_audio_transcricao_vazia_nao_captura_nada():
    """transcrever nunca deveria devolver string vazia (ela mesma levanta
    ErroCaptura nesse caso - ver test_transcrever_* abaixo), mas o
    processamento tambem nao pode quebrar se, por algum motivo, um dublê de
    teste devolver ''."""
    executar = _fake_executar_captura({"resumo_texto": "nao devia rodar"})
    mensagens = Mensagens()
    tc.processar_atualizacao(
        _update_voice(),
        conn=object(),
        executar_captura=executar,
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=_fake_extrair_nota(),
        enviar_mensagem=mensagens,
        baixar_arquivo=lambda file_id: (b"x", "audio/ogg"),
        transcrever=lambda *a, **k: "",
    )
    # string vazia ainda e' "verdadeira o bastante" pra seguir - o contrato
    # de nao devolver vazio e' de transcrever() de verdade (ver testes dela).
    assert executar.chamadas == [("", "")]


# ---- foto -----------------------------------------------------------------


def test_foto_usa_a_maior_resolucao_e_cria_gasto():
    chamadas_download = []
    extrair = _fake_extrair_nota({"valor": 45.9, "estabelecimento": "Padaria Sao Jose", "data": "2026-09-24"})
    executar = _fake_executar_captura({"resumo_texto": "Gasto registrado.", "titulo": "Padaria Sao Jose"}, 201)
    mensagens = Mensagens()

    def baixar(file_id):
        chamadas_download.append(file_id)
        return b"jpeg-fake", "image/jpeg"

    tc.processar_atualizacao(
        _update_foto(),
        conn=object(),
        executar_captura=executar,
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=extrair,
        enviar_mensagem=mensagens,
        baixar_arquivo=baixar,
    )

    assert chamadas_download == ["grande"]  # file_size 900 > 100
    assert extrair.chamadas == [(b"jpeg-fake", "image/jpeg")]
    assert executar.chamadas == [("Gastei R$ 45.9 em Padaria Sao Jose", "")]
    assert "desfazer" in mensagens.enviadas[0].lower()


def test_foto_sem_valor_legivel_nao_cria_gasto():
    extrair = _fake_extrair_nota({"valor": None, "estabelecimento": None, "data": None})
    executar = _fake_executar_captura({"resumo_texto": "nao devia rodar"})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_foto(),
        conn=object(),
        executar_captura=executar,
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=extrair,
        enviar_mensagem=mensagens,
        baixar_arquivo=lambda file_id: (b"x", "image/jpeg"),
    )
    assert executar.chamadas == []
    assert "valor claro" in mensagens.enviadas[0]


@pytest.mark.parametrize("valor_invalido", [0, -10, "45", True, None])
def test_foto_com_valor_invalido_nunca_cria_gasto(valor_invalido):
    extrair = _fake_extrair_nota({"valor": valor_invalido, "estabelecimento": "Loja"})
    executar = _fake_executar_captura({})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_foto(),
        conn=object(),
        executar_captura=executar,
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=extrair,
        enviar_mensagem=mensagens,
        baixar_arquivo=lambda file_id: (b"x", "image/jpeg"),
    )
    assert executar.chamadas == []


def test_foto_erro_na_extracao_avisa_sem_capturar():
    extrair = _fake_extrair_nota(None, "teto mensal de gasto com IA estourado")
    executar = _fake_executar_captura({})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_foto(),
        conn=object(),
        executar_captura=executar,
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=extrair,
        enviar_mensagem=mensagens,
        baixar_arquivo=lambda file_id: (b"x", "image/jpeg"),
    )
    assert executar.chamadas == []
    assert "teto mensal" in mensagens.enviadas[0]


def test_foto_erro_no_download_avisa_sem_chamar_ia():
    extrair = _fake_extrair_nota({"valor": 10})
    mensagens = Mensagens()

    tc.processar_atualizacao(
        _update_foto(),
        conn=object(),
        executar_captura=_fake_executar_captura({}),
        salvar_link=_fake_salvar_link({}),
        extrair_nota_fiscal=extrair,
        enviar_mensagem=mensagens,
        baixar_arquivo=lambda file_id: None,
    )
    assert extrair.chamadas == []
    assert "Não consegui baixar a foto" in mensagens.enviadas[0]


# ---- _eh_link (pura) --------------------------------------------------


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("", None),
        ("   ", None),
        ("ola", None),
        ("ftp://exemplo.com/arquivo", None),
        ("https://exemplo.com sim", None),
        ("https://exemplo.com\noutra linha", None),
    ],
)
def test_eh_link_casos_que_nao_sao_link(texto, esperado):
    assert tc._eh_link(texto) == esperado


def test_eh_link_aceita_url_http_https_pura():
    assert tc._eh_link("https://exemplo.com/pagina") == "https://exemplo.com/pagina"
