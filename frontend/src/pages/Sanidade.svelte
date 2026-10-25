<script lang="ts">
  /**
   * Trilha 5 / MT-5.3 — Protocolos sanitários recorrentes (protocolos_sanitarios).
   * Lista em formato de calendário com destaque em óxido para aplicações vencidas
   * ou vencendo em 7 dias, e ação de registrar aplicação.
   */
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatDateBr } from '../lib/format';

  interface Protocolo {
    id: number;
    nome: string;
    produto: string;
    alvo: string;
    periodicidade_dias: number;
    dias_carencia: number;
    ultima_aplicacao: string | null;
    proxima_aplicacao: string;
    cabecas_previstas: number;
    registrado_por: string;
  }

  interface Carencia {
    brinco: string;
    produto: string;
    data_aplicacao: string;
    data_liberacao: string;
    dias_restantes: number;
  }

  const HOJE = new Date('2026-10-24T00:00:00Z');

  /** Calendário sanitário da Fazenda São Marcos. */
  const PROTOCOLOS_DEMO: Protocolo[] = [
    { id: 1, nome: 'Aftosa — 2ª etapa', produto: 'Vacina bivalente contra aftosa', alvo: 'Rebanho inteiro', periodicidade_dias: 182, dias_carencia: 0, ultima_aplicacao: '2026-04-28', proxima_aplicacao: '2026-10-28', cabecas_previstas: 235, registrado_por: 'joao.vaqueiro' },
    { id: 2, nome: 'Vermifugação estratégica', produto: 'Albendazol 10%', alvo: 'Bezerros e garrotes', periodicidade_dias: 120, dias_carencia: 14, ultima_aplicacao: '2026-06-18', proxima_aplicacao: '2026-10-16', cabecas_previstas: 96, registrado_por: 'joao.vaqueiro' },
    { id: 3, nome: 'Controle de mosca-do-chifre', produto: 'Cipermetrina pour-on', alvo: 'Lotes 2026-A e 2026-B', periodicidade_dias: 45, dias_carencia: 5, ultima_aplicacao: '2026-09-18', proxima_aplicacao: '2026-11-02', cabecas_previstas: 80, registrado_por: 'davi.dono' },
    { id: 4, nome: 'Brucelose — fêmeas de reposição', produto: 'Vacina B19', alvo: 'Fêmeas de 3 a 8 meses', periodicidade_dias: 365, dias_carencia: 0, ultima_aplicacao: '2026-02-10', proxima_aplicacao: '2027-02-10', cabecas_previstas: 18, registrado_por: 'davi.dono' },
    { id: 5, nome: 'Clostridiose (carbúnculo)', produto: 'Vacina polivalente', alvo: 'Bezerros desmamados', periodicidade_dias: 365, dias_carencia: 0, ultima_aplicacao: null, proxima_aplicacao: '2026-10-30', cabecas_previstas: 24, registrado_por: 'joao.vaqueiro' },
    { id: 6, nome: 'Controle de carrapato', produto: 'Fluazuron', alvo: 'Lote 2025-C', periodicidade_dias: 70, dias_carencia: 42, ultima_aplicacao: '2026-08-30', proxima_aplicacao: '2026-11-08', cabecas_previstas: 36, registrado_por: 'joao.vaqueiro' }
  ];

  const CARENCIAS_DEMO: Carencia[] = [
    { brinco: '0402', produto: 'Ivermectina 1%', data_aplicacao: '2026-10-10', data_liberacao: '2026-11-14', dias_restantes: 21 },
    { brinco: '0317', produto: 'Cipermetrina', data_aplicacao: '2026-10-19', data_liberacao: '2026-11-02', dias_restantes: 9 },
    { brinco: '0409', produto: 'Fluazuron', data_aplicacao: '2026-10-02', data_liberacao: '2026-11-13', dias_restantes: 20 },
    { brinco: '0607', produto: 'Fluazuron', data_aplicacao: '2026-10-02', data_liberacao: '2026-11-13', dias_restantes: 20 }
  ];

  let protocolos = $state<Protocolo[]>(PROTOCOLOS_DEMO);
  let carencias = $state<Carencia[]>(CARENCIAS_DEMO);
  let apiConectada = $state(false);
  let carregando = $state(true);

  onMount(async () => {
    try {
      const [lista, bloqueios] = await Promise.all([
        apiFetch<Protocolo[] | { protocolos: Protocolo[] }>('/api/sanitario/protocolos').catch(() => null),
        apiFetch<Carencia[] | { carencias: Carencia[] }>('/api/sanitario/carencias').catch(() => null)
      ]);

      const protos = Array.isArray(lista) ? lista : lista?.protocolos;
      if (protos?.length) {
        protocolos = protos;
        apiConectada = true;
      }
      const cars = Array.isArray(bloqueios) ? bloqueios : bloqueios?.carencias;
      if (cars) carencias = cars;
    } catch {
      // Calendário segue navegável com o protocolo de demonstração.
      apiConectada = false;
    } finally {
      carregando = false;
    }
  });

  function diasPara(iso: string): number {
    const d = new Date(`${iso}T00:00:00Z`);
    return Math.round((d.getTime() - HOJE.getTime()) / 86400000);
  }

  type Estado = 'vencido' | 'vencendo' | 'em_dia';

  function estadoDe(p: Protocolo): Estado {
    const dias = diasPara(p.proxima_aplicacao);
    if (dias < 0) return 'vencido';
    if (dias <= 7) return 'vencendo';
    return 'em_dia';
  }

  function mesRotulo(iso: string): string {
    const d = new Date(`${iso}T00:00:00Z`);
    return d.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  }

  let ordenados = $derived(
    [...protocolos].sort((a, b) => a.proxima_aplicacao.localeCompare(b.proxima_aplicacao))
  );
  let vencidos = $derived(ordenados.filter((p) => estadoDe(p) === 'vencido'));
  let vencendo = $derived(ordenados.filter((p) => estadoDe(p) === 'vencendo'));
  let cabecasEmRisco = $derived(
    [...vencidos, ...vencendo].reduce((s, p) => s + p.cabecas_previstas, 0)
  );

  // Agrupa o calendário por mês de aplicação prevista.
  let porMes = $derived.by(() => {
    const mapa = new Map<string, Protocolo[]>();
    for (const p of ordenados) {
      const chave = p.proxima_aplicacao.slice(0, 7);
      const atual = mapa.get(chave) ?? [];
      atual.push(p);
      mapa.set(chave, atual);
    }
    return Array.from(mapa.entries()).map(([chave, itens]) => ({
      chave,
      rotulo: mesRotulo(`${chave}-01`),
      itens
    }));
  });

  async function registrarAplicacao(p: Protocolo) {
    const hojeIso = HOJE.toISOString().slice(0, 10);
    try {
      await apiFetch('/api/sanitario/protocolos', {
        method: 'POST',
        body: JSON.stringify({ protocolo_id: p.id, data_aplicacao: hojeIso })
      });
      const lista = await apiFetch<Protocolo[] | { protocolos: Protocolo[] }>('/api/sanitario/protocolos');
      const protos = Array.isArray(lista) ? lista : lista.protocolos;
      if (protos?.length) protocolos = protos;
    } catch {
      // Demonstração: a aplicação de hoje reagenda a próxima pela periodicidade do protocolo.
      const proxima = new Date(HOJE);
      proxima.setUTCDate(proxima.getUTCDate() + p.periodicidade_dias);
      protocolos = protocolos.map((item) =>
        item.id === p.id
          ? {
              ...item,
              ultima_aplicacao: hojeIso,
              proxima_aplicacao: proxima.toISOString().slice(0, 10),
              registrado_por: auth.user.username
            }
          : item
      );
    }
  }
</script>

<div class="sanidade">
  <header class="sanidade__header">
    <div>
      <h1 class="page-title">Sanidade</h1>
      <p class="page-subtitle">
        Calendário de protocolos recorrentes e carências ativas de {auth.user.nome_fazenda}
        {#if !apiConectada && !carregando}
          <span class="badge badge--neutro">Modo demonstração (Fazenda São Marcos)</span>
        {/if}
      </p>
    </div>
  </header>

  <section class="indicadores panel" aria-label="Situação sanitária">
    <div class="indicador">
      <span class="indicador__label">Protocolos vencidos</span>
      <strong class="indicador__value dado" class:dado--alerta={vencidos.length > 0} class:dado--ok={vencidos.length === 0}>
        {vencidos.length}
      </strong>
      <span class="indicador__meta">Já passaram da data prevista</span>
    </div>
    <div class="indicador">
      <span class="indicador__label">Vencendo em 7 dias</span>
      <strong class="indicador__value dado" class:dado--alerta={vencendo.length > 0}>{vencendo.length}</strong>
      <span class="indicador__meta">Precisam de compra e curral</span>
    </div>
    <div class="indicador">
      <span class="indicador__label">Cabeças a manejar</span>
      <strong class="indicador__value dado">{cabecasEmRisco} cab.</strong>
      <span class="indicador__meta">Somando os protocolos em atraso ou na janela</span>
    </div>
    <div class="indicador">
      <span class="indicador__label">Animais em carência</span>
      <strong class="indicador__value dado" class:dado--alerta={carencias.length > 0}>{carencias.length}</strong>
      <span class="indicador__meta">Bloqueados para abate</span>
    </div>
  </section>

  <section class="calendario">
    <h2 class="section-title">Calendário de protocolos</h2>

    {#each porMes as grupo (grupo.chave)}
      <div class="mes">
        <h3 class="mes__titulo">{grupo.rotulo}</h3>
        <div class="mes__itens">
          {#each grupo.itens as p (p.id)}
            {@const estado = estadoDe(p)}
            {@const dias = diasPara(p.proxima_aplicacao)}
            <article class="protocolo panel" class:protocolo--alerta={estado !== 'em_dia'}>
              <div class="protocolo__data">
                <strong class="dado">{formatDateBr(p.proxima_aplicacao)}</strong>
                {#if estado === 'vencido'}
                  <span class="badge badge--alerta">Vencido há <span class="dado">{Math.abs(dias)}d</span></span>
                {:else if estado === 'vencendo'}
                  <span class="badge badge--alerta">Vence em <span class="dado">{dias}d</span></span>
                {:else}
                  <span class="badge badge--ok">Em <span class="dado">{dias}d</span></span>
                {/if}
              </div>

              <div class="protocolo__corpo">
                <h4 class="protocolo__nome">{p.nome}</h4>
                <p class="protocolo__produto">{p.produto} · {p.alvo}</p>
                <dl class="protocolo__dados">
                  <div>
                    <dt>Cabeças previstas</dt>
                    <dd class="dado">{p.cabecas_previstas} cab.</dd>
                  </div>
                  <div>
                    <dt>Periodicidade</dt>
                    <dd class="dado">{p.periodicidade_dias} d</dd>
                  </div>
                  <div>
                    <dt>Carência do produto</dt>
                    <dd class="dado" class:dado--alerta={p.dias_carencia > 0}>
                      {p.dias_carencia > 0 ? `${p.dias_carencia} d` : 'sem carência'}
                    </dd>
                  </div>
                  <div>
                    <dt>Última aplicação</dt>
                    <dd>
                      {#if p.ultima_aplicacao}
                        <span class="dado">{formatDateBr(p.ultima_aplicacao)}</span>
                      {:else}
                        <span class="sem-dado">Nunca aplicado</span>
                      {/if}
                    </dd>
                  </div>
                </dl>
              </div>

              <div class="protocolo__rodape">
                <small class="autor">Último registro por <span class="dado">{p.registrado_por}</span></small>
                {#if auth.podeEscreverNoCampo}
                  <button
                    type="button"
                    class="btn"
                    class:btn-primary={estado !== 'em_dia'}
                    class:btn-outline={estado === 'em_dia'}
                    onclick={() => registrarAplicacao(p)}
                  >
                    Registrar aplicação
                  </button>
                {/if}
              </div>
            </article>
          {/each}
        </div>
      </div>
    {/each}
  </section>

  <section class="carencias">
    <h2 class="section-title">Carências ativas (abate bloqueado)</h2>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Brinco</th>
            <th>Produto aplicado</th>
            <th>Data da aplicação</th>
            <th>Liberação para abate</th>
            <th class="col-num">Dias restantes</th>
          </tr>
        </thead>
        <tbody>
          {#each carencias as c (c.brinco + c.produto)}
            <tr class="linha-alerta">
              <td><span class="dado brinco">#{c.brinco}</span></td>
              <td>{c.produto}</td>
              <td><span class="dado">{formatDateBr(c.data_aplicacao)}</span></td>
              <td><span class="dado dado--alerta">{formatDateBr(c.data_liberacao)}</span></td>
              <td class="col-num"><span class="dado dado--alerta">{c.dias_restantes} d</span></td>
            </tr>
          {:else}
            <tr>
              <td colspan="5" class="vazio">Nenhum animal em carência — rebanho inteiro liberado para venda.</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
</div>

<style>
  .sanidade {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .sanidade__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .indicadores {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
  }

  .indicador {
    padding: var(--space-4) var(--space-5);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .indicador:last-child {
    border-right: none;
  }

  .indicador__label {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .indicador__value {
    font-size: var(--text-3xl);
    line-height: var(--leading-tight);
    white-space: nowrap;
    letter-spacing: var(--tracking-display);
  }

  .indicador__meta {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .calendario {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .mes {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .mes__titulo {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--color-ink-tertiary);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--color-border);
    text-transform: none;
  }

  .mes__itens {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
    gap: var(--space-4);
  }

  .protocolo {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4) var(--space-5);
  }

  .protocolo--alerta {
    border-left: 3px solid var(--color-danger);
  }

  .protocolo__data {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .protocolo__data strong {
    font-size: var(--text-lg);
  }

  .protocolo__nome {
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
  }

  .protocolo__produto {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .protocolo__dados {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
    margin-top: var(--space-3);
  }
  .protocolo__dados dt {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }
  .protocolo__dados dd {
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
  }

  .protocolo__rodape {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .autor {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .carencias {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .brinco {
    font-weight: var(--weight-semibold);
  }

  .linha-alerta {
    background: var(--color-danger-bg);
  }

  .sem-dado {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  .vazio {
    padding: var(--space-6);
    text-align: center;
    color: var(--color-ink-tertiary);
  }

  @media (max-width: 1024px) {
    .indicadores {
      grid-template-columns: repeat(2, 1fr);
    }
    .indicador:nth-child(2) {
      border-right: none;
    }
  }

  @media (max-width: 768px) {
    .indicadores {
      grid-template-columns: 1fr;
    }
    .indicador {
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }
  }
</style>
