<script lang="ts">
  /**
   * Trilha 5 — Relatórios.
   * Gráficos de composição do rebanho, faixas de peso e distribuição de GMD
   * (/api/graficos/*), exportações CSV e geração assíncrona do relatório PDF
   * com progresso inline (Seção 5.2 do guia: a rota pesada não trava a tela).
   */
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatGmd } from '../lib/format';
  import EChart from '../components/charts/EChart.svelte';

  interface GraficoSexo {
    M: number;
    F: number;
  }

  interface FaixaPeso {
    faixa: string;
    cabecas: number;
  }

  interface FaixaGmd {
    faixa: string;
    cabecas: number;
    abaixo_da_meta: boolean;
  }

  /** Agregações de demonstração — Fazenda São Marcos (235 cabeças ativas). */
  const SEXO_DEMO: GraficoSexo = { M: 193, F: 42 };

  const PESO_DEMO: FaixaPeso[] = [
    { faixa: 'até 300 kg', cabecas: 18 },
    { faixa: '300 a 350 kg', cabecas: 31 },
    { faixa: '350 a 400 kg', cabecas: 44 },
    { faixa: '400 a 450 kg', cabecas: 58 },
    { faixa: '450 a 500 kg', cabecas: 62 },
    { faixa: 'acima de 500 kg', cabecas: 22 }
  ];

  const GMD_DEMO: FaixaGmd[] = [
    { faixa: 'até 0,300', cabecas: 9, abaixo_da_meta: true },
    { faixa: '0,300 a 0,450', cabecas: 17, abaixo_da_meta: true },
    { faixa: '0,450 a 0,650', cabecas: 46, abaixo_da_meta: true },
    { faixa: '0,650 a 0,800', cabecas: 78, abaixo_da_meta: false },
    { faixa: '0,800 a 1,000', cabecas: 61, abaixo_da_meta: false },
    { faixa: 'acima de 1,000', cabecas: 24, abaixo_da_meta: false }
  ];

  type EstadoPdf = 'ocioso' | 'gerando' | 'pronto' | 'erro';

  let sexo = $state<GraficoSexo>(SEXO_DEMO);
  let faixasPeso = $state<FaixaPeso[]>(PESO_DEMO);
  let faixasGmd = $state<FaixaGmd[]>(GMD_DEMO);
  let apiConectada = $state(false);
  let carregando = $state(true);

  let estadoPdf = $state<EstadoPdf>('ocioso');
  let progressoPdf = $state(0);
  let urlPdf = $state<string | null>(null);
  let mensagemPdf = $state('');
  let temporizador: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    carregarGraficos();
    return () => {
      if (temporizador) clearInterval(temporizador);
    };
  });

  async function carregarGraficos() {
    try {
      const [s, p, g] = await Promise.all([
        apiFetch<GraficoSexo>('/api/graficos/sexo').catch(() => null),
        apiFetch<FaixaPeso[] | { faixas: FaixaPeso[] }>('/api/graficos/peso').catch(() => null),
        apiFetch<FaixaGmd[] | { faixas: FaixaGmd[] }>('/api/graficos/gmd').catch(() => null)
      ]);

      if (s && (s.M !== undefined || s.F !== undefined)) {
        sexo = { M: s.M ?? 0, F: s.F ?? 0 };
        apiConectada = true;
      }
      const listaPeso = Array.isArray(p) ? p : p?.faixas;
      if (listaPeso?.length) {
        faixasPeso = listaPeso;
        apiConectada = true;
      }
      const listaGmd = Array.isArray(g) ? g : g?.faixas;
      if (listaGmd?.length) {
        faixasGmd = listaGmd;
        apiConectada = true;
      }
    } catch {
      // Relatórios seguem navegáveis com as agregações de demonstração.
      apiConectada = false;
    } finally {
      carregando = false;
    }
  }

  let gmdMeta = $derived(auth.user.gmd_meta);
  let totalCabecas = $derived(sexo.M + sexo.F);
  let cabecasAbaixoMeta = $derived(
    faixasGmd.filter((f) => f.abaixo_da_meta).reduce((s, f) => s + f.cabecas, 0)
  );
  let pctAbaixoMeta = $derived(
    totalCabecas > 0 ? (cabecasAbaixoMeta / faixasGmd.reduce((s, f) => s + f.cabecas, 0)) * 100 : 0
  );

  let opcoesSexo = $derived.by(() => ({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        name: 'Composição do rebanho',
        type: 'pie',
        radius: ['36%', '58%'],
        center: ['50%', '44%'],
        itemStyle: { borderColor: '#FFFFFF', borderWidth: 2 },
        label: {
          formatter: '{b}\n{c} cab.',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
          color: '#525E56'
        },
        data: [
          { name: 'Machos', value: sexo.M, itemStyle: { color: '#155E3B' } },
          { name: 'Fêmeas', value: sexo.F, itemStyle: { color: '#3B453E' } }
        ]
      }
    ]
  }));

  let opcoesPeso = $derived.by(() => ({
    grid: { left: 10, right: 14, top: 32, bottom: 16, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'category',
      data: faixasPeso.map((f) => f.faixa),
      axisLabel: { interval: 0, rotate: 24 }
    },
    yAxis: { type: 'value', name: 'cab.', nameTextStyle: { color: '#525E56', fontSize: 11 } },
    series: [
      {
        name: 'Cabeças por faixa de peso',
        type: 'bar',
        barMaxWidth: 32,
        itemStyle: { color: '#155E3B' },
        data: faixasPeso.map((f) => f.cabecas)
      }
    ]
  }));

  let opcoesGmd = $derived.by(() => ({
    grid: { left: 10, right: 14, top: 32, bottom: 16, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'category',
      data: faixasGmd.map((f) => f.faixa),
      axisLabel: { interval: 0, rotate: 24 }
    },
    yAxis: { type: 'value', name: 'cab.', nameTextStyle: { color: '#525E56', fontSize: 11 } },
    series: [
      {
        name: 'Cabeças por faixa de GMD',
        type: 'bar',
        barMaxWidth: 32,
        data: faixasGmd.map((f) => ({
          value: f.cabecas,
          itemStyle: { color: f.abaixo_da_meta ? '#B42318' : '#155E3B' }
        }))
      }
    ]
  }));

  async function gerarPdf() {
    if (estadoPdf === 'gerando') return;
    estadoPdf = 'gerando';
    progressoPdf = 0;
    urlPdf = null;
    mensagemPdf = 'Gerando relatório...';

    // Progresso leve na tela enquanto a rota pesada trabalha no servidor.
    if (temporizador) clearInterval(temporizador);
    temporizador = setInterval(() => {
      progressoPdf = Math.min(progressoPdf + 7, 92);
    }, 320);

    try {
      const resposta = await apiFetch<{ url?: string }>('/api/relatorios/pdf', {
        method: 'POST',
        body: JSON.stringify({ farm_id: auth.user.farm_id })
      });
      urlPdf = resposta.url ?? '/relatorio-pdf';
      estadoPdf = 'pronto';
      mensagemPdf = 'Relatório pronto para download.';
    } catch {
      estadoPdf = 'erro';
      mensagemPdf = 'A rota de PDF ainda não está ativa nesta sessão. Use as exportações CSV abaixo.';
    } finally {
      if (temporizador) {
        clearInterval(temporizador);
        temporizador = null;
      }
      progressoPdf = estadoPdf === 'pronto' ? 100 : 0;
    }
  }
</script>

<div class="relatorios">
  <header class="relatorios__header">
    <div>
      <h1 class="page-title">Relatórios</h1>
      <p class="page-subtitle">
        Composição do rebanho, distribuição de peso e de GMD de {auth.user.nome_fazenda}, com exportações auditáveis
        {#if !apiConectada && !carregando}
          <span class="badge badge--neutro">Modo demonstração (Fazenda São Marcos)</span>
        {/if}
      </p>
    </div>

    <div class="relatorios__acoes">
      {#if auth.podeVerCampo}
        <a class="btn btn-outline" href="/api/v1/export/animais.csv" download>Rebanho em CSV</a>
      {/if}
      {#if auth.podeVerFinanceiro}
        <a class="btn btn-outline" href="/api/v1/export/financeiro.csv?ano=2026" download>Financeiro em CSV</a>
      {/if}
      {#if auth.podeGerirFazenda || auth.papel === 'consultor'}
        <button type="button" class="btn btn-primary" disabled={estadoPdf === 'gerando'} onclick={gerarPdf}>
          {estadoPdf === 'gerando' ? 'Gerando relatório...' : 'Gerar relatório PDF'}
        </button>
      {/if}
    </div>
  </header>

  {#if estadoPdf !== 'ocioso'}
    <div class="pdf-status panel" class:pdf-status--erro={estadoPdf === 'erro'} role="status">
      <div class="pdf-status__texto">
        <strong>{mensagemPdf}</strong>
        {#if estadoPdf === 'gerando'}
          <small>A tela segue utilizável enquanto o arquivo é montado no servidor.</small>
        {/if}
      </div>

      {#if estadoPdf === 'gerando'}
        <div class="pdf-barra" role="progressbar" aria-valuenow={progressoPdf} aria-valuemin="0" aria-valuemax="100">
          <span class="pdf-barra__preenchimento" style:width={`${progressoPdf}%`}></span>
        </div>
        <span class="dado pdf-status__pct">{progressoPdf}%</span>
      {:else if estadoPdf === 'pronto' && urlPdf}
        <a class="btn btn-primary" href={urlPdf} download>Baixar PDF</a>
      {/if}
    </div>
  {/if}

  <section class="mostradores panel" aria-label="Síntese do rebanho">
    <div class="mostrador">
      <span class="mostrador__label">Rebanho ativo</span>
      <strong class="mostrador__value dado">{totalCabecas} cab.</strong>
      <span class="mostrador__meta dado">{sexo.M} machos · {sexo.F} fêmeas</span>
    </div>
    <div class="mostrador">
      <span class="mostrador__label">Meta de GMD da fazenda</span>
      <strong class="mostrador__value dado">{formatGmd(gmdMeta)}</strong>
      <span class="mostrador__meta">Configurada em Configurações</span>
    </div>
    <div class="mostrador">
      <span class="mostrador__label">Abaixo da meta</span>
      <strong class="mostrador__value dado" class:dado--alerta={cabecasAbaixoMeta > 0}>{cabecasAbaixoMeta} cab.</strong>
      <span class="mostrador__meta">
        <span class="dado" class:dado--alerta={pctAbaixoMeta >= 20}>{pctAbaixoMeta.toFixed(0)}%</span> do rebanho avaliado
      </span>
    </div>
  </section>

  <div class="grafico-grid">
    {#if auth.podeVerCampo}
      <section class="grafico-sec panel">
        <div class="grafico-sec__topo">
          <h2 class="section-title">Composição por sexo</h2>
          <p class="grafico-sec__legenda">Participação de machos e fêmeas no rebanho ativo</p>
        </div>
        <EChart options={opcoesSexo} height="280px" rotulo="Composição do rebanho por sexo" />
      </section>

      <section class="grafico-sec panel">
        <div class="grafico-sec__topo">
          <h2 class="section-title">Distribuição por faixa de peso</h2>
          <p class="grafico-sec__legenda">Onde está a massa do rebanho em <span class="dado">kg</span> hoje</p>
        </div>
        <EChart options={opcoesPeso} height="280px" rotulo="Cabeças por faixa de peso" />
      </section>

      <section class="grafico-sec panel grafico-sec--largo">
        <div class="grafico-sec__topo">
          <h2 class="section-title">Distribuição de GMD</h2>
          <p class="grafico-sec__legenda">
            Faixas em óxido estão abaixo da meta de <span class="dado">{formatGmd(gmdMeta)}</span> e concentram a perda de
            ganho no cocho
          </p>
        </div>
        <EChart options={opcoesGmd} height="300px" rotulo="Cabeças por faixa de GMD" />
      </section>
    {:else}
      <section class="grafico-sec panel grafico-sec--largo">
        <p class="sem-permissao">
          Seu papel (<span class="dado">{auth.papel}</span>) não tem acesso aos gráficos de rebanho. As exportações
          financeiras em CSV continuam disponíveis no topo desta tela.
        </p>
      </section>
    {/if}
  </div>

  <section class="tabela-gmd">
    <h2 class="section-title">Faixas de GMD em números</h2>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Faixa de GMD (kg/d)</th>
            <th class="col-num">Cabeças</th>
            <th class="col-num">Participação</th>
            <th>Situação</th>
          </tr>
        </thead>
        <tbody>
          {#each faixasGmd as f (f.faixa)}
            {@const total = faixasGmd.reduce((s, x) => s + x.cabecas, 0)}
            <tr class:linha-alerta={f.abaixo_da_meta}>
              <td><span class="dado">{f.faixa}</span></td>
              <td class="col-num"><span class="dado">{f.cabecas}</span></td>
              <td class="col-num">
                <span class="dado">{total > 0 ? ((f.cabecas / total) * 100).toFixed(1).replace('.', ',') : '0,0'}%</span>
              </td>
              <td>
                {#if f.abaixo_da_meta}
                  <span class="badge badge--alerta">Abaixo da meta</span>
                {:else}
                  <span class="badge badge--ok">Dentro da meta</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
</div>

<style>
  .relatorios {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .relatorios__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .relatorios__acoes {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .pdf-status {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-5);
    flex-wrap: wrap;
  }

  .pdf-status--erro {
    background: var(--color-danger-bg);
    border-color: var(--color-danger);
    color: var(--color-danger-dark);
  }

  .pdf-status__texto {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .pdf-status__texto strong {
    font-size: var(--text-base);
  }
  .pdf-status__texto small {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .pdf-barra {
    flex: 1 1 200px;
    height: 4px;
    min-width: 160px;
    background: var(--n-100);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }

  .pdf-barra__preenchimento {
    display: block;
    height: 100%;
    background: var(--color-primary);
    transition: width var(--transition-normal);
  }

  .pdf-status__pct {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .mostradores {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
  }

  .mostrador {
    padding: var(--space-4) var(--space-5);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .mostrador:last-child {
    border-right: none;
  }

  .mostrador__label {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .mostrador__value {
    font-size: var(--text-3xl);
    line-height: var(--leading-tight);
    white-space: nowrap;
    letter-spacing: var(--tracking-display);
  }

  .mostrador__meta {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .grafico-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-4);
  }

  .grafico-sec {
    padding: var(--space-5);
  }

  .grafico-sec--largo {
    grid-column: 1 / -1;
  }

  .grafico-sec__topo {
    margin-bottom: var(--space-3);
  }

  .grafico-sec__legenda {
    margin-top: var(--space-1);
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
    max-width: 78ch;
  }

  .sem-permissao {
    font-size: var(--text-base);
    color: var(--color-ink-secondary);
  }

  .tabela-gmd {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .linha-alerta {
    background: var(--color-danger-bg);
  }

  @media (max-width: 1024px) {
    .grafico-grid {
      grid-template-columns: 1fr;
    }
    .mostradores {
      grid-template-columns: 1fr;
    }
    .mostrador {
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }
  }
</style>
