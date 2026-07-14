# 03 - Exportacao teste por motivo preenchido

## Objetivo

Gerar uma segunda opcao de exportacao para teste no IQS contendo somente registros em que `NUM_MOTIVO_TRAT_DIF_UCI` esta preenchido.

Essa exportacao nao substitui a exportacao oficial. Ela gera arquivos separados com prefixo `TESTE_MOTIVO_`.

## Entrada

Usa a tabela materializada:

`data/processed/iqs_adms_processed_<ANOMES>.duckdb`

Tabela esperada:

`adms_iqs_export`

## Filtro aplicado

```sql
NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NOT NULL
```

Ou seja, exporta apenas registros em que `NUM_MOTIVO_TRAT_DIF_UCI` nao e nulo nem vazio.

## Saida

Os arquivos sao gravados em:

`data/export`

Formato:

`TESTE_MOTIVO_Interrupcoes_IQS_<timestamp>_<regional>.CSV`

O separador e `|` e o terminador de linha e UNIX (`LF`).

## Execucao

Pelo CMD:

```bat
exportar_motivo.bat
```

Ou diretamente:

```bat
python -m midway.auditoria.motivo
```

## Observacao

Se a tabela `adms_iqs_export` ainda nao existir, execute antes:

```bat
run.bat tratamento
```

ou:

```bat
run.bat exportar
```
