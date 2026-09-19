"""Apaga o PIN de acesso configurado - use se esqueceu o PIN e nao tem
como recuperar (nao existe fluxo de "esqueci o PIN" pelo navegador de
proposito, pra nao virar um jeito de contornar o login).

Roda direto no servidor onde o painel esta hospedado (precisa de acesso
a maquina - se um estranho tivesse acesso pra rodar isso, ele ja teria
acesso ao banco inteiro de qualquer forma):
    python scripts/resetar_pin.py

Depois disso a proxima vez que abrir o painel ele pede pra escolher um
PIN novo, do zero.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import db


def main():
    db.init_db()
    conn = db.get_db()
    try:
        se_ja_tinha = db.obter_configuracao(conn, "pin_hash") is not None
        conn.execute("DELETE FROM configuracoes WHERE chave = 'pin_hash'")
        conn.execute("DELETE FROM login_tentativas")
        conn.commit()
    finally:
        conn.close()

    if se_ja_tinha:
        print("PIN apagado. Abre o painel de novo pra escolher um PIN novo.")
    else:
        print("Nenhum PIN estava configurado - nada pra apagar.")


if __name__ == "__main__":
    main()
