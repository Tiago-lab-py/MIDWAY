# Governança, Login e Cybersegurança - MIDWAY 7.0.0

Data: `2026-07-11`

## Objetivo

Criar uma fundação de governança para o MIDWAY com:

- login obrigatório no frontend React;
- perfis `ADM`, `GESTOR` e `ANALISTA`;
- trilha de auditoria;
- registro governado de alterações;
- validação de dados e SQL versionado;
- preservação do Streamlit como interface de transição.

## Perfis

### ADM

Responsável por:

- criar usuários;
- consultar sessões ativas;
- aplicar ou coordenar scripts SQL;
- administrar parâmetros;
- auditar alterações sensíveis.

### GESTOR

Responsável por:

- autorizar tratativas em massa;
- consultar usuários e indicadores;
- acompanhar fila técnica;
- validar evidências executivas.

### ANALISTA

Responsável por:

- consultar dados;
- analisar fila técnica;
- registrar justificativas;
- apoiar tratamento manual.

## Páginas React

### Login

Valida e-mail e senha pela FastAPI.

Características:

- o e-mail é a credencial de entrada do usuário;
- senha armazenada somente como hash PBKDF2 no PostgreSQL;
- token de sessão armazenado no banco apenas como hash;
- sessão com expiração;
- logout revoga a sessão.

### Administração de Usuários

O perfil `ADM` possui controle local de usuários no frontend React:

- incluir usuário;
- definir senha inicial;
- usar e-mail como login;
- selecionar perfil `ADM`, `GESTOR` ou `ANALISTA`;
- consultar usuários cadastrados;
- consultar sessões ativas;
- acompanhar resets de senha.

Regras:

- senha inicial deve ter no mínimo 12 caracteres;
- senha nunca é gravada em texto puro;
- a API grava apenas `senha_hash`;
- ações administrativas são registradas em auditoria.

### Reset de Senha com Código

O reset de senha é exclusivo do perfil `ADM`.

Fluxo:

1. ADM seleciona o usuário.
2. Sistema gera um código de 4 dígitos.
3. Código aparece na tela por operação governada.
4. ADM digita o código exibido, a nova senha e uma justificativa.
5. API valida código, prazo e perfil.
6. Senha é atualizada como hash.
7. Sessões ativas do usuário são revogadas.
8. Evento fica disponível no monitoramento de reset.

Controles:

- código expira em 10 minutos;
- três tentativas inválidas cancelam o reset;
- códigos e hashes não aparecem em views de monitoramento;
- tabela `midway_reset_senha` mantém status, solicitante, confirmação e justificativa.

### Dashboard

Visão executiva da regra RA `92/82`:

- automáticos;
- fila técnica;
- conflitos;
- reclamações;
- saúde do banco.

### Executivo

Página de autorização em massa.

Regra:

- apenas `SERVICO + ROBUSTA`;
- perfis permitidos: `ADM` e `GESTOR`;
- duplicidades são ignoradas pela API;
- ação fica auditada.

### Fila Técnica

Página para casos problemáticos:

- conflito de serviço;
- evidência por reclamação;
- prioridade;
- status.

### Ajustes IQS

Lista os ajustes automáticos autorizados e aprovados.

### Verificação Dados

Mostra validação operacional:

- tabelas esperadas;
- views esperadas;
- parâmetros esperados;
- pendências de schema.

### SQL

Lista scripts SQL versionados do schema `ddcq`.

Boa prática:

- a tela não executa SQL diretamente;
- aplicação de SQL deve ser feita por processo controlado;
- scripts devem estar versionados no repositório.

### Alterações

Lista a tabela `midway_alteracao_registro`.

Toda alteração sensível deve registrar:

- módulo;
- entidade;
- tipo;
- status;
- justificativa;
- usuário solicitante;
- antes/depois quando aplicável.

### Auditoria

Mostra eventos operacionais da tabela `midway_auditoria_evento`.

### Governança

Mostra:

- usuários;
- perfis;
- sessões ativas;
- segregação de funções.

### Configurações

Mostra:

- URL da API;
- status do PostgreSQL;
- schema;
- tabelas;
- views;
- parâmetros.

## Página Streamlit de Transição

Foi criada a página:

```text
midway/web/pages/11_Governanca.py
```

Finalidade:

- consulta diagnóstica;
- validação do PostgreSQL;
- listagem de scripts SQL;
- usuários;
- alterações;
- auditoria.

Importante:

- ações sensíveis não devem ser executadas pelo Streamlit;
- login oficial e controle de perfil ficam no React + FastAPI;
- Streamlit permanece como apoio durante a migração.

## Comandos

Aplicar governança:

```bat
run.bat postgres_governanca
```

Criar primeiro usuário ADM:

```bat
run.bat admin_bootstrap
```

Opcionalmente definir e-mail e senha inicial:

```bat
set MIDWAY_BOOTSTRAP_EMAIL=admin@empresa.com
set MIDWAY_BOOTSTRAP_PASSWORD=senha_forte_com_12_ou_mais_caracteres
run.bat admin_bootstrap
```

Subir API:

```bat
run.bat api
```

Subir frontend:

```bat
cd frontend
set NODE_OPTIONS=--use-system-ca
npm run dev
```

## Boas Práticas de Governança

- Segregar papéis: `ADM`, `GESTOR`, `ANALISTA`.
- Não permitir alteração em massa sem autorização executiva.
- Exigir justificativa para toda alteração sensível.
- Registrar auditoria de login, logout, autorização, alteração e exportação.
- Manter SQL versionado.
- Evitar execução livre de SQL pela interface.
- Tratar Streamlit como ferramenta transitória ou de diagnóstico.
- Usar PostgreSQL como fonte oficial de decisões e histórico.

## Boas Práticas de Cybersegurança

- Nunca versionar `.env`.
- Nunca versionar senhas reais.
- Usar senha forte no bootstrap.
- Trocar senha temporária após primeiro acesso.
- Armazenar senha somente como hash.
- Armazenar token somente como hash.
- Usar expiração de sessão.
- Revogar sessão no logout.
- Limitar ações por perfil.
- Restringir CORS aos hosts necessários.
- Usar HTTPS em ambiente corporativo.
- Solicitar à TI política de backup, rotação de senha e logs.
- Evitar copiar dados reais para ambiente residencial sem autorização.

## Próximas Melhorias

- Tela para troca de senha.
- Bloqueio automático por excesso de tentativas.
- Integração com autenticação corporativa.
- Worker assíncrono para jobs longos.
- Aprovação dupla para alterações críticas.
- Registro de exportações IQS governadas.

## Roadmap de Telas Avançadas

O plano detalhado de evolução das telas, funções por perfil, fluxo `Analista -> Gestor -> IQS` e backlog por sprint está em:

```text
docs/31_plano_aperfeicoamento_telas_governanca.md
```
