<script lang="ts">
  import { formatBrl } from '../lib/format';
  import { router } from '../lib/router.svelte';

  let cabecasSim = $state(235);
  let arrobaHoje = $state(338.5);
  let ganhoGmdExtra = 0.15;

  let patrimonioEstimado = $derived(cabecasSim * 16.2 * arrobaHoje);
  let ganhoAnualExtra = $derived(((cabecasSim * ganhoGmdExtra * 365) / 30) * arrobaHoje);
</script>

<div class="landing">
  <header class="landing-nav">
    <div class="landing-nav__inner">
      <div class="brand">
        <span class="brand__badge dado">SGG</span>
        <div>
          <strong>Sistema de Gestão de Gado</strong>
          <small>ERP Zootécnico · Pecuária de Corte</small>
        </div>
      </div>

      <div class="landing-actions">
        <button type="button" class="btn btn-outline" onclick={() => router.navegar('login')}>
          Entrar
        </button>
        <button type="button" class="btn btn-primary" onclick={() => router.navegar('inicio')}>
          Abrir demonstração
        </button>
      </div>
    </div>
  </header>

  <section class="hero">
    <div class="hero__inner">
      <div class="hero__copy">
        <span class="badge badge--ok">GMD em SQL · Trava de Carência · P&L por Lote</span>
        <h1>Controle zootécnico e financeiro para pecuária de corte.</h1>
        <p>
          Substitua planilhas soltas por rastreamento individual de brinco, cálculo exato de Ganho Médio Diário
          no banco de dados, bloqueio auditado de venda em carência sanitária e apuração de margem real por lote.
        </p>

        <div class="hero__ctas">
          <button type="button" class="btn btn-primary" onclick={() => router.navegar('inicio')}>
            Testar demonstração (Fazenda São Marcos)
          </button>
          <button type="button" class="btn btn-outline" onclick={() => router.navegar('login')}>
            Criar conta (14 dias grátis)
          </button>
        </div>

        <div class="metric-strip hero__strip">
          <div class="metric-cell">
            <span class="m-lbl">Rebanho demo</span>
            <strong class="dado">235 cab.</strong>
          </div>
          <div class="metric-cell">
            <span class="m-lbl">GMD médio</span>
            <strong class="dado dado--ok">0,730 kg/d</strong>
          </div>
          <div class="metric-cell">
            <span class="m-lbl">Praças monitoradas</span>
            <strong class="dado">33 praças</strong>
          </div>
        </div>
      </div>

      <div class="hero__card panel">
        <h3>Simulador de impacto no rebanho</h3>

        <div class="sim-slider">
          <label for="sim-cab">
            <span>Cabeças em campo</span>
            <strong class="dado">{cabecasSim} cab.</strong>
          </label>
          <input id="sim-cab" type="range" min="30" max="1500" step="5" bind:value={cabecasSim} />
        </div>

        <div class="sim-slider">
          <label for="sim-arr">
            <span>Cotação da arroba na praça</span>
            <strong class="dado">{formatBrl(arrobaHoje)}/@</strong>
          </label>
          <input id="sim-arr" type="range" min="240" max="400" step="1.5" bind:value={arrobaHoje} />
        </div>

        <div class="sim-results">
          <div class="sim-box">
            <span>Patrimônio vivo estimado (média 16,2@)</span>
            <strong class="dado">{formatBrl(patrimonioEstimado)}</strong>
          </div>
          <div class="sim-box sim-box--highlight">
            <span>Receita anual recuperada (+0,150 kg/d no lote lento)</span>
            <strong class="dado dado--ok">+{formatBrl(ganhoAnualExtra)}/ano</strong>
          </div>
        </div>
      </div>
    </div>
  </section>
</div>

<style>
  .landing {
    min-height: 100vh;
    background: var(--color-surface-sunken);
  }

  .landing-nav {
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .landing-nav__inner {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-3) var(--space-6);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  .brand__badge {
    background: var(--color-primary);
    color: #fff;
    font-weight: var(--weight-semibold);
    padding: 4px 10px;
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
  }
  .brand div {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
  }
  .brand small {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .landing-actions {
    display: flex;
    gap: var(--space-2);
  }

  .hero {
    padding: var(--space-12) var(--space-6);
  }

  .hero__inner {
    max-width: 1200px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: var(--space-8);
    align-items: start;
  }

  .hero__copy {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    align-items: flex-start;
  }

  .hero__copy h1 {
    font-size: clamp(1.85rem, 3.2vw, 2.5rem);
    line-height: 1.15;
    letter-spacing: -0.025em;
  }

  .hero__copy p {
    color: var(--color-ink-secondary);
    font-size: var(--text-md);
    line-height: 1.55;
  }

  .hero__ctas {
    display: flex;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding: var(--space-2) 0;
  }

  .hero__strip {
    width: 100%;
    margin-top: var(--space-2);
  }
  .m-lbl {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .hero__card {
    padding: var(--space-6);
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .sim-slider {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .sim-slider label {
    display: flex;
    justify-content: space-between;
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
  }
  .sim-slider input[type='range'] {
    width: 100%;
    accent-color: var(--color-primary);
  }

  .sim-results {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .sim-box {
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .sim-box span {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }
  .sim-box strong {
    font-size: var(--text-xl);
  }
  .sim-box--highlight {
    background: var(--color-primary-bg);
    border-color: var(--color-primary-light);
  }

  @media (max-width: 920px) {
    .hero__inner {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .landing-nav__inner {
      padding: var(--space-3) var(--space-4);
      flex-wrap: wrap;
    }
    .hero {
      padding: var(--space-6) var(--space-4);
    }
    .hero__card {
      padding: var(--space-4);
    }
    .hero__ctas {
      width: 100%;
    }
    .hero__ctas .btn {
      flex: 1 1 100%;
    }
  }
</style>
