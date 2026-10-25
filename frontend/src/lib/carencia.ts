/**
 * Espelho de utils/carencia.py para pré-preenchimento instantâneo (0ms) no curral.
 * A validação e bloqueio final continuam no PostgreSQL (vw_animais_em_carencia).
 */
export const CARENCIA_PADRAO: Record<string, number> = {
  ivermectina: 35,
  doramectina: 42,
  abamectina: 35,
  moxidectina: 23,
  closantel: 42,
  levamisol: 14,
  albendazol: 14,
  oxitetraciclina: 28,
  tetraciclina: 28,
  enrofloxacina: 28,
  florfenicol: 30,
  penicilina: 30,
  tulatromicina: 44,
  cipermetrina: 5,
  fluazuron: 42,
  diminazeno: 21,
  dipirona: 3,
  flunixina: 8
};

function normalizar(texto: string): string {
  return (texto || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export function diasCarenciaSugerido(nomeMedicamento: string): number {
  const alvo = normalizar(nomeMedicamento);
  if (!alvo) return 0;
  let maior = 0;
  for (const [chave, dias] of Object.entries(CARENCIA_PADRAO)) {
    if (alvo.includes(normalizar(chave)) && dias > maior) {
      maior = dias;
    }
  }
  return maior;
}

export function calcularDataLiberacao(dataAplicacaoIso: string, diasCarencia: number): string | null {
  if (!dataAplicacaoIso || diasCarencia <= 0) return null;
  const d = new Date(`${dataAplicacaoIso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  d.setUTCDate(d.getUTCDate() + diasCarencia);
  return d.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
}
