"""Fase 7, faixa N3a - testes de coleta de dados, token e rota/pagina do
widget (`rotas/n3a_widget.py`).

Infra de blueprints (`rotas/__init__.py`, `rotas/_base.py`, Etapa 0 X1)
ainda nao estava integrada em `fase7/integracao` quando esta faixa comecou -
ver `scripts/ralph-n3a-widget/progress.txt`. Pra nao travar os testes desta
faixa nisso, os testes de rota HTTP registram o Blueprint (`n3a_widget.bp`)
num Flask app OUTRO, isolado (nao o `app.app` de producao), e simulam
`rotas._base.app_modulo()` via um stub minimo em `sys.modules` que devolve o
MESMO modulo `app` real (importado com o banco de teste, igual todo outro
teste do projeto) - o comportamento e identico ao de producao (mesmas
funcoes de app.py sendo chamadas), so a forma de registrar o Blueprint que e
provisoria. Assim que `rotas/_base.py` estiver na integracao, estes testes
continuam validos sem alteracao (o stub so preenche o que a infra real vai
prover)."""

import os
import sys
import tempfile
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
import vida

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

from rotas import n3a_widget  # noqa: E402


def _instalar_stub_rotas_base():
    """Registra um `rotas._base` minimo em sys.modules, so com
    `app_modulo()` devolvendo o `app` real (ja importado acima, com banco de
    teste) - o suficiente pro corpo das rotas de `n3a_widget.py` (que faz
    `from rotas._base import app_modulo` DENTRO da funcao) funcionar sem
    precisar da infra completa da Etapa 0 ainda estar mergeada. Devolve os
    valores anteriores de sys.modules["rotas"]/["rotas._base"] pra
    restaurar depois (nao vaza pra outros arquivos de teste)."""
    anterior_rotas = sys.modules.get("rotas")
    anterior_base = sys.modules.get("rotas._base")

    modulo_rotas = anterior_rotas or types.ModuleType("rotas")
    # C1: guarda tambem o ATRIBUTO rotas._base do pacote (antes so o
    # sys.modules era restaurado e o pacote real ficava apontando pro stub).
    anterior_attr = getattr(modulo_rotas, "_base", None)
    modulo_base = types.ModuleType("rotas._base")
    modulo_base.app_modulo = lambda: app
    modulo_rotas._base = modulo_base

    sys.modules["rotas"] = modulo_rotas
    sys.modules["rotas._base"] = modulo_base
    return anterior_rotas, anterior_base, (modulo_rotas, anterior_attr)


def _restaurar_stub_rotas_base(anteriores):
    anterior_rotas, anterior_base, (modulo_rotas, anterior_attr) = anteriores
    if anterior_attr is None:
        if hasattr(modulo_rotas, "_base"):
            delattr(modulo_rotas, "_base")
    else:
        modulo_rotas._base = anterior_attr
    if anterior_rotas is None:
        sys.modules.pop("rotas", None)
    else:
        sys.modules["rotas"] = anterior_rotas
    if anterior_base is None:
        sys.modules.pop("rotas._base", None)
    else:
        sys.modules["rotas._base"] = anterior_base


TOKEN_TESTE = "token-secreto-de-teste-123"


class _BaseWidgetTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

        self._caldav_patch = patch("caldav_client.configurado", return_value=False)
        self._caldav_patch.start()
        self.addCleanup(self._caldav_patch.stop)

        # log de diagnostico do widget (data/widget.log) vai pra pasta temporaria nos testes
        self._log_patch = patch.object(n3a_widget, "_LOG_WIDGET", str(Path(_tmp_dir.name) / "widget.log"))
        self._log_patch.start()
        self.addCleanup(self._log_patch.stop)

        self._stub_anterior = _instalar_stub_rotas_base()
        self.addCleanup(_restaurar_stub_rotas_base, self._stub_anterior)

        self._env_patch = patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": TOKEN_TESTE})
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

        import flask

        self.flask_app = flask.Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"))
        self.flask_app.register_blueprint(n3a_widget.bp)
        self.client = self.flask_app.test_client()

    def tearDown(self):
        self.conn.close()


# --------------------------------------------------------------------------
# Token: header Authorization: Bearer, ?token=, token errado, sem token,
# sem PAINEL_WIDGET_TOKEN configurado.
# --------------------------------------------------------------------------


class TokenTestCase(_BaseWidgetTestCase):
    def test_sem_token_nenhum_e_401(self):
        res = self.client.get("/api/widget")
        self.assertEqual(res.status_code, 401)

    def test_token_certo_via_header_bearer_e_200(self):
        res = self.client.get("/api/widget", headers={"Authorization": f"Bearer {TOKEN_TESTE}"})
        self.assertEqual(res.status_code, 200)

    def test_token_certo_via_query_e_200(self):
        res = self.client.get(f"/api/widget?token={TOKEN_TESTE}")
        self.assertEqual(res.status_code, 200)

    def test_token_errado_via_header_e_401(self):
        res = self.client.get("/api/widget", headers={"Authorization": "Bearer errado-123"})
        self.assertEqual(res.status_code, 401)

    def test_token_errado_via_query_e_401(self):
        res = self.client.get("/api/widget?token=errado-123")
        self.assertEqual(res.status_code, 401)

    def test_header_sem_prefixo_bearer_e_ignorado(self):
        res = self.client.get("/api/widget", headers={"Authorization": TOKEN_TESTE})
        self.assertEqual(res.status_code, 401)

    def test_sem_painel_widget_token_configurado_fica_sempre_fechado(self):
        """"401 sem/errado" - sem PAINEL_WIDGET_TOKEN configurado no
        ambiente, a rota nunca fica aberta pra quem achar a URL (mesmo
        mandando ALGUM token na requisicao, nao ha nada pra comparar)."""
        os.environ.pop("PAINEL_WIDGET_TOKEN", None)
        try:
            res = self.client.get(f"/api/widget?token={TOKEN_TESTE}")
            self.assertEqual(res.status_code, 401)
        finally:
            os.environ["PAINEL_WIDGET_TOKEN"] = TOKEN_TESTE  # restaura pro patch.dict no tearDown

    def test_sessao_logada_do_painel_vale_sem_token_e_visitante_nao(self):
        """2026-10-22 (app iOS nativo): o WKWebView logado pelo PIN le o widget pela sessao."""
        self.flask_app.secret_key = "teste-sessao"
        with self.client.session_transaction() as s:
            s["autenticado"] = True
        res = self.client.get("/api/widget")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["versao"], 1)
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertEqual(self.client.get("/api/widget").status_code, 401)

    def test_pagina_widget_tambem_exige_token(self):
        res = self.client.get("/widget")
        self.assertEqual(res.status_code, 401)

    def test_pagina_widget_com_token_via_query_funciona(self):
        res = self.client.get(f"/widget?token={TOKEN_TESTE}")
        self.assertEqual(res.status_code, 200)


# --------------------------------------------------------------------------
# Formato exato das chaves (/api/widget de ponta a ponta)
# --------------------------------------------------------------------------


class FormatoApiTestCase(_BaseWidgetTestCase):
    def _get(self, query=""):
        return self.client.get(f"/api/widget?token={TOKEN_TESTE}{query}")

    def test_json_tem_exatamente_as_10_chaves_de_topo(self):
        res = self._get()
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(
            set(data.keys()),
            {
                "versao",
                "atualizado_em",
                "estado",
                "foco",
                "proxima_conta",
                "habitos",
                "custo_ia",
                "comida",
                "agenda",
                "linhas",
            },
        )

    def test_agenda_vazia_sem_compromisso_e_lista_vazia_nao_null(self):
        self.assertEqual(self._get().get_json()["agenda"], [])

    def test_versao_1(self):
        self.assertEqual(self._get().get_json()["versao"], 1)

    def test_atualizado_em_e_iso_z(self):
        data = self._get().get_json()
        # Formato "AAAA-MM-DDTHH:MM:SSZ"
        datetime.strptime(data["atualizado_em"], "%Y-%m-%dT%H:%M:%SZ")

    def test_content_type_json(self):
        res = self._get()
        self.assertIn("application/json", res.content_type)


# --------------------------------------------------------------------------
# Coleta de dados real (banco de teste) - foco, proxima_conta, habitos.
# --------------------------------------------------------------------------


class ColetaFocoTestCase(_BaseWidgetTestCase):
    def test_sem_nenhuma_tarefa_com_horario_foco_e_null(self):
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertIsNone(data["foco"])
        self.assertNotIn("Foco:", " ".join(data["linhas"]))

    def test_tarefa_pendente_com_horario_hoje_vira_foco(self):
        hoje = date.today().isoformat()
        agora = datetime.now()
        daqui_a_pouco = (agora + timedelta(minutes=19)).strftime("%H:%M")
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Revisar contrato', ?, ?)",
            (hoje, daqui_a_pouco),
        )
        self.conn.commit()

        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertIsNotNone(data["foco"])
        self.assertEqual(data["foco"]["titulo"], "Revisar contrato")
        self.assertIsInstance(data["foco"]["em_minutos"], int)
        self.assertGreaterEqual(data["foco"]["em_minutos"], 0)
        self.assertTrue(any(l.startswith("Foco: Revisar contrato em") for l in data["linhas"]))
        self.assertEqual(data["foco"]["hora"], daqui_a_pouco)  # widget do Scriptable mostra a hora

    def test_tarefa_concluida_nunca_vira_foco(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES ('Feita', ?, '23:59', datetime('now'))",
            (hoje,),
        )
        self.conn.commit()
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertIsNone(data["foco"])


class ColetaComidaTestCase(_BaseWidgetTestCase):
    """2026-10-13: o que ele comeu hoje (fotos do prato) contra a meta do perfil."""

    def _get(self):
        return self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()

    def test_sem_refeicao_e_sem_peso_no_perfil_comida_e_null(self):
        self.assertIsNone(self._get()["comida"])

    def test_refeicoes_de_hoje_somam_e_vem_com_meta(self):
        import refeicoes

        itens = refeicoes.itens_limpos(
            [{"nome": "Frango", "gramas": 130, "kcal": 207.4, "proteina_g": 41.6, "carbo_g": 30.2, "gordura_g": 9.8}]
        )
        agora = datetime.now()
        refeicoes.registrar(self.conn, itens, "almoco", agora)
        refeicoes.registrar(self.conn, itens, "janta", agora)
        refeicoes.registrar(self.conn, itens, "almoco", agora - timedelta(days=1))  # ontem nao conta
        with patch("refeicoes.meta_do_dia", return_value={"kcal": 2550, "proteina_g": 115}):
            comida = self._get()["comida"]
        self.assertEqual(
            comida,
            {
                "kcal": 415,
                "proteina_g": 83,
                "carbo_g": 60,
                "gordura_g": 20,
                "refeicoes": 2,
                "meta_kcal": 2550,
                "meta_proteina_g": 115,
            },
        )

    def test_sem_refeicao_mas_com_meta_mostra_zero_de_meta(self):
        with patch("refeicoes.meta_do_dia", return_value={"kcal": 2550, "proteina_g": 115}):
            comida = self._get()["comida"]
        self.assertEqual(comida["kcal"], 0)
        self.assertEqual(comida["meta_kcal"], 2550)

    def test_falha_na_comida_nao_derruba_o_widget(self):
        with patch("rotas.n3a_widget._coletar_comida", side_effect=RuntimeError("tabela")):
            data = self._get()
        self.assertNotEqual(data["estado"], "erro")
        self.assertIsNone(data["comida"])


class ColetaProximaContaTestCase(_BaseWidgetTestCase):
    def test_sem_nenhuma_conta_pessoal_e_null(self):
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertIsNone(data["proxima_conta"])

    def test_conta_pessoal_mais_proxima_aparece(self):
        hoje = date.today()
        dia_vencimento = ((hoje + timedelta(days=3)).day) or 1
        db.create_conta_pessoal(self.conn, "Cartao", dia_vencimento, 450.0)
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertIsNotNone(data["proxima_conta"])
        self.assertEqual(data["proxima_conta"]["nome"], "Cartao")
        self.assertIn("em_dias", data["proxima_conta"])
        self.assertNotIn("valor", data["proxima_conta"])

    def test_sem_mostrar_valores_nao_tem_valor_em_reais(self):
        hoje = date.today()
        dia_vencimento = ((hoje + timedelta(days=3)).day) or 1
        db.create_conta_pessoal(self.conn, "Cartao", dia_vencimento, 450.0)
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertNotIn("valor", data["proxima_conta"])
        self.assertNotIn("R$", " ".join(data["linhas"]))

    def test_com_mostrar_valores_1_tem_valor_de_conta_pessoal(self):
        hoje = date.today()
        dia_vencimento = ((hoje + timedelta(days=3)).day) or 1
        db.create_conta_pessoal(self.conn, "Cartao", dia_vencimento, 450.0)
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}&mostrar_valores=1").get_json()
        self.assertEqual(data["proxima_conta"]["valor"], 450.0)

    def test_conta_construtora_nunca_traz_valor_mesmo_com_mostrar_valores(self):
        with patch.object(
            app,
            "_buscar_contas_a_vencer_construtora",
            return_value={
                "status": "ok",
                "contas": [{"fornecedor": "Fornecedor X", "dias_ate_vencer": 2, "valor": 15000.0}],
            },
        ):
            data = self.client.get(f"/api/widget?token={TOKEN_TESTE}&mostrar_valores=1").get_json()
        self.assertIsNotNone(data["proxima_conta"])
        self.assertEqual(data["proxima_conta"]["nome"], "Fornecedor X")
        self.assertNotIn("valor", data["proxima_conta"])


class ColetaHabitosTestCase(_BaseWidgetTestCase):
    def test_sem_habito_nenhum_e_null(self):
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertIsNone(data["habitos"])

    def test_habitos_devidos_hoje_contam_feitos_e_total(self):
        h1 = db.create_habito(self.conn, "Meditar", None, "diario", None, None, None)
        db.create_habito(self.conn, "Ler", None, "diario", None, None, None)
        db.alternar_habito_dia(self.conn, date.today().isoformat(), h1)

        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertEqual(data["habitos"], {"feitos": 1, "total": 2})
        self.assertIn("Habitos: 1/2", data["linhas"])

    def test_habito_nao_devido_hoje_nao_conta(self):
        outro_dia = (date.today().weekday() + 3) % 7  # garante um dia diferente de hoje
        db.create_habito(self.conn, "So terca", None, "dias_semana", str(outro_dia), None, None)
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertIsNone(data["habitos"])


class ColetaCustoIaTestCase(_BaseWidgetTestCase):
    def test_sem_teto_configurado_nao_mostra_percentual(self):
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertIsNone(data["custo_ia"])
        self.assertFalse(any("do teto" in linha for linha in data["linhas"]))

    def test_com_teto_e_sem_gasto_percentual_e_0(self):
        db.definir_teto_mensal_ia(self.conn, 10.0)  # USD
        self.conn.commit()
        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertEqual(data["custo_ia"]["percentual_teto"], 0)

    def test_gasto_registrado_reflete_no_percentual(self):
        import ia.medicao as medicao

        db.definir_teto_mensal_ia(self.conn, 10.0)  # USD
        self.conn.commit()
        # teto e gasto no MESMO cambio (BRL = USD * cambio_usd_brl()), entao
        # a fracao 5/10 = 50% independe do valor exato do cambio fixo.
        medicao.registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=5.0)

        data = self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()
        self.assertEqual(data["custo_ia"]["percentual_teto"], 50)
        self.assertIn("IA: 50% do teto", data["linhas"])


# --------------------------------------------------------------------------
# Estado "erro" - qualquer excecao na coleta vira estado=erro, nunca 500.
# --------------------------------------------------------------------------


AGORA_AGENDA = datetime(2026, 10, 13, 10, 0, 0)  # hora local "de parede", naive, como o widget usa


def _item_visao(titulo, inicio, fim, origem="calendario", concluido=False, dia_inteiro=False):
    """Item no formato que `app._visao_do_dia_itens` devolve (inicio/fim ISO, ver app.py)."""
    return {
        "id": None,
        "titulo": titulo,
        "inicio": inicio.isoformat() if isinstance(inicio, datetime) else inicio,
        "fim": fim.isoformat() if isinstance(fim, datetime) else fim,
        "dia_inteiro": dia_inteiro,
        "origem": origem,
        "concluido": concluido,
    }


class ColetaAgendaTestCase(_BaseWidgetTestCase):
    """`n3a_widget._coletar_agenda` com `app._visao_do_dia_itens` patchado (sem banco de verdade).
    Cobre o filtro (dia inteiro, horario ilegivel, janela de 30 min), tipo, ordem, limite, fuso."""

    def _agenda(self, itens, agora=AGORA_AGENDA):
        with patch.object(app, "_visao_do_dia_itens", return_value=itens):
            return n3a_widget._coletar_agenda(app, self.conn, agora)

    def test_tipo_mapeia_pela_origem(self):
        itens = [
            _item_visao("Dentista", AGORA_AGENDA + timedelta(minutes=30), AGORA_AGENDA + timedelta(minutes=60), "calendario"),
            _item_visao("Revisar", AGORA_AGENDA + timedelta(minutes=60), AGORA_AGENDA + timedelta(minutes=90), "tarefa"),
            _item_visao("Ler", AGORA_AGENDA + timedelta(minutes=90), AGORA_AGENDA + timedelta(minutes=120), "habito"),
            _item_visao("Algo", AGORA_AGENDA + timedelta(minutes=120), AGORA_AGENDA + timedelta(minutes=150), "outra_coisa"),
        ]
        tipos = [i["tipo"] for i in self._agenda(itens)]
        self.assertEqual(tipos, ["compromisso", "tarefa", "habito", "compromisso"])

    def test_formato_de_cada_item(self):
        itens = [_item_visao("  Dentista  ", AGORA_AGENDA + timedelta(minutes=40), AGORA_AGENDA + timedelta(minutes=70))]
        self.assertEqual(
            self._agenda(itens),
            [{"hora": "10:40", "titulo": "Dentista", "em_minutos": 40, "tipo": "compromisso", "concluido": False}],
        )

    def test_dia_inteiro_e_pulado(self):
        itens = [
            _item_visao(
                "Feriado",
                datetime(2026, 10, 13, 0, 0, 0),
                datetime(2026, 10, 13, 23, 59, 0),
                dia_inteiro=True,
            )
        ]
        self.assertEqual(self._agenda(itens), [])

    def test_inicio_ou_fim_ilegivel_e_pulado(self):
        itens = [
            _item_visao("Sem inicio valido", "isso nao e data", AGORA_AGENDA + timedelta(minutes=30)),
            _item_visao("Sem fim", AGORA_AGENDA + timedelta(minutes=30), None),
        ]
        self.assertEqual(self._agenda(itens), [])

    def test_tz_aware_vira_hora_local_naive(self):
        """iCloud pode mandar ISO com fuso: converte pra hora local antes de comparar com `agora`
        (naive local). Montado a partir da hora local pra funcionar em qualquer maquina."""
        inicio_local = AGORA_AGENDA + timedelta(minutes=45)
        fim_local = inicio_local + timedelta(minutes=60)
        itens = [
            _item_visao(
                "Reuniao",
                inicio_local.astimezone(timezone.utc).isoformat(),
                fim_local.astimezone(timezone.utc).isoformat(),
            )
        ]
        resultado = self._agenda(itens)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["hora"], inicio_local.strftime("%H:%M"))
        self.assertEqual(resultado[0]["em_minutos"], 45)

    def test_item_que_terminou_ha_mais_de_30_min_some(self):
        itens = [
            _item_visao("Ja foi", AGORA_AGENDA - timedelta(minutes=60), AGORA_AGENDA - timedelta(minutes=31)),
        ]
        self.assertEqual(self._agenda(itens), [])

    def test_item_que_terminou_ha_exatos_30_min_fica(self):
        itens = [
            _item_visao("Acabou agora ha pouco", AGORA_AGENDA - timedelta(minutes=50), AGORA_AGENDA - timedelta(minutes=30)),
        ]
        self.assertEqual(len(self._agenda(itens)), 1)

    def test_concluido_fica_com_flag_true(self):
        itens = [
            _item_visao(
                "Feita",
                AGORA_AGENDA + timedelta(minutes=10),
                AGORA_AGENDA + timedelta(minutes=10),
                origem="tarefa",
                concluido=True,
            ),
        ]
        resultado = self._agenda(itens)
        self.assertEqual(len(resultado), 1)
        self.assertIs(resultado[0]["concluido"], True)

    def test_limite_de_6_itens_e_ordenado_por_inicio(self):
        # 8 itens, entregues fora de ordem - tem que sair os 6 primeiros por inicio, em ordem crescente
        minutos = [70, 10, 50, 20, 90, 30, 60, 40]
        itens = [
            _item_visao(f"Item {m}", AGORA_AGENDA + timedelta(minutes=m), AGORA_AGENDA + timedelta(minutes=m + 5))
            for m in minutos
        ]
        resultado = self._agenda(itens)
        self.assertEqual(len(resultado), 6)
        self.assertEqual([i["em_minutos"] for i in resultado], [10, 20, 30, 40, 50, 60])
        self.assertEqual([i["titulo"] for i in resultado], [f"Item {m}" for m in [10, 20, 30, 40, 50, 60]])

    def test_em_minutos_nunca_negativo_pra_item_em_andamento(self):
        itens = [
            _item_visao("Em andamento", AGORA_AGENDA - timedelta(minutes=10), AGORA_AGENDA + timedelta(minutes=20)),
        ]
        resultado = self._agenda(itens)
        self.assertEqual(resultado[0]["em_minutos"], 0)
        self.assertGreaterEqual(resultado[0]["em_minutos"], 0)

    def test_titulo_sem_espaco_e_limitado_a_60(self):
        itens = [_item_visao("   " + "x" * 80, AGORA_AGENDA + timedelta(minutes=5), AGORA_AGENDA + timedelta(minutes=35))]
        titulo = self._agenda(itens)[0]["titulo"]
        self.assertEqual(titulo, "x" * 60)

    def test_colecao_vazia_devolve_lista_vazia(self):
        self.assertEqual(self._agenda([]), [])


class ColetaAgendaRotaTestCase(_BaseWidgetTestCase):
    def _get(self):
        return self.client.get(f"/api/widget?token={TOKEN_TESTE}").get_json()

    def test_tarefa_pendente_com_horario_hoje_aparece_na_agenda(self):
        hora = (datetime.now() + timedelta(minutes=19)).strftime("%H:%M")
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Revisar contrato', ?, ?)",
            (date.today().isoformat(), hora),
        )
        self.conn.commit()
        agenda = self._get()["agenda"]
        self.assertEqual(len(agenda), 1)
        self.assertEqual(agenda[0]["titulo"], "Revisar contrato")
        self.assertEqual(agenda[0]["hora"], hora)
        self.assertEqual(agenda[0]["tipo"], "tarefa")
        self.assertIs(agenda[0]["concluido"], False)

    def test_falha_na_agenda_nao_derruba_o_resto_do_widget(self):
        hora = (datetime.now() + timedelta(minutes=19)).strftime("%H:%M")
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Revisar contrato', ?, ?)",
            (date.today().isoformat(), hora),
        )
        self.conn.commit()
        with patch("rotas.n3a_widget._coletar_agenda", side_effect=RuntimeError("calendario caiu")):
            data = self._get()
        self.assertNotEqual(data["estado"], "erro")
        self.assertEqual(data["agenda"], [])
        self.assertEqual(data["foco"]["titulo"], "Revisar contrato")

    def test_estado_erro_devolve_agenda_none(self):
        with patch.object(app, "_visao_do_dia_itens", side_effect=RuntimeError("banco caiu")):
            data = self._get()
        self.assertEqual(data["estado"], "erro")
        self.assertIsNone(data["agenda"])


class EstadoErroTestCase(_BaseWidgetTestCase):
    def test_excecao_na_coleta_vira_estado_erro_nunca_500(self):
        with patch.object(app, "_visao_do_dia_itens", side_effect=RuntimeError("banco caiu")):
            res = self.client.get(f"/api/widget?token={TOKEN_TESTE}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["estado"], "erro")
        self.assertIsNone(data["foco"])
        self.assertIsNone(data["proxima_conta"])
        self.assertIsNone(data["habitos"])
        self.assertIsNone(data["custo_ia"])
        self.assertEqual(data["linhas"], [])

    def test_pagina_widget_tambem_nunca_quebra_com_excecao_na_coleta(self):
        with patch.object(app, "_buscar_contas_a_vencer_construtora", side_effect=RuntimeError("timeout")):
            res = self.client.get(f"/widget?token={TOKEN_TESTE}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"N\xc3\xa3o foi poss\xc3\xadvel carregar", res.data)


# --------------------------------------------------------------------------
# Pagina HTML (/widget) - renderiza, tem meta refresh, sem PIN.
# --------------------------------------------------------------------------


class PaginaWidgetTestCase(_BaseWidgetTestCase):
    def test_pagina_renderiza_200_html(self):
        res = self.client.get(f"/widget?token={TOKEN_TESTE}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.content_type)

    def test_pagina_tem_meta_refresh_900(self):
        res = self.client.get(f"/widget?token={TOKEN_TESTE}")
        self.assertIn(b'http-equiv="refresh" content="900"', res.data)

    def test_pagina_sem_dado_nenhum_mostra_estado_vazio(self):
        res = self.client.get(f"/widget?token={TOKEN_TESTE}")
        # sem IA configurada com gasto = percentual 0, entao normalmente
        # "normal" (custo_ia sempre presente) - so testa que a pagina nunca
        # quebra e sempre devolve 200 com algum corpo.
        self.assertGreater(len(res.data), 0)

    def test_pagina_com_foco_mostra_titulo_da_tarefa(self):
        hoje = date.today().isoformat()
        agora = datetime.now()
        daqui_a_pouco = (agora + timedelta(minutes=19)).strftime("%H:%M")
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Revisar contrato', ?, ?)",
            (hoje, daqui_a_pouco),
        )
        self.conn.commit()
        res = self.client.get(f"/widget?token={TOKEN_TESTE}")
        self.assertIn(b"Revisar contrato", res.data)

    def test_pagina_nao_pede_pin_nem_sessao(self):
        """Sem login/sessao nenhuma no client - so o token na URL basta."""
        res = self.client.get(f"/widget?token={TOKEN_TESTE}")
        self.assertEqual(res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
