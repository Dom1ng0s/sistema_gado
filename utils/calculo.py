KG_POR_ARROBA = 30


def preco_por_arroba(peso_kg, valor_arroba):
    """Preço de compra/venda a partir do peso vivo e valor da arroba, arredondado a centavos."""
    return round((peso_kg / KG_POR_ARROBA) * valor_arroba, 2)
