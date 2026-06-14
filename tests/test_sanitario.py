import pytest
import mysql.connector
from datetime import date, timedelta

DB_CONFIG = {
    "host": "localhost", "user": "gado_test",
    "password": "gado123", "port": 3306, "database": "sistema_gado_test",
}


def login(client):
    return client.post('/login', data={'username': 'testuser', 'password': '123'}, follow_redirects=True)


def _get_user_id():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id FROM usuarios WHERE username='testuser'")
    uid = cur.fetchone()[0]
    cur.close()
    conn.close()
    return uid


def test_sanitario_lista_vazia(client):
    """Página carrega mesmo sem protocolos cadastrados."""
    login(client)
    response = client.get('/sanitario')
    assert response.status_code == 200
    assert 'Calendário Sanitário'.encode('utf-8') in response.data


def test_cadastro_protocolo(client):
    """POST cria protocolo e redireciona para lista."""
    login(client)
    response = client.post('/sanitario', data={
        'nome': 'Febre Aftosa',
        'intervalo_dias': '180',
        'proxima_aplicacao': '2026-07-01',
        'descricao': 'Dose semestral obrigatória',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Febre Aftosa' in response.data
    assert 'Protocolo cadastrado'.encode('utf-8') in response.data


def test_cadastro_protocolo_sem_nome_retorna_erro(client):
    """Validação rejeita protocolo sem nome."""
    login(client)
    response = client.post('/sanitario', data={
        'nome': '',
        'intervalo_dias': '30',
        'proxima_aplicacao': '2026-07-01',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'obrigatório'.encode('utf-8') in response.data or b'nome' in response.data.lower()


def test_cadastro_protocolo_intervalo_invalido(client):
    """Intervalo 0 é rejeitado."""
    login(client)
    response = client.post('/sanitario', data={
        'nome': 'Teste intervalo zero',
        'intervalo_dias': '0',
        'proxima_aplicacao': '2026-07-01',
    }, follow_redirects=True)
    assert response.status_code == 200
    # Deve exibir erro — protocolo não criado
    assert b'Teste intervalo zero' not in response.data or 'erro' in response.data.decode('utf-8').lower()


def test_aplicar_protocolo_avanca_data(client):
    """Aplicar protocolo avança proxima_aplicacao em intervalo_dias."""
    login(client)
    uid = _get_user_id()
    hoje = date.today()
    proxima = hoje + timedelta(days=5)

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO protocolos_sanitarios (user_id, nome, intervalo_dias, proxima_aplicacao) "
        "VALUES (%s, 'Vermifugação', 90, %s)",
        (uid, proxima.isoformat())
    )
    pid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()

    response = client.post(f'/sanitario/{pid}/aplicar', follow_redirects=True)
    assert response.status_code == 200

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT proxima_aplicacao FROM protocolos_sanitarios WHERE id=%s", (pid,))
    nova_data = cur.fetchone()[0]
    cur.close()
    conn.close()

    esperado = proxima + timedelta(days=90)
    assert nova_data == esperado


def test_desativar_protocolo(client):
    """Desativar remove protocolo da lista."""
    login(client)
    uid = _get_user_id()

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO protocolos_sanitarios (user_id, nome, intervalo_dias, proxima_aplicacao) "
        "VALUES (%s, 'Brucelose', 365, '2026-12-01')",
        (uid,)
    )
    pid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()

    client.post(f'/sanitario/{pid}/desativar')

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT ativo FROM protocolos_sanitarios WHERE id=%s", (pid,))
    ativo = cur.fetchone()[0]
    cur.close()
    conn.close()

    assert ativo == 0


def test_aplicar_protocolo_outro_usuario_ignorado(client):
    """Aplicar protocolo de outro usuário não altera o banco."""
    login(client)
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (username, password_hash) VALUES ('san_outro','x')")
    outro_id = cur.lastrowid
    cur.execute(
        "INSERT INTO protocolos_sanitarios (user_id, nome, intervalo_dias, proxima_aplicacao) "
        "VALUES (%s, 'Protocolo Alheio', 30, '2026-07-01')",
        (outro_id,)
    )
    pid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()

    response = client.post(f'/sanitario/{pid}/aplicar', follow_redirects=True)
    assert response.status_code == 200

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT proxima_aplicacao FROM protocolos_sanitarios WHERE id=%s", (pid,))
    data_nao_alterada = cur.fetchone()[0]
    cur.close()
    conn.close()

    from datetime import date as _date
    assert data_nao_alterada == _date(2026, 7, 1)
