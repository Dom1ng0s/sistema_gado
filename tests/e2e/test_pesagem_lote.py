"""
E2E baseline — Pesagem em lote (fluxo completo).

Captura o comportamento ATUAL: selecionar todos os animais de um lote,
preencher os pesos e confirmar deve registrar as pesagens e exibir
mensagem de sucesso com a contagem correta.

Depende do lote e dos 3 animais pré-carregados pelo fixture e2e_db.
"""


def test_pesagem_lote_fluxo_completo(logged_in_page, live_server, e2e_db):
    """Seleciona 3 animais, preenche pesos e verifica confirmação de sucesso."""
    page = logged_in_page
    lote_id = e2e_db["lote_id"]

    # Navega diretamente com lote pré-selecionado para evitar a interação com
    # o select que submete um GET form (onchange) — comportamento mais estável
    page.goto(f"{live_server}/pesagem-lote?lote_id={lote_id}")

    # Os 3 animais do lote devem estar listados
    page.wait_for_selector(".animal-check", timeout=8_000)
    checkboxes = page.locator(".animal-check")
    assert checkboxes.count() == 3, (
        f"Esperava 3 animais no lote, encontrou {checkboxes.count()}"
    )

    # Preenche a data antes de selecionar animais (validação JS exige data)
    page.locator("#data-pesagem").fill("2024-06-20")

    # "Marcar todos" habilita os campos de peso via JS
    page.locator("#marcar-todos").click()

    # Aguarda os inputs de peso ficarem habilitados (a remoção do atributo
    # disabled ocorre no handler change, que é síncrono, mas damos margem)
    page.wait_for_function("() => !document.querySelector('.peso-input').disabled")

    # Preenche um peso para cada animal
    peso_inputs = page.locator(".peso-input")
    assert peso_inputs.count() == 3
    for i in range(3):
        peso_inputs.nth(i).fill("395.0")

    # O botão de confirmação deve estar habilitado após selecionar animais
    # (click() já aguarda a actionability — visível, habilitado e estável —
    # "enabled" não é um state válido para Locator.wait_for)
    btn = page.locator("#btn-confirmar")
    btn.click()

    # Aguarda a mensagem de sucesso (classe alert-success renderizada pela rota)
    page.wait_for_selector(".alert-success", timeout=10_000)
    success_el = page.locator(".alert-success")
    assert success_el.is_visible()

    success_text = success_el.text_content() or ""
    # Mensagem atual: "3 pesagem(ns) registrada(s) com sucesso."
    assert "3" in success_text, f"Contagem de pesagens ausente na mensagem: {success_text!r}"
    assert "sucesso" in success_text.lower(), f"Palavra 'sucesso' ausente: {success_text!r}"
