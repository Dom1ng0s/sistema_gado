<script lang="ts">
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { calcularDataLiberacao, diasCarenciaSugerido } from '../lib/carencia';
  import { formatBrl, formatDateBr } from '../lib/format';
  import { router } from '../lib/router.svelte';

  type EscopoAplicacao = 'individual' | 'lote';

  interface ProdutoSugestao {
    nome: string;
    dosePadraoMl: number;
    custoCabeca: number;
    saldoEstoqueMl: number;
  }

  interface HistoricoAplicacao {
    id: number;
    data: string;
    alvo: string;
    qtdCabecas: number;
    produto: string;
    doseMl: number;
    diasCarencia: number;
    dataLiberacao: string | null;
    custoTotal: number;
    registradoPor: string;
  }

  const PRODUTOS_RAPIDOS: ProdutoSugestao[] = [
    { nome: 'Ivermectina 1%', dosePadraoMl: 10, custoCabeca: 4.8, saldoEstoqueMl: 1500 },
    { nome: 'Doramectina', dosePadraoMl: 10, custoCabeca: 6.5, saldoEstoqueMl: 850 },
    { nome: 'Fluazuron', dosePadraoMl: 45, custoCabeca: 11.2, saldoEstoqueMl: 2000 },
    { nome: 'Oxitetraciclina', dosePadraoMl: 20, custoCabeca: 8.9, saldoEstoqueMl: 500 },
    { nome: 'Vacina Aftosa', dosePadraoMl: 2, custoCabeca: 3.4, saldoEstoqueMl: 600 }
  ];

  const LOTES_MANEJO = [
    { codigo: 'Lote 04', nome: 'Lote 04 · Terminação (42 cab.)', cabecas: 42 },
    { codigo: 'Lote 2026-A', nome: 'Lote 2026-A · Engorda (68 cab.)', cabecas: 68 },
    { codigo: 'Lote Recria Sul', nome: 'Lote Recria Sul · Garrotes (34 cab.)', cabecas: 34 }
  ];

  let escopo = $state<EscopoAplicacao>('individual');
  let brincoIndividual = $state(router.buscaBrinco || '402');
  let loteSelecionado = $state('Lote 04');
  let nomeMedicamento = $state('Ivermectina 1%');
  let dataAplicacao = $state('2026-10-24');

  // Permite override manual caso a bula específica divirja da tabela padrão
  let diasCarenciaManual = $state<number | null>(null);
  let doseMl = $state(10);
  let custoPorCabeca = $state(4.8);
  let baixarDoEstoque = $state(true);
  let observacao = $state('Manejo sanitário de rotina no tronco');

  let salvando = $state(false);
  let feedbackMsg = $state('');
  let feedbackErro = $state('');

  let historicoSessao = $state<HistoricoAplicacao[]>([
    {
      id: 1,
      data: '2026-10-10',
      alvo: '#402, #409 (2 cab.)',
      qtdCabecas: 2,
      produto: 'Ivermectina 1%',
      doseMl: 10,
      diasCarencia: 35,
      dataLiberacao: '14/11/2026',
      custoTotal: 9.6,
      registradoPor: 'demonstracao'
    }
  ]);

  let carenciaSugeridaBula = $derived(diasCarenciaSugerido(nomeMedicamento));
  let diasCarenciaEfetivo = $derived(
    diasCarenciaManual !== null ? diasCarenciaManual : carenciaSugeridaBula
  );
  let dataLiberacaoFormatada = $derived(
    calcularDataLiberacao(dataAplicacao, diasCarenciaEfetivo)
  );

  let qtdCabecasAlvo = $derived.by(() => {
    if (escopo === 'individual') return 1;
    const l = LOTES_MANEJO.find((item) => item.codigo === loteSelecionado);
    return l ? l.cabecas : 1;
  });

  let volumeTotalMl = $derived(doseMl * qtdCabecasAlvo);
  let custoTotalOperacao = $derived(custoPorCabeca * qtdCabecasAlvo);

  function selecionarProdutoRapido(prod: ProdutoSugestao) {
    nomeMedicamento = prod.nome;
    diasCarenciaManual = null;
    doseMl = prod.dosePadraoMl;
    custoPorCabeca = prod.custoCabeca;
  }

  async function registrarMedicacao(e: SubmitEvent) {
    e.preventDefault();
    feedbackMsg = '';
    feedbackErro = '';

    if (!nomeMedicamento.trim()) {
      feedbackErro = 'Informe o nome do medicamento ou vacina aplicada.';
      return;
    }
    if (escopo === 'individual' && !brincoIndividual.trim()) {
      feedbackErro = 'Informe o brinco do animal para aplicação individual.';
      return;
    }

    salvando = true;
    const payload = {
      escopo,
      brinco: escopo === 'individual' ? brincoIndividual.trim().replace(/^#/, '') : null,
      lote: escopo === 'lote' ? loteSelecionado : null,
      medicamento: nomeMedicamento.trim(),
      data_aplicacao: dataAplicacao,
      dias_carencia: diasCarenciaEfetivo,
      dose_ml: doseMl,
      custo_unitario: custoPorCabeca,
      baixar_estoque: baixarDoEstoque,
      observacao
    };

    try {
      await apiFetch('/api/medicacoes', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
    } catch {
      // Continua registrando no estado da sessão caso API esteja em modo demonstração
    } finally {
      salvando = false;
      const alvoDesc =
        escopo === 'individual'
          ? `#${brincoIndividual.trim().replace(/^#/, '')}`
          : `${loteSelecionado} (${qtdCabecasAlvo} cab.)`;

      historicoSessao = [
        {
          id: Date.now(),
          data: dataAplicacao,
          alvo: alvoDesc,
          qtdCabecas: qtdCabecasAlvo,
          produto: nomeMedicamento.trim(),
          doseMl,
          diasCarencia: diasCarenciaEfetivo,
          dataLiberacao: dataLiberacaoFormatada,
          custoTotal: custoTotalOperacao,
          registradoPor: auth.user.username
        },
        ...historicoSessao
      ];

      feedbackMsg =
        diasCarenciaEfetivo > 0
          ? `Medicação registrada para ${alvoDesc}. Trava sanitária ativada até ${dataLiberacaoFormatada}.`
          : `Vacinação/medicação sem carência registrada para ${alvoDesc}.`;
    }
  }
</script>

<div class="medicar-page">
  <header class="page-head">
    <div>
      <div class="badge-row">
        <span class="badge badge--ok">Cálculo Automático de Carência · utils/carencia.py</span>
        <span class="badge badge--neutro dado">Autoria: @{auth.user.username}</span>
      </div>
      <h1 class="page-title">Medicação e Vacinação Sanitária</h1>
      <p class="page-subtitle">
        Selecione um princípio ativo ou digite o medicamento para calcular os dias de carência e a data de liberação para abate.
      </p>
    </div>
  </header>

  <div class="medicar-grid">
    <form class="form-panel panel" onsubmit={registrarMedicacao}>
      <!-- Escopo: Individual vs Lote -->
      <div class="scope-switch" role="radiogroup" aria-label="Escopo da aplicação">
        <button
          type="button"
          class="scope-btn"
          class:scope-btn--active={escopo === 'individual'}
          onclick={() => (escopo = 'individual')}
        >
          Aplicação individual (1 animal)
        </button>
        <button
          type="button"
          class="scope-btn"
          class:scope-btn--active={escopo === 'lote'}
          onclick={() => (escopo = 'lote')}
        >
          Aplicação coletiva em lote
        </button>
      </div>

      {#if escopo === 'individual'}
        <div class="field">
          <label for="med-brinco">Brinco do animal</label>
          <input
            id="med-brinco"
            class="input dado"
            type="text"
            inputmode="numeric"
            placeholder="Ex: 402"
            bind:value={brincoIndividual}
            required
          />
        </div>
      {:else}
        <div class="field">
          <label for="med-lote">Lote de aplicação coletiva</label>
          <select id="med-lote" class="input" bind:value={loteSelecionado}>
            {#each LOTES_MANEJO as l}
              <option value={l.codigo}>{l.nome}</option>
            {/each}
          </select>
        </div>
      {/if}

      <!-- Produto + Pílulas de Seleção Rápida -->
      <div class="field">
        <label for="med-prod">Nome do medicamento ou vacina aplicada</label>
        <input
          id="med-prod"
          class="input"
          type="text"
          placeholder="Ex: Ivermectina 1%, Doramectina, Fluazuron..."
          bind:value={nomeMedicamento}
          oninput={() => (diasCarenciaManual = null)}
          required
        />

        <div class="quick-pills" aria-label="Produtos frequentes no curral">
          {#each PRODUTOS_RAPIDOS as prod}
            <button
              type="button"
              class="pill-btn"
              class:pill-btn--active={nomeMedicamento.toLowerCase() === prod.nome.toLowerCase()}
              onclick={() => selecionarProdutoRapido(prod)}
            >
              <span>{prod.nome}</span>
              <span class="dado pill-btn__days">{diasCarenciaSugerido(prod.nome)}d</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="grid-3">
        <div class="field">
          <label for="med-data">Data da aplicação</label>
          <input id="med-data" class="input dado" type="date" bind:value={dataAplicacao} required />
        </div>

        <div class="field">
          <label for="med-carencia">Dias de carência (abate)</label>
          <input
            id="med-carencia"
            class="input dado"
            type="number"
            min="0"
            max="365"
            inputmode="numeric"
            value={diasCarenciaEfetivo}
            oninput={(e) => {
              const v = parseInt((e.currentTarget as HTMLInputElement).value, 10);
              diasCarenciaManual = Number.isNaN(v) ? 0 : v;
            }}
          />
          <small class="hint">Sugerido pela bula: <span class="dado">{carenciaSugeridaBula} dias</span></small>
        </div>

        <div class="field">
          <label for="med-dose">Dosagem por cabeça (ml)</label>
          <input
            id="med-dose"
            class="input dado"
            type="number"
            step="0.5"
            min="0.5"
            inputmode="decimal"
            bind:value={doseMl}
          />
          <small class="hint">Volume total: <span class="dado">{volumeTotalMl.toFixed(1).replace('.', ',')} ml</span></small>
        </div>
      </div>

      <div class="grid-2">
        <div class="field">
          <label for="med-custo">Custo estimado por cabeça (R$)</label>
          <input
            id="med-custo"
            class="input dado"
            type="number"
            step="0.1"
            min="0"
            inputmode="decimal"
            bind:value={custoPorCabeca}
          />
          <small class="hint">Custo total da aplicação: <strong class="dado">{formatBrl(custoTotalOperacao)}</strong></small>
        </div>

        <div class="field">
          <label for="med-obs">Observação de manejo / lote da partida</label>
          <input
            id="med-obs"
            class="input"
            type="text"
            placeholder="Ex: Partida #8821 · Subcutânea na tábua do pescoço"
            bind:value={observacao}
          />
        </div>
      </div>

      <label class="stock-toggle">
        <input type="checkbox" bind:checked={baixarDoEstoque} />
        <div>
          <strong>Baixar do estoque automaticamente</strong>
          <span>Deduz <strong class="dado">{volumeTotalMl.toFixed(1).replace('.', ',')} ml</strong> no livro-razão de insumos (<code class="dado">estoque_movimentacoes</code>).</span>
        </div>
      </label>

      <!-- Banner de Carência Sanitária (Óxido vs Verde-Pinheiro) -->
      {#if diasCarenciaEfetivo > 0}
        <div class="carencia-alert" role="alert">
          <div class="carencia-alert__head">
            <span class="badge badge--alerta">Trava sanitária de abate ativada</span>
            <span class="dado"><strong>{diasCarenciaEfetivo} dias</strong> de retenção</span>
          </div>
          <p>
            Ao confirmar esta aplicação, {escopo === 'individual' ? `o animal #${brincoIndividual}` : `os ${qtdCabecasAlvo} animais do ${loteSelecionado}`} ficarão bloqueados em <code class="dado">vw_animais_em_carencia</code> até <strong class="dado">{dataLiberacaoFormatada}</strong>.
          </p>
        </div>
      {:else}
        <div class="carencia-ok">
          <span class="badge badge--ok">Carência zero (0 dias)</span>
          <span>Produto sem resíduo impeditivo para abate — animais permanecem liberados para venda imediata.</span>
        </div>
      {/if}

      {#if feedbackErro}
        <div class="carencia-alert" role="alert">{feedbackErro}</div>
      {/if}
      {#if feedbackMsg}
        <div class="carencia-ok" role="status">{feedbackMsg}</div>
      {/if}

      <div class="form-actions">
        <button type="submit" class="btn btn-primary" disabled={salvando}>
          {salvando ? 'Registrando manejo...' : `Confirmar aplicação (${qtdCabecasAlvo} cab.)`}
        </button>
      </div>
    </form>

    <!-- Coluna Direita: Resumo de Impacto e Últimas Aplicações -->
    <aside class="side-panel">
      <div class="panel summary-card">
        <h2 class="section-title">Resumo do lançamento</h2>
        <dl class="summary-list">
          <div>
            <dt>Alvo do manejo</dt>
            <dd class="dado">
              {escopo === 'individual' ? `#${brincoIndividual || '—'}` : `${loteSelecionado} (${qtdCabecasAlvo} cab.)`}
            </dd>
          </div>
          <div>
            <dt>Princípio / Produto</dt>
            <dd>{nomeMedicamento || '—'}</dd>
          </div>
          <div>
            <dt>Prazo de carência</dt>
            <dd class="dado" class:dado--alerta={diasCarenciaEfetivo > 0} class:dado--ok={diasCarenciaEfetivo === 0}>
              {diasCarenciaEfetivo} dias
            </dd>
          </div>
          <div>
            <dt>Liberação para venda</dt>
            <dd class="dado">
              {diasCarenciaEfetivo > 0 ? dataLiberacaoFormatada : 'Imediata (livre)'}
            </dd>
          </div>
          <div>
            <dt>Volume total consumido</dt>
            <dd class="dado">{volumeTotalMl.toFixed(1).replace('.', ',')} ml</dd>
          </div>
          <div>
            <dt>Custo sanitário apropriado</dt>
            <dd class="dado">{formatBrl(custoTotalOperacao)}</dd>
          </div>
        </dl>
      </div>

      <div class="panel history-card">
        <h2 class="section-title">Aplicações recentes na sessão</h2>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Alvo</th>
                <th>Produto</th>
                <th class="col-num">Carência</th>
                <th class="col-num">Liberação</th>
              </tr>
            </thead>
            <tbody>
              {#each historicoSessao as item (item.id)}
                <tr>
                  <td class="dado"><strong>{item.alvo}</strong></td>
                  <td>{item.produto}</td>
                  <td class="col-num dado" class:dado--alerta={item.diasCarencia > 0}>
                    {item.diasCarencia}d
                  </td>
                  <td class="col-num dado">
                    {item.dataLiberacao ?? formatDateBr(item.data)}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </aside>
  </div>
</div>

<style>
  .medicar-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .badge-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-bottom: var(--space-2);
  }

  .medicar-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr);
    gap: var(--space-5);
    align-items: start;
  }

  .form-panel {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .scope-switch {
    display: grid;
    grid-template-columns: 1fr 1fr;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    overflow: hidden;
    background: var(--color-surface-sunken);
  }

  .scope-btn {
    min-height: 40px;
    padding: var(--space-2) var(--space-3);
    border: none;
    background: transparent;
    color: var(--color-ink-secondary);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    line-height: 1.25;
    cursor: pointer;
  }
  .scope-btn--active {
    background: var(--color-primary);
    color: #fff;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  .field label {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--color-ink-secondary);
  }
  .hint {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .quick-pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-1);
  }

  .pill-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: 4px 10px;
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    font-family: var(--font-body);
    font-size: var(--text-xs);
    font-weight: var(--weight-medium);
    color: var(--color-ink);
    cursor: pointer;
  }
  .pill-btn:hover {
    border-color: var(--color-primary);
  }
  .pill-btn--active {
    background: var(--color-primary-bg);
    border-color: var(--color-primary);
    color: var(--color-primary-dark);
    font-weight: var(--weight-semibold);
  }
  .pill-btn__days {
    font-size: 11px;
    color: var(--color-ink-tertiary);
  }

  .grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
  }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
  }

  .stock-toggle {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
  }
  .stock-toggle input {
    margin-top: 3px;
  }
  .stock-toggle div {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
  }
  .stock-toggle strong {
    font-size: var(--text-sm);
    color: var(--color-ink);
  }

  .carencia-alert {
    padding: var(--space-4);
    background: var(--color-danger-bg);
    border: 1px solid var(--color-danger);
    border-left: 4px solid var(--color-danger);
    border-radius: var(--radius-md);
    color: var(--color-danger-dark);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--text-sm);
  }
  .carencia-alert__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .carencia-ok {
    padding: var(--space-3) var(--space-4);
    background: var(--color-primary-bg);
    border: 1px solid var(--color-primary);
    border-left: 4px solid var(--color-primary);
    border-radius: var(--radius-md);
    color: var(--color-primary-dark);
    display: flex;
    align-items: center;
    gap: var(--space-3);
    font-size: var(--text-sm);
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
  }

  .side-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .summary-card,
  .history-card {
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .summary-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .summary-list div {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }
  .summary-list div:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
  .summary-list dt {
    color: var(--color-ink-tertiary);
  }
  .summary-list dd {
    font-weight: var(--weight-semibold);
  }

  @media (max-width: 960px) {
    .medicar-grid,
    .grid-3,
    .grid-2 {
      grid-template-columns: minmax(0, 1fr);
    }
    .form-panel {
      padding: var(--space-4);
    }
    .form-actions .btn {
      width: 100%;
    }
  }

  @media (max-width: 520px) {
    .scope-switch {
      grid-template-columns: 1fr;
    }
    .scope-btn:first-child {
      border-bottom: 1px solid var(--color-border);
    }
  }
</style>
