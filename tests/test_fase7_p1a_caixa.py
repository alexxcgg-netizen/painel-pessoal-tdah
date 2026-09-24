"""Faixa P1a (Fase 7) - testes de assistente/caixa.py: enfileirar/resolver
(contrato fechado de assistente/contrato.py), listar/contar_pendentes,
processar_repeticoes (politica de insistencia: 2h/4h, max 3/dia, silencio),
expirar, ao_resolver e o filtro de fora-de-escopo. Relogio sempre injetado
(monkeypatch de caixa._agora, ou o parametro `agora` explicito onde o
contrato ja permite) - nunca depende da hora real da maquina."""

import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
from assistente import caixa


class _RelogioFixoTestCase(unittest.TestCase):
    """Base: banco temporario + caixa._agora travado num instante fixo
    (trocavel por historia via self._definir_agora)."""

    AGORA_PADRAO = datetime(2026, 9, 24, 10, 0, 0)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()
        caixa._garantir_tabela(self.conn)
        self._agora_original = caixa._agora
        self._definir_agora(self.AGORA_PADRAO)

    def tearDown(self):
        caixa._agora = self._agora_original
        self.conn.close()
        db.DB_PATH = self._db_path_original
        self._tmp.cleanup()

    def _definir_agora(self, momento: datetime):
        self._agora_atual = momento
        caixa._agora = lambda: self._agora_atual

    def _linha(self, item_id):
        row = self.conn.execute(
            "SELECT * FROM assistente_itens WHERE id = ?", (int(item_id),)
        ).fetchone()
        self.assertIsNotNone(row)
        return dict(row)


class EnfileirarTestCase(_RelogioFixoTestCase):
    def test_cria_item_pendente_com_campos_default(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?", origem="p2_conta:123")
        self.assertTrue(item_id)
        linha = self._linha(item_id)
        self.assertEqual(linha["tipo"], "pergunta")
        self.assertEqual(linha["titulo"], "Pagou o cartao?")
        self.assertEqual(linha["corpo"], "")
        self.assertEqual(linha["estado"], "pendente")
        self.assertEqual(linha["origem"], "p2_conta:123")
        self.assertEqual(linha["pushes_hoje"], 0)
        self.assertIsNone(linha["resolvido_em"])
        self.assertEqual(linha["criado_em"], "2026-09-24 10:00:00")

    def test_opcoes_e_repetir_guardados_como_json(self):
        item_id = caixa.enfileirar(
            "pergunta", "Confirma?", opcoes=["sim", "nao", "outra"],
            repetir={"apos_minutos": [30], "max_por_dia": 1},
        )
        linha = self._linha(item_id)
        self.assertEqual(json.loads(linha["opcoes"]), ["sim", "nao", "outra"])
        self.assertEqual(json.loads(linha["repetir"]), {"apos_minutos": [30], "max_por_dia": 1})

    def test_tipo_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            caixa.enfileirar("urgente-demais", "titulo")

    def test_titulo_vazio_levanta_value_error(self):
        with self.assertRaises(ValueError):
            caixa.enfileirar("aviso", "   ")

    def test_chave_unica_deduplica(self):
        id1 = caixa.enfileirar("aviso", "Conta de luz alta", chave_unica="p3_luz:2026-09")
        id2 = caixa.enfileirar("aviso", "Conta de luz alta (de novo)", chave_unica="p3_luz:2026-09")
        self.assertEqual(id1, id2)
        total = self.conn.execute("SELECT COUNT(*) AS n FROM assistente_itens").fetchone()["n"]
        self.assertEqual(total, 1)

    def test_chave_unica_vazia_nao_deduplica(self):
        id1 = caixa.enfileirar("sugestao", "Sugestao A")
        id2 = caixa.enfileirar("sugestao", "Sugestao B")
        self.assertNotEqual(id1, id2)

    def test_duas_chamadas_seguidas_com_mesma_chave_idempotente(self):
        # Simula o tick rodando 2x: mesmo gatilho, mesma chave_unica.
        ids = {caixa.enfileirar("pergunta", "Pagar boleto?", chave_unica="p2_boleto:9") for _ in range(5)}
        self.assertEqual(len(ids), 1)

    def test_fora_de_escopo_amoroso_nao_cria_item(self):
        antes = self.conn.execute("SELECT COUNT(*) AS n FROM assistente_itens").fetchone()["n"]
        item_id = caixa.enfileirar("sugestao", "Que tal ligar pra namorada hoje?")
        depois = self.conn.execute("SELECT COUNT(*) AS n FROM assistente_itens").fetchone()["n"]
        self.assertEqual(item_id, "")
        self.assertEqual(antes, depois)

    def test_fora_de_escopo_checa_corpo_tambem(self):
        item_id = caixa.enfileirar("aviso", "Lembrete", corpo="Marcar date com o crush amanha")
        self.assertEqual(item_id, "")

    def test_fora_de_escopo_case_insensitive(self):
        item_id = caixa.enfileirar("pergunta", "Como esta a ESPOSA hoje?")
        self.assertEqual(item_id, "")

    def test_palavra_ambigua_nao_e_bloqueada_por_engano(self):
        # "casamento" sozinho (sem termo amoroso explicito) nao deve cair no filtro -
        # e um evento com custo real (orcamento) que a Caixa precisa poder avisar.
        item_id = caixa.enfileirar("aviso", "Orcamento do casamento estourou 10%")
        self.assertNotEqual(item_id, "")


class FuzzEnfileirarTestCase(_RelogioFixoTestCase):
    """Entradas hostis/mal formadas em enfileirar - ponto exposto porque
    varias faixas (e futuramente rotas externas) chamam isso."""

    def test_titulo_gigante_nao_quebra(self):
        item_id = caixa.enfileirar("aviso", "A" * 20000)
        self.assertTrue(item_id)

    def test_corpo_gigante_nao_quebra(self):
        item_id = caixa.enfileirar("aviso", "titulo curto", corpo="B" * 50000)
        self.assertTrue(item_id)

    def test_unicode_emoji_nao_quebra(self):
        item_id = caixa.enfileirar("sugestao", "Título com açentuação 🚀🔥", corpo="corpo 中文 عربي")
        self.assertTrue(item_id)
        linha = self._linha(item_id)
        self.assertIn("🚀", linha["titulo"])

    def test_sql_like_no_titulo_nao_quebra(self):
        item_id = caixa.enfileirar("aviso", "'; DROP TABLE assistente_itens; --")
        self.assertTrue(item_id)
        # tabela ainda existe e ainda tem o item
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS n FROM assistente_itens").fetchone()["n"], 1
        )

    def test_opcoes_com_tipos_estranhos_nao_quebra(self):
        item_id = caixa.enfileirar("pergunta", "Escolha", opcoes=[1, None, {"a": "b"}, ["nested"]])
        self.assertTrue(item_id)

    def test_vence_em_string_arbitraria_nao_quebra_insercao(self):
        item_id = caixa.enfileirar("pergunta", "Prazo estranho", vence_em="nao-e-uma-data")
        self.assertTrue(item_id)

    def test_repetir_vazio_dict_nao_quebra(self):
        item_id = caixa.enfileirar("aviso", "Sem config", repetir={})
        self.assertTrue(item_id)

    def test_chave_unica_gigante_nao_quebra(self):
        item_id = caixa.enfileirar("aviso", "chave grande", chave_unica="k" * 5000)
        self.assertTrue(item_id)

    def test_muitos_tipos_invalidos_seguidos_levantam_value_error(self):
        for lixo in ["", "PERGUNTA", "pergunta ", " aviso", "sugestao;", None, 123, [], {}]:
            with self.assertRaises((ValueError, TypeError)):
                caixa.enfileirar(lixo, "titulo qualquer")


class ResolverTestCase(_RelogioFixoTestCase):
    def test_resposta_padrao_resolve_item(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        caixa.resolver(item_id, "sim", "paguei ontem")
        linha = self._linha(item_id)
        self.assertEqual(linha["estado"], "resolvido")
        self.assertEqual(linha["resposta"], "sim")
        self.assertEqual(linha["resposta_texto"], "paguei ontem")
        self.assertEqual(linha["resolvido_em"], "2026-09-24 10:00:00")

    def test_resposta_adiar_nao_resolve_marca_adiado(self):
        item_id = caixa.enfileirar("pergunta", "Confirma a viagem?")
        caixa.resolver(item_id, "adiar")
        linha = self._linha(item_id)
        self.assertEqual(linha["estado"], "adiado")
        self.assertIsNone(linha["resolvido_em"])
        esperado = self.AGORA_PADRAO + timedelta(minutes=caixa.ADIAR_PADRAO_MINUTOS)
        self.assertEqual(linha["adiado_ate"], esperado.strftime("%Y-%m-%d %H:%M:%S"))

    def test_opcao_propria_do_item_e_aceita(self):
        item_id = caixa.enfileirar("pergunta", "Qual categoria?", opcoes=["mercado", "farmacia"])
        caixa.resolver(item_id, "mercado")
        linha = self._linha(item_id)
        self.assertEqual(linha["estado"], "resolvido")
        self.assertEqual(linha["resposta"], "mercado")

    def test_opcao_propria_em_formato_dict_e_aceita(self):
        item_id = caixa.enfileirar(
            "pergunta", "O que fazer?", opcoes=[{"valor": "pagar_metade", "rotulo": "Pagar metade"}]
        )
        caixa.resolver(item_id, "pagar_metade")
        self.assertEqual(self._linha(item_id)["estado"], "resolvido")

    def test_resposta_invalida_levanta_value_error(self):
        item_id = caixa.enfileirar("pergunta", "Pagou?")
        with self.assertRaises(ValueError):
            caixa.resolver(item_id, "talvez")
        # nao mudou o estado do item
        self.assertEqual(self._linha(item_id)["estado"], "pendente")

    def test_item_inexistente_levanta_value_error(self):
        with self.assertRaises(ValueError):
            caixa.resolver("999999", "sim")

    def test_item_id_nao_numerico_levanta_value_error(self):
        with self.assertRaises(ValueError):
            caixa.resolver("abc", "sim")

    def test_resolver_item_ja_resolvido_e_no_op(self):
        item_id = caixa.enfileirar("pergunta", "Pagou?")
        caixa.resolver(item_id, "sim", "primeira resposta")
        caixa.resolver(item_id, "nao", "segunda resposta - nao deveria valer")
        linha = self._linha(item_id)
        self.assertEqual(linha["resposta"], "sim")
        self.assertEqual(linha["resposta_texto"], "primeira resposta")

    def test_resolver_item_expirado_e_no_op(self):
        item_id = caixa.enfileirar("pergunta", "Prazo curto", vence_em="2026-09-24 09:00:00")
        caixa.expirar(self.conn, self.AGORA_PADRAO)
        self.assertEqual(self._linha(item_id)["estado"], "expirado")
        caixa.resolver(item_id, "sim")
        self.assertEqual(self._linha(item_id)["estado"], "expirado")


class AoResolverTestCase(_RelogioFixoTestCase):
    def setUp(self):
        super().setUp()
        self._modulos_registrados = []

    def tearDown(self):
        for nome in self._modulos_registrados:
            sys.modules.pop(nome, None)
        super().tearDown()

    def _registrar_gatilho_falso(self, nome_completo, funcao_ao_resolver=None):
        modulo = types.ModuleType(nome_completo)
        if funcao_ao_resolver is not None:
            modulo.ao_resolver = funcao_ao_resolver
        sys.modules[nome_completo] = modulo
        self._modulos_registrados.append(nome_completo)
        return modulo

    def test_ao_resolver_e_chamado_com_os_argumentos_certos(self):
        chamadas = []

        def ao_resolver(conn, item, resposta, texto):
            chamadas.append((item["id"], resposta, texto))

        self._registrar_gatilho_falso("assistente.gatilhos.p1atestefalso", ao_resolver)
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?", origem="p1atestefalso:77")
        caixa.resolver(item_id, "sim", "paguei")
        self.assertEqual(chamadas, [(int(item_id), "sim", "paguei")])

    def test_ao_resolver_nao_e_chamado_quando_resposta_e_adiar(self):
        chamadas = []
        self._registrar_gatilho_falso(
            "assistente.gatilhos.p1atestefalso2", lambda conn, item, r, t: chamadas.append(1)
        )
        item_id = caixa.enfileirar("pergunta", "Pagou?", origem="p1atestefalso2:1")
        caixa.resolver(item_id, "adiar")
        self.assertEqual(chamadas, [])

    def test_gatilho_inexistente_nao_quebra_resolver(self):
        item_id = caixa.enfileirar("pergunta", "Pagou?", origem="faixa_que_nao_existe:1")
        caixa.resolver(item_id, "sim")  # nao deve levantar excecao
        self.assertEqual(self._linha(item_id)["estado"], "resolvido")

    def test_origem_sem_dois_pontos_nao_quebra_resolver(self):
        item_id = caixa.enfileirar("pergunta", "Pagou?", origem="sem_id_nenhum")
        caixa.resolver(item_id, "sim")
        self.assertEqual(self._linha(item_id)["estado"], "resolvido")

    def test_origem_vazia_nao_quebra_resolver(self):
        item_id = caixa.enfileirar("pergunta", "Pagou?")
        caixa.resolver(item_id, "sim")
        self.assertEqual(self._linha(item_id)["estado"], "resolvido")

    def test_ao_resolver_que_lanca_excecao_nao_derruba_resolver(self):
        def ao_resolver_com_bug(conn, item, resposta, texto):
            raise RuntimeError("bug de outra faixa")

        self._registrar_gatilho_falso("assistente.gatilhos.p1atestefalso3", ao_resolver_com_bug)
        item_id = caixa.enfileirar("pergunta", "Pagou?", origem="p1atestefalso3:1")
        caixa.resolver(item_id, "sim")  # nao deve propagar o RuntimeError
        self.assertEqual(self._linha(item_id)["estado"], "resolvido")

    def test_gatilho_sem_ao_resolver_nao_quebra(self):
        self._registrar_gatilho_falso("assistente.gatilhos.p1atestefalso4", funcao_ao_resolver=None)
        item_id = caixa.enfileirar("pergunta", "Pagou?", origem="p1atestefalso4:1")
        caixa.resolver(item_id, "sim")
        self.assertEqual(self._linha(item_id)["estado"], "resolvido")


class ListarTestCase(_RelogioFixoTestCase):
    def test_estado_none_lista_so_pendentes(self):
        id_pendente = caixa.enfileirar("aviso", "Pendente")
        id_resolvido = caixa.enfileirar("aviso", "Vai ser resolvido")
        caixa.resolver(id_resolvido, "sim")
        itens = caixa.listar(self.conn)
        ids = {i["id"] for i in itens}
        self.assertIn(int(id_pendente), ids)
        self.assertNotIn(int(id_resolvido), ids)

    def test_estado_explicito_filtra(self):
        id_resolvido = caixa.enfileirar("aviso", "Vai ser resolvido")
        caixa.resolver(id_resolvido, "sim")
        resolvidos = caixa.listar(self.conn, estado="resolvido")
        self.assertEqual([i["id"] for i in resolvidos], [int(id_resolvido)])

    def test_estado_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            caixa.listar(self.conn, estado="nao-existe")

    def test_ordenacao_por_urgencia(self):
        id_sugestao = caixa.enfileirar("sugestao", "Sugestao qualquer")
        id_aviso = caixa.enfileirar("aviso", "Aviso qualquer")
        id_pergunta = caixa.enfileirar("pergunta", "Pergunta sem prazo")
        id_pergunta_vencida = caixa.enfileirar(
            "pergunta", "Pergunta vencida", vence_em="2026-09-24 09:00:00"
        )
        id_briefing = caixa.enfileirar("briefing", "Briefing do dia")
        id_memoria = caixa.enfileirar("proposta_memoria", "Lembrar disso?")

        itens = caixa.listar(self.conn)
        ordem = [i["id"] for i in itens]
        self.assertEqual(
            ordem,
            [
                int(id_pergunta_vencida),
                int(id_pergunta),
                int(id_aviso),
                int(id_sugestao),
                int(id_briefing),
                int(id_memoria),
            ],
        )

    def test_dentro_do_mesmo_tipo_ordena_por_vence_em_com_nulos_por_ultimo(self):
        sem_prazo = caixa.enfileirar("aviso", "Sem prazo")
        prazo_distante = caixa.enfileirar("aviso", "Prazo distante", vence_em="2026-10-01 00:00:00")
        prazo_proximo = caixa.enfileirar("aviso", "Prazo proximo", vence_em="2026-09-25 00:00:00")

        itens = caixa.listar(self.conn)
        ordem = [i["id"] for i in itens]
        self.assertEqual(ordem, [int(prazo_proximo), int(prazo_distante), int(sem_prazo)])

    def test_pergunta_com_vence_em_futuro_nao_conta_como_vencida(self):
        id_pergunta_futura = caixa.enfileirar(
            "pergunta", "Pergunta com prazo no futuro", vence_em="2026-09-25 00:00:00"
        )
        id_aviso = caixa.enfileirar("aviso", "Aviso qualquer")
        itens = caixa.listar(self.conn)
        # pergunta (nao vencida) continua na frente do aviso, mas nao no "slot" de vencida
        self.assertEqual([i["id"] for i in itens], [int(id_pergunta_futura), int(id_aviso)])

    def test_limite_e_respeitado(self):
        for i in range(5):
            caixa.enfileirar("sugestao", f"Sugestao {i}")
        itens = caixa.listar(self.conn, limite=2)
        self.assertEqual(len(itens), 2)

    def test_opcoes_e_repetir_decodificados_de_volta(self):
        caixa.enfileirar("pergunta", "Com opcoes", opcoes=["a", "b"], repetir={"apos_minutos": [10]})
        item = caixa.listar(self.conn)[0]
        self.assertEqual(item["opcoes"], ["a", "b"])
        self.assertEqual(item["repetir"], {"apos_minutos": [10]})


class ContarPendentesTestCase(_RelogioFixoTestCase):
    def test_conta_so_pendentes(self):
        caixa.enfileirar("aviso", "Um")
        caixa.enfileirar("aviso", "Dois")
        resolvido = caixa.enfileirar("aviso", "Tres")
        caixa.resolver(resolvido, "sim")
        self.assertEqual(caixa.contar_pendentes(self.conn), 2)

    def test_zero_quando_vazio(self):
        self.assertEqual(caixa.contar_pendentes(self.conn), 0)


class ExpirarTestCase(_RelogioFixoTestCase):
    def test_expira_pendente_vencido(self):
        item_id = caixa.enfileirar("pergunta", "Prazo curto", vence_em="2026-09-24 09:59:59")
        expirados = caixa.expirar(self.conn, self.AGORA_PADRAO)
        self.assertEqual(expirados, 1)
        self.assertEqual(self._linha(item_id)["estado"], "expirado")

    def test_nao_expira_quem_nao_venceu(self):
        item_id = caixa.enfileirar("pergunta", "Prazo longe", vence_em="2026-09-25 00:00:00")
        caixa.expirar(self.conn, self.AGORA_PADRAO)
        self.assertEqual(self._linha(item_id)["estado"], "pendente")

    def test_nao_expira_sem_vence_em(self):
        item_id = caixa.enfileirar("aviso", "Sem prazo")
        caixa.expirar(self.conn, self.AGORA_PADRAO)
        self.assertEqual(self._linha(item_id)["estado"], "pendente")

    def test_expira_tambem_quem_esta_adiado(self):
        item_id = caixa.enfileirar("pergunta", "Adiada e vencida", vence_em="2026-09-24 09:00:00")
        caixa.resolver(item_id, "adiar")
        self.assertEqual(self._linha(item_id)["estado"], "adiado")
        caixa.expirar(self.conn, self.AGORA_PADRAO)
        self.assertEqual(self._linha(item_id)["estado"], "expirado")

    def test_nao_expira_quem_ja_foi_resolvido(self):
        item_id = caixa.enfileirar("pergunta", "Vencida mas resolvida", vence_em="2026-09-24 09:00:00")
        caixa.resolver(item_id, "sim")
        caixa.expirar(self.conn, self.AGORA_PADRAO)
        self.assertEqual(self._linha(item_id)["estado"], "resolvido")

    def test_e_idempotente_chamado_duas_vezes(self):
        item_id = caixa.enfileirar("pergunta", "Prazo curto", vence_em="2026-09-24 09:00:00")
        primeira = caixa.expirar(self.conn, self.AGORA_PADRAO)
        segunda = caixa.expirar(self.conn, self.AGORA_PADRAO)
        self.assertEqual(primeira, 1)
        self.assertEqual(segunda, 0)
        self.assertEqual(self._linha(item_id)["estado"], "expirado")


class ProcessarRepeticoesTestCase(_RelogioFixoTestCase):
    """Politica de insistencia (fase7-assistente.md): push depois de 2h e
    4h, maximo 3 por dia, respeitando aviso_permitido. Sem assistente/avisos
    (P8) ainda existindo, o fallback e "permitido fora de 22h-7h"."""

    def _push_count_mock(self):
        return patch("assistente.caixa.enviar_push", return_value=True)

    def test_primeiro_push_sai_no_tick_logo_apos_criacao(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)
        mock_push.assert_called_once()
        self.assertEqual(resultado["pushes_enviados"], 1)
        linha = self._linha(item_id)
        self.assertEqual(linha["pushes_hoje"], 1)
        self.assertEqual(linha["ultimo_push_em"], "2026-09-24 10:00:00")

    def test_nao_reenvia_antes_de_2h(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        with self._push_count_mock():
            caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO + timedelta(minutes=119))
        mock_push.assert_not_called()
        self.assertEqual(resultado["pushes_enviados"], 0)
        self.assertEqual(self._linha(item_id)["pushes_hoje"], 1)

    def test_reenvia_apos_2h(self):
        caixa.enfileirar("pergunta", "Pagou o cartao?")
        with self._push_count_mock():
            caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO + timedelta(minutes=120))
        mock_push.assert_called_once()
        self.assertEqual(resultado["pushes_enviados"], 1)

    def test_reenvia_apos_4h_mas_nao_de_novo_antes_da_4a(self):
        caixa.enfileirar("pergunta", "Pagou o cartao?")
        t0 = self.AGORA_PADRAO
        with self._push_count_mock():
            caixa.processar_repeticoes(self.conn, t0)  # push 1 (t=0)
        with self._push_count_mock():
            caixa.processar_repeticoes(self.conn, t0 + timedelta(minutes=120))  # push 2 (2h)
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, t0 + timedelta(minutes=239))
        mock_push.assert_not_called()
        self.assertEqual(resultado["pushes_enviados"], 0)
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, t0 + timedelta(minutes=240))  # push 3 (4h)
        mock_push.assert_called_once()
        self.assertEqual(resultado["pushes_enviados"], 1)

    def test_maximo_3_por_dia_mesmo_com_tempo_sobrando(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        t0 = self.AGORA_PADRAO
        for minutos in (0, 120, 240, 300, 360):
            with self._push_count_mock():
                caixa.processar_repeticoes(self.conn, t0 + timedelta(minutes=minutos))
        self.assertEqual(self._linha(item_id)["pushes_hoje"], 3)

    def test_contador_reseta_no_dia_seguinte(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        t0 = self.AGORA_PADRAO
        for minutos in (0, 120, 240):
            with self._push_count_mock():
                caixa.processar_repeticoes(self.conn, t0 + timedelta(minutes=minutos))
        self.assertEqual(self._linha(item_id)["pushes_hoje"], 3)
        amanha = t0 + timedelta(days=1)
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, amanha)
        mock_push.assert_called_once()
        self.assertEqual(resultado["pushes_enviados"], 1)
        self.assertEqual(self._linha(item_id)["pushes_hoje"], 1)

    def test_silencio_padrao_22h_7h_segura_o_push(self):
        # criado as 23h (sem assistente/avisos ainda existir -> fallback fixo 22h-7h)
        self._definir_agora(datetime(2026, 9, 24, 23, 0, 0))
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, datetime(2026, 9, 24, 23, 0, 0))
        mock_push.assert_not_called()
        self.assertEqual(resultado["pushes_enviados"], 0)
        self.assertEqual(self._linha(item_id)["pushes_hoje"], 0)
        self.assertIsNone(self._linha(item_id)["ultimo_push_em"])

    def test_push_sai_assim_que_silencio_acaba(self):
        self._definir_agora(datetime(2026, 9, 24, 23, 0, 0))
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        with self._push_count_mock() as mock_push:
            caixa.processar_repeticoes(self.conn, datetime(2026, 9, 24, 23, 0, 0))
        mock_push.assert_not_called()
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, datetime(2026, 9, 25, 7, 0, 0))
        mock_push.assert_called_once()
        self.assertEqual(resultado["pushes_enviados"], 1)

    def test_idempotente_duas_chamadas_no_mesmo_instante(self):
        caixa.enfileirar("pergunta", "Pagou o cartao?")
        with self._push_count_mock() as mock_push:
            r1 = caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)
            r2 = caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)
        self.assertEqual(mock_push.call_count, 1)
        self.assertEqual(r1["pushes_enviados"], 1)
        self.assertEqual(r2["pushes_enviados"], 0)

    def test_respeita_config_propria_de_repetir_do_item(self):
        item_id = caixa.enfileirar(
            "aviso", "Aviso com config propria", repetir={"apos_minutos": [10, 20], "max_por_dia": 2}
        )
        with self._push_count_mock():
            caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)  # push 1 (t=0)
        self.assertEqual(self._linha(item_id)["pushes_hoje"], 1)
        with self._push_count_mock() as mock_push:
            # so 10 min depois (nao 120, que e o padrao) - config propria do item
            caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO + timedelta(minutes=10))
        mock_push.assert_called_once()
        self.assertEqual(self._linha(item_id)["pushes_hoje"], 2)  # max_por_dia=2 ja bateu o teto
        with self._push_count_mock() as mock_push:
            # push 3 nao sai: max_por_dia=2 ja foi atingido, mesmo com o limiar de 20min vencido
            caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO + timedelta(minutes=20))
        mock_push.assert_not_called()

    def test_reativa_item_adiado_quando_passa_adiado_ate(self):
        item_id = caixa.enfileirar("pergunta", "Confirma a viagem?")
        caixa.resolver(item_id, "adiar")
        self.assertEqual(self._linha(item_id)["estado"], "adiado")

        ainda_nao = self.AGORA_PADRAO + timedelta(minutes=caixa.ADIAR_PADRAO_MINUTOS - 1)
        with self._push_count_mock():
            resultado = caixa.processar_repeticoes(self.conn, ainda_nao)
        self.assertEqual(resultado["reativados"], 0)
        self.assertEqual(self._linha(item_id)["estado"], "adiado")

        ja_passou = self.AGORA_PADRAO + timedelta(minutes=caixa.ADIAR_PADRAO_MINUTOS)
        with self._push_count_mock():
            resultado = caixa.processar_repeticoes(self.conn, ja_passou)
        self.assertEqual(resultado["reativados"], 1)
        linha = self._linha(item_id)
        self.assertEqual(linha["estado"], "pendente")
        self.assertIsNone(linha["adiado_ate"])

    def test_nao_manda_push_quando_nao_ha_itens_pendentes(self):
        with self._push_count_mock() as mock_push:
            resultado = caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)
        mock_push.assert_not_called()
        self.assertEqual(resultado, {"reativados": 0, "pushes_enviados": 0})

    def test_usa_assistente_avisos_quando_existe(self):
        modulo = types.ModuleType("assistente.avisos")
        modulo.aviso_permitido = lambda tipo: False
        sys.modules["assistente.avisos"] = modulo
        try:
            caixa.enfileirar("pergunta", "Pagou o cartao?")
            with self._push_count_mock() as mock_push:
                resultado = caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)
            mock_push.assert_not_called()
            self.assertEqual(resultado["pushes_enviados"], 0)
        finally:
            sys.modules.pop("assistente.avisos", None)

    def test_cai_no_fallback_se_avisos_nao_implementado(self):
        modulo = types.ModuleType("assistente.avisos")

        def _nao_implementado(tipo):
            raise NotImplementedError

        modulo.aviso_permitido = _nao_implementado
        sys.modules["assistente.avisos"] = modulo
        try:
            caixa.enfileirar("pergunta", "Pagou o cartao?")
            with self._push_count_mock() as mock_push:
                resultado = caixa.processar_repeticoes(self.conn, self.AGORA_PADRAO)  # 10h, fora do silencio
            mock_push.assert_called_once()
            self.assertEqual(resultado["pushes_enviados"], 1)
        finally:
            sys.modules.pop("assistente.avisos", None)


class EnviarPushTestCase(_RelogioFixoTestCase):
    def test_sem_push_configurado_devolve_false_sem_excecao(self):
        with patch("assistente.caixa.push_client.configurado", return_value=False):
            resultado = caixa.enviar_push(self.conn, "titulo", "corpo")
        self.assertFalse(resultado)

    def test_apaga_inscricao_morta(self):
        db.save_push_subscription(self.conn, "https://exemplo/endpoint-morto", json.dumps({"endpoint": "x"}))
        with patch("assistente.caixa.push_client.configurado", return_value=True), \
             patch("assistente.caixa.push_client.enviar", return_value=False):
            resultado = caixa.enviar_push(self.conn, "titulo", "corpo")
        self.assertFalse(resultado)
        restantes = db.list_push_subscriptions(self.conn)
        self.assertEqual(restantes, [])

    def test_mantem_inscricao_viva_e_devolve_true(self):
        db.save_push_subscription(self.conn, "https://exemplo/endpoint-vivo", json.dumps({"endpoint": "x"}))
        with patch("assistente.caixa.push_client.configurado", return_value=True), \
             patch("assistente.caixa.push_client.enviar", return_value=True):
            resultado = caixa.enviar_push(self.conn, "titulo", "corpo", url="/assistente")
        self.assertTrue(resultado)
        self.assertEqual(len(db.list_push_subscriptions(self.conn)), 1)

    def test_subscription_json_corrompido_nao_quebra(self):
        db.save_push_subscription(self.conn, "https://exemplo/endpoint-quebrado", "{isso nao e json")
        with patch("assistente.caixa.push_client.configurado", return_value=True), \
             patch("assistente.caixa.push_client.enviar", return_value=True) as mock_enviar:
            resultado = caixa.enviar_push(self.conn, "titulo", "corpo")
        mock_enviar.assert_not_called()
        self.assertFalse(resultado)


if __name__ == "__main__":
    unittest.main()
