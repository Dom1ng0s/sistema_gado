from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user
from db_config import get_db_cursor
import logging
import requests

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api_bp.route('/graficos')
@login_required
def graficos_page():
    return render_template('graficos.html')

@api_bp.route('/dados-graficos')
@login_required
def dados_graficos_api():
    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            # 1. Gráfico Sexo
            cursor.execute("SELECT sexo, COUNT(*) FROM animais WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL GROUP BY sexo", (uid,))
            dados_sexo = {sexo: qtd for sexo, qtd in cursor.fetchall()}
            
            # 2. Gráfico Peso
            cursor.execute("SELECT p.peso FROM pesagens p INNER JOIN (SELECT animal_id, MAX(id) as m FROM pesagens GROUP BY animal_id) u ON p.id=u.m INNER JOIN animais a ON p.animal_id=a.id WHERE a.user_id=%s AND a.data_venda IS NULL AND a.deleted_at IS NULL", (uid,))
            pesos = cursor.fetchall()
            cat_peso = {'Menos de 10@': 0, '10@ a 15@': 0, '15@ a 20@': 0, 'Mais de 20@': 0}
            for (p_kg,) in pesos:
                p_arr = float(p_kg)/30
                if p_arr < 10: cat_peso['Menos de 10@'] += 1
                elif 10 <= p_arr < 15: cat_peso['10@ a 15@'] += 1
                elif 15 <= p_arr < 20: cat_peso['15@ a 20@'] += 1
                else: cat_peso['Mais de 20@'] += 1
            
            # 3. GMD
            cursor.execute("SELECT AVG(v.gmd) FROM v_gmd_analitico v JOIN animais a ON v.animal_id=a.id WHERE v.user_id=%s AND a.data_venda IS NULL AND a.deleted_at IS NULL", (uid,))
            gmd = cursor.fetchone()[0]
            
            return jsonify({'sexo': dados_sexo, 'peso': cat_peso, 'gmd_medio': float(gmd) if gmd else 0.0}), 200
    except Exception as e:
        logger.error(f"Erro API: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@api_bp.route('/proxy-cidades')
def proxy_cidades():
    """
    Busca cidades na API Oficial do IBGE.
    Trata erros de estrutura (NoneType) e conexão.
    """
    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
        
        # Timeout para evitar que o servidor trave se o IBGE demorar
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            dados_brutos = response.json()
            cidades_formatadas = []
            
            for item in dados_brutos:
                # O bloco try/except aqui é crucial.
                # Se 'microrregiao' ou 'mesorregiao' for None, lança TypeError.
                # Se a chave não existir, lança KeyError.
                # Ignoramos ambos para garantir que só cidades válidas entrem.
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
        # 1. BUSCAR LOCALIZAÇÃO DO USUÁRIO
        uf_usuario = None
        with get_db_cursor() as cursor:
            cursor.execute("SELECT cidade_estado FROM configuracoes WHERE user_id = %s", (current_user.id,))
            res = cursor.fetchone()
            if res and res[0]:
                # Formato esperado: "Cidade - UF" (ex: "Uberaba - MG")
                partes = res[0].split('-')
                if len(partes) > 1:
                    uf_usuario = partes[-1].strip().upper() # Pega o "MG"
        
        if not uf_usuario:
            return jsonify({'erro': 'Localização não configurada'}), 404

        # 2. DEFINIR URLs DOS DADOS (Substitua pelo seu USER/REPO corretos)
        base_url = "https://raw.githubusercontent.com/dom1ng0s/gado-scraper/main"
        url_boi = f"{base_url}/cotacoes_boi_hoje.json"
        url_novilha = f"{base_url}/cotacoes_novilha_hoje.json"

        # 3. FUNÇÃO AUXILIAR DE BUSCA E FILTRO
        def buscar_e_filtrar(url, uf):
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code != 200: return []
                
                dados = resp.json()
                resultados = []
                
                # Mapeamento para casos onde o JSON usa nome completo
                mapa_estados = {'AC': 'Acre', 'AL': 'Alagoas', 'RR': 'Roraima'}
                nome_completo = mapa_estados.get(uf, '')

                for item in dados:
                    praca = item.get('praca', '').upper()
                    # Verifica se a praça começa com a UF (ex: "SP Barretos") 
                    # ou se é o nome exato (ex: "ALAGOAS", "SC")
                    if praca.startswith(uf) or praca == uf or (nome_completo and praca == nome_completo.upper()):
                        resultados.append(item)
                
                return resultados
            except Exception as e:
                logger.error(f"Erro ao ler JSON {url}: {e}")
                return []

        # 4. EXECUTAR
        cotacoes_boi = buscar_e_filtrar(url_boi, uf_usuario)
        cotacoes_novilha = buscar_e_filtrar(url_novilha, uf_usuario)

        return jsonify({
            'uf': uf_usuario,
            'boi': cotacoes_boi,
            'novilha': cotacoes_novilha
        })

    except Exception as e:
        logger.error(f"Erro cotacoes: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# --- NOVA ROTA: TODAS AS COTAÇÕES (PARA O MODAL) ---
@api_bp.route('/cotacoes-brasil')
@login_required
def cotacoes_brasil():
    """Retorna a lista completa de cotações (Boi e Novilha) de todas as praças."""
    try:
        # URLs do GitHub (Mesmas da rota regional)
        base_url = "https://raw.githubusercontent.com/dom1ng0s/gado-scraper/main"
        
        # Função interna para buscar JSON cru
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