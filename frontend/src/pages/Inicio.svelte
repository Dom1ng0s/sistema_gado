<script lang="ts">
  import { onMount } from 'svelte';
  import EChart from '../components/charts/EChart.svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatBrl, formatGmd } from '../lib/format';
  import { router } from '../lib/router.svelte';
  import type { DashboardSummary } from '../lib/types';

  let resumo = $state<DashboardSummary>({
    sexo: { M: 193, F: 42 },
    gmd: { gmd_medio: 0.73 },
    alertas: {
      gmd_media_rebanho: 0.73,
      gmd_limite_inferior: 0.395,
      total: 17,
      animais: [
        { id: 104, brinco: '104', gmd_atual: 0.28 },
        { id: 118, brinco: '118', gmd_atual: 0.315 },
        { id: 203, brinco: '203', gmd_atual: 0.34 },
        { id: 402, brinco: '402', gmd_atual: 0.382 }
      ]
    }
  });

  onMount(async () => {
    try {
      const dados = await apiFetch<DashboardSummary>('/api/dashboard-summary');
      resumo = dados;
    } catch {
      // Fallback para os dados da Fazenda São Marcos
    }
  });

  let totalCabecas = $derived((resumo.sexo.M ?? 0) + (resumo.sexo.F ?? 0));
  let gmdAcimaMeta = $derived(resumo.gmd.gmd_medio >= auth.user.gmd_meta);

  let chartPesoOptions = $derived({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 8, right: 12, top: 34, bottom: 12, containLabel: true },
    xAxis: {
      type: 'category',
      data: ['< 10@ (Cria)', '10–15@ (Recria)', '15–18@ (Engorda)', '> 18@ (Abate)'],
      axisLabel: {
        interval: 0,
        fontSize: 11,
        lineHeight: 14,
        formatter: (v: string) => v.replace(' (', '\n(')
      }
    },
    yAxis: { type: 'value', name: 'cab.' },
    series: [
      {
        type: 'bar',
        barMaxWidth: 26,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
        data: [
          { value: 38, itemStyle: { color: '#738070' } },
          { value: 94, itemStyle: { color: '#155E3B' } },
          { value: 67, itemStyle: { color: '#0E3F27' } },
          { value: 36, itemStyle: { color: '#9A5B13' } }
        ]
      }
    ]
  });
</script>

<div class="inicio-grid">
  <header class="workspace-header">
    <div>
      <h1 class="page-title">{auth.user.nome_fazenda}</h1>
      <p class="page-subtitle">Araçatuba, SP · 115 ha úteis em 4 módulos · Papel ativo: {auth.papel}</p>
    </div>

    <div class="workspace-actions">
      {#if auth.podeEscreverNoCampo}
        <button type="button" class="btn btn-primary" onclick={() => router.navegar('pesagem')}>
          Registrar pesagem
        </button>
      {/if}
      <button type="button" class="btn btn-outline" onclick={() => router.navegar('rebanho')}>
        Abrir rebanho
      </button>
    </div>
  </header>

  <!-- Signature Move: Split-Cell Tabular Metric Strip -->
  <section class="metric-strip" aria-label="Indicadores principais da fazenda">
    <button type="button" class="metric-cell" onclick={() => router.navegar('rebanho')}>
      <span class="metric-label">Rebanho em campo</span>
      <div class="metric-readout">
        <strong class="dado">{totalCabecas}</strong>
        <span class="metric-unit">cab.</span>
      </div>
      <span class="metric-sub dado">{resumo.sexo.M ?? 0} machos · {resumo.sexo.F ?? 0} fêmeas</span>
    </button>

    <button type="button" class="metric-cell" onclick={() => router.navegar('pastos-gmd')}>
      <span class="metric-label">GMD médio do rebanho</span>
      <div class="metric-readout">
        <strong class="dado" class:dado--ok={gmdAcimaMeta} class:dado--alerta={!gmdAcimaMeta}>
          {resumo.gmd.gmd_medio.toFixed(3).replace('.', ',')}
        </strong>
        <span class="metric-unit">kg/d</span>
      </div>
      <span class="metric-sub">
        Meta: <span class="dado">{formatGmd(auth.user.gmd_meta)}</span>
        <span class="badge badge--ok">+12,3%</span>
      </span>
    </button>

    {#if auth.podeVerFinanceiro}
      <button type="button" class="metric-cell" onclick={() => router.navegar('lotes')}>
        <span class="metric-label">Patrimônio vivo (338,50/@)</span>
        <div class="metric-readout">
          <strong class="dado">{formatBrl(433640.87)}</strong>
        </div>
        <span class="metric-sub">Custo interno: <span class="dado">R$ 102,52/@</span></span>
      </button>
    {/if}

    <button type="button" class="metric-cell" onclick={() => router.navegar('pastos')}>
      <span class="metric-label">Taxa de lotação</span>
      <div class="metric-readout">
        <strong class="dado">1,64</strong>
        <span class="metric-unit">UA/ha</span>
      </div>
      <span class="metric-sub">86% da capacidade instalada</span>
    </button>
  </section>

  <!-- Two-Column Workspace: Actionable Exceptions + Weight Distribution -->
  <div class="workspace-cols">
    <section class="panel exceptions-panel">
      <div class="panel-head">
        <h2 class="section-title">Pendências operacionais</h2>
        <span class="badge badge--alerta">3 exceções</span>
      </div>

      <div class="exception-rows">
        <div class="exception-row">
          <div class="exception-main">
            <div class="exception-title">
              <span class="badge badge--alerta">GMD abaixo do piso</span>
              <strong>{resumo.alertas.total} animais crescendo abaixo de {formatGmd(resumo.alertas.gmd_limite_inferior ?? 0.395)}</strong>
            </div>
            <div class="brincos-strip">
              {#each resumo.alertas.animais.slice(0, 4) as item}
                <button type="button" class="brinco-chip dado" onclick={() => router.navegar('rebanho', item.brinco)}>
                  #{item.brinco} ({formatGmd(item.gmd_atual)})
                </button>
              {/each}
            </div>
          </div>
          <button type="button" class="btn btn-outline" onclick={() => router.navegar('rebanho')}>
            Filtrar no rebanho
          </button>
        </div>

        <div class="exception-row">
          <div class="exception-main">
            <div class="exception-title">
              <span class="badge badge--alerta">Carência sanitária</span>
              <strong>4 animais bloqueados para abate até 14/11/2026</strong>
            </div>
            <p class="exception-desc">Aplicação recente de Ivermectina 1% (prazo de bula: 35 dias). Brincos: <span class="dado">#402, #409, #415, #418</span>.</p>
          </div>
          <button type="button" class="btn btn-outline" onclick={() => router.navegar('venda')}>
            Ver trava de venda
          </button>
        </div>

        <div class="exception-row">
          <div class="exception-main">
            <div class="exception-title">
              <span class="badge badge--amber">Janela de pesagem</span>
              <strong>2 lotes sem pesagem há mais de 45 dias</strong>
            </div>
            <p class="exception-desc">Lote 2026-A (<span class="dado">68 cab., 52d</span>) e Lote Recria Sul (<span class="dado">34 cab., 47d</span>).</p>
          </div>
          <button type="button" class="btn btn-outline" onclick={() => router.navegar('pesagem')}>
            Iniciar pesagem
          </button>
        </div>
      </div>
    </section>

    <aside class="panel chart-panel">
      <div class="panel-head">
        <div>
          <h2 class="section-title">Distribuição por faixa de arrobas (@)</h2>
          <p class="chart-sub"><span class="dado">36 animais</span> acima de 18@ em ponto de acabamento</p>
        </div>
        <button type="button" class="btn btn-ghost" onclick={() => router.navegar('relatorios')}>
          Relatórios
        </button>
      </div>

      <EChart options={chartPesoOptions} height="240px" />
    </aside>
  </div>
</div>

<style>
  .inicio-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .workspace-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .workspace-actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .metric-label {
    font-size: var(--text-xs);
    font-weight: var(--weight-medium);
    color: var(--color-ink-tertiary);
  }

  .metric-readout {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }
  .metric-readout strong {
    font-size: var(--text-3xl);
    font-weight: var(--weight-medium);
    line-height: 1.1;
    color: var(--color-ink);
  }
  .metric-unit {
    font-family: var(--font-dado);
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .metric-sub {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
  }

  .workspace-cols {
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.75fr);
    gap: var(--space-5);
    align-items: start;
    width: 100%;
    max-width: 100%;
  }

  .panel-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid var(--color-border);
  }

  .chart-sub {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
    margin-top: 2px;
  }

  .exception-rows {
    display: flex;
    flex-direction: column;
  }

  .exception-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid var(--color-border);
  }
  .exception-row:last-child {
    border-bottom: none;
  }

  .exception-main {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .exception-title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .exception-title strong {
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
  }

  .exception-desc {
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
  }

  .brincos-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .brinco-chip {
    padding: 3px 8px;
    font-size: var(--text-xs);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink);
    cursor: pointer;
  }
  .brinco-chip:hover {
    border-color: var(--color-primary);
    color: var(--color-primary-dark);
  }

  .chart-panel {
    display: flex;
    flex-direction: column;
  }

  @media (max-width: 1024px) {
    .workspace-cols {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  @media (max-width: 640px) {
    .panel-head {
      padding: var(--space-3) var(--space-4);
    }
    .workspace-actions {
      width: 100%;
    }
    .workspace-actions .btn {
      flex: 1;
    }
    .exception-row {
      flex-direction: column;
      align-items: flex-start;
      padding: var(--space-3) var(--space-4);
    }
    .exception-row .btn {
      width: 100%;
    }
  }
</style>
