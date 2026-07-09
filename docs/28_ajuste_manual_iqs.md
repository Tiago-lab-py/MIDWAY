# 28 - Ajuste Manual IQS

## Objetivo

Criar uma tela operacional para registrar decisões manuais da pós-operação e gerar um arquivo corrigido no layout IQS.

A tela usa as evidências já materializadas no MIDWAY:

- `gold_interrupcao_tratada`;
- `gold_apuracao_uc`;
- `gold_reclamacao_ocorrencia_resumo`;
- `data/raw/adms_servicos_raw_<ANOMES>.duckdb`;
- `adms_iqs_export`.

## Tela

A página fica em:

```text
10 Ajuste Manual IQS
```

Ela permite:

- consultar candidatos vindos da página `09 Qualidade de Interrupções`;
- registrar ajuste por ocorrência, interrupção ou UC;
- informar causa, componente, clima, tipo, motivo, protocolos e data/hora;
- consultar evidências da interrupção/ocorrência, serviços ADMS e reclamações vinculadas;
- marcar o ajuste como aprovado para exportação;
- editar a grade de ajustes;
- gerar CSV no layout IQS.

## Evidências para decisão

Ao selecionar um candidato, a tela mostra uma prévia comparativa para apoiar a interpretação do analista:

| Cor | Significado |
| --- | --- |
| Branco | valor atual da interrupção/ocorrência no IQS |
| Verde | informação pré-tratada/evidência das gold de reclamações/serviços |
| Vermelho | sugestão do algoritmo de qualidade |
| Amarelo | campo alterado manualmente em ajuste registrado |

As abas de evidência exibem:

- resumo da interrupção/ocorrência com causa e componente descritivos;
- serviços ADMS vinculados à interrupção, com causa/componente descritivos quando disponíveis;
- resumo e detalhe das reclamações vinculadas à ocorrência, incluindo texto, retorno, causa provável e aderência.

## Persistência local

Os ajustes ficam em DuckDB local:

```text
data/control/iqs_ajustes_manuais_<ANOMES>.duckdb
```

Tabela:

```text
ajustes_iqs_manuais
```

Essa base é operacional e não deve ser versionada.

## Escopos

| Escopo | Aplicação |
| --- | --- |
| `OCORRENCIA` | aplica a todas as linhas da ocorrência |
| `INTERRUPCAO` | aplica às linhas da interrupção informada |
| `UC` | aplica somente à UC/interrupção informada |

## Campos ajustáveis

| Campo da tela | Campo IQS exportado |
| --- | --- |
| `NOVO_COD_CAUSA_INTRP` | `COD_CAUSA_INTRP` |
| `NOVO_COD_COMP_INTRP` | `COD_COMP_INTRP` |
| `NOVO_COD_COND_CLIMA_INTRP` | `COD_COND_CLIMA_INTRP` |
| `NOVO_COD_TIPO_INTRP` | `COD_TIPO_INTRP` |
| `NOVO_NUM_MOTIVO_TRAT_DIF_UCI` | `NUM_MOTIVO_TRAT_DIF_UCI` |
| `NOVO_TIPO_PROTOC_JUSTIF_UCI` | `TIPO_PROTOC_JUSTIF_UCI` |
| `NOVO_NUM_PROTOC_JUSTIF_RESP_UCI` | `NUM_PROTOC_JUSTIF_RESP_UCI` |
| `NOVO_TIPO_PROTOC_JUSTIF_INTRP` | `TIPO_PROTOC_JUSTIF_INTRP` |
| `NOVO_NUM_PROTOC_JUSTIF_RESP_INTRP` | `NUM_PROTOC_JUSTIF_RESP_INTRP` |
| `NOVO_VALID_POS_OPERACAO` | `VALID_POS_OPERACAO` |
| `NOVO_ESTADO_INTRP` | `ESTADO_INTRP` |
| `NOVA_DATA_HORA_INIC_INTRP` | `DATA_HORA_INIC_INTRP` |
| `NOVA_DATA_HORA_FIM_INTRP` | `DATA_HORA_FIM_INTRP` |
| `NOVA_DTHR_INICIO_INTRP_UC` | `DTHR_INICIO_INTRP_UC` |

Os campos de data/hora devem ser informados como `dd/mm/aaaa hh:mm:ss`.

## Exportação

A exportação usa somente ajustes aprovados.

Arquivos IQS:

```text
data/export/ajuste_manual_iqs/AJUSTE_MANUAL_Interrupcoes_IQS_<ANOMES>_<timestamp>_<REGIONAL>.CSV
```

Auditoria:

```text
data/marts/Ajuste_Manual_IQS_<ANOMES>_<timestamp>_AUDITORIA.CSV
```

Resumo:

```text
data/marts/Ajuste_Manual_IQS_<ANOMES>_<timestamp>_RESUMO.TXT
```

## Cuidados

- A tela não altera a base processada.
- A exportação aplica ajustes sobre `adms_iqs_export`.
- Se uma linha não existir em `adms_iqs_export`, ela não será exportada.
- Conferir o arquivo de auditoria antes da carga no IQS.
- O CSV final usa o helper oficial MIDWAY para separador `|`, fim de linha UNIX/LF e encoding `ISO-8859-1`.
