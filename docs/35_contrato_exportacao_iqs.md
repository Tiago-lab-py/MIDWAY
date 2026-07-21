# 35 - Contrato rígido de exportação IQS

## Objetivo

Registrar as regras obrigatórias para qualquer arquivo que possa ser enviado ao IQS.

Este contrato vale para a exportação principal, exportações auxiliares e módulos de anomalia que gerem arquivo `Interrupcoes_IQS_*.CSV`.

## Regra central

Todo módulo pode detectar, evidenciar e propor ajustes em formatos próprios de análise, mas a saída final para o IQS deve passar pelo helper oficial:

```text
midway.export.iqs_csv.exportar_dataframe_iqs
```

Quando houver validação completa de colunas do layout oficial, o fluxo principal também usa:

```text
midway.transform.tratamento.exportar_csv_iqs_oficial
```

## Formato físico obrigatório

| Item | Regra |
| --- | --- |
| Separador | `|` |
| Quebra de linha | UNIX/LF, ou seja, `\n` |
| Encoding | `ISO-8859-1` |
| Caracteres especiais | Transliterar ou substituir caracteres fora de `ISO-8859-1` |
| Nulos e vazios | Preencher com espaço simples quando gravado pelo helper oficial |
| Cabeçalho | Ordem e nomes do layout IQS quando for pacote oficial |
| Extensão | `.CSV` |

## Datas

Datas podem existir internamente no DuckDB, PostgreSQL ou pandas em formato ISO, por exemplo:

```text
2026-07-14
2026-07-14 08:09:10
```

No arquivo final aceito pelo IQS, os campos de data/hora do layout devem sair em padrão brasileiro:

```text
dd/mm/aaaa hh:mm:ss
```

Campos atualmente normalizados pelo helper oficial:

| Campo | Saída |
| --- | --- |
| `DATA_HORA_INIC_INTRP` | `dd/mm/aaaa hh:mm:ss` |
| `DATA_HORA_FIM_INTRP` | `dd/mm/aaaa hh:mm:ss` |
| `DTHR_INICIO_INTRP_UC` | `dd/mm/aaaa hh:mm:ss` |

**REGRA DE OURO CONTRA RETRABALHO:** 
Qualquer arquivo exportado pelo sistema, seja o pacote IQS oficial ou **arquivos de auditoria/auxiliares**, deve OBRIGATORIAMENTE conter data e hora completas no formato `dd/mm/aaaa hh:mm:ss` para as colunas de data. 
É terminantemente proibido suprimir a hora (exportar apenas `dd/mm/aaaa`), pois isso gera inconsistência entre relatórios e confusão na leitura dos CSVs, resultando em retrabalho.

## Inteiros sem decimal

Campos numéricos inteiros não devem sair como `123.0`.

Campos atualmente normalizados pelo helper oficial:

| Campo | Saída |
| --- | --- |
| `NUM_INTRP_INIC_MANOBRA_UCI` | inteiro sem decimal |
| `NUM_GEO_CHV_INTRP` | inteiro sem decimal |

## Layout oficial de interrupções

O pacote oficial deve manter a ordem e os nomes do layout IQS.

Se faltar coluna, sobrar coluna ou houver coluna fora de ordem, a exportação oficial deve falhar antes de gravar o pacote.

O arquivo `Mapeamento_Layout_IQS_<YYYYMMDDHHMMSS>.CSV`, quando gerado, deve ser usado para conferir origem de campos vazios ou suspeitos.

## Auditoria versus pacote IQS

| Tipo de arquivo | Pode usar outro formato | Pode ir ao IQS |
| --- | --- | --- |
| Detalhe técnico | Sim, normalmente `;` e `utf-8-sig` | Não |
| Resumo técnico | Sim, normalmente `;` e `utf-8-sig` | Não |
| Auditoria em `data/marts/` | Sim | Não |
| Pré-exportação bloqueada | Deve ser conferível, mas não é pacote final | Não |
| `Interrupcoes_IQS_*.CSV` aprovado | Não, deve seguir este contrato | Sim |

## Regra para novos módulos

Todo módulo exportável deve declarar:

1. quais campos IQS pode alterar;
2. se gera apenas evidência ou também pacote IQS;
3. qual chave impede duplicidade;
4. qual validação bloqueia exportação;
5. que a gravação final usa o helper oficial de exportação IQS.

Se o módulo não conseguir cumprir este contrato, ele pode gerar evidência e fila técnica, mas não deve gerar arquivo final para carga.
