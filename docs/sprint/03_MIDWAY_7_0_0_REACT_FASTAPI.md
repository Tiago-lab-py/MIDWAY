# Sprint 03 - MIDWAY 7.0.0 com React + FastAPI

Data de planejamento: `2026-07-11`

## Objetivo

Iniciar a transicao do MIDWAY de uma interface Streamlit local para uma arquitetura web mais corporativa, com:

- frontend em React;
- backend em FastAPI;
- PostgreSQL `ddcq` como fonte operacional;
- DuckDB mantido para processamento analitico pesado;
- Streamlit mantido como solucao transitoria durante a migracao.

O primeiro recorte funcional sera a tratativa RA `92/82`, porque ela ja possui:

- regra de classificacao automatica;
- autorizacao executiva;
- fila tecnica/manual;
- auditoria;
- views PostgreSQL para acompanhamento.

## Premissas

- O Streamlit nao sera removido nesta sprint.
- O React consumira somente APIs, sem acessar DuckDB ou PostgreSQL diretamente.
- A FastAPI sera a fronteira unica entre tela, banco e processamentos.
- O PostgreSQL `ddcq` sera a fonte oficial de decisoes, status, auditoria e fila.
- Processamentos demorados devem evoluir para jobs controlados em `midway_execucao_lote`.
- A autenticacao corporativa completa fica fora do MVP, mas a arquitetura deve deixar espaco para ela.

## Arquitetura Alvo

```text
Usuario
  -> React
      -> FastAPI
          -> PostgreSQL ddcq
          -> DuckDB / arquivos processados
          -> exportacoes IQS
```

## MVP da Sprint

### Backend FastAPI

Entregas:

- endpoint de saude da API;
- endpoint do painel RA `92/82`;
- endpoint de ajustes automaticos RA `92/82`;
- endpoint da fila tecnica RA `92/82`;
- endpoint para disparar autorizacao executiva RA `92/82`;
- configuracao CORS para frontend local.

Rotas planejadas:

```text
GET  /api/health
GET  /api/executivo/9282/painel
GET  /api/executivo/9282/ajustes-auto
GET  /api/executivo/9282/fila-tecnica
POST /api/executivo/9282/autorizar
```

### Frontend React

Entregas:

- layout base com sidebar;
- dashboard executivo;
- cards principais da tratativa RA `92/82`;
- tabela simples de fila tecnica;
- estado visual da API/banco.

Paginas planejadas:

```text
Dashboard
Executivo 92/82
Fila Tecnica
Auditoria
Configuracoes
```

## Separacao de Responsabilidades

### React

Responsavel por:

- experiencia visual;
- navegacao;
- filtros;
- tabelas;
- chamadas HTTP;
- feedback de carregamento e erro.

### FastAPI

Responsavel por:

- validar parametros;
- consultar PostgreSQL;
- disparar processamentos;
- padronizar respostas;
- centralizar autorizacoes;
- futuramente validar usuario/papel.

### PostgreSQL

Responsavel por:

- autorizacoes;
- ajustes;
- fila tecnica;
- auditoria;
- parametros;
- historico operacional.

### DuckDB

Responsavel por:

- leitura analitica pesada;
- processamento mensal;
- cruzamentos grandes;
- geracao de bases intermediarias.

## Criterio de Sucesso

A sprint sera considerada validada quando:

- `run.bat api` subir a FastAPI;
- `GET /api/health` responder `ok`;
- `GET /api/executivo/9282/painel` retornar os dados das views `ddcq`;
- frontend React exibir os indicadores principais;
- Streamlit continuar funcional;
- PostgreSQL validar `7` tabelas, `4` views e parametros esperados.

## Fora do Escopo

- autenticacao corporativa completa;
- deploy em servidor;
- substituicao total do Streamlit;
- fila assíncrona robusta com worker dedicado;
- migracao completa de todas as paginas.

## Proximas Sprints

### Sprint 04 - Jobs e Execucoes

- criar camada de jobs;
- gravar status em `midway_execucao_lote`;
- acompanhar execucoes no frontend.

### Sprint 05 - Ajuste Manual React

- tratar fila tecnica;
- aprovar/rejeitar ajustes;
- registrar auditoria detalhada.

### Sprint 06 - Exportacao IQS Controlada

- gerar exportacoes a partir de ajustes aprovados;
- registrar exportacoes no PostgreSQL;
- permitir download controlado pelo frontend.
