<script lang="ts">
  /**
   * Trilha 4 (MT-4.1 a MT-4.4) — Inteligência financeira.
   * Fluxo de caixa anual (v_fluxo_caixa), P&L por lote (vw_resultado_lote)
   * e contas a pagar (financial_schedule). Escrita visível apenas para quem gere a fazenda.
   */
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatBrl, formatDateBr, KG_POR_ARROBA } from '../lib/format';
  import EChart from '../components/charts/EChart.svelte';

  interface MesFluxo {
    mes: number;
    entradas: number;
    saidas: number;
  }

  interface Custo {
    id: number;
    data: string;
    descricao: string;
    categoria: string;
    valor: number;
    registrado_por: string;
  }

  interface ResultadoLote {
    lote: string;
    cabecas_ativas: number;
    cabecas_vendidas: number;
    investimento_compra: number;
    custos_rateados: number;
    receita_vendas: number;
    valuation_vivo: number;
  }

  interface Compromisso {
    id: number;
    descricao: string;
    categoria: string;
    vencimento: string;
    valor: number;
    status: 'pendente' | 'pago';
  }

  const CATEGORIAS = ['Suplementação', 'Mão de obra', 'Manutenção de pasto', 'Sanidade', 'Combustível', 'Compra de gado'];

  const ANOS = [2026, 2025];

  /** Fluxo de caixa de demonstração — Fazenda São Marcos. */
  const FLUXO_DEMO: Record<number, MesFluxo[]> = {
    2026: [
      { mes: 1, entradas: 0, saidas: 182400.0 },
      { mes: 2, entradas: 0, saidas: 28640.5 },
      { mes: 3, entradas: 96300.0, saidas: 31210.8 },
      { mes: 4, entradas: 0, saidas: 29880.0 },
      { mes: 5, entradas: 0, saidas: 164520.0 },
      { mes: 6, entradas: 142850.0, saidas: 42310.4 },
      { mes: 7, entradas: 0, saidas: 33940.2 },
      { mes: 8, entradas: 78400.0, saidas: 30115.6 },
      { mes: 9, entradas: 0, saidas: 36720.9 },
      { mes: 10, entradas: 203600.0, saidas: 41980.3 },
      { mes: 11, entradas: 0, saidas: 0 },
      { mes: 12, entradas: 0, saidas: 0 }
    ],
    2025: [
      { mes: 1, entradas: 0, saidas: 148200.0 },
      { mes: 2, entradas: 54300.0, saidas: 26410.0 },
      { mes: 3, entradas: 0, saidas: 28970.4 },
      { mes: 4, entradas: 118600.0, saidas: 31840.7 },
      { mes: 5, entradas: 0, saidas: 139500.0 },
      { mes: 6, entradas: 0, saidas: 30210.2 },
      { mes: 7, entradas: 162400.0, saidas: 34880.1 },
      { mes: 8, entradas: 0, saidas: 29640.8 },
      { mes: 9, entradas: 91200.0, saidas: 32470.5 },
      { mes: 10, entradas: 0, saidas: 35910.6 },
      { mes: 11, entradas: 134700.0, saidas: 38240.0 },
      { mes: 12, entradas: 0, saidas: 27830.9 }
    ]
  };

  const CUSTOS_DEMO: Record<number, Custo[]> = {
    2026: [
      { id: 1, data: '2026-10-18', descricao: 'Sal mineral proteinado (40 sacos)', categoria: 'Suplementação', valor: 9480.0, registrado_por: 'davi.dono' },
      { id: 2, data: '2026-10-12', descricao: 'Folha do vaqueiro e encargos', categoria: 'Mão de obra', valor: 4820.6, registrado_por: 'davi.dono' },
      { id: 3, data: '2026-10-05', descricao: 'Ivermectina 1% (1 L) e seringas', categoria: 'Sanidade', valor: 1340.4, registrado_por: 'joao.vaqueiro' },
      { id: 4, data: '2026-09-28', descricao: 'Roçada e reforma do Piquete 2', categoria: 'Manutenção de pasto', valor: 12900.0, registrado_por: 'davi.dono' },
      { id: 5, data: '2026-09-14', descricao: 'Diesel S10 (800 L)', categoria: 'Combustível', valor: 5120.0, registrado_por: 'davi.dono' },
      { id: 6, data: '2026-08-22', descricao: 'Ureia pecuária e núcleo (seca)', categoria: 'Suplementação', valor: 11760.3, registrado_por: 'davi.dono' },
      { id: 7, data: '2026-06-08', descricao: 'Compra de 42 garrotes (Lote 2026-B)', categoria: 'Compra de gado', valor: 164520.0, registrado_por: 'davi.dono' },
      { id: 8, data: '2026-05-24', descricao: 'Compra de 38 garrotes (Lote 2026-A)', categoria: 'Compra de gado', valor: 139880.0, registrado_por: 'davi.dono' },
      { id: 9, data: '2026-04-11', descricao: 'Vacina contra aftosa (2ª etapa)', categoria: 'Sanidade', valor: 3260.0, registrado_por: 'joao.vaqueiro' },
      { id: 10, data: '2026-03-02', descricao: 'Arame liso e mourões de cerca', categoria: 'Manutenção de pasto', valor: 8740.5, registrado_por: 'davi.dono' },
      { id: 15, data: '2026-01-19', descricao: 'Compra de 48 garrotes (reposição de janeiro)', categoria: 'Compra de gado', valor: 182400.0, registrado_por: 'davi.dono' }
    ],
    2025: [
      { id: 11, data: '2025-11-20', descricao: 'Sal mineral e núcleo de seca', categoria: 'Suplementação', valor: 10210.0, registrado_por: 'davi.dono' },
      { id: 12, data: '2025-09-15', descricao: 'Folha do vaqueiro e encargos', categoria: 'Mão de obra', valor: 4480.0, registrado_por: 'davi.dono' },
      { id: 13, data: '2025-05-06', descricao: 'Compra de 36 garrotes (Lote 2025-C)', categoria: 'Compra de gado', valor: 139500.0, registrado_por: 'davi.dono' },
      { id: 14, data: '2025-04-18', descricao: 'Controle de carrapato do rebanho', categoria: 'Sanidade', valor: 2980.4, registrado_por: 'joao.vaqueiro' }
    ]
  };

  const LOTES_DEMO: ResultadoLote[] = [
    { lote: 'Lote 2025-C', cabecas_ativas: 12, cabecas_vendidas: 24, investimento_compra: 139500.0, custos_rateados: 41280.6, receita_vendas: 246900.0, valuation_vivo: 52140.0 },
    { lote: 'Lote 2026-A', cabecas_ativas: 38, cabecas_vendidas: 0, investimento_compra: 139880.0, custos_rateados: 32410.9, receita_vendas: 0, valuation_vivo: 196420.0 },
    { lote: 'Lote 2026-B', cabecas_ativas: 42, cabecas_vendidas: 0, investimento_compra: 164520.0, custos_rateados: 28970.4, receita_vendas: 0, valuation_vivo: 221380.0 },
    { lote: 'Lote 2024-D', cabecas_ativas: 0, cabecas_vendidas: 31, investimento_compra: 108600.0, custos_rateados: 39840.2, receita_vendas: 171300.0, valuation_vivo: 0 }
  ];

  const AGENDA_DEMO: Compromisso[] = [
    { id: 1, descricao: 'Aftosa 2ª etapa — compra da vacina', categoria: 'Sanidade', vencimento: '2026-10-28', valor: 4200.0, status: 'pendente' },
    { id: 2, descricao: 'Parcela do sal mineral (fornecedor Nutri)', categoria: 'Suplementação', vencimento: '2026-10-20', valor: 9480.0, status: 'pendente' },
    { id: 3, descricao: 'Energia elétrica da sede', categoria: 'Manutenção de pasto', vencimento: '2026-11-05', valor: 1860.4, status: 'pendente' },
    { id: 4, descricao: 'Folha do vaqueiro (novembro)', categoria: 'Mão de obra', vencimento: '2026-11-30', valor: 4820.6, status: 'pendente' },
    { id: 5, descricao: 'Diesel S10 — pedido de setembro', categoria: 'Combustível', vencimento: '2026-10-01', valor: 5120.0, status: 'pago' }
  ];

  const HOJE = new Date('2026-10-24T00:00:00Z');
  const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

  type Aba = 'fluxo' | 'lotes' | 'contas';

  let ano = $state(2026);
  let aba = $state<Aba>('fluxo');
  let apiConectada = $state(false);
  let carregando = $state(false);

  let fluxo = $state<MesFluxo[]>(FLUXO_DEMO[2026]);
  let custos = $state<Custo[]>(CUSTOS_DEMO[2026]);
  let lotes = $state<ResultadoLote[]>(LOTES_DEMO);
  let agenda = $state<Compromisso[]>(AGENDA_DEMO);

  let filtroCategoria = $state('todas');

  // Lançamento de custo (apenas para quem gere a fazenda)
  let formAberto = $state(false);
  let novoData = $state('2026-10-24');
  let novoDescricao = $state('');
  let novoCategoria = $state(CATEGORIAS[0]);
  let novoValor = $state('');
  let novoAgendado = $state(false);
  let mensagemForm = $state('');

  async function carregarAno(alvo: number) {
    carregando = true;
    try {
      const [resumo, detalhe, pl, compromissos] = await Promise.all([
        apiFetch<{ meses: MesFluxo[] }>(`/api/financeiro/resumo?ano=${alvo}`).catch(() => null),
        apiFetch<Custo[] | { custos: Custo[] }>(`/api/financeiro/custos?ano=${alvo}`).catch(() => null),
        apiFetch<ResultadoLote[] | { lotes: ResultadoLote[] }>('/api/financeiro/resultado-lotes').catch(() => null),
        apiFetch<Compromisso[] | { agendamentos: Compromisso[] }>(`/api/financeiro/agendamentos?ano=${alvo}`).catch(() => null)
      ]);

      if (resumo?.meses?.length) {
        fluxo = resumo.meses;
        apiConectada = true;
      } else {
        fluxo = FLUXO_DEMO[alvo] ?? [];
      }

      const listaCustos = Array.isArray(detalhe) ? detalhe : detalhe?.custos;
      custos = listaCustos?.length ? listaCustos : (CUSTOS_DEMO[alvo] ?? []);
      if (listaCustos?.length) apiConectada = true;

      const listaLotes = Array.isArray(pl) ? pl : pl?.lotes;
      lotes = listaLotes?.length ? listaLotes : LOTES_DEMO;

      const listaAgenda = Array.isArray(compromissos) ? compromissos : compromissos?.agendamentos;
      agenda = listaAgenda?.length ? listaAgenda : AGENDA_DEMO;
    } catch {
      // Ano segue navegável com a base de demonstração.
      fluxo = FLUXO_DEMO[alvo] ?? [];
      custos = CUSTOS_DEMO[alvo] ?? [];
      apiConectada = false;
    } finally {
      carregando = false;
    }
  }

  onMount(() => {
    carregarAno(ano);
  });

  function trocarAno(alvo: number) {
    ano = alvo;
    filtroCategoria = 'todas';
    carregarAno(alvo);
  }

  let totalEntradas = $derived(fluxo.reduce((s, m) => s + m.entradas, 0));
  let totalSaidas = $derived(fluxo.reduce((s, m) => s + m.saidas, 0));
  let saldoLiquido = $derived(totalEntradas - totalSaidas);

  // Custo da @ produzida: só o custeio operacional entra no numerador — a compra do animal
  // é investimento em estoque, não custo de produção de arroba.
  let compraDeGado = $derived(
    custos.filter((c) => c.categoria === 'Compra de gado').reduce((s, c) => s + c.valor, 0)
  );
  let custoOperacional = $derived(Math.max(totalSaidas - compraDeGado, 0));

  let diasDoPeriodo = $derived(
    ano === HOJE.getUTCFullYear()
      ? Math.round((HOJE.getTime() - Date.UTC(ano, 0, 1)) / 86400000)
      : 365
  );
  // Arrobas produzidas = cabeças do período × GMD médio × dias, convertido a @.
  let cabecasDoPeriodo = $derived(lotes.reduce((s, l) => s + l.cabecas_ativas + l.cabecas_vendidas, 0));
  let arrobasProduzidas = $derived(
    (cabecasDoPeriodo * auth.user.gmd_meta * diasDoPeriodo) / KG_POR_ARROBA
  );
  let custoPorArroba = $derived(arrobasProduzidas > 0 ? custoOperacional / arrobasProduzidas : null);

  let categorias = $derived(['todas', ...Array.from(new Set(custos.map((c) => c.categoria))).sort()]);
  let custosFiltrados = $derived(
    filtroCategoria === 'todas' ? custos : custos.filter((c) => c.categoria === filtroCategoria)
  );
  let totalCustosFiltrados = $derived(custosFiltrados.reduce((s, c) => s + c.valor, 0));

  let opcoesFluxo = $derived.by(() => {
    let acumulado = 0;
    const saldoAcumulado = fluxo.map((m) => {
      acumulado += m.entradas - m.saidas;
      return Number(acumulado.toFixed(2));
    });

    return {
      grid: { left: 8, right: 8, top: 52, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        confine: true,
        formatter: (params: Array<{ axisValueLabel?: string; marker?: string; seriesName?: string; value?: number }>) => {
          if (!Array.isArray(params) || !params.length) return '';
          const mes = params[0].axisValueLabel ?? '';
          const linhas = params
            .map((p) => {
              const rotuloCurto =
                p.seriesName === 'Saídas operacionais'
                  ? 'Saídas'
                  : p.seriesName === 'Saldo acumulado'
                    ? 'Saldo acum.'
                    : (p.seriesName ?? '');
              const val = `R$ ${Number(p.value ?? 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
              return `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:4px;line-height:1.25;">
                <span style="display:inline-flex;align-items:center;gap:4px;color:#3B453E;">${p.marker ?? ''}${rotuloCurto}</span>
                <strong style="color:#141C17;font-weight:700;">${val}</strong>
              </div>`;
            })
            .join('');
          return `<div style="min-width:156px;">
            <div style="font-weight:700;color:#141C17;margin-bottom:4px;border-bottom:1px solid #DCE1DA;padding-bottom:3px;">${mes} / ${ano}</div>
            ${linhas}
          </div>`;
        }
      },
      legend: { data: ['Entradas', 'Saídas operacionais', 'Saldo acumulado'], top: 0 },
      xAxis: { type: 'category', data: fluxo.map((m) => MESES[m.mes - 1]) },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: (v: number) => `${(v / 1000).toFixed(0)}k`
        }
      },
      series: [
        { name: 'Entradas', type: 'bar', data: fluxo.map((m) => m.entradas), itemStyle: { color: '#155E3B' }, barMaxWidth: 18 },
        { name: 'Saídas operacionais', type: 'bar', data: fluxo.map((m) => m.saidas), itemStyle: { color: '#B42318' }, barMaxWidth: 18 },
        {
          name: 'Saldo acumulado',
          type: 'line',
          data: saldoAcumulado,
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: { width: 2, color: '#3B453E' },
          itemStyle: { color: '#3B453E' }
        }
      ]
    };
  });

  function margemDe(l: ResultadoLote): number {
    return l.receita_vendas + l.valuation_vivo - l.investimento_compra - l.custos_rateados;
  }

  function roiDe(l: ResultadoLote): number | null {
    const investido = l.investimento_compra + l.custos_rateados;
    if (investido <= 0) return null;
    return (margemDe(l) / investido) * 100;
  }

  function diasAteVencer(iso: string): number {
    const d = new Date(`${iso}T00:00:00Z`);
    return Math.round((d.getTime() - HOJE.getTime()) / 86400000);
  }

  function estadoConta(c: Compromisso): 'pago' | 'vencido' | 'proximo' | 'em_dia' {
    if (c.status === 'pago') return 'pago';
    const dias = diasAteVencer(c.vencimento);
    if (dias < 0) return 'vencido';
    if (dias <= 7) return 'proximo';
    return 'em_dia';
  }

  let agendaOrdenada = $derived(
    [...agenda].sort((a, b) => a.vencimento.localeCompare(b.vencimento))
  );
  let totalPendente = $derived(
    agenda.filter((c) => c.status === 'pendente').reduce((s, c) => s + c.valor, 0)
  );
  let totalVencido = $derived(
    agenda.filter((c) => estadoConta(c) === 'vencido').reduce((s, c) => s + c.valor, 0)
  );

  async function salvarCusto(evento: SubmitEvent) {
    evento.preventDefault();
    const valorNumero = Number(novoValor.replace(/\./g, '').replace(',', '.'));
    if (!novoDescricao.trim() || !Number.isFinite(valorNumero) || valorNumero <= 0) {
      mensagemForm = 'Informe uma descrição e um valor maior que zero.';
      return;
    }

    const corpo = JSON.stringify({
      data: novoData,
      descricao: novoDescricao.trim(),
      categoria: novoCategoria,
      valor: valorNumero,
      agendado: novoAgendado
    });

    try {
      const rota = novoAgendado ? '/api/financeiro/agendamentos' : '/api/financeiro/custos';
      await apiFetch(rota, { method: 'POST', body: corpo });
      mensagemForm = 'Lançamento gravado.';
      await carregarAno(ano);
    } catch {
      // Sem API ativa o lançamento entra apenas na visão local de demonstração.
      if (novoAgendado) {
        agenda = [
          ...agenda,
          { id: Date.now(), descricao: novoDescricao.trim(), categoria: novoCategoria, vencimento: novoData, valor: valorNumero, status: 'pendente' }
        ];
      } else {
        custos = [
          { id: Date.now(), data: novoData, descricao: novoDescricao.trim(), categoria: novoCategoria, valor: valorNumero, registrado_por: auth.user.username },
          ...custos
        ];
      }
      mensagemForm = 'Lançamento guardado na visão de demonstração (API indisponível).';
    }

    novoDescricao = '';
    novoValor = '';
    novoAgendado = false;
  }

  async function darBaixa(c: Compromisso) {
    try {
      await apiFetch(`/api/financeiro/agendamentos/${c.id}`, {
        method: 'POST',
        body: JSON.stringify({ status: 'pago' })
      });
      await carregarAno(ano);
    } catch {
      agenda = agenda.map((item) => (item.id === c.id ? { ...item, status: 'pago' as const } : item));
    }
  }
</script>

<div class="financeiro">
  <header class="financeiro__header">
    <div>
      <h1 class="page-title">Financeiro</h1>
      <p class="page-subtitle">
        Fluxo de caixa, resultado por lote e compromissos de {auth.user.nome_fazenda}
        {#if !apiConectada && !carregando}
          <span class="badge badge--neutro">Modo demonstração (Fazenda São Marcos)</span>
        {/if}
      </p>
    </div>

    <div class="financeiro__controles">
      <div class="segmented" role="group" aria-label="Ano do exercício">
        {#each ANOS as opcao}
          <button type="button" class="dado" class:ativo={ano === opcao} onclick={() => trocarAno(opcao)}>{opcao}</button>
        {/each}
      </div>
      <a class="btn btn-outline" href={`/api/v1/export/financeiro.csv?ano=${ano}`} download>Exportar CSV</a>
      {#if auth.podeGerirFazenda}
        <button type="button" class="btn btn-primary" onclick={() => (formAberto = !formAberto)}>
          {formAberto ? 'Fechar lançamento' : 'Lançar custo'}
        </button>
      {/if}
    </div>
  </header>

  <section class="mostradores panel" aria-label="Resultado do ano">
    <div class="mostrador">
      <span class="mostrador__label">Entradas (vendas de gado)</span>
      <strong class="mostrador__value dado dado--ok">{formatBrl(totalEntradas)}</strong>
      <span class="mostrador__meta dado">{ano}</span>
    </div>
    <div class="mostrador">
      <span class="mostrador__label">Saídas operacionais</span>
      <strong class="mostrador__value dado dado--alerta">{formatBrl(totalSaidas)}</strong>
      <span class="mostrador__meta">Custos, sanitário e compras</span>
    </div>
    <div class="mostrador">
      <span class="mostrador__label">Saldo líquido do ano</span>
      <strong
        class="mostrador__value dado"
        class:dado--ok={saldoLiquido >= 0}
        class:dado--alerta={saldoLiquido < 0}
      >{formatBrl(saldoLiquido)}</strong>
      <span class="mostrador__meta">{saldoLiquido >= 0 ? 'Caixa positivo' : 'Caixa negativo'}</span>
    </div>
    <div class="mostrador">
      <span class="mostrador__label">Custo médio por @ produzida</span>
      <strong class="mostrador__value dado">{formatBrl(custoPorArroba)}</strong>
      <span class="mostrador__meta">
        Custeio de <span class="dado">{formatBrl(custoOperacional)}</span> sobre
        <span class="dado">{arrobasProduzidas.toFixed(0)} @</span> produzidas
      </span>
    </div>
  </section>

  {#if formAberto && auth.podeGerirFazenda}
    <form class="form-custo panel" onsubmit={salvarCusto}>
      <h2 class="section-title">Novo lançamento</h2>
      <div class="form-custo__linha">
        <div class="campo">
          <label class="label" for="custo-data">Data</label>
          <input id="custo-data" class="input dado" type="date" bind:value={novoData} />
        </div>
        <div class="campo">
          <label class="label" for="custo-descricao">Descrição</label>
          <input id="custo-descricao" class="input" type="text" placeholder="Ex.: Sal mineral proteinado (40 sacos)" bind:value={novoDescricao} />
        </div>
        <div class="campo">
          <label class="label" for="custo-categoria">Centro de custo</label>
          <select id="custo-categoria" class="input" bind:value={novoCategoria}>
            {#each CATEGORIAS as c}
              <option value={c}>{c}</option>
            {/each}
          </select>
        </div>
        <div class="campo">
          <label class="label" for="custo-valor">Valor (R$)</label>
          <input id="custo-valor" class="input dado" type="text" inputmode="decimal" placeholder="9.480,00" bind:value={novoValor} />
        </div>
      </div>
      <div class="form-custo__rodape">
        <label class="checkbox">
          <input type="checkbox" bind:checked={novoAgendado} />
          Agendar como conta a pagar (não baixa o caixa agora)
        </label>
        <div class="form-custo__acoes">
          {#if mensagemForm}
            <span class="form-custo__msg">{mensagemForm}</span>
          {/if}
          <button type="submit" class="btn btn-primary">Gravar lançamento</button>
        </div>
      </div>
    </form>
  {/if}

  <div class="abas" role="tablist" aria-label="Visões do financeiro">
    <button type="button" role="tab" aria-selected={aba === 'fluxo'} class:ativa={aba === 'fluxo'} onclick={() => (aba = 'fluxo')}>
      Fluxo de caixa e custos
    </button>
    <button type="button" role="tab" aria-selected={aba === 'lotes'} class:ativa={aba === 'lotes'} onclick={() => (aba = 'lotes')}>
      P&amp;L por lote
    </button>
    <button type="button" role="tab" aria-selected={aba === 'contas'} class:ativa={aba === 'contas'} onclick={() => (aba = 'contas')}>
      Contas a pagar
      {#if totalVencido > 0}
        <span class="badge badge--alerta">vencidas</span>
      {/if}
    </button>
  </div>

  {#if aba === 'fluxo'}
    <section class="grafico-sec panel">
      <div class="grafico-sec__topo">
        <h2 class="section-title">Entradas e saídas por mês</h2>
        <p class="grafico-sec__legenda">
          Barras agrupadas de entradas e saídas, com a linha do saldo acumulado do exercício de
          <span class="dado">{ano}</span>
        </p>
      </div>
      <EChart options={opcoesFluxo} height="300px" rotulo={`Fluxo de caixa mensal de ${ano}`} />
    </section>

    <section class="custos">
      <div class="custos__topo">
        <h2 class="section-title">Detalhamento de custos</h2>
        <div class="custos__filtro">
          <label class="label" for="filtro-categoria">Centro de custo</label>
          <select id="filtro-categoria" class="input" bind:value={filtroCategoria}>
            {#each categorias as c}
              <option value={c}>{c === 'todas' ? 'Todos os centros' : c}</option>
            {/each}
          </select>
        </div>
      </div>

      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Data</th>
              <th>Descrição</th>
              <th>Centro de custo</th>
              <th class="col-num">Valor</th>
              <th>Registrado por</th>
            </tr>
          </thead>
          <tbody>
            {#each custosFiltrados as c (c.id)}
              <tr>
                <td><span class="dado">{formatDateBr(c.data)}</span></td>
                <td>{c.descricao}</td>
                <td><span class="badge badge--neutro">{c.categoria}</span></td>
                <td class="col-num"><span class="dado">{formatBrl(c.valor)}</span></td>
                <td><span class="autor dado">{c.registrado_por}</span></td>
              </tr>
            {:else}
              <tr>
                <td colspan="5" class="vazio">Nenhum custo lançado neste centro em {ano}.</td>
              </tr>
            {/each}
          </tbody>
          <tfoot>
            <tr>
              <td colspan="3">Total da visão</td>
              <td class="col-num"><strong class="dado">{formatBrl(totalCustosFiltrados)}</strong></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  {:else if aba === 'lotes'}
    <section class="lotes">
      <div class="lotes__topo">
        <h2 class="section-title">Esse lote deu lucro?</h2>
        <p class="grafico-sec__legenda">
          Resultado de <span class="dado">vw_resultado_lote</span>: compra e custos rateados contra receita realizada
          mais o valuation do estoque vivo a <span class="dado">R$ 338,50/@</span>
        </p>
      </div>

      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Código do lote</th>
              <th class="col-num">Cabeças (ativas / vendidas)</th>
              <th class="col-num">Investimento em compra</th>
              <th class="col-num">Custos rateados</th>
              <th class="col-num">Receita + valuation vivo</th>
              <th class="col-num">Margem</th>
              <th class="col-num">ROI</th>
            </tr>
          </thead>
          <tbody>
            {#each lotes as l (l.lote)}
              {@const margem = margemDe(l)}
              {@const roi = roiDe(l)}
              <tr>
                <td><span class="dado lote-codigo">{l.lote}</span></td>
                <td class="col-num">
                  <span class="dado">{l.cabecas_ativas}</span>
                  <span class="separador">/</span>
                  <span class="dado">{l.cabecas_vendidas}</span>
                </td>
                <td class="col-num"><span class="dado">{formatBrl(l.investimento_compra)}</span></td>
                <td class="col-num"><span class="dado">{formatBrl(l.custos_rateados)}</span></td>
                <td class="col-num">
                  <span class="dado">{formatBrl(l.receita_vendas + l.valuation_vivo)}</span>
                  <small class="dado unidade">
                    {formatBrl(l.receita_vendas)} realizado
                  </small>
                </td>
                <td class="col-num">
                  <span class="dado" class:dado--ok={margem >= 0} class:dado--alerta={margem < 0}>
                    {margem >= 0 ? '+' : ''}{formatBrl(margem)}
                  </span>
                </td>
                <td class="col-num">
                  {#if roi === null}
                    <span class="sem-dado">—</span>
                  {:else}
                    <span class="dado" class:dado--ok={roi >= 0} class:dado--alerta={roi < 0}>
                      {roi >= 0 ? '+' : ''}{roi.toFixed(1).replace('.', ',')}%
                    </span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {:else}
    <section class="contas">
      <div class="contas__topo">
        <h2 class="section-title">Compromissos agendados</h2>
        <div class="contas__totais">
          <span>
            Pendente: <strong class="dado">{formatBrl(totalPendente)}</strong>
          </span>
          {#if totalVencido > 0}
            <span>
              Vencido: <strong class="dado dado--alerta">{formatBrl(totalVencido)}</strong>
            </span>
          {/if}
        </div>
      </div>

      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Compromisso</th>
              <th>Centro de custo</th>
              <th>Vencimento</th>
              <th class="col-num">Valor</th>
              <th>Situação</th>
              {#if auth.podeGerirFazenda}
                <th class="col-acoes">Ação</th>
              {/if}
            </tr>
          </thead>
          <tbody>
            {#each agendaOrdenada as c (c.id)}
              {@const estado = estadoConta(c)}
              {@const dias = diasAteVencer(c.vencimento)}
              <tr class:linha-vencida={estado === 'vencido'}>
                <td>{c.descricao}</td>
                <td><span class="badge badge--neutro">{c.categoria}</span></td>
                <td><span class="dado">{formatDateBr(c.vencimento)}</span></td>
                <td class="col-num">
                  <span class="dado" class:dado--alerta={estado === 'vencido' || estado === 'proximo'}>
                    {formatBrl(c.valor)}
                  </span>
                </td>
                <td>
                  {#if estado === 'pago'}
                    <span class="badge badge--ok">Pago</span>
                  {:else if estado === 'vencido'}
                    <span class="badge badge--alerta">
                      Vencido há <span class="dado">{Math.abs(dias)}d</span>
                    </span>
                  {:else if estado === 'proximo'}
                    <span class="badge badge--alerta">
                      Vence em <span class="dado">{dias}d</span>
                    </span>
                  {:else}
                    <span class="badge badge--neutro">
                      Em <span class="dado">{dias}d</span>
                    </span>
                  {/if}
                </td>
                {#if auth.podeGerirFazenda}
                  <td class="col-acoes">
                    {#if c.status === 'pendente'}
                      <button type="button" class="btn btn-outline btn-mini" onclick={() => darBaixa(c)}>Dar baixa</button>
                    {:else}
                      <span class="sem-dado">—</span>
                    {/if}
                  </td>
                {/if}
              </tr>
            {:else}
              <tr>
                <td colspan={auth.podeGerirFazenda ? 6 : 5} class="vazio">Nenhum compromisso agendado.</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {/if}
</div>

<style>
  .financeiro {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .financeiro__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .financeiro__controles {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
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
    padding: 0 var(--space-4);
    border: none;
    border-right: 1px solid var(--color-border);
    background: transparent;
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
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
  }

  .mostradores {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
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

  .form-custo {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .form-custo__linha {
    display: grid;
    grid-template-columns: 150px 1fr 200px 160px;
    gap: var(--space-4);
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

  .form-custo__rodape {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .checkbox {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
  }

  .form-custo__acoes {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .form-custo__msg {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .abas {
    display: flex;
    gap: var(--space-1);
    border-bottom: 1px solid var(--color-border);
  }

  .abas button {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
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
    max-width: 75ch;
  }

  .custos,
  .lotes,
  .contas {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .custos__topo,
  .contas__topo {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .custos__filtro {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 220px;
  }

  .contas__totais {
    display: flex;
    gap: var(--space-2) var(--space-5);
    flex-wrap: wrap;
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
  }

  .table tfoot td {
    padding: var(--space-3) var(--space-4);
    background: var(--color-surface-raised);
    border-top: 1px solid var(--color-border);
    font-weight: var(--weight-semibold);
  }

  .lote-codigo {
    font-weight: var(--weight-semibold);
  }

  .separador {
    color: var(--color-ink-tertiary);
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

  .linha-vencida {
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
    .mostradores {
      grid-template-columns: repeat(2, 1fr);
    }
    .mostrador:nth-child(2) {
      border-right: none;
    }
    .form-custo__linha {
      grid-template-columns: 1fr 1fr;
    }
  }

  @media (max-width: 768px) {
    .grafico-sec {
      padding: var(--space-4);
    }
    .mostradores {
      grid-template-columns: 1fr;
    }
    .mostrador {
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }
    .form-custo {
      padding: var(--space-4);
    }
    .form-custo__linha {
      grid-template-columns: 1fr;
    }
    .custos__filtro {
      width: 100%;
      min-width: 0;
    }
    .abas {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      overflow-x: hidden;
    }
    .abas button {
      flex-direction: column;
      justify-content: center;
      text-align: center;
      white-space: normal;
      line-height: 1.2;
      gap: 4px;
      padding: var(--space-2) var(--space-1);
      font-size: var(--text-xs);
    }
  }
</style>
