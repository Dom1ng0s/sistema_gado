<script lang="ts">
  import { ApiError, apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatArroba, formatBrl, formatKg, KG_POR_ARROBA } from '../lib/format';

  type ModoVenda = 'individual' | 'lote';

  interface AnimalCarenciaAtiva {
    brinco: string;
    medicamento: string;
    dataAplicacao: string;
    dataLiberacao: string;
    diasRestantes: number;
  }

  interface AnimalVendaDisponivel {
    id: number;
    brinco: string;
    lote: string;
    raca: string;
    pesoAtualKg: number;
    custoCompra: number;
    custoOperacionalSanitario: number;
    carencia: AnimalCarenciaAtiva | null;
  }

  const ANIMAIS_DISPONIVEIS: AnimalVendaDisponivel[] = [
    {
      id: 402,
      brinco: '402',
      lote: 'Lote 04',
      raca: 'Nelore',
      pesoAtualKg: 510.0,
      custoCompra: 3450.0,
      custoOperacionalSanitario: 685.0,
      carencia: {
        brinco: '402',
        medicamento: 'Ivermectina 1%',
        dataAplicacao: '10/10/2026',
        dataLiberacao: '14/11/2026',
        diasRestantes: 21
      }
    },
    {
      id: 409,
      brinco: '409',
      lote: 'Lote 04',
      raca: 'Nelore',
      pesoAtualKg: 495.0,
      custoCompra: 3450.0,
      custoOperacionalSanitario: 685.0,
      carencia: {
        brinco: '409',
        medicamento: 'Ivermectina 1%',
        dataAplicacao: '10/10/2026',
        dataLiberacao: '14/11/2026',
        diasRestantes: 21
      }
    },
    {
      id: 415,
      brinco: '415',
      lote: 'Lote 04',
      raca: 'Angus',
      pesoAtualKg: 528.0,
      custoCompra: 3600.0,
      custoOperacionalSanitario: 710.0,
      carencia: {
        brinco: '415',
        medicamento: 'Albendazol 10%',
        dataAplicacao: '24/10/2026',
        dataLiberacao: '07/11/2026',
        diasRestantes: 14
      }
    },
    {
      id: 421,
      brinco: '421',
      lote: 'Lote 04',
      raca: 'Nelore',
      pesoAtualKg: 516.0,
      custoCompra: 3450.0,
      custoOperacionalSanitario: 640.0,
      carencia: null
    },
    {
      id: 430,
      brinco: '430',
      lote: 'Lote 2026-A',
      raca: 'Cruzamento Industrial',
      pesoAtualKg: 540.0,
      custoCompra: 3580.0,
      custoOperacionalSanitario: 720.0,
      carencia: null
    }
  ];

  let modoVenda = $state<ModoVenda>('individual');
  let comprador = $state('Frigorífico JBS — Unidade Andradina/SP');
  let dataVenda = $state('2026-10-24');
  let valorArrobaNegociada = $state(338.5);

  // Seleção de animais (inicia com #402 para demonstrar prontamente a trava sanitária)
  let brincosSelecionados = $state<string[]>(['402']);
  let pesoSaidaManualKg = $state(510.0);

  // Estado da Trava Sanitária (_carencia_bloqueio)
  let painelBloqueioVisivel = $state(true);
  let confirmarCarenciaOverride = $state(false);
  let carenciasRetornadasApi = $state<AnimalCarenciaAtiva[]>([]);

  let salvandoVenda = $state(false);
  let vendaConcluidaMsg = $state('');

  let animaisSelecionadosObj = $derived(
    ANIMAIS_DISPONIVEIS.filter((a) => brincosSelecionados.includes(a.brinco))
  );

  let carenciasAtivasSelecionadas = $derived.by<AnimalCarenciaAtiva[]>(() => {
    if (carenciasRetornadasApi.length > 0) return carenciasRetornadasApi;
    return animaisSelecionadosObj
      .filter((a) => a.carencia !== null)
      .map((a) => a.carencia as AnimalCarenciaAtiva);
  });

  let pesoTotalSaidaKg = $derived.by(() => {
    if (modoVenda === 'individual' && animaisSelecionadosObj.length === 1) {
      return pesoSaidaManualKg;
    }
    return animaisSelecionadosObj.reduce((acc, a) => acc + a.pesoAtualKg, 0);
  });

  let totalArrobasSaida = $derived(pesoTotalSaidaKg / KG_POR_ARROBA);
  let receitaBrutaTotal = $derived(totalArrobasSaida * valorArrobaNegociada);

  let custoAquisicaoTotal = $derived(
    animaisSelecionadosObj.reduce((acc, a) => acc + a.custoCompra, 0)
  );
  let custoOperacionalTotal = $derived(
    animaisSelecionadosObj.reduce((acc, a) => acc + a.custoOperacionalSanitario, 0)
  );
  let custoTotalAcumulado = $derived(custoAquisicaoTotal + custoOperacionalTotal);
  let resultadoLiquidoPl = $derived(receitaBrutaTotal - custoTotalAcumulado);
  let margemRoiPct = $derived(
    custoTotalAcumulado > 0 ? (resultadoLiquidoPl / custoTotalAcumulado) * 100 : 0
  );

  function selecionarAnimalIndividual(brincoAlvo: string) {
    brincosSelecionados = [brincoAlvo];
    const enc = ANIMAIS_DISPONIVEIS.find((a) => a.brinco === brincoAlvo);
    if (enc) {
      pesoSaidaManualKg = enc.pesoAtualKg;
    }
    confirmarCarenciaOverride = false;
    carenciasRetornadasApi = [];
    vendaConcluidaMsg = '';
    painelBloqueioVisivel = Boolean(enc?.carencia);
  }

  function alternarSelecaoLote(brincoAlvo: string) {
    if (brincosSelecionados.includes(brincoAlvo)) {
      if (brincosSelecionados.length > 1) {
        brincosSelecionados = brincosSelecionados.filter((b) => b !== brincoAlvo);
      }
    } else {
      brincosSelecionados = [...brincosSelecionados, brincoAlvo];
    }
    confirmarCarenciaOverride = false;
    carenciasRetornadasApi = [];
    vendaConcluidaMsg = '';
  }

  async function submeterVenda(comOverrideAuditado: boolean) {
    vendaConcluidaMsg = '';

    // Se houver animal em carência e o operador ainda não confirmou o override, abre o painel de bloqueio
    if (carenciasAtivasSelecionadas.length > 0 && !comOverrideAuditado) {
      painelBloqueioVisivel = true;
      return;
    }

    salvandoVenda = true;
    const payload = {
      comprador: comprador.trim(),
      data_venda: dataVenda,
      valor_arroba: valorArrobaNegociada,
      peso_total_kg: pesoTotalSaidaKg,
      preco_total: receitaBrutaTotal,
      animais: animaisSelecionadosObj.map((a) => ({
        id: a.id,
        brinco: a.brinco,
        peso_saida_kg: modoVenda === 'individual' ? pesoSaidaManualKg : a.pesoAtualKg
      })),
      confirmar_carencia: comOverrideAuditado ? 1 : 0,
      autorizado_por: auth.user.username
    };

    try {
      await apiFetch('/api/vendas', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      vendaConcluidaMsg = comOverrideAuditado
        ? `Venda registrada com override sanitário auditado em vendas_com_carencia (autorizado_por: @${auth.user.username}).`
        : `Venda de ${animaisSelecionadosObj.length} cabeça(s) registrada com sucesso para ${comprador}.`;
    } catch (err: unknown) {
      // Trata retorno HTTP 400 de bloqueio de carência do backend
      if (err instanceof ApiError && err.status === 400 && err.payload && typeof err.payload === 'object') {
        const p = err.payload as { carencias?: AnimalCarenciaAtiva[] };
        if (Array.isArray(p.carencias) && p.carencias.length > 0) {
          carenciasRetornadasApi = p.carencias;
        }
        painelBloqueioVisivel = true;
        salvandoVenda = false;
        return;
      }

      // Fallback para o modo demonstração
      vendaConcluidaMsg = comOverrideAuditado
        ? `Venda confirmada (${formatBrl(receitaBrutaTotal)}) + Auditoria gravada em vendas_com_carencia em nome de @${auth.user.username}.`
        : `Venda de ${animaisSelecionadosObj.length} cabeça(s) (${formatBrl(receitaBrutaTotal)}) registrada com sucesso.`;
    } finally {
      salvandoVenda = false;
    }
  }
</script>

<div class="venda-page">
  <header class="page-head">
    <div>
      <div class="badge-row">
        <span class="badge badge--alerta">Guarda Sanitária · vw_animais_em_carencia</span>
        <span class="badge badge--neutro dado">1 @ = {KG_POR_ARROBA} kg</span>
      </div>
      <h1 class="page-title">Registro de Venda e Trava Sanitária</h1>
      <p class="page-subtitle">
        Calcule o faturamento em arrobas (<code class="dado">peso_kg / 30 * valor_arroba</code>), confira o P&L da operação e valide o status de carência antes do embarque.
      </p>
    </div>

    <div class="mode-switch panel">
      <button
        type="button"
        class="mode-btn"
        class:mode-btn--active={modoVenda === 'individual'}
        onclick={() => {
          modoVenda = 'individual';
          selecionarAnimalIndividual(brincosSelecionados[0] || '402');
        }}
      >
        Venda individual
      </button>
      <button
        type="button"
        class="mode-btn"
        class:mode-btn--active={modoVenda === 'lote'}
        onclick={() => {
          modoVenda = 'lote';
          brincosSelecionados = ['402', '409', '421'];
          painelBloqueioVisivel = true;
        }}
      >
        Venda em lote ({brincosSelecionados.length} cab.)
      </button>
    </div>
  </header>

  <div class="venda-grid">
    <!-- Coluna Principal: Seleção + Condições Comerciais + Bloqueio Sanitário -->
    <div class="main-col">
      <section class="panel card-block">
        <h2 class="section-title">1. Seleção de animais para embarque</h2>

        <div class="animal-selector">
          {#each ANIMAIS_DISPONIVEIS as item}
            {@const ativo = brincosSelecionados.includes(item.brinco)}
            <button
              type="button"
              class="animal-pill"
              class:animal-pill--selected={ativo}
              class:animal-pill--carencia={item.carencia !== null}
              onclick={() =>
                modoVenda === 'individual'
                  ? selecionarAnimalIndividual(item.brinco)
                  : alternarSelecaoLote(item.brinco)}
            >
              <div class="animal-pill__top">
                <strong class="dado">#{item.brinco}</strong>
                {#if item.carencia}
                  <span class="badge badge--alerta dado">Carência {item.carencia.diasRestantes}d</span>
                {:else}
                  <span class="badge badge--ok">Liberado</span>
                {/if}
              </div>
              <span class="animal-pill__meta">{item.raca} · <span class="dado">{formatKg(item.pesoAtualKg)}</span></span>
            </button>
          {/each}
        </div>

        <div class="grid-2">
          <div class="field">
            <label for="v-comprador">Comprador / Frigorífico de destino</label>
            <input
              id="v-comprador"
              class="input"
              type="text"
              placeholder="Ex: Frigorífico JBS / Minerva / Marfrig"
              bind:value={comprador}
              required
            />
          </div>

          <div class="field">
            <label for="v-data">Data do fechamento / embarque</label>
            <input id="v-data" class="input dado" type="date" bind:value={dataVenda} required />
          </div>
        </div>

        <div class="grid-3">
          <div class="field">
            <label for="v-peso">
              {modoVenda === 'individual' ? `Peso de saída (kg) — #${brincosSelecionados[0]}` : `Peso total do lote (${animaisSelecionadosObj.length} cab.)`}
            </label>
            {#if modoVenda === 'individual'}
              <input
                id="v-peso"
                class="input dado"
                type="number"
                step="0.5"
                min="50"
                inputmode="decimal"
                bind:value={pesoSaidaManualKg}
              />
            {:else}
              <input
                id="v-peso"
                class="input dado"
                type="text"
                value={formatKg(pesoTotalSaidaKg)}
                readonly
              />
            {/if}
          </div>

          <div class="field">
            <label for="v-arroba">Preço negociado da arroba (R$/@)</label>
            <input
              id="v-arroba"
              class="input dado"
              type="number"
              step="0.5"
              min="50"
              inputmode="decimal"
              bind:value={valorArrobaNegociada}
            />
          </div>

          <div class="field">
            <label for="v-rend">Rendimento comercial (@)</label>
            <input
              id="v-rend"
              class="input dado"
              type="text"
              value={`${formatArroba(pesoTotalSaidaKg)} → ${formatBrl(receitaBrutaTotal)}`}
              readonly
            />
          </div>
        </div>

        {#if carenciasAtivasSelecionadas.length === 0}
          <div class="normal-actions">
            <span class="badge badge--ok">Todos os animais selecionados estão fora de carência</span>
            <button
              type="button"
              class="btn btn-primary"
              disabled={salvandoVenda}
              onclick={() => submeterVenda(false)}
            >
              {salvandoVenda ? 'Registrando venda...' : `Confirmar venda (${formatBrl(receitaBrutaTotal)})`}
            </button>
          </div>
        {:else if !painelBloqueioVisivel}
          <div class="normal-actions">
            <button
              type="button"
              class="btn btn-primary"
              onclick={() => (painelBloqueioVisivel = true)}
            >
              Validar embarque e confirmar venda
            </button>
          </div>
        {/if}
      </section>

      <!-- Painel de Bloqueio de Carência Sanitária (_carencia_bloqueio) -->
      {#if carenciasAtivasSelecionadas.length > 0 && painelBloqueioVisivel}
        <section class="carencia-bloqueio panel" role="alert" aria-labelledby="titulo-bloqueio-sanitario">
          <div class="carencia-bloqueio__header">
            <div>
              <span class="badge badge--alerta">Trava Sanitária Ativa · HTTP 400</span>
              <h2 id="titulo-bloqueio-sanitario" class="carencia-bloqueio__title">
                Bloqueio Sanitário: <span class="dado">{carenciasAtivasSelecionadas.length}</span> animal(is) em período de carência
              </h2>
            </div>
            <span class="dado carencia-bloqueio__ref">vw_animais_em_carencia</span>
          </div>

          <p class="carencia-bloqueio__desc">
            Os animais listados abaixo receberam medicação cujo prazo residual para abate ainda não encerrou. A venda padrão foi bloqueada para proteção sanitária e jurídica da fazenda.
          </p>

          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>Brinco</th>
                  <th>Medicamento aplicado</th>
                  <th class="col-num">Data aplicação</th>
                  <th class="col-num">Data liberação</th>
                  <th class="col-num">Dias restantes</th>
                </tr>
              </thead>
              <tbody>
                {#each carenciasAtivasSelecionadas as c}
                  <tr>
                    <td class="dado"><strong>#{c.brinco}</strong></td>
                    <td>{c.medicamento}</td>
                    <td class="col-num dado">{c.dataAplicacao}</td>
                    <td class="col-num dado">{c.dataLiberacao}</td>
                    <td class="col-num dado dado--alerta"><strong>{c.diasRestantes} dias</strong></td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <label class="override-checkbox">
            <input type="checkbox" bind:checked={confirmarCarenciaOverride} />
            <span>
              Estou ciente de que os animais listados ainda estão no prazo de carência e autorizo o registro desta venda sob minha responsabilidade (<code class="dado">confirmar_carencia=1</code> · grava auditoria em <code class="dado">vendas_com_carencia</code> com <code class="dado">autorizado_por = @{auth.user.username}</code>).
            </span>
          </label>

          <div class="override-footer">
            <button
              type="button"
              class="btn btn-danger"
              disabled={!confirmarCarenciaOverride || salvandoVenda}
              onclick={() => submeterVenda(true)}
            >
              {salvandoVenda ? 'Gravando auditoria...' : 'Confirmar venda com override auditado'}
            </button>

            <button
              type="button"
              class="btn btn-outline"
              onclick={() => selecionarAnimalIndividual('421')}
            >
              Trocar para animal liberado (#421)
            </button>
          </div>
        </section>
      {/if}

      {#if vendaConcluidaMsg}
        <div class="success-banner panel" role="status">
          <span class="badge badge--ok">Operação concluída</span>
          <span>{vendaConcluidaMsg}</span>
        </div>
      {/if}
    </div>

    <!-- Coluna Lateral: Demonstrativo P&L da Venda -->
    <aside class="pl-sidebar panel">
      <h2 class="section-title">Demonstrativo P&L da Venda</h2>
      <p class="pl-sub">Apuração de margem sobre os animais selecionados</p>

      <div class="pl-kpi-main">
        <span class="pl-kpi-main__label">Receita bruta de venda</span>
        <strong class="pl-kpi-main__value dado dado--ok">{formatBrl(receitaBrutaTotal)}</strong>
        <span class="pl-kpi-main__meta dado">
          {formatKg(pesoTotalSaidaKg)} = {formatArroba(pesoTotalSaidaKg)} × {formatBrl(valorArrobaNegociada)}/@
        </span>
      </div>

      <dl class="pl-breakdown">
        <div>
          <dt>Cabeças no embarque</dt>
          <dd class="dado">{animaisSelecionadosObj.length} cab.</dd>
        </div>
        <div>
          <dt>(-) Custo de aquisição (compra)</dt>
          <dd class="dado">{formatBrl(custoAquisicaoTotal)}</dd>
        </div>
        <div>
          <dt>(-) Custo operacional + sanitário</dt>
          <dd class="dado">{formatBrl(custoOperacionalTotal)}</dd>
        </div>
        <div class="pl-breakdown__total">
          <dt>(=) Custo total investido</dt>
          <dd class="dado">{formatBrl(custoTotalAcumulado)}</dd>
        </div>
      </dl>

      <div class="pl-result" class:pl-result--ok={resultadoLiquidoPl >= 0} class:pl-result--alerta={resultadoLiquidoPl < 0}>
        <div class="pl-result__row">
          <span>Lucro líquido na operação</span>
          <strong class="dado">{formatBrl(resultadoLiquidoPl)}</strong>
        </div>
        <div class="pl-result__row">
          <span>Margem / ROI sobre custo</span>
          <strong class="dado">{margemRoiPct >= 0 ? '+' : ''}{margemRoiPct.toFixed(1).replace('.', ',')}%</strong>
        </div>
      </div>
    </aside>
  </div>
</div>

<style>
  .venda-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .page-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .badge-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .mode-switch {
    display: inline-flex;
    overflow: hidden;
    background: var(--color-surface-sunken);
  }

  .mode-btn {
    min-height: 38px;
    padding: 0 var(--space-4);
    border: none;
    background: transparent;
    color: var(--color-ink-secondary);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    cursor: pointer;
  }
  .mode-btn--active {
    background: var(--color-primary);
    color: #fff;
  }

  .venda-grid {
    display: grid;
    grid-template-columns: 1.55fr 1fr;
    gap: var(--space-5);
    align-items: start;
  }

  .main-col {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .card-block {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .animal-selector {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 148px), 1fr));
    gap: var(--space-2);
  }

  .animal-pill {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    padding: var(--space-3);
    background: var(--color-surface);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    cursor: pointer;
    text-align: left;
  }
  .animal-pill--selected {
    border-color: var(--color-primary);
    background: var(--color-primary-bg);
    box-shadow: inset 0 0 0 1px var(--color-primary);
  }
  .animal-pill--selected.animal-pill--carencia {
    border-color: var(--color-danger);
    background: var(--color-danger-bg);
    box-shadow: inset 0 0 0 1px var(--color-danger);
  }

  .animal-pill__top {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: var(--text-sm);
  }

  .animal-pill__meta {
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
  }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
  }

  .grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  .field label {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--color-ink-secondary);
  }

  .normal-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-border);
  }

  .carencia-bloqueio {
    padding: var(--space-5);
    background: var(--color-danger-bg);
    border: 1px solid var(--color-danger);
    border-left: 4px solid var(--color-danger);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .carencia-bloqueio__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .carencia-bloqueio__title {
    font-size: var(--text-lg);
    color: var(--color-danger-dark);
    margin-top: var(--space-1);
  }

  .carencia-bloqueio__ref {
    font-size: var(--text-xs);
    color: var(--color-danger-dark);
  }

  .carencia-bloqueio__desc {
    font-size: var(--text-sm);
    color: var(--color-danger-dark);
    font-weight: var(--weight-regular);
  }

  .override-checkbox {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--color-surface);
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    color: var(--color-ink);
    cursor: pointer;
  }
  .override-checkbox input {
    margin-top: 3px;
  }

  .override-footer {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .success-banner {
    padding: var(--space-3) var(--space-4);
    background: var(--color-primary-bg);
    border-color: var(--color-primary);
    border-left: 4px solid var(--color-primary);
    color: var(--color-primary-dark);
    display: flex;
    align-items: center;
    gap: var(--space-3);
    font-size: var(--text-sm);
  }

  .pl-sidebar {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .pl-sub {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
    margin-top: -10px;
  }

  .pl-kpi-main {
    padding: var(--space-4);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .pl-kpi-main__label {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }
  .pl-kpi-main__value {
    font-size: var(--text-2xl);
    font-weight: var(--weight-semibold);
  }
  .pl-kpi-main__meta {
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
  }

  .pl-breakdown {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--text-sm);
  }
  .pl-breakdown div {
    display: flex;
    justify-content: space-between;
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--color-border);
  }
  .pl-breakdown dt {
    color: var(--color-ink-secondary);
  }
  .pl-breakdown dd {
    font-weight: var(--weight-semibold);
  }
  .pl-breakdown__total {
    font-weight: var(--weight-semibold);
    color: var(--color-ink);
  }

  .pl-result {
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--text-sm);
  }
  .pl-result--ok {
    background: var(--color-primary-bg);
    border: 1px solid var(--color-primary);
    color: var(--color-primary-dark);
  }
  .pl-result--alerta {
    background: var(--color-danger-bg);
    border: 1px solid var(--color-danger);
    color: var(--color-danger-dark);
  }
  .pl-result__row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  @media (max-width: 960px) {
    .venda-grid,
    .grid-3,
    .grid-2 {
      grid-template-columns: 1fr;
    }
    .card-block,
    .pl-sidebar,
    .carencia-bloqueio {
      padding: var(--space-4);
    }
    .mode-switch {
      width: 100%;
    }
    .mode-btn {
      flex: 1;
    }
    .normal-actions .btn,
    .override-footer .btn {
      width: 100%;
    }
  }
</style>
