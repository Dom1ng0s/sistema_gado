"""Registro de pesagem, fora da rota.

A rota de pesagem era o único lugar onde "o que é uma pesagem válida" existia:
validação do peso e da data em `routes/operacional.py`, escrita no repositório.
Qualquer outra entrada — importação, integração, bot — teria de repetir essas
regras, e a cópia que fica mais fraca é justamente a que guarda o dado digitado
com uma mão no curral.

Então a regra mora aqui, e a rota passou a ser só HTTP: formulário entra,
`registrar` decide, `flash` sai. A validação é a mesma `routes.validators`, não
uma segunda interpretação do que é peso aceitável.

O animal pode vir por id (a web, que acabou de abrir a ficha) ou por brinco
(todo o resto: o brinco é a chave que a pessoa usa no curral). A tradução é
feita aqui, dentro da fazenda certa.
"""

import logging

from repositories import animal_repository
from routes.validators import validate

log = logging.getLogger(__name__)

REGRAS = [
    ('data_pesagem', {'required': True, 'type': 'date', 'label': 'Data da pesagem'}),
    ('peso', {'required': True, 'type': 'float', 'min_val': 0.1, 'max_val': 2000,
              'label': 'Peso'}),
]


def validar(data_pesagem, peso):
    """Erros de uma pesagem, como lista de mensagens. Vazia = válida."""
    return validate({'data_pesagem': data_pesagem, 'peso': peso}, REGRAS)


def resolver_animal(farm_id, animal_id=None, brinco=None):
    """Id do animal dentro desta fazenda, ou None.

    Resolver aqui — e não no chamador — é o que impede uma entrada nova de
    procurar o animal sem o filtro da fazenda.
    """
    if animal_id is not None:
        animal = animal_repository.get_animal_by_id(animal_id, farm_id)
        return animal_id if animal else None
    if brinco:
        return animal_repository.get_animal_id_by_brinco(brinco.strip(), farm_id)
    return None


def registrar(farm_id, peso, data_pesagem, registrado_por,
              animal_id=None, brinco=None):
    """Registra a pesagem. Devolve (animal_id, erro).

    `erro` é a mensagem pronta para mostrar a quem registrou; `animal_id` vem
    preenchido só quando gravou.
    """
    erros = validar(data_pesagem, peso)
    if erros:
        return None, erros[0]

    alvo = resolver_animal(farm_id, animal_id=animal_id, brinco=brinco)
    if alvo is None:
        return None, ("Animal não encontrado."
                      if animal_id is not None
                      else f"Nenhum animal ativo com o brinco '{brinco}'.")

    ok = animal_repository.registrar_pesagem(
        alvo, farm_id, data_pesagem, peso, registrado_por=registrado_por)
    if not ok:
        # O animal existia na checagem e sumiu entre uma coisa e outra:
        # concorrência, não entrada inválida.
        log.warning("Pesagem recusada pelo repositório: animal=%s fazenda=%s",
                    alvo, farm_id)
        return None, "Animal não encontrado."
    return alvo, None
