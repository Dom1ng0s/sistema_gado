# Pecuária de Precisão: Sistema de Gestão de Ativos

> **Foco do Projeto:** Arquitetura de Software e Otimização de Performance em Python e SQL.

## 🎯 O Problema
Sistemas de gestão pecuária comuns funcionam apenas como registros digitais (CRUDs), processando métricas financeiras na camada de aplicação. Isso gera gargalos de performance (O(n)) conforme o rebanho cresce, impedindo a análise de rentabilidade em tempo real.

## 🛠 A Solução Proposta
Uma aplicação Full-Stack que delega a inteligência de dados para o Banco de Dados Relacional, garantindo integridade ACID e alta performance. O sistema visa sair do "cadastro simples" para a "inteligência de negócio".

### Stack Tecnológica
* **Aplicação:** Python 3 + Flask (MVC Pattern)
* **Banco de Dados:** MySQL 8.0 (Foco em Stored Procedures e Views)
* **Frontend:** Jinja2 (Server-Side Rendering)
* **Infraestrutura:** Docker (Containerização para deploy agnóstico)

## 🚀 Diferenciais de Engenharia (Roadmap)
Este projeto está sendo refatorado para demonstrar:
1.  **Otimização de Query:** Migração de lógica de laços Python (`for loops`) para `SQL Views` indexadas.
2.  **Segurança:** Implementação manual de autenticação e hashing.
3.  **Arquitetura Limpa:** Separação clara entre rotas, regras de negócio e persistência.

---
*Projeto em evolução contínua para portfólio de Engenharia de Software.*