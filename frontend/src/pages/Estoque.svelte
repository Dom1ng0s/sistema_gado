<script lang="ts">
  /**
   * Trilha 5 / MT-5.4 — Estoque como livro-razão (vw_saldo_estoque).
   * Barra de saldo atual contra estoque mínimo, alerta de validade próxima
   * e extrato de entradas e saídas (estoque_movimentacoes) com autoria.
   */
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatBrl, formatDateBr } from '../lib/format';

  interface Insumo {
    id: number;
    nome: string;
    categoria: 'Medicamento' | 'Vacina' | 'Suplemento' | 'Insumo';
    unidade: string;
    saldo: number;
    estoque_minimo: number;
    custo_unitario: number;
    validade: string | null;
    lote_fabricante: string;
    dias_carencia: number;
  }

  interface Movimentacao {
    id: number;
    insumo_id: number;
    data: string;
    tipo: 'entrada' | 'saida';
    quantidade: number;
    motivo: string;
    registrado_por: string;
  }

  const HOJE = new Date('2026-10-24T00:00:00Z');

  /** Almoxarifado da Fazenda São Marcos. */
  const INSUMOS_DEMO: Insumo[] = [
    { id: 1, nome: 'Ivermectina 1% (1 L)', categoria: 'Medicamento', unidade: 'frasco', saldo: 2, estoque_minimo: 4, custo_unitario: 168.9, validade: '2027-03-18', lote_fabricante: 'IV-2026-114', dias_carencia: 35 },
    { id: 2, nome: 'Vacina contra aftosa (50 doses)', categoria: 'Vacina', unidade: 'frasco', saldo: 6, estoque_minimo: 5, custo_unitario: 212.4, validade: '2026-11-30', lote_fabricante: 'AF-2026-C9', dias_carencia: 0 },
    { id: 3, nome: 'Sal mineral proteinado (30 kg)', categoria: 'Suplemento', unidade: 'saco', saldo: 18, estoque_minimo: 12, custo_unitario: 237.0, validade: null, lote_fabricante: 'NM-2026-48', dias_carencia: 0 },
    { id: 4, nome: 'Cipermetrina pour-on (1 L)', categoria: 'Medicamento', unidade: 'frasco', saldo: 1, estoque_minimo: 3, custo_unitario: 142.6, validade: '2026-12-12', lote_fabricante: 'CP-2026-77', dias_carencia: 5 },
    { id: 5, nome: 'Albendazol 10% (5 L)', categoria: 'Medicamento', unidade: 'galão', saldo: 3, estoque_minimo: 2, custo_unitario: 398.5, validade: '2028-01-20', lote_fabricante: 'AB-2026-31', dias_carencia: 14 },
    { id: 6, nome: 'Seringa dosadora e agulhas', categoria: 'Insumo', unidade: 'kit', saldo: 4, estoque_minimo: 2, custo_unitario: 86.0, validade: null, lote_fabricante: '—', dias_carencia: 0 },
    { id: 7, nome: 'Vacina polivalente clostridiose', categoria: 'Vacina', unidade: 'frasco', saldo: 2, estoque_minimo: 2, custo_unitario: 189.9, validade: '2026-10-31', lote_fabricante: 'CL-2026-05', dias_carencia: 0 }
  ];

  const MOVIMENTACOES_DEMO: Movimentacao[] = [
    { id: 1, insumo_id: 1, data: '2026-10-10', tipo: 'saida', quantidade: 1, motivo: 'Aplicação no Lote 2026-A (38 cab.)', registrado_por: 'davi.dono' },
    { id: 2, insumo_id: 1, data: '2026-10-05', tipo: 'entrada', quantidade: 3, motivo: 'Compra — Agropecuária Vale Verde', registrado_por: 'davi.dono' },
    { id: 3, insumo_id: 4, data: '2026-10-19', tipo: 'saida', quantidade: 2, motivo: 'Mosca-do-chifre no Lote 2026-B', registrado_por: 'joao.vaqueiro' },
    { id: 4, insumo_id: 3, data: '2026-10-18', tipo: 'entrada', quantidade: 40, motivo: 'Compra — fornecedor Nutri', registrado_por: 'davi.dono' },
    { id: 5, insumo_id: 3, data: '2026-10-21', tipo: 'saida', quantidade: 22, motivo: 'Reposição de cocho nos piquetes 1 a 4', registrado_por: 'joao.vaqueiro' },
    { id: 6, insumo_id: 2, data: '2026-04-28', tipo: 'saida', quantidade: 5, motivo: 'Aftosa 1ª etapa (235 cab.)', registrado_por: 'joao.vaqueiro' },
    { id: 7, insumo_id: 2, data: '2026-10-12', tipo: 'entrada', quantidade: 6, motivo: 'Compra para a 2ª etapa', registrado_por: 'davi.dono' },
    { id: 8, insumo_id: 5, data: '2026-09-11', tipo: 'saida', quantidade: 1, motivo: 'Vermifugação de bezerros', registrado_por: 'davi.dono' },
    { id: 9, insumo_id: 7, data: '2026-08-02', tipo: 'entrada', quantidade: 2, motivo: 'Compra — Agropecuária Vale Verde', registrado_por: 'davi.dono' }
  ];

  let insumos = $state<Insumo[]>(INSUMOS_DEMO);
  let movimentacoes = $state<Movimentacao[]>(MOVIMENTACOES_DEMO);
  let apiConectada = $state(false);
  let carregando = $state(true);

  let filtroCategoria = $state('todas');
  let extratoAberto = $state<number | null>(null);

  // Movimentação manual (entrada de compra ou baixa de uso)
  let formAberto = $state(false);
  let movInsumoId = $state<number>(INSUMOS_DEMO[0].id);
  let movTipo = $state<'entrada' | 'saida'>('entrada');
  let movQuantidade = $state('1');
  let movMotivo = $state('');
  let mensagem = $state('');

  onMount(async () => {
    try {
      const dados = await apiFetch<{ insumos?: Insumo[]; movimentacoes?: Movimentacao[] } | Insumo[]>('/api/estoque');
      if (Array.isArray(dados)) {
        if (dados.length) {
          insumos = dados;
          apiConectada = true;
        }
      } else {
        if (dados.insumos?.length) {
          insumos = dados.insumos;
          apiConectada = true;
        }
        if (dados.movimentacoes) movimentacoes = dados.movimentacoes;
      }
    } catch {
      // Livro-razão segue navegável com o almoxarifado de demonstração.
      apiConectada = false;
    } finally {
      carregando = false;
    }
  });

  function diasPara(iso: string): number {
    const d = new Date(`${iso}T00:00:00Z`);
    return Math.round((d.getTime() - HOJE.getTime()) / 86400000);
  }

  function nivelPct(i: Insumo): number {
    // A escala vai até o dobro do mínimo: 50% da barra marca exatamente o estoque mínimo.
    const referencia = Math.max(i.estoque_minimo * 2, 1);
    return Math.min((i.saldo / referencia) * 100, 100);
  }

  function critico(i: Insumo): boolean {
    return i.saldo <= i.estoque_minimo;
  }

  function validadeProxima(i: Insumo): boolean {
    return i.validade !== null && diasPara(i.validade) <= 60;
  }

  function validadeVencida(i: Insumo): boolean {
    return i.validade !== null && diasPara(i.validade) < 0;
  }

  function formatQtd(valor: number, unidade: string): string {
    const n = Number.isInteger(valor) ? String(valor) : valor.toFixed(1).replace('.', ',');
    return `${n} ${unidade}${valor === 1 ? '' : 's'}`;
  }

  let categorias = $derived(['todas', ...Array.from(new Set(insumos.map((i) => i.categoria))).sort()]);
  let filtrados = $derived(
    filtroCategoria === 'todas' ? insumos : insumos.filter((i) => i.categoria === filtroCategoria)
  );

  let itensCriticos = $derived(insumos.filter(critico));
  let itensValidade = $derived(insumos.filter((i) => validadeProxima(i)));
  let valorEmEstoque = $derived(insumos.reduce((s, i) => s + i.saldo * i.custo_unitario, 0));

  function extratoDe(insumoId: number): Movimentacao[] {
    return movimentacoes
      .filter((m) => m.insumo_id === insumoId)
      .sort((a, b) => b.data.localeCompare(a.data));
  }

  async function registrarMovimentacao(evento: SubmitEvent) {
    evento.preventDefault();
    const quantidade = Number(movQuantidade.replace(',', '.'));
    if (!Number.isFinite(quantidade) || quantidade <= 0) {
      mensagem = 'Informe uma quantidade maior que zero.';
      return;
    }
    if (!movMotivo.trim()) {
      mensagem = 'Descreva o motivo da movimentação para o extrato auditável.';
      return;
    }

    const corpo = JSON.stringify({
      insumo_id: movInsumoId,
      tipo: movTipo,
      quantidade,
      motivo: movMotivo.trim()
    });

    try {
      await apiFetch('/api/estoque', { method: 'POST', body: corpo });
      mensagem = 'Movimentação gravada.';
      const dados = await apiFetch<{ insumos?: Insumo[]; movimentacoes?: Movimentacao[] }>('/api/estoque');
      if (dados.insumos?.length) insumos = dados.insumos;
      if (dados.movimentacoes) movimentacoes = dados.movimentacoes;
    } catch {
      // Demonstração: a movimentação ajusta o saldo e entra no extrato local.
      const delta = movTipo === 'entrada' ? quantidade : -quantidade;
      insumos = insumos.map((i) =>
        i.id === movInsumoId ? { ...i, saldo: Math.max(0, Number((i.saldo + delta).toFixed(1))) } : i
      );
      movimentacoes = [
        {
          id: Date.now(),
          insumo_id: movInsumoId,
          data: HOJE.toISOString().slice(0, 10),
          tipo: movTipo,
          quantidade,
          motivo: movMotivo.trim(),
          registrado_por: auth.user.username
        },
        ...movimentacoes
      ];
      mensagem = 'Movimentação guardada na visão de demonstração (API indisponível).';
    }

    movMotivo = '';
    movQuantidade = '1';
  }
</script>

<div class="estoque">
  <header class="estoque__header">
    <div>
      <h1 class="page-title">Estoque</h1>
      <p class="page-subtitle">
        Livro-razão de medicamentos e insumos de {auth.user.nome_fazenda}, com saldo contra estoque mínimo
        {#if !apiConectada && !carregando}
          <span class="badge badge--neutro">Modo demonstração (Fazenda São Marcos)</span>
        {/if}
      </p>
    </div>
    {#if auth.podeEscreverNoCampo}
      <button type="button" class="btn btn-primary" onclick={() => (formAberto = !formAberto)}>
        {formAberto ? 'Fechar movimentação' : 'Lançar movimentação'}
      </button>
    {/if}
  </header>

  <section class="indicadores panel" aria-label="Situação do almoxarifado">
    <div class="indicador">
      <span class="indicador__label">Itens em estoque crítico</span>
      <strong class="indicador__value dado" class:dado--alerta={itensCriticos.length > 0} class:dado--ok={itensCriticos.length === 0}>
        {itensCriticos.length}
      </strong>
      <span class="indicador__meta">Saldo no mínimo ou abaixo</span>
    </div>
    <div class="indicador">
      <span class="indicador__label">Validade em 60 dias</span>
      <strong class="indicador__value dado" class:dado--alerta={itensValidade.length > 0}>{itensValidade.length}</strong>
      <span class="indicador__meta">Usar antes de vencer</span>
    </div>
    <div class="indicador">
      <span class="indicador__label">Itens cadastrados</span>
      <strong class="indicador__value dado">{insumos.length}</strong>
      <span class="indicador__meta dado">{categorias.length - 1} categorias</span>
    </div>
    {#if auth.podeVerFinanceiro}
      <div class="indicador">
        <span class="indicador__label">Valor parado em estoque</span>
        <strong class="indicador__value dado">{formatBrl(valorEmEstoque)}</strong>
        <span class="indicador__meta">Saldo × custo unitário</span>
      </div>
    {/if}
  </section>

  {#if formAberto && auth.podeEscreverNoCampo}
    <form class="form-mov panel" onsubmit={registrarMovimentacao}>
      <h2 class="section-title">Nova movimentação</h2>
      <div class="form-mov__linha">
        <div class="campo">
          <label class="label" for="mov-insumo">Insumo</label>
          <select id="mov-insumo" class="input" bind:value={movInsumoId}>
            {#each insumos as i}
              <option value={i.id}>{i.nome}</option>
            {/each}
          </select>
        </div>
        <div class="campo">
          <span class="label" id="rotulo-tipo">Tipo</span>
          <div class="segmented" role="group" aria-labelledby="rotulo-tipo">
            <button type="button" class:ativo={movTipo === 'entrada'} onclick={() => (movTipo = 'entrada')}>Entrada</button>
            <button type="button" class:ativo={movTipo === 'saida'} onclick={() => (movTipo = 'saida')}>Saída</button>
          </div>
        </div>
        <div class="campo">
          <label class="label" for="mov-qtd">Quantidade</label>
          <input id="mov-qtd" class="input dado" type="text" inputmode="decimal" bind:value={movQuantidade} />
        </div>
        <div class="campo">
          <label class="label" for="mov-motivo">Motivo</label>
          <input id="mov-motivo" class="input" type="text" placeholder="Ex.: Aplicação no Lote 2026-A" bind:value={movMotivo} />
        </div>
      </div>
      <div class="form-mov__rodape">
        {#if mensagem}
          <span class="form-mov__msg">{mensagem}</span>
        {/if}
        <button type="submit" class="btn btn-primary">Gravar movimentação</button>
      </div>
    </form>
  {/if}

  <div class="filtro-linha">
    <label class="label" for="filtro-categoria">Categoria</label>
    <select id="filtro-categoria" class="input filtro-select" bind:value={filtroCategoria}>
      {#each categorias as c}
        <option value={c}>{c === 'todas' ? 'Todas as categorias' : c}</option>
      {/each}
    </select>
  </div>

  <section class="lista" aria-label="Saldo de insumos">
    {#each filtrados as i (i.id)}
      {@const estaCritico = critico(i)}
      {@const aberto = extratoAberto === i.id}
      <article class="item panel" class:item--alerta={estaCritico}>
        <div class="item__topo">
          <div class="item__id">
            <h2 class="item__nome">{i.nome}</h2>
            <small class="item__meta">
              {i.categoria} · lote <span class="dado">{i.lote_fabricante}</span>
              {#if i.dias_carencia > 0}
                · carência de <span class="dado">{i.dias_carencia} d</span>
              {/if}
            </small>
          </div>
          <div class="item__tags">
            {#if estaCritico}
              <span class="badge badge--alerta">Estoque crítico</span>
            {:else}
              <span class="badge badge--ok">Saldo suficiente</span>
            {/if}
            {#if validadeVencida(i)}
              <span class="badge badge--alerta">Validade vencida</span>
            {:else if validadeProxima(i) && i.validade}
              <span class="badge badge--alerta">
                Vence em <span class="dado">{diasPara(i.validade)}d</span>
              </span>
            {/if}
          </div>
        </div>

        <div class="item__grade">
          <div class="item__dado">
            <span class="item__rotulo">Saldo atual</span>
            <strong class="dado" class:dado--alerta={estaCritico} class:dado--ok={!estaCritico}>
              {formatQtd(i.saldo, i.unidade)}
            </strong>
          </div>
          <div class="item__dado">
            <span class="item__rotulo">Estoque mínimo</span>
            <strong class="dado">{formatQtd(i.estoque_minimo, i.unidade)}</strong>
          </div>
          <div class="item__dado">
            <span class="item__rotulo">Validade</span>
            <strong>
              {#if i.validade}
                <span class="dado" class:dado--alerta={validadeProxima(i)}>{formatDateBr(i.validade)}</span>
              {:else}
                <span class="sem-dado">Não se aplica</span>
              {/if}
            </strong>
          </div>
          {#if auth.podeVerFinanceiro}
            <div class="item__dado">
              <span class="item__rotulo">Valor em estoque</span>
              <strong class="dado">{formatBrl(i.saldo * i.custo_unitario)}</strong>
            </div>
          {/if}
        </div>

        <div class="nivel">
          <div class="nivel__trilha" role="meter" aria-valuenow={i.saldo} aria-valuemin="0" aria-valuemax={i.estoque_minimo * 2} aria-label={`Saldo de ${i.nome}`}>
            <span class="nivel__barra" class:nivel__barra--alerta={estaCritico} style:width={`${nivelPct(i)}%`}></span>
            <span class="nivel__minimo" aria-hidden="true"></span>
          </div>
          <small class="nivel__legenda">
            O traço marca o estoque mínimo de <span class="dado">{formatQtd(i.estoque_minimo, i.unidade)}</span>
          </small>
        </div>

        <div class="item__rodape">
          <button type="button" class="btn btn-ghost" onclick={() => (extratoAberto = aberto ? null : i.id)}>
            {aberto ? 'Fechar extrato' : 'Ver extrato de entradas e saídas'}
          </button>
        </div>

        {#if aberto}
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Tipo</th>
                  <th class="col-num">Quantidade</th>
                  <th>Motivo</th>
                  <th>Registrado por</th>
                </tr>
              </thead>
              <tbody>
                {#each extratoDe(i.id) as m (m.id)}
                  <tr>
                    <td><span class="dado">{formatDateBr(m.data)}</span></td>
                    <td>
                      {#if m.tipo === 'entrada'}
                        <span class="badge badge--ok">Entrada</span>
                      {:else}
                        <span class="badge badge--neutro">Saída</span>
                      {/if}
                    </td>
                    <td class="col-num">
                      <span class="dado" class:dado--ok={m.tipo === 'entrada'}>
                        {m.tipo === 'entrada' ? '+' : '−'}{formatQtd(m.quantidade, i.unidade)}
                      </span>
                    </td>
                    <td>{m.motivo}</td>
                    <td><span class="autor dado">{m.registrado_por}</span></td>
                  </tr>
                {:else}
                  <tr>
                    <td colspan="5" class="vazio">Nenhuma movimentação registrada para este item.</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </article>
    {/each}
  </section>
</div>

<style>
  .estoque {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .estoque__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .indicadores {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
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

  .form-mov {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .form-mov__linha {
    display: grid;
    grid-template-columns: 1fr 180px 140px 1fr;
    gap: var(--space-4);
  }

  .form-mov__rodape {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .form-mov__msg {
    margin-right: auto;
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
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

  .filtro-linha {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .filtro-select {
    max-width: 260px;
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
    padding: 0 var(--space-4);
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
  .segmented button.ativo {
    background: var(--color-primary);
    color: #fff;
    font-weight: var(--weight-semibold);
  }

  .lista {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .item {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-5);
  }

  .item--alerta {
    border-left: 3px solid var(--color-danger);
  }

  .item__topo {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .item__nome {
    font-size: var(--text-lg);
    letter-spacing: var(--tracking-title);
  }

  .item__meta {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .item__tags {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .item__grade {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: var(--space-4);
  }

  .item__dado {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .item__rotulo {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .item__dado strong {
    font-size: var(--text-base);
  }

  .nivel {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .nivel__trilha {
    position: relative;
    height: 4px;
    width: 100%;
    background: var(--n-100);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }

  .nivel__barra {
    display: block;
    height: 100%;
    background: var(--color-primary);
    transition: width var(--transition-normal);
  }

  .nivel__barra--alerta {
    background: var(--color-danger);
  }

  .nivel__minimo {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 50%;
    width: 1px;
    background: var(--n-350);
  }

  .nivel__legenda {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .item__rodape {
    display: flex;
    justify-content: flex-start;
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .autor {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .sem-dado {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .vazio {
    padding: var(--space-6);
    text-align: center;
    color: var(--color-ink-tertiary);
  }

  @media (max-width: 1024px) {
    .form-mov__linha {
      grid-template-columns: 1fr 1fr;
    }
  }

  @media (max-width: 768px) {
    .indicador {
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }
    .form-mov {
      padding: var(--space-4);
    }
    .form-mov__linha {
      grid-template-columns: 1fr;
    }
    .form-mov__rodape {
      flex-wrap: wrap;
    }
    .filtro-linha {
      flex-direction: column;
      align-items: stretch;
    }
    .filtro-select {
      max-width: 100%;
      width: 100%;
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
  }
</style>
