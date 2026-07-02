# Controle de execucao

## Objetivo

O controle de execucao impede que processos pesados sejam executados fora de ordem ou repetidos sem confirmacao explicita.

Ele protege dois pontos criticos:

1. `midway.transform.tratamento` nao pode rodar sem uma extracao finalizada com sucesso.
2. `midway.extract.adms` e `midway.transform.tratamento` nao repetem processamento pesado por acidente.

## Estrutura

```text
data/
  control/
    extract_<ANOMES>.done.json
    extract_<ANOMES>.lock
    tratamento_<ANOMES>.done.json
    tratamento_<ANOMES>.lock
  logs/
    extract_<ANOMES>_<YYYYMMDDHHMMSS>.log
    tratamento_<ANOMES>_<YYYYMMDDHHMMSS>.log
  marts/
  temp/
```

O diretorio `data/temp` e usado pelo DuckDB como area temporaria para consultas grandes.

## Arquivos `.lock`

O arquivo `.lock` indica que uma etapa esta em execucao.

Exemplos:

```text
data/control/extract_202605.lock
data/control/tratamento_202605.lock
```

Enquanto o lock existir, uma nova execucao da mesma etapa e bloqueada.

Se uma execucao cair por erro, o lock e removido automaticamente. Se o computador for desligado ou o processo for encerrado de forma forcada, o lock pode permanecer.

Remova um lock manualmente somente depois de confirmar que nao existe processo Python rodando para a mesma etapa.

## Arquivos `.done.json`

O arquivo `.done.json` indica que uma etapa terminou com sucesso.

Exemplo de extracao:

```json
{
  "etapa": "extract",
  "anomes": "202605",
  "status": "success",
  "started_at": "2026-06-26T14:30:00",
  "finished_at": "2026-06-26T15:12:00",
  "rows": 20917798,
  "duckdb_path": "data/raw/iqs_adms_raw_202605.duckdb",
  "table": "hiadms_raw"
}
```

Exemplo de tratamento:

```json
{
  "etapa": "tratamento",
  "anomes": "202605",
  "status": "success",
  "started_at": "2026-06-26T15:20:00",
  "finished_at": "2026-06-26T15:45:00",
  "rows": 12345,
  "processed_duckdb_path": "data/processed/iqs_adms_processed_202605.duckdb",
  "export_files": [
    "data/export/Interrupcoes_IQS_20260626154500_CSL.CSV"
  ],
  "export_summary_path": "data/export/Exportacao_IQS_20260626154500_RESUMO.TXT",
  "auditoria_outliers_bruto": {
    "path": "data/marts/Auditoria_Outliers_Bruto_IQS_20260626154500.CSV",
    "summary_path": "data/marts/Auditoria_Outliers_Bruto_IQS_20260626154500_RESUMO.TXT",
    "rows": 10,
    "thresholds": {
      "duracao_horas": 24,
      "qtd_ucs": 10000,
      "qtd_intrp_contidas": 100,
      "qtd_ucs_afetadas": 50000
    }
  },
  "auditoria_estado_7": {
    "path": "data/marts/Auditoria_ESTADO_7_IQS_20260626154500.CSV",
    "anomalies_path": "data/marts/Auditoria_ESTADO_7_IQS_20260626154500_ANOMALIAS.CSV",
    "pending_anomalies_path": "data/marts/Auditoria_ESTADO_7_IQS_20260626154500_ANOMALIAS_PENDENTES.CSV",
    "accepted_anomalies_path": "data/marts/Auditoria_ESTADO_7_IQS_20260626154500_ANOMALIAS_ACEITAS.CSV",
    "summary_path": "data/marts/Auditoria_ESTADO_7_IQS_20260626154500_RESUMO.TXT",
    "rows": 100,
    "total_anomalies": 6,
    "accepted_anomalies": 6,
    "alerts": 0,
    "acceptance_input_path": "data/input/estado_7_aceitas.csv"
  },
  "auditoria_manobra_hcai": {
    "path": "data/marts/Auditoria_Manobra_HCAI_IQS_20260626154500.CSV",
    "anomalies_path": "data/marts/Auditoria_Manobra_HCAI_IQS_20260626154500_ANOMALIAS.CSV",
    "summary_path": "data/marts/Auditoria_Manobra_HCAI_IQS_20260626154500_RESUMO.TXT",
    "rows": 100,
    "alerts": 0
  },
  "auditoria_uc_91_d": {
    "path": "data/marts/Auditoria_UC_91_D_IQS_20260626154500.CSV",
    "anomalies_path": "data/marts/Auditoria_UC_91_D_IQS_20260626154500_ANOMALIAS.CSV",
    "summary_path": "data/marts/Auditoria_UC_91_D_IQS_20260626154500_RESUMO.TXT",
    "rows": 100,
    "alerts": 0
  }
}
```

O controle `tratamento_<ANOMES>.done.json` so e gravado se a auditoria de `ESTADO_INTRP = 7` estiver sem anomalias.

## Regra da extracao

Comando:

```bash
python -m midway.extract.adms
```

Comportamento:

- se `extract_<ANOMES>.done.json` existir, a extracao nao e refeita;
- para refazer a extracao, defina `REEXTRAIR=1`;
- durante a extracao, o arquivo bruto e criado como `.incomplete`;
- somente no fim, depois de validar a quantidade de linhas, o arquivo `.incomplete` e renomeado para `.duckdb`;
- o arquivo `extract_<ANOMES>.done.json` so e criado depois da extracao finalizada.

Arquivo temporario:

```text
data/raw/iqs_adms_raw_<ANOMES>.duckdb.incomplete
```

Arquivo final:

```text
data/raw/iqs_adms_raw_<ANOMES>.duckdb
```

## Regra do tratamento

Comando:

```bash
python -m midway.transform.tratamento
```

Comportamento:

- exige `extract_<ANOMES>.done.json` com `status = "success"`;
- exige o DuckDB bruto em `data/raw`;
- se `tratamento_<ANOMES>.done.json` existir, o tratamento nao e refeito;
- para refazer somente o tratamento, defina `REPROCESSAR=1`;
- gera log, DuckDB processado e CSVs finais;
- cria `tratamento_<ANOMES>.done.json` somente ao final da etapa.

## Variaveis de controle

### `REEXTRAIR`

Forca nova extracao Oracle.

```env
REEXTRAIR=1
```

Use somente quando for necessario descartar e recriar o DuckDB bruto.

### `REPROCESSAR`

Forca novo tratamento usando o DuckDB bruto ja extraido.

```env
REPROCESSAR=1
```

Use quando as regras de tratamento ou o layout de exportacao mudarem.

## Execucao recomendada

Primeira execucao da competencia:

```bash
python -m midway.extract.adms
python -m midway.transform.tratamento
```

Reprocessar apenas o tratamento:

```env
REPROCESSAR=1
```

```bash
python -m midway.transform.tratamento
```

Refazer tudo:

```env
REEXTRAIR=1
REPROCESSAR=1
```

```bash
python -m midway.extract.adms
python -m midway.transform.tratamento
```

## Logs

Cada execucao gera um arquivo em `data/logs`.

Exemplos:

```text
data/logs/extract_202605_20260626143000.log
data/logs/tratamento_202605_20260626154500.log
```

Os logs registram:

- inicio e fim da etapa;
- quantidade de registros;
- caminho dos arquivos gerados;
- coluna regional usada;
- mensagens de bloqueio por repeticao ou lock.

## Recuperacao de erro

### DuckDB bruto ja existe sem controle

Esse caso acontece quando o arquivo bruto foi gerado antes da criacao do controle de execucao.

Sintomas:

```text
DuckDB bruto existe sem controle finalizado
Controle nao encontrado: data\control\extract_<ANOMES>.done.json
```

Para validar o DuckDB bruto existente e criar o controle sem reextrair:

```bash
run.bat registrar
```

O comando valida a tabela `hiadms_raw`, conta os registros e cria:

```text
data/control/extract_<ANOMES>.done.json
```

Depois disso, execute:

```bash
run.bat tratamento
```

### Erro durante a extracao

1. Verifique o log em `data/logs`.
2. Confirme se existe arquivo `.incomplete` em `data/raw`.
3. Se for reiniciar a extracao, defina `REEXTRAIR=1`.
4. Rode `python -m midway.extract.adms`.

### Erro durante o tratamento

1. Verifique o log em `data/logs`.
2. Corrija a causa do erro.
3. Defina `REPROCESSAR=1`.
4. Rode `python -m midway.transform.tratamento`.

### Lock pendente

Se aparecer mensagem de lock pendente:

1. confirme que nao existe processo Python rodando;
2. remova o arquivo `.lock` correspondente em `data/control`;
3. execute novamente a etapa.
