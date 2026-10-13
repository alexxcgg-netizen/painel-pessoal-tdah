"""Faixa A14 (roteador de mensagem simples do chat) - ia/roteador_chat.py.

Cobre: flag desligada (sempre "padrao", sem nenhuma excecao mesmo pra
entrada esquisita), flag ligada com 40+ mensagens sinteticas pt-BR
classificadas entre "local"/"luna"/"padrao", e robustez (vazio, gigante,
emoji, so numeros, tipos invalidos). Nenhuma chamada real de API - o
roteador em si nunca chama IA, so decide pra onde a mensagem vai.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
import ia.roteador_chat as roteador


def _escrever_flag(caminho: Path, ativo: bool) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({"ativo": ativo}, f)


class _BaseRoteadorTestCase(unittest.TestCase):
    """Troca ia.roteador_chat.CAMINHO_CONFIG por um arquivo temporario, pra
    nao depender (nem mexer) no ia/roteador_chat.json de verdade."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_flag = Path(self._tmp.name) / "roteador_chat.json"
        self._caminho_original = roteador.CAMINHO_CONFIG
        roteador.CAMINHO_CONFIG = self._caminho_flag

    def tearDown(self):
        roteador.CAMINHO_CONFIG = self._caminho_original
        self._tmp.cleanup()


class FlagDesligadaTestCase(_BaseRoteadorTestCase):
    """Sem o arquivo de flag (estado real de producao antes do Alex ligar)
    -> sempre "padrao", pra qualquer mensagem, mesmo uma que bateria com
    consulta conhecida ou com um gatilho de emocao/conselho."""

    def test_sem_arquivo_de_flag_e_padrao(self):
        self.assertFalse(self._caminho_flag.exists())
        self.assertEqual(roteador.decidir("oi"), "padrao")
        self.assertEqual(roteador.decidir_com_motivo("oi"), ("padrao", "flag_desligada"))

    def test_flag_explicitamente_false_e_padrao(self):
        _escrever_flag(self._caminho_flag, False)
        self.assertEqual(roteador.decidir("oi"), "padrao")

    def test_flag_desligada_mesmo_mensagem_que_seria_local(self):
        _escrever_flag(self._caminho_flag, False)
        self.assertEqual(roteador.decidir("como estao meus projetos"), "padrao")

    def test_flag_desligada_mesmo_mensagem_que_seria_luna(self):
        _escrever_flag(self._caminho_flag, False)
        self.assertEqual(roteador.decidir("bom dia"), "padrao")

    def test_flag_desligada_mesmo_mensagem_vazia_ou_gigante(self):
        _escrever_flag(self._caminho_flag, False)
        self.assertEqual(roteador.decidir(""), "padrao")
        self.assertEqual(roteador.decidir("a" * 5000), "padrao")

    def test_json_corrompido_cai_pra_padrao(self):
        with open(self._caminho_flag, "w", encoding="utf-8") as f:
            f.write("{nao e json valido")
        self.assertEqual(roteador.decidir("oi"), "padrao")

    def test_json_com_formato_inesperado_cai_pra_padrao(self):
        with open(self._caminho_flag, "w", encoding="utf-8") as f:
            json.dump(["ativo", True], f)
        self.assertEqual(roteador.decidir("oi"), "padrao")

    def test_contexto_none_nao_quebra(self):
        self.assertEqual(roteador.decidir("oi", None), "padrao")


class FlagLigadaClassificacaoTestCase(_BaseRoteadorTestCase):
    """Flag ligada: 40+ mensagens sinteticas pt-BR, cada uma checada contra
    o destino esperado. Nenhuma mensagem daqui e dado real do Alex."""

    def setUp(self):
        super().setUp()
        _escrever_flag(self._caminho_flag, True)

    def _assert_destino(self, mensagem, esperado, contexto=None):
        destino, motivo = roteador.decidir_com_motivo(mensagem, contexto)
        self.assertEqual(
            destino, esperado, f"mensagem={mensagem!r} esperado={esperado!r} obtido={destino!r} motivo={motivo!r}"
        )
        self.assertEqual(roteador.decidir(mensagem, contexto), esperado)

    # ---- "local": consulta conhecida (aprendizado.consulta_conhecida) -----
    MENSAGENS_LOCAL = [
        "tomei agua agora",
        "bebi um copo de agua",
        "como estao meus projetos",
        "como estao meus projetos?",
        "quais minhas metas",
        "qual minha meta",
        "como foram meus treinos",
        "como foram meus treinos nos ultimos 7 dias",
        "quais meus habitos",
        "cade meu projeto da viagem",
        "mostra meus projetos",
        "status da viagem",
        "resumo dos meus habitos",
    ]

    def test_mensagens_locais(self):
        for mensagem in self.MENSAGENS_LOCAL:
            with self.subTest(mensagem=mensagem):
                self._assert_destino(mensagem, "local")

    # ---- "padrao": pedido de conselho/decisao -----------------------------
    MENSAGENS_CONSELHO_DECISAO = [
        "devo aceitar essa proposta de emprego?",
        "eu devo comprar esse carro agora",
        "vale a pena fazer esse curso",
        "sera que vale a pena mudar de cidade",
        "me ajuda a decidir entre os dois",
        "me ajudar a decidir isso e dificil",
        "como falo com meu chefe sobre o aumento",
        "como eu falo com ela sobre isso",
        "o que voce acha que eu devo fazer",
        "nao sei se aceito o convite",
        "qual a melhor decisao pra esse caso",
        "me da um conselho sobre isso",
    ]

    def test_mensagens_conselho_decisao(self):
        for mensagem in self.MENSAGENS_CONSELHO_DECISAO:
            with self.subTest(mensagem=mensagem):
                self._assert_destino(mensagem, "padrao")

    # ---- "padrao": pergunta sobre sentimento/emocao ------------------------
    MENSAGENS_EMOCAO = [
        "estou muito triste hoje",
        "to ansioso com a prova",
        "sinto que nao vou dar conta de tudo",
        "me sinto sobrecarregado ultimamente",
        "estou com raiva de tudo",
        "nao aguento mais essa semana",
        "hoje bateu uma ansiedade forte",
        "como eu estou me sentindo essa semana?",
    ]

    def test_mensagens_emocao(self):
        for mensagem in self.MENSAGENS_EMOCAO:
            with self.subTest(mensagem=mensagem):
                self._assert_destino(mensagem, "padrao")

    # ---- "luna": simples, curta, sem gatilho nenhum ------------------------
    MENSAGENS_LUNA = [
        "oi",
        "ola",
        "bom dia",
        "boa noite",
        "obrigado",
        "valeu",
        "tudo bem?",
        "que dia e hoje",
        "que horas sao",
        "ok pode ser",
        "beleza",
        "top, obrigado",
        "faz sentido",
        "show de bola",
    ]

    def test_mensagens_luna(self):
        for mensagem in self.MENSAGENS_LUNA:
            with self.subTest(mensagem=mensagem):
                self._assert_destino(mensagem, "luna")

    # ---- "padrao": mensagem longa demais, mesmo sem gatilho de palavra ----
    def test_mensagem_longa_vai_pro_padrao(self):
        mensagem = "oi " * 60  # bem mais que LIMITE_CARACTERES_LUNA, sem nenhum gatilho
        self._assert_destino(mensagem, "padrao")

    def test_mensagem_no_limite_ainda_e_luna(self):
        mensagem = "a" * roteador.LIMITE_CARACTERES_LUNA
        self._assert_destino(mensagem, "luna")

    def test_mensagem_passou_do_limite_vai_pro_padrao(self):
        mensagem = "a" * (roteador.LIMITE_CARACTERES_LUNA + 1)
        self._assert_destino(mensagem, "padrao")

    # ---- "padrao": historico longo, mesmo mensagem curta e simples --------
    def test_historico_longo_vai_pro_padrao(self):
        contexto = {"historico": [{"papel": "usuario", "texto": "oi"}] * (roteador.LIMITE_HISTORICO_LUNA + 1)}
        self._assert_destino("bom dia", "padrao", contexto=contexto)

    def test_historico_curto_continua_luna(self):
        contexto = {"historico": [{"papel": "usuario", "texto": "oi"}] * 2}
        self._assert_destino("bom dia", "luna", contexto=contexto)


class RobustezTestCase(_BaseRoteadorTestCase):
    """Fuzzing leve: vazio, gigante, emoji, so numeros, tipos invalidos -
    nada disso pode levantar excecao, com flag ligada ou desligada."""

    def setUp(self):
        super().setUp()
        _escrever_flag(self._caminho_flag, True)

    def test_mensagem_vazia(self):
        self.assertEqual(roteador.decidir(""), "padrao")

    def test_mensagem_so_espacos(self):
        self.assertEqual(roteador.decidir("   \n\t  "), "padrao")

    def test_mensagem_none(self):
        self.assertEqual(roteador.decidir(None), "padrao")

    def test_mensagem_gigante(self):
        destino = roteador.decidir("x" * 200_000)
        self.assertEqual(destino, "padrao")

    def test_mensagem_so_emoji(self):
        destino, motivo = roteador.decidir_com_motivo("😀😀😀🔥🔥")
        self.assertIn(destino, ("luna", "padrao"))
        self.assertIsInstance(motivo, str)

    def test_mensagem_so_numeros(self):
        destino = roteador.decidir("123456789")
        self.assertIn(destino, ("luna", "padrao", "local"))

    def test_mensagem_tipo_invalido_numero(self):
        self.assertEqual(roteador.decidir(12345), "padrao")

    def test_mensagem_tipo_invalido_lista(self):
        self.assertEqual(roteador.decidir(["oi"]), "padrao")

    def test_mensagem_tipo_invalido_dict(self):
        self.assertEqual(roteador.decidir({"texto": "oi"}), "padrao")

    def test_contexto_tipo_invalido_nao_quebra(self):
        self.assertEqual(roteador.decidir("oi", contexto="nao e dict"), "luna")
        self.assertEqual(roteador.decidir("oi", contexto=123), "luna")
        self.assertEqual(roteador.decidir("oi", contexto=["a", "b"]), "luna")

    def test_contexto_com_conn_invalida_nao_quebra(self):
        contexto = {"conn": object()}
        destino, motivo = roteador.decidir_com_motivo("como estao meus projetos", contexto)
        # consulta_conhecida nao depende de conn - continua resolvendo local
        # mesmo com uma "conn" invalida em contexto.
        self.assertEqual(destino, "local")

    def test_contexto_historico_tipo_invalido_nao_quebra(self):
        contexto = {"historico": "nao e uma lista"}
        self.assertEqual(roteador.decidir("bom dia", contexto), "luna")

    def test_unicode_com_acento_e_maiuscula(self):
        destino = roteador.decidir("DEVO Aceitar Essa Proposta?")
        self.assertEqual(destino, "padrao")

    def test_caracteres_de_controle_nao_quebram(self):
        destino = roteador.decidir("oi\x00\x01\x02")
        self.assertIn(destino, ("luna", "padrao"))

    def test_classificador_local_ausente_nao_quebra(self):
        # Etapa 0 (X1) pode nao ter extraido classificador_local ainda nesta
        # instalacao - garante que o import tardio/defensivo nao propaga.
        import sys
        from unittest.mock import patch

        # Simula o pacote ausente (None em sys.modules faz o import levantar ImportError).
        with patch.dict(sys.modules, {"classificador_local": None}):
            destino = roteador.decidir("oi")
        self.assertIn(destino, ("luna", "padrao", "local"))

    def test_classificador_local_que_lanca_excecao_nao_quebra(self):
        import sys
        import types

        modulo_fake = types.ModuleType("classificador_local")

        def casar_com_erro(texto):
            raise RuntimeError("regra local quebrada de propósito (teste)")

        modulo_fake.casar = casar_com_erro
        sys.modules["classificador_local"] = modulo_fake
        try:
            destino, motivo = roteador.decidir_com_motivo("oi")
            self.assertIn(destino, ("luna", "padrao"))
        finally:
            del sys.modules["classificador_local"]

    def test_classificador_local_que_casa_devolve_local(self):
        import sys
        import types

        modulo_fake = types.ModuleType("classificador_local")
        modulo_fake.casar = lambda texto: texto.strip().lower() == "oi"
        sys.modules["classificador_local"] = modulo_fake
        try:
            self.assertEqual(roteador.decidir_com_motivo("oi"), ("local", "classificador_local"))
            self.assertEqual(roteador.decidir_com_motivo("bom dia")[0], "luna")
        finally:
            del sys.modules["classificador_local"]

    def test_decidir_nunca_levanta_mesmo_com_flag_quebrando_leitura(self):
        # Diretorio no lugar do arquivo -> open() falha com IsADirectoryError
        # (subclasse de OSError, ja tratado) - garante que continua caindo
        # em "padrao" sem propagar.
        os.remove(self._caminho_flag) if self._caminho_flag.exists() else None
        self._caminho_flag.mkdir()
        try:
            self.assertEqual(roteador.decidir("oi"), "padrao")
        finally:
            self._caminho_flag.rmdir()


class FlagViaDbTestCase(unittest.TestCase):
    """Caminho alternativo da flag: chave em `configuracoes`
    (db.definir_configuracao), pra quando nao ha ia/roteador_chat.json
    ligado mas o chamador passa uma conn em contexto["conn"]."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original_db = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()

        self._caminho_flag_original = roteador.CAMINHO_CONFIG
        # arquivo de flag desligado/ausente de proposito - so a chave no
        # banco deve ligar o roteador neste teste.
        roteador.CAMINHO_CONFIG = Path(self._tmp.name) / "roteador_chat_ausente.json"

    def tearDown(self):
        roteador.CAMINHO_CONFIG = self._caminho_flag_original
        self.conn.close()
        db.DB_PATH = self._caminho_original_db
        self._tmp.cleanup()

    def test_flag_desligada_no_banco_continua_padrao(self):
        contexto = {"conn": self.conn}
        self.assertEqual(roteador.decidir("bom dia", contexto), "padrao")

    def test_flag_ligada_no_banco_ativa_roteador(self):
        db.definir_configuracao(self.conn, roteador.CHAVE_CONFIG_DB, "1")
        contexto = {"conn": self.conn}
        self.assertEqual(roteador.decidir("bom dia", contexto), "luna")

    def test_flag_com_valor_invalido_no_banco_continua_padrao(self):
        db.definir_configuracao(self.conn, roteador.CHAVE_CONFIG_DB, "talvez")
        contexto = {"conn": self.conn}
        self.assertEqual(roteador.decidir("bom dia", contexto), "padrao")


class ConversaDeVerdadeTestCase(unittest.TestCase):
    """e_conversa (2026-10-13): independe da flag - so diz se a mensagem pede
    resposta pensada (vai pro modelo de conversa) ou e registro."""

    def test_conversa(self):
        for m in ("por que o QNH muda com o tempo?", "me explica o que e estol",
                  "qual a diferença entre IFR e VFR", "como eu melhoro meu foco de manhã?",
                  "devo trocar de carro agora?", "to muito ansioso com a prova",
                  "me ajuda a pensar na semana", "o que você acha de eu voltar pra academia?",
                  "dicas pra estudar meteorologia",
                  "me ajuda a escrever uma mensagem pro fornecedor que atrasou",
                  "como eu respondo meu instrutor sem parecer grosso?"):
            with self.subTest(m=m):
                self.assertTrue(roteador.e_conversa(m))

    def test_registro_e_papo_curto_nao_sao(self):
        for m in ("gastei 50 no mercado", "anota comprar pão", "marca dentista amanhã às 14h",
                  "oi", "valeu", "comi 2 ovos", "acordei", "", None, 123, "x" * 5000):
            with self.subTest(m=str(m)[:30]):
                self.assertFalse(roteador.e_conversa(m))

    def test_pergunta_longa_sem_gatilho_e_conversa(self):
        longa = "Hoje fiquei pensando na faculdade e no trabalho com meu pai, " * 4 + "faz sentido?"
        self.assertTrue(roteador.e_conversa(longa))


if __name__ == "__main__":
    unittest.main()
