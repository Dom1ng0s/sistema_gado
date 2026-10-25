<script lang="ts">
  import { auth } from '../../lib/auth.svelte';
  import { router, type RotaId } from '../../lib/router.svelte';
  import type { Papel } from '../../lib/types';

  let recolhida = $state(false);
  let menuRegistrarAberto = $state(false);
  let menuContaAberto = $state(false);
  let exibirTexto = $derived(!recolhida || router.menuMobileAberto);

  function irPara(rota: RotaId) {
    router.navegar(rota);
    menuRegistrarAberto = false;
    menuContaAberto = false;
  }

  function irParaGov(aba: 'fazenda' | 'acessos' | 'plano' | 'lixeira') {
    router.irParaConfig(aba);
    menuContaAberto = false;
  }

  const papeisDemo: Papel[] = ['dono', 'vaqueiro', 'contador', 'consultor'];
</script>

{#if router.menuMobileAberto}
  <div
    class="sidebar-backdrop"
    role="presentation"
    onclick={() => router.alternarMenuMobile(false)}
  ></div>
{/if}

<aside
  class="sidebar"
  class:sidebar--recolhida={recolhida && !router.menuMobileAberto}
  class:sidebar--aberta={router.menuMobileAberto}
  aria-label="Navegação principal"
>
  <div class="sidebar__topo">
    <a
      href="#/inicio"
      class="marca"
      onclick={(e) => {
        e.preventDefault();
        irPara('inicio');
      }}
    >
      <span class="marca__monograma dado">SGG</span>
      {#if exibirTexto}
        <div class="marca__texto">
          <strong>{auth.user.nome_fazenda}</strong>
          <span>Gestão de Gado</span>
        </div>
      {/if}
    </a>

    <button
      type="button"
      class="collapse-btn"
      title={recolhida ? 'Expandir barra lateral' : 'Recolher barra lateral'}
      onclick={() => (recolhida = !recolhida)}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
        {#if recolhida}
          <polyline points="9 18 15 12 9 6" />
        {:else}
          <polyline points="15 18 9 12 15 6" />
        {/if}
      </svg>
    </button>

    <button
      type="button"
      class="drawer-close-btn"
      aria-label="Fechar menu de navegação"
      onclick={() => router.alternarMenuMobile(false)}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round">
        <path d="M18 6 6 18M6 6l12 12" />
      </svg>
    </button>
  </div>

  <div class="sidebar__corpo">
    {#if auth.podeEscreverNoCampo || auth.podeGerirFazenda}
      <div class="registrar">
        <button
          type="button"
          class="btn btn-primary registrar__gatilho"
          aria-expanded={menuRegistrarAberto}
          onclick={() => (menuRegistrarAberto = !menuRegistrarAberto)}
        >
          {#if !exibirTexto}
            <span>+</span>
          {:else}
            <span>Registrar</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          {/if}
        </button>

        {#if menuRegistrarAberto}
          <div class="dropdown-panel" role="menu">
            {#if auth.podeEscreverNoCampo}
              <button type="button" class="dropdown-item" role="menuitem" onclick={() => irPara('pesagem')}>
                <strong>Pesagem no tronco</strong>
                <small>Individual ou lote</small>
              </button>
              <button type="button" class="dropdown-item" role="menuitem" onclick={() => irPara('medicar')}>
                <strong>Medicação ou vacina</strong>
                <small>Cálculo automático de carência</small>
              </button>
              <button type="button" class="dropdown-item" role="menuitem" onclick={() => irPara('entrada')}>
                <strong>Entrada de animal</strong>
                <small>Individual, lote ou CSV</small>
              </button>
            {/if}
            {#if auth.podeGerirFazenda}
              <button type="button" class="dropdown-item" role="menuitem" onclick={() => irPara('venda')}>
                <strong>Registrar venda</strong>
                <small>Com trava sanitária auditada</small>
              </button>
              <button type="button" class="dropdown-item" role="menuitem" onclick={() => irPara('financeiro')}>
                <strong>Lançar custo</strong>
                <small>Pago ou agendado a pagar</small>
              </button>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <nav class="nav-grupos" aria-label="Menu principal">
      <!-- Rotina Diária -->
      <div class="nav-grupo">
        {#if exibirTexto}<span class="nav-categoria">Rotina</span>{/if}

        <button
          type="button"
          class="nav-item"
          class:active={router.rotaAtual === 'inicio'}
          onclick={() => irPara('inicio')}
          title="Início"
        >
          <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>
          {#if exibirTexto}<span>Início</span>{/if}
        </button>

        {#if auth.podeVerCampo}
          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'rebanho'}
            onclick={() => irPara('rebanho')}
            title="Rebanho"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
            {#if exibirTexto}
              <span>Rebanho</span>
              <span class="nav-count dado">235</span>
            {/if}
          </button>
        {/if}

        {#if auth.podeEscreverNoCampo}
          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'pesagem'}
            onclick={() => irPara('pesagem')}
            title="Pesagem"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M12 3v18M5 7h14"/><path d="M5 7 2 14h6zM19 7l-3 7h6z"/></svg>
            {#if exibirTexto}<span>Pesagem</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'entrada'}
            onclick={() => irPara('entrada')}
            title="Entrada e Importação CSV"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
            {#if exibirTexto}<span>Entrada / CSV</span>{/if}
          </button>
        {/if}

        {#if auth.podeGerirFazenda}
          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'venda'}
            onclick={() => irPara('venda')}
            title="Venda"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/></svg>
            {#if exibirTexto}<span>Venda</span>{/if}
          </button>
        {/if}
      </div>

      <!-- Financeiro & Lotes -->
      {#if auth.podeVerFinanceiro}
        <div class="nav-grupo">
          {#if exibirTexto}<span class="nav-categoria">Financeiro</span>{/if}

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'financeiro'}
            onclick={() => irPara('financeiro')}
            title="Fluxo de Caixa"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            {#if exibirTexto}<span>Fluxo de caixa</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'lotes'}
            onclick={() => irPara('lotes')}
            title="Resultado por Lote"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>
            {#if exibirTexto}<span>Resultado por lote</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'simulador-custo'}
            onclick={() => irPara('simulador-custo')}
            title="Simulador de Custo da @"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><rect width="16" height="20" x="4" y="2" rx="2"/><line x1="8" x2="16" y1="6" y2="6"/><line x1="8" x2="16" y1="12" y2="12"/><line x1="8" x2="12" y1="17" y2="17"/></svg>
            {#if exibirTexto}<span>Simulador da @</span>{/if}
          </button>
        </div>
      {/if}

      <!-- Manejo & Zootecnia -->
      {#if auth.podeVerCampo}
        <div class="nav-grupo">
          {#if exibirTexto}<span class="nav-categoria">Zootecnia</span>{/if}

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'pastos'}
            onclick={() => irPara('pastos')}
            title="Pastos e Módulos"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3 17h18M5 17V7l7-4 7 4v10"/></svg>
            {#if exibirTexto}<span>Pastos</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'pastos-gmd'}
            onclick={() => irPara('pastos-gmd')}
            title="GMD por Módulo"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
            {#if exibirTexto}<span>GMD por pasto</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'reproducao'}
            onclick={() => irPara('reproducao')}
            title="Reprodução"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>
            {#if exibirTexto}<span>Reprodução</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'ranking-touros'}
            onclick={() => irPara('ranking-touros')}
            title="Ranking de Touros"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="14"/></svg>
            {#if exibirTexto}<span>Ranking de touros</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'sanidade'}
            onclick={() => irPara('sanidade')}
            title="Sanidade"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            {#if exibirTexto}<span>Sanidade</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'estoque'}
            onclick={() => irPara('estoque')}
            title="Estoque"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/></svg>
            {#if exibirTexto}<span>Estoque</span>{/if}
          </button>

          <button
            type="button"
            class="nav-item"
            class:active={router.rotaAtual === 'relatorios'}
            onclick={() => irPara('relatorios')}
            title="Relatórios"
          >
            <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            {#if exibirTexto}<span>Relatórios</span>{/if}
          </button>
        </div>
      {/if}

      <!-- Conta & Governança -->
      <div class="nav-grupo">
        {#if exibirTexto}<span class="nav-categoria">Sistema</span>{/if}

        <button
          type="button"
          class="nav-item"
          class:active={router.rotaAtual === 'configuracoes' && router.abaConfig === 'acessos'}
          onclick={() => irParaGov('acessos')}
          title="Equipe e Acessos"
        >
          <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/></svg>
          {#if exibirTexto}<span>Equipe e acessos</span>{/if}
        </button>

        <button
          type="button"
          class="nav-item"
          class:active={router.rotaAtual === 'configuracoes' && router.abaConfig === 'plano'}
          onclick={() => irParaGov('plano')}
          title="Plano"
        >
          <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>
          {#if exibirTexto}<span>Plano e vagas</span>{/if}
        </button>

        <button
          type="button"
          class="nav-item"
          class:active={router.rotaAtual === 'configuracoes' && router.abaConfig === 'lixeira'}
          onclick={() => irParaGov('lixeira')}
          title="Lixeira"
        >
          <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
          {#if exibirTexto}<span>Lixeira</span>{/if}
        </button>

        <button
          type="button"
          class="nav-item"
          class:active={router.rotaAtual === 'landing'}
          onclick={() => irPara('landing')}
          title="Página institucional"
        >
          <svg class="nav-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="10"/><line x1="2" x2="22" y1="12" y2="12"/></svg>
          {#if exibirTexto}<span>Apresentação</span>{/if}
        </button>
      </div>
    </nav>

    <div class="conta">
      {#if exibirTexto}
        <div class="rbac-switcher">
          <span class="rbac-switcher__label">Papel (RBAC):</span>
          <div class="rbac-switcher__pills">
            {#each papeisDemo as p}
              <button
                type="button"
                class="rbac-pill"
                class:rbac-pill--ativo={auth.papel === p}
                onclick={() => auth.setPapelSimulado(p)}
              >
                {p}
              </button>
            {/each}
          </div>
        </div>
      {/if}

      <button
        type="button"
        class="conta__gatilho"
        aria-expanded={menuContaAberto}
        onclick={() => (menuContaAberto = !menuContaAberto)}
      >
        <span class="conta__avatar dado">{auth.user.username.slice(0, 2).toUpperCase()}</span>
        {#if exibirTexto}
          <span class="conta__info">
            <strong>{auth.user.username}</strong>
            <small>{auth.user.nome_fazenda}</small>
          </span>
        {/if}
      </button>

      {#if menuContaAberto}
        <div class="dropdown-panel dropdown-panel--up" role="menu">
          <div class="dropdown-header">
            <span>Alternar fazenda</span>
          </div>
          {#each auth.user.fazendas as faz}
            <button
              type="button"
              class="dropdown-item"
              onclick={() => {
                auth.trocarFazenda(faz.id);
                menuContaAberto = false;
              }}
            >
              <strong>{faz.atual ? '• ' : ''}{faz.nome}</strong>
              <small>Papel: {faz.papel}</small>
            </button>
          {/each}
          <hr class="dropdown-sep" />
          <button type="button" class="dropdown-item" onclick={() => irParaGov('fazenda')}>
            <strong>Configurações da fazenda</strong>
            <small>Cidade/UF e meta de GMD</small>
          </button>
          <button type="button" class="dropdown-item" onclick={() => irPara('login')}>
            <strong>Trocar conta / Login</strong>
            <small>Autenticação e senha</small>
          </button>
        </div>
      {/if}
    </div>
  </div>
</aside>

<style>
  .sidebar {
    width: var(--sidebar-largura);
    flex-shrink: 0;
    background: var(--color-surface);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    padding: var(--space-4) var(--space-3);
    gap: var(--space-4);
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
  }

  .sidebar--recolhida {
    width: var(--sidebar-recolhida);
    align-items: center;
  }

  .sidebar__topo {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-1);
    gap: var(--space-2);
  }

  .marca {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    text-decoration: none;
    color: var(--color-ink);
    min-width: 0;
  }
  .marca__monograma {
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    background: var(--color-primary);
    color: #fff;
    font-size: var(--text-xs);
    font-weight: var(--weight-semibold);
    flex-shrink: 0;
  }
  .marca__texto {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
    min-width: 0;
  }
  .marca__texto strong {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .marca__texto span {
    font-size: 11px;
    color: var(--color-ink-tertiary);
  }

  .collapse-btn {
    background: transparent;
    border: 1px solid var(--color-border);
    color: var(--color-ink-tertiary);
    width: 26px;
    height: 26px;
    border-radius: var(--radius-sm);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
  }
  .collapse-btn:hover {
    background: var(--color-surface-sunken);
    color: var(--color-ink);
  }

  .drawer-close-btn {
    display: none;
    background: transparent;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    width: 34px;
    height: 34px;
    align-items: center;
    justify-content: center;
    color: var(--color-ink);
    cursor: pointer;
    flex-shrink: 0;
  }

  .sidebar-backdrop {
    display: none;
  }

  .sidebar__corpo {
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: var(--space-4);
    width: 100%;
  }

  .registrar {
    position: relative;
  }
  .registrar__gatilho {
    width: 100%;
    justify-content: space-between;
  }

  .dropdown-panel {
    position: absolute;
    left: 0;
    right: 0;
    top: calc(100% + 4px);
    min-width: 224px;
    z-index: var(--z-dropdown);
    background: var(--color-surface);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
    padding: var(--space-1);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .dropdown-panel--up {
    top: auto;
    bottom: calc(100% + 6px);
  }

  .dropdown-header {
    padding: 4px var(--space-2);
    font-size: 11px;
    font-weight: var(--weight-medium);
    color: var(--color-ink-tertiary);
  }

  .dropdown-sep {
    border: 0;
    border-top: 1px solid var(--color-border);
    margin: 4px 0;
  }

  .dropdown-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    text-align: left;
    cursor: pointer;
    color: var(--color-ink);
  }
  .dropdown-item:hover {
    background: var(--color-surface-sunken);
  }
  .dropdown-item strong {
    font-size: var(--text-sm);
    font-weight: var(--weight-medium);
  }
  .dropdown-item small {
    font-size: 11px;
    color: var(--color-ink-tertiary);
  }

  .nav-grupos {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    flex: 1;
  }

  .nav-grupo {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .nav-categoria {
    font-size: 11px;
    font-weight: var(--weight-medium);
    color: var(--color-ink-tertiary);
    padding: 0 var(--space-2) 4px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    width: 100%;
    padding: 7px var(--space-2);
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-ink-secondary);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: var(--weight-medium);
    text-align: left;
    cursor: pointer;
    transition: background-color var(--transition-fast), color var(--transition-fast);
  }

  .nav-svg {
    width: 16px;
    height: 16px;
    flex-shrink: 0;
    color: var(--color-ink-tertiary);
  }

  .nav-count {
    margin-left: auto;
    font-size: 11px;
    color: var(--color-ink-tertiary);
  }

  .nav-item:hover {
    background: var(--color-surface-sunken);
    color: var(--color-ink);
  }

  .nav-item.active {
    background: var(--color-primary-bg);
    color: var(--color-primary-dark);
    font-weight: var(--weight-semibold);
  }
  .nav-item.active .nav-svg,
  .nav-item.active .nav-count {
    color: var(--color-primary-dark);
  }

  .conta {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .rbac-switcher {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .rbac-switcher__label {
    font-size: 11px;
    color: var(--color-ink-tertiary);
  }
  .rbac-switcher__pills {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
  }
  .rbac-pill {
    font-size: 11px;
    padding: 3px 6px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--color-border);
    background: var(--color-surface-raised);
    color: var(--color-ink-secondary);
    cursor: pointer;
  }
  .rbac-pill--ativo {
    background: var(--color-ink);
    border-color: var(--color-ink);
    color: #fff;
    font-weight: var(--weight-medium);
  }

  .conta__gatilho {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
    color: var(--color-ink);
    cursor: pointer;
    text-align: left;
  }
  .conta__avatar {
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    background: var(--n-200);
    color: var(--color-ink);
    font-size: var(--text-xs);
    font-weight: var(--weight-semibold);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .conta__info {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
    overflow: hidden;
  }
  .conta__info strong {
    font-size: var(--text-sm);
  }
  .conta__info small {
    font-size: 11px;
    color: var(--color-ink-tertiary);
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
  }

  @media (max-width: 860px) {
    .sidebar-backdrop {
      display: block;
      position: fixed;
      inset: 0;
      background: rgba(17, 24, 20, 0.45);
      z-index: var(--z-modal);
    }
    .sidebar {
      position: fixed;
      top: 0;
      bottom: 0;
      left: 0;
      width: min(304px, 88vw);
      height: 100dvh;
      z-index: var(--z-modal);
      border-right: 1px solid var(--color-border);
      padding: var(--space-4);
      box-shadow: var(--shadow-lg);
      transform: translateX(-104%);
      transition: transform var(--transition-normal);
    }
    .sidebar--aberta {
      transform: translateX(0);
    }
    .collapse-btn {
      display: none;
    }
    .drawer-close-btn {
      display: inline-flex;
    }
    .nav-item {
      min-height: 40px;
    }
  }
</style>
