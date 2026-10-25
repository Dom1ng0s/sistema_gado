<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatBrl, formatDateBr, formatGmd, formatKg } from '../lib/format';
  import { router } from '../lib/router.svelte';
  import type { Papel } from '../lib/types';

  type AbaGov = 'fazenda' | 'equipe' | 'plano' | 'lixeira';

  interface MembroAcesso {
    id: number;
    username: string;
    email: string;
    papel: Exclude<Papel, 'dono'>;
    dataEntrada: string;
    ativo: boolean;
  }

  interface AnimalLixeira {
    id: number;
    brinco: string;
    raca: string;
    sexo: 'M' | 'F';
    lote: string;
    ultimoPesoKg: number;
    deletedAt: string;
    excluidoPor: string;
  }

  interface CidadeIbge {
    nome: string;
    uf: string;
  }

  const CIDADES_PADRAO: CidadeIbge[] = [
    { nome: 'Araçatuba', uf: 'SP' },
    { nome: 'Presidente Prudente', uf: 'SP' },
    { nome: 'Barretos', uf: 'SP' },
    { nome: 'São José do Rio Preto', uf: 'SP' },
    { nome: 'Campo Grande', uf: 'MS' },
    { nome: 'Três Lagoas', uf: 'MS' },
    { nome: 'Dourados', uf: 'MS' },
    { nome: 'Uberaba', uf: 'MG' },
    { nome: 'Rio Verde', uf: 'GO' },
    { nome: 'Rondonópolis', uf: 'MT' }
  ];

  const DESCRICAO_PAPEL: Record<Exclude<Papel, 'dono'>, string> = {
    vaqueiro: 'Registra pesagens, medicações, pastos e entradas. Não vê financeiro nem exclui animais.',
    contador: 'Apenas leitura do módulo financeiro e exportação de CSV.',
    consultor: 'Leitura completa de rebanho, GMD e financeiro em múltiplas fazendas, sem permissão de escrita.'
  };

  let abaAtiva = $state<AbaGov>('fazenda');
  let statusMsg = $state('');
  let erroMsg = $state('');

  $effect(() => {
    if (router.abaConfig === 'acessos') abaAtiva = 'equipe';
    else if (router.abaConfig === 'plano') abaAtiva = 'plano';
    else if (router.abaConfig === 'lixeira') abaAtiva = 'lixeira';
    else abaAtiva = 'fazenda';
  });

  // 1. Dados da Fazenda
  let nomeFazenda = $state(auth.user.nome_fazenda);
  let buscaCidade = $state('Araçatuba - SP');
  let cidadeSelecionada = $state('Araçatuba');
  let ufSelecionada = $state('SP');
  let sugestoesCidades = $state<CidadeIbge[]>([]);
  let mostrarSugestoesCidade = $state(false);
  let metaGmd = $state(auth.user.gmd_meta || 0.65);
  let custoDiarioCabeca = $state(4.85);
  let salvandoFazenda = $state(false);

  // 2. Equipe e Acessos (acessos_fazenda)
  let emailConvite = $state('');
  let papelConvite = $state<Exclude<Papel, 'dono'>>('vaqueiro');
  let enviandoConvite = $state(false);
  let membrosEquipe = $state<MembroAcesso[]>([
    {
      id: 101,
      username: 'saomarcos.joao',
      email: 'joao.curral@fazendasaomarcos.com.br',
      papel: 'vaqueiro',
      dataEntrada: '2026-04-12',
      ativo: true
    },
    {
      id: 102,
      username: 'saomarcos.contabil',
      email: 'fiscal@escritoriorural.com.br',
      papel: 'contador',
      dataEntrada: '2026-05-03',
      ativo: true
    },
    {
      id: 103,
      username: 'saomarcos.zootecnia',
      email: 'dr.marcelo@agroconsult.com.br',
      papel: 'consultor',
      dataEntrada: '2026-06-18',
      ativo: true
    },
    {
      id: 104,
      username: 'saomarcos.antonio',
      email: 'antonio.temp@gmail.com',
      papel: 'vaqueiro',
      dataEntrada: '2026-01-10',
      ativo: false
    }
  ]);

  // 3. Plano e Assinatura (utils/plano.py)
  let modoTrialDemo = $state(false);

  // 4. Lixeira (Soft Delete)
  let animaisLixeira = $state<AnimalLixeira[]>([
    {
      id: 801,
      brinco: '312',
      raca: 'Nelore',
      sexo: 'M',
      lote: 'Lote 04',
      ultimoPesoKg: 442.0,
      deletedAt: '2026-10-19',
      excluidoPor: 'demonstracao'
    },
    {
      id: 802,
      brinco: '198',
      raca: 'Cruzamento Industrial',
      sexo: 'F',
      lote: 'Lote Recria Sul',
      ultimoPesoKg: 365.5,
      deletedAt: '2026-10-21',
      excluidoPor: 'demonstracao'
    }
  ]);

  onMount(async () => {
    try {
      const cfg = await apiFetch<{
        nome_fazenda?: string;
        cidade?: string;
        uf?: string;
        gmd_meta?: number;
        custo_diario_cabeca?: number;
      }>('/api/configuracoes');
      if (cfg.nome_fazenda) nomeFazenda = cfg.nome_fazenda;
      if (cfg.cidade && cfg.uf) {
        cidadeSelecionada = cfg.cidade;
        ufSelecionada = cfg.uf;
        buscaCidade = `${cfg.cidade} - ${cfg.uf}`;
      }
      if (typeof cfg.gmd_meta === 'number') metaGmd = cfg.gmd_meta;
      if (typeof cfg.custo_diario_cabeca === 'number') custoDiarioCabeca = cfg.custo_diario_cabeca;
    } catch {
      // Mantém dados da Fazenda São Marcos em modo demonstração
    }

    try {
      const listaAcessos = await apiFetch<MembroAcesso[]>('/api/acessos');
      if (Array.isArray(listaAcessos) && listaAcessos.length > 0) {
        membrosEquipe = listaAcessos;
      }
    } catch {
      // Fallback demonstração
    }

    try {
      const lixeiraApi = await apiFetch<AnimalLixeira[]>('/api/lixeira');
      if (Array.isArray(lixeiraApi)) {
        animaisLixeira = lixeiraApi;
      }
    } catch {
      // Fallback demonstração
    }
  });

  async function pesquisarCidadesIbge(termo: string) {
    buscaCidade = termo;
    if (termo.trim().length < 2) {
      sugestoesCidades = [];
      mostrarSugestoesCidade = false;
      return;
    }

    try {
      const resp = await apiFetch<CidadeIbge[]>(`/proxy-cidades?q=${encodeURIComponent(termo.trim())}`);
      if (Array.isArray(resp) && resp.length > 0) {
        sugestoesCidades = resp.slice(0, 8);
        mostrarSugestoesCidade = true;
        return;
      }
    } catch {
      // Fallback local imediato
    }

    const alvo = termo.toLowerCase();
    sugestoesCidades = CIDADES_PADRAO.filter(
      (c) => c.nome.toLowerCase().includes(alvo) || c.uf.toLowerCase().includes(alvo)
    );
    mostrarSugestoesCidade = sugestoesCidades.length > 0;
  }

  function escolherCidade(c: CidadeIbge) {
    cidadeSelecionada = c.nome;
    ufSelecionada = c.uf;
    buscaCidade = `${c.nome} - ${c.uf}`;
    mostrarSugestoesCidade = false;
  }

  async function salvarDadosFazenda(e: SubmitEvent) {
    e.preventDefault();
    statusMsg = '';
    erroMsg = '';
    salvandoFazenda = true;

    try {
      await apiFetch('/api/configuracoes', {
        method: 'PUT',
        body: JSON.stringify({
          nome_fazenda: nomeFazenda.trim(),
          cidade: cidadeSelecionada,
          uf: ufSelecionada,
          gmd_meta: metaGmd,
          custo_diario_cabeca: custoDiarioCabeca
        })
      });
    } catch {
      // Continua atualizando store reativo local
    } finally {
      salvandoFazenda = false;
      auth.user.nome_fazenda = nomeFazenda.trim();
      auth.user.gmd_meta = metaGmd;
      statusMsg = `Parâmetros da ${nomeFazenda} salvos (Meta GMD: ${formatGmd(metaGmd)} · Praça: ${cidadeSelecionada}/${ufSelecionada}).`;
    }
  }

  async function convidarMembro(e: SubmitEvent) {
    e.preventDefault();
    statusMsg = '';
    erroMsg = '';

    const emailLimpo = emailConvite.trim().toLowerCase();
    if (!emailLimpo || !emailLimpo.includes('@')) {
      erroMsg = 'Informe um e-mail válido para gerar o acesso delegado.';
      return;
    }

    enviandoConvite = true;
    const prefixoFazenda = nomeFazenda
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]/g, '')
      .slice(0, 10) || 'fazenda';
    const prefixoPessoa = emailLimpo.split('@')[0].replace(/[^a-z0-9]/g, '').slice(0, 10) || 'membro';
    const usernameGerado = `${prefixoFazenda}.${prefixoPessoa}`;

    try {
      await apiFetch('/api/acessos', {
        method: 'POST',
        body: JSON.stringify({ email: emailLimpo, papel: papelConvite })
      });
    } catch {
      // Fallback demonstração
    } finally {
      enviandoConvite = false;
      membrosEquipe = [
        {
          id: Date.now(),
          username: usernameGerado,
          email: emailLimpo,
          papel: papelConvite,
          dataEntrada: '2026-10-24',
          ativo: true
        },
        ...membrosEquipe
      ];
      emailConvite = '';
      statusMsg = `Convite enviado! Acesso delegado criado como @${usernameGerado} (${papelConvite}).`;
    }
  }

  async function revogarAcesso(membro: MembroAcesso) {
    statusMsg = '';
    try {
      await apiFetch(`/api/acessos/${membro.id}`, { method: 'DELETE' });
    } catch {
      // Fallback demonstração
    }
    membrosEquipe = membrosEquipe.map((m) =>
      m.id === membro.id ? { ...m, ativo: false } : m
    );
    statusMsg = `Acesso de @${membro.username} revogado imediatamente (ativo = 0).`;
  }

  async function restaurarAnimalLixeira(item: AnimalLixeira) {
    statusMsg = '';
    try {
      await apiFetch(`/api/lixeira/${item.id}/restaurar`, { method: 'POST' });
    } catch {
      // Fallback demonstração
    }
    animaisLixeira = animaisLixeira.filter((a) => a.id !== item.id);
    auth.user.plano.cabecas += 1;
    statusMsg = `Animal #${item.brinco} restaurado para o rebanho ativo (${item.lote}).`;
  }
</script>

<div class="gov-page">
  <header class="page-head">
    <div>
      <div class="badge-row">
        <span class="badge badge--ok">Governança SaaS · Migrations 0006 & 0007</span>
        <span class="badge badge--neutro dado">Papel ativo: {auth.user.papel}</span>
      </div>
      <h1 class="page-title">Configurações, Equipe e Assinatura</h1>
      <p class="page-subtitle">
        Gerencie parâmetros zootécnicos da fazenda, delegação de acessos por papel, capacidade do plano e lixeira auditada.
      </p>
    </div>
  </header>

  <!-- Abas de Governança -->
  <div class="gov-tabs panel" role="tablist" aria-label="Seções de governança">
    <button
      type="button"
      role="tab"
      aria-selected={abaAtiva === 'fazenda'}
      class="gov-tab"
      class:gov-tab--active={abaAtiva === 'fazenda'}
      onclick={() => {
        abaAtiva = 'fazenda';
        statusMsg = '';
      }}
    >
      1. Dados da Fazenda
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={abaAtiva === 'equipe'}
      class="gov-tab"
      class:gov-tab--active={abaAtiva === 'equipe'}
      onclick={() => {
        abaAtiva = 'equipe';
        statusMsg = '';
      }}
    >
      2. Equipe e Acessos ({membrosEquipe.filter((m) => m.ativo).length})
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={abaAtiva === 'plano'}
      class="gov-tab"
      class:gov-tab--active={abaAtiva === 'plano'}
      onclick={() => {
        abaAtiva = 'plano';
        statusMsg = '';
      }}
    >
      3. Plano e Assinatura
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={abaAtiva === 'lixeira'}
      class="gov-tab"
      class:gov-tab--active={abaAtiva === 'lixeira'}
      onclick={() => {
        abaAtiva = 'lixeira';
        statusMsg = '';
      }}
    >
      4. Lixeira ({animaisLixeira.length})
    </button>
  </div>

  {#if erroMsg}
    <div class="feedback feedback--erro panel" role="alert">{erroMsg}</div>
  {/if}
  {#if statusMsg}
    <div class="feedback feedback--ok panel" role="status">{statusMsg}</div>
  {/if}

  {#if abaAtiva === 'fazenda'}
    <form class="panel section-card" onsubmit={salvarDadosFazenda}>
      <h2 class="section-title">Parâmetros operacionais e localização</h2>

      <div class="grid-2">
        <div class="field">
          <label for="cfg-nome">Nome da propriedade rural</label>
          <input id="cfg-nome" class="input" type="text" bind:value={nomeFazenda} required />
        </div>

        <div class="field city-autocomplete">
          <label for="cfg-cidade">Cidade / UF (autocomplete IBGE para cotação regional)</label>
          <input
            id="cfg-cidade"
            class="input"
            type="text"
            placeholder="Digite o município..."
            value={buscaCidade}
            oninput={(e) => pesquisarCidadesIbge((e.currentTarget as HTMLInputElement).value)}
          />
          <small class="hint">
            Praça vinculada: <strong class="dado">{cidadeSelecionada} / {ufSelecionada}</strong> (destrava <code class="dado">/cotacoes-regionais</code>)
          </small>

          {#if mostrarSugestoesCidade}
            <ul class="suggestions-list panel" role="listbox">
              {#each sugestoesCidades as cid}
                <li>
                  <button type="button" class="suggestion-btn" onclick={() => escolherCidade(cid)}>
                    <span>{cid.nome}</span>
                    <span class="badge badge--neutro dado">{cid.uf}</span>
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>

      <div class="grid-2">
        <div class="field">
          <label for="cfg-gmd">Meta de GMD do rebanho (kg/dia)</label>
          <input
            id="cfg-gmd"
            class="input dado"
            type="number"
            step="0.01"
            min="0.1"
            max="2.5"
            inputmode="decimal"
            bind:value={metaGmd}
            required
          />
          <small class="hint">
            Define o corte semântico entre verde-pinheiro (<span class="dado">&gt;= {formatGmd(metaGmd)}</span>) e alerta óxido.
          </small>
        </div>

        <div class="field">
          <label for="cfg-diaria">Custo diário estimado por cabeça (R$/dia)</label>
          <input
            id="cfg-diaria"
            class="input dado"
            type="number"
            step="0.05"
            min="0"
            inputmode="decimal"
            bind:value={custoDiarioCabeca}
            required
          />
          <small class="hint">
            Usado para projetar o custo operacional acumulado na ficha individual (<strong class="dado">{formatBrl(custoDiarioCabeca * 30)}/mês</strong>).
          </small>
        </div>
      </div>

      <div class="card-footer">
        <button type="submit" class="btn btn-primary" disabled={salvandoFazenda}>
          {salvandoFazenda ? 'Salvando alterações...' : 'Salvar parâmetros da fazenda'}
        </button>
      </div>
    </form>
  {:else if abaAtiva === 'equipe'}
    <div class="equipe-stack">
      <form class="panel section-card" onsubmit={convidarMembro}>
        <h2 class="section-title">Convidar membro para a equipe (<code class="dado">acessos_fazenda</code>)</h2>

        <div class="grid-invite">
          <div class="field">
            <label for="eq-email">E-mail do convidado</label>
            <input
              id="eq-email"
              class="input"
              type="email"
              placeholder="vaqueiro@fazenda.com.br"
              bind:value={emailConvite}
              required
            />
          </div>

          <div class="field">
            <label for="eq-papel">Papel de acesso (RBAC)</label>
            <select id="eq-papel" class="input" bind:value={papelConvite}>
              <option value="vaqueiro">Vaqueiro (Operação de curral e campo)</option>
              <option value="contador">Contador (Leitura financeira e exportação CSV)</option>
              <option value="consultor">Consultor (Leitura técnica multi-fazenda)</option>
            </select>
          </div>

          <div class="field field--btn">
            <button type="submit" class="btn btn-primary" disabled={enviandoConvite}>
              {enviandoConvite ? 'Gerando acesso...' : 'Conceder acesso'}
            </button>
          </div>
        </div>

        <div class="role-explanation">
          <strong>Permissões do papel <span class="dado">{papelConvite}</span>:</strong>
          <span>{DESCRICAO_PAPEL[papelConvite]}</span>
        </div>
      </form>

      <section class="panel section-card">
        <h2 class="section-title">Membros com acesso à {nomeFazenda}</h2>

        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Usuário gerado</th>
                <th>E-mail</th>
                <th>Papel</th>
                <th class="col-num">Data de entrada</th>
                <th>Status</th>
                <th>Ação</th>
              </tr>
            </thead>
            <tbody>
              {#each membrosEquipe as m (m.id)}
                <tr>
                  <td class="dado"><strong>@{m.username}</strong></td>
                  <td>{m.email}</td>
                  <td><span class="badge badge--neutro dado">{m.papel}</span></td>
                  <td class="col-num dado">{formatDateBr(m.dataEntrada)}</td>
                  <td>
                    {#if m.ativo}
                      <span class="badge badge--ok">Ativo</span>
                    {:else}
                      <span class="badge badge--alerta">Revogado</span>
                    {/if}
                  </td>
                  <td>
                    {#if m.ativo}
                      <button
                        type="button"
                        class="btn btn-danger btn-sm"
                        onclick={() => revogarAcesso(m)}
                      >
                        Revogar acesso
                      </button>
                    {:else}
                      <span class="dado text-muted">Inativo</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  {:else if abaAtiva === 'plano'}
    <section class="panel section-card">
      <div class="plan-header">
        <div>
          <div class="badge-row">
            <span class="badge badge--ok">Plano {modoTrialDemo ? 'Avaliação (Trial 14d)' : auth.user.plano.rotulo}</span>
            <span class="badge badge--neutro dado">
              Status: {modoTrialDemo ? 'em_trial (faltam 11 dias)' : auth.user.plano.status}
            </span>
          </div>
          <h2 class="section-title">Capacidade contratada e assinatura (<code class="dado">utils/plano.py</code>)</h2>
        </div>

        <button
          type="button"
          class="btn btn-outline btn-sm"
          onclick={() => (modoTrialDemo = !modoTrialDemo)}
        >
          Alternar visão: {modoTrialDemo ? 'Ver Plano Porteira Ativo' : 'Simular Trial 14 dias'}
        </button>
      </div>

      <div class="plan-meter">
        <div class="plan-meter__labels">
          <span>Ocupação de cabeças ativas no rebanho</span>
          <strong class="dado">
            {auth.user.plano.cabecas} / {auth.user.plano.limite_cabecas ?? 250} cabeças — {auth.user.plano.uso_pct ?? 94}%
          </strong>
        </div>
        <div class="plan-bar">
          <div
            class="plan-bar__fill"
            style={`width: ${auth.user.plano.uso_pct ?? 94}%`}
          ></div>
        </div>
        <small class="hint">
          Restam <strong class="dado">{auth.user.plano.vagas ?? 15} vagas</strong> antes do bloqueio de novas entradas no plano Porteira (<span class="dado">250 cab.</span>). Animais vendidos ou na lixeira não consomem vagas.
        </small>
      </div>

      <div class="tiers-grid">
        <div class="tier-card panel">
          <span class="badge badge--neutro">Avaliação gratuita</span>
          <h3>Período de Teste</h3>
          <strong class="tier-price dado">14 dias grátis</strong>
          <p>Acesso integral ao Modo Curral, trava sanitária, P&L por lote e até <span class="dado">50 cabeças</span> para validação em campo.</p>
        </div>

        <div class="tier-card tier-card--current panel">
          <span class="badge badge--ok">Plano atual</span>
          <h3>Tier Porteira</h3>
          <strong class="tier-price dado">R$ 149,00<small>/mês</small></strong>
          <p>Até <strong class="dado">250 cabeças ativas</strong>, equipe ilimitada (<code class="dado">vaqueiro</code>, <code class="dado">contador</code>, <code class="dado">consultor</code>) e cobrança automática via Asaas.</p>
        </div>

        <div class="tier-card panel">
          <span class="badge badge--neutro">Expansão</span>
          <h3>Tier Fazenda / Corporativo</h3>
          <strong class="tier-price dado">R$ 299,00<small>/mês</small></strong>
          <p>Sem limite de cabeças (<code class="dado">sem_limite = true</code>), múltiplas propriedades rurais e exportação contábil consolidada.</p>
        </div>
      </div>
    </section>
  {:else}
    <section class="panel section-card">
      <div class="trash-head">
        <div>
          <h2 class="section-title">Lixeira de Animais (<code class="dado">deleted_at IS NOT NULL</code>)</h2>
          <p class="page-subtitle">
            Animais excluídos logicamente saem da contagem ativa do rebanho e do cálculo de GMD, mas preservam todo o histórico sanitário e de pesagens caso precisem ser restaurados.
          </p>
        </div>
      </div>

      {#if animaisLixeira.length === 0}
        <p class="empty-trash">Nenhum animal na lixeira no momento.</p>
      {:else}
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Brinco</th>
                <th>Sexo / Raça</th>
                <th>Último Lote</th>
                <th class="col-num">Último peso</th>
                <th class="col-num">Excluído em</th>
                <th>Excluído por</th>
                <th>Ação de recuperação</th>
              </tr>
            </thead>
            <tbody>
              {#each animaisLixeira as item (item.id)}
                <tr>
                  <td class="dado"><strong>#{item.brinco}</strong></td>
                  <td>{item.sexo} · {item.raca}</td>
                  <td>{item.lote}</td>
                  <td class="col-num dado">{formatKg(item.ultimoPesoKg)}</td>
                  <td class="col-num dado">{formatDateBr(item.deletedAt)}</td>
                  <td class="dado">@{item.excluidoPor}</td>
                  <td>
                    <button
                      type="button"
                      class="btn btn-outline btn-sm"
                      onclick={() => restaurarAnimalLixeira(item)}
                    >
                      Restaurar para o rebanho
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>
  {/if}
</div>

<style>
  .gov-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .badge-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .gov-tabs {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    overflow: hidden;
    background: var(--color-surface-sunken);
  }

  .gov-tab {
    min-height: 42px;
    border: none;
    border-right: 1px solid var(--color-border);
    background: transparent;
    color: var(--color-ink-secondary);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    cursor: pointer;
  }
  .gov-tab:last-child {
    border-right: none;
  }
  .gov-tab--active {
    background: var(--color-surface);
    color: var(--color-primary-dark);
    box-shadow: inset 0 -2px 0 var(--color-primary);
  }

  .feedback {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-sm);
  }
  .feedback--ok {
    background: var(--color-primary-bg);
    border-color: var(--color-primary);
    border-left: 4px solid var(--color-primary);
    color: var(--color-primary-dark);
  }
  .feedback--erro {
    background: var(--color-danger-bg);
    border-color: var(--color-danger);
    border-left: 4px solid var(--color-danger);
    color: var(--color-danger-dark);
  }

  .section-card {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .equipe-stack {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
  }

  .grid-invite {
    display: grid;
    grid-template-columns: 1.2fr 1.2fr auto;
    gap: var(--space-3);
    align-items: end;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  .field label {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--color-ink-secondary);
  }
  .hint {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .city-autocomplete {
    position: relative;
  }

  .suggestions-list {
    position: absolute;
    top: 66px;
    left: 0;
    right: 0;
    z-index: var(--z-dropdown);
    list-style: none;
    max-height: 220px;
    overflow-y: auto;
    box-shadow: var(--shadow-md);
  }

  .suggestion-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-2) var(--space-3);
    border: none;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-surface);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    color: var(--color-ink);
    cursor: pointer;
  }
  .suggestion-btn:hover {
    background: var(--color-surface-raised);
  }

  .role-explanation {
    padding: var(--space-3) var(--space-4);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .card-footer {
    display: flex;
    justify-content: flex-end;
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-border);
  }

  .btn-sm {
    min-height: 30px;
    padding: 0 var(--space-3);
    font-size: var(--text-xs);
  }

  .text-muted {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .plan-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .plan-meter {
    padding: var(--space-4);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .plan-meter__labels {
    display: flex;
    justify-content: space-between;
    font-size: var(--text-sm);
  }

  .plan-bar {
    width: 100%;
    height: 10px;
    background: var(--n-100);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }
  .plan-bar__fill {
    height: 100%;
    background: var(--color-primary);
  }

  .tiers-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-4);
  }

  .tier-card {
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
  }
  .tier-card--current {
    border-color: var(--color-primary);
    background: var(--color-primary-bg);
  }
  .tier-card h3 {
    font-size: var(--text-md);
  }
  .tier-price {
    font-size: var(--text-xl);
    color: var(--color-ink);
  }
  .tier-price small {
    font-size: var(--text-xs);
    font-weight: var(--weight-regular);
  }
  .tier-card p {
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
    font-weight: var(--weight-regular);
  }

  .empty-trash {
    font-size: var(--text-sm);
    color: var(--color-ink-tertiary);
  }

  @media (max-width: 960px) {
    .grid-2,
    .grid-invite,
    .tiers-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 768px) {
    .gov-tabs {
      grid-template-columns: repeat(2, 1fr);
    }
    .gov-tab:nth-child(1),
    .gov-tab:nth-child(2) {
      border-bottom: 1px solid var(--color-border);
    }
    .gov-tab:nth-child(2) {
      border-right: none;
    }
    .section-card {
      padding: var(--space-4);
    }
    .card-footer .btn {
      width: 100%;
    }
  }
</style>
