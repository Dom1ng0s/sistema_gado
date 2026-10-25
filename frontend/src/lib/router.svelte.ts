export type RotaId =
  | 'landing'
  | 'login'
  | 'inicio'
  | 'rebanho'
  | 'entrada'
  | 'pesagem'
  | 'medicar'
  | 'venda'
  | 'financeiro'
  | 'simulador-custo'
  | 'lotes'
  | 'pastos'
  | 'pastos-gmd'
  | 'estoque'
  | 'sanidade'
  | 'reproducao'
  | 'ranking-touros'
  | 'relatorios'
  | 'configuracoes';

const ROTAS_VALIDAS: ReadonlySet<RotaId> = new Set<RotaId>([
  'landing',
  'login',
  'inicio',
  'rebanho',
  'entrada',
  'pesagem',
  'medicar',
  'venda',
  'financeiro',
  'simulador-custo',
  'lotes',
  'pastos',
  'pastos-gmd',
  'estoque',
  'sanidade',
  'reproducao',
  'ranking-touros',
  'relatorios',
  'configuracoes'
]);

class RouterStore {
  rotaAtual = $state<RotaId>('inicio');
  buscaBrinco = $state<string>('');
  loteSelecionado = $state<string | null>(null);
  abaConfig = $state<'fazenda' | 'acessos' | 'plano' | 'lixeira'>('fazenda');
  menuMobileAberto = $state<boolean>(false);
  navTick = $state<number>(0);

  navegar(rota: RotaId, brinco?: string) {
    this.rotaAtual = rota;
    this.menuMobileAberto = false;
    this.navTick += 1;
    if (brinco !== undefined) {
      this.buscaBrinco = brinco;
    } else if (rota === 'rebanho') {
      this.buscaBrinco = '';
    }
    if (typeof window !== 'undefined') {
      const targetHash = `#/${rota}`;
      if (window.location.hash !== targetHash) {
        window.location.hash = targetHash;
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  irParaConfig(aba: 'fazenda' | 'acessos' | 'plano' | 'lixeira') {
    this.abaConfig = aba;
    this.navegar('configuracoes');
  }

  abrirLote(codigoLote: string) {
    this.loteSelecionado = codigoLote;
    this.navegar('lotes');
  }

  alternarMenuMobile(forcar?: boolean) {
    this.menuMobileAberto = forcar !== undefined ? forcar : !this.menuMobileAberto;
  }
}

export const router = new RouterStore();

if (typeof window !== 'undefined') {
  const sincronizarHash = () => {
    const limpo = window.location.hash.replace(/^#\/?/, '').split('?')[0] as RotaId;
    if (limpo && ROTAS_VALIDAS.has(limpo)) {
      router.rotaAtual = limpo;
      router.menuMobileAberto = false;
    }
  };
  window.addEventListener('hashchange', sincronizarHash);
  sincronizarHash();
}
