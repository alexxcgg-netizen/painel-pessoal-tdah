"""Gera a chave de criptografia em repouso (Open Finance + saude).

Roda uma unica vez (ou de novo se quiser trocar a chave - mas ver o aviso
abaixo antes):
    python scripts/gerar_chave_criptografia.py

So imprime a chave pronta pra colar no .env - nao salva em arquivo nenhum
(diferente de scripts/gerar_chaves_push.py, que guarda a chave privada em
disco): ENCRYPTION_KEY e a UNICA copia dela, entao o lugar certo e direto no
.env (ou no gerenciador de segredos do seu deploy), nunca escrita solta num
arquivo dentro do repositorio.
"""

from cryptography.fernet import Fernet


def main():
    chave = Fernet.generate_key().decode()

    print("\nAdicione isso ao seu .env:\n")
    print(f"ENCRYPTION_KEY={chave}")
    print(
        "\nATENCAO: guarde essa chave em algum lugar seguro fora do servidor (ex: um "
        "gerenciador de senhas). Sem ela, todo dado ja criptografado com ela vira "
        "irrecuperavel pra sempre - nao existe 'recuperar senha' pra isso. Se voce ja "
        "tem uma ENCRYPTION_KEY configurada e gerar uma nova aqui, os dados gravados com a "
        "antiga ficam ilegiveis ate a antiga voltar ao .env. Ver docs/SEGURANCA.md."
    )


if __name__ == "__main__":
    main()
