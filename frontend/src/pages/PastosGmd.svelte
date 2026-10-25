<script lang="ts">
  import EChart from '../components/charts/EChart.svelte';
  import { auth } from '../lib/auth.svelte';
  import { formatGmd } from '../lib/format';
  import { router } from '../lib/router.svelte';

  const rankingModulos = [
    { pos: 1, modulo: 'Piquete 02 · Mombaça Rotacionado', pasto: 'Setor Norte', animais: 68, areaHa: 28, uaHa: 1.92, gmdMedio: 0.915 },
    { pos: 2, modulo: 'Piquete 01 · Braquiarão Reforma', pasto: 'Setor Norte', animais: 54, areaHa: 25, uaHa: 1.71, gmdMedio: 0.812 },
    { pos: 3, modulo: 'Módulo 04 · Integração Lavoura-Pecuária', pasto: 'Setor Leste', animais: 62, areaHa: 30, uaHa: 1.65, gmdMedio: 0.745 },
    { pos: 4, modulo: 'Módulo 03 · Baixada Sul', pasto: 'Setor Sul', animais: 51, areaHa: 32, uaHa: 1.38, gmdMedio: 0.52 }
  ];

  let chartOptions = $derived({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, confine: true },
    grid: { left: 8, right: 44, top: 16, bottom: 24, containLabel: true },
    xAxis: { type: 'value', name: 'kg/d', splitNumber: 3, nameTextStyle: { fontSize: 11 } },
    yAxis: {
      type: 'category',
      inverse: true,
      data: rankingModulos.map((m) => m.modulo.split(' · ')[0]),
      axisLabel: { fontSize: 11 }
    },
    series: [
      {
        name: 'GMD médio (kg/d)',
        type: 'bar',
        barWidth: 20,
        itemStyle: { borderRadius: [0, 4, 4, 0] },
        data: rankingModulos.map((m) => ({
          value: m.gmdMedio,
          itemStyle: {
            color: m.gmdMedio >= auth.user.gmd_meta ? '#155E3B' : '#B42318'
          }
        }))
      }
    ]
  });
</script>

<div class="pgmd-page">
  <header class="pgmd-header">
    <div>
      <h1 class="page-title">Ranking GMD por Módulo de Pasto</h1>
      <p class="page-subtitle">
        Desempenho forrageiro comparativo (<code class="dado">kg/dia</code>) contra a meta de <span class="dado">{formatGmd(auth.user.gmd_meta)}</span>.
      </p>
    </div>
    <div class="pgmd-actions">
      <button type="button" class="btn btn-outline" onclick={() => router.navegar('pastos')}>
        Pastos e lotação
      </button>
      <button type="button" class="btn btn-outline" onclick={() => router.navegar('ranking-touros')}>
        Ranking de touros
      </button>
    </div>
  </header>

  <div class="panel chart-panel">
    <EChart options={chartOptions} height="220px" />
  </div>

  <div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th>#</th>
          <th>Módulo / Piquete</th>
          <th>Setor</th>
          <th class="col-num">Área (ha)</th>
          <th class="col-num">Cabeças</th>
          <th class="col-num">Lotação (UA/ha)</th>
          <th class="col-num">GMD médio</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {#each rankingModulos as m}
          <tr>
            <td class="dado"><strong>{m.pos}</strong></td>
            <td><strong>{m.modulo}</strong></td>
            <td>{m.pasto}</td>
            <td class="col-num">{m.areaHa} ha</td>
            <td class="col-num">{m.animais} cab.</td>
            <td class="col-num">{m.uaHa.toFixed(2).replace('.', ',')} UA/ha</td>
            <td class="col-num" class:dado--ok={m.gmdMedio >= auth.user.gmd_meta} class:dado--alerta={m.gmdMedio < auth.user.gmd_meta}>
              <strong>{formatGmd(m.gmdMedio)}</strong>
            </td>
            <td>
              {#if m.gmdMedio >= auth.user.gmd_meta}
                <span class="badge badge--ok">Na meta</span>
              {:else}
                <span class="badge badge--alerta">Abaixo da meta</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>

<style>
  .pgmd-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }
  .pgmd-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: var(--space-4);
    flex-wrap: wrap;
  }
  .pgmd-actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .chart-panel {
    padding: var(--space-4);
  }
</style>
