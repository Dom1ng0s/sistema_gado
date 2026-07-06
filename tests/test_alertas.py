"""
Testes de Fase 6.2 — Alertas por email proativos.

Estratégia: smoke tests com SMTP desabilitado (sem MAIL_USERNAME no ambiente de teste).
Verifica que as funções não lançam exceção e não chamam send se não há dados.
"""
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def disable_smtp(monkeypatch):
    """Garante que nenhum email real seja enviado durante os testes."""
    monkeypatch.setenv('MAIL_USERNAME', '')
    monkeypatch.setenv('MAIL_PASSWORD', '')


def test_verificar_contas_vencendo_sem_dados(app, db_setup):
    """verificar_contas_vencendo não lança exceção com banco vazio."""
    from utils.alertas import verificar_contas_vencendo
    verificar_contas_vencendo(app)   # não deve levantar


def test_verificar_protocolos_vencendo_sem_dados(app, db_setup):
    """verificar_protocolos_vencendo não lança exceção com banco vazio."""
    from utils.alertas import verificar_protocolos_vencendo
    verificar_protocolos_vencendo(app)


def test_verificar_estoque_critico_sem_dados(app, db_setup):
    """verificar_estoque_critico não lança exceção com banco vazio."""
    from utils.alertas import verificar_estoque_critico
    verificar_estoque_critico(app)


def test_send_alert_contas_nao_envia_sem_smtp():
    """send_alert_contas retorna silenciosamente quando SMTP não está configurado."""
    from utils.email_service import send_alert_contas
    contas = [("Ração", 1500.0, "2026-06-20")]
    send_alert_contas("test@example.com", contas)   # não deve lançar


def test_send_alert_protocolo_nao_envia_sem_smtp():
    """send_alert_protocolo retorna silenciosamente quando SMTP não está configurado."""
    from utils.email_service import send_alert_protocolo
    protocolos = [("Febre Aftosa", "2026-06-18")]
    send_alert_protocolo("test@example.com", protocolos)


def test_send_alert_estoque_nao_envia_sem_smtp():
    """send_alert_estoque retorna silenciosamente quando SMTP não está configurado."""
    from utils.email_service import send_alert_estoque
    produtos = [("Ivomec", 5.0, "ml", None, 0)]
    send_alert_estoque("test@example.com", produtos)


def test_verificar_contas_chama_send_quando_ha_dados(app, db_setup):
    """verificar_contas_vencendo chama send_alert_contas quando há conta vencendo."""
    import itertools
    from werkzeug.security import generate_password_hash
    import db_config as dbc

    seq = itertools.count(88000)
    n = next(seq)
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash, email) VALUES (%s, %s, %s)",
        (f"alerta_u{n}", generate_password_hash("x"), f"alerta{n}@test.com")
    )
    uid = cur.lastrowid
    cur.execute(
        "INSERT INTO financial_schedule "
        "(user_id, descricao, valor, vencimento, status) "
        "VALUES (%s, 'Ração', 2000.00, CURDATE(), 'pendente')",
        (uid,)
    )
    conn.commit(); cur.close(); conn.close()

    with patch('utils.email_service._send') as mock_send:
        mock_send.return_value = None
        # Precisa que MAIL_USERNAME esteja set para _send ser chamado
        import os
        with patch.dict(os.environ, {'MAIL_USERNAME': 'x', 'MAIL_PASSWORD': 'y'}):
            from utils.alertas import verificar_contas_vencendo
            verificar_contas_vencendo(app)
        mock_send.assert_called_once()

    # cleanup
    conn2 = dbc.get_db_connection()
    cur2 = conn2.cursor()
    cur2.execute("DELETE FROM financial_schedule WHERE user_id=%s", (uid,))
    cur2.execute("DELETE FROM usuarios WHERE id=%s", (uid,))
    conn2.commit(); cur2.close(); conn2.close()


def test_verificar_contas_vencendo_agrupa_por_usuario(app, db_setup):
    """A query agrupada não deve misturar as contas de usuários diferentes."""
    import itertools
    from werkzeug.security import generate_password_hash
    import db_config as dbc

    seq = itertools.count(89000)
    n1, n2 = next(seq), next(seq)
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash, email) VALUES (%s, %s, %s)",
        (f"alerta_u{n1}", generate_password_hash("x"), f"alerta{n1}@test.com")
    )
    uid1 = cur.lastrowid
    cur.execute(
        "INSERT INTO usuarios (username, password_hash, email) VALUES (%s, %s, %s)",
        (f"alerta_u{n2}", generate_password_hash("x"), f"alerta{n2}@test.com")
    )
    uid2 = cur.lastrowid
    cur.execute(
        "INSERT INTO financial_schedule (user_id, descricao, valor, vencimento, status) "
        "VALUES (%s, 'Ração', 2000.00, CURDATE(), 'pendente')",
        (uid1,)
    )
    cur.execute(
        "INSERT INTO financial_schedule (user_id, descricao, valor, vencimento, status) "
        "VALUES (%s, 'Sal Mineral', 500.00, CURDATE(), 'pendente')",
        (uid2,)
    )
    conn.commit(); cur.close(); conn.close()

    with patch('utils.email_service.send_alert_contas') as mock_send:
        from utils.alertas import verificar_contas_vencendo
        verificar_contas_vencendo(app)
        assert mock_send.call_count == 2
        chamadas = {c.args[0]: c.args[1] for c in mock_send.call_args_list}
        assert chamadas[f"alerta{n1}@test.com"][0][0] == 'Ração'
        assert chamadas[f"alerta{n2}@test.com"][0][0] == 'Sal Mineral'

    conn2 = dbc.get_db_connection()
    cur2 = conn2.cursor()
    cur2.execute("DELETE FROM financial_schedule WHERE user_id IN (%s, %s)", (uid1, uid2))
    cur2.execute("DELETE FROM usuarios WHERE id IN (%s, %s)", (uid1, uid2))
    conn2.commit(); cur2.close(); conn2.close()
