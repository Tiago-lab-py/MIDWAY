# Migração COPEL - DBGUO/DDCQ

## Objetivo

Preparar o MIDWAY para sair do ambiente local de desenvolvimento e rodar dentro da infraestrutura COPEL, usando o banco corporativo DBGUO/PostgreSQL com schema operacional `ddcq`.

Este documento é o direcionamento de implantação. Ele não deve conter senha, host real sensível ou credencial produtiva.

## Princípio de Arquitetura

O MIDWAY deve separar três camadas:

| Camada | Responsabilidade | Destino COPEL |
| --- | --- | --- |
| Processamento analítico | RAW, SILVER, GOLD, cálculos pesados e arquivos intermediários | DuckDB/arquivos controlados em diretório corporativo |
| Governança operacional | usuários, perfis, decisões, fila técnica, aprovações, auditoria e geração IQS | PostgreSQL DBGUO no schema `ddcq` |
| Fontes oficiais | IQS, ADMS, DBGUO, serviços, cadastros e referências | Conexões corporativas homologadas |

O PostgreSQL `ddcq` não deve receber todo o volume bruto sem necessidade. Ele é a fonte oficial das decisões, estados de processamento e trilhas de auditoria.

## Ambiente Alvo

| Item | Direcionamento |
| --- | --- |
| Banco | DBGUO/PostgreSQL corporativo |
| Schema | `ddcq` |
| Usuário aplicação | Preferencialmente usuário técnico dedicado, por exemplo `midway_app` |
| Usuário dono/admin | Definido pela TI, por exemplo `ddcq_owner` |
| Acesso humano | Via DBeaver/cliente homologado, com permissões por perfil |
| API | FastAPI usando `MIDWAY_DATABASE_URL` |
| Frontend | React consumindo apenas a API, sem conexão direta ao banco |

## Variáveis de Ambiente

Configurar fora do repositório, preferencialmente por cofre corporativo, variável de ambiente do servidor ou arquivo `.env` protegido.

```env
MIDWAY_ENV=copel
MIDWAY_DATABASE_URL=postgresql://midway_app:<senha>@<servidor_dbguo>:5432/<database>
MIDWAY_DB_SCHEMA=ddcq
ANOMES=202606
```

Quando houver conexão Oracle/IQS e DBGUO de reclamações:

```env
IQS_UID=<usuario_iqs>
IQS_PWD=<senha_iqs>
IQS_DB=<tns_iqs>
IQS_CONFIG_DIR=<diretorio_tns>
IQS_ORACLE_THICK_MODE=1
IQS_ORACLE_CLIENT_LIB_DIR=<instant_client_homologado>

DDCQ_USER=<usuario_dbguo_reclamacoes>
DDCQ_USER_PASS=<senha_dbguo_reclamacoes>
DBGUO_DB=<tns_dbguo>
DBGUO_CONFIG_DIR=<diretorio_tns>
```

Observação: nomes exatos de host, database, TNS e usuários devem ser definidos pela TI/DBA COPEL.

## Provisão do Banco

### 1. Criar ou liberar database

A TI/DBA deve definir se o MIDWAY usará:

- database corporativo existente no DBGUO; ou
- database dedicado para o MIDWAY; ou
- schema `ddcq` dentro de database operacional homologado.

### 2. Criar schema

Script base:

```text
SQL/postgres/ddcq/001_schema.sql
```

Atenção: o script local contém exemplos de autorização (`midway_app`) e `ALTER ROLE`. Em ambiente COPEL, a TI pode precisar adaptar owner, grants e search path conforme política corporativa.

### 3. Aplicar modelo operacional

Executar nesta ordem:

1. `SQL/postgres/ddcq/001_schema.sql`
2. `SQL/postgres/ddcq/002_tabelas_operacionais.sql`
3. `SQL/postgres/ddcq/003_indices.sql`
4. `SQL/postgres/ddcq/004_seed_parametros.sql`
5. `SQL/postgres/ddcq/006_governanca.sql`
6. `SQL/postgres/ddcq/007_iqs_geracao_governada.sql`
7. `SQL/postgres/ddcq/008_nucleo_anomalias_v7.sql`

O arquivo `SQL/postgres/ddcq/005_views_9282.sql` é suporte histórico/especializado e não deve ser tratado como centro do produto.

## Permissões Mínimas

| Perfil técnico | Permissões esperadas |
| --- | --- |
| `ddcq_owner` | criar schema, tabelas, índices, views e grants |
| `midway_app` | `USAGE` no schema, `SELECT`, `INSERT`, `UPDATE`, `DELETE` nas tabelas operacionais, uso de sequences |
| consulta/auditoria | `SELECT` em views/tabelas autorizadas |

Recomendação: separar permissões de aplicação, DBA e consulta humana.

## Validação Pós-Provisão

No servidor da aplicação ou estação autorizada:

```bat
run.bat postgres_validar
```

Critérios esperados:

- conexão com `MIDWAY_DATABASE_URL`;
- schema `ddcq` acessível;
- tabelas operacionais criadas;
- views/parâmetros mínimos disponíveis;
- usuário da aplicação sem erro de permissão.

## DBeaver

Para inspeção controlada:

| Campo | Valor esperado |
| --- | --- |
| Host | servidor DBGUO/PostgreSQL definido pela TI |
| Porta | normalmente `5432`, salvo padrão interno diferente |
| Database | database definido pela TI |
| Usuário | usuário autorizado, não necessariamente `midway_app` |
| Schema | `ddcq` |

Depois de conectar:

```sql
SELECT current_user, current_database(), current_schema();

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'ddcq'
ORDER BY table_name;
```

## Fluxo de Migração

1. Definir host/database/schema com TI.
2. Criar usuário técnico e políticas de senha/rotação.
3. Configurar `MIDWAY_DATABASE_URL` e `MIDWAY_DB_SCHEMA`.
4. Aplicar scripts `SQL/postgres/ddcq`.
5. Rodar `run.bat postgres_validar`.
6. Executar `run.bat postgres_governanca`.
7. Executar `run.bat admin_bootstrap` somente para primeiro acesso controlado.
8. Configurar credenciais IQS/DBGUO fora do repositório.
9. Extrair bases oficiais.
10. Materializar RAW/SILVER/GOLD.
11. Rodar módulos regulatórios e anomalias.
12. Registrar decisões governadas.
13. Gerar pacote IQS somente com aprovação.
14. Homologar arquivo no IQS.

## Homologação IQS

Antes de carga real:

- conferir contrato em `docs/35_contrato_exportacao_iqs.md`;
- validar encoding `ISO-8859-1`;
- validar quebra UNIX/LF;
- validar datas em `dd/mm/aaaa hh:mm:ss`;
- validar arquivo único ou divisão por regional conforme decisão COPEL;
- validar ausência de coluna extra;
- executar carga controlada no ambiente homologado.

## Segurança

Não fazer:

- gravar senha real em `.env.example`, documentação ou commit;
- usar usuário pessoal como usuário técnico da API em produção;
- permitir frontend conectar direto no PostgreSQL;
- liberar `ddcq_owner` para execução normal da aplicação;
- exportar IQS sem aprovação humana registrada;
- tratar arquivos locais de desenvolvimento como fonte oficial COPEL.

Fazer:

- usar cofre corporativo ou variável protegida;
- registrar auditoria de login, decisão, aprovação e geração IQS;
- revisar CORS para origem corporativa;
- restringir DBeaver a usuários autorizados;
- manter evidência de cada lote processado.

## Critério de Pronto para Rodar na COPEL

- [ ] Host/database DBGUO/PostgreSQL definido.
- [ ] Schema `ddcq` criado.
- [ ] Usuário técnico `midway_app` ou equivalente criado.
- [ ] Scripts `SQL/postgres/ddcq` aplicados.
- [ ] `MIDWAY_DATABASE_URL` configurado fora do repositório.
- [ ] `run.bat postgres_validar` aprovado.
- [ ] Usuários/perfis de governança criados.
- [ ] Conexões IQS/DBGUO homologadas.
- [ ] Diretórios corporativos de entrada/saída definidos.
- [ ] Exportação IQS homologada com lote controlado.

