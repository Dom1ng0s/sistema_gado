from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user
import logging
import requests
from repositories import animal_repository, configuracao_repository

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api_bp.route('/graficos')
@login_required
def graficos_page():
    return render_template('graficos.html')

@api_bp.route('/api/graficos/sexo')
@login_required
def graficos_sexo():
    try:
        rows = animal_repository.get_contagem_por_sexo(current_user.id)
        return jsonify({sexo: qtd for sexo, qtd in rows})
    except Exception as e:
        logger.error(f"Erro Gráfico Sexo: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/graficos/peso')
@login_required
def graficos_peso():
    try:
        rows = animal_repository.get_pesos_atuais_rebanho(current_user.id)
        cat_peso = {'Menos de 10@': 0, '10@ a 15@': 0, '15@ a 20@': 0, 'Mais de 20@': 0}
        for (p_kg,) in rows:
            p_arr = float(p_kg) / 30
            if p_arr < 10:
                cat_peso['Menos de 10@'] += 1
            elif 10 <= p_arr < 15:
                cat_peso['10@ a 15@'] += 1
            elif 15 <= p_arr < 20:
                cat_peso['15@ a 20@'] += 1
            else:
                cat_peso['Mais de 20@'] += 1
        return jsonify(cat_peso)
    except Exception as e:
        logger.error(f"Erro Gráfico Peso: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/graficos/gmd')
@login_required
def graficos_gmd():
    try:
        gmd_medio = animal_repository.get_gmd_medio_rebanho(current_user.id)
        return jsonify({'gmd_medio': gmd_medio})
    except Exception as e:
        logger.error(f"Erro Gráfico GMD: {e}")
        return jsonify({'error': str(e)}), 500

# --- FIM DAS ROTAS DE GRÁFICOS ---

@api_bp.route('/proxy-cidades')
def proxy_cidades():
    """
    Busca cidades na API Oficial do IBGE.
    Trata erros de estrutura (NoneType) e conexão.
    """
    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            dados_brutos = response.json()
            cidades_formatadas = []
            for item in dados_brutos:
                try:
                    cidades_formatadas.append({
                        "nome": item['nome'],
                        "uf": item['microrregiao']['mesorregiao']['UF']['sigla']
                    })
                except (KeyError, TypeError):
                    continue
            return jsonify(cidades_formatadas)
        else:
            logger.error(f"Erro IBGE: Status {response.status_code}")
            return jsonify({'error': f"Erro no IBGE: {response.status_code}"}), 502

    except Exception as e:
        logger.error(f"Erro proxy: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@api_bp.route('/cotacoes-regionais')
@login_required
def cotacoes_regionais():
    """
    1. Pega o estado (UF) do usuário.
    2. Baixa o JSON do Gado-Scraper (GitHub).
    3. Filtra as cotações do estado correspondente.
    """
    try:
        uf_usuario = None
        res = configuracao_repository.get_configuracao(current_user.id)
        if res and res[1]:
            partes = res[1].split('-')
            if len(partes) > 1:
                uf_usuario = partes[-1].strip().upper()

        if not uf_usuario:
            return jsonify({'erro': 'Localização não configurada'}), 404

        base_url = "https://raw.githubusercontent.com/dom1ng0s/gado-scraper/main"
        url_boi = f"{base_url}/cotacoes_boi_hoje.json"
        url_novilha = f"{base_url}/cotacoes_novilha_hoje.json"

        def buscar_e_filtrar(url, uf):
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code != 200:
                    return []
                dados = resp.json()
                resultados = []
                mapa_estados = {'AC': 'Acre', 'AL': 'Alagoas', 'RR': 'Roraima'}
                nome_completo = mapa_estados.get(uf, '')
                for item in dados:
                    praca = item.get('praca', '').upper()
                    if praca.startswith(uf) or praca == uf or (nome_completo and praca == nome_completo.upper()):
                        resultados.append(item)
                return resultados
            except Exception as e:
                logger.error(f"Erro ao ler JSON {url}: {e}")
                return []

        cotacoes_boi = buscar_e_filtrar(url_boi, uf_usuario)
        cotacoes_novilha = buscar_e_filtrar(url_novilha, uf_usuario)

        return jsonify({'uf': uf_usuario, 'boi': cotacoes_boi, 'novilha': cotacoes_novilha})

    except Exception as e:
        logger.error(f"Erro cotacoes: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@api_bp.route('/cotacoes-brasil')
@login_required
def cotacoes_brasil():
    """Retorna a lista completa de cotações (Boi e Novilha) de todas as praças."""
    try:
        base_url = "https://raw.githubusercontent.com/dom1ng0s/gado-scraper/main"

        def buscar_dados(endpoint):
            try:
                resp = requests.get(f"{base_url}/{endpoint}", timeout=5)
                return resp.json() if resp.status_code == 200 else []
            except:
                return []

        boi = buscar_dados("cotacoes_boi_hoje.json")
        novilha = buscar_dados("cotacoes_novilha_hoje.json")

        return jsonify({'boi': boi, 'novilha': novilha})

    except Exception as e:
        logger.error(f"Erro cotacoes brasil: {e}")
        return jsonify({'error': str(e)}), 500
