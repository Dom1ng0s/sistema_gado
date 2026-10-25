<script lang="ts">
  /**
   * Trilha 2 / MT-2.3 e MT-2.4 — Prontuário zootécnico individual.
   * Cabeçalho com genealogia, faixa de engorda, curva de crescimento (ECharts)
   * e abas de histórico auditável com a coluna "Registrado por".
   */
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { router } from '../lib/router.svelte';
  import { formatArroba, formatBrl, formatDateBr, formatGmd, formatKg, KG_POR_ARROBA } from '../lib/format';
  import EChart from '../components/charts/EChart.svelte';

  interface AnimalProp {
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
    nascido_na_fazenda: boolean;
    carencia_dias: number | null;
    carencia_medicamento: string | null;
    carencia_liberacao: string | null;
    pai: string | null;
    mae: string | null;
    data_entrada: string;
    custo_acumulado: number;
  }

  interface Pesagem {
    data: string;
    peso_kg: number;
    ganho_kg: number | null;
    gmd_periodo: number | null;
    registrado_por: string;
  }

  interface Medicacao {
    data: string;
    produto: string;
    dose: string;
    dias_carencia: number;
    liberacao: string;
    registrado_por: string;
  }

  interface Cria {
    brinco: string;
    sexo: 'M' | 'F';
    nascimento: string;
    peso_atual: number;
    gmd_atual: number | null;
    registrado_por: string;
  }

  interface Props {
    animal: AnimalProp;
    onVoltar?: () => void;
  }

  let { animal, onVoltar }: Props = $props();

  type Aba = 'pesagens' | 'sanitario' | 'progenie';
  let aba = $state<Aba>('pesagens');

  let apiConectada = $state(false);

  /** Histórico de demonstração da Fazenda São Marcos, derivado do peso real do animal aberto. */
  function pesagensDemo(a: AnimalProp): Pesagem[] {
    const etapas = 6;
    const ganhoTotal = a.peso_atual - a.peso_inicial;
    const entrada = new Date(`${a.data_entrada}T00:00:00Z`);
    const intervalo = Math.max(1, Math.round(a.dias_fazenda / (etapas - 1)));
    const autores = ['davi.dono', 'joao.vaqueiro', 'joao.vaqueiro', 'davi.dono', 'joao.vaqueiro', 'davi.dono'];

    const linhas: Pesagem[] = [];
    for (let i = 0; i < etapas; i += 1) {
      const d = new Date(entrada);
      d.setUTCDate(d.getUTCDate() + intervalo * i);
      // Curva levemente desacelerada no fim do período, como no cocho real.
      const fracao = i === 0 ? 0 : Math.pow(i / (etapas - 1), 0.92);
      const peso = Number((a.peso_inicial + ganhoTotal * fracao).toFixed(1));
      const anterior = linhas[i - 1];
      const ganho = anterior ? Number((peso - anterior.peso_kg).toFixed(1)) : null;
      linhas.push({
        data: d.toISOString().slice(0, 10),
        peso_kg: peso,
        ganho_kg: ganho,
        gmd_periodo: ganho === null ? null : Number((ganho / intervalo).toFixed(3)),
        registrado_por: autores[i % autores.length]
      });
    }
    return linhas;
  }

  function medicacoesDemo(a: AnimalProp): Medicacao[] {
    const base: Medicacao[] = [
      { data: '2026-06-02', produto: 'Aftosa (2ª etapa)', dose: '5 mL', dias_carencia: 0, liberacao: '—', registrado_por: 'joao.vaqueiro' },
      { data: '2026-07-18', produto: 'Cipermetrina (mosca-do-chifre)', dose: '20 mL', dias_carencia: 5, liberacao: '23/07/2026', registrado_por: 'joao.vaqueiro' },
      { data: '2026-09-11', produto: 'Vermífugo Albendazol 10%', dose: '25 mL', dias_carencia: 14, liberacao: '25/09/2026', registrado_por: 'davi.dono' }
    ];
    if (a.carencia_dias && a.carencia_medicamento && a.carencia_liberacao) {
      base.push({
        data: '2026-10-10',
        produto: a.carencia_medicamento,
        dose: '15 mL',
        dias_carencia: 35,
        liberacao: a.carencia_liberacao,
        registrado_por: 'davi.dono'
      });
    }
    return base;
  }

  function progenieDemo(a: AnimalProp): Cria[] {
    if (a.sexo === 'F') {
      return [
        { brinco: '0520', sexo: 'F', nascimento: '2026-08-24', peso_atual: 351.0, gmd_atual: null, registrado_por: 'joao.vaqueiro' },
        { brinco: '0211', sexo: 'F', nascimento: '2026-03-26', peso_atual: 441.0, gmd_atual: 0.689, registrado_por: 'davi.dono' }
      ];
    }
    return [
      { brinco: '0203', sexo: 'F', nascimento: '2026-01-21', peso_atual: 382.0, gmd_atual: 0.34, registrado_por: 'davi.dono' },
      { brinco: '0712', sexo: 'F', nascimento: '2026-01-20', peso_atual: 405.0, gmd_atual: 0.448, registrado_por: 'joao.vaqueiro' },
      { brinco: '0409', sexo: 'M', nascimento: '2025-11-02', peso_atual: 474.0, gmd_atual: 0.758, registrado_por: 'davi.dono' }
    ];
  }

  // O histórico vem da API quando ela responde; sem isso, cai no demo derivado do animal aberto.
  let pesagensApi = $state<Pesagem[] | null>(null);
  let medicacoesApi = $state<Medicacao[] | null>(null);
  let progenieApi = $state<Cria[] | null>(null);

  let pesagens = $derived(pesagensApi ?? pesagensDemo(animal));
  let medicacoes = $derived(medicacoesApi ?? medicacoesDemo(animal));
  let progenie = $derived(progenieApi ?? progenieDemo(animal));

  onMount(async () => {
    try {
      const detalhe = await apiFetch<{
        pesagens?: Pesagem[];
        medicacoes?: Medicacao[];
        progenie?: Cria[];
      }>(`/api/animais/${animal.id}`);
      if (detalhe.pesagens?.length) pesagensApi = detalhe.pesagens;
      if (detalhe.medicacoes) medicacoesApi = detalhe.medicacoes;
      if (detalhe.progenie) progenieApi = detalhe.progenie;
      apiConectada = true;
    } catch {
      // Prontuário segue navegável com o histórico de demonstração.
      apiConectada = false;
    }
  });

  let gmdMeta = $derived(auth.user.gmd_meta);
  let ganhoKg = $derived(animal.peso_atual - animal.peso_inicial);
  let ganhoArrobas = $derived(ganhoKg / KG_POR_ARROBA);
  let naMeta = $derived(animal.gmd_atual !== null && animal.gmd_atual >= gmdMeta);
  let desvioMetaPct = $derived(
    animal.gmd_atual === null ? null : Math.round(((animal.gmd_atual - gmdMeta) / gmdMeta) * 100)
  );
  let valuationHoje = $derived((animal.peso_atual / KG_POR_ARROBA) * 338.5);
  let margemHoje = $derived(valuationHoje - animal.custo_acumulado);
  let custoPorArrobaProduzida = $derived(
    ganhoArrobas > 0 ? animal.custo_acumulado / ganhoArrobas : null
  );
  let gmdMedioProgenie = $derived.by(() => {
    const comGmd = progenie.filter((c) => c.gmd_atual !== null);
    if (!comGmd.length) return null;
    return comGmd.reduce((s, c) => s + (c.gmd_atual ?? 0), 0) / comGmd.length;
  });

  // Curva de crescimento: peso real, linha tracejada da meta e marcadores de medicação.
  let opcoesCurva = $derived.by(() => {
    const datas = pesagens.map((p) => formatDateBr(p.data));
    const pesos = pesagens.map((p) => p.peso_kg);

    const inicio = pesagens[0];
    const diasPorEtapa =
      pesagens.length > 1 ? animal.dias_fazenda / (pesagens.length - 1) : 0;
    const curvaMeta = pesagens.map((_, i) =>
      Number(((inicio?.peso_kg ?? animal.peso_inicial) + gmdMeta * diasPorEtapa * i).toFixed(1))
    );

    // Cada medicação é ancorada na pesagem mais próxima no tempo.
    const marcadores = medicacoes.map((m) => {
      const alvo = new Date(`${m.data}T00:00:00Z`).getTime();
      let melhor = 0;
      let menorDistancia = Number.POSITIVE_INFINITY;
      pesagens.forEach((p, i) => {
        const dist = Math.abs(new Date(`${p.data}T00:00:00Z`).getTime() - alvo);
        if (dist < menorDistancia) {
          menorDistancia = dist;
          melhor = i;
        }
      });
      return {
        name: m.produto,
        coord: [datas[melhor], pesos[melhor]],
        value: m.dias_carencia > 0 ? `${m.dias_carencia}d` : 'vac.'
      };
    });

    return {
      grid: { left: 12, right: 16, top: 36, bottom: 16, containLabel: true },
      tooltip: { trigger: 'axis' },
      legend: { data: ['Peso medido', 'Meta de GMD'], left: 0, top: 0 },
      xAxis: { type: 'category', data: datas, boundaryGap: false },
      yAxis: { type: 'value', name: 'kg', nameTextStyle: { color: '#525E56', fontSize: 11 }, scale: true },
      series: [
        {
          name: 'Peso medido',
          type: 'line',
          data: pesos,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2, color: '#155E3B' },
          itemStyle: { color: '#155E3B' },
          markPoint: {
            symbol: 'pin',
            symbolSize: 34,
            itemStyle: { color: '#B42318' },
            label: { color: '#fff', fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" },
            data: marcadores
          }
        },
        {
          name: 'Meta de GMD',
          type: 'line',
          data: curvaMeta,
          symbol: 'none',
          lineStyle: { width: 1.5, type: 'dashed', color: '#3B453E' },
          itemStyle: { color: '#3B453E' }
        }
      ]
    };
  });
</script>

<div class="ficha">
  <div class="ficha__voltar">
    <button type="button" class="btn btn-ghost" onclick={() => onVoltar?.()}>← Voltar ao rebanho</button>
    {#if !apiConectada}
      <span class="badge badge--neutro">Modo demonstração (Fazenda São Marcos)</span>
    {/if}
  </div>

  <header class="prontuario-topo panel">
    <div class="prontuario-topo__id">
      <span class="prontuario-topo__rotulo">Brinco</span>
      <strong class="prontuario-topo__brinco dado">#{animal.brinco}</strong>
      <div class="tags">
        <span class="badge badge--neutro">{animal.sexo === 'M' ? 'Macho' : 'Fêmea'}</span>
        <span class="badge badge--neutro">{animal.raca}</span>
        <span class="badge badge--neutro">{animal.lote}</span>
        <span class="badge badge--neutro">{animal.pasto}</span>
        {#if animal.nascido_na_fazenda}
          <span class="badge badge--ok">Nascido na fazenda</span>
        {/if}
      </div>
    </div>

    <div class="prontuario-topo__lado">
      <dl class="genealogia">
        <div>
          <dt>Pai</dt>
          <dd>
            {#if animal.pai}
              <button type="button" class="link-dado dado" onclick={() => router.navegar('rebanho', animal.pai ?? '')}>
                #{animal.pai}
              </button>
            {:else}
              <span class="sem-dado">Não informado</span>
            {/if}
          </dd>
        </div>
        <div>
          <dt>Mãe</dt>
          <dd>
            {#if animal.mae}
              <button type="button" class="link-dado dado" onclick={() => router.navegar('rebanho', animal.mae ?? '')}>
                #{animal.mae}
              </button>
            {:else}
              <span class="sem-dado">Não informado</span>
            {/if}
          </dd>
        </div>
        <div>
          <dt>Entrada</dt>
          <dd><span class="dado">{formatDateBr(animal.data_entrada)}</span></dd>
        </div>
        <div>
          <dt>Tempo de cocho</dt>
          <dd><span class="dado">{animal.dias_fazenda} d</span></dd>
        </div>
      </dl>

      {#if auth.podeEscreverNoCampo || auth.podeGerirFazenda}
        <div class="prontuario-topo__acoes">
          {#if auth.podeEscreverNoCampo}
            <button type="button" class="btn btn-primary" onclick={() => router.navegar('pesagem', animal.brinco)}>Pesar</button>
            <button type="button" class="btn btn-outline" onclick={() => router.navegar('medicar', animal.brinco)}>Medicar</button>
          {/if}
          {#if auth.podeGerirFazenda}
            <button type="button" class="btn btn-outline" onclick={() => router.navegar('venda', animal.brinco)}>Vender</button>
          {/if}
        </div>
      {/if}
    </div>
  </header>

  {#if animal.carencia_dias}
    <div class="bloqueio-carencia" role="status">
      <strong>Carência sanitária ativa — abate bloqueado</strong>
      <p>
        {animal.carencia_medicamento} aplicada neste animal. Liberação em
        <span class="dado">{animal.carencia_liberacao}</span>
        (faltam <span class="dado">{animal.carencia_dias}d</span>).
      </p>
    </div>
  {/if}

  <section class="engorda panel" aria-label="Indicadores de engorda">
    <div class="engorda__cell">
      <span class="engorda__label">Peso inicial → atual</span>
      <strong class="engorda__value dado">{formatKg(animal.peso_atual)}</strong>
      <span class="engorda__meta dado">
        {formatKg(animal.peso_inicial)} → {formatArroba(animal.peso_atual)}
      </span>
    </div>

    <div class="engorda__cell">
      <span class="engorda__label">Ganho acumulado</span>
      <strong class="engorda__value dado dado--ok">+{formatKg(ganhoKg)}</strong>
      <span class="engorda__meta dado">+{ganhoArrobas.toFixed(1).replace('.', ',')} @ no período</span>
    </div>

    <div class="engorda__cell">
      <span class="engorda__label">GMD acumulado vs. meta</span>
      {#if animal.gmd_atual === null}
        <strong class="engorda__value sem-dado">— (1ª pesagem)</strong>
        <span class="engorda__meta">Meta: <span class="dado">{formatGmd(gmdMeta)}</span></span>
      {:else}
        <strong class="engorda__value dado" class:dado--ok={naMeta} class:dado--alerta={!naMeta}>
          {formatGmd(animal.gmd_atual)}
        </strong>
        <span class="engorda__meta">
          Meta: <span class="dado">{formatGmd(gmdMeta)}</span>
          <span class="dado" class:dado--ok={naMeta} class:dado--alerta={!naMeta}>
            ({desvioMetaPct !== null && desvioMetaPct >= 0 ? '+' : ''}{desvioMetaPct}%)
          </span>
        </span>
      {/if}
    </div>

    {#if auth.podeVerFinanceiro}
      <div class="engorda__cell">
        <span class="engorda__label">Custo acumulado</span>
        <strong class="engorda__value dado">{formatBrl(animal.custo_acumulado)}</strong>
        <span class="engorda__meta">
          {#if custoPorArrobaProduzida}
            <span class="dado">{formatBrl(custoPorArrobaProduzida)}</span> por @ produzida
          {:else}
            Compra, sanitário e diárias
          {/if}
        </span>
      </div>

      <div class="engorda__cell">
        <span class="engorda__label">Valuation hoje</span>
        <strong class="engorda__value dado">{formatBrl(valuationHoje)}</strong>
        <span class="engorda__meta">
          Base <span class="dado">R$ 338,50/@</span> ·
          <span class="dado" class:dado--ok={margemHoje >= 0} class:dado--alerta={margemHoje < 0}>
            {margemHoje >= 0 ? '+' : ''}{formatBrl(margemHoje)}
          </span>
        </span>
      </div>
    {/if}
  </section>

  <section class="grafico-sec panel">
    <div class="grafico-sec__topo">
      <h2 class="section-title">Curva de crescimento</h2>
      <p class="grafico-sec__legenda">
        Peso medido em <span class="dado">kg</span>, linha tracejada da meta de
        <span class="dado">{formatGmd(gmdMeta)}</span> e pinos de medicação aplicada
      </p>
    </div>
    <EChart options={opcoesCurva} height="300px" rotulo={`Curva de peso do animal ${animal.brinco}`} />
  </section>

  <section class="historico">
    <div class="abas" role="tablist" aria-label="Histórico auditável do animal">
      <button type="button" role="tab" aria-selected={aba === 'pesagens'} class:ativa={aba === 'pesagens'} onclick={() => (aba = 'pesagens')}>
        Pesagens <span class="dado">({pesagens.length})</span>
      </button>
      <button type="button" role="tab" aria-selected={aba === 'sanitario'} class:ativa={aba === 'sanitario'} onclick={() => (aba = 'sanitario')}>
        Medicações e sanitário <span class="dado">({medicacoes.length})</span>
      </button>
      <button type="button" role="tab" aria-selected={aba === 'progenie'} class:ativa={aba === 'progenie'} onclick={() => (aba = 'progenie')}>
        Progênie <span class="dado">({progenie.length})</span>
      </button>
    </div>

    {#if aba === 'pesagens'}
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Data</th>
              <th class="col-num">Peso (kg)</th>
              <th class="col-num">Arroba (@)</th>
              <th class="col-num">Ganho no período</th>
              <th class="col-num">GMD do intervalo</th>
              <th>Registrado por</th>
            </tr>
          </thead>
          <tbody>
            {#each pesagens as p (p.data)}
              <tr>
                <td><span class="dado">{formatDateBr(p.data)}</span></td>
                <td class="col-num"><span class="dado">{formatKg(p.peso_kg)}</span></td>
                <td class="col-num"><span class="dado">{formatArroba(p.peso_kg)}</span></td>
                <td class="col-num">
                  {#if p.ganho_kg === null}
                    <span class="sem-dado">— (entrada)</span>
                  {:else}
                    <span class="dado" class:dado--ok={p.ganho_kg > 0} class:dado--alerta={p.ganho_kg <= 0}>
                      {p.ganho_kg > 0 ? '+' : ''}{formatKg(p.ganho_kg)}
                    </span>
                  {/if}
                </td>
                <td class="col-num">
                  {#if p.gmd_periodo === null}
                    <span class="sem-dado">—</span>
                  {:else}
                    <span class="dado" class:dado--ok={p.gmd_periodo >= gmdMeta} class:dado--alerta={p.gmd_periodo < gmdMeta}>
                      {formatGmd(p.gmd_periodo)}
                    </span>
                  {/if}
                </td>
                <td><span class="autor dado">{p.registrado_por}</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else if aba === 'sanitario'}
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Produto aplicado</th>
              <th>Dose</th>
              <th>Data da aplicação</th>
              <th class="col-num">Dias de carência</th>
              <th>Liberação para abate</th>
              <th>Registrado por</th>
            </tr>
          </thead>
          <tbody>
            {#each medicacoes as m (m.data + m.produto)}
              <tr>
                <td>{m.produto}</td>
                <td><span class="dado">{m.dose}</span></td>
                <td><span class="dado">{formatDateBr(m.data)}</span></td>
                <td class="col-num"><span class="dado">{m.dias_carencia} d</span></td>
                <td>
                  {#if m.produto === animal.carencia_medicamento && animal.carencia_dias}
                    <span class="badge badge--alerta">
                      <span class="dado">{m.liberacao}</span> · faltam <span class="dado">{animal.carencia_dias}d</span>
                    </span>
                  {:else if m.dias_carencia > 0}
                    <span class="badge badge--ok"><span class="dado">{m.liberacao}</span> · cumprida</span>
                  {:else}
                    <span class="sem-dado">Sem carência</span>
                  {/if}
                </td>
                <td><span class="autor dado">{m.registrado_por}</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      {#if progenie.length}
        <p class="progenie-resumo">
          GMD médio da progênie:
          <strong
            class="dado"
            class:dado--ok={(gmdMedioProgenie ?? 0) >= gmdMeta}
            class:dado--alerta={(gmdMedioProgenie ?? 0) < gmdMeta}
          >{formatGmd(gmdMedioProgenie)}</strong>
          em <span class="dado">{progenie.length}</span> crias nascidas na fazenda
        </p>
      {/if}
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Brinco da cria</th>
              <th>Sexo</th>
              <th>Nascimento</th>
              <th class="col-num">Peso atual</th>
              <th class="col-num">GMD (kg/d)</th>
              <th>Registrado por</th>
            </tr>
          </thead>
          <tbody>
            {#each progenie as c (c.brinco)}
              <tr>
                <td>
                  <button type="button" class="link-dado dado" onclick={() => router.navegar('rebanho', c.brinco)}>
                    #{c.brinco}
                  </button>
                </td>
                <td><span class="dado">{c.sexo}</span></td>
                <td><span class="dado">{formatDateBr(c.nascimento)}</span></td>
                <td class="col-num"><span class="dado">{formatKg(c.peso_atual)}</span></td>
                <td class="col-num">
                  {#if c.gmd_atual === null}
                    <span class="sem-dado">— (1ª pesagem)</span>
                  {:else}
                    <span class="dado" class:dado--ok={c.gmd_atual >= gmdMeta} class:dado--alerta={c.gmd_atual < gmdMeta}>
                      {formatGmd(c.gmd_atual)}
                    </span>
                  {/if}
                </td>
                <td><span class="autor dado">{c.registrado_por}</span></td>
              </tr>
            {:else}
              <tr>
                <td colspan="6" class="vazio">Nenhuma cria registrada para este animal.</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
</div>

<style>
  .ficha {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .ficha__voltar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .prontuario-topo {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-6);
    flex-wrap: wrap;
    padding: var(--space-5);
  }

  .prontuario-topo__rotulo {
    display: block;
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .prontuario-topo__brinco {
    display: block;
    font-size: var(--text-3xl);
    line-height: var(--leading-tight);
    letter-spacing: var(--tracking-display);
  }

  .tags {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-top: var(--space-3);
  }

  .prontuario-topo__lado {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: var(--space-4);
  }

  .genealogia {
    display: flex;
    gap: var(--space-6);
    flex-wrap: wrap;
  }
  .genealogia dt {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }
  .genealogia dd {
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
  }

  .prontuario-topo__acoes {
    display: flex;
    gap: var(--space-2);
  }

  .bloqueio-carencia {
    padding: var(--space-4) var(--space-5);
    background: var(--color-danger-bg);
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-md);
    color: var(--color-danger-dark);
  }
  .bloqueio-carencia strong {
    display: block;
    font-size: var(--text-base);
    color: var(--color-danger-dark);
  }
  .bloqueio-carencia p {
    margin-top: var(--space-1);
    font-size: var(--text-sm);
  }

  .engorda {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  }

  .engorda__cell {
    padding: var(--space-4) var(--space-5);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .engorda__cell:last-child {
    border-right: none;
  }

  .engorda__label {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .engorda__value {
    font-size: var(--text-2xl);
    line-height: var(--leading-tight);
    white-space: nowrap;
  }

  .engorda__meta {
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
  }

  .historico {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
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

  .progenie-resumo {
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
  }

  .autor {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
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

  .sem-dado {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .vazio {
    padding: var(--space-6);
    text-align: center;
    color: var(--color-ink-tertiary);
  }

  @media (max-width: 768px) {
    .prontuario-topo {
      padding: var(--space-4);
    }
    .prontuario-topo__lado {
      align-items: flex-start;
      width: 100%;
    }
    .prontuario-topo__acoes {
      flex-wrap: wrap;
      width: 100%;
    }
    .engorda__cell {
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
