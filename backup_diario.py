"""Backup automatico DIARIO do banco do painel.

Complementa o backup semanal que ja existe em `app.py`
(`rodar_backup_automatico_semanal`, que tambem manda copia pro Telegram):
aquele cobre "o disco morreu", este cobre "apaguei/estraguei algo ontem" com
um ponto de restauracao por dia. Os dois convivem na mesma pasta sem se
atrapalhar - o semanal usa `painel-backup-<data>_<hora>.db` e rotaciona so os
seus; este usa `painel-AAAA-MM-DD.db` e rotaciona so os seus.

Mesma tecnica do export manual (`rotas/backup.py`): `sqlite3.Connection.backup()`,
que tira um snapshot consistente mesmo com o banco em uso (nunca copia crua
do arquivo, que podia pegar uma escrita pela metade).

Resiliente de proposito: qualquer erro (disco cheio, permissao, banco travado)
e logado e engolido - um backup que falha nunca derruba o app nem o
agendador. O arquivo e escrito num temporario e so entao trocado pelo
definitivo, entao um backup que falha no meio nunca destroi o do mesmo dia
que ja estava bom.

Quando roda (ver `app.iniciar_scheduler`): todo dia as 3h30 e, ao subir o app,
se o ultimo backup diario tiver mais de 24 h (o PC do Alex nem sempre esta
ligado as 3h30)."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import db

log = logging.getLogger("app")

BACKUP_DIARIO_MANTER = 14  # duas semanas de pontos de restauracao diarios
IDADE_MAXIMA_HORAS = 24
_PADRAO_NOME = re.compile(r"^painel-\d{4}-\d{2}-\d{2}\.db$")


def diretorio_backups() -> Path:
    """`BACKUP_DIR` se configurado (mesma variavel do backup semanal), senao a
    pasta `backups/` irma do banco (`data/backups/`, ja coberta pelo
    .gitignore porque `data/` inteira e ignorada)."""
    configurado = os.environ.get("BACKUP_DIR")
    if configurado:
        return Path(configurado)
    return Path(db.DB_PATH).parent / "backups"


def listar_backups(diretorio: Path | None = None) -> list[Path]:
    """Backups diarios existentes, do mais antigo pro mais novo (o nome carrega
    a data, entao a ordenacao por nome nao depende de mtime do filesystem)."""
    diretorio = diretorio or diretorio_backups()
    if not diretorio.is_dir():
        return []
    return sorted(p for p in diretorio.iterdir() if p.is_file() and _PADRAO_NOME.match(p.name))


def _rotacionar(diretorio: Path) -> None:
    for antigo in listar_backups(diretorio)[:-BACKUP_DIARIO_MANTER]:
        try:
            antigo.unlink()
        except OSError as e:
            log.error("backup diario: falha ao apagar backup antigo %s: %s", antigo.name, e)


def rodar_backup_diario(agora: datetime | None = None) -> Path | None:
    """Tira o snapshot do dia em `painel-AAAA-MM-DD.db` e apaga os alem dos
    `BACKUP_DIARIO_MANTER` mais recentes. Devolve o caminho, ou None se falhou
    (nunca levanta excecao)."""
    agora = agora or datetime.now()
    temporario = None
    try:
        diretorio = diretorio_backups()
        diretorio.mkdir(parents=True, exist_ok=True)
        destino = diretorio / f"painel-{agora.strftime('%Y-%m-%d')}.db"
        temporario = diretorio / f"{destino.name}.parcial"

        origem = sqlite3.connect(db.DB_PATH)
        dest_conn = sqlite3.connect(temporario)
        try:
            origem.backup(dest_conn)
        finally:
            dest_conn.close()
            origem.close()

        os.replace(temporario, destino)
        temporario = None
        _rotacionar(diretorio)
        log.info("backup diario salvo em %s", destino)
        return destino
    except Exception as e:
        log.error("backup diario falhou: %s", e)
        return None
    finally:
        if temporario is not None:
            try:
                Path(temporario).unlink(missing_ok=True)
            except OSError:
                pass


def backup_se_atrasado(agora: datetime | None = None) -> Path | None:
    """Chamado ao subir o app: so faz backup se nao existe nenhum ou se o mais
    recente tem mais de `IDADE_MAXIMA_HORAS` (mtime do arquivo). Devolve o
    caminho do backup novo, ou None se nao precisou / falhou."""
    agora = agora or datetime.now()
    try:
        existentes = listar_backups()
        if existentes:
            idade_s = agora.timestamp() - existentes[-1].stat().st_mtime
            if idade_s <= IDADE_MAXIMA_HORAS * 3600:
                return None
        return rodar_backup_diario(agora)
    except Exception as e:
        log.error("backup diario (checagem ao subir) falhou: %s", e)
        return None
