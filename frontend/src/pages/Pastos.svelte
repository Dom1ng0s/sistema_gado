<script lang="ts">
  /**
   * Trilha 5 / MT-5.1 — Pastos e módulos (vw_ocupacao_atual).
   * Grid de cartões de piquete com lotação em UA/ha, barra de ocupação
   * (óxido acima de 100% = superpastejo) e alocação de lote entre módulos.
   */
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatGmd } from '../lib/format';
  import EChart from '../components/charts/EChart.svelte';

  interface Pasto {
    id: number;
    nome: string;
    area_ha: number;
    cabecas: number;
    ua_total: number;
    capacidade_ua_ha: number;
    gmd_medio: number | null;
    lote_principal: string;
    forrageira: string;
    dias_ocupacao: number;
  }

  /** Fazenda São Marcos — 4 módulos de pastejo rotacionado. */
  const DEMO: Pasto[] = [
    { id: 1, nome: 'Piquete 1', area_ha: 32.0, cabecas: 56, ua_total: 59.4, capacidade_ua_ha: 1.7, gmd_medio: 0.312, lote_principal: 'Lote 2025-C', forrageira: 'Brachiaria brizantha', dias_ocupacao: 46 },
    { id: 2, nome: 'Piquete 2', area_ha: 28.5, cabecas: 36, ua_total: 40.3, capacidade_ua_ha: 1.6, gmd_medio: 0.512, lote_principal: 'Lote 2025-C', forrageira: 'Brachiaria brizantha', dias_ocupacao: 31 },
    { id: 3, nome: 'Piquete 3', area_ha: 41.0, cabecas: 62, ua_total: 66.4, capacidade_ua_ha: 1.8, gmd_medio: 0.839, lote_principal: 'Lote 2026-A', forrageira: 'Panicum mombaça', dias_ocupacao: 18 },
    { id: 4, nome: 'Piquete 4', area_ha: 36.0, cabecas: 54, ua_total: 59.8, capacidade_ua_ha: 1.9, gmd_medio: 1.021, lote_principal: 'Lote 2026-B', forrageira: 'Panicum mombaça', dias_ocupacao: 12 },
    { id: 5, nome: 'Reserva de descanso', area_ha: 22.0, cabecas: 0, ua_total: 0, capacidade_ua_ha: 1.5, gmd_medio: null, lote_principal: '—', forrageira: 'Brachiaria humidicola', dias_ocupacao: 0 }
  ];

  const LOTES = ['Lote 2025-C', 'Lote 2026-A', 'Lote 2026-B'];

  let pastos = $state<Pasto[]>(DEMO);
  let apiConectada = $state(false);
  let carregando = $state(true);

  // Alocação de lote entre módulos
  let modalAberto = $state(false);
  let loteAlocar = $state(LOTES[0]);
  let destinoId = $state<number>(DEMO[4].id);
  let cabecasAlocar = $state('36');
  let mensagem = $state('');

  onMount(async () => {
    try {
      const dados = await apiFetch<Pasto[] | { pastos: Pasto[] }>('/api/pastos');
      const lista = Array.isArray(dados) ? dados : dados.pastos;
      if (lista?.length) {
        pastos = lista;
        apiConectada = true;
      }
    } catch {
      // Grid segue navegável com os módulos de demonstração.
      apiConectada = false;
    } finally {
      carregando = false;
    }
  });

  function lotacao(p: Pasto): number {
    return p.area_ha > 0 ? p.ua_total / p.area_ha : 0;
  }

  function ocupacaoPct(p: Pasto): number {
    const capacidadeUa = p.capacidade_ua_ha * p.area_ha;
    return capacidadeUa > 0 ? (p.ua_total / capacidadeUa) * 100 : 0;
  }

  function superpastejo(p: Pasto): boolean {
    return ocupacaoPct(p) > 100;
  }

  function formatUaHa(valor: number): string {
    return `${valor.toFixed(2).replace('.', ',')} UA/ha`;
  }

  function formatHa(valor: number): string {
    return `${valor.toFixed(1).replace('.', ',')} ha`;
  }

  let gmdMeta = $derived(auth.user.gmd_meta);
  let areaTotal = $derived(pastos.reduce((s, p) => s + p.area_ha, 0));
  let uaTotal = $derived(pastos.reduce((s, p) => s + p.ua_total, 0));
  let cabecasTotal = $derived(pastos.reduce((s, p) => s + p.cabecas, 0));
  let lotacaoMedia = $derived(areaTotal > 0 ? uaTotal / areaTotal : 0);
  let modulosEmSuperpastejo = $derived(pastos.filter(superpastejo).length);

  let opcoesGmdModulo = $derived.by(() => {
    const comGmd = pastos.filter((p) => p.gmd_medio !== null);
    return {
      grid: { left: 54, right: 20, top: 30, bottom: 28 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: { type: 'category', data: comGmd.map((p) => p.nome) },
      yAxis: { type: 'value', name: 'kg/d', nameTextStyle: { color: '#525E56', fontSize: 11 } },
      series: [
        {
          name: 'GMD médio do módulo',
          type: 'bar',
          barMaxWidth: 36,
          data: comGmd.map((p) => ({
            value: Number((p.gmd_medio ?? 0).toFixed(3)),
            itemStyle: { color: (p.gmd_medio ?? 0) >= gmdMeta ? '#155E3B' : '#B42318' }
          })),
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: '#3B453E', type: 'dashed', width: 1.5 },
            label: {
              formatter: `Meta ${gmdMeta.toFixed(3).replace('.', ',')}`,
              color: '#525E56',
              fontSize: 11,
              fontFamily: "'IBM Plex Mono', monospace"
            },
            data: [{ yAxis: gmdMeta }]
          }
        }
      ]
    };
  });

  async function alocar(evento: SubmitEvent) {
    evento.preventDefault();
    const cabecas = Number(cabecasAlocar);
    if (!Number.isFinite(cabecas) || cabecas <= 0) {
      mensagem = 'Informe a quantidade de cabeças a mover.';
      return;
    }

    try {
      await apiFetch('/api/pastos/alocar', {
        method: 'POST',
        body: JSON.stringify({ lote: loteAlocar, pasto_id: destinoId, cabecas })
      });
      mensagem = 'Alocação registrada.';
      const dados = await apiFetch<Pasto[] | { pastos: Pasto[] }>('/api/pastos');
      const lista = Array.isArray(dados) ? dados : dados.pastos;
      if (lista?.length) pastos = lista;
    } catch {
      // Simulação local: move as cabeças e a UA proporcional entre os módulos.
      const origem = pastos.find((p) => p.lote_principal === loteAlocar && p.cabecas > 0);
      const uaPorCabeca = origem && origem.cabecas > 0 ? origem.ua_total / origem.cabecas : 1.1;
      pastos = pastos.map((p) => {
        if (origem && p.id === origem.id) {
          const movidas = Math.min(cabecas, p.cabecas);
          return { ...p, cabecas: p.cabecas - movidas, ua_total: Number((p.ua_total - movidas * uaPorCabeca).toFixed(1)) };
        }
        if (p.id === destinoId) {
          return {
            ...p,
            cabecas: p.cabecas + cabecas,
            ua_total: Number((p.ua_total + cabecas * uaPorCabeca).toFixed(1)),
            lote_principal: loteAlocar,
            dias_ocupacao: 0
          };
        }
        return p;
      });
      mensagem = 'Alocação aplicada na visão de demonstração (API indisponível).';
    }
  }
</script>

<div class="pastos">
  <header class="pastos__header">
    <div>
      <h1 class="page-title">Pastos e módulos</h1>
      <p class="page-subtitle">
        Ocupação atual dos piquetes de {auth.user.nome_fazenda} em <span class="dado">UA/ha</span> contra a capacidade de suporte
        {#if !apiConectada && !carregando}
          <span class="badge badge--neutro">Modo demonstração (Fazenda São Marcos)</span>
        {/if}
      </p>
    </div>
    {#if auth.podeEscreverNoCampo}
      <button type="button" class="btn btn-primary" onclick={() => (modalAberto = true)}>Alocar lote</button>
    {/if}
  </header>

  <section class="resumo panel" aria-label="Resumo da área de pastejo">
    <div class="resumo__cell">
      <span class="resumo__label">Área de pastejo</span>
      <strong class="resumo__value dado">{formatHa(areaTotal)}</strong>
      <span class="resumo__meta dado">{pastos.length} módulos</span>
    </div>
    <div class="resumo__cell">
      <span class="resumo__label">Cabeças alocadas</span>
      <strong class="resumo__value dado">{cabecasTotal} cab.</strong>
      <span class="resumo__meta dado">{uaTotal.toFixed(1).replace('.', ',')} UA</span>
    </div>
    <div class="resumo__cell">
      <span class="resumo__label">Lotação média</span>
      <strong class="resumo__value dado">{formatUaHa(lotacaoMedia)}</strong>
      <span class="resumo__meta">Média ponderada por área</span>
    </div>
    <div class="resumo__cell">
      <span class="resumo__label">Módulos em superpastejo</span>
      <strong class="resumo__value dado" class:dado--alerta={modulosEmSuperpastejo > 0} class:dado--ok={modulosEmSuperpastejo === 0}>
        {modulosEmSuperpastejo}
      </strong>
      <span class="resumo__meta">Acima de <span class="dado">100%</span> da capacidade</span>
    </div>
  </section>

  <section class="grid-pastos" aria-label="Cartões dos módulos de pastejo">
    {#each pastos as p (p.id)}
      {@const pct = ocupacaoPct(p)}
      {@const estourou = superpastejo(p)}
      <article class="cartao panel" class:cartao--alerta={estourou}>
        <header class="cartao__topo">
          <div>
            <h2 class="cartao__nome">{p.nome}</h2>
            <small class="cartao__forrageira">{p.forrageira}</small>
          </div>
          {#if estourou}
            <span class="badge badge--alerta">Superpastejo</span>
          {:else if p.cabecas === 0}
            <span class="badge badge--neutro">Em descanso</span>
          {:else}
            <span class="badge badge--ok">Dentro da capacidade</span>
          {/if}
        </header>

        <dl class="cartao__dados">
          <div>
            <dt>Área</dt>
            <dd class="dado">{formatHa(p.area_ha)}</dd>
          </div>
          <div>
            <dt>Cabeças</dt>
            <dd class="dado">{p.cabecas} cab.</dd>
          </div>
          <div>
            <dt>Lotação atual</dt>
            <dd class="dado" class:dado--alerta={estourou}>{formatUaHa(lotacao(p))}</dd>
          </div>
          <div>
            <dt>Capacidade máxima</dt>
            <dd class="dado">{formatUaHa(p.capacidade_ua_ha)}</dd>
          </div>
          <div>
            <dt>GMD médio do módulo</dt>
            <dd>
              {#if p.gmd_medio === null}
                <span class="sem-dado">— (sem animais)</span>
              {:else}
                <span class="dado" class:dado--ok={p.gmd_medio >= gmdMeta} class:dado--alerta={p.gmd_medio < gmdMeta}>
                  {formatGmd(p.gmd_medio)}
                </span>
              {/if}
            </dd>
          </div>
          <div>
            <dt>Dias de ocupação</dt>
            <dd class="dado">{p.dias_ocupacao} d</dd>
          </div>
        </dl>

        <div class="ocupacao">
          <div class="ocupacao__rotulo">
            <span>Ocupação da capacidade</span>
            <strong class="dado" class:dado--alerta={estourou} class:dado--ok={!estourou && p.cabecas > 0}>
              {pct.toFixed(0)}%
            </strong>
          </div>
          <div
            class="ocupacao__trilha"
            role="meter"
            aria-valuenow={Math.round(pct)}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-label={`Ocupação de ${p.nome}`}
          >
            <span class="ocupacao__barra" class:ocupacao__barra--alerta={estourou} style:width={`${Math.min(pct, 100)}%`}></span>
          </div>
          <small class="cartao__lote">Lote em uso: <span class="dado">{p.lote_principal}</span></small>
        </div>
      </article>
    {/each}
  </section>

  <section class="grafico-sec panel">
    <div class="grafico-sec__topo">
      <h2 class="section-title">GMD médio por módulo</h2>
      <p class="grafico-sec__legenda">
        Comparação do ganho médio diário de cada piquete contra a meta da fazenda
        (<span class="dado">{formatGmd(gmdMeta)}</span>) — módulos em óxido pedem ajuste de lotação ou suplementação
      </p>
    </div>
    <EChart options={opcoesGmdModulo} height="260px" rotulo="GMD médio por módulo de pastejo" />
  </section>
</div>

{#if modalAberto}
  <div
    class="modal-fundo"
    role="button"
    tabindex="-1"
    aria-label="Fechar alocação"
    onclick={() => (modalAberto = false)}
    onkeydown={(e) => e.key === 'Escape' && (modalAberto = false)}
  ></div>
  <div class="modal panel" role="dialog" aria-modal="true" aria-labelledby="titulo-alocar">
    <h2 class="section-title" id="titulo-alocar">Alocar lote em módulo</h2>
    <p class="modal__nota">
      A movimentação altera a lotação em <span class="dado">UA/ha</span> dos dois módulos e reinicia o contador de
      dias de ocupação no destino.
    </p>

    <form class="modal__form" onsubmit={alocar}>
      <div class="campo">
        <label class="label" for="alocar-lote">Lote</label>
        <select id="alocar-lote" class="input" bind:value={loteAlocar}>
          {#each LOTES as l}
            <option value={l}>{l}</option>
          {/each}
        </select>
      </div>

      <div class="campo">
        <label class="label" for="alocar-cabecas">Cabeças</label>
        <input id="alocar-cabecas" class="input dado" type="number" inputmode="numeric" min="1" bind:value={cabecasAlocar} />
      </div>

      <div class="campo">
        <label class="label" for="alocar-destino">Módulo de destino</label>
        <select id="alocar-destino" class="input" bind:value={destinoId}>
          {#each pastos as p}
            <option value={p.id}>
              {p.nome} — {formatUaHa(lotacao(p))} de {formatUaHa(p.capacidade_ua_ha)}
            </option>
          {/each}
        </select>
      </div>

      <div class="modal__acoes">
        {#if mensagem}
          <span class="modal__msg">{mensagem}</span>
        {/if}
        <button type="button" class="btn btn-ghost" onclick={() => (modalAberto = false)}>Fechar</button>
        <button type="submit" class="btn btn-primary">Confirmar alocação</button>
      </div>
    </form>
  </div>
{/if}

<style>
  .pastos {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .pastos__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .resumo {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
  }

  .resumo__cell {
    padding: var(--space-4) var(--space-5);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .resumo__cell:last-child {
    border-right: none;
  }

  .resumo__label {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .resumo__value {
    font-size: var(--text-2xl);
    line-height: var(--leading-tight);
    white-space: nowrap;
  }

  .resumo__meta {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .grid-pastos {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
    gap: var(--space-4);
  }

  .cartao {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-5);
  }

  .cartao--alerta {
    border-left: 3px solid var(--color-danger);
  }

  .cartao__topo {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .cartao__nome {
    font-size: var(--text-lg);
    letter-spacing: var(--tracking-title);
  }

  .cartao__forrageira {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .cartao__dados {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
  }
  .cartao__dados dt {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }
  .cartao__dados dd {
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
  }

  .ocupacao {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .ocupacao__rotulo {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .ocupacao__trilha {
    height: 4px;
    width: 100%;
    background: var(--n-100);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }

  .ocupacao__barra {
    display: block;
    height: 100%;
    background: var(--color-primary);
    transition: width var(--transition-normal);
  }

  .ocupacao__barra--alerta {
    background: var(--color-danger);
  }

  .cartao__lote {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
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

  .sem-dado {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .modal-fundo {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal);
    border: none;
    background: rgba(23, 37, 28, 0.42);
  }

  .modal {
    position: fixed;
    z-index: var(--z-modal);
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(520px, calc(100vw - 24px));
    max-height: calc(100dvh - 24px);
    overflow-y: auto;
    padding: var(--space-5);
    box-shadow: var(--shadow-lg);
  }

  .modal__nota {
    margin-top: var(--space-2);
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .modal__form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    margin-top: var(--space-4);
  }

  .campo {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .label {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--color-ink-secondary);
  }

  .modal__acoes {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .modal__msg {
    margin-right: auto;
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  @media (max-width: 1024px) {
    .resumo {
      grid-template-columns: repeat(2, 1fr);
    }
    .resumo__cell:nth-child(2) {
      border-right: none;
    }
  }

  @media (max-width: 768px) {
    .resumo {
      grid-template-columns: 1fr;
    }
    .resumo__cell {
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }
  }
</style>
