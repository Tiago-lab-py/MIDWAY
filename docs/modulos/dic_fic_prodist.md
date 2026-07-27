# Módulo `DIC_FIC_PRODIST`

## Objetivo

Calcular os indicadores individuais de continuidade por UC:

- `DIC`;
- `FIC`;
- `DMIC`;
- `DICRI`;
- `DISE`.

Este módulo segue o PRODIST Módulo 8 vigente e os filtros COPEL descritos em `docs/36_regras_prodist_copel.md`.

## Escopo

- UC;
- interrupção;
- ocorrência;
- indicador individual.

## Fontes

- `silver_interrupcao_tratada`;
- `silver_interrupcao_uc_apuravel`;
- `gold_apuracao_uc`;
- `gold_continuidade_uc`;
- `gold_uc_fatura`;
- `gold_metas_uc`;
- `gold_vrc`.

## Critério regulatório

Base apurável:

- UC faturada;
- interrupção com duração maior ou igual a 3 minutos;
- sem manobra anterior contabilizável;
- sem tratamento diferenciado em `NUM_MOTIVO_TRAT_DIF_UCI`;
- datas válidas;
- protocolo coerente com o indicador.

## Fórmulas operacionais

| Indicador | Regra |
| --- | --- |
| `DIC` | soma das horas apuráveis da UC em `TIPO_PROTOC_JUSTIF_UCI = '0'` |
| `FIC` | quantidade de interrupções apuráveis da UC em `TIPO_PROTOC_JUSTIF_UCI = '0'` |
| `DMIC` | maior duração individual apurável da UC em `TIPO_PROTOC_JUSTIF_UCI = '0'` |
| `DICRI` | soma das horas em dia crítico, `TIPO_PROTOC_JUSTIF_UCI = '1'` |
| `DISE` | soma das horas em ISE, `TIPO_PROTOC_JUSTIF_UCI IN ('5', '6')` |

## Particularidade COPEL

Para base financeira de compensação, o módulo separa indicadores realizados de indicadores compensáveis.

Exclusões da base compensável:

- `COD_COMP_INTRP = '46', '48'`;
- `COD_CAUSA_INTRP = '71', '75'`;
- posto particular;
- chave particular/acessante;
- UC acessante.

## Saída

| Tabela | Uso |
| --- | --- |
| `gold_apuracao_uc` | base UC/interrupção apurável |
| `gold_continuidade_uc` | indicadores individuais por UC, metas e bases compensáveis |

## Testes associados

- `tests/test_apuracao_dic_fic.py`;
- `tests/test_contratos_tabelas.py`;
- `tests/test_ressarcimento_prodist.py`.

## Relação com exportação IQS

Este módulo não gera pacote IQS diretamente. Ele fornece impacto regulatório para priorização, governança e cálculo de compensação.
