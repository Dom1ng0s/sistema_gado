export type Papel = 'dono' | 'vaqueiro' | 'contador' | 'consultor';

export interface FazendaAcesso {
  id: number;
  nome: string;
  papel: Papel;
  atual: boolean;
}

export interface PlanoResumo {
  tier: string;
  rotulo: string;
  status: string;
  em_trial: boolean;
  dias_restantes: number | null;
  expirado: boolean;
  limite_cabecas: number | null;
  sem_limite: boolean;
  cabecas: number;
  vagas: number | null;
  estourado: boolean;
  uso_pct: number | null;
}

export interface UsuarioSessao {
  id: number;
  username: string;
  email: string | null;
  farm_id: number;
  nome_fazenda: string;
  gmd_meta: number;
  papel: Papel;
  fazendas: FazendaAcesso[];
  plano: PlanoResumo;
}

export interface AlertaGmdItem {
  id: number;
  brinco: string;
  gmd_atual: number;
}

export interface DashboardSummary {
  sexo: { M?: number; F?: number };
  gmd: { gmd_medio: number };
  alertas: {
    gmd_media_rebanho: number;
    gmd_limite_inferior: number | null;
    total: number;
    animais: AlertaGmdItem[];
  };
}

export interface CotacaoPraca {
  praca: string;
  valor?: string | number;
  avista?: string | number;
  prazo?: string | number;
}

export interface CotacoesRegionaisResponse {
  uf: string;
  boi: CotacaoPraca[];
  novilha: CotacaoPraca[];
}
