export const KG_POR_ARROBA = 30;

const brlFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});

export function formatBrl(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—';
  return brlFormatter.format(valor);
}

export function formatKg(pesoKg: number | null | undefined): string {
  if (pesoKg === null || pesoKg === undefined || Number.isNaN(pesoKg)) return '—';
  return `${pesoKg.toFixed(1).replace('.', ',')} kg`;
}

export function formatArroba(pesoKg: number | null | undefined): string {
  if (pesoKg === null || pesoKg === undefined || Number.isNaN(pesoKg)) return '—';
  const arrobas = pesoKg / KG_POR_ARROBA;
  return `${arrobas.toFixed(1).replace('.', ',')} @`;
}

export function formatGmd(gmd: number | null | undefined): string {
  if (gmd === null || gmd === undefined || Number.isNaN(gmd)) return '—';
  return `${gmd.toFixed(3).replace('.', ',')} kg/d`;
}

export function formatDateBr(isoOrBr: string | null | undefined): string {
  if (!isoOrBr) return '—';
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(isoOrBr)) return isoOrBr;
  const d = new Date(isoOrBr);
  if (Number.isNaN(d.getTime())) return isoOrBr;
  return d.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
}
