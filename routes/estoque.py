from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import logging
from repositories import estoque_repository
from routes.validators import validate

estoque_bp = Blueprint('estoque', __name__)
logger = logging.getLogger(__name__)

CATEGORIAS_VALIDAS = ['medicamento', 'vacina', 'suplemento', 'mineral', 'outro']


@estoque_bp.route('/estoque', methods=['GET', 'POST'])
@login_required
def lista_estoque():
    if request.method == 'POST':
        erros = validate(request.form, [
            ('nome',            {'required': True, 'type': 'str', 'label': 'Nome do produto'}),
            ('unidade',         {'required': True, 'type': 'str', 'label': 'Unidade'}),
            ('categoria',       {'required': True, 'type': 'str', 'choices': CATEGORIAS_VALIDAS, 'label': 'Categoria'}),
            ('estoque_minimo',  {'required': False, 'type': 'float', 'min_val': 0, 'label': 'Estoque mínimo'}),
        ])
        if erros:
            flash(' | '.join(erros), 'error')
        else:
            nome = request.form.get('nome', '').strip()
            unidade = request.form.get('unidade', '').strip()
            categoria = request.form.get('categoria', '').strip()
            minimo_raw = request.form.get('estoque_minimo', '').strip()
            estoque_minimo = float(minimo_raw) if minimo_raw else 0.0
            estoque_repository.insert_produto(current_user.id, nome, unidade, categoria, estoque_minimo)
            flash(f"Produto '{nome}' cadastrado com sucesso.", 'success')
        return redirect(url_for('estoque.lista_estoque'))

    busca = request.args.get('busca', '').strip()
    try:
        produtos = estoque_repository.get_produtos(current_user.id)
        if busca:
            bl = busca.lower()
            produtos = [p for p in produtos if bl in (p[2] or '').lower()]
    except Exception as e:
        logger.error(f"Erro ao listar estoque: {e}", exc_info=True)
        flash("Erro ao carregar estoque. Execute init_db.py para criar as views necessárias.", 'error')
        produtos = []
    return render_template('estoque_lista.html', produtos=produtos, busca=busca)


@estoque_bp.route('/estoque/<int:produto_id>')
@login_required
def detalhe_estoque(produto_id):
    produto = estoque_repository.get_produto_by_id(produto_id, current_user.id)
    if not produto:
        flash("Produto não encontrado.", 'error')
        return redirect(url_for('estoque.lista_estoque'))
    movimentacoes = estoque_repository.get_movimentacoes_by_produto(produto_id, current_user.id)
    return render_template('estoque_detalhe.html', produto=produto, movimentacoes=movimentacoes)


@estoque_bp.route('/estoque/<int:produto_id>/entrada', methods=['POST'])
@login_required
def registrar_entrada(produto_id):
    if not estoque_repository.get_produto_by_id(produto_id, current_user.id):
        flash("Produto não encontrado.", 'error')
        return redirect(url_for('estoque.lista_estoque'))

    erros = validate(request.form, [
        ('quantidade',      {'required': True, 'type': 'float', 'min_val': 0.001, 'label': 'Quantidade'}),
        ('custo_unitario',  {'required': False, 'type': 'float', 'min_val': 0, 'label': 'Custo unitário'}),
        ('data_mov',        {'required': True, 'type': 'date', 'label': 'Data da movimentação'}),
    ])
    if erros:
        flash(' | '.join(erros), 'error')
    else:
        quantidade = float(request.form['quantidade'])
        custo_raw = request.form.get('custo_unitario', '').strip()
        custo_unitario = float(custo_raw) if custo_raw else None
        motivo = request.form.get('motivo', '').strip() or None
        data_mov = request.form['data_mov']
        lote_fabricante = request.form.get('lote_fabricante', '').strip() or None
        data_validade = request.form.get('data_validade', '').strip() or None

        estoque_repository.insert_movimentacao(
            current_user.id, produto_id, 'entrada', quantidade, custo_unitario, motivo, data_mov,
            lote_fabricante=lote_fabricante, data_validade=data_validade,
        )
        flash("Entrada registrada com sucesso.", 'success')

    return redirect(url_for('estoque.detalhe_estoque', produto_id=produto_id))


@estoque_bp.route('/estoque/<int:produto_id>/saida', methods=['POST'])
@login_required
def registrar_saida(produto_id):
    if not estoque_repository.get_produto_by_id(produto_id, current_user.id):
        flash("Produto não encontrado.", 'error')
        return redirect(url_for('estoque.lista_estoque'))

    erros = validate(request.form, [
        ('quantidade', {'required': True, 'type': 'float', 'min_val': 0.001, 'label': 'Quantidade'}),
        ('data_mov',   {'required': True, 'type': 'date', 'label': 'Data da movimentação'}),
    ])
    if erros:
        flash(' | '.join(erros), 'error')
    else:
        quantidade = float(request.form['quantidade'])
        motivo = request.form.get('motivo', '').strip() or None
        data_mov = request.form['data_mov']
        try:
            estoque_repository.insert_movimentacao(
                current_user.id, produto_id, 'saida', quantidade, None, motivo, data_mov
            )
            flash("Saída registrada com sucesso.", 'success')
        except ValueError as e:
            flash(str(e), 'error')

    return redirect(url_for('estoque.detalhe_estoque', produto_id=produto_id))
