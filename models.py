from flask_login import UserMixin
from db_config import get_db_cursor


class User(UserMixin):
    """A conta que logou, mais a fazenda em que ela está trabalhando.

    `id` é sempre a linha real em `usuarios` — é identidade: quem assina a ação,
    de quem é a senha, qual conta apagar. `farm_id` é o tenant: é o que vai para
    os repositórios e aparece em `animais.user_id`. Para o dono os dois são o
    mesmo número; para um vaqueiro ou contador convidado, não.

    Essa distinção é a razão de o código de rota usar `current_user.farm_id` em
    quase todo lugar: trocar um pelo outro vira, num caso, o convidado olhando a
    fazenda errada, e no outro, ele apagando a conta do dono.
    """

    def __init__(self, id, username, password_hash, email=None,
                 farm_id=None, papel='dono', ativo=1):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.farm_id = farm_id or id
        self.papel = papel
        self.ativo = ativo

    # `get_id()` vem do UserMixin e serializa `self.id` — continua correto de
    # graça porque `self.id` voltou a ser só a conta.

    @staticmethod
    def acessos_de(uid):
        """Fazendas em que `uid` tem acesso ativo, como {owner_user_id: papel}.

        Vazio significa dono: `dono` não é uma linha em `acessos_fazenda`, é a
        ausência dela.
        """
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT owner_user_id, papel FROM acessos_fazenda "
                "WHERE account_user_id = %s AND ativo = 1 ORDER BY owner_user_id",
                (uid,),
            )
            return {linha[0]: linha[1] for linha in cursor.fetchall()}

    @staticmethod
    def resolver_fazenda(uid, acessos, escolhida=None):
        """(farm_id, papel) a partir dos acessos ativos e da fazenda escolhida.

        Função pura: é aqui que mora a revalidação. `escolhida` vem da sessão do
        usuário e **só** é aceita se o banco a devolveu como acesso ativo —
        qualquer outro valor cai no primeiro acesso, ou na própria conta. Um
        consultor atende N fazendas; o seletor na navbar vem depois, a
        revalidação não pode.
        """
        if not acessos:
            return uid, 'dono'
        if escolhida in acessos:
            return escolhida, acessos[escolhida]
        primeira = next(iter(acessos))
        return primeira, acessos[primeira]

    @staticmethod
    def get_user_id(user_id, fazenda_escolhida=None):
        # Flask-Login serializa o id como string na sessão; o Postgres não
        # coage text→integer implicitamente como o MySQL fazia.
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return None
        with get_db_cursor() as cursor:
            # `ativo = 1` aqui é a revogação da conta inteira: o cookie de quem
            # foi desligado para de valer no request seguinte.
            cursor.execute(
                "SELECT id, username, password_hash, email, ativo "
                "FROM usuarios WHERE id = %s AND ativo = 1",
                (uid,),
            )
            dados = cursor.fetchone()
        if not dados:
            return None
        acessos = User.acessos_de(uid)
        farm_id, papel = User.resolver_fazenda(uid, acessos, fazenda_escolhida)
        return User(dados[0], dados[1], dados[2], dados[3],
                    farm_id=farm_id, papel=papel, ativo=dados[4])
