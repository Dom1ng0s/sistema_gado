<script lang="ts">
  /**
   * Trilha 5 / MT-5.2 — Painel reprodutivo.
   * Coberturas, diagnóstico de gestação (DG), previsão de parto (+285 dias),
   * registro de parto vivo e Ranking de Touros pelo GMD médio da progênie.
   */
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { router } from '../lib/router.svelte';
  import { formatDateBr, formatGmd, formatKg } from '../lib/format';
  import EChart from '../components/charts/EChart.svelte';

  const GESTACAO_DIAS = 285;
  const HOJE = new Date('2026-10-24T00:00:00Z');

  type Dg = 'positivo' | 'negativo' | 'pendente';

  interface Cobertura {
    id: number;
    matriz: string;
    touro: string;
    data_cobertura: string;
    tipo: 'Monta natural' | 'Inseminação artificial';
    dg: Dg;
    data_dg: string | null;
    parto_registrado: boolean;
    cria_brinco: string | null;
    registrado_por: string;
  }

  interface Touro {
    brinco: string;
    raca: string;
    crias: number;
    gmd_medio_progenie: number;
    peso_medio_progenie: number;
    taxa_prenhez: number;
  }

  /** Estação de monta 2026 da Fazenda São Marcos. */
  const COBERTURAS_DEMO: Cobertura[] = [
    { id: 1, matriz: 'Vaca-88', touro: 'Touro-02', data_cobertura: '2026-02-14', tipo: 'Monta natural', dg: 'positivo', data_dg: '2026-04-10', parto_registrado: true, cria_brinco: '0520', registrado_por: 'davi.dono' },
    { id: 11, matriz: 'Vaca-76', touro: 'Touro-02', data_cobertura: '2026-01-22', tipo: 'Monta natural', dg: 'positivo', data_dg: '2026-03-18', parto_registrado: false, cria_brinco: null, registrado_por: 'davi.dono' },
    { id: 12, matriz: 'Vaca-82', touro: 'Touro-07', data_cobertura: '2026-02-02', tipo: 'Inseminação artificial', dg: 'positivo', data_dg: '2026-03-30', parto_registrado: false, cria_brinco: null, registrado_por: 'joao.vaqueiro' },
    { id: 2, matriz: 'Vaca-91', touro: 'Touro-07', data_cobertura: '2026-02-20', tipo: 'Inseminação artificial', dg: 'positivo', data_dg: '2026-04-15', parto_registrado: false, cria_brinco: null, registrado_por: 'joao.vaqueiro' },
    { id: 3, matriz: 'Vaca-103', touro: 'Touro-02', data_cobertura: '2026-03-02', tipo: 'Monta natural', dg: 'positivo', data_dg: '2026-04-28', parto_registrado: false, cria_brinco: null, registrado_por: 'joao.vaqueiro' },
    { id: 4, matriz: 'Vaca-115', touro: 'Touro-11', data_cobertura: '2026-03-08', tipo: 'Inseminação artificial', dg: 'negativo', data_dg: '2026-05-04', parto_registrado: false, cria_brinco: null, registrado_por: 'davi.dono' },
    { id: 5, matriz: 'Vaca-120', touro: 'Touro-07', data_cobertura: '2026-03-15', tipo: 'Monta natural', dg: 'positivo', data_dg: '2026-05-11', parto_registrado: false, cria_brinco: null, registrado_por: 'joao.vaqueiro' },
    { id: 6, matriz: 'Vaca-127', touro: 'Touro-02', data_cobertura: '2026-04-02', tipo: 'Monta natural', dg: 'positivo', data_dg: '2026-05-29', parto_registrado: false, cria_brinco: null, registrado_por: 'davi.dono' },
    { id: 7, matriz: 'Vaca-134', touro: 'Touro-11', data_cobertura: '2026-08-18', tipo: 'Inseminação artificial', dg: 'pendente', data_dg: null, parto_registrado: false, cria_brinco: null, registrado_por: 'joao.vaqueiro' },
    { id: 8, matriz: 'Vaca-141', touro: 'Touro-07', data_cobertura: '2026-09-04', tipo: 'Monta natural', dg: 'pendente', data_dg: null, parto_registrado: false, cria_brinco: null, registrado_por: 'joao.vaqueiro' },
    { id: 9, matriz: 'Vaca-150', touro: 'Touro-02', data_cobertura: '2026-09-22', tipo: 'Monta natural', dg: 'pendente', data_dg: null, parto_registrado: false, cria_brinco: null, registrado_por: 'davi.dono' },
    { id: 10, matriz: 'Vaca-158', touro: 'Touro-11', data_cobertura: '2026-04-26', tipo: 'Inseminação artificial', dg: 'negativo', data_dg: '2026-06-21', parto_registrado: false, cria_brinco: null, registrado_por: 'davi.dono' }
  ];

  const TOUROS_DEMO: Touro[] = [
    { brinco: 'Touro-02', raca: 'Nelore', crias: 18, gmd_medio_progenie: 0.742, peso_medio_progenie: 428.5, taxa_prenhez: 92 },
    { brinco: 'Touro-07', raca: 'Nelore x Angus', crias: 14, gmd_medio_progenie: 0.861, peso_medio_progenie: 452.0, taxa_prenhez: 88 },
    { brinco: 'Touro-11', raca: 'Nelore', crias: 9, gmd_medio_progenie: 0.564, peso_medio_progenie: 396.0, taxa_prenhez: 61 }
  ];

  type Aba = 'coberturas' | 'touros';

  let coberturas = $state<Cobertura[]>(COBERTURAS_DEMO);
  let touros = $state<Touro[]>(TOUROS_DEMO);
  let aba = $state<Aba>('coberturas');
  let filtroDg = $state<'todos' | Dg>('todos');
  let apiConectada = $state(false);
  let carregando = $state(true);

  onMount(async () => {
    try {
      const dados = await apiFetch<{ coberturas?: Cobertura[]; touros?: Touro[] }>('/api/reproducao');
      if (dados.coberturas?.length) {
        coberturas = dados.coberturas;
        apiConectada = true;
      }
      if (dados.touros?.length) touros = dados.touros;
    } catch {
      // Painel segue navegável com a estação de monta de demonstração.
      apiConectada = false;
    } finally {
      carregando = false;
    }
  });

  function previsaoParto(c: Cobertura): string {
    const d = new Date(`${c.data_cobertura}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() + GESTACAO_DIAS);
    return d.toISOString().slice(0, 10);
  }

  function diasAteParto(c: Cobertura): number {
    const alvo = new Date(`${previsaoParto(c)}T00:00:00Z`);
    return Math.round((alvo.getTime() - HOJE.getTime()) / 86400000);
  }

  function diasDesdeCobertura(c: Cobertura): number {
    const d = new Date(`${c.data_cobertura}T00:00:00Z`);
    return Math.round((HOJE.getTime() - d.getTime()) / 86400000);
  }

  let gmdMeta = $derived(auth.user.gmd_meta);

  let gestantes = $derived(coberturas.filter((c) => c.dg === 'positivo' && !c.parto_registrado));
  let pendentes = $derived(coberturas.filter((c) => c.dg === 'pendente'));
  let diagnosticadas = $derived(coberturas.filter((c) => c.dg !== 'pendente'));
  let taxaPrenhez = $derived(
    diagnosticadas.length === 0
      ? 0
      : (diagnosticadas.filter((c) => c.dg === 'positivo').length / diagnosticadas.length) * 100
  );
  let partosProximos30d = $derived(
    gestantes.filter((c) => {
      const dias = diasAteParto(c);
      return dias >= 0 && dias <= 30;
    })
  );
  // DG recomendado a partir de 45 dias da cobertura.
  let dgAtrasado = $derived(pendentes.filter((c) => diasDesdeCobertura(c) >= 45));

  let coberturasFiltradas = $derived(
    (filtroDg === 'todos' ? coberturas : coberturas.filter((c) => c.dg === filtroDg)).slice().sort(
      (a, b) => b.data_cobertura.localeCompare(a.data_cobertura)
    )
  );

  let tourosOrdenados = $derived(
    [...touros].sort((a, b) => b.gmd_medio_progenie - a.gmd_medio_progenie)
  );

  let opcoesRanking = $derived.by(() => ({
    grid: { left: 96, right: 36, top: 20, bottom: 24 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', name: 'kg/d', nameTextStyle: { color: '#525E56', fontSize: 11 } },
    yAxis: {
      type: 'category',
      data: [...tourosOrdenados].reverse().map((t) => t.brinco)
    },
    series: [
      {
        name: 'GMD médio da progênie',
        type: 'bar',
        barMaxWidth: 24,
        label: {
          show: true,
          position: 'right',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
          color: '#525E56',
          formatter: (p: { value: number }) => p.value.toFixed(3).replace('.', ',')
        },
        data: [...tourosOrdenados].reverse().map((t) => ({
          value: Number(t.gmd_medio_progenie.toFixed(3)),
          itemStyle: { color: t.gmd_medio_progenie >= gmdMeta ? '#155E3B' : '#B42318' }
        })),
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#3B453E', type: 'dashed', width: 1.5 },
          label: { show: false },
          data: [{ xAxis: gmdMeta }]
        }
      }
    ]
  }));

  async function registrarParto(c: Cobertura) {
    try {
      await apiFetch('/api/reproducao/partos', {
        method: 'POST',
        body: JSON.stringify({ cobertura_id: c.id, matriz: c.matriz, touro: c.touro })
      });
      const dados = await apiFetch<{ coberturas?: Cobertura[] }>('/api/reproducao');
      if (dados.coberturas?.length) coberturas = dados.coberturas;
    } catch {
      // Na visão de demonstração o parto já cria o brinco da cria vinculada à matriz e ao touro.
      const novoBrinco = `09${String(c.id).padStart(2, '0')}`;
      coberturas = coberturas.map((item) =>
        item.id === c.id
          ? { ...item, parto_registrado: true, cria_brinco: novoBrinco, registrado_por: auth.user.username }
          : item
      );
    }
  }

  async function registrarDg(c: Cobertura, resultado: Dg) {
    try {
      await apiFetch(`/api/reproducao/${c.id}/dg`, {
        method: 'POST',
        body: JSON.stringify({ resultado })
      });
      const dados = await apiFetch<{ coberturas?: Cobertura[] }>('/api/reproducao');
      if (dados.coberturas?.length) coberturas = dados.coberturas;
    } catch {
      coberturas = coberturas.map((item) =>
        item.id === c.id
          ? { ...item, dg: resultado, data_dg: HOJE.toISOString().slice(0, 10), registrado_por: auth.user.username }
          : item
      );
    }
  }
</script>

<div class="reproducao">
  <header class="reproducao__header">
    <div>
      <h1 class="page-title">Reprodução</h1>
      <p class="page-subtitle">
        Estação de monta, diagnóstico de gestação e previsão de parto de {auth.user.nome_fazenda}
        {#if !apiConectada && !carregando}
          <span class="badge badge--neutro">Modo demonstração (Fazenda São Marcos)</span>
        {/if}
      </p>
    </div>
  </header>

  <section class="indicadores panel" aria-label="Indicadores reprodutivos">
    <div class="indicador">
      <span class="indicador__label">Taxa de prenhez</span>
      <strong class="indicador__value dado" class:dado--ok={taxaPrenhez >= 75} class:dado--alerta={taxaPrenhez < 75}>
        {taxaPrenhez.toFixed(0)}%
      </strong>
      <span class="indicador__meta dado">{diagnosticadas.length} matrizes diagnosticadas</span>
    </div>
    <div class="indicador">
      <span class="indicador__label">Vacas em gestação</span>
      <strong class="indicador__value dado">{gestantes.length}</strong>
      <span class="indicador__meta">Gestação de <span class="dado">{GESTACAO_DIAS}</span> dias</span>
    </div>
    <div class="indicador">
      <span class="indicador__label">Partos previstos em 30 d</span>
      <strong class="indicador__value dado">{partosProximos30d.length}</strong>
      <span class="indicador__meta">
        {#if partosProximos30d.length}
          Primeiro: <span class="dado">{formatDateBr(previsaoParto(partosProximos30d[0]))}</span>
        {:else}
          Nenhum parto na janela
        {/if}
      </span>
    </div>
    <div class="indicador">
      <span class="indicador__label">DG pendente</span>
      <strong class="indicador__value dado" class:dado--alerta={dgAtrasado.length > 0}>{pendentes.length}</strong>
      <span class="indicador__meta" class:texto--alerta={dgAtrasado.length > 0}>
        {#if dgAtrasado.length}
          <span class="dado">{dgAtrasado.length}</span> com mais de <span class="dado">45 d</span> de cobertura
        {:else}
          Todas dentro da janela de 45 d
        {/if}
      </span>
    </div>
  </section>

  <div class="abas" role="tablist" aria-label="Visões da reprodução">
    <button type="button" role="tab" aria-selected={aba === 'coberturas'} class:ativa={aba === 'coberturas'} onclick={() => (aba = 'coberturas')}>
      Coberturas e DG
    </button>
    <button type="button" role="tab" aria-selected={aba === 'touros'} class:ativa={aba === 'touros'} onclick={() => (aba = 'touros')}>
      Ranking de touros
    </button>
  </div>

  {#if aba === 'coberturas'}
    <div class="filtro-linha">
      <span class="label" id="rotulo-dg">Diagnóstico de gestação (DG)</span>
      <div class="segmented" role="group" aria-labelledby="rotulo-dg">
        <button type="button" class:ativo={filtroDg === 'todos'} onclick={() => (filtroDg = 'todos')}>Todos</button>
        <button type="button" class:ativo={filtroDg === 'positivo'} onclick={() => (filtroDg = 'positivo')}>Positivo</button>
        <button type="button" class:ativo={filtroDg === 'negativo'} onclick={() => (filtroDg = 'negativo')}>Negativo</button>
        <button type="button" class:ativo={filtroDg === 'pendente'} onclick={() => (filtroDg = 'pendente')}>Pendente</button>
      </div>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Matriz</th>
            <th>Touro</th>
            <th>Tipo de cobertura</th>
            <th>Data da cobertura</th>
            <th>DG</th>
            <th>Previsão de parto</th>
            <th>Registrado por</th>
            {#if auth.podeEscreverNoCampo}
              <th class="col-acoes">Ação</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each coberturasFiltradas as c (c.id)}
            {@const dias = diasAteParto(c)}
            {@const atrasadoDg = c.dg === 'pendente' && diasDesdeCobertura(c) >= 45}
            <tr class:linha-alerta={atrasadoDg}>
              <td>
                <button type="button" class="link-dado dado" onclick={() => router.navegar('rebanho', c.matriz)}>
                  #{c.matriz}
                </button>
              </td>
              <td>
                <button type="button" class="link-dado dado" onclick={() => router.navegar('rebanho', c.touro)}>
                  #{c.touro}
                </button>
              </td>
              <td>{c.tipo}</td>
              <td>
                <span class="dado">{formatDateBr(c.data_cobertura)}</span>
                <small class="dado unidade">há {diasDesdeCobertura(c)} d</small>
              </td>
              <td>
                {#if c.dg === 'positivo'}
                  <span class="badge badge--ok">Positivo</span>
                  {#if c.data_dg}
                    <small class="dado unidade">{formatDateBr(c.data_dg)}</small>
                  {/if}
                {:else if c.dg === 'negativo'}
                  <span class="badge badge--alerta">Negativo</span>
                  {#if c.data_dg}
                    <small class="dado unidade">{formatDateBr(c.data_dg)}</small>
                  {/if}
                {:else if atrasadoDg}
                  <span class="badge badge--alerta">Pendente há <span class="dado">{diasDesdeCobertura(c)}d</span></span>
                {:else}
                  <span class="badge badge--neutro">Pendente</span>
                {/if}
              </td>
              <td>
                {#if c.dg !== 'positivo'}
                  <span class="sem-dado">—</span>
                {:else if c.parto_registrado}
                  <span class="badge badge--ok">
                    Parto registrado · cria <span class="dado">#{c.cria_brinco}</span>
                  </span>
                {:else}
                  <span class="dado">{formatDateBr(previsaoParto(c))}</span>
                  <small class="dado unidade" class:texto--alerta={dias <= 30}>
                    {dias >= 0 ? `faltam ${dias}d` : `atrasado ${Math.abs(dias)}d`}
                  </small>
                {/if}
              </td>
              <td><span class="autor dado">{c.registrado_por}</span></td>
              {#if auth.podeEscreverNoCampo}
                <td class="col-acoes">
                  {#if c.dg === 'pendente'}
                    <button type="button" class="btn btn-outline btn-mini" onclick={() => registrarDg(c, 'positivo')}>
                      DG positivo
                    </button>
                    <button type="button" class="btn btn-ghost btn-mini" onclick={() => registrarDg(c, 'negativo')}>
                      DG negativo
                    </button>
                  {:else if c.dg === 'positivo' && !c.parto_registrado}
                    <button type="button" class="btn btn-primary btn-mini" onclick={() => registrarParto(c)}>
                      Registrar parto
                    </button>
                  {:else}
                    <span class="sem-dado">—</span>
                  {/if}
                </td>
              {/if}
            </tr>
          {:else}
            <tr>
              <td colspan={auth.podeEscreverNoCampo ? 8 : 7} class="vazio">
                Nenhuma cobertura neste filtro.
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <section class="grafico-sec panel">
      <div class="grafico-sec__topo">
        <h2 class="section-title">GMD médio da progênie por touro</h2>
        <p class="grafico-sec__legenda">
          Quem está deixando filhos que ganham peso. A linha tracejada é a meta da fazenda
          (<span class="dado">{formatGmd(gmdMeta)}</span>)
        </p>
      </div>
      <EChart options={opcoesRanking} height="240px" rotulo="Ranking de touros por GMD da progênie" />
    </section>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th class="col-num">Posição</th>
            <th>Touro</th>
            <th>Raça</th>
            <th class="col-num">Crias avaliadas</th>
            <th class="col-num">GMD médio da progênie</th>
            <th class="col-num">Peso médio da progênie</th>
            <th class="col-num">Taxa de prenhez</th>
          </tr>
        </thead>
        <tbody>
          {#each tourosOrdenados as t, i (t.brinco)}
            <tr>
              <td class="col-num"><span class="dado">{i + 1}º</span></td>
              <td>
                <button type="button" class="link-dado dado" onclick={() => router.navegar('rebanho', t.brinco)}>
                  #{t.brinco}
                </button>
              </td>
              <td>{t.raca}</td>
              <td class="col-num"><span class="dado">{t.crias}</span></td>
              <td class="col-num">
                <span
                  class="dado"
                  class:dado--ok={t.gmd_medio_progenie >= gmdMeta}
                  class:dado--alerta={t.gmd_medio_progenie < gmdMeta}
                >{formatGmd(t.gmd_medio_progenie)}</span>
              </td>
              <td class="col-num"><span class="dado">{formatKg(t.peso_medio_progenie)}</span></td>
              <td class="col-num">
                <span class="dado" class:dado--ok={t.taxa_prenhez >= 75} class:dado--alerta={t.taxa_prenhez < 75}>
                  {t.taxa_prenhez}%
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .reproducao {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .reproducao__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .indicadores {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
  }

  .indicador {
    padding: var(--space-4) var(--space-5);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .indicador:last-child {
    border-right: none;
  }

  .indicador__label {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .indicador__value {
    font-size: var(--text-3xl);
    line-height: var(--leading-tight);
    white-space: nowrap;
    letter-spacing: var(--tracking-display);
  }

  .indicador__meta {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .texto--alerta {
    color: var(--color-danger);
  }

  .abas {
    display: flex;
    gap: var(--space-1);
    border-bottom: 1px solid var(--color-border);
    overflow-x: auto;
  }

  .abas button {
    padding: var(--space-3) var(--space-4);
    border: none;
    border-bottom: 2px solid transparent;
    background: transparent;
    font-family: var(--font-body);
    font-size: var(--text-base);
    font-weight: var(--weight-medium);
    color: var(--color-ink-secondary);
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .abas button:hover {
    color: var(--color-ink);
  }
  .abas button.ativa {
    color: var(--color-primary);
    border-bottom-color: var(--color-primary);
    font-weight: var(--weight-semibold);
  }

  .filtro-linha {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .label {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--color-ink-secondary);
  }

  .segmented {
    display: inline-flex;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    overflow: hidden;
    background: var(--color-surface);
  }

  .segmented button {
    min-height: 36px;
    padding: 0 var(--space-3);
    border: none;
    border-right: 1px solid var(--color-border);
    background: transparent;
    font-size: var(--text-sm);
    font-weight: var(--weight-medium);
    color: var(--color-ink-secondary);
    cursor: pointer;
  }
  .segmented button:last-child {
    border-right: none;
  }
  .segmented button:hover {
    background: var(--color-surface-raised);
  }
  .segmented button.ativo {
    background: var(--color-primary);
    color: #fff;
    font-weight: var(--weight-semibold);
  }

  .grafico-sec {
    padding: var(--space-5);
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

  .link-dado {
    padding: 0;
    border: none;
    background: transparent;
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
    color: var(--color-ink);
    cursor: pointer;
    text-decoration: underline;
    text-decoration-color: var(--color-border-strong);
    text-underline-offset: 3px;
  }
  .link-dado:hover {
    color: var(--color-primary);
  }

  .unidade {
    display: block;
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .autor {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .sem-dado {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .linha-alerta {
    background: var(--color-danger-bg);
  }

  .col-acoes {
    text-align: right;
    white-space: nowrap;
  }

  .btn-mini {
    min-height: 28px;
    padding: 0 var(--space-3);
    font-size: var(--text-xs);
  }

  .vazio {
    padding: var(--space-8);
    text-align: center;
    color: var(--color-ink-tertiary);
  }

  @media (max-width: 1024px) {
    .indicadores {
      grid-template-columns: repeat(2, 1fr);
    }
    .indicador:nth-child(2) {
      border-right: none;
    }
  }

  @media (max-width: 768px) {
    .indicadores {
      grid-template-columns: 1fr;
    }
    .indicador {
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }
    .abas {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      overflow-x: hidden;
    }
    .abas button {
      text-align: center;
      white-space: normal;
      line-height: 1.2;
      padding: var(--space-2) var(--space-1);
      font-size: var(--text-xs);
    }
  }
</style>
