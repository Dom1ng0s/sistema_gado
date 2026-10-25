<script lang="ts">
  import { formatArroba, formatBrl, formatGmd, formatKg } from '../lib/format';
  import { router } from '../lib/router.svelte';

  interface AnimalLote {
    brinco: string;
    sexo: 'M' | 'F';
    raca: string;
    pesoCompra: number;
    pesoAtual: number;
    gmd: number;
    custoCompra: number;
    custoSanitario: number;
    status: 'Ativo' | 'Vendido';
    valorVenda?: number;
  }

  interface LoteInfo {
    id: number;
    codigo: string;
    descricao: string;
    dataCompra: string;
    totalCabecas: number;
    vendidos: number;
    custoAquisicao: number;
    custoSanitario: number;
    custoOperacionalRateado: number;
    receitaRealizada: number;
    valuationEstoqueVivo: number;
    gmdMedio: number;
    animais: AnimalLote[];
  }

  const lotesDemo: LoteInfo[] = [
    {
      id: 1,
      codigo: 'LOTE-2026-A',
      descricao: 'Garrotes Nelore · Compra Leilão Vale do Rio Grande',
      dataCompra: '12/03/2026',
      totalCabecas: 68,
      vendidos: 22,
      custoAquisicao: 190400,
      custoSanitario: 6420,
      custoOperacionalRateado: 28900,
      receitaRealizada: 118800,
      valuationEstoqueVivo: 224480,
      gmdMedio: 0.785,
      animais: [
        { brinco: '401', sexo: 'M', raca: 'Nelore', pesoCompra: 330, pesoAtual: 495, gmd: 0.812, custoCompra: 2800, custoSanitario: 95, status: 'Ativo' },
        { brinco: '402', sexo: 'M', raca: 'Nelore', pesoCompra: 325, pesoAtual: 498.5, gmd: 0.845, custoCompra: 2800, custoSanitario: 110, status: 'Ativo' },
        { brinco: '405', sexo: 'M', raca: 'Nelore', pesoCompra: 340, pesoAtual: 525, gmd: 0.91, custoCompra: 2800, custoSanitario: 85, status: 'Vendido', valorVenda: 5920 },
        { brinco: '409', sexo: 'M', raca: 'Nelore', pesoCompra: 335, pesoAtual: 474, gmd: 0.382, custoCompra: 2800, custoSanitario: 120, status: 'Ativo' }
      ]
    },
    {
      id: 2,
      codigo: 'LOTE-2026-B',
      descricao: 'Cruzamento Industrial Angus x Nelore · Recria Intensiva',
      dataCompra: '04/05/2026',
      totalCabecas: 85,
      vendidos: 15,
      custoAquisicao: 255000,
      custoSanitario: 8150,
      custoOperacionalRateado: 34200,
      receitaRealizada: 86250,
      valuationEstoqueVivo: 315000,
      gmdMedio: 0.89,
      animais: [
        { brinco: '510', sexo: 'M', raca: 'Angus x Nelore', pesoCompra: 350, pesoAtual: 512, gmd: 0.94, custoCompra: 3000, custoSanitario: 96, status: 'Ativo' },
        { brinco: '512', sexo: 'F', raca: 'Angus x Nelore', pesoCompra: 310, pesoAtual: 448, gmd: 0.82, custoCompra: 3000, custoSanitario: 96, status: 'Ativo' }
      ]
    },
    {
      id: 3,
      codigo: 'LOTE-CRIA-FAZ',
      descricao: 'Bezerros nascidos na fazenda · Safra 2025/2026',
      dataCompra: '15/01/2026',
      totalCabecas: 82,
      vendidos: 0,
      custoAquisicao: 0,
      custoSanitario: 7380,
      custoOperacionalRateado: 41000,
      receitaRealizada: 0,
      valuationEstoqueVivo: 218940,
      gmdMedio: 0.645,
      animais: [
        { brinco: '104', sexo: 'M', raca: 'Nelore', pesoCompra: 210, pesoAtual: 340, gmd: 0.28, custoCompra: 0, custoSanitario: 90, status: 'Ativo' },
        { brinco: '118', sexo: 'F', raca: 'Nelore', pesoCompra: 195, pesoAtual: 325, gmd: 0.315, custoCompra: 0, custoSanitario: 90, status: 'Ativo' }
      ]
    }
  ];

  let loteAtivo = $state<LoteInfo | null>(null);

  $effect(() => {
    if (router.loteSelecionado) {
      const encontrado = lotesDemo.find((l) => l.codigo === router.loteSelecionado);
      if (encontrado) loteAtivo = encontrado;
    }
  });

  function custoTotalLote(l: LoteInfo) {
    return l.custoAquisicao + l.custoSanitario + l.custoOperacionalRateado;
  }

  function resultadoEconomicoLote(l: LoteInfo) {
    return l.receitaRealizada + l.valuationEstoqueVivo - custoTotalLote(l);
  }

  function roiLote(l: LoteInfo) {
    const c = custoTotalLote(l);
    return c > 0 ? (resultadoEconomicoLote(l) / c) * 100 : 100;
  }
</script>

<div class="lotes-page">
  {#if !loteAtivo}
    <header class="lotes-header">
      <div>
        <h1 class="page-title">Resultado por Lote (P&L)</h1>
        <p class="page-subtitle">
          Comparativo de aquisição, custos rateados, vendas realizadas e estoque vivo em campo (<code class="dado">vw_resultado_lote</code>).
        </p>
      </div>
      <div class="lotes-actions">
        <button type="button" class="btn btn-outline" onclick={() => router.navegar('simulador-custo')}>
          Simulador da @
        </button>
        <button type="button" class="btn btn-primary" onclick={() => router.navegar('entrada')}>
          Novo lote / Entrada
        </button>
      </div>
    </header>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Código do lote</th>
            <th>Descrição / Origem</th>
            <th class="col-num">Entrada</th>
            <th class="col-num">Ativos / Total</th>
            <th class="col-num">GMD médio</th>
            <th class="col-num">Custo acumulado</th>
            <th class="col-num">Receita + Estoque vivo</th>
            <th class="col-num">Margem (P&L)</th>
            <th>ROI</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each lotesDemo as l}
            {@const margem = resultadoEconomicoLote(l)}
            {@const roi = roiLote(l)}
            <tr>
              <td class="dado"><strong>{l.codigo}</strong></td>
              <td>{l.descricao}</td>
              <td class="col-num">{l.dataCompra}</td>
              <td class="col-num">{l.totalCabecas - l.vendidos}/{l.totalCabecas}</td>
              <td class="col-num" class:dado--ok={l.gmdMedio >= 0.65} class:dado--alerta={l.gmdMedio < 0.65}>
                {formatGmd(l.gmdMedio)}
              </td>
              <td class="col-num">{formatBrl(custoTotalLote(l))}</td>
              <td class="col-num">{formatBrl(l.receitaRealizada + l.valuationEstoqueVivo)}</td>
              <td class="col-num" class:dado--ok={margem >= 0} class:dado--alerta={margem < 0}>
                <strong>{margem >= 0 ? '+' : ''}{formatBrl(margem)}</strong>
              </td>
              <td>
                <span class="badge dado" class:badge--ok={margem >= 0} class:badge--alerta={margem < 0}>
                  {roi >= 0 ? '+' : ''}{roi.toFixed(1).replace('.', ',')}%
                </span>
              </td>
              <td>
                <button type="button" class="btn btn-outline" onclick={() => (loteAtivo = l)}>
                  Prontuário
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    {@const margem = resultadoEconomicoLote(loteAtivo)}
    <header class="lotes-header">
      <div>
        <button type="button" class="btn btn-ghost" onclick={() => { loteAtivo = null; router.loteSelecionado = null; }}>
          ← Todos os lotes
        </button>
        <h1 class="page-title dado">{loteAtivo.codigo}</h1>
        <p class="page-subtitle">{loteAtivo.descricao} · Adquirido em <span class="dado">{loteAtivo.dataCompra}</span></p>
      </div>
      <div class="lotes-actions">
        <button type="button" class="btn btn-outline" onclick={() => router.navegar('pesagem')}>
          Pesar lote
        </button>
        <button type="button" class="btn btn-primary" onclick={() => router.navegar('venda')}>
          Vender animais
        </button>
      </div>
    </header>

    <section class="metric-strip" aria-label="Resumo financeiro do lote">
      <div class="metric-cell">
        <span class="m-lbl">Custo de aquisição</span>
        <strong class="m-val dado">{formatBrl(loteAtivo.custoAquisicao)}</strong>
        <span class="m-sub dado">{loteAtivo.totalCabecas} cabeças originais</span>
      </div>
      <div class="metric-cell">
        <span class="m-lbl">Custos sanitários e rateio</span>
        <strong class="m-val dado dado--alerta">{formatBrl(loteAtivo.custoSanitario + loteAtivo.custoOperacionalRateado)}</strong>
        <span class="m-sub">Sanidade: <span class="dado">{formatBrl(loteAtivo.custoSanitario)}</span></span>
      </div>
      <div class="metric-cell">
        <span class="m-lbl">Receita + Estoque vivo</span>
        <strong class="m-val dado dado--ok">{formatBrl(loteAtivo.receitaRealizada + loteAtivo.valuationEstoqueVivo)}</strong>
        <span class="m-sub">Realizado: <span class="dado">{formatBrl(loteAtivo.receitaRealizada)}</span></span>
      </div>
      <div class="metric-cell">
        <span class="m-lbl">Margem líquida do lote</span>
        <strong class="m-val dado" class:dado--ok={margem >= 0} class:dado--alerta={margem < 0}>
          {margem >= 0 ? '+' : ''}{formatBrl(margem)}
        </strong>
        <span class="m-sub">GMD médio: <span class="dado">{formatGmd(loteAtivo.gmdMedio)}</span></span>
      </div>
    </section>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Brinco</th>
            <th>Sexo / Raça</th>
            <th class="col-num">Peso entrada</th>
            <th class="col-num">Peso atual</th>
            <th class="col-num">Arrobas (@)</th>
            <th class="col-num">GMD</th>
            <th class="col-num">Custo acumulado</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {#each loteAtivo.animais as a}
            <tr>
              <td class="dado"><strong>#{a.brinco}</strong></td>
              <td>{a.sexo} · {a.raca}</td>
              <td class="col-num">{formatKg(a.pesoCompra)}</td>
              <td class="col-num">{formatKg(a.pesoAtual)}</td>
              <td class="col-num">{formatArroba(a.pesoAtual)}</td>
              <td class="col-num" class:dado--ok={a.gmd >= 0.65} class:dado--alerta={a.gmd < 0.65}>
                {formatGmd(a.gmd)}
              </td>
              <td class="col-num">{formatBrl(a.custoCompra + a.custoSanitario)}</td>
              <td>
                {#if a.status === 'Vendido'}
                  <span class="badge badge--amber">Vendido ({formatBrl(a.valorVenda ?? 0)})</span>
                {:else}
                  <span class="badge badge--ok">Em campo</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .lotes-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .lotes-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .lotes-actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .m-lbl {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }
  .m-val {
    font-size: var(--text-2xl);
    font-weight: var(--weight-medium);
  }
  .m-sub {
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
  }
</style>
