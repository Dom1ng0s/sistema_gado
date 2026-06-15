import logging
from db_config import get_db_cursor

logger = logging.getLogger(__name__)


def _get_usuarios_com_email():
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, email FROM usuarios WHERE email IS NOT NULL AND email != ''")
        return cursor.fetchall()


def verificar_contas_vencendo(app):
    with app.app_context():
        try:
            from utils.email_service import send_alert_contas
            usuarios = _get_usuarios_com_email()
            for uid, email in usuarios:
                with get_db_cursor() as cursor:
                    cursor.execute(
                        "SELECT descricao, valor, vencimento FROM financial_schedule "
                        "WHERE user_id = %s AND status = 'pendente' AND deleted_at IS NULL "
                        "AND vencimento <= DATE_ADD(CURDATE(), INTERVAL 3 DAY) "
                        "ORDER BY vencimento ASC",
                        (uid,)
                    )
                    contas = cursor.fetchall()
                if contas:
                    send_alert_contas(email, contas)
        except Exception as e:
            logger.error(f"Alerta contas: {e}", exc_info=True)


def verificar_protocolos_vencendo(app):
    with app.app_context():
        try:
            from utils.email_service import send_alert_protocolo
            usuarios = _get_usuarios_com_email()
            for uid, email in usuarios:
                with get_db_cursor() as cursor:
                    cursor.execute(
                        "SELECT nome, proxima_aplicacao FROM protocolos_sanitarios "
                        "WHERE user_id = %s AND ativo = 1 "
                        "AND proxima_aplicacao <= DATE_ADD(CURDATE(), INTERVAL 7 DAY) "
                        "ORDER BY proxima_aplicacao ASC",
                        (uid,)
                    )
                    protocolos = cursor.fetchall()
                if protocolos:
                    send_alert_protocolo(email, protocolos)
        except Exception as e:
            logger.error(f"Alerta protocolos: {e}", exc_info=True)


def verificar_estoque_critico(app):
    with app.app_context():
        try:
            from utils.email_service import send_alert_estoque
            usuarios = _get_usuarios_com_email()
            for uid, email in usuarios:
                with get_db_cursor() as cursor:
                    cursor.execute(
                        "SELECT nome, saldo_atual, unidade, proxima_validade, tem_vencido "
                        "FROM vw_saldo_estoque "
                        "WHERE user_id = %s AND (abaixo_minimo = 1 OR tem_vencido = 1)",
                        (uid,)
                    )
                    produtos = cursor.fetchall()
                if produtos:
                    send_alert_estoque(email, produtos)
        except Exception as e:
            logger.error(f"Alerta estoque: {e}", exc_info=True)
