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

## Execução

```bat
cd /d D:\MIDWAY_novo
set ANOMES=202606
set REEXTRAIR_DBGUO=1
extrair_dbguo_reclamacoes.bat
```

## Saídas

```text
data\raw\dbguo_raw_202606.duckdb
data\marts\DBGUO_Reclamacoes_202606_<timestamp>_AMOSTRA.CSV
data\marts\DBGUO_Reclamacoes_202606_<timestamp>_RESUMO.TXT
```

