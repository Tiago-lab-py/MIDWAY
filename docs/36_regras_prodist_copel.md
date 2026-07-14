# 36 - Regras PRODIST Módulo 8 e filtros COPEL

## Objetivo

Centralizar as regras regulatórias que sustentam três módulos do MIDWAY:

1. `DIC_FIC_PRODIST`;
2. `DEC_FEC_PRODIST`;
3. `RESSARCIMENTO_PRODIST`.

Esses módulos não devem ser tratados como anomalias comuns. Eles são módulos regulatórios de cálculo e devem seguir o PRODIST Módulo 8 vigente, com as particularidades operacionais e filtros adotados para a COPEL.

## Referência regulatória

Referência oficial consultada em `2026-07-14`:

- ANEEL - PRODIST: `https://www.gov.br/aneel/pt-br/centrais-de-conteudos/procedimentos-regulatorios/prodist`
- Módulo 8 - Qualidade do Fornecimento: publicado pela ANEEL na página oficial do PRODIST.

Sempre que a ANEEL atualizar o Módulo 8, este documento e os testes dos módulos regulatórios devem ser revisados antes de alterar fórmulas.

## Escopo do ressarcimento

Neste projeto, `RESSARCIMENTO_PRODIST` significa compensação financeira por transgressão de indicadores de continuidade do fornecimento.

Não confundir com ressarcimento por danos elétricos, que pertence a outro contexto regulatório.

## Base canônica do MIDWAY

| Camada | Papel |
| --- | --- |
| `silver_interrupcao_uc_apuravel` | Base tratada por UC/interrupção, já filtrada para apuração |
| `gold_apuracao_uc` | Base individual de UC para DIC/FIC e agregações |
| `gold_apuracao_previa` | Agregação para DEC/FEC |
| `gold_continuidade_uc` | Indicadores individuais e bases compensáveis |
| `gold_ressarcimento_prodist` | Compensações calculadas por indicador |

## Filtros gerais de apuração

Uma linha só entra na base apurável quando:

- a UC existe em `gold_uc_fatura`;
- a UC está faturada com `FATURADO = 'S'`;
- há início e fim válidos;
- `DATA_HORA_FIM_INTRP >= DTHR_INICIO_INTRP_UC`;
- duração é maior ou igual a 3 minutos;
- não há manobra anterior contabilizável em `NUM_INTRP_INIC_MANOBRA_UCI`;
- `NUM_MOTIVO_TRAT_DIF_UCI` está nulo;
- o tipo de protocolo direciona o indicador correto.

## Tipo de protocolo

| `TIPO_PROTOC_JUSTIF_UCI` | Uso |
| --- | --- |
| `0` | Base líquida de `DIC`, `FIC`, `DMIC`, `DEC` e `FEC` |
| `1` | Base de `DICRI` |
| `5` | Base de `DISE` |
| `6` | Base de `DISE` |

## Particularidades COPEL

### Denominador DEC/FEC

O cálculo de `DEC` e `FEC` usa o total de consumidores faturados da empresa, isto é, o registro consolidado:

```text
REGIONAL_TOTAL = 'COPEL'
```

Mesmo quando a saída está agrupada por regional operacional, o denominador regulatório usado pela apuração prévia é o total COPEL.

### Regionalização

O MIDWAY normaliza siglas históricas para regionais operacionais:

| Origem | Regional |
| --- | --- |
| `P` | `CSL` |
| `L` | `NRT` |
| `M` | `NRO` |
| `C` | `LES` |
| `V` | `OES` |
| vazio/outros | `COPEL` |

### Exclusões da base financeira de compensação

A base de indicadores realizados preserva rastreabilidade operacional, mas a base financeira de compensação exclui eventos com:

| Filtro | Campo |
| --- | --- |
| Componente 52 | `COD_COMP_INTRP = '52'` |
| Causa 71 | `COD_CAUSA_INTRP = '71'` |
| Posto particular | `INDIC_PROPR_POSTO_INTRP = 'P'` |
| Chave particular/acessante | `INDIC_PROPR_CHVP_INTRP = 'P'` e `UC_ACESSANTE = 'S'` |
| UC acessante | `UC_ACESSANTE = 'S'` |

Esses filtros são específicos do contrato operacional atual da COPEL no MIDWAY e devem ser tratados como regra explícita, não como detalhe escondido no SQL.

## Regra de manutenção

Qualquer alteração nos módulos `DIC_FIC_PRODIST`, `DEC_FEC_PRODIST` ou `RESSARCIMENTO_PRODIST` deve:

1. citar o item do PRODIST Módulo 8 que motivou a mudança;
2. registrar se a mudança é regulatória ou particularidade COPEL;
3. atualizar os testes automatizados;
4. atualizar os documentos dos três módulos quando houver impacto cruzado.
