# PostgreSQL ddcq - MIDWAY 7.0.0

Data: `2026-07-11`

## Objetivo

Definir como criar e usar um banco PostgreSQL para a versao `7.0.0` do MIDWAY, primeiro em ambiente local residencial para desenvolvimento e depois no ambiente corporativo dBGUO/PostgreSQL no schema `ddcq`.

O objetivo nao e trocar todo o motor analitico imediatamente. O PostgreSQL entra como banco operacional e multiusuario.

## Decisao Arquitetural

```text
PostgreSQL ddcq
  -> ajustes
  -> autorizacoes executivas
  -> fila tecnica
  -> auditoria
  -> status de processamento
  -> parametros
  -> exportacoes geradas

DuckDB / Parquet / arquivos mensais
  -> massa analitica pesada
  -> apuracao
  -> cruzamentos grandes
  -> dados historicos por ANOMES
```

## Ambientes

## 1. Ambiente local residencial

Uso:

- desenvolver;
- validar modelo;
- testar tela e regras;
- usar dados pequenos ou mascarados.

Exemplo de conexao:

```env
MIDWAY_DATABASE_URL=postgresql://midway_app:senha_local@localhost:5432/midway
MIDWAY_DB_SCHEMA=ddcq
MIDWAY_ENV=local
```

## 2. Ambiente empresa dBGUO/PostgreSQL

Uso:

- piloto corporativo;
- dados reais;
- multiusuario;
- auditoria;
- backup institucional.

Exemplo de conexao:

```env
MIDWAY_DATABASE_URL=postgresql://midway_app:senha_empresa@servidor_dbguo:5432/dbguo
MIDWAY_DB_SCHEMA=ddcq
MIDWAY_ENV=empresa
```

## Principio Importante

O codigo nao deve saber se esta em casa ou na empresa. A diferenca deve estar no `.env`.

```text
Mesmo codigo
  + .env local
      -> PostgreSQL local

Mesmo codigo
  + .env empresa
      -> dBGUO/PostgreSQL schema ddcq
```

## Criacao Local do PostgreSQL

### Opcao A - Instalador Windows

1. Instalar PostgreSQL no Windows.
2. Guardar a senha do usuario `postgres`.
3. Abrir `pgAdmin` ou `psql`.
4. Criar database, usuario e schema.

### Opcao B - Docker

Quando Docker for permitido:

```bat
docker run --name midway-postgres ^
  -e POSTGRES_PASSWORD=postgres ^
  -e POSTGRES_DB=midway ^
  -p 5432:5432 ^
  -v midway_postgres_data:/var/lib/postgresql/data ^
  -d postgres:16
```

No ambiente corporativo, o uso de Docker depende da TI.

## Criacao do Banco Local

Conectar como usuario administrador e executar:

```sql
CREATE DATABASE midway;
```

Conectar no database `midway`:

```sql
CREATE USER midway_app WITH PASSWORD 'trocar_senha_local';

CREATE SCHEMA IF NOT EXISTS ddcq AUTHORIZATION midway_app;

GRANT CONNECT ON DATABASE midway TO midway_app;
GRANT USAGE, CREATE ON SCHEMA ddcq TO midway_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA ddcq
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO midway_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA ddcq
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO midway_app;
```

Para desenvolvimento local simples, o dono do schema pode ser o proprio `midway_app`.

## Criacao no dBGUO / Empresa

Solicitar para TI:

```sql
CREATE SCHEMA IF NOT EXISTS ddcq;
```

Permissoes minimas para o usuario da aplicacao:

```sql
GRANT USAGE ON SCHEMA ddcq TO midway_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ddcq TO midway_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA ddcq TO midway_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA ddcq
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO midway_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA ddcq
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO midway_app;
```

Se a empresa exigir separacao:

- usuario dono: `ddcq_owner`;
- usuario aplicacao: `midway_app`;
- usuario leitura: `midway_readonly`.

## DDL Inicial Proposto

Este DDL e uma proposta inicial para a versao `7.0.0`. Ele deve ser refinado antes da implantacao definitiva.

```sql
CREATE SCHEMA IF NOT EXISTS ddcq;

CREATE TABLE IF NOT EXISTS ddcq.midway_execucao_lote (
    id_lote              uuid PRIMARY KEY,
    anomes               varchar(6) NOT NULL,
    tipo_lote            varchar(60) NOT NULL,
    status_lote          varchar(30) NOT NULL,
    origem               varchar(120),
    parametros           jsonb,
    iniciado_em          timestamp NOT NULL DEFAULT now(),
    finalizado_em        timestamp,
    criado_por           varchar(120),
    mensagem             text
);

CREATE TABLE IF NOT EXISTS ddcq.midway_autorizacao_executiva (
    id_autorizacao       uuid PRIMARY KEY,
    anomes               varchar(6) NOT NULL,
    tipo_autorizacao     varchar(80) NOT NULL,
    regra                varchar(120) NOT NULL,
    status_autorizacao   varchar(30) NOT NULL,
    qtd_candidatos       integer NOT NULL DEFAULT 0,
    qtd_autorizados      integer NOT NULL DEFAULT 0,
    qtd_rejeitados       integer NOT NULL DEFAULT 0,
    justificativa        text,
    autorizado_por       varchar(120),
    autorizado_em        timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ddcq.midway_ajuste_iqs (
    id_ajuste                         uuid PRIMARY KEY,
    anomes                            varchar(6) NOT NULL,
    aprovado                          boolean NOT NULL DEFAULT false,
    origem_ajuste                     varchar(80) NOT NULL,
    escopo                            varchar(30) NOT NULL,
    num_ocorrencia_adms               varchar(80),
    num_seq_intrp                     varchar(80),
    num_uc_uci                        varchar(80),
    sigla_regional                    varchar(20),
    cod_causa_intrp_original          varchar(20),
    cod_comp_intrp_original           varchar(20),
    novo_cod_causa_intrp              varchar(20),
    novo_cod_comp_intrp               varchar(20),
    novo_cod_cond_clima_intrp         varchar(20),
    novo_cod_tipo_intrp               varchar(20),
    novo_num_motivo_trat_dif_uci      varchar(20),
    novo_valid_pos_operacao           varchar(10),
    justificativa                     text,
    id_autorizacao                    uuid REFERENCES ddcq.midway_autorizacao_executiva(id_autorizacao),
    criado_por                        varchar(120),
    criado_em                         timestamp NOT NULL DEFAULT now(),
    atualizado_por                    varchar(120),
    atualizado_em                     timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ddcq.midway_fila_tecnica (
    id_fila                 uuid PRIMARY KEY,
    anomes                  varchar(6) NOT NULL,
    tipo_fila               varchar(80) NOT NULL,
    prioridade              integer NOT NULL DEFAULT 0,
    status_fila             varchar(30) NOT NULL DEFAULT 'ABERTA',
    num_ocorrencia_adms     varchar(80),
    num_seq_intrp           varchar(80),
    cod_causa_atual         varchar(20),
    cod_comp_atual          varchar(20),
    cod_causa_sugerida      varchar(20),
    cod_comp_sugerido       varchar(20),
    fonte_sugestao          varchar(80),
    nivel_evidencia         varchar(80),
    score_sugestao          numeric(10, 2),
    evidencia_resumo        text,
    responsavel             varchar(120),
    criado_em               timestamp NOT NULL DEFAULT now(),
    atualizado_em           timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ddcq.midway_auditoria_evento (
    id_evento           uuid PRIMARY KEY,
    anomes              varchar(6),
    tipo_evento         varchar(80) NOT NULL,
    entidade            varchar(80),
    id_entidade         varchar(120),
    usuario             varchar(120),
    detalhe             jsonb,
    criado_em           timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ddcq.midway_exportacao_iqs (
    id_exportacao       uuid PRIMARY KEY,
    anomes              varchar(6) NOT NULL,
    tipo_exportacao     varchar(80) NOT NULL,
    status_exportacao   varchar(30) NOT NULL,
    caminho_arquivo     text,
    qtd_linhas          integer NOT NULL DEFAULT 0,
    gerado_por          varchar(120),
    gerado_em           timestamp NOT NULL DEFAULT now(),
    id_lote             uuid REFERENCES ddcq.midway_execucao_lote(id_lote)
);

CREATE TABLE IF NOT EXISTS ddcq.midway_parametro (
    chave               varchar(120) PRIMARY KEY,
    valor               text,
    descricao           text,
    atualizado_por      varchar(120),
    atualizado_em       timestamp NOT NULL DEFAULT now()
);
```

## Indices Iniciais

```sql
CREATE INDEX IF NOT EXISTS idx_midway_ajuste_iqs_anomes
    ON ddcq.midway_ajuste_iqs(anomes);

CREATE INDEX IF NOT EXISTS idx_midway_ajuste_iqs_ocorrencia
    ON ddcq.midway_ajuste_iqs(num_ocorrencia_adms);

CREATE INDEX IF NOT EXISTS idx_midway_ajuste_iqs_intrp
    ON ddcq.midway_ajuste_iqs(num_seq_intrp);

CREATE INDEX IF NOT EXISTS idx_midway_fila_tecnica_anomes_status
    ON ddcq.midway_fila_tecnica(anomes, status_fila);

CREATE INDEX IF NOT EXISTS idx_midway_auditoria_evento_tipo_data
    ON ddcq.midway_auditoria_evento(tipo_evento, criado_em);
```

## Idempotencia

Para evitar duplicidade em reprocessamentos, algumas regras devem ter chave funcional.

Exemplo para ajuste automatico RA `92/82`:

```text
ANOMES
NUM_SEQ_INTRP
NOVO_COD_COMP_INTRP
NOVO_COD_CAUSA_INTRP
ORIGEM_AJUSTE
```

Posteriormente pode ser criado um indice unico parcial:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_midway_ajuste_auto_9282
ON ddcq.midway_ajuste_iqs (
    anomes,
    num_seq_intrp,
    novo_cod_comp_intrp,
    novo_cod_causa_intrp,
    origem_ajuste
)
WHERE origem_ajuste = 'AUTO_EXECUTIVO_9282';
```

## Estrategia Para Grandes Volumes

Evitar carregar tudo no PostgreSQL sem necessidade.

Preferir:

- marts consolidados;
- cargas incrementais;
- tabelas por `ANOMES`;
- staging temporario;
- `COPY` no servidor quando permitido;
- indices criados depois da carga;
- limpeza de staging depois da validacao.

Exemplo de carga eficiente:

```sql
CREATE TABLE ddcq.stg_9282_importacao (
    anomes varchar(6),
    num_seq_intrp varchar(80),
    num_ocorrencia_adms varchar(80),
    cod_comp_sugerido varchar(20),
    cod_causa_sugerida varchar(20),
    fonte_sugestao varchar(80),
    nivel_evidencia varchar(80),
    score_sugestao numeric(10, 2)
);
```

Depois a carga oficial deve fazer `INSERT INTO ... SELECT ...` com validacao.

## Variaveis .env Propostas

```env
MIDWAY_DATABASE_URL=postgresql://midway_app:trocar@localhost:5432/midway
MIDWAY_DB_SCHEMA=ddcq
MIDWAY_ENV=local
MIDWAY_DB_POOL_SIZE=5
MIDWAY_DB_ECHO=0
```

No ambiente empresa, apenas trocar a URL e ambiente:

```env
MIDWAY_DATABASE_URL=postgresql://midway_app:trocar@servidor_dbguo:5432/dbguo
MIDWAY_DB_SCHEMA=ddcq
MIDWAY_ENV=empresa
```

## Checklist Para TI

Solicitar:

- criacao ou liberacao do schema `ddcq`;
- usuario de aplicacao com permissao de escrita no schema;
- usuario de leitura, se necessario;
- politica de backup;
- limite de conexoes;
- limite de tamanho;
- metodo de carga aceito:
  - `COPY`;
  - arquivo em pasta de rede;
  - ferramenta corporativa;
  - carga via aplicacao;
- liberacao de rede entre servidor da aplicacao e PostgreSQL;
- definicao de onde ficarao arquivos exportados.

## Checklist Local

- Instalar PostgreSQL.
- Criar database `midway`.
- Criar usuario `midway_app`.
- Criar schema `ddcq`.
- Rodar DDL inicial.
- Criar `.env`.
- Testar conexao.
- Criar primeira carga pequena de teste.

## Politica de Dados

Para ambiente residencial:

- usar dados mascarados;
- usar amostras pequenas;
- nao copiar base real completa sem autorizacao;
- nao guardar senha real da empresa;
- nao versionar `.env`.

Para ambiente empresa:

- usar credencial corporativa;
- registrar auditoria;
- manter backup;
- restringir permissao de escrita;
- versionar DDL no repositorio.

## Scripts Versionados

Scripts criados no repositorio:

```text
SQL/postgres/ddcq/001_schema.sql
SQL/postgres/ddcq/002_tabelas_operacionais.sql
SQL/postgres/ddcq/003_indices.sql
SQL/postgres/ddcq/004_seed_parametros.sql
SQL/postgres/ddcq/005_views_9282.sql
```

Modulo Python de conexao:

```text
midway/db/postgres.py
```

## Acompanhamento RA 92/82 no DBeaver

Apos aplicar `SQL/postgres/ddcq/005_views_9282.sql`, atualizar a conexao no DBeaver e abrir:

```text
postgres > midway > Esquemas > ddcq > Views
```

Views criadas:

```sql
SELECT * FROM ddcq.vw_midway_9282_painel ORDER BY anomes;
SELECT * FROM ddcq.vw_midway_9282_ajustes_auto ORDER BY criado_em DESC;
SELECT * FROM ddcq.vw_midway_9282_fila_tecnica ORDER BY prioridade DESC, criado_em;
SELECT * FROM ddcq.vw_midway_9282_auditoria ORDER BY criado_em DESC;
```

Uso recomendado:

- `vw_midway_9282_painel`: visao executiva com autorizacoes, ajustes e fila tecnica.
- `vw_midway_9282_ajustes_auto`: trilha dos registros automaticos autorizados.
- `vw_midway_9282_fila_tecnica`: casos problemáticos para tratamento manual.
- `vw_midway_9282_auditoria`: evidencia da autorização em massa.
