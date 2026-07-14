# Extração DBGUO Reclamações

## Objetivo

Extrair dados de reclamações do banco DBGUO e gravar o DuckDB bruto:

```text
data\raw\dbguo_raw_<ANOMES>.duckdb
```

Tabela criada:

```text
raw_dbguo_reclamacoes
```

## Variáveis `.env`

```env
DDCQ_USER=ddcq_user
DDCQ_USER_PASS=sua_senha
DBGUO_DB=nome_tns_dbguo
DBGUO_CONFIG_DIR=C:\APL\Oracle12_32\12CR2\network\admin
ANOMES=202606
```

Também são aceitos os aliases:

```env
DDCQ_DB=nome_tns_dbguo
DDCQ_CONFIG_DIR=C:\caminho\tns
```

## SQL

O SQL fica em:

```text
SQL\DBGUO_reclamacoes.sql
```

Ele recebe o parâmetro:

```text
:anomes
```

### Janela de extração

A extração deve limitar as reclamações ao mês de apuração com margem operacional de 2 dias:

```text
início = primeiro dia do ANOMES - 2 dias
fim    = primeiro dia do mês seguinte + 2 dias
```

Exemplo para `ANOMES=202606`:

```text
2026-05-30 00:00:00 <= DATA_RECLAMACAO < 2026-07-03 00:00:00
```

Essa margem cobre reclamações imediatamente antes/depois das interrupções do mês sem trazer todo o histórico DBGUO, evitando inflar o volume de `SEM_OCORRENCIA_PROVAVEL`.

## Execução

```bat
cd /d D:\MIDWAY
set ANOMES=202606
set REEXTRAIR_DBGUO=1
run.bat extrair_dbguo_reclamacoes
```

## Saídas

```text
data\raw\dbguo_raw_202606.duckdb
data\marts\DBGUO_Reclamacoes_202606_<timestamp>_AMOSTRA.CSV
data\marts\DBGUO_Reclamacoes_202606_<timestamp>_RESUMO.TXT
```
