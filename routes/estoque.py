from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from repositories import estoque_repository

estoque_bp = Blueprint('estoque', __name__)

CATEGORIAS_VALIDAS = {'medicamento', 'vacina', 'suplemento', 'mineral', 'outro'}


@estoque_bp.route('/estoque', methods=['GET', 'POST'])
@login_required
def lista_estoque():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        unidade = request.form.get('unidade', '').strip()
        categoria = request.form.get('categoria', '').strip()
        minimo_raw = request.form.get('estoque_minimo', '0').strip()

        erros = []
        if not nome:
            erros.append("Nome do produto é obrigatório.")
        if not unidade:
            erros.append("Unidade é obrigatória.")
        if categoria not in CATEGORIAS_VALIDAS:
            erros.append("Categoria inválida.")
        try:
            estoque_minimo = float(minimo_raw) if minimo_raw else 0.0
            if estoque_minimo < 0:
                erros.append("Estoque mínimo não pode ser negativo.")
        except ValueError:
            erros.append("Estoque mínimo deve ser um número.")

        if erros:
            for e in erros:
                flash(e, 'erro')
        else:
            estoque_repository.insert_produto(current_user.id, nome, unidade, categoria, estoque_minimo)
            flash(f"Produto '{nome}' cadastrado com sucesso.", 'sucesso')
        return redirect(url_for('estoque.lista_estoque'))

    try:
        produtos = estoque_repository.get_produtos(current_user.id)
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error(f"Erro ao listar estoque: {e}", exc_info=True)
        flash("Erro ao carregar estoque. Execute init_db.py para criar as views necessárias.", 'erro')
        produtos = []
    return render_template('estoque_lista.html', produtos=produtos)


@estoque_bp.route('/estoque/<int:produto_id>')
@login_required
def detalhe_estoque(produto_id):
    produto = estoque_repository.get_produto_by_id(produto_id, current_user.id)
    if not produto:
        flash("Produto não encontrado.", 'erro')
        return redirect(url_for('estoque.lista_estoque'))
    movimentacoes = estoque_repository.get_movimentacoes_by_produto(produto_id, current_user.id)
    return render_template('estoque_detalhe.html', produto=produto, movimentacoes=movimentacoes)


@estoque_bp.route('/estoque/<int:produto_id>/entrada', methods=['POST'])
@login_required
def registrar_entrada(produto_id):
    if not estoque_repository.get_produto_by_id(produto_id, current_user.id):
        flash("Produto não encontrado.", 'erro')
        return redirect(url_for('estoque.lista_estoque'))

    quantidade_raw = request.form.get('quantidade', '').strip()
    custo_raw = request.form.get('custo_unitario', '').strip()
    motivo = request.form.get('motivo', '').strip() or None
    data_mov = request.form.get('data_mov', '').strip()

    erros = []
    try:
        quantidade = float(quantidade_raw)
        if quantidade <= 0:
            erros.append("Quantidade deve ser maior que zero.")
    except ValueError:
        erros.append("Quantidade inválida.")

    custo_unitario = None
    if custo_raw:
        try:
            custo_unitario = float(custo_raw)
        except ValueError:
            erros.append("Custo unitário inválido.")

    if not data_mov:
        erros.append("Data da movimentação é obrigatória.")

    if erros:
        for e in erros:
            flash(e, 'erro')
    else:
        estoque_repository.insert_movimentacao(
            current_user.id, produto_id, 'entrada', quantidade, custo_unitario, motivo, data_mov
        )
        flash("Entrada registrada com sucesso.", 'sucesso')

    return redirect(url_for('estoque.detalhe_estoque', produto_id=produto_id))


@estoque_bp.route('/estoque/<int:produto_id>/saida', methods=['POST'])
@login_required
def registrar_saida(produto_id):
    if not estoque_repository.get_produto_by_id(produto_id, current_user.id):
        flash("Produto não encontrado.", 'erro')
        return redirect(url_for('estoque.lista_estoque'))

    quantidade_raw = request.form.get('quantidade', '').strip()
    motivo = request.form.get('motivo', '').strip() or None
    data_mov = request.form.get('data_mov', '').strip()

    erros = []
    try:
        quantidade = float(quantidade_raw)
        if quantidade <= 0:
            erros.append("Quantidade deve ser maior que zero.")
    except ValueError:
        erros.append("Quantidade inválida.")

    if not data_mov:
        erros.append("Data da movimentação é obrigatória.")

    if not erros:
        saldo = estoque_repository.get_saldo_atual(produto_id, current_user.id)
        if quantidade > saldo:
            erros.append(f"Saldo insuficiente. Saldo atual: {saldo:.3f}.")

    if erros:
        for e in erros:
            flash(e, 'erro')
    else:
        estoque_repository.insert_movimentacao(
            current_user.id, produto_id, 'saida', quantidade, None, motivo, data_mov
        )
        flash("Saída registrada com sucesso.", 'sucesso')

    return redirect(url_for('estoque.detalhe_estoque', produto_id=produto_id))
