import smtplib
import ssl
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send_welcome_email(to_email: str, username: str) -> None:
    mail_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(os.getenv('MAIL_PORT', 587))
    mail_user = os.getenv('MAIL_USERNAME')
    mail_pass = os.getenv('MAIL_PASSWORD')
    mail_from = os.getenv('MAIL_FROM', mail_user)

    if not mail_user or not mail_pass:
        raise RuntimeError("MAIL_USERNAME e MAIL_PASSWORD não configurados no .env")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Bem-vindo ao SGG — Sistema de Gestão de Gado'
    msg['From'] = mail_from
    msg['To'] = to_email

    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#EAF3DE;font-family:'DM Sans',sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 16px;">
          <table width="480" cellpadding="0" cellspacing="0"
                 style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(59,109,17,.12);">
            <tr>
              <td style="background:#3B6D11;padding:28px 32px;">
                <p style="margin:0;color:#fff;font-size:20px;font-weight:600;">SGG &mdash; Sistema de Gado</p>
              </td>
            </tr>
            <tr>
              <td style="padding:36px 32px;">
                <h2 style="margin:0 0 8px;color:#1C1C1A;font-size:24px;font-weight:700;">
                  Bem-vindo, {username}! 🐄
                </h2>
                <p style="margin:0 0 24px;color:#4A4A46;font-size:15px;line-height:1.7;">
                  Sua conta no <strong>SGG</strong> foi criada com sucesso.<br>
                  Agora você tem acesso a todas as ferramentas para gerir sua fazenda com eficiência:
                </p>
                <table cellpadding="0" cellspacing="0" style="margin:0 0 28px;width:100%;">
                  <tr>
                    <td style="padding:10px 0;border-bottom:1px solid #F0EDE6;color:#3B6D11;font-size:14px;">
                      ✔ Controle de rebanho e pesagens
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:10px 0;border-bottom:1px solid #F0EDE6;color:#3B6D11;font-size:14px;">
                      ✔ Gestão financeira e fluxo de caixa
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:10px 0;border-bottom:1px solid #F0EDE6;color:#3B6D11;font-size:14px;">
                      ✔ Controle de pastos e lotação
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:10px 0;color:#3B6D11;font-size:14px;">
                      ✔ Estoque de medicamentos e insumos
                    </td>
                  </tr>
                </table>
                <p style="margin:0;color:#888780;font-size:13px;line-height:1.6;">
                  Em caso de dúvidas, responda este email.<br>
                  Bom trabalho na gestão da sua pecuária!
                </p>
              </td>
            </tr>
            <tr>
              <td style="background:#F7F6F2;padding:16px 32px;text-align:center;">
                <p style="margin:0;color:#B0AEA6;font-size:12px;">SGG — Sistema de Gestão de Gado</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, 'html'))

    context = ssl.create_default_context()
    with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(mail_user, mail_pass)
        server.sendmail(mail_from, to_email, msg.as_string())


# ── Helpers internos ───────────────────────────────────────────────────────

def _get_smtp_config():
    user = os.getenv('MAIL_USERNAME')
    pwd  = os.getenv('MAIL_PASSWORD')
    return {
        'server': os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
        'port':   int(os.getenv('MAIL_PORT', 587)),
        'user':   user,
        'pwd':    pwd,
        'from':   os.getenv('MAIL_FROM', user),
    }


def _send(to_email: str, subject: str, html: str) -> None:
    cfg = _get_smtp_config()
    if not cfg['user'] or not cfg['pwd']:
        logger.debug("MAIL não configurado — alerta ignorado.")
        return
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = cfg['from']
    msg['To'] = to_email
    msg.attach(MIMEText(html, 'html'))
    ctx = ssl.create_default_context()
    with smtplib.SMTP(cfg['server'], cfg['port'], timeout=10) as s:
        s.ehlo(); s.starttls(context=ctx)
        s.login(cfg['user'], cfg['pwd'])
        s.sendmail(cfg['from'], to_email, msg.as_string())


# ── Alertas proativos ──────────────────────────────────────────────────────

def send_alert_contas(to_email: str, contas: list) -> None:
    rows = ''.join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #F0EDE6;'>{c[0]}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #F0EDE6;text-align:right;'>R$ {float(c[1]):,.2f}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #F0EDE6;text-align:center;'>{c[2]}</td></tr>"
        for c in contas
    )
    html = f"""
    <html><body style="font-family:'DM Sans',sans-serif;background:#EAF3DE;padding:32px;">
      <table width="520" style="background:#fff;border-radius:10px;overflow:hidden;margin:0 auto;">
        <tr><td style="background:#3B6D11;padding:20px 28px;">
          <p style="margin:0;color:#fff;font-size:18px;font-weight:600;">SGG — Contas a Vencer</p>
        </td></tr>
        <tr><td style="padding:28px;">
          <p style="margin:0 0 16px;color:#1C1C1A;">As seguintes contas vencem nos próximos <strong>3 dias</strong>:</p>
          <table width="100%" style="border-collapse:collapse;">
            <tr style="background:#F7F6F2;">
              <th style="padding:8px;text-align:left;">Descrição</th>
              <th style="padding:8px;text-align:right;">Valor</th>
              <th style="padding:8px;text-align:center;">Vencimento</th>
            </tr>{rows}
          </table>
        </td></tr>
      </table>
    </body></html>"""
    _send(to_email, 'SGG — Contas a vencer nos próximos 3 dias', html)


def send_alert_protocolo(to_email: str, protocolos: list) -> None:
    rows = ''.join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #F0EDE6;'>{p[0]}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #F0EDE6;text-align:center;'>{p[1]}</td></tr>"
        for p in protocolos
    )
    html = f"""
    <html><body style="font-family:'DM Sans',sans-serif;background:#EAF3DE;padding:32px;">
      <table width="520" style="background:#fff;border-radius:10px;overflow:hidden;margin:0 auto;">
        <tr><td style="background:#3B6D11;padding:20px 28px;">
          <p style="margin:0;color:#fff;font-size:18px;font-weight:600;">SGG — Protocolos Sanitários</p>
        </td></tr>
        <tr><td style="padding:28px;">
          <p style="margin:0 0 16px;color:#1C1C1A;">Os seguintes protocolos vencem em até <strong>7 dias</strong>:</p>
          <table width="100%" style="border-collapse:collapse;">
            <tr style="background:#F7F6F2;">
              <th style="padding:8px;text-align:left;">Protocolo</th>
              <th style="padding:8px;text-align:center;">Data</th>
            </tr>{rows}
          </table>
        </td></tr>
      </table>
    </body></html>"""
    _send(to_email, 'SGG — Protocolos sanitários vencendo em breve', html)


def _validade_html(p) -> str:
    if p[4]:
        return "<strong style='color:#C0392B'>Vencido</strong>"
    return str(p[3]) if p[3] else '—'


def send_alert_estoque(to_email: str, produtos: list) -> None:
    rows = ''.join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #F0EDE6;'>{p[0]}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #F0EDE6;text-align:right;'>{float(p[1]):.3f} {p[2]}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #F0EDE6;text-align:center;'>{_validade_html(p)}</td></tr>"
        for p in produtos
    )
    html = f"""
    <html><body style="font-family:'DM Sans',sans-serif;background:#EAF3DE;padding:32px;">
      <table width="520" style="background:#fff;border-radius:10px;overflow:hidden;margin:0 auto;">
        <tr><td style="background:#3B6D11;padding:20px 28px;">
          <p style="margin:0;color:#fff;font-size:18px;font-weight:600;">SGG — Estoque Crítico</p>
        </td></tr>
        <tr><td style="padding:28px;">
          <p style="margin:0 0 16px;color:#1C1C1A;">Produtos abaixo do mínimo ou com validade vencida:</p>
          <table width="100%" style="border-collapse:collapse;">
            <tr style="background:#F7F6F2;">
              <th style="padding:8px;text-align:left;">Produto</th>
              <th style="padding:8px;text-align:right;">Saldo</th>
              <th style="padding:8px;text-align:center;">Validade</th>
            </tr>{rows}
          </table>
        </td></tr>
      </table>
    </body></html>"""
    _send(to_email, 'SGG — Estoque crítico detectado', html)


def send_reset_code(to_email: str, code: str) -> None:
    mail_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(os.getenv('MAIL_PORT', 587))
    mail_user = os.getenv('MAIL_USERNAME')
    mail_pass = os.getenv('MAIL_PASSWORD')
    mail_from = os.getenv('MAIL_FROM', mail_user)

    if not mail_user or not mail_pass:
        raise RuntimeError("MAIL_USERNAME e MAIL_PASSWORD não configurados no .env")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Código de Verificação — SGG Sistema de Gado'
    msg['From'] = mail_from
    msg['To'] = to_email

    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#EAF3DE;font-family:'DM Sans',sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 16px;">
          <table width="400" cellpadding="0" cellspacing="0"
                 style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(59,109,17,.12);">
            <tr>
              <td style="background:#3B6D11;padding:24px 32px;">
                <p style="margin:0;color:#fff;font-size:20px;font-weight:600;">SGG &mdash; Sistema de Gado</p>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <h2 style="margin:0 0 12px;color:#1C1C1A;font-size:22px;">Recuperação de Senha</h2>
                <p style="margin:0 0 24px;color:#4A4A46;font-size:15px;line-height:1.6;">
                  Use o código abaixo para redefinir sua senha.<br>
                  Ele expira em <strong>15 minutos</strong>.
                </p>
                <div style="text-align:center;margin:0 0 28px;">
                  <span style="display:inline-block;font-size:42px;font-weight:700;letter-spacing:12px;
                               color:#3B6D11;background:#EAF3DE;padding:18px 28px;border-radius:10px;
                               border:2px solid #C0DD97;">
                    {code}
                  </span>
                </div>
                <p style="margin:0;color:#888780;font-size:13px;line-height:1.5;">
                  Se você não solicitou este código, ignore este email.<br>
                  Sua senha permanece inalterada.
                </p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, 'html'))

    context = ssl.create_default_context()
    with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(mail_user, mail_pass)
        server.sendmail(mail_from, to_email, msg.as_string())
