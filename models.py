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
                 farm_id=None, papel='dono', ativo=1, acessos=None,
                 tem_fazenda_propria=True):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.farm_id = farm_id or id
        self.papel = papel
        self.ativo = ativo
        # Guardado no objeto porque o loader já pagou a consulta: o seletor de
        # fazenda na navbar sai daqui sem um segundo round-trip por request.
        self.acessos = acessos or {}
        self.tem_fazenda_propria = tem_fazenda_propria

    @property
    def fazendas(self):
        """Ids de fazenda que este usuário pode abrir, a própria primeiro."""
        ids = [self.id] if (self.tem_fazenda_propria or not self.acessos) else []
        return ids + [i for i in self.acessos if i != self.id]

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
    def resolver_fazenda(uid, acessos, escolhida=None, tem_fazenda_propria=False):
        """(farm_id, papel) a partir dos acessos ativos e da fazenda escolhida.

        Função pura: é aqui que mora a revalidação. `escolhida` vem da sessão do
        usuário e **só** é aceita se o banco a devolveu como acesso ativo (ou se
        for a própria fazenda) — qualquer outro valor é descartado.

        O padrão de quem não escolheu nada depende de ter fazenda própria. Quem
        tem — um dono que também é contador de outra fazenda — abre na sua, e
        não no rebanho alheio, senão aceitar um convite mudaria a tela inicial
        de alguém. Quem não tem é convidado puro: cai na fazenda a que foi
        convidado, em vez de abrir num rebanho vazio.
        """
        if escolhida == uid and (tem_fazenda_propria or not acessos):
            return uid, 'dono'
        if escolhida in acessos:
            return escolhida, acessos[escolhida]
        if tem_fazenda_propria or not acessos:
            return uid, 'dono'
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
                # `tem_fazenda` sai no mesmo round-trip de propósito: ele decide
                # em que fazenda a sessão abre, e isso é resolvido em todo
                # request.
                "SELECT u.id, u.username, u.password_hash, u.email, u.ativo, "
                "       EXISTS (SELECT 1 FROM configuracoes c WHERE c.user_id = u.id) "
                "FROM usuarios u WHERE u.id = %s AND u.ativo = 1",
                (uid,),
            )
            dados = cursor.fetchone()
        if not dados:
            return None
        tem_fazenda = bool(dados[5])
        acessos = User.acessos_de(uid)
        farm_id, papel = User.resolver_fazenda(uid, acessos, fazenda_escolhida,
                                               tem_fazenda_propria=tem_fazenda)
        return User(dados[0], dados[1], dados[2], dados[3],
                    farm_id=farm_id, papel=papel, ativo=dados[4],
                    acessos=acessos, tem_fazenda_propria=tem_fazenda)
