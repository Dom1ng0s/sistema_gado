<script lang="ts">
  import { formatBrl, formatGmd, KG_POR_ARROBA } from '../lib/format';
  import { router } from '../lib/router.svelte';

  let qtdAnimais = $state(235);
  let gmdProjetado = $state(0.73);
  let cotacaoArrobaMercado = $state(338.5);

  let custoArrendamento = $state(84000);
  let custoSuplementacao = $state(98500);
  let custoMaoObra = $state(62400);
  let custosExtras = $state(31200);

  let custoAnualTotal = $derived(custoArrendamento + custoSuplementacao + custoMaoObra + custosExtras);
  let custoCabecaAno = $derived(qtdAnimais > 0 ? custoAnualTotal / qtdAnimais : 0);
  let custoCabecaDia = $derived(custoCabecaAno / 365);

  let kgProduzidosAno = $derived(qtdAnimais * gmdProjetado * 365);
  let arrobasProduzidasAno = $derived(kgProduzidosAno / KG_POR_ARROBA);
  let arrobasPorCabecaAno = $derived(qtdAnimais > 0 ? arrobasProduzidasAno / qtdAnimais : 0);

  let custoPorArroba = $derived(arrobasProduzidasAno > 0 ? custoAnualTotal / arrobasProduzidasAno : 0);
  let margemPorArroba = $derived(cotacaoArrobaMercado - custoPorArroba);
  let resultadoAnualProjetado = $derived(margemPorArroba * arrobasProduzidasAno);

  function pctDoTotal(val: number): string {
    if (custoAnualTotal <= 0) return '0,0%';
    return `${((val / custoAnualTotal) * 100).toFixed(1).replace('.', ',')}%`;
  }
</script>

<div class="sim-page">
  <header class="sim-header">
    <div>
      <h1 class="page-title">Simulador de Ponto de Equilíbrio</h1>
      <p class="page-subtitle">
        Cálculo do custo real por arroba produzida (<code class="dado">R$/@</code>) a partir do GMD e do desembolso anual.
      </p>
    </div>
    <div class="sim-header__actions">
      <button type="button" class="btn btn-outline" onclick={() => router.navegar('financeiro')}>
        Fluxo de caixa
      </button>
      <button type="button" class="btn btn-outline" onclick={() => router.navegar('lotes')}>
        Resultado por lote
      </button>
    </div>
  </header>

  <!-- Primary Readout Strip -->
  <section class="metric-strip" aria-label="Resultado do ponto de equilíbrio">
    <div class="metric-cell">
      <span class="metric-label">Custo de produção por @</span>
      <strong class="metric-val dado">{formatBrl(custoPorArroba)}/@</strong>
      <span class="metric-sub">Ponto de equilíbrio mínimo</span>
    </div>

    <div class="metric-cell">
      <span class="metric-label">Margem líquida por @</span>
      <strong class="metric-val dado" class:dado--ok={margemPorArroba >= 0} class:dado--alerta={margemPorArroba < 0}>
        {margemPorArroba >= 0 ? '+' : ''}{formatBrl(margemPorArroba)}/@
      </strong>
      <span class="metric-sub">Mercado: <span class="dado">{formatBrl(cotacaoArrobaMercado)}/@</span></span>
    </div>

    <div class="metric-cell">
      <span class="metric-label">Custo diário por cabeça</span>
      <strong class="metric-val dado">{formatBrl(custoCabecaDia)}/d</strong>
      <span class="metric-sub">Anual: <span class="dado">{formatBrl(custoCabecaAno)}/cab</span></span>
    </div>

    <div class="metric-cell">
      <span class="metric-label">Resultado operacional projetado</span>
      <strong class="metric-val dado" class:dado--ok={resultadoAnualProjetado >= 0} class:dado--alerta={resultadoAnualProjetado < 0}>
        {formatBrl(resultadoAnualProjetado)}
      </strong>
      <span class="metric-sub"><span class="dado">{arrobasProduzidasAno.toFixed(1).replace('.', ',')} @</span> produzidas/ano</span>
    </div>
  </section>

  <div class="sim-layout">
    <div class="panel sim-form">
      <div class="form-sec">
        <h3>Parâmetros produtivos</h3>
        <div class="grid-3">
          <div class="field">
            <label for="s-qtd">Rebanho médio (cab.)</label>
            <input id="s-qtd" class="input dado" type="number" min="1" bind:value={qtdAnimais} />
          </div>
          <div class="field">
            <label for="s-gmd">GMD projetado (kg/dia)</label>
            <input id="s-gmd" class="input dado" type="number" step="0.025" min="0.05" bind:value={gmdProjetado} />
          </div>
          <div class="field">
            <label for="s-cot">Cotação de venda (R$/@)</label>
            <input id="s-cot" class="input dado" type="number" step="1" bind:value={cotacaoArrobaMercado} />
          </div>
        </div>
      </div>

      <div class="form-sec">
        <h3>Desembolso operacional anual (R$)</h3>
        <div class="grid-2">
          <div class="field">
            <label for="c-sup">Suplementação e nutrição</label>
            <input id="c-sup" class="input dado" type="number" step="1000" bind:value={custoSuplementacao} />
          </div>
          <div class="field">
            <label for="c-arr">Arrendamento / custo da terra</label>
            <input id="c-arr" class="input dado" type="number" step="1000" bind:value={custoArrendamento} />
          </div>
          <div class="field">
            <label for="c-mao">Mão de obra e encargos</label>
            <input id="c-mao" class="input dado" type="number" step="1000" bind:value={custoMaoObra} />
          </div>
          <div class="field">
            <label for="c-ext">Sanidade, manutenção e outros</label>
            <input id="c-ext" class="input dado" type="number" step="1000" bind:value={custosExtras} />
          </div>
        </div>
      </div>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Centro de custo</th>
            <th class="col-num">Desembolso anual</th>
            <th class="col-num">R$ por @ produzida</th>
            <th class="col-num">Peso no custo</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Suplementação e nutrição</td>
            <td class="col-num">{formatBrl(custoSuplementacao)}</td>
            <td class="col-num">{formatBrl(arrobasProduzidasAno > 0 ? custoSuplementacao / arrobasProduzidasAno : 0)}</td>
            <td class="col-num">{pctDoTotal(custoSuplementacao)}</td>
          </tr>
          <tr>
            <td>Arrendamento / terra</td>
            <td class="col-num">{formatBrl(custoArrendamento)}</td>
            <td class="col-num">{formatBrl(arrobasProduzidasAno > 0 ? custoArrendamento / arrobasProduzidasAno : 0)}</td>
            <td class="col-num">{pctDoTotal(custoArrendamento)}</td>
          </tr>
          <tr>
            <td>Mão de obra e encargos</td>
            <td class="col-num">{formatBrl(custoMaoObra)}</td>
            <td class="col-num">{formatBrl(arrobasProduzidasAno > 0 ? custoMaoObra / arrobasProduzidasAno : 0)}</td>
            <td class="col-num">{pctDoTotal(custoMaoObra)}</td>
          </tr>
          <tr>
            <td>Sanidade, manutenção e outros</td>
            <td class="col-num">{formatBrl(custosExtras)}</td>
            <td class="col-num">{formatBrl(arrobasProduzidasAno > 0 ? custosExtras / arrobasProduzidasAno : 0)}</td>
            <td class="col-num">{pctDoTotal(custosExtras)}</td>
          </tr>
          <tr>
            <td><strong>Total operacional ({formatGmd(gmdProjetado)} · {arrobasPorCabecaAno.toFixed(1).replace('.', ',')} @/cab/ano)</strong></td>
            <td class="col-num"><strong>{formatBrl(custoAnualTotal)}</strong></td>
            <td class="col-num"><strong>{formatBrl(custoPorArroba)}</strong></td>
            <td class="col-num"><strong>100,0%</strong></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<style>
  .sim-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .sim-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .sim-header__actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .metric-label {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }
  .metric-val {
    font-size: var(--text-2xl);
    font-weight: var(--weight-medium);
  }
  .metric-sub {
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
  }

  .sim-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-5);
    align-items: start;
  }

  .sim-form {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .form-sec {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .form-sec h3 {
    font-size: var(--text-base);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--color-border);
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

  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .field label {
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
  }

  @media (max-width: 980px) {
    .sim-layout,
    .grid-3,
    .grid-2 {
      grid-template-columns: 1fr;
    }
  }
</style>
