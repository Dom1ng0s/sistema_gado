<script lang="ts">
  /**
   * Trilha 2 / MT-2.1 e MT-2.2 — Painel do Rebanho.
   * Tabela densa com filtros enxutos, ordenação tabular e Barra Flutuante de Seleção em Lote.
   * A ficha individual (AnimalFicha.svelte) abre como sub-visão desta mesma rota.
   */
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { router } from '../lib/router.svelte';
  import { formatArroba, formatGmd, formatKg } from '../lib/format';
  import AnimalFicha from './AnimalFicha.svelte';

  interface AnimalLinha {
    id: number;
    brinco: string;
    sexo: 'M' | 'F';
    raca: string;
    lote: string;
    pasto: string;
    peso_inicial: number;
    peso_atual: number;
    gmd_atual: number | null;
    dias_fazenda: number;
    pesagens: number;
    nascido_na_fazenda: boolean;
    carencia_dias: number | null;
    carencia_medicamento: string | null;
    carencia_liberacao: string | null;
    pai: string | null;
    mae: string | null;
    data_entrada: string;
    custo_acumulado: number;
  }

  /** Fazenda São Marcos — base de demonstração para navegar offline ou sem sessão ativa. */
  const DEMO: AnimalLinha[] = [
    { id: 1, brinco: '0402', sexo: 'M', raca: 'Nelore', lote: 'Lote 2026-A', pasto: 'Piquete 3', peso_inicial: 352.0, peso_atual: 498.5, gmd_atual: 0.957, dias_fazenda: 153, pesagens: 6, nascido_na_fazenda: false, carencia_dias: 21, carencia_medicamento: 'Ivermectina 1%', carencia_liberacao: '14/11/2026', pai: 'Touro-02', mae: null, data_entrada: '2026-05-24', custo_acumulado: 4120.4 },
    { id: 2, brinco: '0409', sexo: 'M', raca: 'Nelore', lote: 'Lote 2026-A', pasto: 'Piquete 3', peso_inicial: 358.0, peso_atual: 474.0, gmd_atual: 0.758, dias_fazenda: 153, pesagens: 6, nascido_na_fazenda: false, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: 'Touro-02', mae: null, data_entrada: '2026-05-24', custo_acumulado: 3980.1 },
    { id: 3, brinco: '0104', sexo: 'M', raca: 'Nelore x Angus', lote: 'Lote 2025-C', pasto: 'Piquete 1', peso_inicial: 310.0, peso_atual: 388.0, gmd_atual: 0.28, dias_fazenda: 278, pesagens: 9, nascido_na_fazenda: false, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: null, mae: null, data_entrada: '2026-01-19', custo_acumulado: 5230.0 },
    { id: 4, brinco: '0118', sexo: 'M', raca: 'Nelore', lote: 'Lote 2025-C', pasto: 'Piquete 1', peso_inicial: 322.0, peso_atual: 409.5, gmd_atual: 0.315, dias_fazenda: 278, pesagens: 9, nascido_na_fazenda: false, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: null, mae: null, data_entrada: '2026-01-19', custo_acumulado: 5190.7 },
    { id: 5, brinco: '0203', sexo: 'F', raca: 'Nelore', lote: 'Lote 2025-C', pasto: 'Piquete 2', peso_inicial: 288.0, peso_atual: 382.0, gmd_atual: 0.34, dias_fazenda: 276, pesagens: 8, nascido_na_fazenda: true, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: 'Touro-02', mae: 'Vaca-88', data_entrada: '2026-01-21', custo_acumulado: 3410.5 },
    { id: 6, brinco: '0211', sexo: 'F', raca: 'Nelore', lote: 'Lote 2025-C', pasto: 'Piquete 2', peso_inicial: 295.0, peso_atual: 441.0, gmd_atual: 0.689, dias_fazenda: 212, pesagens: 7, nascido_na_fazenda: true, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: 'Touro-07', mae: 'Vaca-91', data_entrada: '2026-03-26', custo_acumulado: 2980.0 },
    { id: 7, brinco: '0315', sexo: 'M', raca: 'Nelore x Angus', lote: 'Lote 2026-B', pasto: 'Piquete 4', peso_inicial: 368.0, peso_atual: 512.0, gmd_atual: 1.044, dias_fazenda: 138, pesagens: 5, nascido_na_fazenda: false, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: null, mae: null, data_entrada: '2026-06-08', custo_acumulado: 4460.9 },
    { id: 8, brinco: '0317', sexo: 'M', raca: 'Nelore x Angus', lote: 'Lote 2026-B', pasto: 'Piquete 4', peso_inicial: 371.5, peso_atual: 505.5, gmd_atual: 0.971, dias_fazenda: 138, pesagens: 5, nascido_na_fazenda: false, carencia_dias: 9, carencia_medicamento: 'Cipermetrina', carencia_liberacao: '02/11/2026', pai: null, mae: null, data_entrada: '2026-06-08', custo_acumulado: 4502.3 },
    { id: 9, brinco: '0520', sexo: 'F', raca: 'Nelore', lote: 'Lote 2026-B', pasto: 'Piquete 4', peso_inicial: 302.0, peso_atual: 351.0, gmd_atual: null, dias_fazenda: 61, pesagens: 1, nascido_na_fazenda: true, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: 'Touro-07', mae: 'Vaca-88', data_entrada: '2026-08-24', custo_acumulado: 1190.0 },
    { id: 10, brinco: '0607', sexo: 'M', raca: 'Nelore', lote: 'Lote 2026-A', pasto: 'Piquete 3', peso_inicial: 344.0, peso_atual: 467.0, gmd_atual: 0.804, dias_fazenda: 153, pesagens: 6, nascido_na_fazenda: false, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: null, mae: null, data_entrada: '2026-05-24', custo_acumulado: 3875.6 },
    { id: 11, brinco: '0712', sexo: 'F', raca: 'Nelore', lote: 'Lote 2025-C', pasto: 'Piquete 2', peso_inicial: 281.0, peso_atual: 405.0, gmd_atual: 0.448, dias_fazenda: 277, pesagens: 9, nascido_na_fazenda: true, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: 'Touro-02', mae: 'Vaca-91', data_entrada: '2026-01-20', custo_acumulado: 3120.8 },
    { id: 12, brinco: '0815', sexo: 'M', raca: 'Nelore', lote: 'Lote 2026-B', pasto: 'Piquete 4', peso_inicial: 376.0, peso_atual: 524.5, gmd_atual: 1.076, dias_fazenda: 138, pesagens: 5, nascido_na_fazenda: false, carencia_dias: null, carencia_medicamento: null, carencia_liberacao: null, pai: null, mae: null, data_entrada: '2026-06-08', custo_acumulado: 4610.2 }
  ];

  type ColunaOrdem = 'brinco' | 'peso_atual' | 'gmd_atual' | 'dias_fazenda';
  type FiltroSexo = 'todos' | 'M' | 'F';
  type FiltroOrigem = 'todos' | 'nascidos';
  type FiltroStatus = 'todos' | 'abaixo' | 'carencia';

  let animais = $state<AnimalLinha[]>(DEMO);
  let apiConectada = $state(false);
  let carregando = $state(true);

  let busca = $state(router.buscaBrinco ?? '');
  let filtroSexo = $state<FiltroSexo>('todos');
  let filtroOrigem = $state<FiltroOrigem>('todos');
  let filtroStatus = $state<FiltroStatus>('todos');
  let filtroLote = $state('todos');

  let colunaOrdem = $state<ColunaOrdem>('brinco');
  let ordemAsc = $state(true);

  let selecionados = $state<number[]>([]);
  let animalAberto = $state<AnimalLinha | null>(null);

  onMount(async () => {
    try {
      const dados = await apiFetch<AnimalLinha[] | { animais: AnimalLinha[] }>('/api/animais');
      const lista = Array.isArray(dados) ? dados : dados.animais;
      if (lista?.length) {
        animais = lista;
        apiConectada = true;
      }
    } catch {
      // Sem sessão ativa ou offline: a tela segue navegável com a base da Fazenda São Marcos.
      apiConectada = false;
    } finally {
      carregando = false;
    }
  });

  // A busca global por brinco (atalho '/') ou re-navegação para Rebanho atualiza o filtro e fecha a sub-ficha.
  $effect(() => {
    const _tick = router.navTick;
    const vindoDaBarra = router.buscaBrinco;
    if (_tick >= 0) {
      animalAberto = null;
      busca = vindoDaBarra ?? '';
    }
  });

  let lotes = $derived(['todos', ...Array.from(new Set(animais.map((a) => a.lote))).sort()]);
  let gmdMeta = $derived(auth.user.gmd_meta);

  function abaixoDaMeta(a: AnimalLinha): boolean {
    return a.gmd_atual !== null && a.gmd_atual < gmdMeta;
  }

  let filtrados = $derived.by(() => {
    const termo = busca.trim().replace('#', '').toLowerCase();
    const lista = animais.filter((a) => {
      if (termo && !a.brinco.toLowerCase().includes(termo)) return false;
      if (filtroSexo !== 'todos' && a.sexo !== filtroSexo) return false;
      if (filtroOrigem === 'nascidos' && !a.nascido_na_fazenda) return false;
      if (filtroStatus === 'abaixo' && !abaixoDaMeta(a)) return false;
      if (filtroStatus === 'carencia' && !a.carencia_dias) return false;
      if (filtroLote !== 'todos' && a.lote !== filtroLote) return false;
      return true;
    });

    const fator = ordemAsc ? 1 : -1;
    return lista.sort((x, y) => {
      if (colunaOrdem === 'brinco') {
        return x.brinco.localeCompare(y.brinco, 'pt-BR', { numeric: true }) * fator;
      }
      const vx = x[colunaOrdem] ?? -1;
      const vy = y[colunaOrdem] ?? -1;
      return (vx - vy) * fator;
    });
  });

  let selecionadosNaVisao = $derived(filtrados.filter((a) => selecionados.includes(a.id)));
  let todosMarcados = $derived(filtrados.length > 0 && selecionadosNaVisao.length === filtrados.length);
  let pesoSelecionado = $derived(selecionadosNaVisao.reduce((s, a) => s + a.peso_atual, 0));

  let totalAbaixo = $derived(filtrados.filter(abaixoDaMeta).length);
  let totalCarencia = $derived(filtrados.filter((a) => a.carencia_dias).length);
  let gmdMedio = $derived.by(() => {
    const comGmd = filtrados.filter((a) => a.gmd_atual !== null);
    if (!comGmd.length) return 0;
    return comGmd.reduce((s, a) => s + (a.gmd_atual ?? 0), 0) / comGmd.length;
  });

  function ordenarPor(coluna: ColunaOrdem) {
    if (colunaOrdem === coluna) {
      ordemAsc = !ordemAsc;
    } else {
      colunaOrdem = coluna;
      ordemAsc = coluna === 'brinco';
    }
  }

  function setaDe(coluna: ColunaOrdem): string {
    if (colunaOrdem !== coluna) return '';
    return ordemAsc ? '↑' : '↓';
  }

  function alternar(id: number) {
    selecionados = selecionados.includes(id)
      ? selecionados.filter((i) => i !== id)
      : [...selecionados, id];
  }

  function alternarTodos() {
    selecionados = todosMarcados ? [] : filtrados.map((a) => a.id);
  }

  function limparSelecao() {
    selecionados = [];
  }

  function levarSelecaoPara(rota: 'pesagem' | 'medicar' | 'venda') {
    const brincos = selecionadosNaVisao.map((a) => a.brinco).join(',');
    router.navegar(rota, brincos);
  }

  function limparFiltros() {
    busca = '';
    router.buscaBrinco = '';
    filtroSexo = 'todos';
    filtroOrigem = 'todos';
    filtroStatus = 'todos';
    filtroLote = 'todos';
  }
</script>

{#if animalAberto}
  <AnimalFicha animal={animalAberto} onVoltar={() => (animalAberto = null)} />
{:else}
  <div class="rebanho">
    <header class="rebanho__header">
      <div>
        <h1 class="page-title">Rebanho</h1>
        <p class="page-subtitle">
          Gado ativo de {auth.user.nome_fazenda} — ordene por peso, GMD ou tempo de cocho e opere em lote
          {#if !apiConectada && !carregando}
            <span class="badge badge--neutro">Modo demonstração (Fazenda São Marcos)</span>
          {/if}
        </p>
      </div>
      <a class="btn btn-outline" href="/api/v1/export/animais.csv" download>Exportar CSV</a>
    </header>

    <section class="resumo panel" aria-label="Resumo dos animais visíveis">
      <div class="resumo__cell">
        <span class="resumo__label">Animais na visão</span>
        <strong class="resumo__value dado">{filtrados.length} cab.</strong>
        <span class="resumo__meta dado">de {animais.length} ativos</span>
      </div>
      <div class="resumo__cell">
        <span class="resumo__label">GMD médio da visão</span>
        <strong
          class="resumo__value dado"
          class:dado--ok={gmdMedio >= gmdMeta}
          class:dado--alerta={gmdMedio < gmdMeta}
        >{formatGmd(gmdMedio)}</strong>
        <span class="resumo__meta">Meta: <span class="dado">{formatGmd(gmdMeta)}</span></span>
      </div>
      <div class="resumo__cell">
        <span class="resumo__label">Abaixo da meta</span>
        <strong class="resumo__value dado" class:dado--alerta={totalAbaixo > 0}>{totalAbaixo} cab.</strong>
        <span class="resumo__meta">Perdem ganho no cocho</span>
      </div>
      <div class="resumo__cell">
        <span class="resumo__label">Em carência sanitária</span>
        <strong class="resumo__value dado" class:dado--alerta={totalCarencia > 0}>{totalCarencia} cab.</strong>
        <span class="resumo__meta">Bloqueados para abate</span>
      </div>
    </section>

    <section class="filtros panel" aria-label="Filtros do rebanho">
      <div class="filtro-campo filtro-campo--busca">
        <label class="label" for="busca-brinco">Brinco</label>
        <input
          id="busca-brinco"
          class="input dado"
          type="search"
          inputmode="numeric"
          placeholder="Ex.: 0402"
          bind:value={busca}
        />
      </div>

      <div class="filtro-campo">
        <span class="label" id="rotulo-sexo">Sexo</span>
        <div class="segmented" role="group" aria-labelledby="rotulo-sexo">
          <button type="button" class:ativo={filtroSexo === 'todos'} onclick={() => (filtroSexo = 'todos')}>Todos</button>
          <button type="button" class:ativo={filtroSexo === 'M'} onclick={() => (filtroSexo = 'M')}>Machos</button>
          <button type="button" class:ativo={filtroSexo === 'F'} onclick={() => (filtroSexo = 'F')}>Fêmeas</button>
        </div>
      </div>

      <div class="filtro-campo">
        <span class="label" id="rotulo-origem">Origem</span>
        <div class="segmented" role="group" aria-labelledby="rotulo-origem">
          <button type="button" class:ativo={filtroOrigem === 'todos'} onclick={() => (filtroOrigem = 'todos')}>Todos</button>
          <button type="button" class:ativo={filtroOrigem === 'nascidos'} onclick={() => (filtroOrigem = 'nascidos')}>
            Nascidos na fazenda
          </button>
        </div>
      </div>

      <div class="filtro-campo">
        <span class="label" id="rotulo-status">Status</span>
        <div class="segmented" role="group" aria-labelledby="rotulo-status">
          <button type="button" class:ativo={filtroStatus === 'todos'} onclick={() => (filtroStatus = 'todos')}>Todos</button>
          <button type="button" class:ativo={filtroStatus === 'abaixo'} onclick={() => (filtroStatus = 'abaixo')}>
            Abaixo da meta
          </button>
          <button type="button" class:ativo={filtroStatus === 'carencia'} onclick={() => (filtroStatus = 'carencia')}>
            Em carência
          </button>
        </div>
      </div>

      <div class="filtro-campo">
        <label class="label" for="filtro-lote">Lote</label>
        <select id="filtro-lote" class="input" bind:value={filtroLote}>
          {#each lotes as lote}
            <option value={lote}>{lote === 'todos' ? 'Todos os lotes' : lote}</option>
          {/each}
        </select>
      </div>

      <button type="button" class="btn btn-ghost filtros__limpar" onclick={limparFiltros}>Limpar filtros</button>
    </section>

    <div class="table-wrap" class:com-barra={selecionadosNaVisao.length >= 2}>
      <table class="table rebanho-table">
        <thead>
          <tr>
            <th class="col-check">
              <input
                type="checkbox"
                aria-label="Selecionar todos os animais da visão"
                checked={todosMarcados}
                onchange={alternarTodos}
              />
            </th>
            <th>
              <button type="button" class="th-ordena" onclick={() => ordenarPor('brinco')}>
                Brinco <span class="dado seta">{setaDe('brinco')}</span>
              </button>
            </th>
            <th>Sexo · Raça · Lote</th>
            <th class="col-num">
              <button type="button" class="th-ordena" onclick={() => ordenarPor('peso_atual')}>
                Peso atual (kg e @) <span class="dado seta">{setaDe('peso_atual')}</span>
              </button>
            </th>
            <th class="col-num">
              <button type="button" class="th-ordena" onclick={() => ordenarPor('gmd_atual')}>
                GMD (kg/d) <span class="dado seta">{setaDe('gmd_atual')}</span>
              </button>
            </th>
            <th class="col-num">
              <button type="button" class="th-ordena" onclick={() => ordenarPor('dias_fazenda')}>
                Dias na fazenda <span class="dado seta">{setaDe('dias_fazenda')}</span>
              </button>
            </th>
            <th class="col-acoes">Ações rápidas</th>
          </tr>
        </thead>
        <tbody>
          {#each filtrados as animal (animal.id)}
            <tr class:linha-selecionada={selecionados.includes(animal.id)}>
              <td class="col-check">
                <input
                  type="checkbox"
                  aria-label={`Selecionar animal ${animal.brinco}`}
                  checked={selecionados.includes(animal.id)}
                  onchange={() => alternar(animal.id)}
                />
              </td>
              <td>
                <button type="button" class="brinco-link dado" onclick={() => (animalAberto = animal)}>
                  #{animal.brinco}
                </button>
                {#if animal.carencia_dias}
                  <span
                    class="badge badge--alerta"
                    title={`${animal.carencia_medicamento} — liberação em ${animal.carencia_liberacao}`}
                  >
                    Carência <span class="dado">{animal.carencia_dias}d</span>
                  </span>
                {/if}
                {#if animal.nascido_na_fazenda}
                  <span class="badge badge--neutro">Nascido aqui</span>
                {/if}
              </td>
              <td class="celula-contexto">
                <span class="dado">{animal.sexo}</span> · {animal.raca} · {animal.lote}
                <small>{animal.pasto}</small>
              </td>
              <td class="col-num">
                <span class="dado">{formatKg(animal.peso_atual)}</span>
                <small class="dado unidade">{formatArroba(animal.peso_atual)}</small>
              </td>
              <td class="col-num">
                {#if animal.gmd_atual === null}
                  <span class="sem-dado">— (1ª pesagem)</span>
                {:else}
                  <span
                    class="dado"
                    class:dado--ok={animal.gmd_atual >= gmdMeta}
                    class:dado--alerta={animal.gmd_atual < gmdMeta}
                  >
                    {animal.gmd_atual < gmdMeta ? '↓ ' : ''}{formatGmd(animal.gmd_atual)}
                  </span>
                {/if}
              </td>
              <td class="col-num"><span class="dado">{animal.dias_fazenda} d</span></td>
              <td class="col-acoes">
                {#if auth.podeEscreverNoCampo}
                  <button type="button" class="btn btn-ghost btn-mini" onclick={() => router.navegar('pesagem', animal.brinco)}>
                    Pesar
                  </button>
                  <button type="button" class="btn btn-ghost btn-mini" onclick={() => router.navegar('medicar', animal.brinco)}>
                    Medicar
                  </button>
                {/if}
                {#if auth.podeGerirFazenda}
                  <button type="button" class="btn btn-ghost btn-mini" onclick={() => router.navegar('venda', animal.brinco)}>
                    Vender
                  </button>
                {/if}
                <button type="button" class="btn btn-ghost btn-mini" onclick={() => (animalAberto = animal)}>Ficha</button>
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="7" class="vazio">
                Nenhum animal atende aos filtros atuais.
                <button type="button" class="btn btn-ghost" onclick={limparFiltros}>Limpar filtros</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if selecionadosNaVisao.length >= 2}
      <div class="barra-lote" role="region" aria-label="Ações em lote para os animais selecionados">
        <div class="barra-lote__info">
          <strong class="dado">{selecionadosNaVisao.length} animais selecionados</strong>
          <span class="dado barra-lote__peso">{formatKg(pesoSelecionado)} · {formatArroba(pesoSelecionado)}</span>
        </div>
        <div class="barra-lote__acoes">
          {#if auth.podeEscreverNoCampo}
            <button type="button" class="btn btn-primary" onclick={() => levarSelecaoPara('pesagem')}>
              Pesar selecionados
            </button>
            <button type="button" class="btn btn-outline" onclick={() => levarSelecaoPara('medicar')}>
              Vacinar ou medicar
            </button>
          {/if}
          {#if auth.podeGerirFazenda}
            <button type="button" class="btn btn-outline" onclick={() => levarSelecaoPara('venda')}>Vender lote</button>
          {/if}
          <button type="button" class="btn btn-ghost barra-lote__limpar" onclick={limparSelecao}>Limpar seleção</button>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .rebanho {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .rebanho__header {
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

  .filtros {
    display: flex;
    align-items: flex-end;
    gap: var(--space-4);
    flex-wrap: wrap;
    padding: var(--space-4);
  }

  .filtro-campo {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 140px;
  }
  .filtro-campo--busca {
    min-width: 170px;
  }

  .label {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--color-ink-secondary);
  }

  .filtros__limpar {
    margin-left: auto;
  }

  .segmented {
    display: inline-flex;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    overflow: hidden;
    background: var(--color-surface);
  }

  .segmented button {
    min-height: 38px;
    padding: 0 var(--space-3);
    border: none;
    border-right: 1px solid var(--color-border);
    background: transparent;
    font-family: var(--font-body);
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

  .table-wrap.com-barra {
    margin-bottom: 76px;
  }

  .th-ordena {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0;
    border: none;
    background: transparent;
    font-family: inherit;
    font-size: inherit;
    font-weight: inherit;
    color: inherit;
    cursor: pointer;
  }
  .th-ordena:hover {
    color: var(--color-primary);
  }

  .seta {
    width: 10px;
    color: var(--color-primary);
  }

  .col-check {
    width: 36px;
    text-align: center;
  }

  .col-acoes {
    white-space: nowrap;
    text-align: right;
  }

  .btn-mini {
    min-height: 28px;
    padding: 0 var(--space-2);
    font-size: var(--text-xs);
  }

  .brinco-link {
    padding: 0;
    border: none;
    background: transparent;
    font-family: var(--font-dado);
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
    color: var(--color-ink);
    cursor: pointer;
    text-decoration: underline;
    text-decoration-color: var(--color-border-strong);
    text-underline-offset: 3px;
  }
  .brinco-link:hover {
    color: var(--color-primary);
  }

  .celula-contexto {
    color: var(--color-ink-secondary);
    font-size: var(--text-sm);
  }
  .celula-contexto small {
    display: block;
    color: var(--color-ink-tertiary);
    font-size: var(--text-xs);
  }

  .unidade {
    display: block;
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .sem-dado {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .linha-selecionada {
    background: var(--color-primary-bg);
  }

  .vazio {
    padding: var(--space-8);
    text-align: center;
    color: var(--color-ink-tertiary);
  }

  .barra-lote {
    position: fixed;
    left: var(--sidebar-largura);
    right: 0;
    bottom: 0;
    z-index: var(--z-nav);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
    padding: var(--space-3) var(--space-6);
    background: var(--n-900);
    color: #fff;
    box-shadow: var(--shadow-md);
  }

  .barra-lote__info {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
  }
  .barra-lote__info strong {
    font-size: var(--text-md);
  }
  .barra-lote__peso {
    font-size: var(--text-sm);
    color: var(--n-300);
  }

  .barra-lote__acoes {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .barra-lote__acoes :global(.btn-outline) {
    background: transparent;
    color: #fff;
    border-color: var(--n-400);
  }
  .barra-lote__acoes :global(.btn-outline:hover) {
    background: var(--n-800);
  }

  .barra-lote__limpar {
    color: var(--n-300);
  }
  .barra-lote__limpar:hover {
    background: var(--n-800);
    color: #fff;
  }

  @media (max-width: 1024px) {
    .resumo {
      grid-template-columns: repeat(2, 1fr);
    }
    .resumo__cell:nth-child(2) {
      border-right: none;
    }
    .barra-lote {
      left: 0;
    }
  }

  @media (max-width: 860px) {
    .barra-lote {
      left: 0;
      bottom: var(--bottom-nav-altura);
      padding: var(--space-3) var(--space-4);
    }
    .table-wrap.com-barra {
      margin-bottom: 112px;
    }
  }

  @media (max-width: 768px) {
    .filtros {
      flex-direction: column;
      align-items: stretch;
      gap: var(--space-3);
      padding: var(--space-3) var(--space-4);
    }
    .filtro-campo,
    .filtro-campo--busca {
      width: 100%;
      min-width: 0;
    }
    .segmented {
      display: flex;
      width: 100%;
      overflow-x: auto;
    }
    .segmented button {
      flex: 1;
      white-space: nowrap;
      padding: 0 var(--space-2);
    }
    .filtros__limpar {
      margin-left: 0;
      width: 100%;
    }
    .resumo {
      grid-template-columns: 1fr;
    }
    .resumo__cell {
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }

    /* Mobile Ledger Rows: full animal readout in 100% screen width without horizontal cutoff */
    .table-wrap {
      overflow-x: hidden;
    }
    .table,
    .table tbody {
      display: block;
      width: 100%;
    }
    .table thead {
      display: none;
    }
    .table tbody tr {
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr) auto;
      gap: var(--space-2) var(--space-3);
      padding: var(--space-3) var(--space-4);
      border-bottom: 1px solid var(--color-border);
      align-items: center;
    }
    .table tbody tr:last-child {
      border-bottom: none;
    }
    .table tbody td {
      padding: 0;
      border: none;
    }
    .table tbody td.col-check {
      grid-column: 1;
      grid-row: 1;
      width: auto;
      text-align: left;
    }
    .table tbody td:nth-child(2) {
      grid-column: 2;
      grid-row: 1;
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }
    .table tbody td:nth-child(4) {
      grid-column: 3;
      grid-row: 1;
      text-align: right;
    }
    .table tbody td:nth-child(4) .unidade {
      display: inline;
      margin-left: 4px;
    }
    .table tbody td.celula-contexto {
      grid-column: 1 / 3;
      grid-row: 2;
      font-size: var(--text-xs);
    }
    .table tbody td.celula-contexto small {
      display: inline;
      margin-left: 6px;
    }
    .table tbody td:nth-child(5) {
      grid-column: 3;
      grid-row: 2;
      text-align: right;
      font-size: var(--text-sm);
    }
    .table tbody td:nth-child(6) {
      display: none;
    }
    .table tbody td.col-acoes {
      grid-column: 1 / -1;
      grid-row: 3;
      display: flex;
      gap: var(--space-2);
      padding-top: var(--space-2);
      border-top: 1px solid var(--color-border);
      justify-content: flex-start;
      flex-wrap: wrap;
    }
    .table tbody td.col-acoes .btn-mini {
      flex: 1;
      min-height: 34px;
    }
    .table tbody td.vazio {
      grid-column: 1 / -1;
      padding: var(--space-6) var(--space-4);
    }
  }
</style>
