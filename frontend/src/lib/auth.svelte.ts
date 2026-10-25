import type { Papel, UsuarioSessao } from './types';

/**
 * Estado global de sessão e RBAC (espelhando utils/permissions.py).
 * Permite simular os 4 papéis (dono, vaqueiro, contador, consultor) durante o desenvolvimento
 * e sincronizar com /api/auth/me assim que a Trilha 1 (Backend Auth API) estiver ativa.
 */
const SESSAO_PADRAO: UsuarioSessao = {
  id: 1,
  username: 'demonstracao',
  email: 'demo@fazendasaomarcos.com.br',
  farm_id: 1,
  nome_fazenda: 'Fazenda São Marcos',
  gmd_meta: 0.65,
  papel: 'dono',
  fazendas: [
    { id: 1, nome: 'Fazenda São Marcos', papel: 'dono', atual: true },
    { id: 2, nome: 'Estância Santa Inês', papel: 'consultor', atual: false }
  ],
  plano: {
    tier: 'porteira',
    rotulo: 'Porteira',
    status: 'ativo',
    em_trial: false,
    dias_restantes: null,
    expirado: false,
    limite_cabecas: 250,
    sem_limite: false,
    cabecas: 235,
    vagas: 15,
    estourado: false,
    uso_pct: 94
  }
};

class AuthStore {
  user = $state<UsuarioSessao>(SESSAO_PADRAO);

  get papel(): Papel {
    return this.user.papel;
  }

  get podeEscreverNoCampo(): boolean {
    return this.user.papel === 'dono' || this.user.papel === 'vaqueiro';
  }

  get podeVerCampo(): boolean {
    return this.user.papel === 'dono' || this.user.papel === 'vaqueiro' || this.user.papel === 'consultor';
  }

  get podeVerFinanceiro(): boolean {
    return this.user.papel === 'dono' || this.user.papel === 'contador' || this.user.papel === 'consultor';
  }

  get podeGerirFazenda(): boolean {
    return this.user.papel === 'dono';
  }

  setPapelSimulado(papel: Papel) {
    this.user.papel = papel;
  }

  trocarFazenda(farmId: number) {
    const alvo = this.user.fazendas.find((f) => f.id === farmId);
    if (!alvo) return;
    this.user.farm_id = alvo.id;
    this.user.nome_fazenda = alvo.nome;
    this.user.papel = alvo.papel;
    this.user.fazendas = this.user.fazendas.map((f) => ({
      ...f,
      atual: f.id === farmId
    }));
  }
}

export const auth = new AuthStore();
