"""Convites e acessos delegados (`acessos_fazenda`).

O PR dos acessos criou a tabela; sem isto ela só era alimentável por SQL. Aqui
mora o que a tela de acessos precisa: listar quem entra na fazenda, convidar
por email e revogar.

Toda escrita é escopada por `owner_user_id`. Não é zelo: o id do acesso vem da
URL, e sem o dono no WHERE um dono revogaria o acesso de outra fazenda só
trocando o número.
"""

import re
import secrets
import unicodedata

from db_config import get_db_cursor

PAPEIS_CONVIDAVEIS = ('vaqueiro', 'contador', 'consultor')


def listar_por_fazenda(owner_user_id, incluir_revogados=True):
    """Acessos da fazenda, o mais recente primeiro."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT a.id, a.account_user_id, u.username, u.email, a.papel, a.ativo, "
            "       a.created_at "
            "FROM acessos_fazenda a JOIN usuarios u ON u.id = a.account_user_id "
            "WHERE a.owner_user_id = %s " +
            ("" if incluir_revogados else "AND a.ativo = 1 ") +
            "ORDER BY a.ativo DESC, a.created_at DESC",
            (owner_user_id,)
        )
        return cursor.fetchall()


def conceder(account_user_id, owner_user_id, papel):
    """Cria ou reativa o acesso. Reconvidar quem foi revogado é o caso comum —
    o vaqueiro da safra passada volta — e o UNIQUE recusaria um INSERT novo."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO acessos_fazenda (account_user_id, owner_user_id, papel, ativo) "
            "VALUES (%s, %s, %s, 1) "
            "ON CONFLICT (account_user_id, owner_user_id) "
            "DO UPDATE SET papel = EXCLUDED.papel, ativo = 1 "
            "RETURNING id",
            (account_user_id, owner_user_id, papel)
        )
        return cursor.fetchone()[0]


def revogar(acesso_id, owner_user_id):
    """Desliga o acesso. `ativo = 0` em vez de DELETE: o loader relê em todo
    request, então vale na requisição seguinte, e a linha fica como registro de
    que aquela pessoa teve acesso."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE acessos_fazenda SET ativo = 0 WHERE id = %s AND owner_user_id = %s",
            (acesso_id, owner_user_id)
        )
        return cursor.rowcount > 0


def nomes_de_fazendas(user_ids):
    """{user_id: nome_fazenda} para o seletor. Conta sem configuração entra com
    o próprio username, que é melhor do que uma linha em branco no menu."""
    ids = [int(i) for i in user_ids]
    if not ids:
        return {}
    marcadores = ','.join(['%s'] * len(ids))
    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT u.id, COALESCE(NULLIF(c.nome_fazenda, ''), u.username) "
            f"FROM usuarios u LEFT JOIN configuracoes c ON c.user_id = u.id "
            f"WHERE u.id IN ({marcadores})",
            ids
        )
        return {linha[0]: linha[1] for linha in cursor.fetchall()}


def _slug(texto, tamanho=20):
    """Pedaço de nome seguro para username: sem acento, sem espaço, minúsculo."""
    sem_acento = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode()
    limpo = re.sub(r'[^a-zA-Z0-9]+', '', sem_acento).lower()
    return limpo[:tamanho]


def gerar_username(nome_fazenda, email):
    """Username de sistema no formato `<fazenda>.<pessoa>`.

    `usuarios.username` é UNIQUE global: a segunda fazenda a convidar um "joao"
    colidiria. Prefixar com a fazenda resolve isso e ainda deixa o login legível
    para quem administra — mas quem foi convidado entra pelo email, não por
    este nome.
    """
    fazenda = _slug(nome_fazenda) or 'fazenda'
    pessoa = _slug((email or '').split('@')[0]) or 'convidado'
    base = f"{fazenda}.{pessoa}"[:45]
    with get_db_cursor() as cursor:
        candidato = base
        for _ in range(50):
            cursor.execute("SELECT 1 FROM usuarios WHERE username = %s", (candidato,))
            if not cursor.fetchone():
                return candidato
            candidato = f"{base}{secrets.randbelow(900) + 100}"
    # 50 colisões seguidas é defeito, não azar: melhor falhar do que entregar
    # um username que o INSERT vai recusar.
    raise RuntimeError(f"não foi possível gerar username a partir de '{base}'")


def criar_convidado(username, email, password_hash):
    """Conta nova, sem fazenda própria (nenhuma linha em `configuracoes`).

    É essa ausência que faz o loader levar o convidado direto para a fazenda a
    que ele foi convidado, em vez de abrir num rebanho vazio que é dele.

    `password_hash` é NOT NULL, então o convidado nasce com uma senha aleatória
    que ninguém conhece — inclusive ele. A senha de verdade vem pelo código de
    `password_reset_tokens`, o mesmo fluxo de "esqueci minha senha".
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO usuarios (username, email, password_hash) VALUES (%s, %s, %s) "
            "RETURNING id",
            (username, email, password_hash)
        )
        return cursor.fetchone()[0]
