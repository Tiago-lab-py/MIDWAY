# Módulo `DEC_FEC_PRODIST`

## Objetivo

Calcular os indicadores coletivos de continuidade:

- `DEC`;
- `FEC`.

Este módulo segue o PRODIST Módulo 8 vigente e os filtros COPEL descritos em `docs/36_regras_prodist_copel.md`.

## Escopo

- conjunto;
- regional;
- empresa;
- ocorrência/interrupção agregada.

## Fontes

- `gold_apuracao_uc`;
- `gold_apuracao_previa`;
- `gold_consumidores`;
- `gold_uc_fatura`.

## Base de cálculo

O módulo usa a mesma base líquida de `DIC/FIC`:

- duração maior ou igual a 3 minutos;
- UC faturada;
- sem manobra contabilizável;
- sem tratamento diferenciado;
- `TIPO_PROTOC_JUSTIF_UCI = '0'`.

## Fórmulas operacionais

| Indicador | Regra |
| --- | --- |
| `CHI_LIQUIDO` | soma das horas apuráveis |
| `CI_LIQUIDO` | contagem de UCs interrompidas apuráveis |
| `DEC_LIQUIDO` | `CHI_LIQUIDO / TOTAL_CONSUMIDORES` |
| `FEC_LIQUIDO` | `CI_LIQUIDO / TOTAL_CONSUMIDORES` |

Também são mantidos `DEC_BRUTO` e `FEC_BRUTO` para auditoria e comparação.

## Particularidade COPEL

O denominador oficial usado pelo MIDWAY é o total de consumidores faturados da COPEL:

```text
gold_consumidores.REGIONAL_TOTAL = 'COPEL'
```

Isso evita que uma regional operacional use denominador parcial quando o objetivo é estimar impacto regulatório consolidado.

## Saída

| Tabela | Uso |
| --- | --- |
| `gold_apuracao_previa` | prévia agregada de `DEC/FEC`, `CI/CHI` e campos de auditoria |

## Testes associados

- `tests/test_apuracao_dic_fic.py`;
- `tests/test_contratos_tabelas.py`.

## Relação com exportação IQS

Este módulo não altera o IQS diretamente. Ele mede impacto coletivo dos ajustes e deve ser usado antes/depois de qualquer pacote aprovado.
