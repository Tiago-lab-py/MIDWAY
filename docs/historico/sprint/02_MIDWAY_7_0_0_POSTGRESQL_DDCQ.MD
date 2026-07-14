# Sprint 02 - MIDWAY 7.0.0 com PostgreSQL no schema ddcq

Data de planejamento: `2026-07-11`

## Objetivo

Planejar a transição do MIDWAY de uma ferramenta local, monousuário e baseada em Streamlit/DuckDB para uma solução operacional com banco PostgreSQL, mantendo o processamento analítico pesado em DuckDB/Parquet quando for mais eficiente.

A versão `7.0.0` não deve abandonar o que já funciona. Ela deve criar a fundação para:

- uso multiusuário;
- rastreabilidade de ajustes e autorizações;
- separação entre decisão executiva e tratamento técnico;
- implantação futura na empresa usando o PostgreSQL/dBGUO no schema `ddcq`;
- desenvolvimento local em casa com o mesmo modelo de banco.

## Premissas

- O desenvolvimento pode usar PostgreSQL local no computador de casa.
- Na empresa, o banco alvo será o PostgreSQL/dBGUO, preferencialmente no schema `ddcq`.
- Dados sensíveis reais não devem ser levados para ambiente residencial sem autorização formal.
- O PostgreSQL deve guardar o controle operacional, não necessariamente todo o volume analítico bruto.
- DuckDB e arquivos mensais continuam úteis para processamento, auditoria e massa pesada.
- O Streamlit continua existindo durante a transição, mas deixa de ser a arquitetura final.

## Resultado Esperado

Ao final do ciclo `7.0.0`, deve existir:

```text
docs/
  sprint/
    02_MIDWAY_7_0_0_POSTGRESQL_DDCQ.MD
  29_postgresql_ddcq_midway_7_0_0.md

Banco PostgreSQL:
  schema ddcq
  tabelas operacionais iniciais
  controle de ajustes
  controle de autorizacoes executivas
  fila tecnica/manual
  auditoria de eventos
```

E o MIDWAY deve conseguir alternar ambiente apenas por configuracao:

```env
MIDWAY_DATABASE_URL=postgresql://usuario:senha@localhost:5432/midway
MIDWAY_DB_SCHEMA=ddcq
```

Na empresa:

```env
MIDWAY_DATABASE_URL=postgresql://usuario:senha@servidor_empresa:5432/dbguo
MIDWAY_DB_SCHEMA=ddcq
```

## Visao de Produto

### Antes

```text
Usuario unico
  -> Streamlit
      -> DuckDB local
      -> CSVs locais
```

### Depois

```text
Usuarios
  -> Aplicacao web / Streamlit transitorio
      -> API / camada de servico
          -> PostgreSQL ddcq para controle operacional
          -> DuckDB/Parquet para analitico pesado
          -> exportacoes IQS controladas
```

## Separacao de Responsabilidades

### Executivo

Responsavel por:

- acompanhar indicadores consolidados;
- autorizar tratativas em massa;
- aprovar ajustes automaticos seguros;
- acompanhar impacto e volume.

Exemplo atual:

- autorizar RA `92/82` somente quando `SERVICO + ROBUSTA`;
- deixar conflitos e reclamacoes para fila tecnica.

### Qualidade de Interrupcoes

Responsavel por:

- explicar a evidencia;
- cruzar interrupcao, servico e reclamacao;
- apontar divergencias;
- apoiar priorizacao.

### Ajuste Manual IQS

Responsavel por:

- tratar excecoes;
- analisar conflitos;
- complementar informacoes tecnicas;
- aprovar ou corrigir registros problematicos;
- gerar CSV IQS controlado.

### PostgreSQL ddcq

Responsavel por:

- guardar decisoes;
- guardar historico;
- guardar status de processamento;
- guardar fila de trabalho;
- guardar parametros e permissoes;
- permitir multiusuario e auditoria.

## Escopo Geral da Versao 7.0.0

### Dentro do escopo

- Definir modelo operacional no schema `ddcq`.
- Criar scripts SQL versionados para criacao do banco.
- Migrar controle de ajustes manuais para PostgreSQL.
- Criar tabelas para autorizacoes executivas.
- Criar tabela de fila tecnica.
- Criar tabela de auditoria.
- Preparar configuracao `.env` para ambiente local e empresa.
- Manter compatibilidade com DuckDB para leitura analitica.
- Documentar instalacao local e implantacao na empresa.

### Fora do escopo inicial

- Reescrever todo frontend.
- Substituir todo Streamlit imediatamente.
- Jogar todo dado bruto no PostgreSQL.
- Automatizar carga massiva sem negociacao com TI.
- Criar autenticacao corporativa completa no primeiro passo.

## Sprints Propostas

## Sprint 02.1 - Fundacao PostgreSQL local

### Objetivo

Criar o PostgreSQL local para desenvolvimento e preparar o schema `ddcq`.

### Entregas

- Guia de instalacao PostgreSQL local.
- `.env.example` com variaveis PostgreSQL.
- Script SQL inicial:
  - `CREATE SCHEMA ddcq`;
  - tabelas operacionais;
  - indices basicos;
  - comentario das tabelas principais.

### Criterios de aceite

- Conectar localmente no PostgreSQL.
- Criar schema `ddcq`.
- Executar script sem erro.
- Validar que as tabelas foram criadas.

## Sprint 02.2 - Modelo operacional ddcq

### Objetivo

Modelar as tabelas que substituem controles locais em DuckDB/arquivo.

### Tabelas iniciais

- `ddcq.midway_execucao_lote`;
- `ddcq.midway_ajuste_iqs`;
- `ddcq.midway_autorizacao_executiva`;
- `ddcq.midway_fila_tecnica`;
- `ddcq.midway_auditoria_evento`;
- `ddcq.midway_parametro`;
- `ddcq.midway_exportacao_iqs`.

### Criterios de aceite

- Cada tabela tem chave primaria.
- Cada tabela tem campos de auditoria.
- Ajustes e autorizacoes conseguem se relacionar.
- Modelo suporta o caso RA `92/82`.

## Sprint 02.3 - Migrar autorizacao executiva 92/82

### Objetivo

Persistir no PostgreSQL a autorizacao em massa feita no Executivo.

### Regras

- `SERVICO + ROBUSTA`:
  - gera ajuste aprovado;
  - registra autorizacao executiva;
  - registra auditoria.
- `ROBUSTA_COM_CONFLITO`:
  - gera fila tecnica;
  - nao gera ajuste aprovado automatico.
- `RECLAMACAO`:
  - gera fila tecnica ou sugestao;
  - nao gera ajuste automatico.

### Criterios de aceite

- Um lote de autorizacao tem identificador unico.
- Reexecucao nao duplica ajustes.
- Itens automaticos e manuais ficam separados.
- Ajuste Manual consegue visualizar a fila tecnica.

## Sprint 02.4 - Ajuste Manual com banco central

### Objetivo

Mover a base local de ajustes manuais para PostgreSQL.

### Entregas

- Leitura dos ajustes no schema `ddcq`.
- Gravacao de novo ajuste no schema `ddcq`.
- Edicao de aprovacao e justificativa.
- Exportacao IQS usando ajustes aprovados do PostgreSQL.

### Criterios de aceite

- Dois usuarios nao sobrescrevem a mesma base local.
- Ajustes ficam rastreaveis por responsavel e data.
- Exportacao usa somente ajustes aprovados.

## Sprint 02.5 - Marts para telas lentas

### Objetivo

Reduzir lentidao do Streamlit criando tabelas/materializacoes prontas para tela.

### Entregas

- Mart `9282` consolidado por `ANOMES`.
- Mart de resumo executivo.
- Mart de qualidade de interrupcoes.
- Rotina de atualizacao por lote.

### Criterios de aceite

- Tela Executivo abre sem recalculo pesado.
- Ranking 92/82 usa mart pronto.
- Consultas dinamicas ficam limitadas a filtros simples.

## Sprint 02.6 - Pacote para empresa

### Objetivo

Preparar implantacao no dBGUO/PostgreSQL corporativo.

### Entregas

- Documento para TI.
- Scripts SQL.
- Lista de permissoes.
- Estimativa de volume.
- Plano de backup.
- Plano de carga inicial.
- Plano de rollback.

### Criterios de aceite

- TI consegue entender o que sera criado.
- Schema `ddcq` nao conflita com objetos existentes.
- Parametros de conexao ficam fora do codigo.

## Sprint 02.7 - API e frontend futuro

### Objetivo

Preparar a transicao do Streamlit para uma aplicacao web multiusuario.

### Entregas

- Contrato inicial de endpoints.
- Separacao de regras em servicos Python.
- Identificacao das telas prioritarias:
  - Executivo;
  - Qualidade de Interrupcoes;
  - Ajuste Manual;
  - Exportacoes IQS.

### Criterios de aceite

- Regras principais nao dependem diretamente do Streamlit.
- Endpoints podem ser criados sem duplicar logica.
- A aplicacao web futura tem fronteiras claras.

## Modelo de Decisao

| Tipo de caso | Acao | Responsavel |
| --- | --- | --- |
| `SERVICO + ROBUSTA` | Ajuste automatico aprovado | Executivo |
| `SERVICO + ROBUSTA_COM_CONFLITO` | Fila tecnica | Tecnico |
| `RECLAMACAO` | Revisao assistida | Tecnico |
| `SEM_EVIDENCIA` | Manter ou investigar depois | Qualidade/Tecnico |

## Riscos

| Risco | Mitigacao |
| --- | --- |
| Restricao de upload no dBGUO | Carga incremental, staging e negociacao com TI |
| Lentidao em grandes volumes | Marts por `ANOMES`, DuckDB/Parquet para analitico |
| Dados sensiveis fora da empresa | Usar massa mascarada/local |
| Conflito multiusuario | PostgreSQL central e auditoria |
| Reprocessamento duplicar ajuste | Chaves de idempotencia |

## Proxima Acao Recomendada

1. Criar PostgreSQL local.
2. Criar database `midway`.
3. Criar schema `ddcq`.
4. Executar DDL inicial.
5. Migrar primeiro caso: autorizacao executiva RA `92/82`.
6. Apresentar para TI o pacote de criacao no dBGUO.
