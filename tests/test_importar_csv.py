"""
Issue #9 — importar_csv passa a inserir em chunks via executemany em vez de
1 INSERT por linha, com fallback linha a linha quando um chunk falha.
Rota: POST /importar-csv
"""
import io
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc

_seq = itertools.count(12000)


def _n():
    return next(_seq)


def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"csv_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    cur.execute("DELETE p FROM pesagens p JOIN animais a ON p.animal_id = a.id WHERE a.user_id = %s", (user_id,))
    cur.execute("DELETE FROM animais WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit(); cur.close(); conn.close()


def _login(client, uid):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM usuarios WHERE id = %s", (uid,))
    username = cur.fetchone()[0]
    cur.close(); conn.close()
    client.post("/login", data={"username": username, "password": "x"}, follow_redirects=True)


def _upload(client, csv_text):
    data = {'arquivo': (io.BytesIO(csv_text.encode('utf-8')), 'animais.csv')}
    return client.post('/importar-csv', data=data, content_type='multipart/form-data')


def test_importar_csv_insere_linhas_validas_em_lote(app):
    uid = _make_user()
    try:
        with app.test_client() as client:
            _login(client, uid)
            csv_text = "brinco,sexo,data_compra,peso_kg,valor_arroba\n"
            for i in range(5):
                csv_text += f"CSVA{_n()},M,2024-01-01,250,150\n"
            r = _upload(client, csv_text)
            assert r.status_code == 200
            assert b"5" in r.data  # inseridos: 5

            conn = dbc.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM animais WHERE user_id = %s", (uid,))
            assert cur.fetchone()[0] == 5
            cur.close(); conn.close()
    finally:
        _purge(uid)


def test_importar_csv_brinco_duplicado_no_proprio_arquivo_reporta_conflito(app):
    """Duas linhas do mesmo arquivo com o mesmo brinco: o chunk inteiro falha no
    executemany (unique constraint), o fallback linha a linha insere a primeira
    e reporta a segunda como conflito — sem perder a primeira."""
    uid = _make_user()
    try:
        with app.test_client() as client:
            _login(client, uid)
            brinco_dup = f"CSVDUP{_n()}"
            csv_text = (
                "brinco,sexo,data_compra,peso_kg,valor_arroba\n"
                f"{brinco_dup},M,2024-01-01,250,150\n"
                f"{brinco_dup},F,2024-01-02,260,150\n"
            )
            r = _upload(client, csv_text)
            assert r.status_code == 200

            conn = dbc.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM animais WHERE user_id = %s AND brinco = %s", (uid, brinco_dup))
            assert cur.fetchone()[0] == 1  # só a primeira ocorrência foi inserida
            cur.close(); conn.close()
            assert "conflito".encode('utf-8') in r.data or "já existe".encode('utf-8') in r.data
    finally:
        _purge(uid)
