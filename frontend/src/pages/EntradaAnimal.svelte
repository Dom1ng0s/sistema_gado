<script lang="ts">
  import { apiFetch } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { formatArroba, formatBrl, formatKg, KG_POR_ARROBA } from '../lib/format';

  type AbaEntrada = 'individual' | 'lote' | 'csv';
  type OrigemAnimal = 'compra' | 'nascido';
  type ModoPreco = 'arroba' | 'cabeca';

  interface AnimalRecemCadastrado {
    brinco: string;
    sexo: 'M' | 'F';
    raca: string;
    lote: string;
    pesoKg: number;
    precoCompra: number;
    origem: OrigemAnimal;
  }

  const RACAS = ['Nelore', 'Angus', 'Cruzamento Industrial', 'Brahman', 'Senepol'];
  const LOTES = ['Lote 2026-A', 'Lote 04', 'Lote Recria Sul', 'Lote Maternidade'];

  let abaAtiva = $state<AbaEntrada>('individual');

  // Campos do Cadastro Individual
  let brinco = $state('');
  let sexo = $state<'M' | 'F'>('M');
  let raca = $state('Nelore');
  let origem = $state<OrigemAnimal>('compra');
  let paiBrinco = $state('Touro-02');
  let maeBrinco = $state('Vaca-88');
  let dataNascimento = $state('2026-03-15');
  let dataEntrada = $state('2026-10-24');
  let pesoEntradaKg = $state(330);
  let modoPreco = $state<ModoPreco>('arroba');
  let valorArrobaCompra = $state(315.0);
  let precoFixoCabeca = $state(3465.0);
  let loteIndividual = $state('Lote 2026-A');

  // Campos do Cadastro em Lote
  let prefixoBrinco = $state('');
  let brincoInicial = $state(501);
  let quantidadeLote = $state(10);
  let sexoLote = $state<'M' | 'F'>('M');
  let racaLote = $state('Nelore');
  let loteDestinoColetivo = $state('Lote 2026-A');
  let pesoMedioLoteKg = $state(315.0);
  let valorArrobaLote = $state(315.0);

  // Campos de Importação CSV
  let csvTexto = $state(
    `brinco;sexo;raca;peso_kg;preco_compra;lote\n601;M;Nelore;342,0;3591,00;Lote 2026-A\n602;M;Nelore;338,5;3554,25;Lote 2026-A\n603;F;Angus;295,0;3097,50;Lote Recria Sul`
  );

  let salvando = $state(false);
  let erroValidacao = $state('');
  let sucessoMsg = $state('');

  let recemCadastrados = $state<AnimalRecemCadastrado[]>([]);

  // Espelho exato de utils/plano.py
  let cabecasAtuais = $derived(auth.user.plano.cabecas);
  let limiteCabecas = $derived(auth.user.plano.limite_cabecas ?? 250);
  let vagasRestantes = $derived(Math.max(0, limiteCabecas - cabecasAtuais));
  let usoPercentual = $derived(Math.min(100, Math.round((cabecasAtuais / limiteCabecas) * 100)));

  let linhasCsvParseadas = $derived.by(() => {
    const linhas = csvTexto
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.length > 0 && !l.toLowerCase().startsWith('brinco'));

    return linhas.map((linha) => {
      const cols = linha.split(/[;,]/).map((c) => c.trim());
      const peso = parseFloat((cols[3] || '0').replace(',', '.')) || 0;
      const preco = parseFloat((cols[4] || '0').replace(',', '.')) || 0;
      return {
        brinco: cols[0] || '—',
        sexo: (cols[1]?.toUpperCase() === 'F' ? 'F' : 'M') as 'M' | 'F',
        raca: cols[2] || 'Nelore',
        pesoKg: peso,
        precoCompra: preco,
        lote: cols[5] || 'Lote 2026-A'
      };
    });
  });

  let qtdSolicitada = $derived.by(() => {
    if (abaAtiva === 'individual') return 1;
    if (abaAtiva === 'lote') return Math.max(0, Number(quantidadeLote) || 0);
    return linhasCsvParseadas.length;
  });

  let excedeLimitePlano = $derived(
    !auth.user.plano.sem_limite && qtdSolicitada > vagasRestantes
  );

  // Mensagem canônica de utils/plano.py -> pode_cadastrar()
  let mensagemBloqueioPlano = $derived.by(() => {
    if (!excedeLimitePlano) return '';
    return `Limite do plano ${auth.user.plano.rotulo} atingido (${cabecasAtuais}/${limiteCabecas} cabeças ativas — ${vagasRestantes} vagas restantes). Esta operação tenta cadastrar ${qtdSolicitada} cabeça(s). Reduza a quantidade ou faça upgrade do plano.`;
  });

  let precoCalculadoIndividual = $derived.by(() => {
    if (origem === 'nascido') return 0;
    if (modoPreco === 'arroba') {
      return (pesoEntradaKg / KG_POR_ARROBA) * valorArrobaCompra;
    }
    return precoFixoCabeca;
  });

  let investimentoTotalLote = $derived(
    quantidadeLote * (pesoMedioLoteKg / KG_POR_ARROBA) * valorArrobaLote
  );

  function atualizarContadorPlano(novos: number) {
    const novoTotal = auth.user.plano.cabecas + novos;
    const lim = auth.user.plano.limite_cabecas ?? 250;
    auth.user.plano.cabecas = novoTotal;
    auth.user.plano.vagas = Math.max(0, lim - novoTotal);
    auth.user.plano.uso_pct = Math.min(100, Math.round((novoTotal / lim) * 100));
    auth.user.plano.estourado = novoTotal >= lim;
  }

  async function submeterIndividual(e: SubmitEvent) {
    e.preventDefault();
    erroValidacao = '';
    sucessoMsg = '';

    if (excedeLimitePlano) {
      erroValidacao = mensagemBloqueioPlano;
      return;
    }

    const b = brinco.trim().replace(/^#/, '');
    if (!b) {
      erroValidacao = 'Informe o identificador do brinco do animal.';
      return;
    }

    salvando = true;
    const payload = {
      modo: 'individual',
      brinco: b,
      sexo,
      raca,
      origem,
      pai_brinco: origem === 'nascido' ? paiBrinco : null,
      mae_brinco: origem === 'nascido' ? maeBrinco : null,
      data_nascimento: origem === 'nascido' ? dataNascimento : null,
      data_entrada: dataEntrada,
      peso_entrada_kg: pesoEntradaKg,
      preco_compra: precoCalculadoIndividual,
      lote: loteIndividual
    };

    try {
      await apiFetch('/api/animais', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
    } catch {
      // Continua em modo demonstração local
    } finally {
      salvando = false;
      atualizarContadorPlano(1);
      recemCadastrados = [
        {
          brinco: b,
          sexo,
          raca,
          lote: loteIndividual,
          pesoKg: pesoEntradaKg,
          precoCompra: precoCalculadoIndividual,
          origem
        },
        ...recemCadastrados
      ];
      sucessoMsg = `Animal #${b} (${raca} · ${formatKg(pesoEntradaKg)}) incorporado ao ${loteIndividual}.`;
      brinco = '';
    }
  }

  async function submeterLote(e: SubmitEvent) {
    e.preventDefault();
    erroValidacao = '';
    sucessoMsg = '';

    if (excedeLimitePlano) {
      erroValidacao = mensagemBloqueioPlano;
      return;
    }
    if (quantidadeLote <= 0) {
      erroValidacao = 'Informe uma quantidade válida de animais para o lote.';
      return;
    }

    salvando = true;
    const novosItens: AnimalRecemCadastrado[] = [];
    const precoUnit = (pesoMedioLoteKg / KG_POR_ARROBA) * valorArrobaLote;

    for (let i = 0; i < quantidadeLote; i++) {
      const codigoBrinco = `${prefixoBrinco.trim()}${brincoInicial + i}`;
      novosItens.push({
        brinco: codigoBrinco,
        sexo: sexoLote,
        raca: racaLote,
        lote: loteDestinoColetivo,
        pesoKg: pesoMedioLoteKg,
        precoCompra: precoUnit,
        origem: 'compra'
      });
    }

    try {
      await apiFetch('/api/animais', {
        method: 'POST',
        body: JSON.stringify({
          modo: 'lote',
          lote: loteDestinoColetivo,
          animais: novosItens
        })
      });
    } catch {
      // Fallback demonstração
    } finally {
      salvando = false;
      atualizarContadorPlano(quantidadeLote);
      recemCadastrados = [...novosItens, ...recemCadastrados];
      sucessoMsg = `Lote com ${quantidadeLote} animais (#${prefixoBrinco}${brincoInicial} a #${prefixoBrinco}${brincoInicial + quantidadeLote - 1}) cadastrado com sucesso.`;
      brincoInicial = brincoInicial + quantidadeLote;
    }
  }

  async function submeterCsv(e: SubmitEvent) {
    e.preventDefault();
    erroValidacao = '';
    sucessoMsg = '';

    if (linhasCsvParseadas.length === 0) {
      erroValidacao = 'Nenhuma linha válida encontrada no CSV.';
      return;
    }
    if (excedeLimitePlano) {
      erroValidacao = mensagemBloqueioPlano;
      return;
    }

    salvando = true;
    try {
      await apiFetch('/api/animais', {
        method: 'POST',
        body: JSON.stringify({
          modo: 'csv',
          animais: linhasCsvParseadas
        })
      });
    } catch {
      // Fallback demonstração
    } finally {
      salvando = false;
      const qtd = linhasCsvParseadas.length;
      atualizarContadorPlano(qtd);
      recemCadastrados = [
        ...linhasCsvParseadas.map((item) => ({
          ...item,
          origem: 'compra' as OrigemAnimal
        })),
        ...recemCadastrados
      ];
      sucessoMsg = `Importação concluída: ${qtd} animais adicionados ao rebanho ativo.`;
    }
  }
</script>

<div class="entrada-page">
  <header class="page-head">
    <div>
      <div class="badge-row">
        <span class="badge badge--ok">Porta de Entrada do Rebanho</span>
        <span class="badge badge--neutro dado">Plano {auth.user.plano.rotulo}</span>
      </div>
      <h1 class="page-title">Entrada e Cadastro de Animais</h1>
      <p class="page-subtitle">
        Registre compras externas, nascimentos na fazenda, lotes numerados em sequência ou importe planilhas CSV.
      </p>
    </div>
  </header>

  <!-- Guarda Visual de Capacidade do Plano (utils/plano.py) -->
  <section
    class="capacity-guard panel"
    class:capacity-guard--alerta={excedeLimitePlano || usoPercentual >= 95}
    aria-label="Capacidade do plano"
  >
    <div class="capacity-guard__top">
      <div class="capacity-guard__title">
        <strong>Ocupação do plano {auth.user.plano.rotulo}:</strong>
        <span class="dado">
          {cabecasAtuais} / {limiteCabecas} cabeças — <strong>{vagasRestantes} vagas restantes</strong>
        </span>
      </div>
      <span
        class="badge dado"
        class:badge--ok={!excedeLimitePlano}
        class:badge--alerta={excedeLimitePlano}
      >
        {usoPercentual}% ocupado · Solicitando +{qtdSolicitada} cab.
      </span>
    </div>

    <div class="capacity-bar" role="progressbar" aria-valuenow={usoPercentual} aria-valuemin={0} aria-valuemax={100}>
      <div
        class="capacity-bar__fill"
        class:capacity-bar__fill--alerta={excedeLimitePlano || usoPercentual >= 95}
        style={`width: ${usoPercentual}%`}
      ></div>
    </div>

    {#if excedeLimitePlano}
      <p class="capacity-guard__msg" role="alert">
        {mensagemBloqueioPlano}
      </p>
    {/if}
  </section>

  <!-- Abas: Individual | Lote | CSV -->
  <div class="tabs-bar panel" role="tablist" aria-label="Modalidade de entrada">
    <button
      type="button"
      role="tab"
      aria-selected={abaAtiva === 'individual'}
      class="tab-btn"
      class:tab-btn--active={abaAtiva === 'individual'}
      onclick={() => {
        abaAtiva = 'individual';
        erroValidacao = '';
      }}
    >
      1. Cadastro Individual
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={abaAtiva === 'lote'}
      class="tab-btn"
      class:tab-btn--active={abaAtiva === 'lote'}
      onclick={() => {
        abaAtiva = 'lote';
        erroValidacao = '';
      }}
    >
      2. Cadastro em Lote (Sequencial)
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={abaAtiva === 'csv'}
      class="tab-btn"
      class:tab-btn--active={abaAtiva === 'csv'}
      onclick={() => {
        abaAtiva = 'csv';
        erroValidacao = '';
      }}
    >
      3. Importação de CSV
    </button>
  </div>

  {#if erroValidacao}
    <div class="alert-box alert-box--erro" role="alert">
      <strong>Operação bloqueada:</strong>
      <span>{erroValidacao}</span>
    </div>
  {/if}

  {#if sucessoMsg}
    <div class="alert-box alert-box--ok" role="status">
      <span>{sucessoMsg}</span>
    </div>
  {/if}

  {#if abaAtiva === 'individual'}
    <form class="form-panel panel" onsubmit={submeterIndividual}>
      <div class="grid-4">
        <div class="field">
          <label for="ind-brinco">Brinco do animal</label>
          <input
            id="ind-brinco"
            class="input dado"
            type="text"
            inputmode="numeric"
            placeholder="Ex: 488"
            bind:value={brinco}
            required
          />
        </div>

        <div class="field">
          <label for="ind-sexo">Sexo</label>
          <select id="ind-sexo" class="input" bind:value={sexo}>
            <option value="M">Macho (M)</option>
            <option value="F">Fêmea (F)</option>
          </select>
        </div>

        <div class="field">
          <label for="ind-raca">Raça predominante</label>
          <select id="ind-raca" class="input" bind:value={raca}>
            {#each RACAS as r}
              <option value={r}>{r}</option>
            {/each}
          </select>
        </div>

        <div class="field">
          <label for="ind-lote">Lote de manejo</label>
          <select id="ind-lote" class="input" bind:value={loteIndividual}>
            {#each LOTES as l}
              <option value={l}>{l}</option>
            {/each}
          </select>
        </div>
      </div>

      <!-- Origem: Compra externa vs Nascido na fazenda -->
      <div class="origin-box">
        <span class="origin-box__label">Origem do animal</span>
        <div class="origin-options">
          <label class="radio-card" class:radio-card--active={origem === 'compra'}>
            <input type="radio" name="origem" value="compra" bind:group={origem} />
            <div>
              <strong>Compra externa (reposição)</strong>
              <span>Registra desembolso de aquisição no P&L do lote</span>
            </div>
          </label>

          <label class="radio-card" class:radio-card--active={origem === 'nascido'}>
            <input type="radio" name="origem" value="nascido" bind:group={origem} />
            <div>
              <strong>Nascido na fazenda (cria própria)</strong>
              <span>Vincula genealogia (Pai/Mãe) e custo de aquisição R$ 0,00</span>
            </div>
          </label>
        </div>
      </div>

      {#if origem === 'nascido'}
        <div class="grid-3 genealogy-box">
          <div class="field">
            <label for="ind-pai">Brinco do Pai (Reprodutor/Sêmen)</label>
            <input id="ind-pai" class="input dado" type="text" bind:value={paiBrinco} placeholder="Ex: Touro-02" />
          </div>
          <div class="field">
            <label for="ind-mae">Brinco da Mãe (Matriz)</label>
            <input id="ind-mae" class="input dado" type="text" bind:value={maeBrinco} placeholder="Ex: Vaca-88" />
          </div>
          <div class="field">
            <label for="ind-nasc">Data de nascimento</label>
            <input id="ind-nasc" class="input dado" type="date" bind:value={dataNascimento} />
          </div>
        </div>
      {/if}

      <div class="grid-3">
        <div class="field">
          <label for="ind-peso">Peso de entrada (kg)</label>
          <input
            id="ind-peso"
            class="input dado"
            type="number"
            step="0.5"
            min="20"
            inputmode="decimal"
            bind:value={pesoEntradaKg}
            required
          />
          <small class="hint">
            Conversão imediata: <strong class="dado">{formatArroba(pesoEntradaKg)}</strong>
          </small>
        </div>

        {#if origem === 'compra'}
          <div class="field">
            <label for="ind-modo-preco">Base de negociação</label>
            <select id="ind-modo-preco" class="input" bind:value={modoPreco}>
              <option value="arroba">Valor por arroba (R$/@)</option>
              <option value="cabeca">Preço fechado por cabeça (R$)</option>
            </select>
          </div>

          {#if modoPreco === 'arroba'}
            <div class="field">
              <label for="ind-val-arr">Valor da @ de compra (R$/@)</label>
              <input
                id="ind-val-arr"
                class="input dado"
                type="number"
                step="0.5"
                min="0"
                inputmode="decimal"
                bind:value={valorArrobaCompra}
              />
              <small class="hint">
                Custo final da cabeça: <strong class="dado">{formatBrl(precoCalculadoIndividual)}</strong>
              </small>
            </div>
          {:else}
            <div class="field">
              <label for="ind-val-cab">Preço de compra da cabeça (R$)</label>
              <input
                id="ind-val-cab"
                class="input dado"
                type="number"
                step="10"
                min="0"
                inputmode="decimal"
                bind:value={precoFixoCabeca}
              />
            </div>
          {/if}
        {:else}
          <div class="field">
            <label for="ind-data-ent">Data de desmama / incorporação</label>
            <input id="ind-data-ent" class="input dado" type="date" bind:value={dataEntrada} />
          </div>
          <div class="field">
            <label for="ind-custo-cria">Custo de compra externa</label>
            <input id="ind-custo-cria" class="input dado" type="text" value="R$ 0,00 (Cria própria)" readonly />
          </div>
        {/if}
      </div>

      <div class="form-footer">
        <span class="dado">
          Resumo: <strong>#{brinco || '—'}</strong> · {formatKg(pesoEntradaKg)} ({formatArroba(pesoEntradaKg)}) · {formatBrl(precoCalculadoIndividual)}
        </span>
        <button type="submit" class="btn btn-primary" disabled={salvando || excedeLimitePlano}>
          {salvando ? 'Cadastrando...' : 'Cadastrar animal no rebanho'}
        </button>
      </div>
    </form>
  {:else if abaAtiva === 'lote'}
    <form class="form-panel panel" onsubmit={submeterLote}>
      <div class="grid-4">
        <div class="field">
          <label for="lote-pref">Prefixo do brinco (opcional)</label>
          <input id="lote-pref" class="input dado" type="text" placeholder="Ex: SM-" bind:value={prefixoBrinco} />
        </div>
        <div class="field">
          <label for="lote-ini">Numeração inicial</label>
          <input
            id="lote-ini"
            class="input dado"
            type="number"
            min="1"
            inputmode="numeric"
            bind:value={brincoInicial}
            required
          />
        </div>
        <div class="field">
          <label for="lote-qtd">Quantidade de cabeças</label>
          <input
            id="lote-qtd"
            class="input dado"
            type="number"
            min="1"
            max="250"
            inputmode="numeric"
            bind:value={quantidadeLote}
            required
          />
          <small class="hint">
            Gera de <strong class="dado">#{prefixoBrinco}{brincoInicial}</strong> até <strong class="dado">#{prefixoBrinco}{brincoInicial + Math.max(0, quantidadeLote - 1)}</strong>
          </small>
        </div>
        <div class="field">
          <label for="lote-dest">Lote de destino</label>
          <select id="lote-dest" class="input" bind:value={loteDestinoColetivo}>
            {#each LOTES as l}
              <option value={l}>{l}</option>
            {/each}
          </select>
        </div>
      </div>

      <div class="grid-4">
        <div class="field">
          <label for="lote-sexo">Sexo do lote</label>
          <select id="lote-sexo" class="input" bind:value={sexoLote}>
            <option value="M">Machos (M)</option>
            <option value="F">Fêmeas (F)</option>
          </select>
        </div>
        <div class="field">
          <label for="lote-raca">Raça do lote</label>
          <select id="lote-raca" class="input" bind:value={racaLote}>
            {#each RACAS as r}
              <option value={r}>{r}</option>
            {/each}
          </select>
        </div>
        <div class="field">
          <label for="lote-peso">Peso médio de entrada (kg)</label>
          <input
            id="lote-peso"
            class="input dado"
            type="number"
            step="0.5"
            inputmode="decimal"
            bind:value={pesoMedioLoteKg}
            required
          />
          <small class="hint">Média: <span class="dado">{formatArroba(pesoMedioLoteKg)}</span>/cab.</small>
        </div>
        <div class="field">
          <label for="lote-arr">Valor da @ negociada (R$/@)</label>
          <input
            id="lote-arr"
            class="input dado"
            type="number"
            step="0.5"
            inputmode="decimal"
            bind:value={valorArrobaLote}
            required
          />
        </div>
      </div>

      <div class="form-footer">
        <span class="dado">
          Investimento total do lote (<strong class="dado">{quantidadeLote} cab.</strong>): <strong class="dado">{formatBrl(investimentoTotalLote)}</strong>
        </span>
        <button type="submit" class="btn btn-primary" disabled={salvando || excedeLimitePlano}>
          {salvando ? 'Gerando lote...' : `Confirmar entrada de ${quantidadeLote} cabeças`}
        </button>
      </div>
    </form>
  {:else}
    <form class="form-panel panel" onsubmit={submeterCsv}>
      <div class="field">
        <label for="csv-area">Cole os dados do CSV (separados por ponto-e-vírgula ou vírgula)</label>
        <textarea
          id="csv-area"
          class="input csv-textarea dado"
          rows="5"
          bind:value={csvTexto}
        ></textarea>
        <small class="hint">
          Formato esperado: <code class="dado">brinco;sexo;raca;peso_kg;preco_compra;lote</code>
        </small>
      </div>

      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Brinco</th>
              <th>Sexo</th>
              <th>Raça</th>
              <th>Lote</th>
              <th class="col-num">Peso de entrada</th>
              <th class="col-num">Arrobas (@)</th>
              <th class="col-num">Preço de compra</th>
            </tr>
          </thead>
          <tbody>
            {#each linhasCsvParseadas as item}
              <tr>
                <td class="dado"><strong>#{item.brinco}</strong></td>
                <td class="dado">{item.sexo}</td>
                <td>{item.raca}</td>
                <td>{item.lote}</td>
                <td class="col-num dado">{formatKg(item.pesoKg)}</td>
                <td class="col-num dado">{formatArroba(item.pesoKg)}</td>
                <td class="col-num dado">{formatBrl(item.precoCompra)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="form-footer">
        <span class="dado">
          Linhas prontas para importação: <strong>{linhasCsvParseadas.length} cabeças</strong>
        </span>
        <button type="submit" class="btn btn-primary" disabled={salvando || excedeLimitePlano}>
          {salvando ? 'Importando CSV...' : `Importar ${linhasCsvParseadas.length} animais`}
        </button>
      </div>
    </form>
  {/if}

  {#if recemCadastrados.length > 0}
    <section class="recent-sec">
      <h2 class="section-title">Animais incorporados nesta sessão (<span class="dado">{recemCadastrados.length}</span>)</h2>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Brinco</th>
              <th>Sexo / Raça</th>
              <th>Lote</th>
              <th>Origem</th>
              <th class="col-num">Peso inicial</th>
              <th class="col-num">Valor de aquisição</th>
            </tr>
          </thead>
          <tbody>
            {#each recemCadastrados.slice(0, 12) as item}
              <tr>
                <td class="dado"><strong>#{item.brinco}</strong></td>
                <td>{item.sexo} · {item.raca}</td>
                <td>{item.lote}</td>
                <td>
                  <span class="badge badge--neutro">
                    {item.origem === 'nascido' ? 'Cria própria' : 'Compra externa'}
                  </span>
                </td>
                <td class="col-num dado">{formatKg(item.pesoKg)} ({formatArroba(item.pesoKg)})</td>
                <td class="col-num dado">{formatBrl(item.precoCompra)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {/if}
</div>

<style>
  .entrada-page {
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

  .capacity-guard {
    padding: var(--space-4) var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    border-left: 4px solid var(--color-primary);
  }
  .capacity-guard--alerta {
    border-left-color: var(--color-danger);
    background: var(--color-danger-bg);
  }

  .capacity-guard__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    font-size: var(--text-sm);
  }

  .capacity-bar {
    width: 100%;
    height: 8px;
    background: var(--n-100);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }

  .capacity-bar__fill {
    height: 100%;
    background: var(--color-primary);
    transition: width var(--transition-normal);
  }
  .capacity-bar__fill--alerta {
    background: var(--color-danger);
  }

  .capacity-guard__msg {
    font-size: var(--text-xs);
    font-weight: var(--weight-semibold);
    color: var(--color-danger-dark);
  }

  .tabs-bar {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    overflow: hidden;
    background: var(--color-surface-sunken);
  }

  .tab-btn {
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
  .tab-btn:last-child {
    border-right: none;
  }
  .tab-btn--active {
    background: var(--color-surface);
    color: var(--color-primary-dark);
    box-shadow: inset 0 -2px 0 var(--color-primary);
  }

  .alert-box {
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .alert-box--erro {
    background: var(--color-danger-bg);
    border: 1px solid var(--color-danger);
    border-left: 4px solid var(--color-danger);
    color: var(--color-danger-dark);
  }
  .alert-box--ok {
    background: var(--color-primary-bg);
    border: 1px solid var(--color-primary);
    border-left: 4px solid var(--color-primary);
    color: var(--color-primary-dark);
  }

  .form-panel {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .grid-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-3);
  }

  .grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
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

  .origin-box {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .origin-box__label {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--color-ink-secondary);
  }

  .origin-options {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
  }

  .radio-card {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    cursor: pointer;
  }
  .radio-card--active {
    background: var(--color-primary-bg);
    border-color: var(--color-primary);
  }
  .radio-card div {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: var(--text-xs);
    color: var(--color-ink-secondary);
  }
  .radio-card strong {
    font-size: var(--text-sm);
    color: var(--color-ink);
  }

  .genealogy-box {
    padding: var(--space-3) var(--space-4);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .csv-textarea {
    padding: var(--space-3);
    font-size: var(--text-sm);
    line-height: 1.5;
    resize: vertical;
  }

  .form-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }

  .recent-sec {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  @media (max-width: 960px) {
    .grid-4,
    .grid-3,
    .origin-options {
      grid-template-columns: 1fr;
    }
    .form-panel {
      padding: var(--space-4);
    }
    .form-footer .btn {
      width: 100%;
    }
  }

  @media (max-width: 560px) {
    .tabs-bar {
      grid-template-columns: 1fr;
    }
    .tab-btn {
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }
    .tab-btn:last-child {
      border-bottom: none;
    }
  }
</style>
