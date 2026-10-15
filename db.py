import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import criptografia
import vida

DB_PATH = Path(__file__).parent / "data" / "painel.db"
DB_PATH_PRODUCAO = DB_PATH.resolve()


def garantir_banco_nao_producao():
    """Guarda de seguranca: levanta RuntimeError se DB_PATH atual apontar pro banco de
    producao real (data/painel.db). Testes, migracoes ad-hoc e scripts de fuzzing/reproducao
    devem chamar isso logo depois de sobrescrever DB_PATH (e antes de qualquer escrita) -
    incidente real na Fase 4: um script de reproducao esqueceu de trocar DB_PATH e chegou a
    tocar o banco real. Nao chamar isso do app.py em producao normal (ali DB_PATH == producao
    de proposito). Bypass explicito via PAINEL_PERMITIR_PRODUCAO=sim, pro raro caso em que
    rodar contra producao de verdade e intencional."""
    try:
        atual = DB_PATH.resolve()
    except OSError:
        return
    if atual == DB_PATH_PRODUCAO and os.environ.get("PAINEL_PERMITIR_PRODUCAO") != "sim":
        raise RuntimeError(
            f"BLOQUEADO: DB_PATH aponta pro banco de producao real ({DB_PATH_PRODUCAO}). "
            "Teste/migracao/script de fuzzing nunca deve rodar contra o banco real - troque "
            "DB_PATH pra um arquivo temporario antes de importar app/chamar init_db(). Se "
            "voce tem certeza que quer mesmo produção, defina PAINEL_PERMITIR_PRODUCAO=sim."
        )


# ---- Criptografia de campo (Open Finance + saude) -------------------------
# Ver docs/SEGURANCA.md pro escopo completo e o porque. `_cnum`/`_dnum` sao so
# `criptografia.criptografar/descriptografar` com um passo a mais de
# serializar/desserializar numero <-> texto (str() e o inverso de int()/
# float() sem perda pro que este app grava - nao ha NaN/infinito em
# saldo/passos/sono, entao nao precisa de um serializador mais esperto).
def _cnum(valor) -> str | None:
    if valor is None:
        return None
    return criptografia.criptografar(str(valor))


def _dnum(valor_cifrado, conversor):
    texto = criptografia.descriptografar(valor_cifrado)
    if texto is None:
        return None
    try:
        return conversor(texto)
    except (TypeError, ValueError):
        # dado corrompido/formato inesperado - nunca derruba a leitura
        return None


def _criado_local(linhas) -> list[dict]:
    """`criado_em` com DEFAULT datetime('now') e UTC; quem compara com
    date.today() precisa da hora local (senao item criado as 22h de Brasilia
    ja "nasce amanha")."""
    resultado = []
    for r in linhas:
        d = dict(r)
        try:
            if len(d["criado_em"]) <= 10:  # so data (legado/teste): nada a converter
                raise ValueError
            utc = datetime.fromisoformat(d["criado_em"]).replace(tzinfo=timezone.utc)
            d["criado_em"] = utc.astimezone().replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
        except (KeyError, TypeError, ValueError):
            pass
        resultado.append(d)
    return resultado


def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source_text TEXT,
            due_at TEXT,
            due_date TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            completed_at TEXT,
            position INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            source_text TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banco TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'conta',
            saldo REAL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(banco, tipo)
        );

        CREATE TABLE IF NOT EXISTS bank_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL REFERENCES bank_accounts(id) ON DELETE CASCADE,
            data TEXT NOT NULL,
            descricao TEXT,
            valor REAL NOT NULL,
            external_id TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(bank_account_id, external_id)
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            valor_alvo REAL NOT NULL,
            prazo TEXT,
            valor_guardado REAL NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS goal_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
            valor REAL NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL UNIQUE,
            subscription_json TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Fase 6 (US-E10): `categoria` classifica as memorias fixas e editaveis
        -- de "O que eu lembro sobre voce" (sua_rotina/seus_planos/fora_do_painel -
        -- ver MEMORIAS_INICIAIS_FASE6/_seed_memorias_categorizadas_fase6). NULL
        -- continua sendo o caso de sempre: fato solto capturado automaticamente
        -- (registrar_memoria/parsed["memoria"]), sem grupo fixo.
        CREATE TABLE IF NOT EXISTS memorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            texto TEXT NOT NULL,
            source_text TEXT,
            categoria TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS saude_dados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            passos INTEGER,
            distancia_km REAL,
            sono_horas REAL,
            andares_subidos INTEGER,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notificacoes_enviadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            referencia_id INTEGER NOT NULL DEFAULT 0,
            data TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(tipo, referencia_id, data)
        );

        -- Aviso importante que insiste (2026-10-13, pedido do Alex: "avisa uma vez so e se eu
        -- nao ver passa em branco"): o que saiu, quantas vezes e se ele abriu. aberto_em vem do
        -- toque na notificacao (service worker -> POST /api/push/aberto); encerrado_em quando
        -- deixou de valer (tarefa concluida) ou acabaram as repeticoes.
        CREATE TABLE IF NOT EXISTS avisos_insistentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            referencia_id INTEGER NOT NULL DEFAULT 0,
            data TEXT NOT NULL,
            titulo TEXT NOT NULL,
            corpo TEXT NOT NULL,
            tag TEXT NOT NULL,
            enviado_em TEXT NOT NULL,
            tentativas INTEGER NOT NULL DEFAULT 1,
            aberto_em TEXT,
            encerrado_em TEXT,
            UNIQUE(tipo, referencia_id, data)
        );

        CREATE TABLE IF NOT EXISTS chat_mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            papel TEXT NOT NULL CHECK (papel IN ('user', 'assistant')),
            texto TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS lembretes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            data TEXT NOT NULL,
            recorrente INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS medicamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            dosagem TEXT,
            horario TEXT NOT NULL,
            recorrencia TEXT NOT NULL DEFAULT 'diaria',
            tarefa_modelo_id INTEGER NOT NULL REFERENCES tasks(id),
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS atividade_dias (
            dia TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS voos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            origem TEXT,
            destino TEXT NOT NULL,
            horas REAL,
            observacao TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );

        CREATE TABLE IF NOT EXISTS login_tentativas (
            ip TEXT PRIMARY KEY,
            tentativas INTEGER NOT NULL DEFAULT 0,
            bloqueado_ate REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS uber_pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem TEXT,
            destino TEXT NOT NULL,
            origem_lat REAL,
            origem_lng REAL,
            destino_lat REAL,
            destino_lng REAL,
            product_id TEXT,
            disparar_em TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'aguardando',
            fare_id TEXT,
            preco_texto TEXT,
            request_id TEXT,
            erro TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cotacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cotacoes_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cotacao_id INTEGER NOT NULL REFERENCES cotacoes(id) ON DELETE CASCADE,
            fornecedor TEXT,
            valor REAL,
            prazo_texto TEXT,
            observacao TEXT,
            origem TEXT NOT NULL DEFAULT 'texto',
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS esperas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quem TEXT NOT NULL,
            sobre TEXT NOT NULL,
            source_text TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            resolvido_em TEXT
        );

        CREATE TABLE IF NOT EXISTS interacoes_aprendizado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            referencia_id INTEGER NOT NULL DEFAULT 0,
            disparado_em TEXT NOT NULL DEFAULT (datetime('now')),
            resolvido_em TEXT,
            latencia_horas REAL
        );

        CREATE TABLE IF NOT EXISTS incomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            source_text TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS orcamentos (
            categoria TEXT PRIMARY KEY,
            valor_limite REAL NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS apelidos_gasto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao_normalizada TEXT NOT NULL,
            valor REAL NOT NULL,
            apelido TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(descricao_normalizada, valor)
        );

        CREATE TABLE IF NOT EXISTS correcoes_classificacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            texto_original TEXT NOT NULL,
            tipo_errado TEXT,
            categoria_errada TEXT,
            tipo_certo TEXT NOT NULL,
            categoria_certa TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            corpo TEXT NOT NULL,
            tags TEXT,
            source_text TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS hidratacao_registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS medidas_corporais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            valor REAL NOT NULL,
            unidade TEXT NOT NULL,
            data TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS checkins (
            data TEXT PRIMARY KEY,
            energia INTEGER,
            sono INTEGER,
            humor INTEGER,
            atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Suporta a fila offline do front (Fase 4, item 2): a pagina guarda em
        -- IndexedDB as capturas que falharam por falta de rede e reenvia quando
        -- volta a conexao. Sem isso, um reenvio automatico (ex: o servidor ja
        -- processou mas a conexao caiu antes do cliente receber a resposta)
        -- duplicaria a tarefa/gasto. O client_id nasce no navegador
        -- (crypto.randomUUID) e so /api/capture usa - o Atalho do iPhone
        -- (/api/atalho/capturar) nunca manda client_id, entao nunca cai aqui.
        CREATE TABLE IF NOT EXISTS capture_idempotency (
            client_id TEXT PRIMARY KEY,
            response_json TEXT NOT NULL,
            status INTEGER NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rotina_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            momento TEXT NOT NULL,
            texto TEXT NOT NULL,
            posicao INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS rotina_marcacoes (
            data TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            feito_em TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (data, item_id)
        );

        CREATE TABLE IF NOT EXISTS essencial_dia (
            data TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            posicao INTEGER NOT NULL,
            motivo TEXT,
            PRIMARY KEY (data, task_id)
        );

        CREATE TABLE IF NOT EXISTS contas_pessoais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            valor REAL,
            dia_vencimento INTEGER NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contas_pessoais_pagas (
            conta_id INTEGER NOT NULL,
            vencimento TEXT NOT NULL,
            pago_em TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (conta_id, vencimento)
        );

        CREATE TABLE IF NOT EXISTS assinaturas_revisao (
            descricao_normalizada TEXT NOT NULL,
            ano_mes TEXT NOT NULL,
            descricao TEXT NOT NULL,
            valor REAL,
            resposta TEXT NOT NULL,
            respondido_em TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (descricao_normalizada, ano_mes)
        );

        CREATE TABLE IF NOT EXISTS pessoas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            frequencia_dias INTEGER NOT NULL DEFAULT 14,
            ultimo_contato TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS conversas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pessoa_id INTEGER,
            pessoa_nome TEXT NOT NULL,
            sobre TEXT,
            data TEXT NOT NULL,
            source_text TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS decisoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT NOT NULL,
            analise_json TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS treino_fichas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo TEXT NOT NULL,
            exercicios TEXT NOT NULL,
            atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            grupo TEXT,
            duracao_min INTEGER,
            nota TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS viagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            destino TEXT NOT NULL,
            data_ida TEXT NOT NULL,
            data_volta TEXT,
            motivo TEXT,
            internacional INTEGER NOT NULL DEFAULT 0,
            numero_voo TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS viagem_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            viagem_id INTEGER NOT NULL,
            texto TEXT NOT NULL,
            feito INTEGER NOT NULL DEFAULT 0
        );

        -- 2026-10-11: rotina recorrente "excluida" num dia = pulada so naquele dia (senao
        -- materializar_tarefas_recorrentes recriava a instancia no proximo tick).
        CREATE TABLE IF NOT EXISTS tarefas_puladas (
            origem_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (origem_id, data)
        );

        CREATE TABLE IF NOT EXISTS lugares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cidade TEXT,
            tipo TEXT,
            nota TEXT,
            lat REAL,
            lng REAL,
            geocode_status TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Fase 6 F3 (US-F12): cache do status de voo por API externa (ver
        -- voo_status.py) - chave (numero_voo, data) porque o mesmo numero de
        -- voo se repete todo dia (ex: "LA3251" voa toda tarde); nunca chama a
        -- API de novo dentro da janela de cache, pra nao estourar o limite
        -- gratuito mensal.
        CREATE TABLE IF NOT EXISTS voo_status_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_voo TEXT NOT NULL,
            data TEXT NOT NULL,
            resposta_json TEXT NOT NULL,
            buscado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(numero_voo, data)
        );

        -- Fase 6 (US-E1a): secao unica de manutencao (antes eram duas tabelas
        -- separadas - `manutencoes`, generica por tempo, e `manutencoes_veiculo`,
        -- especifica de carro por km/data - ver _migrar_manutencoes_unificadas
        -- pra migracao dos bancos que ja tinham as duas). `tipo` classifica
        -- casa/carro/equipamento/outro; km/proxima_em_km/proxima_em_data so
        -- fazem sentido pra tipo='carro' (nulos pros demais). Carro continua
        -- com semantica de HISTORICO (registro novo a cada manutencao feita,
        -- intervalo_meses fica 0/sentinela, nunca lido); os demais tipos
        -- continuam com semantica de EDICAO NO LUGAR (ultima_vez atualizada
        -- pelo botao "feita hoje").
        CREATE TABLE IF NOT EXISTS manutencoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL DEFAULT 'outro',
            item TEXT NOT NULL,
            intervalo_meses INTEGER NOT NULL,
            ultima_vez TEXT,
            km REAL,
            proxima_em_km REAL,
            proxima_em_data TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            item_normalizado TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            comprado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS responder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quem TEXT NOT NULL,
            sobre TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            respondido_em TEXT
        );

        CREATE TABLE IF NOT EXISTS aprender (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema TEXT NOT NULL,
            nota TEXT,
            ultima_vez TEXT,
            concluido_em TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS salvos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            titulo TEXT,
            resumo TEXT,
            lido_em TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS app_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app TEXT NOT NULL,
            evento TEXT NOT NULL,
            em TEXT NOT NULL
        );

        -- Fase 5 (US-A3): camada robo antes da IA no classificador de intent -
        -- comando repetido/parecido o suficiente resolve localmente sem gastar
        -- chamada de API. texto_normalizado e a chave (ver
        -- aprendizado.normalizar_texto_intent); so aplica com
        -- vezes_confirmado >= aprendizado.LIMIAR_CONFIRMACOES_PADRAO_INTENT
        -- (ver aprendizado.padrao_intent_confiavel).
        CREATE TABLE IF NOT EXISTS padroes_intent_aprendidos (
            texto_normalizado TEXT PRIMARY KEY,
            acao TEXT NOT NULL,
            parametros TEXT NOT NULL DEFAULT '{}',
            vezes_confirmado INTEGER NOT NULL DEFAULT 1,
            ultima_vez TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Fase 5 (US-C2): diario de decisao - o que foi decidido, o contexto/
        -- motivo na hora, e um resultado preenchido depois (revisao). NAO e
        -- a mesma coisa que a tabela `decisoes` (Fase 1 - "vale a pena?" com
        -- pros/contras da IA, efemera): esta aqui e um diario persistente pra
        -- revisar depois, dai o nome diferente pra nao colidir.
        CREATE TABLE IF NOT EXISTS diario_decisoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decisao TEXT NOT NULL,
            contexto TEXT,
            data TEXT NOT NULL DEFAULT (date('now')),
            revisao_em TEXT,
            resultado TEXT,
            source_text TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Fase 5 (US-C6): brain dump - despejo rapido de pensamento solto,
        -- sem classificar em tarefa/nota/gasto na hora. `processado` vira 1
        -- quando o item e convertido (ou descartado) depois, com calma.
        CREATE TABLE IF NOT EXISTS brain_dump (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            texto TEXT NOT NULL,
            processado INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ideias_presente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pessoa TEXT NOT NULL,
            ideia TEXT NOT NULL,
            ocasiao TEXT,
            comprado INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Fase 6 (US-E5, docs/CARDS.md "Desfazer"): o que cada botao
        -- Desfazer de um card pode reverter - ids EXATOS gravados no momento
        -- da acao (nunca "o ultimo"). itens_json criptografado em repouso
        -- (pode ter ajuste de saldo).
        CREATE TABLE IF NOT EXISTS acoes_desfazer (
            token TEXT PRIMARY KEY,
            itens_json TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            desfeito_em TEXT
        );

        CREATE TABLE IF NOT EXISTS garantias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto TEXT NOT NULL,
            data_compra TEXT NOT NULL,
            prazo_garantia_meses INTEGER NOT NULL,
            nota_fiscal_anexo TEXT,
            notificado INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Fase 6 (US-E12): modulo Habitos NOVO, separado de rotina_itens/
        -- rotina_marcacoes (aquela e a Rotina guiada manha/noite - decisao
        -- do Alex de nao misturar os dois conceitos). frequencia_tipo:
        -- 'diario' (todo dia conta), 'dias_semana' (dias fixos, ver
        -- dias_semana em CSV "0,2,4" com 0=segunda) ou 'n_vezes_semana'
        -- ("qualquer dia conta" ate bater vezes_por_semana).
        CREATE TABLE IF NOT EXISTS habitos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            meta TEXT,
            frequencia_tipo TEXT NOT NULL DEFAULT 'diario',
            dias_semana TEXT,
            vezes_por_semana INTEGER,
            horario TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS habito_marcacoes (
            data TEXT NOT NULL,
            habito_id INTEGER NOT NULL,
            marcado_em TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (data, habito_id)
        );

        -- Fase 6 (US-E13): modulo Projetos generico (nao e Viagens - aquele
        -- modulo continua separado; ver converter_viagem_para_projeto em
        -- vida.py pro card reaproveitar o mesmo formato visual sem migrar
        -- dado nenhum). status e augmentado por vida.status_projeto na
        -- leitura (nunca gravado errado aqui: so 'pausado' e escolha manual,
        -- 'no_rumo'/'atrasado' sao calculados a partir do prazo).
        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            prazo_final TEXT,
            status TEXT NOT NULL DEFAULT 'no_rumo',
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS projeto_etapas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
            texto TEXT NOT NULL,
            data_prevista TEXT,
            posicao INTEGER NOT NULL DEFAULT 0,
            feita INTEGER NOT NULL DEFAULT 0,
            feita_em TEXT
        );

        -- Fase 6 (US-E14): fonte da verdade de todo evento que o PAINEL criou
        -- no calendario "Painel" do iCloud - caldav_client.apagar_evento so
        -- apaga um UID que exista aqui (decisao do Alex: nunca tocar evento
        -- que o painel nao criou, mesmo que esteja no mesmo calendario).
        CREATE TABLE IF NOT EXISTS eventos_criados (
            uid TEXT PRIMARY KEY,
            titulo TEXT NOT NULL,
            inicio TEXT NOT NULL,
            fim TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Voz premium (voz_premium.py): cache do audio das frases curtas (chave =
        -- sha256 de modelo+voz+texto) e contagem de caracteres gastos por mes
        -- (o plano gratis do ElevenLabs tem ~10 mil creditos/mes).
        CREATE TABLE IF NOT EXISTS voz_cache (
            chave TEXT PRIMARY KEY,
            audio BLOB NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS voz_uso (
            mes TEXT PRIMARY KEY,
            caracteres INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()
    _garantir_coluna(conn, "tasks", "due_date", "TEXT")
    _garantir_coluna(conn, "tasks", "hora", "TEXT")
    _garantir_coluna(conn, "tasks", "depende_do_tempo", "INTEGER NOT NULL DEFAULT 0")
    # Rotina recorrente (pedido explicito: "toda segunda tem academia as 7h",
    # remedio diario etc - o app precisa substituir o Calendario da Apple de
    # verdade, que ja tem isso). Uma linha com recorrencia preenchida e um
    # MODELO (due_date sempre NULL, nunca aparece sozinha em lista nenhuma) -
    # materializar_tarefas_recorrentes (app.py) gera a instancia do dia,
    # marcada com recorrente_origem_id apontando de volta pro modelo.
    _garantir_coluna(conn, "tasks", "recorrencia", "TEXT")
    _garantir_coluna(conn, "tasks", "recorrente_origem_id", "INTEGER")
    _garantir_coluna(conn, "voos", "hora", "TEXT")
    # 2026-10-14: escalas da navegacao em ordem ("SBNF,SBFL") - origem e destino ficam nas
    # colunas proprias (ver rota_voo.py)
    _garantir_coluna(conn, "voos", "escalas", "TEXT")
    _garantir_coluna(conn, "expenses", "tipo", "TEXT NOT NULL DEFAULT 'real'")
    _garantir_coluna(conn, "bank_transactions", "categoria", "TEXT")
    _garantir_coluna(conn, "bank_accounts", "saldo", "REAL")
    # Fase 5 (US-A5): qual funcionalidade gerou a chamada (chat, captura,
    # classificador de intent, etc) - existia so model/tokens/custo antes,
    # sem como separar o gasto por origem no card financeiro.
    _garantir_coluna(conn, "api_usage", "feature", "TEXT NOT NULL DEFAULT 'outro'")
    # Fase 5 (US-C5): marcacao simples de importancia numa espera ja
    # existente, pra priorizar quem responder primeiro (ver
    # vida.priorizar_esperas) sem criar um sistema de contatos novo.
    _garantir_coluna(conn, "esperas", "importante", "INTEGER NOT NULL DEFAULT 0")
    # Fase 5 (US-C7): esforco estimado da tarefa (baixa/media/alta) - usado
    # pra sugerir tarefas compativeis com o nivel de energia atual (ver
    # vida.tarefas_compativeis_com_energia). Sem valor = tratado como 'media'.
    _garantir_coluna(conn, "tasks", "esforco", "TEXT")
    # 2026-10-14 (cards da IA, 2a leva - docs/CARDS.md): compromisso com cara propria
    # (date/balada/documentos/presente) e o que o card guarda dele em JSON (com quem, lista
    # do que levar/preparar com o que ja foi marcado, ideias de presente e a escolhida...).
    _garantir_coluna(conn, "tasks", "estilo", "TEXT")
    _garantir_coluna(conn, "tasks", "extras", "TEXT")
    # Fase 6 (US-E15): limite manual do cartao (Open Finance nao manda isso) -
    # so faz sentido pra tipo='cartao', mas a coluna e generica em
    # bank_accounts (mesmo padrao de "saldo", que tambem so e preenchido
    # quando existe) pra nao precisar de tabela nova so pra um numero.
    _garantir_coluna(conn, "bank_accounts", "limite", "REAL")
    # Fase 6 (US-E2, docs/CARDS.md): cards da resposta do chat, gravados
    # junto da mensagem pra recarregar a pagina nao perder os cards.
    _garantir_coluna(conn, "chat_mensagens", "cards_json", "TEXT")
    # Fase 6 (US-E3): botao "Desperta voce" do card de lembrete (push no
    # horario do lembrete - ver notificacoes.lembretes_para_despertar).
    _garantir_coluna(conn, "lembretes", "despertar", "INTEGER NOT NULL DEFAULT 0")
    # 2026-10-15: medidas reais do aparelho (tela/barra de abas, microfone) pra parar de chutar
    # bug de iPhone sem iPhone - rotas/diagnostico.py grava, scripts/ler_chat.py mostra.
    conn.execute(
        """CREATE TABLE IF NOT EXISTS diagnostico_cliente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            dados_json TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    # Fase 6 (US-E1a): unificacao das duas secoes de manutencao - colunas
    # novas em bancos que ainda tem o `manutencoes` de 5 colunas (ver
    # _migrar_manutencoes_unificadas logo abaixo pra copia dos dados de
    # `manutencoes_veiculo`, se a tabela antiga ainda existir).
    _garantir_coluna(conn, "manutencoes", "tipo", "TEXT NOT NULL DEFAULT 'outro'")
    _garantir_coluna(conn, "manutencoes", "km", "REAL")
    _garantir_coluna(conn, "manutencoes", "proxima_em_km", "REAL")
    _garantir_coluna(conn, "manutencoes", "proxima_em_data", "TEXT")
    # Fase 6 (US-E10): "O que eu lembro sobre voce" ganha grupos fixos
    # (sua_rotina/seus_planos/fora_do_painel) - coluna nova em bancos que ja
    # tem `memorias` de antes.
    _garantir_coluna(conn, "memorias", "categoria", "TEXT")
    # Fase 6 F3 (US-F11): nacional x internacional muda a regra pratica da
    # linha do tempo de planejamento (vida.marcos_planejamento_viagem) -
    # sem essa coluna nao da pra saber qual conjunto de marcos mostrar.
    _garantir_coluna(conn, "viagens", "internacional", "INTEGER NOT NULL DEFAULT 0")
    # Fase 6 F3 (US-F12): numero do voo comprado (preenchido pelo Alex depois
    # da compra) - sem isso nao ha o que consultar na API de status de voo.
    _garantir_coluna(conn, "viagens", "numero_voo", "TEXT")
    # Fase 6 F3 (US-F13): coordenadas cacheadas do geocode Nominatim (US-F13) -
    # nunca geocodifica o mesmo lugar duas vezes (politica de uso do Nominatim).
    _garantir_coluna(conn, "lugares", "lat", "REAL")
    _garantir_coluna(conn, "lugares", "lng", "REAL")
    _garantir_coluna(conn, "lugares", "geocode_status", "TEXT")
    # Revisao da Fase 6: status "erro" (falha temporaria do Nominatim) so
    # tenta de novo depois desse instante (UTC, "AAAA-MM-DD HH:MM:SS").
    _garantir_coluna(conn, "lugares", "geocode_tentar_depois", "TEXT")
    _garantir_indices(conn)
    _seed_perfil_inicial(conn)
    _seed_rotina_padrao(conn)
    _migrar_criptografia_campos_sensiveis(conn)
    _migrar_manutencoes_unificadas(conn)
    _seed_memorias_categorizadas_fase6(conn)
    conn.close()
    # Fase 7: mudanca de schema nova mora em migracoes/*.sql (ver
    # migracoes/README.md) - SEMPRE por ultimo, depois de tudo acima.
    aplicar_migracoes()


# ---- Migracoes por arquivo (Fase 7, Etapa 0) -------------------------------
# Cada faixa cria migracoes/AAAAMMDDHHMM_<faixa>_<descricao>.sql em vez de
# editar init_db(). Aplicadas em ordem alfabetica, uma vez so por banco
# (tabela migracoes_aplicadas), cada arquivo numa transacao propria.

MIGRACOES_DIR = Path(__file__).parent / "migracoes"

_RE_COMENTARIO_INICIAL = re.compile(r"^(\s|--[^\n]*(\n|$)|/\*.*?\*/)+", re.S)
_CONTROLE_TRANSACAO = {"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}


class ErroMigracao(RuntimeError):
    """Uma migracao de migracoes/ falhou - ja desfeita inteira (ROLLBACK)."""


def _sem_comentario_inicial(comando: str) -> str:
    return _RE_COMENTARIO_INICIAL.sub("", comando, count=1)


def _comandos_sql(texto: str) -> list[str]:
    """Divide um script SQL em comandos, respeitando string com ';' e corpo
    de trigger (BEGIN ... END;) - usa o proprio parser do sqlite
    (complete_statement). Pedaco so de comentario/espaco e descartado."""
    comandos = []
    inicio = 0
    for i, ch in enumerate(texto):
        if ch == ";" and sqlite3.complete_statement(texto[inicio:i + 1]):
            comandos.append(texto[inicio:i + 1])
            inicio = i + 1
    comandos.append(texto[inicio:])
    return [c for c in comandos if _sem_comentario_inicial(c).strip()]


def _primeira_palavra(comando: str) -> str:
    palavras = _sem_comentario_inicial(comando).split(None, 1)
    return palavras[0].rstrip(";").upper() if palavras else ""


def aplicar_migracoes() -> list[str]:
    """Aplica os migracoes/*.sql que ainda nao rodaram neste banco (ordem
    alfabetica) e devolve os nomes aplicados agora. Cada arquivo roda numa
    transacao `BEGIN IMMEDIATE` junto com o registro em migracoes_aplicadas -
    falhou, ROLLBACK e ErroMigracao com o nome do arquivo (nunca deixa o
    banco pela metade). Chamada pelo init_db()."""
    pasta = Path(MIGRACOES_DIR)
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=30)
    aplicadas = []
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS migracoes_aplicadas (nome TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)"
        )
        arquivos = sorted(pasta.glob("*.sql")) if pasta.is_dir() else []
        for arquivo in arquivos:
            nome = arquivo.name
            if conn.execute("SELECT 1 FROM migracoes_aplicadas WHERE nome = ?", (nome,)).fetchone():
                continue
            try:
                comandos = _comandos_sql(arquivo.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeDecodeError) as e:
                raise ErroMigracao(f"migracao {nome}: nao consegui ler o arquivo ({e})") from e
            proibido = next((c for c in comandos if _primeira_palavra(c) in _CONTROLE_TRANSACAO), None)
            if proibido:
                raise ErroMigracao(
                    f"migracao {nome}: sem BEGIN/COMMIT/ROLLBACK/SAVEPOINT no arquivo - a transacao e "
                    f"de quem aplica (achei: {_sem_comentario_inicial(proibido).strip()[:60]!r})"
                )
            conn.execute("BEGIN IMMEDIATE")
            try:
                # outro processo pode ter aplicado entre a checagem e o lock
                if conn.execute("SELECT 1 FROM migracoes_aplicadas WHERE nome = ?", (nome,)).fetchone():
                    conn.execute("ROLLBACK")
                    continue
                for comando in comandos:
                    conn.execute(comando)
                conn.execute(
                    "INSERT INTO migracoes_aplicadas (nome, aplicada_em) VALUES (?, datetime('now'))", (nome,)
                )
                conn.execute("COMMIT")
            except Exception as e:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise ErroMigracao(f"migracao {nome} falhou e foi desfeita inteira: {e}") from e
            aplicadas.append(nome)
    finally:
        conn.close()
    return aplicadas


def _garantir_indices(conn):
    """Indices nas colunas mais filtradas/ordenadas pelo app - rodado depois das
    migracoes de coluna acima, pra nunca tentar indexar uma coluna que ainda nao
    existe num banco antigo. Banco e pequeno (uso pessoal), entao isso e mais
    sobre nao regredir conforme o historico cresce do que sobre um problema de
    performance que exista hoje."""
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_completed_at ON tasks(completed_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
        CREATE INDEX IF NOT EXISTS idx_subtasks_task_id ON subtasks(task_id);
        CREATE INDEX IF NOT EXISTS idx_expenses_created_at ON expenses(created_at);
        CREATE INDEX IF NOT EXISTS idx_expenses_tipo ON expenses(tipo);
        CREATE INDEX IF NOT EXISTS idx_bank_transactions_bank_account_id ON bank_transactions(bank_account_id);
        CREATE INDEX IF NOT EXISTS idx_goal_deposits_goal_id ON goal_deposits(goal_id);
        CREATE INDEX IF NOT EXISTS idx_cotacoes_itens_cotacao_id ON cotacoes_itens(cotacao_id);
        CREATE INDEX IF NOT EXISTS idx_voos_data ON voos(data);
        CREATE INDEX IF NOT EXISTS idx_esperas_resolvido_em ON esperas(resolvido_em);
        CREATE INDEX IF NOT EXISTS idx_interacoes_aprendizado_aberta
            ON interacoes_aprendizado(tipo, referencia_id, resolvido_em);
        CREATE INDEX IF NOT EXISTS idx_incomes_created_at ON incomes(created_at);
        CREATE INDEX IF NOT EXISTS idx_notas_criado_em ON notas(criado_em);
        CREATE INDEX IF NOT EXISTS idx_tasks_recorrencia ON tasks(recorrencia);
        CREATE INDEX IF NOT EXISTS idx_tasks_recorrente_origem_id ON tasks(recorrente_origem_id);
        CREATE INDEX IF NOT EXISTS idx_medicamentos_ativo ON medicamentos(ativo);
        CREATE INDEX IF NOT EXISTS idx_hidratacao_registros_data ON hidratacao_registros(data);
        CREATE INDEX IF NOT EXISTS idx_medidas_corporais_tipo_data ON medidas_corporais(tipo, data);
        CREATE INDEX IF NOT EXISTS idx_conversas_pessoa_id ON conversas(pessoa_id);
        CREATE INDEX IF NOT EXISTS idx_conversas_data ON conversas(data);
        CREATE INDEX IF NOT EXISTS idx_treinos_data ON treinos(data);
        CREATE INDEX IF NOT EXISTS idx_viagem_itens_viagem_id ON viagem_itens(viagem_id);
        CREATE INDEX IF NOT EXISTS idx_compras_pendentes ON compras(comprado_em, item_normalizado);
        CREATE INDEX IF NOT EXISTS idx_responder_respondido_em ON responder(respondido_em);
        CREATE INDEX IF NOT EXISTS idx_app_eventos_em ON app_eventos(em);
        CREATE INDEX IF NOT EXISTS idx_capture_idempotency_criado_em ON capture_idempotency(criado_em);
        CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);
        CREATE INDEX IF NOT EXISTS idx_habito_marcacoes_habito_id ON habito_marcacoes(habito_id);
        CREATE INDEX IF NOT EXISTS idx_projeto_etapas_projeto_id ON projeto_etapas(projeto_id);
        """
    )
    conn.commit()


def _garantir_coluna(conn, tabela: str, coluna: str, tipo: str):
    """Adiciona uma coluna nova numa tabela que ja existe de uma versao anterior
    do app - CREATE TABLE IF NOT EXISTS nao faz isso sozinho."""
    colunas = [r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
    if coluna not in colunas:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        conn.commit()


PERFIL_INICIAL = [
    "Se chama Alex, tem 20 anos (nasceu em 8 de dezembro de 2005).",
    "E piloto de aviao.",
    "Tem uma construtora - constroi predios e casas.",
]


# Fase 6 (US-E10): texto inicial de "O que eu lembro sobre voce" - repositorio
# privado (confirmado pelo Alex), pode ficar no codigo como seed. Cada grupo e
# uma categoria de `memorias` (coluna `categoria`); ver _seed_memorias_categorizadas_fase6
# pra regra de idempotencia (so semeia categoria vazia, nunca sobrescreve edicao).
MEMORIAS_INICIAIS_FASE6 = {
    "sua_rotina": [
        "Horario de trabalho variavel - pode comecar antes das 7h em dias cheios, ou seguir horario "
        "comum (7h-9h) em dias mais tranquilos. Nao tratar como fixo.",
        "Treino sem horario fixo preferido - sugerir de forma flexivel, nao travado num periodo do dia.",
        "Sono ainda irregular, em processo de ajuste - esse e justamente um dos motivos de construir o "
        "painel. Quando o padrao de sono vier ruim em periodo de viagem/trabalho intenso (voo, semana "
        "pesada), ajustar a sugestao dos dias seguintes de acordo (tarefa mais leve primeiro).",
    ],
    "seus_planos": [
        "Expansao da empresa (construtora): acompanhar como projeto de alto nivel (nome, etapa atual, "
        "marco), sem numero financeiro - valor e detalhe de caixa ficam so no painel financeiro-construtora, "
        "nunca aqui.",
        "Ao avaliar 'vale a pena' em decisao financeira grande: contexto conhecido, nao regra automatica - "
        "historicamente prefere financiar a taxa baixa e manter capital girando no negocio, em vez de "
        "imobilizar em compra a vista, mas a analise continua caso a caso com os numeros reais, sem assumir "
        "financiamento como resposta padrao.",
    ],
    "fora_do_painel": [
        "Compra de carro: so decisao pontual, nao vira projeto/meta rastreado.",
        "Vida amorosa/relacionamento: sem registro de data ou gesto automatizado.",
    ],
}

CATEGORIAS_MEMORIA = tuple(MEMORIAS_INICIAIS_FASE6.keys())


def _seed_memorias_categorizadas_fase6(conn):
    """Semeia MEMORIAS_INICIAIS_FASE6, uma categoria de cada vez - so insere
    numa categoria que ainda esta vazia (idempotente: roda em todo init_db,
    mas nunca duplica nem sobrescreve edicao/remocao que o Alex ja tenha
    feito - se ele apagar um item e a categoria ficar vazia nao-intencionalmente,
    o comportamento e semear de novo, igual a primeira vez; isso e o que o
    criterio "categoria vazia" literalmente decide)."""
    for categoria, itens in MEMORIAS_INICIAIS_FASE6.items():
        ja_tem = conn.execute(
            "SELECT 1 FROM memorias WHERE categoria = ? LIMIT 1", (categoria,)
        ).fetchone()
        if ja_tem:
            continue
        for texto in itens:
            conn.execute(
                "INSERT INTO memorias (texto, source_text, categoria) VALUES (?, ?, ?)",
                (texto, "seed-fase6", categoria),
            )
    conn.commit()


def _seed_perfil_inicial(conn):
    """Poe os fatos basicos do perfil como memoria logo na primeira vez que o
    banco e criado, pra ele ja "conhecer" a pessoa desde o primeiro uso em vez
    de aprender tudo do zero. So roda uma vez (marca pelo source_text)."""
    ja_existe = conn.execute(
        "SELECT 1 FROM memorias WHERE source_text = 'perfil-inicial' LIMIT 1"
    ).fetchone()
    if ja_existe:
        return
    for texto in PERFIL_INICIAL:
        conn.execute(
            "INSERT INTO memorias (texto, source_text) VALUES (?, ?)", (texto, "perfil-inicial")
        )
    conn.commit()


def _seed_rotina_padrao(conn):
    """Itens padrao da rotina manha/noite, uma vez so (marca em configuracoes) -
    se o Alex apagar tudo depois, nao volta sozinho."""
    if obter_configuracao(conn, "rotina_semeada"):
        return
    for momento, itens in vida.ITENS_ROTINA_PADRAO.items():
        for posicao, texto in enumerate(itens):
            conn.execute(
                "INSERT INTO rotina_itens (momento, texto, posicao) VALUES (?, ?, ?)",
                (momento, texto, posicao),
            )
    definir_configuracao(conn, "rotina_semeada", "1")


def _migrar_criptografia_campos_sensiveis(conn):
    """Criptografa em repouso o que ja estava gravado em texto plano (Open
    Finance + saude) na primeira subida do app depois que ENCRYPTION_KEY foi
    configurada. So roda se a chave estiver presente (sem chave, nao ha com
    que criptografar - ver criptografia.py) e so uma vez (marca em
    `configuracoes`, mesmo padrao de _seed_rotina_padrao): rodar duas vezes
    criptografaria um valor que ja esta cifrado, virando lixo ilegivel."""
    if not criptografia.configurada():
        return
    if obter_configuracao(conn, "criptografia_migrada"):
        return

    for row in conn.execute("SELECT id, saldo FROM bank_accounts").fetchall():
        if row["saldo"] is not None:
            conn.execute(
                "UPDATE bank_accounts SET saldo = ? WHERE id = ?",
                (_cnum(row["saldo"]), row["id"]),
            )

    for row in conn.execute("SELECT id, descricao, valor FROM bank_transactions").fetchall():
        conn.execute(
            "UPDATE bank_transactions SET descricao = ?, valor = ? WHERE id = ?",
            (criptografia.criptografar(row["descricao"]), _cnum(row["valor"]), row["id"]),
        )

    for row in conn.execute(
        "SELECT id, passos, distancia_km, sono_horas, andares_subidos FROM saude_dados"
    ).fetchall():
        conn.execute(
            """UPDATE saude_dados SET passos = ?, distancia_km = ?, sono_horas = ?,
               andares_subidos = ? WHERE id = ?""",
            (
                _cnum(row["passos"]),
                _cnum(row["distancia_km"]),
                _cnum(row["sono_horas"]),
                _cnum(row["andares_subidos"]),
                row["id"],
            ),
        )

    for row in conn.execute("SELECT id, valor FROM medidas_corporais").fetchall():
        conn.execute(
            "UPDATE medidas_corporais SET valor = ? WHERE id = ?", (_cnum(row["valor"]), row["id"])
        )

    for row in conn.execute("SELECT id, nome, dosagem, horario FROM medicamentos").fetchall():
        conn.execute(
            "UPDATE medicamentos SET nome = ?, dosagem = ?, horario = ? WHERE id = ?",
            (
                criptografia.criptografar(row["nome"]),
                criptografia.criptografar(row["dosagem"]),
                criptografia.criptografar(row["horario"]),
                row["id"],
            ),
        )

    definir_configuracao(conn, "criptografia_migrada", "1")
    conn.commit()


def _migrar_manutencoes_unificadas(conn):
    """Fase 6 (US-E1a): copia as linhas de `manutencoes_veiculo` (tabela
    dedicada da Fase 5/US-C14, por km/data) pra dentro de `manutencoes` (que
    ja ganhou as colunas `tipo`/km/proxima_em_km/proxima_em_data acima) como
    tipo='carro', e apaga a tabela antiga - a partir daqui so existe UMA
    tabela/secao de manutencao. Idempotente por dois motivos independentes
    (mesmo padrao de _migrar_criptografia_campos_sensiveis): a flag em
    `configuracoes` evita rodar de novo, e mesmo sem a flag, depois da
    primeira vez a tabela `manutencoes_veiculo` nao existe mais - nada pra
    copiar. intervalo_meses grava 0 (sentinela, nunca lido pra tipo='carro',
    so existe pra satisfazer a coluna NOT NULL)."""
    if obter_configuracao(conn, "manutencoes_unificadas_fase6"):
        return
    existe = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'manutencoes_veiculo'"
    ).fetchone()
    if existe:
        for row in conn.execute(
            "SELECT tipo, data, km, proxima_em_km, proxima_em_data, criado_em FROM manutencoes_veiculo"
        ).fetchall():
            conn.execute(
                """INSERT INTO manutencoes
                   (tipo, item, intervalo_meses, ultima_vez, km, proxima_em_km, proxima_em_data, criado_em)
                   VALUES ('carro', ?, 0, ?, ?, ?, ?, ?)""",
                (row["tipo"], row["data"], row["km"], row["proxima_em_km"], row["proxima_em_data"], row["criado_em"]),
            )
        conn.execute("DROP TABLE manutencoes_veiculo")
    definir_configuracao(conn, "manutencoes_unificadas_fase6", "1")
    conn.commit()


def save_push_subscription(conn, endpoint: str, subscription_json: str):
    conn.execute(
        "INSERT OR REPLACE INTO push_subscriptions (endpoint, subscription_json) VALUES (?, ?)",
        (endpoint, subscription_json),
    )
    conn.commit()


def list_push_subscriptions(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM push_subscriptions").fetchall()]


def delete_push_subscription(conn, endpoint: str):
    conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    conn.commit()


def get_or_create_bank_account(conn, banco: str, tipo: str = "conta") -> int:
    row = conn.execute(
        "SELECT id FROM bank_accounts WHERE banco = ? AND tipo = ?", (banco, tipo)
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO bank_accounts (banco, tipo) VALUES (?, ?)", (banco, tipo))
    conn.commit()
    return cur.lastrowid


def atualizar_saldo_conta(conn, bank_account_id: int, saldo: float) -> None:
    """Grava o saldo mais recente vindo da sincronizacao (Pluggy) - sobrescreve
    qualquer ajuste otimista feito entre uma sincronizacao e outra, pra nao
    acumular deriva."""
    conn.execute(
        "UPDATE bank_accounts SET saldo = ? WHERE id = ?", (_cnum(saldo), bank_account_id)
    )
    conn.commit()


def _descriptografar_conta(d: dict) -> dict:
    d["saldo"] = _dnum(d["saldo"], float)
    return d


def _descriptografar_transacao(d: dict) -> dict:
    d["descricao"] = criptografia.descriptografar(d["descricao"])
    d["valor"] = _dnum(d["valor"], float)
    return d


def list_bank_accounts(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM bank_accounts ORDER BY banco, tipo").fetchall()
    return [_descriptografar_conta(dict(r)) for r in rows]


def estatisticas_conta(conn, bank_account_id: int) -> dict:
    """Total de transacoes, data da mais recente e total gasto (soma das
    saidas) de uma conta - valor/descricao sao criptografados em repouso,
    entao SUM/CASE direto no SQL nao funciona mais aqui: descriptografa e
    soma em Python (tabela pequena, app de uso pessoal - ver docs/SEGURANCA.md)."""
    rows = conn.execute(
        "SELECT valor, data FROM bank_transactions WHERE bank_account_id = ?", (bank_account_id,)
    ).fetchall()
    total_gasto = 0.0
    ultima = None
    for r in rows:
        valor = _dnum(r["valor"], float)
        if r["data"] is not None and (ultima is None or r["data"] > ultima):
            ultima = r["data"]
        if valor is not None and valor < 0:
            total_gasto += -valor
    return {"total": len(rows), "ultima": ultima, "total_gasto": total_gasto}


def list_bank_transactions(conn, bank_account_id: int, limite: int = 100) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM bank_transactions WHERE bank_account_id = ? ORDER BY data DESC LIMIT ?",
        (bank_account_id, limite),
    ).fetchall()
    return [_descriptografar_transacao(dict(r)) for r in rows]


def list_all_bank_transactions(conn) -> list[dict]:
    """Todas as transacoes bancarias, de todas as contas, ja descriptografadas
    - usado por quem precisa filtrar/somar em Python porque a condicao
    envolve `valor` (criptografado, ver `_gastos_reais_unificados` em app.py)."""
    rows = conn.execute("SELECT * FROM bank_transactions").fetchall()
    return [_descriptografar_transacao(dict(r)) for r in rows]


def list_bank_transactions_by_ids(conn, ids: list[int]) -> list[dict]:
    """Mesma descriptografia de list_all_bank_transactions, mas so pras
    linhas pedidas (por id) - usado pela paginacao de /api/gastos/unificados
    (rotas/f8_banco.py, Fase vel/A2a) pra nao pagar o custo de decifrar
    (Fernet) as transacoes bancarias inteiras so pra montar uma pagina de
    30 itens. Lista de ids vazia devolve lista vazia sem tocar no banco."""
    if not ids:
        return []
    marcadores = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT * FROM bank_transactions WHERE id IN ({marcadores})", ids
    ).fetchall()
    return [_descriptografar_transacao(dict(r)) for r in rows]


def buscar_conta_por_nome(conn, nome: str) -> dict | None:
    """Acha a conta bancaria cujo nome mais parece com o texto informado (ex: o
    Alex escreveu "Nubank" ou "nubank" no chat) - correspondencia parcial e sem
    diferenciar maiusculas, preferindo 'conta' sobre 'cartao' quando ha as duas
    pro mesmo banco. Retorna None se nao achar nada parecido (nunca inventa)."""
    nome = (nome or "").strip()
    if not nome:
        return None
    row = conn.execute(
        "SELECT * FROM bank_accounts WHERE banco LIKE ? ORDER BY (tipo = 'conta') DESC, id ASC LIMIT 1",
        (f"%{nome}%",),
    ).fetchone()
    return _descriptografar_conta(dict(row)) if row else None


def ajustar_saldo_conta(conn, bank_account_id: int, delta: float) -> tuple[float, float] | None:
    """Aplica um ajuste otimista de saldo (o gasto/renda foi digitado no chat,
    nao veio de uma nova sincronizacao) e devolve (saldo_antes, saldo_depois).
    Devolve None se a conta nunca teve saldo sincronizado - nunca calcula um
    saldo a partir do nada."""
    row = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (bank_account_id,)).fetchone()
    if row is None or row["saldo"] is None:
        return None
    saldo_antes = _dnum(row["saldo"], float)
    saldo_depois = saldo_antes + delta
    conn.execute(
        "UPDATE bank_accounts SET saldo = ? WHERE id = ?", (_cnum(saldo_depois), bank_account_id)
    )
    conn.commit()
    return (saldo_antes, saldo_depois)


def insert_bank_transactions(conn, bank_account_id: int, transactions: list[dict]) -> int:
    """Insere transacoes ignorando duplicatas (mesmo external_id). Retorna quantas foram novas.
    Cada dict pode trazer uma 'categoria' ja decidida (ver gastos.sugerir_categoria,
    chamado por quem importa o OFX) - fica NULL quando nao foi possivel decidir."""
    novas = 0
    for t in transactions:
        cur = conn.execute(
            """INSERT OR IGNORE INTO bank_transactions
               (bank_account_id, data, descricao, valor, external_id, categoria)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                bank_account_id,
                t["data"],
                criptografia.criptografar(t["descricao"]),
                _cnum(t["valor"]),
                t["external_id"],
                t.get("categoria"),
            ),
        )
        if cur.rowcount:
            novas += 1
    conn.commit()
    return novas


def create_goal(conn, titulo: str, valor_alvo: float, prazo: str | None) -> int:
    cur = conn.execute(
        "INSERT INTO goals (titulo, valor_alvo, prazo) VALUES (?, ?, ?)",
        (titulo, valor_alvo, prazo),
    )
    conn.commit()
    return cur.lastrowid


def add_to_goal(conn, goal_id: int, valor: float):
    conn.execute(
        "UPDATE goals SET valor_guardado = valor_guardado + ? WHERE id = ?", (valor, goal_id)
    )
    conn.execute("INSERT INTO goal_deposits (goal_id, valor) VALUES (?, ?)", (goal_id, valor))
    conn.commit()


def list_goal_deposits(conn, goal_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT valor, criado_em FROM goal_deposits WHERE goal_id = ? ORDER BY criado_em",
        (goal_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_goals(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM goals ORDER BY criado_em DESC").fetchall()
    return [dict(r) for r in rows]


def record_usage(
    conn, model: str, input_tokens: int, output_tokens: int, cost_usd: float, feature: str = "outro"
):
    conn.execute(
        "INSERT INTO api_usage (model, input_tokens, output_tokens, cost_usd, feature) VALUES (?, ?, ?, ?, ?)",
        (model, input_tokens, output_tokens, cost_usd, feature or "outro"),
    )
    conn.commit()


def _limite_utc(momento_local: datetime) -> str:
    """api_usage.created_at e UTC (datetime('now') do SQLite, sem tzinfo) -
    um limite de periodo calculado em horario local (inicio do mes, N dias
    atras) precisa virar UTC antes de comparar, senao a virada de mes/dia
    fica errada em ate ~12h dependendo do fuso."""
    return momento_local.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")


def resumo_custo_api(conn) -> dict:
    """Resumo do gasto com a API da Anthropic (US-A5) - soma api_usage.cost_usd
    (USD, mesma unidade ja usada por total_cost_usd) por periodo, pro card
    financeiro. mes_atual usa o calendario local (dia 1 00:00); ultimos_30_dias
    e uma janela corrida a partir de agora."""
    agora_local = datetime.now().astimezone()
    inicio_mes_local = agora_local.replace(hour=0, minute=0, second=0, microsecond=0, day=1)
    desde_30_dias_local = agora_local - timedelta(days=30)

    mes_atual = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM api_usage WHERE created_at >= ?",
        (_limite_utc(inicio_mes_local),),
    ).fetchone()["total"]
    ultimos_30_dias = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM api_usage WHERE created_at >= ?",
        (_limite_utc(desde_30_dias_local),),
    ).fetchone()["total"]
    por_feature = conn.execute(
        "SELECT feature, COALESCE(SUM(cost_usd), 0) AS total FROM api_usage "
        "WHERE created_at >= ? GROUP BY feature ORDER BY total DESC",
        (_limite_utc(desde_30_dias_local),),
    ).fetchall()

    teto = obter_teto_mensal_ia(conn)
    fracao_teto = (mes_atual / teto) if teto else None

    return {
        "moeda": "USD",
        "mes_atual_usd": round(mes_atual, 4),
        "ultimos_30_dias_usd": round(ultimos_30_dias, 4),
        "ultimos_30_dias_por_feature": [
            {"feature": r["feature"], "custo_usd": round(r["total"], 4)} for r in por_feature
        ],
        # Fase 5 (US-A6): teto None = nunca configurado (sem limite, todos os
        # campos abaixo ficam None/False). fracao_teto e mes_atual/teto, sem
        # arredondar pro chamador decidir a casa decimal.
        "teto_mensal_usd": teto,
        "fracao_teto": fracao_teto,
        "teto_perto": fracao_teto is not None and fracao_teto >= 0.8,
        "teto_estourado": fracao_teto is not None and fracao_teto >= 1.0,
    }


def total_cost_usd(conn) -> float:
    row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) AS total FROM api_usage").fetchone()
    return row["total"]


def create_memoria(conn, texto: str, source_text: str | None = None, categoria: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO memorias (texto, source_text, categoria) VALUES (?, ?, ?)", (texto, source_text, categoria)
    )
    conn.commit()
    return cur.lastrowid


def list_memorias(conn, limit: int = 200) -> list[dict]:
    # 2026-10-13: era 30 - passando de 30 fatos, os MAIS ANTIGOS (perfil inicial, rotina,
    # planos) sumiam do prompt do chat e da tela "O que eu lembro" sem aviso. Fato e curto
    # (~50 caracteres): 200 cabem com folga no prompt.
    rows = conn.execute(
        "SELECT * FROM memorias ORDER BY criado_em DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def update_memoria(conn, memoria_id: int, texto: str) -> bool:
    """Edicao no lugar do texto de uma memoria (Fase 6, US-E10) - so o texto
    muda, categoria/source_text ficam como estavam."""
    cur = conn.execute("UPDATE memorias SET texto = ? WHERE id = ?", (texto, memoria_id))
    conn.commit()
    return cur.rowcount > 0


def delete_memoria(conn, memoria_id: int):
    conn.execute("DELETE FROM memorias WHERE id = ?", (memoria_id,))
    conn.commit()


def contexto_memorias_categorizadas(conn) -> dict[str, list[dict]]:
    """Fase 6 (US-E10): funcao unica que devolve as memorias fixas agrupadas
    por categoria (sua_rotina/seus_planos/fora_do_painel), pro prompt do
    assistente e pra caixa "Com a sua rotina em mente" (US-E4/E7) - cada
    grupo em ordem de criacao (os itens do seed primeiro, depois o que o
    Alex foi adicionando)."""
    resultado = {categoria: [] for categoria in CATEGORIAS_MEMORIA}
    rows = conn.execute(
        "SELECT * FROM memorias WHERE categoria IN ({}) ORDER BY criado_em ASC".format(
            ",".join("?" for _ in CATEGORIAS_MEMORIA)
        ),
        CATEGORIAS_MEMORIA,
    ).fetchall()
    for row in rows:
        item = dict(row)
        resultado.setdefault(item["categoria"], []).append(item)
    return resultado


def create_nota(
    conn, titulo: str, corpo: str, tags: list[str] | None = None, source_text: str | None = None
) -> int:
    tags_str = ",".join(t.strip().lower() for t in tags if t.strip()) if tags else None
    cur = conn.execute(
        "INSERT INTO notas (titulo, corpo, tags, source_text) VALUES (?, ?, ?, ?)",
        (titulo, corpo, tags_str, source_text),
    )
    conn.commit()
    return cur.lastrowid


def list_notas(conn, limit: int = 50) -> list[dict]:
    rows = conn.execute("SELECT * FROM notas ORDER BY atualizado_em DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def buscar_notas(conn, termo: str, limit: int = 10) -> list[dict]:
    """Acha notas pelo titulo, corpo ou uma tag que contenha o termo - usado
    pelo chat quando o Alex pergunta algo tipo "o que eu anotei sobre Portugal"."""
    termo = (termo or "").strip()
    if not termo:
        return []
    curinga = f"%{termo}%"
    rows = conn.execute(
        """SELECT * FROM notas
           WHERE titulo LIKE ? OR corpo LIKE ? OR tags LIKE ?
           ORDER BY atualizado_em DESC LIMIT ?""",
        (curinga, curinga, curinga.lower(), limit),
    ).fetchall()
    return [dict(r) for r in rows]


def apagar_nota(conn, nota_id: int):
    conn.execute("DELETE FROM notas WHERE id = ?", (nota_id,))
    conn.commit()


def create_diario_decisao(
    conn,
    decisao: str,
    contexto: str | None = None,
    revisao_em: str | None = None,
    source_text: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO diario_decisoes (decisao, contexto, revisao_em, source_text) VALUES (?, ?, ?, ?)",
        (decisao, contexto, revisao_em, source_text),
    )
    conn.commit()
    return cur.lastrowid


def list_diario_decisoes(conn, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM diario_decisoes ORDER BY data DESC, criado_em DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def obter_diario_decisao(conn, decisao_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM diario_decisoes WHERE id = ?", (decisao_id,)).fetchone()
    return dict(row) if row else None


def registrar_resultado_diario_decisao(conn, decisao_id: int, resultado: str) -> bool:
    cur = conn.execute(
        "UPDATE diario_decisoes SET resultado = ?, atualizado_em = datetime('now') WHERE id = ?",
        (resultado, decisao_id),
    )
    conn.commit()
    return cur.rowcount > 0


def apagar_diario_decisao(conn, decisao_id: int):
    conn.execute("DELETE FROM diario_decisoes WHERE id = ?", (decisao_id,))
    conn.commit()


def create_brain_dump(conn, texto: str) -> int:
    cur = conn.execute("INSERT INTO brain_dump (texto) VALUES (?)", (texto,))
    conn.commit()
    return cur.lastrowid


def list_brain_dump_pendentes(conn, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM brain_dump WHERE processado = 0 ORDER BY criado_em LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def obter_brain_dump(conn, item_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM brain_dump WHERE id = ?", (item_id,)).fetchone()
    return dict(row) if row else None


def marcar_brain_dump_processado(conn, item_id: int) -> bool:
    cur = conn.execute(
        "UPDATE brain_dump SET processado = 1 WHERE id = ? AND processado = 0", (item_id,)
    )
    conn.commit()
    return cur.rowcount > 0


def apagar_brain_dump(conn, item_id: int):
    conn.execute("DELETE FROM brain_dump WHERE id = ?", (item_id,))
    conn.commit()


def criar_tarefa_de_brain_dump(
    conn, titulo: str, due_date: str | None = None, hora: str | None = None, source_text: str | None = None
) -> int:
    """Insert minimo de tarefa (sem passar pela classificacao por IA de
    /api/capture) - usado so na conversao de um item de brain dump (US-C6),
    onde o Alex ja escolheu manualmente que e uma tarefa."""
    cur = conn.execute(
        "INSERT INTO tasks (title, due_date, hora, source_text) VALUES (?, ?, ?, ?)",
        (titulo, due_date, hora, source_text),
    )
    conn.commit()
    return cur.lastrowid


def criar_gasto_de_brain_dump(
    conn, valor: float, categoria: str | None, descricao: str, source_text: str | None = None
) -> int:
    """Mesmo espirito de criar_tarefa_de_brain_dump, so que pra gasto."""
    cur = conn.execute(
        "INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (?, ?, ?, ?, 'real')",
        (valor, categoria or "outros", descricao, source_text),
    )
    conn.commit()
    return cur.lastrowid


CAMPOS_SAUDE = ("passos", "distancia_km", "sono_horas", "andares_subidos")


def _descriptografar_saude(d: dict) -> dict:
    d["passos"] = _dnum(d["passos"], int)
    d["distancia_km"] = _dnum(d["distancia_km"], float)
    d["sono_horas"] = _dnum(d["sono_horas"], float)
    d["andares_subidos"] = _dnum(d["andares_subidos"], int)
    return d


def upsert_saude_dia(conn, data: str, campos: dict):
    """Grava (ou atualiza, se o dia ja existir) os campos de saude informados
    pra aquele dia - so mexe nos campos presentes em `campos`, preserva o
    resto (o Atalho do iPhone pode mandar so passos numa chamada e sono
    noutra, por exemplo). Cuidado: o valor preservado de uma linha existente
    ja esta CIFRADO (veio direto da coluna) - so os campos novos, que chegam
    em texto plano via `campos`, passam por `_cnum` aqui. Criptografar de
    novo um valor ja cifrado o transformaria em lixo ilegivel."""
    existente = conn.execute("SELECT * FROM saude_dados WHERE data = ?", (data,)).fetchone()
    valores = {}
    for campo in CAMPOS_SAUDE:
        novo = campos.get(campo)
        if novo is not None:
            valores[campo] = _cnum(novo)
        elif existente:
            valores[campo] = existente[campo]  # ja cifrado (ou texto plano legado) - mantem como esta
        else:
            valores[campo] = None
    if existente:
        conn.execute(
            """UPDATE saude_dados SET passos = ?, distancia_km = ?, sono_horas = ?,
               andares_subidos = ? WHERE data = ?""",
            (*[valores[c] for c in CAMPOS_SAUDE], data),
        )
    else:
        conn.execute(
            """INSERT INTO saude_dados (data, passos, distancia_km, sono_horas, andares_subidos)
               VALUES (?, ?, ?, ?, ?)""",
            (data, *[valores[c] for c in CAMPOS_SAUDE]),
        )
    conn.commit()


def get_saude_dia(conn, data: str) -> dict | None:
    row = conn.execute("SELECT * FROM saude_dados WHERE data = ?", (data,)).fetchone()
    return _descriptografar_saude(dict(row)) if row else None


def list_saude_dados(conn, desde: str | None = None, ate: str | None = None) -> list[dict]:
    """Linhas de saude_dados descriptografadas, opcionalmente filtradas por
    intervalo de `data` (nao e campo criptografado, entao o filtro continua
    no SQL normalmente). Base comum pra quem precisa agregar/filtrar por
    passos/sono/etc em Python (ver media_passos_ultimos_dias aqui e as
    correlacoes de sono em aprendizado.py)."""
    query = "SELECT * FROM saude_dados WHERE 1=1"
    params = []
    if desde is not None:
        query += " AND data >= ?"
        params.append(desde)
    if ate is not None:
        query += " AND data < ?"
        params.append(ate)
    rows = conn.execute(query, params).fetchall()
    return [_descriptografar_saude(dict(r)) for r in rows]


def media_passos_ultimos_dias(conn, antes_de: str, dias: int = 7) -> float | None:
    """AVG(passos) precisava ser feito no SQL antes de `passos` virar
    criptografado - agora descriptografa cada linha do periodo e faz a media
    em Python (data continua filtrada no SQL, so o AVG mudou de lugar)."""
    inicio = (date.fromisoformat(antes_de) - timedelta(days=dias)).isoformat()
    linhas = list_saude_dados(conn, desde=inicio, ate=antes_de)
    valores = [l["passos"] for l in linhas if l["passos"] is not None]
    if not valores:
        return None
    return sum(valores) / len(valores)


def ja_notificou_hoje(conn, tipo: str, referencia_id: int = 0) -> bool:
    row = conn.execute(
        "SELECT 1 FROM notificacoes_enviadas WHERE tipo = ? AND referencia_id = ? AND data = ?",
        (tipo, referencia_id, date.today().isoformat()),
    ).fetchone()
    return row is not None


def marcar_notificado(conn, tipo: str, referencia_id: int = 0):
    conn.execute(
        "INSERT OR IGNORE INTO notificacoes_enviadas (tipo, referencia_id, data) VALUES (?, ?, ?)",
        (tipo, referencia_id, date.today().isoformat()),
    )
    conn.commit()


def registrar_aviso_insistente(conn, tipo: str, referencia_id: int, titulo: str, corpo: str, tag: str, agora: datetime):
    """1o envio de um aviso que insiste (ver notificacoes.INSISTENCIA). Mesmo aviso no mesmo dia
    nao reabre (UNIQUE)."""
    conn.execute(
        "INSERT OR IGNORE INTO avisos_insistentes (tipo, referencia_id, data, titulo, corpo, tag, enviado_em) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tipo, referencia_id, agora.date().isoformat(), titulo, corpo, tag, agora.isoformat(timespec="seconds")),
    )
    conn.commit()


def marcar_aviso_aberto(conn, tag: str, agora: datetime | None = None) -> int:
    """Toque na notificacao: para de insistir naquele aviso (todas as linhas abertas da tag)."""
    agora = agora or datetime.now()
    n = conn.execute(
        "UPDATE avisos_insistentes SET aberto_em = ? WHERE tag = ? AND aberto_em IS NULL",
        (agora.isoformat(timespec="seconds"), tag),
    ).rowcount
    conn.commit()
    return n


def avisos_insistentes_pendentes(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM avisos_insistentes WHERE aberto_em IS NULL AND encerrado_em IS NULL ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def registrar_repeticao_aviso(conn, aviso_id: int):
    conn.execute("UPDATE avisos_insistentes SET tentativas = tentativas + 1 WHERE id = ?", (aviso_id,))
    conn.commit()


def encerrar_aviso_insistente(conn, aviso_id: int, agora: datetime | None = None):
    agora = agora or datetime.now()
    conn.execute(
        "UPDATE avisos_insistentes SET encerrado_em = ? WHERE id = ? AND encerrado_em IS NULL",
        (agora.isoformat(timespec="seconds"), aviso_id),
    )
    conn.commit()


def ja_notificado_alguma_vez(conn, tipo: str, referencia_id: int = 0) -> bool:
    """Como ja_notificou_hoje, mas ignora a data - pra avisos que devem disparar
    UMA VEZ so quando a condicao aparece (ex: cutucar sobre uma tarefa parada),
    nao repetir todo dia enquanto a condicao continuar verdadeira."""
    row = conn.execute(
        "SELECT 1 FROM notificacoes_enviadas WHERE tipo = ? AND referencia_id = ?",
        (tipo, referencia_id),
    ).fetchone()
    return row is not None


def obter_configuracao(conn, chave: str) -> str | None:
    row = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,)).fetchone()
    return row["valor"] if row else None


def definir_configuracao(conn, chave: str, valor: str):
    conn.execute(
        "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, valor),
    )
    conn.commit()


CHAVE_TETO_MENSAL_IA = "teto_mensal_ia_usd"


def obter_teto_mensal_ia(conn) -> float | None:
    """Teto mensal de gasto com a API da Anthropic (US-A6), em USD (mesma
    moeda de api_usage.cost_usd) - None quando o Alex nunca configurou (sem
    teto nenhum, comportamento igual a antes desta historia)."""
    valor = obter_configuracao(conn, CHAVE_TETO_MENSAL_IA)
    if not valor:
        return None
    try:
        teto = float(valor)
    except (TypeError, ValueError):
        return None
    return teto if teto > 0 else None


def definir_teto_mensal_ia(conn, teto: float | None) -> None:
    """teto None ou <= 0 remove o limite (mesmo efeito de nunca ter configurado)."""
    if teto is None or teto <= 0:
        conn.execute("DELETE FROM configuracoes WHERE chave = ?", (CHAVE_TETO_MENSAL_IA,))
        conn.commit()
        return
    definir_configuracao(conn, CHAVE_TETO_MENSAL_IA, str(teto))


def salvar_mensagem_chat(conn, papel: str, texto: str, cards: list | None = None):
    """`cards` (Fase 6, docs/CARDS.md): os cards da resposta, gravados como
    JSON criptografado em repouso (podem ter valor/saldo - mesmo cuidado do
    resto do dado financeiro, ver docs/SEGURANCA.md). None/[] = sem cards."""
    cards_json = criptografia.criptografar(json.dumps(cards, ensure_ascii=False)) if cards else None
    conn.execute(
        "INSERT INTO chat_mensagens (papel, texto, cards_json) VALUES (?, ?, ?)", (papel, texto, cards_json)
    )
    conn.commit()


# Edicao feita pela IA (2026-10-09): o Desfazer volta EXATAMENTE os valores
# antigos dessas colunas. Lista fechada - nada de tabela/coluna vinda da IA, e
# nenhuma coluna de dinheiro (expenses.amount fica de fora de proposito).
EDICAO_COLUNAS = {
    "tasks": ("title", "hora", "due_date", "due_at", "completed_at", "local"),
    "lembretes": ("titulo", "data", "recorrente", "despertar"),
    "voos": ("data", "origem", "destino", "horas", "aeronave", "funcao", "observacao"),
    # 2026-10-11 (pedido do Alex): valor de gasto/renda que ELE digitou pode ser corrigido pela
    # IA ("errei o valor"). Banco (bank_transactions) e construtora continuam fora - nem
    # estao nesta lista, e a construtora nem e guardada aqui.
    "expenses": ("category", "description", "amount"),
    "incomes": ("category", "description", "amount"),
}

# Colunas que voltam quando o Desfazer restaura uma tarefa apagada pela IA.
TAREFA_RESTAURAVEL = (
    "id", "title", "source_text", "due_at", "due_date", "completed_at", "created_at", "hora",
    "depende_do_tempo", "esforco", "local", "recorrente_origem_id",
)
SUBTAREFA_RESTAURAVEL = ("title", "completed_at", "position")

ENTIDADES_DESFAZIVEIS = (
    "edicao", "tarefa_apagada",
    "tarefa", "gasto", "renda", "lembrete", "meta", "evento",
    # Fase 6 (US-E7): modulos ligados aos cards
    "habito", "habito_marcacao", "projeto", "projeto_etapa", "etapa_concluida", "viagem", "hidratacao", "treino",
    # 2026-10-13: refeicao registrada pela foto do prato (refeicoes.py)
    "refeicao",
    # 2026-10-14: voo agendado pelo chat (card voo_agendado) - so apaga se ainda sem horas
    "voo_agendado",
)


def criar_acao_desfazer(conn, itens: list[dict]) -> str | None:
    """Fase 6 (US-E5): grava os itens exatos que um card pode desfazer e
    devolve o token (vai na action `desfazer` do card). So guarda chaves
    conhecidas - nada vindo de texto da IA."""
    limpos = []
    for item in itens or []:
        if not isinstance(item, dict) or item.get("entidade") not in ENTIDADES_DESFAZIVEIS:
            continue
        limpo = {"entidade": item["entidade"]}
        if isinstance(item.get("id"), int):
            limpo["id"] = item["id"]
        if isinstance(item.get("uid"), str) and item["uid"]:
            limpo["uid"] = item["uid"]
        if isinstance(item.get("conta_id"), int) and isinstance(item.get("delta"), (int, float)):
            limpo["conta_id"] = item["conta_id"]
            limpo["delta"] = float(item["delta"])
        # habito_marcacao (US-E7): o dia e o estado que a acao deixou - o
        # desfazer volta pro estado oposto naquele dia exato.
        if item["entidade"] == "habito_marcacao":
            dia = item.get("data")
            if not (isinstance(dia, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", dia)) or not isinstance(item.get("feito"), bool):
                continue
            limpo["data"] = dia
            limpo["feito"] = item["feito"]
        if item["entidade"] == "edicao":
            tabela, antes = item.get("tabela"), item.get("antes")
            colunas = EDICAO_COLUNAS.get(tabela)
            if not colunas or not isinstance(antes, dict) or not antes:
                continue
            valores = {}
            for col, val in antes.items():
                if col not in colunas:
                    continue
                if val is not None and not isinstance(val, (str, int, float)):
                    continue
                valores[col] = val[:500] if isinstance(val, str) else val
            if not valores:
                continue
            limpo["tabela"] = tabela
            limpo["antes"] = valores
        if item["entidade"] == "tarefa_apagada":
            linha = item.get("linha")
            if not isinstance(linha, dict) or linha.get("id") != item.get("id"):
                continue
            limpo["linha"] = {
                c: (v[:2000] if isinstance(v, str) else v)
                for c, v in linha.items()
                if c in TAREFA_RESTAURAVEL and (v is None or isinstance(v, (str, int, float)))
            }
            subs = item.get("subtarefas")
            if isinstance(subs, list):
                limpo["subtarefas"] = [
                    {c: (s[c][:500] if isinstance(s.get(c), str) else s.get(c)) for c in SUBTAREFA_RESTAURAVEL
                     if s.get(c) is None or isinstance(s.get(c), (str, int, float))}
                    for s in subs[:100] if isinstance(s, dict) and isinstance(s.get("title"), str)
                ]
            pulo = item.get("pulo")
            if isinstance(pulo, dict) and isinstance(pulo.get("origem_id"), int) and isinstance(pulo.get("data"), str) \
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", pulo["data"]):
                limpo["pulo"] = {"origem_id": pulo["origem_id"], "data": pulo["data"]}
        if "id" in limpo or "uid" in limpo:
            limpos.append(limpo)
    if not limpos:
        return None
    token = secrets.token_urlsafe(16)
    conn.execute(
        "INSERT INTO acoes_desfazer (token, itens_json) VALUES (?, ?)",
        (token, criptografia.criptografar(json.dumps(limpos))),
    )
    conn.commit()
    return token


def obter_acao_desfazer(conn, token: str) -> dict | None:
    row = conn.execute("SELECT * FROM acoes_desfazer WHERE token = ?", (token,)).fetchone()
    if not row:
        return None
    try:
        itens = json.loads(criptografia.descriptografar(row["itens_json"]) or "[]")
    except (TypeError, ValueError):
        itens = []
    return {"token": row["token"], "itens": itens if isinstance(itens, list) else [], "desfeito_em": row["desfeito_em"]}


def tokens_desfeitos(conn, tokens: list[str]) -> set[str]:
    tokens = [t for t in tokens if isinstance(t, str)]
    if not tokens:
        return set()
    marcadores = ",".join("?" for _ in tokens)
    rows = conn.execute(
        f"SELECT token FROM acoes_desfazer WHERE desfeito_em IS NOT NULL AND token IN ({marcadores})", tokens
    ).fetchall()
    return {r["token"] for r in rows}


def reverter_ajuste_saldo(conn, bank_account_id: int, delta: float) -> None:
    """Desfaz um ajuste otimista de saldo (ajustar_saldo_conta) SEM commit -
    quem chama (desfazer) faz tudo numa transacao so."""
    row = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (bank_account_id,)).fetchone()
    if row is None or row["saldo"] is None:
        return
    atual = _dnum(row["saldo"], float)
    if atual is None:
        return
    conn.execute("UPDATE bank_accounts SET saldo = ? WHERE id = ?", (_cnum(atual - delta), bank_account_id))


def cards_de_mensagem_chat(mensagem: dict) -> list:
    """Le de volta os cards gravados por salvar_mensagem_chat - lista vazia
    em mensagem antiga (sem cards) ou dado ilegivel (nunca derruba o
    historico por causa de um card)."""
    bruto = mensagem.get("cards_json")
    if not bruto:
        return []
    try:
        cards = json.loads(criptografia.descriptografar(bruto) or "[]")
    except (TypeError, ValueError):
        return []
    return cards if isinstance(cards, list) else []


def list_chat_mensagens(conn, limit: int = 20) -> list[dict]:
    """Mais recentes primeiro (pra LIMIT pegar as ultimas N) - quem usa pra
    montar historico de conversa deve inverter a ordem antes de mandar pra IA."""
    rows = conn.execute(
        "SELECT * FROM chat_mensagens ORDER BY criado_em DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def create_lembrete(conn, titulo: str, data_str: str, recorrente: bool = False) -> int:
    cur = conn.execute(
        "INSERT INTO lembretes (titulo, data, recorrente) VALUES (?, ?, ?)",
        (titulo, data_str, int(recorrente)),
    )
    conn.commit()
    return cur.lastrowid


def list_lembretes(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM lembretes ORDER BY data").fetchall()
    return [dict(r) for r in rows]


def definir_despertar_lembrete(conn, lembrete_id: int, ativo: bool) -> bool:
    """Fase 6 (US-E3): liga/desliga o push no horario do lembrete."""
    cur = conn.execute("UPDATE lembretes SET despertar = ? WHERE id = ?", (int(bool(ativo)), lembrete_id))
    conn.commit()
    return cur.rowcount > 0


ESTILOS_TAREFA = ("date", "balada", "documentos", "presente")


def extras_tarefa(conn, task_id: int) -> dict:
    row = conn.execute("SELECT extras FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row or not row["extras"]:
        return {}
    try:
        dados = json.loads(row["extras"])
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def salvar_extras_tarefa(conn, task_id: int, extras: dict) -> bool:
    cur = conn.execute(
        "UPDATE tasks SET extras = ? WHERE id = ?", (json.dumps(extras, ensure_ascii=False), task_id)
    )
    conn.commit()
    return cur.rowcount > 0


def reabrir_tarefa(conn, task_id: int) -> bool:
    """Fase 6 (US-E3): par do complete_task - tira o completed_at."""
    cur = conn.execute("UPDATE tasks SET completed_at = NULL WHERE id = ?", (task_id,))
    conn.commit()
    return cur.rowcount > 0


def delete_lembrete(conn, lembrete_id: int):
    conn.execute("DELETE FROM lembretes WHERE id = ?", (lembrete_id,))
    conn.commit()


def create_medicamento(
    conn, nome: str, dosagem: str | None, horario: str, recorrencia: str, tarefa_modelo_id: int
) -> int:
    """A tarefa recorrente que de verdade aparece na agenda/dispara aviso ja
    foi criada antes disso (ver _criar_medicamento em app.py, que orquestra
    as duas insercoes) - esta tabela e so metadado estruturado (nome/dosagem
    separados, pra exibir bonito e listar "que remedios estao ativos" sem
    precisar fazer parsing do titulo da tarefa)."""
    cur = conn.execute(
        "INSERT INTO medicamentos (nome, dosagem, horario, recorrencia, tarefa_modelo_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            criptografia.criptografar(nome),
            criptografia.criptografar(dosagem),
            criptografia.criptografar(horario),
            recorrencia,
            tarefa_modelo_id,
        ),
    )
    conn.commit()
    return cur.lastrowid


def _descriptografar_medicamento(d: dict) -> dict:
    d["nome"] = criptografia.descriptografar(d["nome"])
    d["dosagem"] = criptografia.descriptografar(d["dosagem"])
    d["horario"] = criptografia.descriptografar(d["horario"])
    return d


def list_medicamentos_ativos(conn) -> list[dict]:
    """`horario` e criptografado, entao a ordenacao (que antes era `ORDER BY
    horario` no SQL) agora acontece em Python depois de descriptografar -
    texto cifrado nao ordena como a hora original."""
    rows = conn.execute("SELECT * FROM medicamentos WHERE ativo = 1").fetchall()
    medicamentos = [_descriptografar_medicamento(dict(r)) for r in rows]
    medicamentos.sort(key=lambda m: m["horario"] or "")
    return medicamentos


def delete_medicamento(conn, medicamento_id: int):
    """Apaga o medicamento E a tarefa-modelo recorrente vinculada - sem
    depender de ON DELETE CASCADE (nao ligado neste banco, ver delete_cotacao
    pro mesmo padrao), apaga explicitamente os dois. As instancias ja
    materializadas em dias anteriores ficam no historico normalmente (nao
    somem - so param de gerar novas a partir de hoje)."""
    row = conn.execute(
        "SELECT tarefa_modelo_id FROM medicamentos WHERE id = ?", (medicamento_id,)
    ).fetchone()
    if row:
        conn.execute("DELETE FROM tasks WHERE id = ?", (row["tarefa_modelo_id"],))
    conn.execute("DELETE FROM medicamentos WHERE id = ?", (medicamento_id,))
    conn.commit()


def get_medicamento_ativo(conn, medicamento_id: int) -> dict | None:
    """Um medicamento ativo (descriptografado) ou None - id fora do intervalo do
    SQLite (inteiro gigante vindo da URL) tambem vira None, nunca erro."""
    try:
        row = conn.execute(
            "SELECT * FROM medicamentos WHERE id = ? AND ativo = 1", (medicamento_id,)
        ).fetchone()
    except OverflowError:
        return None
    return _descriptografar_medicamento(dict(row)) if row else None


def instancia_do_dia_do_medicamento(conn, med: dict, dia: str) -> dict | None:
    """R4 ("Tomei"): a instancia de `dia` da tarefa recorrente "Tomar X" - e ela que
    de verdade representa a dose do dia (a agenda, o lembrete e a previa da noite ja
    contam "tomado" = instancia concluida), entao o botao Tomei usa a mesma fonte em
    vez de uma tabela paralela. None se o remedio nao cai nesse dia."""
    row = conn.execute(
        "SELECT id, completed_at FROM tasks WHERE recorrente_origem_id = ? AND due_date = ? ORDER BY id LIMIT 1",
        (med["tarefa_modelo_id"], dia),
    ).fetchone()
    return dict(row) if row else None


def utc_para_hora_local(texto_utc: str | None) -> str | None:
    """"AAAA-MM-DD HH:MM:SS" em UTC (datetime('now') do SQLite) -> "HH:MM" no fuso do processo."""
    if not texto_utc:
        return None
    try:
        dt = datetime.strptime(texto_utc[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%H:%M")
    except ValueError:
        return None


def registrar_hidratacao(conn, data: str) -> int:
    """+1 copo no dia informado - conta simples, sem limite de meta (o Alex so
    quer parar de esquecer de beber agua, nao gerenciar meta em ml)."""
    conn.execute("INSERT INTO hidratacao_registros (data) VALUES (?)", (data,))
    conn.commit()
    return contar_hidratacao_dia(conn, data)


def contar_hidratacao_dia(conn, data: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM hidratacao_registros WHERE data = ?", (data,)
    ).fetchone()
    return row["total"]


def create_medida_corporal(conn, tipo: str, valor: float, unidade: str, data: str) -> int:
    """`valor` (o numero em si - peso, cintura, etc) e criptografado; `tipo`
    fica em texto plano porque e uma categoria (usado em WHERE tipo = ? abaixo
    - criptografado, deixaria de dar pra filtrar), assim como `data` (usada
    em ORDER BY)."""
    cur = conn.execute(
        "INSERT INTO medidas_corporais (tipo, valor, unidade, data) VALUES (?, ?, ?, ?)",
        (tipo, _cnum(valor), unidade, data),
    )
    conn.commit()
    return cur.lastrowid


def _descriptografar_medida(d: dict) -> dict:
    d["valor"] = _dnum(d["valor"], float)
    return d


_DESCRIPTOGRAFADORES_POR_TABELA = {
    "bank_accounts": _descriptografar_conta,
    "bank_transactions": _descriptografar_transacao,
    "saude_dados": _descriptografar_saude,
    "medidas_corporais": _descriptografar_medida,
    "medicamentos": _descriptografar_medicamento,
}


def descriptografar_linhas_export(nome_tabela: str, linhas: list[dict]) -> list[dict]:
    """Usado pelo export completo (JSON/CSV, ver app.py) pra devolver as
    tabelas do escopo de criptografia (docs/SEGURANCA.md) legiveis, em vez do
    token cifrado cru - achado de revisao: sem isso, o export prometido como
    "legivel/pra planilha" saia com saldo/sono/etc ilegivel. E o MESMO nivel
    de acesso que a tela ja mostra descriptografado pra quem esta logado
    (rota atras de sessao), nao um vazamento novo - o backup .db bruto
    (sqlite3.backup) continua cifrado de proposito, documentado em
    docs/SEGURANCA.md. Tabela fora do escopo volta sem alteracao."""
    descriptografador = _DESCRIPTOGRAFADORES_POR_TABELA.get(nome_tabela)
    if not descriptografador:
        return linhas
    return [descriptografador(linha) for linha in linhas]


def list_medidas_corporais(conn, tipo: str | None = None, limite: int = 50) -> list[dict]:
    if tipo:
        rows = conn.execute(
            "SELECT * FROM medidas_corporais WHERE tipo = ? ORDER BY data DESC, id DESC LIMIT ?",
            (tipo, limite),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM medidas_corporais ORDER BY data DESC, id DESC LIMIT ?", (limite,)
        ).fetchall()
    return [_descriptografar_medida(dict(r)) for r in rows]


def delete_medida_corporal(conn, medida_id: int):
    conn.execute("DELETE FROM medidas_corporais WHERE id = ?", (medida_id,))
    conn.commit()


def create_income(
    conn, amount: float, category: str, description: str | None = None, source_text: str | None = None
) -> int:
    cur = conn.execute(
        "INSERT INTO incomes (amount, category, description, source_text) VALUES (?, ?, ?, ?)",
        (amount, category, description, source_text),
    )
    conn.commit()
    return cur.lastrowid


def list_incomes(conn, limit: int = 200) -> list[dict]:
    """Mais recente primeiro - 'id DESC' desempata quando duas entradas caem
    no mesmo segundo (created_at so tem resolucao de segundo)."""
    rows = conn.execute(
        "SELECT * FROM incomes ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def total_incomes_mes(conn, ano_mes: str) -> float:
    """Soma das entradas do mes (ano_mes no formato 'AAAA-MM')."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM incomes WHERE strftime('%Y-%m', created_at) = ?",
        (ano_mes,),
    ).fetchone()
    return row["total"]


def total_gastos_mes(conn, ano_mes: str, tipo: str = "real") -> float:
    """Soma dos gastos do mes por tipo ('real' ou 'planejado', ano_mes no
    formato 'AAAA-MM') - todas as categorias juntas."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE tipo = ? AND strftime('%Y-%m', created_at) = ?",
        (tipo, ano_mes),
    ).fetchone()
    return row["total"]


def total_gastos_bancarios_mes(conn, ano_mes: str) -> float:
    """Soma das saidas (valor negativo, convencao ja usada no resto do app)
    do extrato bancario sincronizado no mes - complementa total_gastos_mes,
    que so ve o que foi digitado no chat. `data` filtra no SQL normalmente
    (nao e campo criptografado), mas a soma de `valor` (criptografado) e
    feita em Python depois de descriptografar cada linha."""
    rows = conn.execute(
        "SELECT valor FROM bank_transactions WHERE strftime('%Y-%m', data) = ?", (ano_mes,)
    ).fetchall()
    total = 0.0
    for r in rows:
        valor = _dnum(r["valor"], float)
        if valor is not None and valor < 0:
            total += -valor
    return total


def _saida_pelo_sinal(transacao: dict) -> float | None:
    """Regra das somas (total_gastos_bancarios_mes, _gastos_reais_unificados):
    saida = valor negativo."""
    valor = transacao.get("valor")
    return -valor if valor is not None and valor < 0 else None


def data_local_do_gasto(created_at) -> str | None:
    """`created_at` de expenses e UTC (DEFAULT datetime('now')) - o gasto das 22h
    de Brasilia ja e "amanha" em UTC. Pra parear com a `data` do extrato (dia
    local da compra) converte pro dia local; so data (legado/teste) fica como esta."""
    texto = (created_at or "").strip()
    if len(texto) < 10:
        return None
    if len(texto) == 10:
        return texto
    try:
        utc = datetime.fromisoformat(texto).replace(tzinfo=timezone.utc)
    except ValueError:
        return texto[:10]
    return utc.astimezone().date().isoformat()


def gastos_chat_repetidos_no_banco(conn, regra_saida=None, so_dias=None) -> set[int]:
    """Ids de expenses (tipo 'real', digitados no chat/nota fiscal) que TAMBEM
    vieram no extrato do banco: mesmo valor (ao centavo) no mesmo dia. Decisao do
    Alex (2026-10-15): "se for igual junta" - conta uma vez so, fica a linha do
    banco (descricao estavel, que e o que a deteccao de assinatura agrupa) e o do
    chat sai das somas/listas. Nada e apagado. Pareamento 1 pra 1: dois cafes de
    R$ 5 no chat e um no banco = um continua.

    `regra_saida(transacao) -> valor positivo | None` decide o que e saida no
    extrato (padrao: valor negativo, a regra das somas; a aba Financas passa a
    regra do tipo_operacao). So decifra as transacoes dos dias que tem gasto no
    chat - nunca o extrato inteiro (custo do Fernet, ver Fase vel/A2a); `so_dias`
    (datas locais 'AAAA-MM-DD') limita ainda mais, pra paginacao. O pareamento e
    por dia, entao limitar a dias inteiros da o mesmo resultado que olhar tudo."""
    regra_saida = regra_saida or _saida_pelo_sinal
    por_dia: dict[str, list[tuple[int, int]]] = {}
    for r in conn.execute(
        "SELECT id, amount, created_at FROM expenses WHERE tipo = 'real' ORDER BY id"
    ).fetchall():
        dia = data_local_do_gasto(r["created_at"])
        if dia is None or r["amount"] is None or (so_dias is not None and dia not in so_dias):
            continue
        por_dia.setdefault(dia, []).append((r["id"], round(abs(r["amount"]) * 100)))
    if not por_dia:
        return set()

    banco_por_dia: dict[str, list[int]] = {}
    dias = list(por_dia)
    for i in range(0, len(dias), 500):
        lote = dias[i:i + 500]
        marcadores = ",".join("?" * len(lote))
        for r in conn.execute(
            f"SELECT * FROM bank_transactions WHERE substr(data, 1, 10) IN ({marcadores})", lote
        ).fetchall():
            t = _descriptografar_transacao(dict(r))
            saida = regra_saida(t)
            if saida:
                banco_por_dia.setdefault(t["data"][:10], []).append(round(abs(saida) * 100))

    repetidos = set()
    for dia, gastos_do_dia in por_dia.items():
        sobrando = banco_por_dia.get(dia, [])
        for expense_id, centavos in gastos_do_dia:
            if centavos in sobrando:
                sobrando.remove(centavos)
                repetidos.add(expense_id)
    return repetidos


def total_gasto_real_mes(conn, ano_mes: str) -> float:
    """Gasto real do mes = chat + extrato, sem contar duas vezes o que esta nos
    dois (gastos_chat_repetidos_no_banco). O repetido sai do lado do chat, no mes
    em que o chat o somou."""
    repetidos = gastos_chat_repetidos_no_banco(conn)
    descontar = 0.0
    if repetidos:
        # ids inteiros vindos do proprio banco - literal em vez de "?" pra nao bater no limite de parametros
        lista = ",".join(str(int(i)) for i in repetidos)
        descontar = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) AS t FROM expenses WHERE strftime('%Y-%m', created_at) = ? "
            f"AND id IN ({lista})",
            (ano_mes,),
        ).fetchone()["t"]
    return total_gastos_mes(conn, ano_mes, "real") + total_gastos_bancarios_mes(conn, ano_mes) - descontar


def definir_orcamento(conn, categoria: str, valor_limite: float) -> None:
    conn.execute(
        "INSERT INTO orcamentos (categoria, valor_limite) VALUES (?, ?) "
        "ON CONFLICT(categoria) DO UPDATE SET valor_limite = excluded.valor_limite",
        (categoria, valor_limite),
    )
    conn.commit()


def obter_orcamento(conn, categoria: str) -> float | None:
    row = conn.execute(
        "SELECT valor_limite FROM orcamentos WHERE categoria = ?", (categoria,)
    ).fetchone()
    return row["valor_limite"] if row else None


def list_orcamentos(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM orcamentos ORDER BY categoria").fetchall()]


def apagar_orcamento(conn, categoria: str) -> None:
    conn.execute("DELETE FROM orcamentos WHERE categoria = ?", (categoria,))
    conn.commit()


def gasto_mes_por_categoria(conn, categoria: str, ano_mes: str) -> float:
    """Soma dos gastos REAIS do mes numa categoria (ano_mes no formato 'AAAA-MM')."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE category = ? AND tipo = 'real' AND strftime('%Y-%m', created_at) = ?",
        (categoria, ano_mes),
    ).fetchone()
    return row["total"]


def definir_apelido_gasto(conn, descricao_normalizada: str, valor: float, apelido: str) -> None:
    """Guarda o que uma cobranca generica (ex: "apple.com/bill") realmente e
    - "descricao_normalizada" + "valor" juntos formam a chave porque duas
    assinaturas diferentes da mesma empresa (ex: iCloud e Apple Music) tem
    o mesmo texto de cobranca mas valores diferentes; sem o valor na chave,
    uma sobrescreveria o apelido da outra."""
    conn.execute(
        "INSERT INTO apelidos_gasto (descricao_normalizada, valor, apelido) VALUES (?, ?, ?) "
        "ON CONFLICT(descricao_normalizada, valor) DO UPDATE SET apelido = excluded.apelido",
        (descricao_normalizada, valor, apelido),
    )
    conn.commit()


def list_apelidos_gasto(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM apelidos_gasto").fetchall()]


def create_espera(conn, quem: str, sobre: str, source_text: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO esperas (quem, sobre, source_text) VALUES (?, ?, ?)",
        (quem, sobre, source_text),
    )
    conn.commit()
    return cur.lastrowid


def list_esperas_pendentes(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM esperas WHERE resolvido_em IS NULL ORDER BY criado_em"
    ).fetchall()
    return [dict(r) for r in rows]


def resolver_espera(conn, espera_id: int) -> bool:
    """Marca como resolvida (chegou a resposta, ou nao precisa mais esperar).
    Retorna False se o id nao existir ou ja estiver resolvido - pra rota
    devolver 404 em vez de um 'ok' silencioso que nao fez nada."""
    cur = conn.execute(
        "UPDATE esperas SET resolvido_em = datetime('now') WHERE id = ? AND resolvido_em IS NULL",
        (espera_id,),
    )
    if cur.rowcount > 0:
        fechar_interacao_aprendizado(conn, "espera_parada", espera_id)
    conn.commit()
    return cur.rowcount > 0


def apagar_espera(conn, espera_id: int):
    conn.execute("DELETE FROM esperas WHERE id = ?", (espera_id,))
    conn.commit()


def marcar_espera_importante(conn, espera_id: int, importante: bool) -> bool:
    cur = conn.execute(
        "UPDATE esperas SET importante = ? WHERE id = ?", (1 if importante else 0, espera_id)
    )
    conn.commit()
    return cur.rowcount > 0


def espera_pendente_por_quem_aproximado(conn, quem: str) -> dict | None:
    """Acha uma espera ainda em aberto cujo 'quem' bate (sem diferenciar
    maiusculas/minusculas, por substring nos dois sentidos) - mesmo padrao de
    cotacao_por_titulo_aproximado, pra 'o fornecedor de ferro ja respondeu'
    achar a espera certa sem repetir o nome palavra por palavra. Mais de uma
    batendo, pega a mais antiga (a que esta esperando ha mais tempo)."""
    quem_norm = (quem or "").strip().lower()
    if not quem_norm:
        return None
    rows = conn.execute(
        "SELECT * FROM esperas WHERE resolvido_em IS NULL ORDER BY criado_em"
    ).fetchall()
    for r in rows:
        existente = r["quem"].strip().lower()
        if quem_norm in existente or existente in quem_norm:
            return dict(r)
    return None


def registrar_interacao_aprendizado(conn, tipo: str, referencia_id: int = 0) -> int:
    """Abre um registro de interacao (ex: cutucada de tarefa_parada mandada
    agora) pra depois medir quanto tempo levou ate ser resolvida - ver
    fechar_interacao_aprendizado. Chamado no momento em que a notificacao
    e' de fato ENVIADA (nao quando a condicao so passa a ser verdadeira),
    pra latencia_horas medir o efeito real da cutucada."""
    cur = conn.execute(
        "INSERT INTO interacoes_aprendizado (tipo, referencia_id) VALUES (?, ?)",
        (tipo, referencia_id),
    )
    conn.commit()
    return cur.lastrowid


def fechar_interacao_aprendizado(conn, tipo: str, referencia_id: int = 0) -> bool:
    """Fecha a interacao aberta mais recente desse tipo/referencia (se
    houver) registrando quanto tempo levou desde que foi disparada -
    julianday() calcula a diferenca em dias com precisao de fracao, *24
    converte pra horas. E' um no-op seguro quando nao ha interacao aberta
    (o caso comum: toda tarefa concluida chama isso, mas so as que
    passaram por uma cutucada de tarefa_parada tem algo pra fechar)."""
    cur = conn.execute(
        """UPDATE interacoes_aprendizado
           SET resolvido_em = datetime('now'),
               latencia_horas = (julianday('now') - julianday(disparado_em)) * 24
           WHERE id = (
               SELECT id FROM interacoes_aprendizado
               WHERE tipo = ? AND referencia_id = ? AND resolvido_em IS NULL
               ORDER BY disparado_em DESC LIMIT 1
           )""",
        (tipo, referencia_id),
    )
    conn.commit()
    return cur.rowcount > 0


def latencias_resolvidas(conn, tipo: str) -> list[float]:
    rows = conn.execute(
        "SELECT latencia_horas FROM interacoes_aprendizado "
        "WHERE tipo = ? AND latencia_horas IS NOT NULL",
        (tipo,),
    ).fetchall()
    return [r["latencia_horas"] for r in rows]


def complete_task(conn, task_id: int) -> None:
    conn.execute("UPDATE tasks SET completed_at = datetime('now') WHERE id = ?", (task_id,))
    fechar_interacao_aprendizado(conn, "tarefa_parada", task_id)
    conn.commit()


def definir_esforco_tarefa(conn, task_id: int, esforco: str) -> bool:
    """Fase 5 (US-C7): marca o esforco estimado (baixa/media/alta) de uma
    tarefa - usado por vida.tarefas_compativeis_com_energia pra sugerir
    tarefa de acordo com o nivel de energia atual."""
    cur = conn.execute("UPDATE tasks SET esforco = ? WHERE id = ?", (esforco, task_id))
    conn.commit()
    return cur.rowcount > 0


def reclassificar_tarefa_para_gasto(
    conn, task_id: int, valor: float, categoria: str | None = None, tipo: str = "real"
) -> tuple[int, int] | None:
    """Corrige uma captura que a IA classificou errado como tarefa quando na
    verdade era gasto: move a linha de tasks pra expenses preservando
    titulo/source_text/data de criacao (transacao unica - ou os dois lados
    acontecem, ou nenhum). "valor" (e opcionalmente "tipo") vem de quem esta
    corrigindo na hora, porque o texto original pode nao ter um valor
    monetario claro pra IA ter adivinhado sozinha. Subtarefas vinculadas nao
    fazem sentido pra um gasto, entao sao apagadas junto - o numero apagado
    volta no retorno pra UI poder avisar. None se a tarefa nao existir."""
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return None
    subtasks_removidas = conn.execute(
        "SELECT COUNT(*) AS n FROM subtasks WHERE task_id = ?", (task_id,)
    ).fetchone()["n"]
    conn.execute("DELETE FROM subtasks WHERE task_id = ?", (task_id,))
    cur = conn.execute(
        "INSERT INTO expenses (amount, category, description, source_text, tipo, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (valor, categoria or "outros", task["title"], task["source_text"], tipo, task["created_at"]),
    )
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return cur.lastrowid, subtasks_removidas


def reclassificar_gasto_para_tarefa(
    conn,
    expense_id: int,
    due_at: str | None = None,
    due_date: str | None = None,
    hora: str | None = None,
) -> int | None:
    """Corrige uma captura que a IA classificou errado como gasto quando na
    verdade era tarefa: move a linha de expenses pra tasks preservando a
    descricao (vira titulo), source_text e a data de criacao original -
    transacao unica, mesmo espirito de reclassificar_tarefa_para_gasto.
    "tipo" (real/planejado) do gasto nao tem equivalente em tarefa, entao e
    simplesmente descartado. None se o gasto nao existir."""
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        return None
    titulo = expense["description"] or expense["source_text"] or "gasto reclassificado"
    cur = conn.execute(
        "INSERT INTO tasks (title, due_at, due_date, hora, source_text, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (titulo, due_at, due_date, hora, expense["source_text"], expense["created_at"]),
    )
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    return cur.lastrowid


def atualizar_categoria_gasto(conn, expense_id: int, categoria: str) -> bool:
    """Corrige so a categoria de um gasto ja lancado, sem mexer em mais
    nada - usado tanto por uma edicao manual quanto (indiretamente, via
    registrar_correcao_classificacao) pelo aprendizado leve de classificacao."""
    cur = conn.execute("UPDATE expenses SET category = ? WHERE id = ?", (categoria, expense_id))
    conn.commit()
    return cur.rowcount > 0


# tipo_certo (correcoes_classificacao, Fase 4) -> acao de intent equivalente
# (ACOES_INTENT, Fase 5) - so cobre o que tem correspondencia direta hoje;
# "meta" nao tem acao equivalente na lista fechada do classificador de intent
# ainda, entao correcao pra "meta" nao gera padrao (fica de fora por
# interpretacao explicita, nao e um esquecimento).
_TIPO_CERTO_PARA_ACAO_INTENT = {"tarefa": "registrar_tarefa", "gasto": "registrar_gasto"}


def registrar_correcao_classificacao(
    conn,
    texto_original: str,
    tipo_errado: str | None,
    categoria_errada: str | None,
    tipo_certo: str,
    categoria_certa: str | None,
) -> None:
    """Grava uma correcao manual de classificacao (tarefa <-> gasto errado, ou
    categoria de gasto errada) pra aprendizado.correcao_semelhante usar depois
    numa captura nova parecida - mesmo espirito de apelidos_gasto (guardar o
    que o Alex corrigiu, sem IA/rede neural nenhuma aqui), so que aqui o
    "erro" pode ser o TIPO inteiro da captura, nao so um apelido generico.

    Fase 5 (US-A4): a mesma correcao tambem vira um padrao de confianca alta
    em padroes_intent_aprendidos (via _TIPO_CERTO_PARA_ACAO_INTENT) - o Alex
    corrigindo manualmente uma vez ja e sinal forte o bastante pra nao exigir
    repetir o erro LIMIAR_CONFIRMACOES_PADRAO_INTENT vezes (ver
    aprendizado.confirmar_padrao_intent, mesmo espirito com
    forcar_confianca_alta=True)."""
    conn.execute(
        "INSERT INTO correcoes_classificacao "
        "(texto_original, tipo_errado, categoria_errada, tipo_certo, categoria_certa) "
        "VALUES (?, ?, ?, ?, ?)",
        (texto_original, tipo_errado, categoria_errada, tipo_certo, categoria_certa),
    )
    acao_intent = _TIPO_CERTO_PARA_ACAO_INTENT.get(tipo_certo)
    if acao_intent:
        normalizado = normalizar_texto_intent(texto_original)
        if normalizado:
            parametros = {"categoria": categoria_certa} if categoria_certa else {}
            upsert_padrao_intent(
                conn, normalizado, acao_intent, parametros, LIMIAR_CONFIRMACOES_PADRAO_INTENT
            )
    conn.commit()


def list_correcoes_classificacao(conn) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM correcoes_classificacao ORDER BY criado_em DESC"
        ).fetchall()
    ]


# ---- Padrao aprendido de intent (Fase 5, US-A3/US-A4) ---------------------
# Normalizacao e o limiar moram aqui (nao em aprendizado.py, que importa este
# modulo) pra registrar_correcao_classificacao poder alimentar o padrao
# direto, sem import circular. aprendizado.py reexporta os dois pra manter a
# API publica estavel (normalizar_texto_intent/LIMIAR_CONFIRMACOES_PADRAO_INTENT
# continuam acessiveis por la tambem) - a decisao de QUANDO confiar num
# padrao (padrao_intent_confiavel/confirmar_padrao_intent) fica em
# aprendizado.py, que e quem concentra essa logica no projeto.
LIMIAR_CONFIRMACOES_PADRAO_INTENT = 3

_PONTUACAO_BORDA_INTENT = " .!?,;:"


def normalizar_texto_intent(texto: str) -> str:
    """minusculo + espacos colapsados + pontuacao solta na borda removida -
    o suficiente pra "Gastei 50 no mercado" e "gastei 50 no mercado."
    baterem como o mesmo padrao, sem virar um match semantico."""
    if not texto or not isinstance(texto, str):
        return ""
    normalizado = re.sub(r"\s+", " ", texto.strip().lower())
    return normalizado.strip(_PONTUACAO_BORDA_INTENT)


def buscar_padrao_intent(conn, texto_normalizado: str) -> dict | None:
    """CRUD puro (sem decisao de confianca - isso e aprendizado.padrao_intent_confiavel)."""
    row = conn.execute(
        "SELECT * FROM padroes_intent_aprendidos WHERE texto_normalizado = ?", (texto_normalizado,)
    ).fetchone()
    if not row:
        return None
    padrao = dict(row)
    padrao["parametros"] = json.loads(padrao["parametros"])
    return padrao


def upsert_padrao_intent(
    conn, texto_normalizado: str, acao: str, parametros: dict, vezes_confirmado: int
) -> None:
    conn.execute(
        "INSERT INTO padroes_intent_aprendidos "
        "(texto_normalizado, acao, parametros, vezes_confirmado, ultima_vez) "
        "VALUES (?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(texto_normalizado) DO UPDATE SET "
        "acao = excluded.acao, parametros = excluded.parametros, "
        "vezes_confirmado = excluded.vezes_confirmado, ultima_vez = excluded.ultima_vez",
        (texto_normalizado, acao, json.dumps(parametros or {}, ensure_ascii=False), vezes_confirmado),
    )
    conn.commit()


def marcar_ou_criar_feito(
    conn, titulo: str, source_text: str | None = None, hoje: date | None = None
) -> dict:
    """Catch-up de fim do dia: o Alex conta algo que ja fez mas nunca tinha
    registrado em tempo real. Se bater (por aproximacao, mesmo padrao de
    cotacao_por_titulo_aproximado) com uma tarefa pendente existente, marca
    ela como concluida (fecha o loop de aprendizado tambem, via
    complete_task); senao cria uma tarefa nova ja nascendo concluida - um
    registro honesto de trabalho feito fora do que foi planejado."""
    hoje = hoje or date.today()
    titulo_norm = (titulo or "").strip().lower()
    if not titulo_norm:
        return {"ok": False, "erro": "titulo vazio"}
    candidatas = conn.execute(
        "SELECT id, title FROM tasks WHERE completed_at IS NULL "
        "AND (due_date IS NULL OR due_date <= ?)",
        (hoje.isoformat(),),
    ).fetchall()
    for c in candidatas:
        existente = c["title"].strip().lower()
        if titulo_norm in existente or existente in titulo_norm:
            complete_task(conn, c["id"])
            return {"ok": True, "acao": "marcada_concluida", "titulo": c["title"], "task_id": c["id"]}
    cur = conn.execute(
        "INSERT INTO tasks (title, due_date, source_text, completed_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (titulo, hoje.isoformat(), source_text),
    )
    conn.commit()
    return {"ok": True, "acao": "registrada_e_concluida", "titulo": titulo, "task_id": cur.lastrowid}


def registrar_atividade(conn, dia_iso: str) -> None:
    conn.execute("INSERT OR IGNORE INTO atividade_dias (dia) VALUES (?)", (dia_iso,))
    conn.commit()


def list_dias_ativos(conn) -> set[str]:
    rows = conn.execute("SELECT dia FROM atividade_dias").fetchall()
    return {r["dia"] for r in rows}


def create_voo(
    conn, data_str: str, destino: str, origem: str | None = None, horas: float | None = None,
    observacao: str | None = None, hora: str | None = None, escalas: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO voos (data, origem, destino, horas, observacao, hora, escalas) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (data_str, origem, destino, horas, observacao, hora, escalas),
    )
    conn.commit()
    return cur.lastrowid


def list_voos(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM voos ORDER BY data DESC").fetchall()
    return [dict(r) for r in rows]


def delete_voo(conn, voo_id: int):
    conn.execute("DELETE FROM voos WHERE id = ?", (voo_id,))
    conn.commit()


def criar_uber_pedido(conn, origem: str | None, destino: str, disparar_em: str) -> int:
    cur = conn.execute(
        "INSERT INTO uber_pedidos (origem, destino, disparar_em) VALUES (?, ?, ?)",
        (origem, destino, disparar_em),
    )
    conn.commit()
    return cur.lastrowid


def uber_pedidos_para_disparar(conn, agora_iso: str) -> list[dict]:
    """Pedidos ainda 'aguardando' (contagem regressiva rodando) cujo horario
    de disparar a estimativa ja chegou."""
    rows = conn.execute(
        "SELECT * FROM uber_pedidos WHERE status = 'aguardando' AND disparar_em <= ?",
        (agora_iso,),
    ).fetchall()
    return [dict(r) for r in rows]


def uber_pedido(conn, pedido_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM uber_pedidos WHERE id = ?", (pedido_id,)).fetchone()
    return dict(row) if row else None


def uber_pedidos_aguardando_confirmacao(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM uber_pedidos WHERE status = 'aguardando_confirmacao' ORDER BY criado_em"
    ).fetchall()
    return [dict(r) for r in rows]


_UBER_PEDIDO_COLUNAS = {
    "origem_lat", "origem_lng", "destino_lat", "destino_lng", "product_id",
    "status", "fare_id", "preco_texto", "request_id", "erro",
}


def atualizar_uber_pedido(conn, pedido_id: int, **campos):
    """Atualiza so os campos passados. As chaves de 'campos' sao sempre
    literais escritas no proprio codigo (nunca vem de input externo), mas
    a whitelist evita que um nome de campo errado vire SQL invalido calado."""
    invalidos = set(campos) - _UBER_PEDIDO_COLUNAS
    if invalidos:
        raise ValueError(f"campo(s) invalido(s) pra uber_pedidos: {invalidos}")
    if not campos:
        return
    colunas = ", ".join(f"{c} = ?" for c in campos)
    conn.execute(
        f"UPDATE uber_pedidos SET {colunas} WHERE id = ?", (*campos.values(), pedido_id)
    )
    conn.commit()


def criar_cotacao(conn, titulo: str) -> int:
    cur = conn.execute("INSERT INTO cotacoes (titulo) VALUES (?)", (titulo,))
    conn.commit()
    return cur.lastrowid


def cotacao_por_titulo_aproximado(conn, titulo: str) -> dict | None:
    """Acha uma cotacao existente cujo titulo bate (sem diferenciar
    maiusculas/minusculas, por substring nos dois sentidos) - pra
    'fornecedor tal, R$500, pra cotacao de ferro' cair na mesma cotacao de
    'abrir cotacao de ferro' mesmo sem repetir o titulo palavra por
    palavra. Se houver mais de uma, pega a mais recente."""
    titulo_norm = (titulo or "").strip().lower()
    if not titulo_norm:
        return None
    rows = conn.execute("SELECT * FROM cotacoes ORDER BY criado_em DESC").fetchall()
    for r in rows:
        existente = r["titulo"].strip().lower()
        if titulo_norm in existente or existente in titulo_norm:
            return dict(r)
    return None


def get_cotacao(conn, cotacao_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM cotacoes WHERE id = ?", (cotacao_id,)).fetchone()
    return dict(row) if row else None


def list_cotacoes(conn) -> list[dict]:
    """Cada cotacao com quantos itens tem e o menor valor entre eles (NULL
    se nenhum item ainda tem valor) - o essencial pra listar sem precisar
    buscar os itens de cada uma."""
    rows = conn.execute(
        """SELECT c.*, COUNT(i.id) AS total_itens, MIN(i.valor) AS menor_valor
           FROM cotacoes c LEFT JOIN cotacoes_itens i ON i.cotacao_id = c.id
           GROUP BY c.id ORDER BY c.criado_em DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def criar_item_cotacao(
    conn,
    cotacao_id: int,
    fornecedor: str | None,
    valor: float | None,
    prazo_texto: str | None = None,
    observacao: str | None = None,
    origem: str = "texto",
) -> int:
    cur = conn.execute(
        """INSERT INTO cotacoes_itens (cotacao_id, fornecedor, valor, prazo_texto, observacao, origem)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (cotacao_id, fornecedor, valor, prazo_texto, observacao, origem),
    )
    conn.commit()
    return cur.lastrowid


def list_itens_cotacao(conn, cotacao_id: int) -> list[dict]:
    """Itens da cotacao, mais barato primeiro - itens sem valor (ex: PDF que
    nao deu pra extrair) ficam por ultimo, nao desaparecem."""
    rows = conn.execute(
        """SELECT * FROM cotacoes_itens WHERE cotacao_id = ?
           ORDER BY (valor IS NULL), valor, criado_em""",
        (cotacao_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_cotacao(conn, cotacao_id: int):
    """Apaga a cotacao e os itens dela - sem depender de ON DELETE CASCADE
    do SQLite (que so funciona com PRAGMA foreign_keys ligado, nao ligado
    aqui), apaga os itens primeiro explicitamente."""
    conn.execute("DELETE FROM cotacoes_itens WHERE cotacao_id = ?", (cotacao_id,))
    conn.execute("DELETE FROM cotacoes WHERE id = ?", (cotacao_id,))
    conn.commit()


def delete_item_cotacao(conn, item_id: int):
    conn.execute("DELETE FROM cotacoes_itens WHERE id = ?", (item_id,))
    conn.commit()


# ---- Assistente de vida (BRIEFING.md, Fase 1) ----

def salvar_checkin(conn, data: str, campos: dict) -> dict:
    """Grava so os campos informados (energia/sono/humor, 1-3) - cada toque
    do Alex salva na hora, sem precisar responder os tres de uma vez."""
    validos = {k: v for k, v in campos.items() if k in vida.CAMPOS_CHECKIN and v is not None}
    # INSERT OR IGNORE + UPDATE (em vez de checar antes e inserir): dois toques
    # rapidos no primeiro check-in do dia nao colidem na chave primaria.
    conn.execute("INSERT OR IGNORE INTO checkins (data) VALUES (?)", (data,))
    if validos:
        sets = ", ".join(f"{k} = ?" for k in validos)
        conn.execute(
            f"UPDATE checkins SET {sets}, atualizado_em = datetime('now') WHERE data = ?",
            (*validos.values(), data),
        )
    conn.commit()
    return get_checkin(conn, data)


def get_checkin(conn, data: str) -> dict | None:
    row = conn.execute("SELECT * FROM checkins WHERE data = ?", (data,)).fetchone()
    return dict(row) if row else None


def list_checkins(conn, desde: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM checkins WHERE data >= ? ORDER BY data", (desde,)).fetchall()
    return [dict(r) for r in rows]


def list_rotina_itens(conn, momento: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM rotina_itens WHERE momento = ? AND ativo = 1 ORDER BY posicao, id", (momento,)
    ).fetchall()
    return [dict(r) for r in rows]


def create_rotina_item(conn, momento: str, texto: str) -> int:
    posicao = conn.execute(
        "SELECT COALESCE(MAX(posicao), -1) + 1 AS p FROM rotina_itens WHERE momento = ?", (momento,)
    ).fetchone()["p"]
    cur = conn.execute(
        "INSERT INTO rotina_itens (momento, texto, posicao) VALUES (?, ?, ?)", (momento, texto, posicao)
    )
    conn.commit()
    return cur.lastrowid


def delete_rotina_item(conn, item_id: int):
    conn.execute("DELETE FROM rotina_marcacoes WHERE item_id = ?", (item_id,))
    conn.execute("DELETE FROM rotina_itens WHERE id = ?", (item_id,))
    conn.commit()


def rotina_marcadas(conn, data: str) -> set[int]:
    rows = conn.execute("SELECT item_id FROM rotina_marcacoes WHERE data = ?", (data,)).fetchall()
    return {r["item_id"] for r in rows}


def alternar_rotina_item(conn, data: str, item_id: int) -> bool:
    """Marca/desmarca o item no dia. Devolve o estado novo (True = feito)."""
    ja = conn.execute(
        "SELECT 1 FROM rotina_marcacoes WHERE data = ? AND item_id = ?", (data, item_id)
    ).fetchone()
    if ja:
        conn.execute("DELETE FROM rotina_marcacoes WHERE data = ? AND item_id = ?", (data, item_id))
    else:
        conn.execute("INSERT INTO rotina_marcacoes (data, item_id) VALUES (?, ?)", (data, item_id))
    conn.commit()
    return not ja


def get_essencial(conn, data: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM essencial_dia WHERE data = ? ORDER BY posicao", (data,)
    ).fetchall()
    return [dict(r) for r in rows]


def salvar_essencial(conn, data: str, escolhas: list[tuple[int, str | None]]):
    conn.execute("DELETE FROM essencial_dia WHERE data = ?", (data,))
    for posicao, (task_id, motivo) in enumerate(escolhas):
        conn.execute(
            "INSERT INTO essencial_dia (data, task_id, posicao, motivo) VALUES (?, ?, ?, ?)",
            (data, task_id, posicao, motivo),
        )
    conn.commit()


def create_conta_pessoal(conn, nome: str, dia_vencimento: int, valor: float | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO contas_pessoais (nome, dia_vencimento, valor) VALUES (?, ?, ?)",
        (nome, dia_vencimento, valor),
    )
    conn.commit()
    return cur.lastrowid


def list_contas_pessoais(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM contas_pessoais WHERE ativo = 1 ORDER BY dia_vencimento, nome"
    ).fetchall()
    return _criado_local(rows)


def delete_conta_pessoal(conn, conta_id: int):
    conn.execute("DELETE FROM contas_pessoais_pagas WHERE conta_id = ?", (conta_id,))
    conn.execute("DELETE FROM contas_pessoais WHERE id = ?", (conta_id,))
    conn.commit()


def marcar_conta_paga(conn, conta_id: int, vencimento: str):
    conn.execute(
        "INSERT OR IGNORE INTO contas_pessoais_pagas (conta_id, vencimento) VALUES (?, ?)",
        (conta_id, vencimento),
    )
    conn.commit()


def conta_paga(conn, conta_id: int, vencimento: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM contas_pessoais_pagas WHERE conta_id = ? AND vencimento = ?",
            (conta_id, vencimento),
        ).fetchone()
    )


def responder_assinatura(
    conn, descricao_normalizada: str, ano_mes: str, descricao: str, valor: float | None, resposta: str
):
    conn.execute(
        """INSERT INTO assinaturas_revisao (descricao_normalizada, ano_mes, descricao, valor, resposta)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(descricao_normalizada, ano_mes) DO UPDATE SET
             resposta = excluded.resposta, respondido_em = datetime('now')""",
        (descricao_normalizada, ano_mes, descricao, valor, resposta),
    )
    conn.commit()


def respostas_assinaturas(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM assinaturas_revisao").fetchall()
    return [dict(r) for r in rows]


def create_pessoa(conn, nome: str, frequencia_dias: int = 14) -> int:
    cur = conn.execute(
        "INSERT INTO pessoas (nome, frequencia_dias) VALUES (?, ?)", (nome, frequencia_dias)
    )
    conn.commit()
    return cur.lastrowid


def list_pessoas(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM pessoas ORDER BY nome").fetchall()
    return [dict(r) for r in rows]


def delete_pessoa(conn, pessoa_id: int):
    """Conversas antigas ficam (so perdem o vinculo) - historico nao some."""
    conn.execute("UPDATE conversas SET pessoa_id = NULL WHERE pessoa_id = ?", (pessoa_id,))
    conn.execute("DELETE FROM pessoas WHERE id = ?", (pessoa_id,))
    conn.commit()


def registrar_conversa(
    conn, pessoa_id: int | None, pessoa_nome: str, sobre: str | None, data: str, source_text: str | None = None
) -> int:
    cur = conn.execute(
        "INSERT INTO conversas (pessoa_id, pessoa_nome, sobre, data, source_text) VALUES (?, ?, ?, ?, ?)",
        (pessoa_id, pessoa_nome, sobre, data, source_text),
    )
    if pessoa_id is not None:
        conn.execute(
            """UPDATE pessoas SET ultimo_contato = ?
               WHERE id = ? AND (ultimo_contato IS NULL OR ultimo_contato < ?)""",
            (data, pessoa_id, data),
        )
    conn.commit()
    return cur.lastrowid


def list_conversas(conn, pessoa_id: int | None = None, limite: int = 20) -> list[dict]:
    if pessoa_id is None:
        rows = conn.execute(
            "SELECT * FROM conversas ORDER BY data DESC, id DESC LIMIT ?", (limite,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversas WHERE pessoa_id = ? ORDER BY data DESC, id DESC LIMIT ?",
            (pessoa_id, limite),
        ).fetchall()
    return [dict(r) for r in rows]


def create_decisao(conn, pergunta: str, analise_json: str) -> int:
    cur = conn.execute(
        "INSERT INTO decisoes (pergunta, analise_json) VALUES (?, ?)", (pergunta, analise_json)
    )
    conn.commit()
    return cur.lastrowid


def list_decisoes(conn, limite: int = 10) -> list[dict]:
    rows = conn.execute("SELECT * FROM decisoes ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    return [dict(r) for r in rows]


# ---- Assistente de vida (BRIEFING.md, Fase 2) ----

def salvar_ficha_treino(conn, grupo: str, exercicios: str) -> int:
    """Uma ficha por grupo (comparado sem acento/caixa) - salvar de novo o
    mesmo grupo substitui os exercicios em vez de duplicar."""
    alvo = vida.normalizar_nome(grupo)
    for f in list_fichas_treino(conn):
        if vida.normalizar_nome(f["grupo"]) == alvo:
            conn.execute(
                "UPDATE treino_fichas SET grupo = ?, exercicios = ?, atualizado_em = datetime('now') WHERE id = ?",
                (grupo, exercicios, f["id"]),
            )
            conn.commit()
            return f["id"]
    cur = conn.execute("INSERT INTO treino_fichas (grupo, exercicios) VALUES (?, ?)", (grupo, exercicios))
    conn.commit()
    return cur.lastrowid


def list_fichas_treino(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM treino_fichas ORDER BY grupo").fetchall()
    return [dict(r) for r in rows]


def delete_ficha_treino(conn, ficha_id: int):
    conn.execute("DELETE FROM treino_fichas WHERE id = ?", (ficha_id,))
    conn.commit()


def registrar_treino(
    conn, data: str, grupo: str | None, duracao_min: int | None, nota: str | None, origem: str | None = None
) -> int:
    cur = conn.execute(
        "INSERT INTO treinos (data, grupo, duracao_min, nota, origem) VALUES (?, ?, ?, ?, ?)",
        (data, grupo, duracao_min, nota, origem),
    )
    conn.commit()
    return cur.lastrowid


def get_ficha_treino(conn, ficha_id: int) -> dict | None:
    try:
        row = conn.execute("SELECT * FROM treino_fichas WHERE id = ?", (ficha_id,)).fetchone()
    except OverflowError:
        return None
    return dict(row) if row else None


def treinos_do_dia_por_grupo(conn, data: str) -> dict[str, str]:
    """{grupo normalizado: criado_em UTC do primeiro treino do dia} - base do
    "Feito hoje" das fichas (treino registrado pelo chat ou pelo botao conta igual)."""
    rows = conn.execute(
        "SELECT grupo, criado_em FROM treinos WHERE data = ? AND grupo IS NOT NULL ORDER BY id", (data,)
    ).fetchall()
    feitos: dict[str, str] = {}
    for r in rows:
        feitos.setdefault(vida.normalizar_nome(r["grupo"]), r["criado_em"])
    return feitos


def desfazer_treinos_do_dia_por_grupo(conn, data: str, grupo: str) -> int:
    alvo = vida.normalizar_nome(grupo)
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id, grupo FROM treinos WHERE data = ? AND grupo IS NOT NULL AND origem = 'botao'", (data,)
        ).fetchall()
        if vida.normalizar_nome(r["grupo"]) == alvo
    ]
    for i in ids:
        conn.execute("DELETE FROM treinos WHERE id = ?", (i,))
    conn.commit()
    return len(ids)


def list_treinos(conn, limite: int = 20) -> list[dict]:
    rows = conn.execute("SELECT * FROM treinos ORDER BY data DESC, id DESC LIMIT ?", (limite,)).fetchall()
    return [dict(r) for r in rows]


def create_viagem(
    conn,
    destino: str,
    data_ida: str,
    data_volta: str | None,
    motivo: str | None,
    internacional: bool = False,
) -> int:
    cur = conn.execute(
        "INSERT INTO viagens (destino, data_ida, data_volta, motivo, internacional) VALUES (?, ?, ?, ?, ?)",
        (destino, data_ida, data_volta, motivo, int(bool(internacional))),
    )
    conn.commit()
    return cur.lastrowid


def definir_numero_voo_viagem(conn, viagem_id: int, numero_voo: str | None) -> bool:
    """US-F12: o Alex preenche o numero do voo depois de comprar a passagem -
    None/"" apaga (volta pro modo so-manual)."""
    cur = conn.execute("UPDATE viagens SET numero_voo = ? WHERE id = ?", (numero_voo or None, viagem_id))
    conn.commit()
    return cur.rowcount > 0


def list_viagens_futuras(conn, hoje: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM viagens WHERE COALESCE(data_volta, data_ida) >= ? ORDER BY data_ida", (hoje,)
    ).fetchall()
    return [dict(r) for r in rows]


def delete_viagem(conn, viagem_id: int):
    conn.execute("DELETE FROM viagem_itens WHERE viagem_id = ?", (viagem_id,))
    conn.execute("DELETE FROM viagens WHERE id = ?", (viagem_id,))
    conn.commit()


def substituir_itens_viagem(conn, viagem_id: int, itens: list[str]):
    conn.execute("DELETE FROM viagem_itens WHERE viagem_id = ?", (viagem_id,))
    for texto in itens:
        conn.execute("INSERT INTO viagem_itens (viagem_id, texto) VALUES (?, ?)", (viagem_id, texto))
    conn.commit()


def list_itens_viagem(conn, viagem_id: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM viagem_itens WHERE viagem_id = ? ORDER BY id", (viagem_id,)).fetchall()
    return [dict(r) for r in rows]


def alternar_item_viagem(conn, item_id: int) -> bool | None:
    row = conn.execute("SELECT feito FROM viagem_itens WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return None
    novo = 0 if row["feito"] else 1
    conn.execute("UPDATE viagem_itens SET feito = ? WHERE id = ?", (novo, item_id))
    conn.commit()
    return bool(novo)


def create_lugar(conn, nome: str, cidade: str | None, tipo: str | None, nota: str | None) -> int:
    cur = conn.execute(
        "INSERT INTO lugares (nome, cidade, tipo, nota) VALUES (?, ?, ?, ?)", (nome, cidade, tipo, nota)
    )
    conn.commit()
    return cur.lastrowid


def list_lugares(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM lugares ORDER BY cidade, nome").fetchall()
    return [dict(r) for r in rows]


def delete_lugar(conn, lugar_id: int):
    conn.execute("DELETE FROM lugares WHERE id = ?", (lugar_id,))
    conn.commit()


def salvar_geocode_lugar(
    conn, lugar_id: int, lat: float | None, lng: float | None, status: str, tentar_depois: str | None = None
) -> None:
    """US-F13: grava o resultado (ou a falta dele) do geocode Nominatim -
    'status' e 'ok'/'nao_encontrado'/'recusado' (definitivos) ou 'erro'
    (temporario, com `tentar_depois` = instante UTC "AAAA-MM-DD HH:MM:SS" a
    partir do qual pode consultar de novo - revisao da Fase 6). Politica de
    uso do Nominatim: nunca repetir a mesma consulta que ja respondeu."""
    conn.execute(
        "UPDATE lugares SET lat = ?, lng = ?, geocode_status = ?, geocode_tentar_depois = ? WHERE id = ?",
        (lat, lng, status, tentar_depois, lugar_id),
    )
    conn.commit()


def lugares_sem_geocode(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM lugares WHERE geocode_status IS NULL ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def proximo_lugar_para_geocodificar(conn, agora_utc: str) -> dict | None:
    """O UNICO lugar que um GET /api/lugares pode geocodificar agora: nunca
    consultado (status NULL) ou com falha temporaria cuja espera ja passou
    (`agora_utc` no mesmo formato de geocode_tentar_depois)."""
    row = conn.execute(
        "SELECT * FROM lugares WHERE geocode_status IS NULL "
        "OR (geocode_status = 'erro' AND (geocode_tentar_depois IS NULL OR geocode_tentar_depois <= ?)) "
        "ORDER BY id LIMIT 1",
        (agora_utc,),
    ).fetchone()
    return dict(row) if row else None


# ---- Fase 6 F3 (US-F12): cache de status de voo ----------------------------

def obter_status_voo_cache(conn, numero_voo: str, data: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM voo_status_cache WHERE numero_voo = ? AND data = ?", (numero_voo, data)
    ).fetchone()
    return dict(row) if row else None


def salvar_status_voo_cache(conn, numero_voo: str, data: str, resposta_json: str) -> None:
    conn.execute(
        """
        INSERT INTO voo_status_cache (numero_voo, data, resposta_json, buscado_em)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(numero_voo, data) DO UPDATE SET
            resposta_json = excluded.resposta_json,
            buscado_em = excluded.buscado_em
        """,
        (numero_voo, data, resposta_json),
    )
    conn.commit()


# ---- Faixa M4 (uso diario): cache do resumo de IA do dia -------------------
# Mesmo espirito do cache de voo acima - uma linha por dia (`data`), guarda a
# "impressao" (fingerprint do que era relevante) junto com a resposta, pra
# `app.py` decidir se ainda vale ou se precisa chamar a IA de novo.

def obter_resumo_dia_cache(conn, data: str) -> dict | None:
    row = conn.execute("SELECT * FROM resumo_dia_cache WHERE data = ?", (data,)).fetchone()
    return dict(row) if row else None


def salvar_resumo_dia_cache(conn, data: str, impressao: str, resposta_json: str) -> None:
    conn.execute(
        """
        INSERT INTO resumo_dia_cache (data, impressao, resposta_json, gerado_em)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(data) DO UPDATE SET
            impressao = excluded.impressao,
            resposta_json = excluded.resposta_json,
            gerado_em = excluded.gerado_em
        """,
        (data, impressao, resposta_json),
    )
    conn.commit()


def create_manutencao(
    conn,
    tipo: str,
    item: str,
    intervalo_meses: int | None,
    ultima_vez: str | None,
    km: float | None = None,
    proxima_em_km: float | None = None,
    proxima_em_data: str | None = None,
) -> int:
    """Secao unica de manutencao (Fase 6, US-E1a - ver comentario da tabela
    em init_db). intervalo_meses grava 0 quando None (tipo='carro', onde o
    campo nao se aplica - a coluna e NOT NULL por historico; nunca lido
    pra esse tipo, ver _manutencoes_com_status)."""
    cur = conn.execute(
        """INSERT INTO manutencoes (tipo, item, intervalo_meses, ultima_vez, km, proxima_em_km, proxima_em_data)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tipo, item, intervalo_meses if intervalo_meses is not None else 0, ultima_vez, km, proxima_em_km, proxima_em_data),
    )
    conn.commit()
    return cur.lastrowid


def list_manutencoes(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM manutencoes ORDER BY criado_em DESC, id DESC").fetchall()
    return _criado_local(rows)


def get_manutencao(conn, manutencao_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM manutencoes WHERE id = ?", (manutencao_id,)).fetchone()
    return dict(row) if row else None


def marcar_manutencao_feita(conn, manutencao_id: int, data: str) -> bool:
    cur = conn.execute("UPDATE manutencoes SET ultima_vez = ? WHERE id = ?", (data, manutencao_id))
    conn.commit()
    return cur.rowcount > 0


def delete_manutencao(conn, manutencao_id: int):
    conn.execute("DELETE FROM manutencoes WHERE id = ?", (manutencao_id,))
    conn.commit()


def km_atual_veiculo(conn) -> float | None:
    """Maior km ja registrado em qualquer manutencao de carro - usado como
    "km atual do veiculo" pra decidir se uma manutencao por km esta perto do
    limite (nao ha odometro conectado, so o que foi digitado manualmente a
    cada manutencao)."""
    row = conn.execute("SELECT MAX(km) AS km_max FROM manutencoes WHERE tipo = 'carro'").fetchone()
    return row["km_max"]


# ---- Fase 5 (Grupo C): ideias de presente ----

def create_ideia_presente(conn, pessoa: str, ideia: str, ocasiao: str | None) -> int:
    cur = conn.execute(
        "INSERT INTO ideias_presente (pessoa, ideia, ocasiao) VALUES (?, ?, ?)",
        (pessoa, ideia, ocasiao),
    )
    conn.commit()
    return cur.lastrowid


def list_ideias_presente(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM ideias_presente ORDER BY comprado, pessoa COLLATE NOCASE, criado_em DESC"
    ).fetchall()
    return _criado_local(rows)


def alternar_ideia_presente_comprada(conn, ideia_id: int) -> bool | None:
    row = conn.execute("SELECT comprado FROM ideias_presente WHERE id = ?", (ideia_id,)).fetchone()
    if not row:
        return None
    novo = 0 if row["comprado"] else 1
    conn.execute("UPDATE ideias_presente SET comprado = ? WHERE id = ?", (novo, ideia_id))
    conn.commit()
    return bool(novo)


def delete_ideia_presente(conn, ideia_id: int):
    conn.execute("DELETE FROM ideias_presente WHERE id = ?", (ideia_id,))
    conn.commit()


# ---- Fase 5 (Grupo C): cofre de garantia ----

def create_garantia(
    conn, produto: str, data_compra: str, prazo_garantia_meses: int, nota_fiscal_anexo: str | None
) -> int:
    cur = conn.execute(
        """INSERT INTO garantias (produto, data_compra, prazo_garantia_meses, nota_fiscal_anexo)
           VALUES (?, ?, ?, ?)""",
        (produto, data_compra, prazo_garantia_meses, nota_fiscal_anexo),
    )
    conn.commit()
    return cur.lastrowid


def list_garantias(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM garantias ORDER BY data_compra DESC").fetchall()
    return _criado_local(rows)


def get_garantia(conn, garantia_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM garantias WHERE id = ?", (garantia_id,)).fetchone()
    return dict(row) if row else None


def delete_garantia(conn, garantia_id: int):
    conn.execute("DELETE FROM garantias WHERE id = ?", (garantia_id,))
    conn.commit()


def marcar_garantia_notificada(conn, garantia_id: int):
    conn.execute("UPDATE garantias SET notificado = 1 WHERE id = ?", (garantia_id,))
    conn.commit()


def adicionar_compra(conn, item: str) -> tuple[int, bool]:
    """Nao duplica item que ja esta na lista (pendente). Devolve (id, novo)."""
    item = vida.limpar_item_compra(item) or item
    normalizado = vida.normalizar_item_compra(item)
    existente = conn.execute(
        "SELECT id FROM compras WHERE item_normalizado = ? AND comprado_em IS NULL", (normalizado,)
    ).fetchone()
    if existente:
        return existente["id"], False
    cur = conn.execute("INSERT INTO compras (item, item_normalizado) VALUES (?, ?)", (item, normalizado))
    conn.commit()
    return cur.lastrowid, True


def list_compras_pendentes(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM compras WHERE comprado_em IS NULL ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def marcar_comprado(conn, compra_id: int):
    conn.execute("UPDATE compras SET comprado_em = datetime('now') WHERE id = ?", (compra_id,))
    conn.commit()


def delete_compra(conn, compra_id: int):
    conn.execute("DELETE FROM compras WHERE id = ?", (compra_id,))
    conn.commit()


def create_responder(conn, quem: str, sobre: str | None) -> int:
    cur = conn.execute("INSERT INTO responder (quem, sobre) VALUES (?, ?)", (quem, sobre))
    conn.commit()
    return cur.lastrowid


def list_responder_pendentes(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM responder WHERE respondido_em IS NULL ORDER BY criado_em").fetchall()
    return _criado_local(rows)


def marcar_respondido(conn, responder_id: int):
    conn.execute("UPDATE responder SET respondido_em = datetime('now') WHERE id = ?", (responder_id,))
    conn.commit()



# ---- Assistente de vida (BRIEFING.md, Fase 3) ----

def create_aprender(conn, tema: str, nota: str | None) -> int:
    cur = conn.execute("INSERT INTO aprender (tema, nota) VALUES (?, ?)", (tema, nota))
    conn.commit()
    return cur.lastrowid


def list_aprender(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM aprender WHERE concluido_em IS NULL ORDER BY COALESCE(ultima_vez, substr(criado_em, 1, 10))"
    ).fetchall()
    return _criado_local(rows)


def marcar_aprender(conn, aprender_id: int, campo: str, data: str) -> bool:
    if campo not in ("ultima_vez", "concluido_em"):
        raise ValueError(campo)
    cur = conn.execute(f"UPDATE aprender SET {campo} = ? WHERE id = ?", (data, aprender_id))
    conn.commit()
    return cur.rowcount > 0


def delete_aprender(conn, aprender_id: int):
    conn.execute("DELETE FROM aprender WHERE id = ?", (aprender_id,))
    conn.commit()


def create_salvo(conn, url: str, titulo: str | None, resumo: str | None) -> int:
    cur = conn.execute("INSERT INTO salvos (url, titulo, resumo) VALUES (?, ?, ?)", (url, titulo, resumo))
    conn.commit()
    return cur.lastrowid


def list_salvos(conn, limite: int = 30) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM salvos ORDER BY (lido_em IS NOT NULL), id DESC LIMIT ?", (limite,)
    ).fetchall()
    return [dict(r) for r in rows]


def marcar_salvo_lido(conn, salvo_id: int) -> bool:
    cur = conn.execute("UPDATE salvos SET lido_em = datetime('now') WHERE id = ?", (salvo_id,))
    conn.commit()
    return cur.rowcount > 0


def delete_salvo(conn, salvo_id: int):
    conn.execute("DELETE FROM salvos WHERE id = ?", (salvo_id,))
    conn.commit()


def registrar_evento_app(conn, app: str, evento: str, em: str):
    conn.execute("INSERT INTO app_eventos (app, evento, em) VALUES (?, ?, ?)", (app, evento, em))
    # so os ultimos 60 dias interessam (resumo semanal / 30 dias na tela)
    conn.execute("DELETE FROM app_eventos WHERE em < datetime(?, '-60 days')", (em,))
    conn.commit()


def list_eventos_app(conn, desde: str) -> list[dict]:
    rows = conn.execute("SELECT app, evento, em FROM app_eventos WHERE em >= ? ORDER BY em", (desde,)).fetchall()
    return [dict(r) for r in rows]


# ---- Fase 6, US-E12: modulo Habitos (novo, separado da Rotina guiada) -----

def create_habito(
    conn,
    nome: str,
    meta: str | None,
    frequencia_tipo: str,
    dias_semana: str | None,
    vezes_por_semana: int | None,
    horario: str | None,
) -> int:
    cur = conn.execute(
        """INSERT INTO habitos (nome, meta, frequencia_tipo, dias_semana, vezes_por_semana, horario)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (nome, meta, frequencia_tipo, dias_semana, vezes_por_semana, horario),
    )
    conn.commit()
    return cur.lastrowid


def list_habitos(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM habitos WHERE ativo = 1 ORDER BY criado_em, id").fetchall()
    return [dict(r) for r in rows]


def get_habito(conn, habito_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM habitos WHERE id = ? AND ativo = 1", (habito_id,)).fetchone()
    return dict(row) if row else None


def buscar_habito_por_nome(conn, nome: str) -> dict | None:
    """Igual buscar_conta_por_nome: correspondencia parcial sem diferenciar
    maiusculas, pra chat tool (marcar_habito) aceitar texto livre em vez de
    exigir o id exato."""
    nome = (nome or "").strip()
    if not nome:
        return None
    row = conn.execute(
        "SELECT * FROM habitos WHERE ativo = 1 AND nome LIKE ? ORDER BY id ASC LIMIT 1", (f"%{nome}%",)
    ).fetchone()
    return dict(row) if row else None


def delete_habito(conn, habito_id: int):
    conn.execute("DELETE FROM habito_marcacoes WHERE habito_id = ?", (habito_id,))
    conn.execute("DELETE FROM habitos WHERE id = ?", (habito_id,))
    conn.commit()


def habito_marcado(conn, data: str, habito_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM habito_marcacoes WHERE data = ? AND habito_id = ?", (data, habito_id)
    ).fetchone()
    return row is not None


def alternar_habito_dia(conn, data: str, habito_id: int) -> bool:
    """Marca/desmarca o habito no dia informado - devolve o novo estado
    (True = ficou marcado). Mesmo padrao de alternar_rotina_item."""
    if habito_marcado(conn, data, habito_id):
        conn.execute("DELETE FROM habito_marcacoes WHERE data = ? AND habito_id = ?", (data, habito_id))
        conn.commit()
        return False
    conn.execute("INSERT INTO habito_marcacoes (data, habito_id) VALUES (?, ?)", (data, habito_id))
    conn.commit()
    return True


def marcacoes_habito_no_periodo(conn, habito_id: int, inicio: str, fim: str) -> set[str]:
    """Datas (AAAA-MM-DD) marcadas de um habito entre inicio e fim (inclusive) -
    usado tanto pros 7 circulos da semana quanto pra contar quantas vezes na
    semana atual (frequencia 'n_vezes_semana')."""
    rows = conn.execute(
        "SELECT data FROM habito_marcacoes WHERE habito_id = ? AND data BETWEEN ? AND ?",
        (habito_id, inicio, fim),
    ).fetchall()
    return {r["data"] for r in rows}


# ---- Fase 6, US-E13: modulo Projetos generico ------------------------------

def create_projeto(conn, nome: str, prazo_final: str | None) -> int:
    cur = conn.execute("INSERT INTO projetos (nome, prazo_final) VALUES (?, ?)", (nome, prazo_final))
    conn.commit()
    return cur.lastrowid


def list_projetos(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM projetos ORDER BY criado_em, id").fetchall()
    return [dict(r) for r in rows]


def get_projeto(conn, projeto_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
    return dict(row) if row else None


def buscar_projeto_por_nome(conn, nome: str) -> dict | None:
    nome = (nome or "").strip()
    if not nome:
        return None
    row = conn.execute(
        "SELECT * FROM projetos WHERE nome LIKE ? ORDER BY id ASC LIMIT 1", (f"%{nome}%",)
    ).fetchone()
    return dict(row) if row else None


def delete_projeto(conn, projeto_id: int):
    conn.execute("DELETE FROM projeto_etapas WHERE projeto_id = ?", (projeto_id,))
    conn.execute("DELETE FROM projetos WHERE id = ?", (projeto_id,))
    conn.commit()


def _tocar_projeto(conn, projeto_id: int):
    conn.execute("UPDATE projetos SET atualizado_em = datetime('now') WHERE id = ?", (projeto_id,))


def definir_status_projeto(conn, projeto_id: int, status: str) -> bool:
    if status not in ("no_rumo", "atrasado", "pausado"):
        return False
    cur = conn.execute("UPDATE projetos SET status = ? WHERE id = ?", (status, projeto_id))
    _tocar_projeto(conn, projeto_id)
    conn.commit()
    return cur.rowcount > 0


def adicionar_etapa_projeto(conn, projeto_id: int, texto: str, data_prevista: str | None) -> int | None:
    if not get_projeto(conn, projeto_id):
        return None
    posicao = conn.execute(
        "SELECT COALESCE(MAX(posicao), -1) + 1 AS p FROM projeto_etapas WHERE projeto_id = ?", (projeto_id,)
    ).fetchone()["p"]
    cur = conn.execute(
        "INSERT INTO projeto_etapas (projeto_id, texto, data_prevista, posicao) VALUES (?, ?, ?, ?)",
        (projeto_id, texto, data_prevista, posicao),
    )
    _tocar_projeto(conn, projeto_id)
    conn.commit()
    return cur.lastrowid


def list_etapas_projeto(conn, projeto_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM projeto_etapas WHERE projeto_id = ? ORDER BY posicao, id", (projeto_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def concluir_etapa_projeto(conn, etapa_id: int) -> int | None:
    """Marca a etapa como feita (idempotente) - devolve o projeto_id pra quem
    chamou poder recalcular %/status, ou None se a etapa nao existe."""
    row = conn.execute("SELECT projeto_id FROM projeto_etapas WHERE id = ?", (etapa_id,)).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE projeto_etapas SET feita = 1, feita_em = COALESCE(feita_em, datetime('now')) WHERE id = ?",
        (etapa_id,),
    )
    _tocar_projeto(conn, row["projeto_id"])
    conn.commit()
    return row["projeto_id"]


def apagar_etapa_projeto(conn, etapa_id: int) -> int | None:
    row = conn.execute("SELECT projeto_id FROM projeto_etapas WHERE id = ?", (etapa_id,)).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM projeto_etapas WHERE id = ?", (etapa_id,))
    _tocar_projeto(conn, row["projeto_id"])
    conn.commit()
    return row["projeto_id"]


# ---- Fase 6, US-E14: eventos criados pelo painel no calendario "Painel" ---

def registrar_evento_criado(conn, uid: str, titulo: str, inicio: str, fim: str):
    conn.execute(
        "INSERT INTO eventos_criados (uid, titulo, inicio, fim) VALUES (?, ?, ?, ?)", (uid, titulo, inicio, fim)
    )
    conn.commit()


def evento_criado_pelo_painel(conn, uid: str) -> dict | None:
    row = conn.execute("SELECT * FROM eventos_criados WHERE uid = ?", (uid,)).fetchone()
    return dict(row) if row else None


def esquecer_evento_criado(conn, uid: str):
    conn.execute("DELETE FROM eventos_criados WHERE uid = ?", (uid,))
    conn.commit()


def list_eventos_criados(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM eventos_criados ORDER BY inicio").fetchall()
    return [dict(r) for r in rows]


# ---- Fase 6, US-E15: limite manual do cartao -------------------------------

def definir_limite_conta(conn, bank_account_id: int, limite: float | None) -> bool:
    cur = conn.execute("UPDATE bank_accounts SET limite = ? WHERE id = ?", (limite, bank_account_id))
    conn.commit()
    return cur.rowcount > 0


def gasto_mes_conta(conn, bank_account_id: int, ano_mes: str) -> float:
    """Mesma logica de total_gastos_bancarios_mes, mas filtrada numa unica
    conta/cartao - usado pra calcular a fracao do limite (US-E15). 'ciclo do
    cartao' aqui e simplificado pro mes-calendario (strftime %Y-%m) porque o
    app nao conhece a data de fechamento real da fatura de cada cartao."""
    rows = conn.execute(
        "SELECT valor FROM bank_transactions WHERE bank_account_id = ? AND strftime('%Y-%m', data) = ?",
        (bank_account_id, ano_mes),
    ).fetchall()
    total = 0.0
    for r in rows:
        valor = _dnum(r["valor"], float)
        if valor is not None and valor < 0:
            total += -valor
    return total
