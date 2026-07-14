# 28 - Ajuste Manual IQS

## Objetivo

A tela de Ajuste Manual IQS apoia a pós-operação na decisão de corrigir, validar e exportar alterações controladas para o IQS.

Ela não altera diretamente a base processada. O fluxo registra a decisão manual em uma base local de controle, aplica os ajustes aprovados sobre `adms_iqs_export` e gera arquivos CSV no layout IQS.

## Bases utilizadas

A tela cruza evidências já materializadas no MIDWAY:

- `adms_iqs_export`;
- `gold_interrupcao_tratada`;
- `gold_apuracao_uc`;
- `gold_reclamacao_ocorrencia_resumo`;
- `gold_iqs_referencia_componente_causa`;
- `data/raw/adms_servicos_raw_<ANOMES>.duckdb`.

A referência `gold_iqs_referencia_componente_causa` é usada para navegação assistida e validação de consistência entre grupo, componente e causa.

## Pré-requisitos

Antes de usar a tela, gerar as bases principais e a referência IQS:

```bat
set ANOMES=202606
run.bat apuracao_parcial
run.bat referencia_iqs
run.bat exportar
```

Para reextrair a referência de grupo/componente/causa:

```bat
set ANOMES=202606
run.bat reextrair_referencia_iqs
```

## Tela

A página fica em:

```text
10 Ajuste Manual IQS
```

Ela permite:

- consultar candidatos vindos da página `09 Qualidade de Interrupções`;
- filtrar candidatos por classificação de qualidade e validação pós-operação;
- registrar ajuste por ocorrência, interrupção ou UC;
- navegar por `GRUPO_COMPONENTE_REDE` → `COD_COMP_INTRP` → `COD_CAUSA_INTRP` em cascata;
- consultar evidências da ocorrência, serviços ADMS e reclamações vinculadas;
- marcar o ajuste como aprovado para exportação;
- editar a grade de ajustes;
- gerar CSV no layout IQS para carga controlada.

## Classificações de qualidade

A tela consome as classificações calculadas em `09 Qualidade de Interrupções`.

| Classificação | Uso operacional |
| --- | --- |
| `SUSPEITA_IMPROCEDENTE` | serviço ADMS com causa 85, indicando possível improcedência |
| `SUSPEITA_ATENDIDO_OUTRA_OCORRENCIA` | serviço ADMS com causa 22, indicando possível atendimento por outra ocorrência |
| `INCONSISTENCIA_COMPONENTE_CAUSA` | par componente/causa do serviço não existe na referência IQS |
| `RECLAMACAO_FORTE_SEM_SERVICO` | muitas reclamações, sem serviço ADMS vinculado |
| `RECLAMACAO_FORTE_REVISAR_CAUSA` | reclamações fortes com baixa/média aderência à causa IQS |
| `MULTIPLOS_SERVICOS_REVISAR` | mais de um serviço vinculado à interrupção |
| `CAUSA_COMPONENTE_COM_EVIDENCIA` | serviço e reclamação trazem evidência complementar |
| `RECLAMACAO_SEM_SERVICO` | existe reclamação sem serviço vinculado |
| `SERVICO_SEM_RECLAMACAO` | existe serviço sem reclamação vinculada |
| `SEM_EVIDENCIA_COMPLEMENTAR` | sem sinal relevante adicional |

## Consistência componente/causa

A regra `INCONSISTENCIA_COMPONENTE_CAUSA` compara o par:

```text
COD_COMP_SRVE / COD_CAUSA_SRVE
```

contra a referência oficial extraída do IQS:

```text
gold_iqs_referencia_componente_causa
```

Quando o par do serviço não existe na referência, a tela mostra:

- `PARES_COMP_CAUSA_INCONSISTENTES`;
- `SUGESTAO_PARES_COMP_CAUSA`;
- `SUGESTAO_COD_COMP_INTRP`;
- `SUGESTAO_COD_CAUSA_INTRP`.

A sugestão é usada para preencher o formulário do ajuste manual, mas o analista pode revisar antes de salvar.

Importante: se a tabela de referência não existir ou estiver vazia, o sistema não marca falsamente todos os pares como inconsistentes.

## Navegação em cascata

A seleção de causa e componente segue a ordem operacional do IQS:

1. escolher `GRUPO_COMPONENTE_REDE`;
2. a lista de `COD_COMP_INTRP` é filtrada pelo grupo escolhido;
3. a lista de `COD_CAUSA_INTRP` é filtrada pelo componente escolhido;
4. as descrições `DESC_COMP_INTRP` e `DESC_CAUSA_INTRP` ficam visíveis para facilitar a decisão do usuário leigo.

Quando há sugestão automática, o sistema tenta posicionar o grupo correto pelo par componente/causa sugerido. Se não encontrar o par, usa o componente sugerido como fallback.

## Evidências para decisão

Ao selecionar ou buscar uma ocorrência, a tela mostra uma prévia comparativa:

| Cor | Significado |
| --- | --- |
| Sem cor | valor atual da ocorrência/interrupção no IQS |
| Verde | sugestão do algoritmo ou informação pré-tratada/evidência |
| Amarelo | ajuste manual registrado |

As abas de evidência exibem:

- `Ocorrência`: dados da ocorrência/interrupção encontrados nas gold/silver disponíveis;
- `Serviço ADMS`: serviços vinculados à interrupção, com causa e componente do serviço;
- `Reclamações`: resumo e detalhe das reclamações vinculadas.

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

Os campos de data/hora devem ser informados como:

```text
dd/mm/aaaa hh:mm:ss
```

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
- Reextrair `referencia_iqs` sempre que houver mudança cadastral relevante de grupo, componente ou causa no IQS.
- O CSV final usa o helper oficial MIDWAY para separador `|`, fim de linha UNIX/LF e encoding `ISO-8859-1`.
