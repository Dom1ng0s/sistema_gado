<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from '../../lib/auth.svelte';
  import { router } from '../../lib/router.svelte';

  let inputEl: HTMLInputElement | undefined = $state();
  let termo = $state('');

  function submeterBusca(e: SubmitEvent) {
    e.preventDefault();
    if (!termo.trim()) return;
    router.navegar('rebanho', termo.trim());
  }

  onMount(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === '/' &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
        inputEl?.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });
</script>

<header class="topbar">
  <button
    type="button"
    class="topbar__menu-btn"
    aria-label="Abrir menu principal"
    aria-expanded={router.menuMobileAberto}
    onclick={() => router.alternarMenuMobile()}
  >
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  </button>

  {#if auth.podeVerCampo}
    <form class="busca-global" role="search" onsubmit={submeterBusca}>
      <div class="busca-global__campo">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-4.3-4.3" />
        </svg>
        <label class="sr-only" for="busca-brinco">Buscar animal por brinco</label>
        <input
          bind:this={inputEl}
          bind:value={termo}
          id="busca-brinco"
          type="search"
          placeholder="Buscar brinco..."
          autocomplete="off"
        />
        <kbd class="busca-global__atalho" aria-hidden="true">/</kbd>
      </div>
    </form>
  {:else}
    <div class="topbar__context">Leitura contábil · {auth.user.nome_fazenda}</div>
  {/if}

  <div class="topbar__meta">
    <span class="market-ticker">
      Boi SP: <strong class="dado">R$ 338,50/@</strong>
      <span class="sep">·</span>
      Novilha: <strong class="dado">R$ 312,00/@</strong>
    </span>

    {#if auth.user.plano.limite_cabecas}
      <button
        type="button"
        class="quota-pill"
        class:quota-pill--alerta={auth.user.plano.estourado || (auth.user.plano.uso_pct ?? 0) >= 95}
        onclick={() => router.irParaConfig('plano')}
        title="Capacidade do plano atual"
      >
        <span class="quota-pill__label">{auth.user.plano.rotulo}:</span>
        <strong class="dado">{auth.user.plano.cabecas}/{auth.user.plano.limite_cabecas} cab.</strong>
      </button>
    {/if}
  </div>
</header>

<style>
  .topbar {
    position: sticky;
    top: 0;
    z-index: var(--z-sticky);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-6);
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .topbar__menu-btn {
    display: none;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    flex-shrink: 0;
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink);
    cursor: pointer;
  }

  .busca-global {
    display: flex;
    align-items: center;
    flex: 1;
    min-width: 0;
    max-width: 380px;
  }

  .busca-global__campo {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex: 1;
    min-width: 0;
    padding: 0 var(--space-3);
    min-height: 36px;
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-tertiary);
  }
  .busca-global__campo svg {
    flex-shrink: 0;
  }
  .busca-global__campo:focus-within {
    background: var(--color-surface);
    border-color: var(--color-primary);
    outline: 2px solid var(--color-primary);
    outline-offset: -1px;
  }

  .busca-global__campo input {
    border: none;
    background: transparent;
    width: 100%;
    min-width: 0;
    font-family: var(--font-dado);
    font-size: var(--text-sm);
    color: var(--color-ink);
    outline: none;
  }

  .busca-global__atalho {
    font-family: var(--font-dado);
    font-size: 11px;
    padding: 1px 6px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    color: var(--color-ink-tertiary);
    flex-shrink: 0;
  }

  .topbar__context {
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .topbar__meta {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    flex-shrink: 0;
  }

  .market-ticker {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }
  .market-ticker strong {
    color: var(--color-ink);
  }
  .sep {
    margin: 0 var(--space-1);
    color: var(--color-border-strong);
  }

  .quota-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    font-size: var(--text-xs);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    color: var(--color-ink-secondary);
    cursor: pointer;
    white-space: nowrap;
  }
  .quota-pill--alerta {
    background: var(--color-danger-bg);
    border-color: var(--color-danger);
    color: var(--color-danger-dark);
  }

  @media (max-width: 860px) {
    .topbar {
      padding: var(--space-2) var(--space-3);
      gap: var(--space-2);
    }
    .topbar__menu-btn {
      display: inline-flex;
    }
    .busca-global {
      max-width: none;
    }
    .busca-global__campo {
      min-height: 38px;
    }
    .busca-global__campo input {
      font-size: 1rem;
    }
    .busca-global__atalho,
    .market-ticker {
      display: none;
    }
  }

  @media (max-width: 480px) {
    .quota-pill__label {
      display: none;
    }
  }
</style>
