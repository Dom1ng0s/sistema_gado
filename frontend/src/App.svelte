<script lang="ts">
  import { onMount } from 'svelte';
  import BottomNav from './components/shell/BottomNav.svelte';
  import Sidebar from './components/shell/Sidebar.svelte';
  import TopBar from './components/shell/TopBar.svelte';
  import { router } from './lib/router.svelte';

  function sincronizarRotulosTabelas() {
    if (typeof document === 'undefined') return;
    const tabelas = document.querySelectorAll<HTMLTableElement>('table.table:not(.rebanho-table)');
    for (const tabela of tabelas) {
      const ths = Array.from(tabela.querySelectorAll('thead th')).map((th) =>
        (th.textContent ?? '').replace(/[↑↓]/g, '').trim()
      );
      if (ths.length >= 3) {
        tabela.classList.add('table--stack-mobile');
      } else {
        tabela.classList.add('table--compact-mobile');
      }
      for (const tr of tabela.querySelectorAll('tbody tr')) {
        const tds = tr.querySelectorAll('td');
        if (tds.length <= 1) continue;
        tds.forEach((td, i) => {
          const rotulo = ths[i];
          if (rotulo && !td.hasAttribute('data-label')) {
            td.setAttribute('data-label', rotulo);
          }
        });
      }
    }
  }

  onMount(() => {
    sincronizarRotulosTabelas();
    const obs = new MutationObserver(() => sincronizarRotulosTabelas());
    obs.observe(document.body, { childList: true, subtree: true });
    return () => obs.disconnect();
  });

  import Configuracoes from './pages/Configuracoes.svelte';
  import CurralMedicar from './pages/CurralMedicar.svelte';
  import CurralPesagem from './pages/CurralPesagem.svelte';
  import EntradaAnimal from './pages/EntradaAnimal.svelte';
  import Estoque from './pages/Estoque.svelte';
  import Financeiro from './pages/Financeiro.svelte';
  import Inicio from './pages/Inicio.svelte';
  import Landing from './pages/Landing.svelte';
  import Login from './pages/Login.svelte';
  import Pastos from './pages/Pastos.svelte';
  import PastosGmd from './pages/PastosGmd.svelte';
  import RankingTouros from './pages/RankingTouros.svelte';
  import Rebanho from './pages/Rebanho.svelte';
  import Relatorios from './pages/Relatorios.svelte';
  import Reproducao from './pages/Reproducao.svelte';
  import ResultadoLotes from './pages/ResultadoLotes.svelte';
  import Sanidade from './pages/Sanidade.svelte';
  import SimuladorCusto from './pages/SimuladorCusto.svelte';
  import Venda from './pages/Venda.svelte';
</script>

{#if router.rotaAtual === 'login'}
  <main id="main-content">
    <Login />
  </main>
{:else if router.rotaAtual === 'landing'}
  <main id="main-content">
    <Landing />
  </main>
{:else}
  <div class="app-shell">
    <Sidebar />

    <div class="app-main">
      <TopBar />

      <main id="main-content" class="page-container">
        {#if router.rotaAtual === 'inicio'}
          <Inicio />
        {:else if router.rotaAtual === 'rebanho'}
          <Rebanho />
        {:else if router.rotaAtual === 'entrada'}
          <EntradaAnimal />
        {:else if router.rotaAtual === 'pesagem'}
          <CurralPesagem />
        {:else if router.rotaAtual === 'medicar'}
          <CurralMedicar />
        {:else if router.rotaAtual === 'venda'}
          <Venda />
        {:else if router.rotaAtual === 'financeiro'}
          <Financeiro />
        {:else if router.rotaAtual === 'simulador-custo'}
          <SimuladorCusto />
        {:else if router.rotaAtual === 'lotes'}
          <ResultadoLotes />
        {:else if router.rotaAtual === 'pastos'}
          <Pastos />
        {:else if router.rotaAtual === 'pastos-gmd'}
          <PastosGmd />
        {:else if router.rotaAtual === 'estoque'}
          <Estoque />
        {:else if router.rotaAtual === 'sanidade'}
          <Sanidade />
        {:else if router.rotaAtual === 'reproducao'}
          <Reproducao />
        {:else if router.rotaAtual === 'ranking-touros'}
          <RankingTouros />
        {:else if router.rotaAtual === 'relatorios'}
          <Relatorios />
        {:else if router.rotaAtual === 'configuracoes'}
          <Configuracoes />
        {:else}
          <Inicio />
        {/if}
      </main>

      <BottomNav />
    </div>
  </div>
{/if}

<style>
  .app-shell {
    display: flex;
    min-height: 100vh;
    width: 100%;
    max-width: 100%;
    align-items: stretch;
  }

  .app-main {
    flex: 1;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .page-container {
    flex: 1;
    padding: var(--space-6) var(--space-8);
    max-width: 1400px;
    width: 100%;
    min-width: 0;
    margin: 0 auto;
  }

  @media (max-width: 860px) {
    .app-shell {
      flex-direction: column;
    }
    .page-container {
      padding: var(--space-4) var(--space-4) calc(var(--bottom-nav-altura) + var(--space-6));
    }
  }
</style>
