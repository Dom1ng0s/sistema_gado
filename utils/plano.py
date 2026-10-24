"""Regras do plano da fazenda: trial, status e limite de cabeças.

Tudo aqui é função pura sobre o dicionário que `configuracao_repository.get_plano`
devolve — nada consulta banco, nada lê `g`. É o que permite testar o dia 15 do
trial e o limite estourado sem subir request nem fabricar linha.

A cobrança é manual neste estágio: o dono clica no link de pagamento, o
pagamento é conferido e a ativação é feita por fora (`scripts/ativar_plano.py`).
O que o código precisa saber é só o que já está em `configuracoes`.

`limite_cabecas <= 0` significa **sem limite**. É a saída para a conta grande
negociada à mão, e evita que alguém tenha de inventar um 999999 que um dia vai
ser pequeno.
"""

from datetime import datetime, timezone

TRIAL_DIAS = 14
LIMITE_PADRAO = 250

#: Conta sem linha em `configuracoes` (o cadastro sempre cria uma; contas de
#: teste e dados antigos podem não ter). Tratada como aberta, não como vencida:
#: a ausência de configuração é falha nossa, não inadimplência do cliente.
PLANO_PADRAO = {
    'tier': 'porteira',
    'status': 'ativo',
    'trial_ends_at': None,
    'limite_cabecas': LIMITE_PADRAO,
}

ROTULOS = {
    'trial': 'Avaliação',
    'porteira': 'Porteira',
}


def rotulo(tier):
    """Nome do tier para a tela. Tier desconhecido aparece como ele é — a
    ativação manual pode criar um nome que o código ainda não conhece, e
    esconder isso atrás de "Plano" deixaria a tela mentindo."""
    return ROTULOS.get(tier, (tier or '').replace('_', ' ').capitalize() or '—')


def _agora(agora=None):
    return agora or datetime.now(timezone.utc)


def em_trial(plano):
    return plano.get('tier') == 'trial' and plano.get('trial_ends_at') is not None


def dias_restantes(plano, agora=None):
    """Dias inteiros até o fim do trial; None fora do trial.

    Arredonda para cima: faltando 30 minutos, o dono ainda está no "último
    dia", não em zero. Negativo significa vencido há tantos dias.
    """
    if not em_trial(plano):
        return None
    fim = plano['trial_ends_at']
    restante = fim - _agora(agora)
    dias = restante.days
    if restante.seconds or restante.microseconds:
        dias += 1
    return dias


def trial_expirado(plano, agora=None):
    dias = dias_restantes(plano, agora)
    return dias is not None and dias <= 0


def sem_limite(plano):
    limite = plano.get('limite_cabecas')
    return limite is None or limite <= 0


def vagas(plano, cabecas):
    """Quantas cabeças ainda cabem. None quando não há limite.

    Pode voltar negativo: a fazenda que já tinha 400 cabeças quando o limite
    virou 250 não perde animal nenhum — ela só não cadastra mais. O limite
    nunca esconde animal existente.
    """
    if sem_limite(plano):
        return None
    return plano['limite_cabecas'] - cabecas


def pode_cadastrar(plano, cabecas, quantos=1):
    """(ok, mensagem) para cadastrar `quantos` animais.

    A mensagem é a que o dono lê, então diz o número e o caminho da saída.
    """
    livres = vagas(plano, cabecas)
    if livres is None:
        return True, None
    if quantos <= livres:
        return True, None
    limite = plano['limite_cabecas']
    if livres <= 0:
        return False, (
            f"Seu plano permite {limite} cabeças e a fazenda já tem {cabecas}. "
            "Venda ou exclua animais, ou amplie o plano em Configurações → Plano."
        )
    return False, (
        f"Seu plano permite {limite} cabeças e restam {livres} vaga(s) — "
        f"você tentou cadastrar {quantos}. Amplie o plano em "
        "Configurações → Plano."
    )


def resumo(plano, cabecas, agora=None):
    """O que a tela de plano mostra, já resolvido."""
    livres = vagas(plano, cabecas)
    return {
        'tier': plano.get('tier'),
        'rotulo': rotulo(plano.get('tier')),
        'status': plano.get('status'),
        'em_trial': em_trial(plano),
        'dias_restantes': dias_restantes(plano, agora),
        'expirado': trial_expirado(plano, agora),
        'trial_ends_at': plano.get('trial_ends_at'),
        'limite_cabecas': plano.get('limite_cabecas'),
        'sem_limite': sem_limite(plano),
        'cabecas': cabecas,
        'vagas': livres,
        'estourado': livres is not None and livres <= 0,
        # Percentual para a barra; sem limite não tem barra para desenhar.
        'uso_pct': (None if livres is None or plano['limite_cabecas'] <= 0
                    else min(100, round(cabecas * 100 / plano['limite_cabecas']))),
    }
