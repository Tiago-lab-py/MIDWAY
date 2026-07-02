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

Os dois pacotes usam o mesmo layout aceito pelo IQS:

- separador `|`;
- terminador de linha UNIX `LF`;
- datas em `DD/MM/YYYY HH24:MI:SS`;
- `SELECT DISTINCT` para evitar linhas 100% duplicadas.

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
