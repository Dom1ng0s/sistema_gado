/* ============================================================
   SGG — Kit de interface
   Carregado em todas as páginas autenticadas (via base.html).

   Concentra o comportamento que antes estava duplicado (ou faltando)
   em cada template: feedback de carregamento, validação inline,
   diálogos com foco preso, toasts e busca com autocomplete.
   ============================================================ */
(function () {
  'use strict';

  /* ── utilidades ──────────────────────────────────────────── */

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* ── formatação pt-BR ─────────────────────────────────────
     O produtor lê "0,842", não "0.842". O ponto como separador decimal é
     leitura de máquina; dentro da interface tudo sai em português. */
  function num(valor, casas) {
    var n = typeof valor === 'number' ? valor : parseFloat(valor);
    if (!isFinite(n)) return '—';
    return n.toLocaleString('pt-BR', {
      minimumFractionDigits: casas == null ? 0 : casas,
      maximumFractionDigits: casas == null ? 3 : casas
    });
  }

  /* Plural de "animal" é "animais" — nunca "animalis". */
  function animais(n) { return n === 1 ? '1 animal' : num(n) + ' animais'; }

  window.sggNum     = num;
  window.sggAnimais = animais;

  /* ══════════════════════════════════════════════════════════
     TEMA DOS GRÁFICOS (ECharts)
     Os gráficos usavam a paleta padrão do ECharts — azul e roxo, sem
     relação nenhuma com o resto do produto. Aqui eles passam a falar a
     mesma língua: verde para o rebanho, âmbar para dinheiro, vermelho só
     para o que está abaixo da meta.
     ══════════════════════════════════════════════════════════ */

  function tokenCor(nome, alternativa) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
    return v || alternativa;
  }

  function temaGrafico() {
    var tinta   = tokenCor('--n-700', '#33312A');
    var fraco   = tokenCor('--n-400', '#767260');
    var linha   = tokenCor('--n-100', '#EDEAE2');
    var fonte   = "Inter, system-ui, sans-serif";
    return {
      color: [
        tokenCor('--g-500', '#649628'), tokenCor('--a-300', '#F0B049'),
        tokenCor('--g-700', '#3B5C17'), tokenCor('--a-500', '#B87309'),
        tokenCor('--g-300', '#A3CB70'), tokenCor('--n-400', '#767260')
      ],
      backgroundColor: 'transparent',
      textStyle: { fontFamily: fonte, color: tinta },
      title:  { textStyle: { fontFamily: fonte, color: tinta, fontWeight: 600 } },
      legend: { textStyle: { fontFamily: fonte, color: fraco } },
      grid:   { borderColor: linha },
      categoryAxis: {
        axisLine:  { lineStyle: { color: linha } },
        axisTick:  { show: false },
        axisLabel: { color: fraco, fontFamily: fonte, fontSize: 11 },
        splitLine: { show: false }
      },
      valueAxis: {
        axisLine:  { show: false },
        axisTick:  { show: false },
        axisLabel: { color: fraco, fontFamily: fonte, fontSize: 11 },
        splitLine: { lineStyle: { color: linha, type: 'dashed' } }
      },
      tooltip: {
        backgroundColor: '#fff',
        borderColor: linha,
        borderWidth: 1,
        textStyle: { color: tinta, fontFamily: fonte, fontSize: 12 },
        extraCssText: 'box-shadow:0 8px 20px -6px rgba(42,38,26,.16);border-radius:10px;'
      },
      bar:  { itemStyle: { borderRadius: [4, 4, 0, 0] } },
      line: { symbolSize: 7, lineStyle: { width: 2.5 }, smooth: true },
      pie:  { itemStyle: { borderColor: '#fff', borderWidth: 2 } }
    };
  }

  var temaRegistrado = false;

  /* Substitui echarts.init() nos templates: registra o tema uma única vez e
     devolve a instância já temada. */
  window.sggGrafico = function (el, opcoes) {
    if (!window.echarts) return null;
    if (!temaRegistrado) {
      echarts.registerTheme('sgg', temaGrafico());
      temaRegistrado = true;
    }
    return echarts.init(el, 'sgg', opcoes);
  };

  var FOCUSABLE = [
    'a[href]', 'button:not([disabled])', 'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])', 'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  function focaveis(raiz) {
    return Array.prototype.filter.call(
      raiz.querySelectorAll(FOCUSABLE),
      function (el) { return el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement; }
    );
  }

  /* Prende o foco dentro de `caixa` e devolve uma função que solta e
     restaura o foco para onde ele estava. Sem isso, o Tab escapa do
     diálogo e o usuário de teclado "cai" atrás do overlay. */
  function prenderFoco(caixa, elementoInicial) {
    var anterior = document.activeElement;

    function onKeydown(e) {
      if (e.key !== 'Tab') return;
      var itens = focaveis(caixa);
      if (!itens.length) { e.preventDefault(); return; }
      var primeiro = itens[0], ultimo = itens[itens.length - 1];
      if (e.shiftKey && document.activeElement === primeiro) {
        e.preventDefault(); ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault(); primeiro.focus();
      }
    }

    document.addEventListener('keydown', onKeydown, true);
    (elementoInicial || focaveis(caixa)[0] || caixa).focus();

    return function soltar() {
      document.removeEventListener('keydown', onKeydown, true);
      if (anterior && typeof anterior.focus === 'function') anterior.focus();
    };
  }

  /* Marca elementos fora do diálogo como invisíveis ao leitor de tela. */
  function isolarFundo(caixa) {
    var irmaos = [];
    Array.prototype.forEach.call(document.body.children, function (el) {
      if (el === caixa || el.contains(caixa) || el.tagName === 'SCRIPT') return;
      irmaos.push([el, el.getAttribute('aria-hidden')]);
      el.setAttribute('aria-hidden', 'true');
    });
    return function () {
      irmaos.forEach(function (par) {
        if (par[1] === null) par[0].removeAttribute('aria-hidden');
        else par[0].setAttribute('aria-hidden', par[1]);
      });
    };
  }

  /* ══════════════════════════════════════════════════════════
     TOAST
     Erros usam role="alert" (anúncio imediato); sucesso e aviso usam
     status polido, para não interromper o que o leitor está lendo.
     ══════════════════════════════════════════════════════════ */

  var ICONES = {
    error:   '<svg class="icon icon-md" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 7v6M12 16.5v.01"/></svg>',
    success: '<svg class="icon icon-md" viewBox="0 0 24 24" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    warning: '<svg class="icon icon-md" viewBox="0 0 24 24" aria-hidden="true"><path d="m10.29 3.86-8.6 14.9A2 2 0 0 0 3.43 22h17.14a2 2 0 0 0 1.74-2.84l-8.6-14.9a2 2 0 0 0-3.42 0Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>'
  };

  var PREFIXO = { error: 'Erro:', success: 'Pronto:', warning: 'Atenção:' };

  window.sggToast = function (msg, tipo, opcoes) {
    tipo = tipo || 'error';
    opcoes = opcoes || {};
    var container = document.getElementById('sggToastContainer');
    if (!container) return;

    var t = document.createElement('div');
    t.className = 'toast toast-' + tipo;
    t.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
    t.innerHTML =
      '<span class="toast-icon" style="flex-shrink:0;color:var(--color-' +
        (tipo === 'error' ? 'danger' : tipo === 'success' ? 'success' : 'warning') + ');">' +
        (ICONES[tipo] || '') + '</span>' +
      '<span><span class="sr-only">' + (PREFIXO[tipo] || '') + ' </span>' + esc(msg) + '</span>' +
      '<button type="button" class="toast-close" aria-label="Dispensar aviso">&times;</button>';

    var fechado = false;
    function fechar() {
      if (fechado) return;
      fechado = true;
      t.style.transition = 'opacity 180ms ease';
      t.style.opacity = '0';
      setTimeout(function () { t.remove(); }, 200);
    }

    t.querySelector('.toast-close').addEventListener('click', fechar);
    container.appendChild(t);

    /* Erros não somem sozinhos: o usuário precisa poder ler e agir.
       Confirmações somem, porque a informação já cumpriu seu papel. */
    var vida = opcoes.duracao != null ? opcoes.duracao : (tipo === 'error' ? 0 : 5000);
    if (vida > 0) setTimeout(fechar, vida);

    return fechar;
  };

  /* ══════════════════════════════════════════════════════════
     CONFIRMAÇÃO
     Reservada a ações destrutivas e irreversíveis. Rótulo do botão diz
     o que vai acontecer ("Excluir animal"), não "OK".
     ══════════════════════════════════════════════════════════ */

  var confirmState = null;

  function iniciarConfirm() {
    var modal = document.getElementById('sggConfirmModal');
    if (!modal) return null;

    var titleEl = document.getElementById('sgg-confirm-title');
    var msgEl   = document.getElementById('sgg-confirm-msg');
    var btnOk   = document.getElementById('sgg-confirm-ok');
    var btnCan  = document.getElementById('sgg-confirm-cancel');

    function fechar() {
      modal.style.display = 'none';
      modal.setAttribute('aria-hidden', 'true');
      if (confirmState) {
        confirmState.soltarFoco();
        confirmState.restaurarFundo();
        confirmState = null;
      }
    }

    btnOk.addEventListener('click', function () {
      var cb = confirmState && confirmState.onConfirm;
      fechar();
      if (cb) cb();
    });
    btnCan.addEventListener('click', fechar);
    modal.addEventListener('click', function (e) { if (e.target === modal) fechar(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && confirmState) fechar();
    });

    /* Assinatura antiga sggConfirm(titulo, msg, cb) continua valendo;
       o 4º argumento é opcional. */
    window.sggConfirm = function (titulo, msg, onConfirm, opcoes) {
      opcoes = opcoes || {};
      titleEl.textContent = titulo || 'Confirmar';
      msgEl.textContent   = msg   || '';
      btnOk.textContent   = opcoes.confirmar || 'Confirmar';
      btnCan.textContent  = opcoes.cancelar  || 'Cancelar';
      btnOk.className     = 'btn ' + (opcoes.tom === 'primary' ? 'btn-primary' : 'btn-danger');

      modal.style.display = 'flex';
      modal.setAttribute('aria-hidden', 'false');

      confirmState = {
        onConfirm: onConfirm || null,
        restaurarFundo: isolarFundo(modal),
        /* Foco inicial em Cancelar: a saída segura é o padrão. */
        soltarFoco: prenderFoco(modal, btnCan)
      };
    };

    return fechar;
  }

  /* ══════════════════════════════════════════════════════════
     VALIDAÇÃO INLINE
     Mensagens em linguagem do usuário, com ícone e texto — nunca só a
     cor da borda. Valida ao sair do campo; depois do primeiro erro,
     revalida a cada tecla para que o acerto apareça na hora.
     ══════════════════════════════════════════════════════════ */

  function rotuloDe(campo) {
    var lbl = campo.labels && campo.labels[0];
    if (!lbl && campo.id && window.CSS && CSS.escape) {
      lbl = document.querySelector('label[for="' + CSS.escape(campo.id) + '"]');
    }
    var txt = lbl ? lbl.textContent : (campo.getAttribute('aria-label') || campo.name || 'este campo');
    return txt.replace(/\(opcional\)/gi, '').replace(/[*:]/g, '').trim().toLowerCase();
  }

  function mensagemDe(campo) {
    var v = campo.validity;
    var custom = campo.getAttribute('data-msg');
    var rot = rotuloDe(campo);

    if (v.valid) return '';
    if (custom) return custom;

    if (v.valueMissing) {
      if (campo.type === 'checkbox' || campo.type === 'radio') return 'Escolha uma opção para ' + rot + '.';
      if (campo.tagName === 'SELECT') return 'Selecione ' + rot + '.';
      return 'Informe ' + rot + '.';
    }
    if (v.typeMismatch) {
      if (campo.type === 'email') return 'Digite um e-mail completo, como nome@fazenda.com.br.';
      return 'O formato de ' + rot + ' não está correto.';
    }
    if (v.rangeUnderflow) return 'O menor valor aceito para ' + rot + ' é ' + campo.min + '.';
    if (v.rangeOverflow)  return 'O maior valor aceito para ' + rot + ' é ' + campo.max + '.';
    if (v.stepMismatch)   return 'Use no máximo duas casas decimais em ' + rot + '.';
    if (v.tooShort)       return 'Use ao menos ' + campo.minLength + ' caracteres em ' + rot + '.';
    if (v.tooLong)        return 'Use no máximo ' + campo.maxLength + ' caracteres em ' + rot + '.';
    if (v.patternMismatch) return 'O formato de ' + rot + ' não está correto.';
    if (v.badInput)       return 'Digite apenas números em ' + rot + '.';
    return 'Revise ' + rot + '.';
  }

  function caixaMsg(campo) {
    var id = (campo.id || campo.name || 'campo') + '-erro';
    var el = document.getElementById(id);
    if (!el) {
      el = document.createElement('p');
      el.id = id;
      el.className = 'field-msg';
      el.innerHTML =
        '<svg class="icon icon-sm" viewBox="0 0 24 24" aria-hidden="true">' +
        '<circle cx="12" cy="12" r="10"/><path d="M12 7v6M12 16.5v.01"/></svg><span></span>';
      var alvo = campo.closest('.form-group') || campo.parentNode;
      alvo.appendChild(el);
    }
    return el;
  }

  function marcarErro(campo, msg) {
    var box = caixaMsg(campo);
    box.querySelector('span').textContent = msg;
    box.classList.add('is-visible');
    campo.classList.add('is-invalid');
    campo.classList.remove('is-valid');
    campo.setAttribute('aria-invalid', 'true');

    var desc = (campo.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
    if (desc.indexOf(box.id) === -1) desc.push(box.id);
    campo.setAttribute('aria-describedby', desc.join(' '));
  }

  function limparErro(campo) {
    var box = document.getElementById((campo.id || campo.name || 'campo') + '-erro');
    if (box) box.classList.remove('is-visible');
    campo.classList.remove('is-invalid');
    campo.removeAttribute('aria-invalid');
    if (campo.value && campo.checkValidity()) campo.classList.add('is-valid');
    else campo.classList.remove('is-valid');
  }

  function validarCampo(campo) {
    if (campo.disabled || campo.type === 'hidden' || campo.hasAttribute('data-sem-validacao')) return true;
    /* Campo escondido por um toggle (ex.: bloco "nascido na fazenda") não
       deve bloquear o envio de um formulário em que ele nem aparece. */
    if (!campo.getClientRects().length) return true;

    /* Um campo decimal ainda em modo `text` não avalia min/max: devolve o tipo
       antes de checar, senão a validação sairia mais frouxa que o servidor.
       Nunca com o campo focado — trocar o tipo no meio da digitação apagaria
       o valor incompleto, que é justamente o que a troca existe para evitar. */
    if (campo.sggRestaurarTipo && document.activeElement !== campo) campo.sggRestaurarTipo();

    if (campo.checkValidity()) { limparErro(campo); return true; }
    marcarErro(campo, mensagemDe(campo));
    return false;
  }

  function ligarValidacao(form) {
    if (form.hasAttribute('novalidate')) return;      // o template valida por conta própria
    if (form.method && form.method.toLowerCase() === 'get') return;
    form.setAttribute('novalidate', '');              // assume o controle das mensagens
    form.dataset.sggValidado = '1';

    form.addEventListener('blur', function (e) {
      var c = e.target;
      if (c.matches && c.matches('input, select, textarea')) validarCampo(c);
    }, true);

    form.addEventListener('input', function (e) {
      var c = e.target;
      if (c.matches && c.matches('input, select, textarea') && c.classList.contains('is-invalid')) {
        validarCampo(c);
      }
    });
  }

  function validarForm(form) {
    var campos = form.querySelectorAll('input, select, textarea');
    var primeiroInvalido = null;
    for (var i = 0; i < campos.length; i++) {
      if (!validarCampo(campos[i]) && !primeiroInvalido) primeiroInvalido = campos[i];
    }
    if (primeiroInvalido) {
      primeiroInvalido.focus();
      primeiroInvalido.scrollIntoView({ block: 'center', behavior: 'smooth' });
      var n = form.querySelectorAll('.is-invalid').length;
      window.sggToast(
        n === 1 ? 'Um campo precisa ser corrigido antes de salvar.'
                : n + ' campos precisam ser corrigidos antes de salvar.',
        'error', { duracao: 6000 }
      );
      return false;
    }
    return true;
  }

  /* ══════════════════════════════════════════════════════════
     ESTADO DE CARREGAMENTO NO ENVIO
     ══════════════════════════════════════════════════════════ */

  function marcarEnviando(form) {
    var btn = form.querySelector('button[type="submit"], input[type="submit"]');
    if (!btn || btn.classList.contains('btn-loading')) return;
    btn.dataset.rotuloOriginal = btn.textContent;
    btn.classList.add('btn-loading');
    btn.setAttribute('aria-busy', 'true');
    btn.disabled = true;
  }

  function limparEnviando(escopo) {
    (escopo || document).querySelectorAll('.btn-loading').forEach(function (btn) {
      btn.classList.remove('btn-loading');
      btn.removeAttribute('aria-busy');
      btn.disabled = false;
    });
  }
  window.sggLimparCarregando = limparEnviando;

  /* Duas fases, de propósito.

     Captura (antes de qualquer handler do template): valida. Se reprovar,
     `stopPropagation` impede que o handler do próprio template rode e
     deixe um spinner girando para sempre.

     Bolha (depois de todos os handlers): só então marca "enviando", e
     apenas se ninguém cancelou o envio — as telas de pesagem e venda em
     lote validam por conta própria e chamam preventDefault. */
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.method && form.method.toLowerCase() === 'get') return;

    restaurarDecimais(form);

    if (form.dataset.sggValidado === '1' && !validarForm(form)) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (e.defaultPrevented) return;
    if (form.method && form.method.toLowerCase() === 'get') return;
    if (form.hasAttribute('data-sem-loading')) return;
    marcarEnviando(form);
  });

  /* Voltar pelo histórico restaura a página do cache com o botão ainda
     travado — destrava. */
  window.addEventListener('pageshow', function () { limparEnviando(); });

  /* ══════════════════════════════════════════════════════════
     ENTRADA DECIMAL
     O produtor digita "1500,50". Em <input type="number"> a vírgula é
     descartada pelo navegador e o campo fica vazio sem explicação.
     Converte a vírgula em ponto no ato, preservando type=number (e,
     portanto, todo cálculo que já lê parseFloat(campo.value)).
     ══════════════════════════════════════════════════════════ */

  /* "1.234,56" → "1234.56". Aceita o formato brasileiro e devolve o formato
     que o servidor (e todo parseFloat já existente) espera. */
  function normalizarDecimal(bruto) {
    var s = String(bruto).replace(/\s|R\$/g, '');
    if (s.indexOf(',') !== -1) s = s.replace(/\./g, '').replace(',', '.');
    s = s.replace(/[^0-9.\-]/g, '');
    var partes = s.split('.');
    if (partes.length > 2) s = partes.shift() + '.' + partes.join('');
    return s;
  }

  /* Enquanto o campo está focado ele vira `text`; ao sair, volta a `number`.

     Motivo: em <input type="number"> o navegador descarta qualquer valor
     intermediário que não seja um número completo. Digitar a vírgula de
     "280,50" zera o campo inteiro em locales que não usam vírgula — o
     usuário vê o que digitou sumir sem explicação. Como `text`, o valor
     intermediário sobrevive; ao desfocar ele já está normalizado com ponto,
     então min/max/step nativos e os cálculos que leem parseFloat(campo.value)
     continuam funcionando exatamente como antes. */
  function ligarDecimal(campo) {
    if (campo.dataset.sggDecimal === '1') return;
    campo.dataset.sggDecimal = '1';
    campo.setAttribute('inputmode', 'decimal');

    function paraTexto() {
      if (campo.type === 'number') campo.type = 'text';
    }

    function paraNumero() {
      if (campo.type !== 'text') return;
      var normalizado = normalizarDecimal(campo.value);
      campo.type = 'number';
      campo.value = normalizado;
    }
    campo.sggRestaurarTipo = paraNumero;

    campo.addEventListener('focus', paraTexto);
    campo.addEventListener('blur', paraNumero);

    campo.addEventListener('input', function () {
      if (campo.type !== 'text') return;
      var limpo = normalizarDecimal(campo.value);
      if (limpo === campo.value) return;
      var pos = campo.selectionStart;
      var delta = campo.value.length - limpo.length;
      campo.value = limpo;
      try { campo.setSelectionRange(pos - delta, pos - delta); } catch (e) { /* sem seleção */ }
    });

    campo.addEventListener('paste', function (e) {
      var txt = (e.clipboardData || window.clipboardData).getData('text');
      if (!/[,.]/.test(txt)) return;
      e.preventDefault();
      paraTexto();
      campo.value = normalizarDecimal(txt);
      campo.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }

  /* Devolve todo campo decimal ao tipo `number` antes de validar/enviar —
     senão o campo ainda focado escaparia de min/max nativos. */
  function restaurarDecimais(escopo) {
    (escopo || document).querySelectorAll('[data-sgg-decimal="1"]').forEach(function (c) {
      if (c.sggRestaurarTipo) c.sggRestaurarTipo();
    });
  }
  window.sggNormalizarDecimal = normalizarDecimal;

  /* ══════════════════════════════════════════════════════════
     BUSCA COM AUTOCOMPLETE E TOLERÂNCIA A ERRO DE DIGITAÇÃO
     ══════════════════════════════════════════════════════════ */

  /* Distância de edição limitada — para sugerir "A-001" quando o
     usuário digitou "A-010" ou "a001". Corta cedo acima do limite. */
  function distancia(a, b, limite) {
    if (Math.abs(a.length - b.length) > limite) return limite + 1;
    var linha = [], i, j;
    for (j = 0; j <= b.length; j++) linha[j] = j;
    for (i = 1; i <= a.length; i++) {
      var ant = linha[0], melhor = (linha[0] = i);
      for (j = 1; j <= b.length; j++) {
        var atual = linha[j];
        linha[j] = Math.min(
          linha[j] + 1,
          linha[j - 1] + 1,
          ant + (a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1)
        );
        ant = atual;
        if (linha[j] < melhor) melhor = linha[j];
      }
      if (melhor > limite) return limite + 1;
    }
    return linha[b.length];
  }

  var RE_ACENTOS = new RegExp('[\u0300-\u036f]', 'g');
  var RE_BOM     = new RegExp('^\ufeff');

  function normalizar(s) {
    return String(s).toLowerCase().normalize('NFD').replace(RE_ACENTOS, '');
  }

  function parseCSV(texto) {
    var linhas = [], campo = '', linha = [], dentroAspas = false;
    texto = texto.replace(RE_BOM, '');
    for (var i = 0; i < texto.length; i++) {
      var c = texto[i];
      if (dentroAspas) {
        if (c === '"') {
          if (texto[i + 1] === '"') { campo += '"'; i++; }
          else dentroAspas = false;
        } else campo += c;
      } else if (c === '"') dentroAspas = true;
      else if (c === ',') { linha.push(campo); campo = ''; }
      else if (c === '\n') { linha.push(campo); linhas.push(linha); linha = []; campo = ''; }
      else if (c !== '\r') campo += c;
    }
    if (campo || linha.length) { linha.push(campo); linhas.push(linha); }
    return linhas;
  }

  var CACHE_KEY = 'sgg:animais:v1';

  function carregarAnimais() {
    try {
      var cru = sessionStorage.getItem(CACHE_KEY);
      if (cru) return Promise.resolve(JSON.parse(cru));
    } catch (e) { /* sessionStorage bloqueado — segue sem cache */ }

    return fetch('/api/v1/export/animais.csv', { headers: { 'Accept': 'text/csv' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (txt) {
        var linhas = parseCSV(txt);
        linhas.shift();                                   // cabeçalho
        var itens = linhas.filter(function (l) { return l[1]; }).map(function (l) {
          return { brinco: l[1], raca: l[3] || '', peso: l[7] || '', norm: normalizar(l[1]) };
        });
        try { sessionStorage.setItem(CACHE_KEY, JSON.stringify(itens)); } catch (e) {}
        return itens;
      });
  }

  function enviarBusca(campo) {
    var form = campo.form;
    if (!form) return;
    if (form.requestSubmit) form.requestSubmit();
    else form.submit();
  }

  function ligarCombobox(campo) {
    var caixa = campo.closest('.combo');
    var lista = caixa && caixa.querySelector('.combo__list');
    if (!lista) return;

    var itens = null, opcoes = [], ativo = -1, carregando = false;

    campo.setAttribute('role', 'combobox');
    campo.setAttribute('aria-expanded', 'false');
    campo.setAttribute('aria-autocomplete', 'list');
    campo.setAttribute('aria-controls', lista.id);
    campo.setAttribute('autocomplete', 'off');

    var vivo = document.getElementById('combo-status');

    function garantirDados() {
      if (itens || carregando) return Promise.resolve(itens);
      carregando = true;
      return carregarAnimais().then(function (d) { itens = d; return d; })
        .catch(function () { itens = []; return itens; })
        .then(function (d) { carregando = false; return d; });
    }

    function fechar() {
      lista.hidden = true;
      campo.setAttribute('aria-expanded', 'false');
      campo.removeAttribute('aria-activedescendant');
      ativo = -1;
    }

    function destacar(texto, termo) {
      var pos = normalizar(texto).indexOf(normalizar(termo));
      if (pos === -1 || !termo) return esc(texto);
      return esc(texto.slice(0, pos)) + '<mark>' + esc(texto.slice(pos, pos + termo.length)) +
             '</mark>' + esc(texto.slice(pos + termo.length));
    }

    function render(termo) {
      if (!opcoes.length) { fechar(); return; }
      lista.innerHTML = opcoes.map(function (o, i) {
        var meta = [o.raca, o.peso ? o.peso + ' kg' : ''].filter(Boolean).join(' · ');
        return '<li class="combo__opt" role="option" id="opt-' + i + '" aria-selected="false">' +
               '<span>' + destacar(o.brinco, termo) + '</span>' +
               (meta ? '<span class="combo__opt-meta">' + esc(meta) + '</span>' : '') + '</li>';
      }).join('');
      lista.hidden = false;
      campo.setAttribute('aria-expanded', 'true');
      if (vivo) {
        vivo.textContent = opcoes.length + (opcoes.length === 1 ? ' animal encontrado.' : ' animais encontrados.');
      }
    }

    function marcarAtivo(i) {
      var lis = lista.querySelectorAll('.combo__opt');
      lis.forEach(function (li) { li.setAttribute('aria-selected', 'false'); });
      if (i < 0 || i >= lis.length) { campo.removeAttribute('aria-activedescendant'); return; }
      lis[i].setAttribute('aria-selected', 'true');
      lis[i].scrollIntoView({ block: 'nearest' });
      campo.setAttribute('aria-activedescendant', lis[i].id);
    }

    function buscar(termo) {
      var t = normalizar(termo.trim());
      if (!t) { opcoes = []; fechar(); return; }

      var comeca = [], contem = [], perto = [];
      var limite = t.length <= 3 ? 1 : 2;   // tolerância cresce com o termo

      for (var i = 0; i < itens.length; i++) {
        var it = itens[i];
        if (it.norm.indexOf(t) === 0) comeca.push(it);
        else if (it.norm.indexOf(t) !== -1) contem.push(it);
        else if (comeca.length + contem.length < 8 && distancia(t, it.norm, limite) <= limite) perto.push(it);
        if (comeca.length >= 8) break;
      }

      opcoes = comeca.concat(contem, perto).slice(0, 8);
      render(termo.trim());
    }

    campo.addEventListener('focus', garantirDados);

    campo.addEventListener('input', function () {
      var v = campo.value;
      garantirDados().then(function () { buscar(v); });
    });

    campo.addEventListener('keydown', function (e) {
      if (lista.hidden) {
        if (e.key === 'ArrowDown') { garantirDados().then(function () { buscar(campo.value); }); }
        return;
      }
      var lis = lista.querySelectorAll('.combo__opt');
      if (e.key === 'ArrowDown')      { e.preventDefault(); ativo = (ativo + 1) % lis.length; marcarAtivo(ativo); }
      else if (e.key === 'ArrowUp')   { e.preventDefault(); ativo = (ativo - 1 + lis.length) % lis.length; marcarAtivo(ativo); }
      else if (e.key === 'Home')      { e.preventDefault(); ativo = 0; marcarAtivo(ativo); }
      else if (e.key === 'End')       { e.preventDefault(); ativo = lis.length - 1; marcarAtivo(ativo); }
      else if (e.key === 'Escape')    { e.preventDefault(); fechar(); }
      else if (e.key === 'Enter' && ativo >= 0) {
        e.preventDefault();
        campo.value = opcoes[ativo].brinco;
        fechar();
        enviarBusca(campo);
      }
    });

    lista.addEventListener('mousedown', function (e) {
      var li = e.target.closest('.combo__opt');
      if (!li) return;
      e.preventDefault();
      var i = Array.prototype.indexOf.call(lista.children, li);
      campo.value = opcoes[i].brinco;
      fechar();
      enviarBusca(campo);
    });

    document.addEventListener('click', function (e) {
      if (!caixa.contains(e.target)) fechar();
    });
  }

  /* Busca sem resultado: oferece o brinco mais próximo do que foi digitado. */
  function sugerirCorrecao() {
    var alvo = document.getElementById('sgg-sugestao');
    if (!alvo) return;
    var termo = alvo.dataset.termo || '';
    if (!termo) return;

    carregarAnimais().then(function (itens) {
      var t = normalizar(termo), melhor = null, melhorD = 99;
      var limite = Math.max(1, Math.min(3, Math.floor(t.length / 2)));
      itens.forEach(function (it) {
        var d = distancia(t, it.norm, limite);
        if (d < melhorD) { melhorD = d; melhor = it; }
      });
      if (!melhor || melhorD > limite) return;

      var url = new URL(window.location.href);
      url.searchParams.set('busca', melhor.brinco);
      alvo.innerHTML = 'Nenhum resultado para <b>' + esc(termo) + '</b>. Você quis dizer ' +
                       '<a href="' + esc(url.pathname + url.search) + '"><b>' + esc(melhor.brinco) + '</b></a>?';
      alvo.hidden = false;
    }).catch(function () { /* silencioso: a busca simples continua valendo */ });
  }

  /* ══════════════════════════════════════════════════════════
     CHROME DA PÁGINA
     ══════════════════════════════════════════════════════════ */

  function ligarScrollEdge() {
    var ticking = false;
    function atualizar() {
      document.body.classList.toggle('is-scrolled', window.scrollY > 4);
      ticking = false;
    }
    window.addEventListener('scroll', function () {
      if (!ticking) { ticking = true; requestAnimationFrame(atualizar); }
    }, { passive: true });
    atualizar();
  }

  function ligarNav() {
    var toggle = document.getElementById('nav-toggle');
    var links  = document.getElementById('nav-links');
    if (toggle && links) {
      toggle.addEventListener('click', function () {
        var aberto = links.classList.toggle('open');
        this.setAttribute('aria-expanded', aberto);
      });
      links.querySelectorAll('.nav-link').forEach(function (link) {
        link.addEventListener('click', function () {
          links.classList.remove('open');
          toggle.setAttribute('aria-expanded', 'false');
        });
      });
    }

    var dropdowns = [];
    document.querySelectorAll('.nav-dropdown').forEach(function (dd) {
      var trigger = dd.querySelector('.nav-dropdown-toggle');
      var menu    = dd.querySelector('.nav-dropdown-menu');
      if (trigger && menu) dropdowns.push({ trigger: trigger, menu: menu });
    });
    if (!dropdowns.length) return;

    function fechar(dd) {
      dd.menu.classList.remove('open');
      dd.trigger.setAttribute('aria-expanded', 'false');
    }

    dropdowns.forEach(function (dd) {
      dd.trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        dropdowns.forEach(function (o) { if (o !== dd) fechar(o); });
        var aberto = dd.menu.classList.toggle('open');
        dd.trigger.setAttribute('aria-expanded', aberto);
        if (aberto) {
          var primeiro = dd.menu.querySelector('a, button');
          if (primeiro) primeiro.focus();
        }
      });

      /* Seta para baixo abre e entra no menu; Escape volta ao gatilho. */
      dd.trigger.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown') { e.preventDefault(); dd.trigger.click(); }
      });
      dd.menu.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { fechar(dd); dd.trigger.focus(); }
      });
    });

    document.addEventListener('click', function (e) {
      dropdowns.forEach(function (dd) {
        if (!dd.menu.contains(e.target) && !dd.trigger.contains(e.target)) fechar(dd);
      });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') dropdowns.forEach(fechar);
    });
  }

  /* Menu de ações genérico (.action-menu) — substitui o handler que cada
     página reimplementava. */
  function ligarActionMenus() {
    var menus = [];
    document.querySelectorAll('.action-menu').forEach(function (raiz) {
      var trigger = raiz.querySelector('.action-menu__trigger');
      var painel  = raiz.querySelector('.action-menu__panel');
      if (!trigger || !painel) return;
      var m = { raiz: raiz, trigger: trigger, painel: painel };
      menus.push(m);

      function fechar(devolverFoco) {
        painel.classList.remove('open');
        trigger.setAttribute('aria-expanded', 'false');
        if (devolverFoco) trigger.focus();
      }
      m.fechar = fechar;

      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        menus.forEach(function (o) { if (o !== m) o.fechar(false); });
        var aberto = !painel.classList.contains('open');
        painel.classList.toggle('open', aberto);
        trigger.setAttribute('aria-expanded', aberto ? 'true' : 'false');
        if (aberto) {
          var primeiro = painel.querySelector('[role="menuitem"]');
          /* O painel sai de visibility:hidden. focus() num elemento ainda
             invisível é ignorado, então força o recálculo de estilo antes. */
          void painel.offsetHeight;
          if (primeiro) primeiro.focus();
        }
      });

      painel.addEventListener('keydown', function (e) {
        var itens = Array.prototype.slice.call(painel.querySelectorAll('[role="menuitem"]'));
        var i = itens.indexOf(document.activeElement);
        if (e.key === 'ArrowDown') { e.preventDefault(); itens[(i + 1) % itens.length].focus(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); itens[(i - 1 + itens.length) % itens.length].focus(); }
        else if (e.key === 'Escape') { e.preventDefault(); fechar(true); }
      });

      painel.addEventListener('click', function (e) {
        if (e.target.closest('[role="menuitem"]')) fechar(false);
      });
    });

    if (!menus.length) return;
    document.addEventListener('click', function (e) {
      menus.forEach(function (m) { if (!m.raiz.contains(e.target)) m.fechar(false); });
    });
  }

  /* ══════════════════════════════════════════════════════════
     BOOT
     ══════════════════════════════════════════════════════════ */

  function iniciar() {
    iniciarConfirm();
    ligarNav();
    ligarActionMenus();
    ligarScrollEdge();

    document.querySelectorAll('form').forEach(ligarValidacao);
    document.querySelectorAll('[data-decimal], input[step]').forEach(function (c) {
      if (c.type === 'number') ligarDecimal(c);
    });
    document.querySelectorAll('.combo input[type="text"], .combo input[type="search"]').forEach(ligarCombobox);
    sugerirCorrecao();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }

  /* Exposto para templates que criam campos dinamicamente (cadastro em lote). */
  window.sggLigarValidacao = ligarValidacao;
  window.sggValidarCampo   = validarCampo;
  window.sggEscapar        = esc;
  window.sggPrenderFoco    = prenderFoco;
  window.sggIsolarFundo    = isolarFundo;
})();
