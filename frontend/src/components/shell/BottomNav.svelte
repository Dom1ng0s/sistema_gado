<script lang="ts">
  import { auth } from '../../lib/auth.svelte';
  import { router, type RotaId } from '../../lib/router.svelte';

  let sheetAberto = $state(false);

  function ir(rota: RotaId) {
    sheetAberto = false;
    router.navegar(rota);
  }

  function alternarSheet() {
    router.alternarMenuMobile(false);
    sheetAberto = !sheetAberto;
  }

  function alternarMenu() {
    sheetAberto = false;
    router.alternarMenuMobile();
  }

  let emRotaSecundaria = $derived(
    router.menuMobileAberto ||
      router.rotaAtual === 'pastos' ||
      router.rotaAtual === 'pastos-gmd' ||
      router.rotaAtual === 'sanidade' ||
      router.rotaAtual === 'estoque' ||
      router.rotaAtual === 'reproducao' ||
      router.rotaAtual === 'ranking-touros' ||
      router.rotaAtual === 'relatorios' ||
      router.rotaAtual === 'configuracoes'
  );
</script>

{#if sheetAberto}
  <div
    class="sheet-backdrop"
    role="presentation"
    onclick={() => (sheetAberto = false)}
  >
    <div
      class="sheet-panel"
      role="dialog"
      tabindex="-1"
      aria-label="Registrar operação de campo"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.key === 'Escape' && (sheetAberto = false)}
    >
      <div class="sheet-head">
        <strong>Registrar operação</strong>
        <button type="button" class="sheet-close" onclick={() => (sheetAberto = false)}>Fechar</button>
      </div>

      <div class="sheet-grid">
        {#if auth.podeEscreverNoCampo}
          <button type="button" class="sheet-item" onclick={() => ir('pesagem')}>
            <strong>Pesagem no tronco</strong>
            <small>Individual ou lote</small>
          </button>

          <button type="button" class="sheet-item" onclick={() => ir('medicar')}>
            <strong>Medicar ou vacinar</strong>
            <small>Cálculo automático de carência</small>
          </button>

          <button type="button" class="sheet-item" onclick={() => ir('entrada')}>
            <strong>Entrada de animal</strong>
            <small>Individual, lote ou CSV</small>
          </button>
        {/if}

        {#if auth.podeGerirFazenda}
          <button type="button" class="sheet-item" onclick={() => ir('venda')}>
            <strong>Registrar venda</strong>
            <small>Com trava sanitária</small>
          </button>
        {/if}

        {#if auth.podeVerFinanceiro}
          <button type="button" class="sheet-item" onclick={() => ir('simulador-custo')}>
            <strong>Simulador da @</strong>
            <small>Ponto de equilíbrio</small>
          </button>

          <button type="button" class="sheet-item" onclick={() => ir('lotes')}>
            <strong>Resultado por lote</strong>
            <small>P&L e prontuário</small>
          </button>
        {/if}

        {#if auth.podeVerCampo}
          <button type="button" class="sheet-item" onclick={() => ir('pastos')}>
            <strong>Pastos e lotação</strong>
            <small>Alocação e UA/ha</small>
          </button>

          <button type="button" class="sheet-item" onclick={() => ir('sanidade')}>
            <strong>Sanidade e carência</strong>
            <small>Protocolos e bloqueios</small>
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<nav class="bottom-nav" aria-label="Navegação mobile">
  <button
    type="button"
    class="bnav-btn"
    class:active={router.rotaAtual === 'inicio' && !router.menuMobileAberto}
    onclick={() => ir('inicio')}
  >
    <svg class="bnav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>
    <span>Início</span>
  </button>

  <button
    type="button"
    class="bnav-btn"
    class:active={router.rotaAtual === 'rebanho' && !router.menuMobileAberto}
    onclick={() => ir('rebanho')}
  >
    <svg class="bnav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
    <span>Rebanho</span>
  </button>

  <button
    type="button"
    class="bnav-cta"
    aria-label="Registrar operação"
    aria-expanded={sheetAberto}
    onclick={alternarSheet}
  >
    + Registrar
  </button>

  <button
    type="button"
    class="bnav-btn"
    class:active={(router.rotaAtual === 'financeiro' || router.rotaAtual === 'simulador-custo' || router.rotaAtual === 'lotes') && !router.menuMobileAberto}
    onclick={() => ir('financeiro')}
  >
    <svg class="bnav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
    <span>Financeiro</span>
  </button>

  <button
    type="button"
    class="bnav-btn"
    class:active={emRotaSecundaria}
    aria-expanded={router.menuMobileAberto}
    onclick={alternarMenu}
  >
    <svg class="bnav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
    <span>Menu</span>
  </button>
</nav>

<style>
  .bottom-nav {
    display: none;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: var(--bottom-nav-altura);
    background: var(--color-surface);
    border-top: 1px solid var(--color-border);
    z-index: var(--z-nav);
    justify-content: space-around;
    align-items: center;
    padding: 0 var(--space-2);
  }

  .bnav-btn {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    background: none;
    border: none;
    color: var(--color-ink-tertiary);
    font-family: var(--font-body);
    font-size: 11px;
    font-weight: var(--weight-medium);
    cursor: pointer;
    padding: 6px var(--space-2);
    border-radius: var(--radius-sm);
    min-width: 56px;
  }
  .bnav-svg {
    width: 17px;
    height: 17px;
  }
  .bnav-btn.active {
    color: var(--color-primary);
    font-weight: var(--weight-semibold);
  }

  .bnav-cta {
    background: var(--color-primary);
    color: #fff;
    border: none;
    border-radius: var(--radius-md);
    padding: 9px 14px;
    font-family: var(--font-body);
    font-size: var(--text-xs);
    font-weight: var(--weight-semibold);
    cursor: pointer;
    white-space: nowrap;
  }

  .sheet-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(20, 28, 23, 0.45);
    z-index: var(--z-modal);
    display: flex;
    align-items: flex-end;
  }

  .sheet-panel {
    width: 100%;
    max-height: 85dvh;
    overflow-y: auto;
    background: var(--color-surface);
    border-top: 1px solid var(--color-border);
    padding: var(--space-4) var(--space-4) calc(var(--bottom-nav-altura) + var(--space-4));
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    box-shadow: var(--shadow-lg);
  }

  .sheet-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .sheet-close {
    background: transparent;
    border: 1px solid var(--color-border-strong);
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    font-weight: var(--weight-medium);
    color: var(--color-ink);
    cursor: pointer;
  }

  .sheet-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
  }

  .sheet-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: var(--space-3);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    text-align: left;
    cursor: pointer;
  }
  .sheet-item strong {
    font-size: var(--text-sm);
    color: var(--color-ink);
  }
  .sheet-item small {
    font-size: 11px;
    color: var(--color-ink-tertiary);
  }

  @media (max-width: 860px) {
    .bottom-nav {
      display: flex;
    }
  }

  @media (max-width: 380px) {
    .sheet-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
