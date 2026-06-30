"""
E2E baseline — Cadastro em lote de animais.

Captura o comportamento ATUAL: preencher a tabela com 3 animais
e submeter deve persistir os dados e exibir mensagem de sucesso.

C-3: erro de validação deve preservar todos os dados do formulário.
"""


def test_cadastro_lote_com_tres_animais(logged_in_page, live_server):
    """Preenche formulário com 3 animais e verifica mensagem de sucesso."""
    page = logged_in_page

    page.goto(f"{live_server}/cadastro-lote")

    # Campos do cabeçalho do lote
    page.locator("#prefixoInput").fill("E2E-LOTE-NOVO")
    page.locator("input[name='data_compra']").fill("2024-06-15")
    page.locator("input[name='valor_arroba']").fill("260.00")

    # Gera 3 linhas na tabela dinâmica
    page.locator("#qtdInput").fill("3")
    page.locator("button:has-text('GERAR TABELA')").click()

    # Aguarda as 3 linhas aparecerem no tbody
    page.wait_for_selector("#gradeBody tr", timeout=5_000)
    assert page.locator("#gradeBody tr").count() == 3, "Tabela não gerou 3 linhas"

    # Preenche brinco e peso para cada animal
    brincos = page.locator("input[name='brincos[]']")
    pesos = page.locator("input[name='pesos[]']")
    for i in range(3):
        brincos.nth(i).fill(f"E2E-N-{i + 1:02d}")
        pesos.nth(i).fill("340.5")

    # O botão de submit só aparece após gerarGrade()
    page.locator("#btnSalvar").click()

    # Verifica mensagem de sucesso (fundo verde, não vermelho)
    page.wait_for_selector(".alert", timeout=10_000)
    alert = page.locator(".alert").first
    assert alert.is_visible()

    alert_text = alert.text_content() or ""
    # Mensagem atual: "Lote 'E2E-LOTE-NOVO' salvo com 3 animais e pesos individuais!"
    assert "E2E-LOTE-NOVO" in alert_text, f"Código do lote ausente na mensagem: {alert_text!r}"
    assert "3" in alert_text, f"Contagem de animais ausente na mensagem: {alert_text!r}"

    # Confirma que não é alerta de erro (fundo vermelho)
    # Erros contêm 'Erro' ou '❌' no texto
    assert "Erro" not in alert_text and "❌" not in alert_text, (
        f"Mensagem de erro inesperada: {alert_text!r}"
    )


def test_cadastro_lote_preserva_dados_em_erro_validacao(logged_in_page, live_server):
    """C-3: dados do formulário devem ser preservados quando ocorre erro de validação.

    Fluxo: preenche cabeçalho + 3 animais → limpa um brinco (bypassando HTML5) →
    submete → verifica mensagem de erro → verifica que cabeçalho e animais
    restantes foram restaurados no formulário re-renderizado.
    """
    page = logged_in_page
    page.goto(f"{live_server}/cadastro-lote")

    # Preenche campos do cabeçalho
    page.locator("#prefixoInput").fill("LOTE-PRESERVA")
    page.locator("input[name='data_compra']").fill("2024-08-20")
    page.locator("input[name='valor_arroba']").fill("250.00")
    page.locator("input[name='descricao']").fill("Teste preservacao de dados")

    # Gera 3 linhas na tabela dinâmica
    page.locator("#qtdInput").fill("3")
    page.locator("button:has-text('GERAR TABELA')").click()
    page.wait_for_selector("#gradeBody tr", timeout=5_000)
    assert page.locator("#gradeBody tr").count() == 3

    # Preenche brincos e pesos
    brincos = page.locator("input[name='brincos[]']")
    pesos   = page.locator("input[name='pesos[]']")
    for i in range(3):
        brincos.nth(i).fill(f"PRES-{i + 1:02d}")
        pesos.nth(i).fill("320.0")

    # Remove restrições HTML5 para forçar erro server-side com brinco vazio
    page.evaluate(
        "document.querySelectorAll('input[name=\"brincos[]\"]')"
        ".forEach(i => i.removeAttribute('required'))"
    )
    page.evaluate(
        "document.querySelectorAll('input[name=\"pesos[]\"]')"
        ".forEach(i => i.removeAttribute('required'))"
    )

    # Limpa o primeiro brinco → servidor deve rejeitar com "Todos os brincos devem ser preenchidos"
    brincos.nth(0).fill("")

    page.locator("#btnSalvar").click()

    # Aguarda a resposta de erro
    page.wait_for_selector(".alert", timeout=10_000)
    alert = page.locator(".alert").first
    assert alert.is_visible()
    alert_text = alert.text_content() or ""
    assert "brinco" in alert_text.lower() or "Todos" in alert_text, (
        f"Mensagem de erro de validação esperada, obteve: {alert_text!r}"
    )

    # Campos do cabeçalho devem estar preservados
    assert page.locator("input[name='codigo_lote']").input_value() == "LOTE-PRESERVA", \
        "codigo_lote não foi preservado"
    assert page.locator("input[name='data_compra']").input_value() == "2024-08-20", \
        "data_compra não foi preservada"
    assert page.locator("input[name='valor_arroba']").input_value() == "250.00", \
        "valor_arroba não foi preservado"

    # A tabela deve ter sido restaurada com 3 linhas (via JS restore)
    page.wait_for_selector("#gradeBody tr", timeout=5_000)
    assert page.locator("#gradeBody tr").count() == 3, \
        "Tabela de animais não foi restaurada com 3 linhas após erro de validação"

    # O segundo e terceiro brincos devem estar preservados
    assert page.locator("input[name='brincos[]']").nth(1).input_value() == "PRES-02", \
        "Brinco do 2º animal não foi preservado"
    assert page.locator("input[name='brincos[]']").nth(2).input_value() == "PRES-03", \
        "Brinco do 3º animal não foi preservado"
    assert page.locator("input[name='pesos[]']").nth(1).input_value() == "320.0", \
        "Peso do 2º animal não foi preservado"
