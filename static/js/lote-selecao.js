// Widget de seleção em lote: checkbox por linha, marcar/desmarcar todos, contagem.
// Cada página injeta onCheck/onUncheck para o comportamento específico do campo de peso.
const KG_POR_ARROBA = 30;

function initSelecaoLote({ onCheck, onUncheck } = {}) {
  const checks       = document.querySelectorAll('.animal-check');
  const marcarTodos  = document.getElementById('marcar-todos');
  const btnConfirmar = document.getElementById('btn-confirmar');
  const contagemTxt  = document.getElementById('contagem-txt');

  function toggleAnimal(checkbox) {
    const id  = checkbox.value;
    const row = checkbox.closest('tr');
    const pw  = document.getElementById('pw-' + id);
    const inp = document.getElementById('peso-' + id);
    const hid = document.getElementById('hid-' + id);

    if (checkbox.checked) {
      row.classList.add('selecionado');
      pw.classList.add('visivel');
      inp.disabled = false;
      hid.disabled = false;
      if (onCheck) onCheck(id, inp);
    } else {
      row.classList.remove('selecionado');
      pw.classList.remove('visivel');
      inp.disabled = true;
      hid.disabled = true;
      if (onUncheck) onUncheck(id, inp);
    }
    atualizarEstado();
  }

  function atualizarEstado() {
    const selecionados = document.querySelectorAll('.animal-check:checked').length;
    contagemTxt.textContent = selecionados + ' selecionado(s)';
    btnConfirmar.disabled = selecionados === 0;
    marcarTodos.indeterminate = selecionados > 0 && selecionados < checks.length;
    marcarTodos.checked = selecionados === checks.length && checks.length > 0;
  }

  checks.forEach(chk => {
    chk.addEventListener('change', () => toggleAnimal(chk));
  });

  marcarTodos.addEventListener('change', function () {
    const marcarTudo = this.checked;
    checks.forEach(chk => {
      chk.checked = marcarTudo;
      toggleAnimal(chk);
    });
  });

  return { checks, marcarTodos, btnConfirmar, contagemTxt, toggleAnimal, atualizarEstado };
}
