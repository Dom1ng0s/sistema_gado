<script lang="ts">
  import { onMount } from 'svelte';
  import * as echarts from 'echarts/core';
  import { BarChart, LineChart, PieChart } from 'echarts/charts';
  import {
    GridComponent,
    TooltipComponent,
    LegendComponent,
    MarkLineComponent,
    MarkPointComponent,
    DatasetComponent
  } from 'echarts/components';
  import { CanvasRenderer } from 'echarts/renderers';

  echarts.use([
    BarChart,
    LineChart,
    PieChart,
    GridComponent,
    TooltipComponent,
    LegendComponent,
    MarkLineComponent,
    MarkPointComponent,
    DatasetComponent,
    CanvasRenderer
  ]);

  const TEMA_SGG = 'sgg-ledger';

  const FIO = '#DCE1DA';
  const TINTA_EIXO = '#525E56';
  const FONTE_DADO = "'IBM Plex Mono', monospace";

  function registrarTema() {
    echarts.registerTheme(TEMA_SGG, {
      color: ['#155E3B', '#B42318', '#3B453E'],
      backgroundColor: 'transparent',
      animationDuration: 180,
      textStyle: { fontFamily: "'Archivo', sans-serif" },
      categoryAxis: {
        axisLine: { lineStyle: { color: FIO } },
        axisTick: { show: false },
        axisLabel: { color: TINTA_EIXO, fontFamily: FONTE_DADO, fontSize: 11, hideOverlap: true },
        splitLine: { show: false }
      },
      valueAxis: {
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: TINTA_EIXO, fontFamily: FONTE_DADO, fontSize: 11, hideOverlap: true },
        splitLine: { show: true, lineStyle: { color: FIO, type: 'dashed' } }
      },
      legend: {
        textStyle: { color: TINTA_EIXO, fontSize: 12 },
        itemWidth: 10,
        itemHeight: 10,
        icon: 'rect'
      },
      tooltip: {
        confine: true,
        backgroundColor: '#FFFFFF',
        borderColor: FIO,
        borderWidth: 1,
        padding: [8, 10],
        extraCssText: 'box-sizing: border-box; box-shadow: 0 4px 12px rgba(20, 28, 23, 0.12);',
        textStyle: { color: '#141C17', fontFamily: FONTE_DADO, fontSize: 11 },
        axisPointer: { lineStyle: { color: '#9AA696' }, crossStyle: { color: '#9AA696' } }
      }
    });
  }

  interface Props {
    options: Record<string, unknown>;
    height?: string;
    rotulo?: string;
  }

  let { options, height = '280px', rotulo = 'Gráfico' }: Props = $props();

  let alvo: HTMLDivElement | undefined = $state();
  let grafico: echarts.ECharts | null = null;

  function posicionarTooltipConfinado(
    point: number[],
    _params: unknown,
    _dom: unknown,
    _rect: unknown,
    size: { contentSize: [number, number]; viewSize: [number, number] }
  ): [number, number] {
    const [tw, th] = size.contentSize;
    const [vw, vh] = size.viewSize;
    const pad = 8;

    let x = point[0] + 12;
    if (x + tw + pad > vw) {
      x = point[0] - tw - 12;
    }
    x = Math.max(pad, Math.min(x, Math.max(pad, vw - tw - pad)));

    let y = point[1] - th - 12;
    if (y < pad) {
      y = Math.min(point[1] + 12, Math.max(pad, vh - th - pad));
    }
    y = Math.max(pad, Math.min(y, Math.max(pad, vh - th - pad)));

    return [x, y];
  }

  function comTooltipConfinado(opcoes: Record<string, unknown>): echarts.EChartsCoreOption {
    const t = (opcoes.tooltip && typeof opcoes.tooltip === 'object' ? opcoes.tooltip : {}) as Record<string, unknown>;
    return {
      ...opcoes,
      tooltip: {
        confine: true,
        position: posicionarTooltipConfinado,
        extraCssText: 'max-width: calc(100% - 16px); box-sizing: border-box; box-shadow: 0 4px 12px rgba(20, 28, 23, 0.12);',
        ...t
      }
    } as echarts.EChartsCoreOption;
  }

  onMount(() => {
    if (!alvo) return;
    registrarTema();
    grafico = echarts.init(alvo, TEMA_SGG, { renderer: 'canvas' });
    grafico.setOption(comTooltipConfinado(options), true);

    const redimensionar = () => {
      if (!alvo || !grafico) return;
      const w = alvo.clientWidth;
      if (w > 0) {
        grafico.resize({ width: w });
      }
    };

    const observador = new ResizeObserver(redimensionar);
    observador.observe(alvo);
    if (alvo.parentElement) {
      observador.observe(alvo.parentElement);
    }
    window.addEventListener('resize', redimensionar);

    return () => {
      window.removeEventListener('resize', redimensionar);
      observador.disconnect();
      grafico?.dispose();
      grafico = null;
    };
  });

  $effect(() => {
    const atual = options;
    if (grafico) {
      grafico.setOption(comTooltipConfinado(atual), true);
      if (alvo && alvo.clientWidth > 0) {
        grafico.resize({ width: alvo.clientWidth });
      }
    }
  });
</script>

<div class="echart" style:height bind:this={alvo} role="img" aria-label={rotulo}></div>

<style>
  .echart {
    position: relative;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    overflow: hidden;
    background: transparent;
  }
  .echart :global(> div:first-child),
  .echart :global(canvas) {
    max-width: 100% !important;
  }
</style>
