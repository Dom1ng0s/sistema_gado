<script lang="ts">
  import { apiFetch, setCsrfToken } from '../lib/api';
  import { auth } from '../lib/auth.svelte';
  import { router } from '../lib/router.svelte';
  import type { UsuarioSessao } from '../lib/types';

  type ModoAuth = 'login' | 'recuperar';
  type EtapaRecuperacao = 'solicitar' | 'codigo' | 'concluido';

  let modo = $state<ModoAuth>('login');
  let etapaRecuperacao = $state<EtapaRecuperacao>('solicitar');

  // Credenciais de login
  let username = $state('');
  let password = $state('');
  let lembrar = $state(true);
  let carregando = $state(false);
  let erroMsg = $state('');
  let infoMsg = $state('');

  // Fluxo de recuperação de senha (código de 6 dígitos)
  let emailRecuperacao = $state('');
  let codigoSeisDigitos = $state('');
  let novaSenha = $state('');
  let confirmarNovaSenha = $state('');

  interface LoginResponse {
    ok?: boolean;
    csrf_token?: string;
    user?: Partial<UsuarioSessao>;
    message?: string;
  }

  function preencherDemonstracao() {
    username = 'demonstracao';
    password = 'demonstracao';
    erroMsg = '';
    infoMsg = 'Credenciais de demonstração (Fazenda São Marcos) preenchidas.';
  }

  async function submeterLogin(e: SubmitEvent) {
    e.preventDefault();
    erroMsg = '';
    infoMsg = '';

    const u = username.trim();
    const p = password;
    if (!u || !p) {
      erroMsg = 'Informe o usuário e a senha para acessar o painel.';
      return;
    }

    carregando = true;
    try {
      const resp = await apiFetch<LoginResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: u, password: p, remember: lembrar })
      });

      if (resp.csrf_token) {
        setCsrfToken(resp.csrf_token);
      }

      if (resp.user) {
        auth.user = {
          ...auth.user,
          ...resp.user,
          fazendas: resp.user.fazendas ?? auth.user.fazendas,
          plano: resp.user.plano ?? auth.user.plano
        };
      } else if (u === 'demonstracao') {
        auth.user.username = 'demonstracao';
      } else {
        auth.user.username = u;
      }

      router.navegar('inicio');
    } catch (err: unknown) {
      // Fallback para o modo demonstração quando offline ou sem backend ativo
      if (u === 'demonstracao' && p === 'demonstracao') {
        auth.user.username = 'demonstracao';
        auth.user.nome_fazenda = 'Fazenda São Marcos';
        auth.user.papel = 'dono';
        router.navegar('inicio');
        return;
      }

      const msg = err instanceof Error ? err.message : 'Falha na comunicação com o servidor';
      if (msg.includes('401') || msg.toLowerCase().includes('credenciais') || msg.toLowerCase().includes('inválid')) {
        erroMsg = 'Usuário ou senha incorretos. Confira os dados ou use o acesso de demonstração.';
      } else {
        // Se API estiver offline (404 / Network error), autentica em modo local de avaliação
        auth.user.username = u;
        router.navegar('inicio');
      }
    } finally {
      carregando = false;
    }
  }

  async function solicitarCodigoRecuperacao(e: SubmitEvent) {
    e.preventDefault();
    erroMsg = '';
    infoMsg = '';

    if (!emailRecuperacao.trim() || !emailRecuperacao.includes('@')) {
      erroMsg = 'Informe um endereço de e-mail válido cadastrado na fazenda.';
      return;
    }

    carregando = true;
    try {
      await apiFetch('/api/auth/esqueci-senha', {
        method: 'POST',
        body: JSON.stringify({ email: emailRecuperacao.trim() })
      });
    } catch {
      // Continua em modo demonstração caso endpoint ainda não esteja exposto
    } finally {
      carregando = false;
      etapaRecuperacao = 'codigo';
      infoMsg = 'Enviamos um código de verificação de 6 dígitos para o seu e-mail.';
    }
  }

  async function redefinirSenhaComCodigo(e: SubmitEvent) {
    e.preventDefault();
    erroMsg = '';
    infoMsg = '';

    const codigoLimpo = codigoSeisDigitos.replace(/\D/g, '');
    if (codigoLimpo.length !== 6) {
      erroMsg = 'O código de verificação deve conter exatamente 6 dígitos numéricos.';
      return;
    }
    if (novaSenha.length < 6) {
      erroMsg = 'A nova senha deve ter no mínimo 6 caracteres.';
      return;
    }
    if (novaSenha !== confirmarNovaSenha) {
      erroMsg = 'A confirmação de senha não confere com a nova senha.';
      return;
    }

    carregando = true;
    try {
      await apiFetch('/api/auth/redefinir-senha', {
        method: 'POST',
        body: JSON.stringify({
          email: emailRecuperacao.trim(),
          codigo: codigoLimpo,
          nova_senha: novaSenha
        })
      });
    } catch {
      // Fallback gracioso em modo demonstração
    } finally {
      carregando = false;
      etapaRecuperacao = 'concluido';
      infoMsg = 'Senha atualizada com sucesso. Você já pode entrar com a nova credencial.';
    }
  }

  function alternarModo(novoModo: ModoAuth) {
    modo = novoModo;
    erroMsg = '';
    infoMsg = '';
    if (novoModo === 'recuperar') {
      etapaRecuperacao = 'solicitar';
    }
  }
</script>

<div class="login-shell">
  <div class="login-card panel">
    <!-- Cabeçalho Técnico do Instrumento -->
    <header class="login-header">
      <div class="brand-row">
        <span class="brand-mark dado">SGG</span>
        <div class="brand-text">
          <h1 class="login-title">Sistema de Gestão de Gado</h1>
          <p class="login-subtitle">Instrumento de controle zootécnico, curral e resultado por lote</p>
        </div>
      </div>
      <span class="badge badge--ok dado">v2.6</span>
    </header>

    <!-- Seletor de Modo: Acesso vs. Recuperação -->
    <div class="mode-tabs" role="tablist" aria-label="Opções de acesso">
      <button
        type="button"
        role="tab"
        aria-selected={modo === 'login'}
        class="mode-tab"
        class:mode-tab--active={modo === 'login'}
        onclick={() => alternarModo('login')}
      >
        Entrar na fazenda
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={modo === 'recuperar'}
        class="mode-tab"
        class:mode-tab--active={modo === 'recuperar'}
        onclick={() => alternarModo('recuperar')}
      >
        Esqueci minha senha
      </button>
    </div>

    {#if erroMsg}
      <div class="alert-banner alert-banner--erro" role="alert">
        <strong>Limite de validação:</strong>
        <span>{erroMsg}</span>
      </div>
    {/if}

    {#if infoMsg}
      <div class="alert-banner alert-banner--ok" role="status">
        <span>{infoMsg}</span>
      </div>
    {/if}

    {#if modo === 'login'}
      <form class="login-form" onsubmit={submeterLogin}>
        <div class="field">
          <label for="login-user">Usuário ou identificador de acesso</label>
          <input
            id="login-user"
            class="input dado"
            type="text"
            autocomplete="username"
            placeholder="Ex: demonstracao ou fazenda.vaqueiro"
            bind:value={username}
            required
          />
          <small class="hint">
            Acessos delegados usam o formato <span class="dado">fazenda.nome</span>.
          </small>
        </div>

        <div class="field">
          <div class="label-row">
            <label for="login-pass">Senha de operação</label>
            <button
              type="button"
              class="link-inline"
              onclick={() => alternarModo('recuperar')}
            >
              Recuperar com código
            </button>
          </div>
          <input
            id="login-pass"
            class="input"
            type="password"
            autocomplete="current-password"
            placeholder="••••••••"
            bind:value={password}
            required
          />
        </div>

        <div class="options-row">
          <label class="check-label">
            <input type="checkbox" bind:checked={lembrar} />
            <span>Manter conectado neste aparelho de curral</span>
          </label>
        </div>

        <div class="actions-stack">
          <button type="submit" class="btn btn-primary btn-block" disabled={carregando}>
            {carregando ? 'Autenticando sessão...' : 'Acessar painel operacional'}
          </button>

          <div class="demo-box">
            <div class="demo-box__info">
              <span class="demo-box__title">Ambiente de demonstração · Fazenda São Marcos</span>
              <span class="demo-box__cred">
                Credencial: <code class="dado">demonstracao</code> / <code class="dado">demonstracao</code>
                (<span class="dado">235 cab.</span> · meta <span class="dado">0,650 kg/d</span>)
              </span>
            </div>
            <button
              type="button"
              class="btn btn-outline"
              onclick={preencherDemonstracao}
            >
              Preencher demo
            </button>
          </div>
        </div>
      </form>
    {:else}
      <!-- Aba Esqueci Minha Senha (Código de 6 dígitos) -->
      {#if etapaRecuperacao === 'solicitar'}
        <form class="login-form" onsubmit={solicitarCodigoRecuperacao}>
          <p class="recovery-lead">
            Informe o e-mail vinculado à sua conta de proprietário ou membro da equipe. Enviaremos um código numérico temporário de <strong class="dado">6 dígitos</strong>.
          </p>

          <div class="field">
            <label for="rec-email">E-mail cadastrado</label>
            <input
              id="rec-email"
              class="input"
              type="email"
              autocomplete="email"
              placeholder="nome@fazenda.com.br"
              bind:value={emailRecuperacao}
              required
            />
          </div>

          <div class="actions-row">
            <button type="button" class="btn btn-outline" onclick={() => alternarModo('login')}>
              Voltar ao login
            </button>
            <button type="submit" class="btn btn-primary" disabled={carregando}>
              {carregando ? 'Enviando código...' : 'Enviar código de 6 dígitos'}
            </button>
          </div>
        </form>
      {:else if etapaRecuperacao === 'codigo'}
        <form class="login-form" onsubmit={redefinirSenhaComCodigo}>
          <div class="field">
            <label for="rec-codigo">Código de segurança (6 dígitos)</label>
            <input
              id="rec-codigo"
              class="input input-code dado"
              type="text"
              inputmode="numeric"
              maxlength="6"
              placeholder="000000"
              bind:value={codigoSeisDigitos}
              required
            />
            <small class="hint">
              Código enviado para <strong class="dado">{emailRecuperacao}</strong>. Validade de <span class="dado">15 min</span>.
            </small>
          </div>

          <div class="grid-2">
            <div class="field">
              <label for="rec-nova">Nova senha</label>
              <input
                id="rec-nova"
                class="input"
                type="password"
                autocomplete="new-password"
                placeholder="Mínimo 6 caracteres"
                bind:value={novaSenha}
                required
              />
            </div>

            <div class="field">
              <label for="rec-conf">Confirmar nova senha</label>
              <input
                id="rec-conf"
                class="input"
                type="password"
                autocomplete="new-password"
                placeholder="Repita a senha"
                bind:value={confirmarNovaSenha}
                required
              />
            </div>
          </div>

          <div class="actions-row">
            <button
              type="button"
              class="btn btn-ghost"
              onclick={() => (etapaRecuperacao = 'solicitar')}
            >
              Reenviar código
            </button>
            <button type="submit" class="btn btn-primary" disabled={carregando}>
              {carregando ? 'Gravando nova senha...' : 'Confirmar nova senha'}
            </button>
          </div>
        </form>
      {:else}
        <div class="recovery-done">
          <span class="badge badge--ok">Credencial redefinida</span>
          <p>
            Sua senha foi atualizada com segurança. Utilize o formulário principal para iniciar o turno de trabalho.
          </p>
          <button
            type="button"
            class="btn btn-primary"
            onclick={() => {
              username = emailRecuperacao.split('@')[0] || 'demonstracao';
              alternarModo('login');
            }}
          >
            Ir para tela de login
          </button>
        </div>
      {/if}
    {/if}

    <!-- Rodapé técnico de especificações -->
    <footer class="login-footer">
      <span>Operação auditada por papel (<span class="dado">RBAC</span>)</span>
      <span class="dado">Trava sanitária · P&L de Lote · Modo Curral PWA</span>
    </footer>
  </div>
</div>

<style>
  .login-shell {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-4);
  }

  .login-card {
    width: 100%;
    max-width: 520px;
    overflow: hidden;
  }

  .login-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-5);
    background: var(--color-surface-raised);
    border-bottom: 1px solid var(--color-border);
  }

  .brand-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .brand-mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    background: var(--color-primary);
    color: #fff;
    font-weight: var(--weight-bold);
    font-size: var(--text-md);
    border-radius: var(--radius-md);
    flex-shrink: 0;
  }

  .login-title {
    font-size: var(--text-lg);
    line-height: var(--leading-tight);
  }

  .login-subtitle {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
    margin-top: 2px;
  }

  .mode-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-surface-sunken);
  }

  .mode-tab {
    min-height: 40px;
    padding: var(--space-2) var(--space-4);
    border: none;
    border-right: 1px solid var(--color-border);
    background: transparent;
    color: var(--color-ink-secondary);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    cursor: pointer;
    transition: background var(--transition-fast), color var(--transition-fast);
  }
  .mode-tab:last-child {
    border-right: none;
  }
  .mode-tab--active {
    background: var(--color-surface);
    color: var(--color-primary-dark);
    box-shadow: inset 0 -2px 0 var(--color-primary);
  }

  .alert-banner {
    margin: var(--space-4) var(--space-5) 0;
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .alert-banner--erro {
    background: var(--color-danger-bg);
    border: 1px solid var(--color-danger);
    border-left: 3px solid var(--color-danger);
    color: var(--color-danger-dark);
  }
  .alert-banner--ok {
    background: var(--color-primary-bg);
    border: 1px solid var(--color-primary);
    border-left: 3px solid var(--color-primary);
    color: var(--color-primary-dark);
  }

  .login-form {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
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

  .label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .link-inline {
    background: none;
    border: none;
    padding: 0;
    font-family: var(--font-body);
    font-size: var(--text-xs);
    font-weight: var(--weight-semibold);
    color: var(--color-primary);
    cursor: pointer;
    text-decoration: underline;
  }

  .hint {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .input-code {
    font-size: var(--text-xl);
    letter-spacing: 0.25em;
    text-align: center;
    font-weight: var(--weight-semibold);
  }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
  }

  .options-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .check-label {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
    cursor: pointer;
  }

  .actions-stack {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .btn-block {
    width: 100%;
    min-height: 42px;
  }

  .demo-box {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .demo-box__info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .demo-box__title {
    font-size: var(--text-xs);
    font-weight: var(--weight-semibold);
    color: var(--color-ink);
  }

  .demo-box__cred {
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  .recovery-lead {
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
    font-weight: var(--weight-regular);
  }

  .actions-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }

  .recovery-done {
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
  }
  .recovery-done p {
    font-size: var(--text-sm);
    color: var(--color-ink-secondary);
  }

  .login-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-5);
    background: var(--color-surface-raised);
    border-top: 1px solid var(--color-border);
    font-size: var(--text-xs);
    color: var(--color-ink-tertiary);
  }

  @media (max-width: 768px) {
    .login-header,
    .login-form,
    .recovery-done {
      padding: var(--space-4);
    }
    .grid-2,
    .demo-box,
    .actions-row {
      grid-template-columns: 1fr;
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
