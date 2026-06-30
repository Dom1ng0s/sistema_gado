"""
E2E baseline — Fluxo de login.

Captura o comportamento ATUAL como linha de base de regressão.
Qualquer alteração futura no fluxo de autenticação que quebre
estes testes indica uma regressão que precisa de atenção.
"""

from .conftest import E2E_USER, E2E_PASS


def test_login_sucesso(page, live_server):
    """Login com credenciais válidas redireciona para /painel."""
    page.goto(f"{live_server}/login")

    page.locator("#username").fill(E2E_USER)
    page.locator("#password").fill(E2E_PASS)
    page.locator("#loginForm button[type='submit']").click()

    page.wait_for_url("**/painel", timeout=10_000)
    assert "/painel" in page.url


def test_login_credenciais_erradas(page, live_server):
    """Senha incorreta mantém o usuário na página de login com mensagem de erro."""
    page.goto(f"{live_server}/login")

    page.locator("#username").fill(E2E_USER)
    page.locator("#password").fill("senha_completamente_errada_xyz")
    page.locator("#loginForm button[type='submit']").click()

    # Deve permanecer em /login — nunca redirecionar para /painel
    page.wait_for_selector(".flash-error", timeout=8_000)
    assert "/painel" not in page.url
    assert "/login" in page.url or page.url.endswith(f":{5099}/")  # pode ser redirect para /login

    error_el = page.locator(".flash-error")
    assert error_el.is_visible()
    error_text = error_el.text_content() or ""
    # Mensagem atual: "Usuário ou senha incorretos"
    assert len(error_text.strip()) > 0, "Mensagem de erro está vazia"
