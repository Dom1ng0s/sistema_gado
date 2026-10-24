"""Sugestão de dias de carência a partir do nome do produto aplicado.

Não há cadastro de produtos no sistema: `medicacoes.nome_medicamento` é texto
livre digitado no curral. O dicionário abaixo cobre o que de fato aparece nesse
campo — o prazo da bula dos princípios ativos de uso corrente em bovino de
corte — e serve só para **pré-preencher** o formulário. O valor gravado é o que
o usuário confirmar; nada aqui sobrepõe o que ele digitou.

Os prazos são conservadores (o maior entre as apresentações comuns). Produto
desconhecido cai em 0, que é o comportamento de hoje: sem prazo declarado, a
venda não trava.
"""
import unicodedata

# princípio ativo / nome comercial -> dias de carência
# Só entram produtos COM prazo. Vacina, vitamina, ADE, fosfato e ceftiofur não
# têm carência para carne e por isso ficam de fora: ausência aqui já significa 0.
CARENCIA_PADRAO = {
    'ivermectina':     35,
    'doramectina':     42,
    'abamectina':      35,
    'moxidectina':     23,
    'closantel':       42,
    'levamisol':       14,
    'albendazol':      14,
    'oxitetraciclina': 28,
    'tetraciclina':    28,
    'enrofloxacina':   28,
    'florfenicol':     30,
    'penicilina':      30,
    'tulatromicina':   44,
    'cipermetrina':     5,
    'fluazuron':       42,
    'diminazeno':      21,
    'dipirona':         3,
    'flunixina':        8,
}


def _normalizar(texto):
    """minúsculas sem acento — o campo é digitado à mão, com e sem acento."""
    sem_acento = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def dias_carencia_sugerido(nome_medicamento):
    """Dias de carência sugeridos para o nome digitado, ou 0 se não reconhecido.

    Casa por substring porque o campo vem como "Ivermectina 1% 10ml" ou
    "ivomec (ivermectina)". Entre duas chaves que casem, vence o prazo maior —
    errar para o lado seguro é travar uma venda a mais, não liberar uma a menos.
    """
    alvo = _normalizar(nome_medicamento)
    if not alvo:
        return 0
    casados = [dias for chave, dias in CARENCIA_PADRAO.items()
               if _normalizar(chave) in alvo]
    return max(casados) if casados else 0
