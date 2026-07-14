# 14 - Fluxo oficial atual do MIDWAY

## Objetivo

Este documento consolida o fluxo operacional vigente do MIDWAY.

Ele deve ser usado como referencia principal para rodar, validar e auditar o processamento mensal.

O fluxo vigente deve ser lido com o norte multi-anomalias descrito em `docs/33_reorientacao_anomalias_oms_iqs.md`: `92/82` e um modulo especifico, enquanto o produto principal e detectar, revisar e exportar tratamentos de todas as anomalias relevantes dos dados OMS/ADMS para o IQS.

O catalogo oficial dos modulos esta em `docs/modulos/README.md`, a regra comum de decisao/exportacao esta em `docs/34_governanca_exportacao_iqs.md`, o contrato fisico do arquivo IQS esta em `docs/35_contrato_exportacao_iqs.md` e os calculos regulatórios seguem `docs/36_regras_prodist_copel.md`.

## Camadas oficiais

```text
data/raw/iqs_adms_raw_<ANOMES>.duckdb
```

Base bruta ADMS/HIADMS, com a tabela `hiadms_raw`.

```text
data/raw/iqs_raw_<ANOMES>.duckdb
```

Base bruta das extracoes auxiliares do IQS.

Tabelas:

- `raw_iqs_consumidores`;
- `raw_iqs_uc_fatura`;
- `raw_iqs_vrc`;
- `raw_iqs_metas_uc`.

```text
data/processed/iqs_adms_processed_<ANOMES>.duckdb
```

Base processada do MIDWAY.

Camadas principais:

- `adms_iqs_alterados`;
- `adms_iqs_export`;
- `silver_iqs_consumidores`;
- `silver_iqs_uc_fatura`;
- `silver_iqs_vrc`;
- `silver_iqs_metas_uc`;
- `silver_interrupcao_tratada`;
- `silver_interrupcao_uc_apuravel`;
- `gold_apuracao_uc`;
- `gold_apuracao_previa`;
- `gold_continuidade_uc`;
- `gold_ressarcimento_prodist`.

```text
data/export
```

Arquivos finais e BDOs.

```text
data/marts
```

Auditorias, metricas, amostras e resumos.

```text
PostgreSQL ddcq
```

Banco operacional para:

- catalogo de anomalias;
- evidencias;
- sugestoes;
- decisoes humanas;
- ajustes aprovados;
- auditoria;
- pacotes de exportacao IQS.

## Dicionario operacional

### `COD_TIPO_INTRP`

Natureza da interrupcao:

| Codigo | Significado |
| --- | --- |
| `1` | Acidental |
| `2` | Programado |
| `3` | Voluntario |

A regra de sobreposicao temporal deve comparar apenas eventos da mesma UC e do mesmo `COD_TIPO_INTRP`.

### `TIPO_PROTOC_JUSTIF_UCI`

Familia de indicador:

| Codigo | Uso |
| --- | --- |
| `0` | Base liquida para `DIC`, `FIC` e `DMIC` |
| `1` | Dia Critico, base para `DICRI` |
| `5` | ISE, base para `DISE` |
| `6` | ISE, base para `DISE` |

### `NUM_MOTIVO_TRAT_DIF_UCI`

Regra principal de elegibilidade da base apuravel.

Para entrar no calculo de indicadores, deve estar nulo.

Quando preenchido, indica tratamento diferenciado e o registro nao deve entrar na base apuravel.

## Regras vigentes

### Sobreposicao total por equipamento

Regra historica/removida do fluxo principal.

O processo nao marca mais interrupcoes como `ESTADO_INTRP = 7` por criterio de equipamento e nao gera `91/R` por essa regra.

### Sobreposicao total por UC

Regra vigente.

Quando uma UC esta totalmente contida por outra interrupcao da mesma UC, mesmo `COD_TIPO_INTRP` e mesmo `TIPO_PROTOC_JUSTIF_UCI`, o registro contido recebe:

```text
NUM_MOTIVO_TRAT_DIF_UCI = 91
INDIC_SIT_PROCES_INDIC_UCI = D
```

### Sobreposicao parcial por UC

Regra vigente.

Quando uma UC possui sobreposicao parcial com outra interrupcao da mesma UC, mesmo `COD_TIPO_INTRP` e mesmo `TIPO_PROTOC_JUSTIF_UCI`, o inicio do segundo trecho e ajustado para o fim da interrupcao anterior:

```text
DTHR_INICIO_INTRP_UC = DATA_HORA_FIM_INTRP anterior
```

O campo de manobra recebe a interrupcao anterior quando aplicavel:

```text
NUM_INTRP_INIC_MANOBRA_UCI
```

### Analise de interrupcao e ocorrencia sem UC

Apos executar as regras de sobreposicao total e parcial por UC, o processo avalia se restaram interrupcoes em `ESTADO_INTRP = 4` sem nenhuma UC apuravel.

Tambem e feita analise por ocorrencia, pois a ocorrencia agrupa uma ou mais interrupcoes.

Quando uma ocorrencia fica completamente sem UC apuravel, o sistema apenas sinaliza a possibilidade de avaliar marcacao das interrupcoes como:

```text
ESTADO_INTRP = 7
NUM_MOTIVO_TRAT_DIF_UCI = 91
INDIC_SIT_PROCES_INDIC_UCI = R
```

Essa marcacao nao e automatica no fluxo principal.

Tabelas analiticas:

```text
gold_interrupcao_sem_uc
gold_ocorrencia_sem_uc
```

Arquivos:

```text
Auditoria_Interrupcao_Sem_UC_<ANOMES>_<timestamp>.CSV
Auditoria_Ocorrencia_Sem_UC_<ANOMES>_<timestamp>.CSV
```

## Fluxo local sem Oracle

Use quando os DuckDBs ja existem em `data/raw`.

```bat
cd /d D:\MIDWAY
set REPROCESSAR=1
run.bat reprocessar
run.bat exportacoes_auxiliares
run.bat sincronizar_iqs_raw
run.bat apuracao_parcial
run.bat validar_dados
run.bat anomalias_setup
```

## Fluxo completo com extracao

Use quando houver acesso ao Oracle/IQS.

```bat
cd /d D:\MIDWAY
set REEXTRAIR=1
set REPROCESSAR=1
run.bat full_mais_apuracao
run.bat validar_dados
run.bat anomalias_setup
```

## Fluxo de anomalias e exportação IQS

Após o processamento mensal, o fluxo de anomalias deve seguir:

```text
RAW/SILVER/GOLD
  -> run.bat anomalias_setup
  -> aba Anomalias / Analise Tecnica
  -> decisao humana governada
  -> ajustes aprovados
  -> geracao de pacote IQS
  -> auditoria da exportacao
```

Cada modulo deve produzir evidencia e proposta de acao. A exportacao final deve aceitar ajustes aprovados de qualquer modulo, nao apenas de `92/82`.

## Fluxo de validacao

Comando recomendado:

```bat
run.bat validar_dados
```

Esse comando executa:

1. testes automatizados;
2. metricas de qualidade.

Se houver falha critica, o comando retorna erro.

Comandos equivalentes separados:

```bat
run.bat testar_dados
run.bat metricas_qualidade
```

## Painel visual

Para avaliar resultados sem abrir CSVs grandes:

```bat
run.bat painel
```

O painel mostra:

- metricas de qualidade;
- sobreposicao residual;
- fechamento `DIC/FIC`;
- ressarcimento PRODIST;
- arquivos em `data/marts`;
- consulta SQL somente leitura.

## Checklist de fechamento mensal

```text
[ ] Confirmar ANOMES no .env
[ ] Confirmar data/raw/iqs_adms_raw_<ANOMES>.duckdb
[ ] Confirmar count de raw_db.hiadms_raw
[ ] Confirmar data/raw/iqs_raw_<ANOMES>.duckdb
[ ] Rodar run.bat reprocessar ou run.bat full_mais_apuracao
[ ] Conferir Exportacao_IQS_*_RESUMO.TXT
[ ] Rodar run.bat exportacoes_auxiliares
[ ] Rodar run.bat sincronizar_iqs_raw
[ ] Rodar run.bat apuracao_parcial
[ ] Rodar run.bat validar_dados
[ ] Rodar run.bat anomalias_setup
[ ] Revisar aba Anomalias por tipo de modulo
[ ] Aprovar/rejeitar propostas governadas
[ ] Conferir Metricas_Qualidade_Dados_*_RESUMO.TXT
[ ] Conferir BDO_interupcao_<yyyymmdd>.csv
[ ] Conferir Gold_Continuidade_UC_*_RESUMO.TXT
[ ] Conferir Gold_Ressarcimento_PRODIST_*_RESUMO.TXT
[ ] Gerar pacote IQS somente com ajustes aprovados
[ ] Abrir run.bat painel para revisao visual
```

## Criterios de aceite

Para fechamento operacional:

- `run.bat validar_dados` deve passar;
- metricas criticas devem ser `0`;
- `gold_apuracao_uc` deve fechar com `gold_continuidade_uc`;
- sobreposicao residual por mesma UC e mesmo `COD_TIPO_INTRP` deve ser `0`;
- `NUM_MOTIVO_TRAT_DIF_UCI` deve estar nulo em `gold_apuracao_uc`;
- `gold_ressarcimento_prodist` deve ter a mesma quantidade de UCs de `gold_continuidade_uc`.

Alertas que nao bloqueiam automaticamente:

- duracoes liquidas maiores ou iguais a 24h;
- `DICRI/DISE` ainda agregados por UC no ressarcimento PRODIST.

## Pendencias conhecidas

- Refatorar `midway.apuracao.previa`.
- Refatorar `midway.transform.tratamento`.
- Evoluir `DICRI/DISE` para granularidade por evento no ressarcimento PRODIST.
- Criar testes pequenos com DuckDB fixture para regras unitarias de sobreposicao.
