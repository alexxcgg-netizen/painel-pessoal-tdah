"""Banco modelo dos testes (2026-10-30): `init_db` num banco vazio vira uma copia.

Medido: `init_db` leva ~330 ms e copiar o resultado ~0,4 ms - e a suite recria o banco a cada
teste em centenas de arquivos. O modelo e feito pelo `init_db` de verdade na primeira vez, por
processo, entao o conteudo nao tem como divergir. So o caso exato "arquivo ainda nao existe" usa
a copia: banco que ja existe (testes de migracao), `MIGRACOES_DIR` trocado e o banco real seguem
pelo `init_db` original. `ENCRYPTION_KEY` muda o que o init_db grava, por isso um modelo por estado.
"""

import atexit
import shutil
import tempfile
from pathlib import Path

_pasta = None


def _caminho_do_modelo(criptografado: bool) -> Path:
    global _pasta
    if _pasta is None:
        _pasta = Path(tempfile.mkdtemp(prefix="painel_modelo_"))
        atexit.register(shutil.rmtree, _pasta, ignore_errors=True)
    return _pasta / f"modelo_{int(criptografado)}.db"


def instalar(db, criptografia) -> None:
    """Troca `db.init_db`. Precisa rodar antes do `import app` (que faz `from db import init_db`)."""
    original = db.init_db
    migracoes_padrao = Path(db.MIGRACOES_DIR)

    def init_db():
        caminho = Path(db.DB_PATH)
        if (
            caminho.resolve() == db.DB_PATH_PRODUCAO
            or caminho.exists()
            or Path(db.MIGRACOES_DIR) != migracoes_padrao
        ):
            return original()
        modelo = _caminho_do_modelo(criptografia.configurada())
        if not modelo.exists():
            try:
                db.DB_PATH = modelo
                original()
            finally:
                db.DB_PATH = caminho
        caminho.parent.mkdir(exist_ok=True)
        shutil.copyfile(modelo, caminho)

    init_db.original = original
    db.init_db = init_db
