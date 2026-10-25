<script lang="ts">
  import EChart from '../components/charts/EChart.svelte';
  import { auth } from '../lib/auth.svelte';
  import { formatGmd, formatKg } from '../lib/format';
  import { router } from '../lib/router.svelte';

  const touros = [
    { pos: 1, brinco: 'T-04 Black Titan', raca: 'Aberdeen Angus', filhosPesados: 28, pesoMedioDesmama: 256.0, gmdFilhos: 0.94, origem: 'Sêmen Importado' },
    { pos: 2, brinco: 'T-01 Imperador FIV', raca: 'Nelore PO', filhosPesados: 34, pesoMedioDesmama: 242.5, gmdFilhos: 0.885, origem: 'Inseminação (IATF)' },
    { pos: 3, brinco: 'T-02 Guardião SM', raca: 'Nelore', filhosPesados: 19, pesoMedioDesmama: 221.0, gmdFilhos: 0.725, origem: 'Repasse Campo' },
    { pos: 4, brinco: 'T-07 Soberano', raca: 'Brahman', filhosPesados: 12, pesoMedioDesmama: 205.0, gmdFilhos: 0.59, origem: 'Repasse Campo' }
  ];

  let chartOptions = $derived({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, confine: true },
    grid: { left: 8, right: 44, top: 16, bottom: 24, containLabel: true },
    xAxis: { type: 'value', name: 'kg/d', splitNumber: 3, nameTextStyle: { fontSize: 11 } },
    yAxis: {
      type: 'category',
      inverse: true,
      data: touros.map((t) => t.brinco),
      axisLabel: { fontSize: 11 }
    },
    series: [
      {
        name: 'GMD médio da progênie',
        type: 'bar',
        barWidth: 20,
        itemStyle: { borderRadius: [0, 4, 4, 0] },
        data: touros.map((t) => ({
          value: t.gmdFilhos,
          itemStyle: {
            color: t.gmdFilhos >= auth.user.gmd_meta ? '#155E3B' : '#B42318'
          }
        }))
      }
    ]
  });
</script>

<div class="touros-page">
  <header class="touros-header">
    <div>
      <h1 class="page-title">Ranking de Touros (Progênie)</h1>
      <p class="page-subtitle">
        Avaliação genética por peso médio à desmama e GMD dos filhos nascidos na fazenda.
      </p>
    </div>
    <div class="touros-actions">
      <button type="button" class="btn btn-outline" onclick={() => router.navegar('reproducao')}>
        Painel de reprodução
      </button>
      <button type="button" class="btn btn-outline" onclick={() => router.navegar('pastos-gmd')}>
        GMD por pasto
      </button>
    </div>
  </header>

  <section class="metric-strip" aria-label="Resumo genético">
    <div class="metric-cell">
      <span class="m-lbl">GMD médio do rebanho (referência)</span>
      <strong class="m-val dado dado--ok">0,730 kg/d</strong>
      <span class="m-sub">Meta: <span class="dado">{formatGmd(auth.user.gmd_meta)}</span></span>
    </div>
    <div class="metric-cell">
      <span class="m-lbl">Reprodutores avaliados</span>
      <strong class="m-val dado">{touros.length} touros</strong>
      <span class="m-sub dado">93 filhos pesados</span>
    </div>
    <div class="metric-cell">
      <span class="m-lbl">Líder em ganho diário</span>
      <strong class="m-val dado">T-04 Black Titan</strong>
      <span class="m-sub">Progênie: <span class="dado">0,940 kg/d</span></span>
    </div>
  </section>

  <div class="panel chart-panel">
    <EChart options={chartOptions} height="220px" />
  </div>

  <div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th>#</th>
          <th>Reprodutor / Touro</th>
          <th>Raça</th>
          <th>Modalidade</th>
          <th class="col-num">Filhos pesados</th>
          <th class="col-num">Peso médio desmama</th>
          <th class="col-num">GMD médio dos filhos</th>
        </tr>
      </thead>
      <tbody>
        {#each touros as t}
          <tr>
            <td class="dado"><strong>{t.pos}</strong></td>
            <td><strong>{t.brinco}</strong></td>
            <td>{t.raca}</td>
            <td>{t.origem}</td>
            <td class="col-num">{t.filhosPesados} cab.</td>
            <td class="col-num">{formatKg(t.pesoMedioDesmama)}</td>
            <td class="col-num" class:dado--ok={t.gmdFilhos >= auth.user.gmd_meta} class:dado--alerta={t.gmdFilhos < auth.user.gmd_meta}>
              <strong>{formatGmd(t.gmdFilhos)}</strong>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>

<style>
  .touros-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }
  .touros-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: var(--space-4);
    flex-wrap: wrap;
  }
  .touros-actions {
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
  .chart-panel {
    padding: var(--space-5);
  }
</style>
