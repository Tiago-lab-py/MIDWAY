# 04 - Exportacao por pacote de sobreposicao

## Objetivo

Gerar arquivos separados para teste/carga no IQS conforme o tipo de tratamento aplicado.

## Pacote 1 - Sobreposicao equipamento e UC total

Pasta:

`data/export/sobreposicao_eqp_uc`

Inclui registros com uma das acoes:

- `ACAO_SOBREPOSICAO_INTERRUPCAO`
- `ACAO_SOBREPOSICAO_TOTAL_UC`
- `ACAO_REDIREC_MANOBRA_ESTADO_7`

Esse pacote cobre:

1. sobreposicao total por equipamento;
2. sobreposicao total por UC.
3. redirecionamento de `NUM_INTRP_INIC_MANOBRA_UCI` que apontava para interrupcao marcada como `ESTADO_INTRP = 7`.

## Pacote 2 - Sobreposicao UC parcial

Pasta:

`data/export/sobreposicao_UC_parcial`

Inclui registros com:

- `ACAO_AJUSTE_PARCIAL`

Esse pacote cobre a terceira etapa do tratamento, que ajusta:

- `DTHR_INICIO_INTRP_UC`;
- `NUM_INTRP_INIC_MANOBRA_UCI`.

## Layout

Os pacotes usam obrigatoriamente o layout oficial aceito pelo IQS. O arquivo deve ser gerado exatamente com:

- separador `|`;
- terminador de linha UNIX `LF` (`\n`), sem `CRLF`;
- encoding `ISO-8859-1`, equivalente ao pos-processamento `iconv -f UTF-8 -t ISO-8859-1//TRANSLIT`;
- caracteres fora de `ISO-8859-1` transliterados/removidos para evitar caracteres especiais rejeitados na integracao;
- datas em `DD/MM/AAAA HH24:MI:SS`;
- 58 colunas, sem coluna extra, sem coluna faltante e na ordem fixa abaixo;
- campos sem valor gravados como um espaco simples (` `), nunca como campo vazio entre separadores (`||`);
- campos inteiros gravados sem decimal `.0`, especialmente `NUM_INTRP_INIC_MANOBRA_UCI` e `NUM_GEO_CHV_INTRP`;
- `SELECT DISTINCT` para evitar linhas 100% duplicadas.

Header oficial:

```text
PID_INTRP_CONJTO_PIN|PID_POSTO_PIN|INDIC_AREA_REDE_POSTO_PIN|ALIM_INTRP_PIN|ESTADO_INTRP|ALIM_INTRP|CAR_SE|INDIC_INTRP_SE_ALIM|NUM_OCORRENCIA_ADMS|INDIC_INTRP_AT|CONS_INTRP|KVA_INTRP|NUM_OPER_CHV_INTRP|NUM_FUNCAO_ELET_HCAI|DESC_INTRP|VALID_POS_OPERACAO|DATA_HORA_INIC_INTRP|DATA_HORA_FIM_INTRP|TIPO_EQP_INTRP|COORD_X_INTRP|COORD_Y_INTRP|NUM_SEQ_INTRP|COD_CAUSA_INTRP|COD_COMP_INTRP|COD_AREA_ELET_INTRP|COD_GRUPO_COMP_INTRP|COD_COND_CLIMA_INTRP|COD_TIPO_INTRP|INDIC_JUMP_INTRP|NUM_PROTOC_JUSTIF_RESP_INTRP|TIPO_PROTOC_JUSTIF_INTRP|COD_CONJTO_ELET_ANEEL_INTRP|INDIC_CALC_DMIC_INTRP|INDIC_PONTO_CONEX_INTRP|NUM_GEO_CHV_INTRP|TIPO_REDE_CHV_INTRP|TIPO_CHV_INTRP|INDIC_PROPR_POSTO_INTRP|TENSAO_OPER_ALIM_INTRP|INDIC_DESLIG_ENT_SERV_INTRP|INDIC_PROPR_CHVP_INTRP|INDIC_CHVP_INIC_ALIM_INTRP|PID|PID_INTRP_UCI|NUM_INTRP_UCI|NUM_POSTO_UCI|NUM_UC_UCI|TIPO_SIT_UC_UCI|DTHR_INICIO_INTRP_UC|NUM_INTRP_INIC_MANOBRA_UCI|NUM_MOTIVO_TRAT_DIF_UCI|UC_ACESSANTE|SIGLA_REGIONAL|NUM_PROTOC_JUSTIF_RESP_UCI|TIPO_PROTOC_JUSTIF_UCI|PID_PIN|INDIC_PROCES_IND_PIN|INDIC_SIT_PROCES_INDIC_UCI
```

Campos de data obrigatoriamente no formato `DD/MM/AAAA HH24:MI:SS`:

- `DATA_HORA_INIC_INTRP`;
- `DATA_HORA_FIM_INTRP`;
- `DTHR_INICIO_INTRP_UC`.

O exportador principal do IQS valida esse layout antes de gravar o CSV. Se a ordem das colunas mudar, se faltar campo ou se houver campo extra, a exportacao deve falhar para evitar problema de integracao.

Equivalencia operacional do arquivo gerado:

```bash
dos2unix arquivo.csv
iconv -f UTF-8 -t ISO-8859-1//TRANSLIT arquivo.csv
```

O MIDWAY ja grava o arquivo final com `LF` UNIX e `ISO-8859-1` transliterado, entao esses comandos passam a ser apenas uma referencia de compatibilidade.

## Execucao

Pelo CMD:

```bat
run.bat exportacao_sobreposicao
```

## Dependencia

Antes de executar, a base processada deve existir:

`data/processed/iqs_adms_processed_<ANOMES>.duckdb`

E precisa conter as tabelas:

- `adms_iqs_alterados`;
- `adms_iqs_export`.

Se necessario, execute antes:

```bat
run.bat tratamento
```
## Exportacao de interrupcao sem UC

Alem das exportacoes separadas de sobreposicao total/parcial por UC, existe uma exportacao especifica para interrupcoes que ficam sem UC apuravel depois da sobreposicao total por UC.

Essa rotina identifica interrupcoes em `ESTADO_INTRP = 4` nas quais todas as UCs foram classificadas como:

| Campo | Valor |
| --- | --- |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `91` |
| `INDIC_SIT_PROCES_INDIC_UCI` | `D` |

Quando a interrupcao inteira fica sem UC e nao possui referencia de manobra em `NUM_INTRP_INIC_MANOBRA_UCI`, a rotina gera arquivo no layout IQS alterando:

| Campo | Valor exportado |
| --- | --- |
| `ESTADO_INTRP` | `7` |
| `NUM_MOTIVO_TRAT_DIF_UCI` | `91` |
| `INDIC_SIT_PROCES_INDIC_UCI` | `R` |

Comando:

```bat
run.bat interrupcao_sem_uc
```

Saida:

```text
data/export/interrupcao_sem_uc
```

## Organizacao das pastas

Cada pasta recebe apenas os arquivos do respectivo processamento:

| Pasta | Conteudo |
| --- | --- |
| `data/export/sobreposicao_total_uc` | somente sobreposicao total por UC (`91/D`) |
| `data/export/sobreposicao_UC_parcial` | somente ajuste parcial por UC |
| `data/export/interrupcao_sem_uc` | somente interrupcoes sem UC exportadas como `ESTADO_INTRP = 7` |

As pastas de sobreposicao total por UC e sobreposicao parcial por UC respeitam a analise por `COD_TIPO_INTRP`. A comparacao e feita sempre dentro do mesmo tipo, sem restringir artificialmente a lista de tipos.

## Ordem de gravacao

Para manter nomes sequenciais por timestamp, a gravacao deve respeitar a ordem:

1. `sobreposicao_total_uc`
2. `sobreposicao_UC_parcial`
3. `interrupcao_sem_uc`

O exportador de sobreposicoes aplica intervalo de 1 segundo entre a gravacao da sobreposicao total e parcial. O fluxo `run.bat full_mais_apuracao` tambem aplica intervalo de 1 segundo antes da exportacao de `interrupcao_sem_uc`.

Comando recomendado para gerar as tres pastas na ordem correta:

```bat
run.bat exportacoes_auxiliares
```

Auditoria:

```text
data/marts/Auditoria_ESTADO_7_Interrupcao_Sem_UC_<ANOMES>_<timestamp>.CSV
data/marts/Auditoria_ESTADO_7_Interrupcao_Sem_UC_<ANOMES>_<timestamp>_RESUMO.TXT
```

Tabela materializada no DuckDB processado:

```text
Auditoria_ESTADO_7
adms_iqs_interrupcao_sem_uc_export
```

Documento detalhado: `docs/07_interrupcao_sem_UC.md`.
