# Ressarcimento previo por continuidade individual

## Objetivo

Adicionar na tabela `gold_continuidade_uc` uma apuracao previa do valor de compensacao/ressarcimento por ultrapassagem das metas individuais de continuidade.

A base normativa deve ser validada contra a versao vigente do PRODIST Modulo 8. A ANEEL mantem a pagina oficial do PRODIST com links para a versao vigente dos modulos, incluindo o Modulo 8 - Qualidade do Fornecimento de Energia Eletrica.

Fonte oficial para conferencia: https://www.gov.br/aneel/pt-br/centrais-de-conteudos/procedimentos-regulatorios/prodist

A regra financeira aderente ao PRODIST Modulo 8 foi separada na tabela:

```text
gold_ressarcimento_prodist
```

Detalhamento da validacao normativa: `docs/10_prodist_modulo8.md`.

## Tabelas de entrada

| Tabela | Uso |
| --- | --- |
| `gold_continuidade_uc` | indicadores realizados por UC |
| `gold_vrc` | valor base de compensacao da UC |
| `gold_metas_uc` | metas individuais e grupo/nivel de tensao |

## Campos em `gold_continuidade_uc`

| Campo | Origem / regra |
| --- | --- |
| `GRUPO_TENSAO` | grupo/nivel de tensao da UC |
| `COD_GRUPO_NIVEL_TENSAO_UC` | origem `gold_vrc` ou `gold_metas_uc` |
| `COD_NIVEL_TENSAO_UC` | origem `gold_vrc` ou `gold_metas_uc` |
| `VRC` | `gold_vrc.VRC` |
| `KEI` | fator por grupo/nivel de tensao |
| `COMP_DIC` | compensacao calculada por DIC |
| `COMP_FIC` | compensacao calculada por FIC |
| `COMP_DMIC` | compensacao calculada por DMIC |
| `COMP_DICRI` | compensacao previa calculada por DICRI |
| `COMP_DISE` | compensacao previa calculada por DISE |
| `COMP_GERAL` | maior valor entre `COMP_DIC`, `COMP_FIC` e `COMP_DMIC` |

Para calculo financeiro PRODIST, usar preferencialmente os campos `*_PRODIST` da tabela `gold_ressarcimento_prodist`.

## Definicao dos indicadores realizados

| Indicador | Regra |
| --- | --- |
| `DIC` | somatorio das duracoes elegiveis conforme regra IQS liquida |
| `FIC` | quantidade de interrupcoes elegiveis conforme regra IQS liquida |
| `DMIC` | maior duracao individual elegivel conforme regra IQS liquida |
| `DIC_BRT` | somatorio das duracoes conforme regra IQS bruta |
| `FIC_BRT` | quantidade de interrupcoes conforme regra IQS bruta |
| `DMIC_BRT` | maior duracao individual conforme regra IQS bruta |

`DIC`, `FIC` e `DMIC` usam `TIPO_PROTOC_JUSTIF_UCI = '0'`, interrupcoes longas e contabilizaveis, aplicando tambem as siglas IQS de indicador e regra de expurgo quando disponiveis:

```text
SIGLA_TIQS_DIC
SIGLA_REID_DIC
SIGLA_TIQS_FIC
SIGLA_REID_FIC
```

Quando essas siglas ainda nao existem na base processada, o MIDWAY assume comportamento padrao:

```text
SIGLA_TIQS_DIC = DIC_
SIGLA_REID_DIC = nulo
SIGLA_TIQS_FIC = FIC_
SIGLA_REID_FIC = nulo
```

Exemplo:

```text
Interrupcoes da UC: 10h, 2h, 4h, 1h, 8h
DIC  = 25h
FIC  = 5
DMIC = 10h
```

Eventos com `COD_COMP_INTRP = 52` ou `COD_CAUSA_INTRP = 71` nao compoem `DIC`, `FIC`, `DMIC` nem a base financeira de compensacao.

## Regra do KEI

```sql
CASE
    WHEN COD_GRUPO_NIVEL_TENSAO_UC = 'A'
     AND COD_NIVEL_TENSAO_UC IN ('1','2','3')
    THEN 108

    WHEN COD_GRUPO_NIVEL_TENSAO_UC = 'A'
     AND COD_NIVEL_TENSAO_UC IN ('3a','4','S')
    THEN 40

    WHEN COD_GRUPO_NIVEL_TENSAO_UC = 'B'
    THEN 34

    ELSE 0
END AS KEI
```

## Formula previa de compensacao

Usar os indicadores realizados e metas da `gold_continuidade_uc`.

A compensacao previa so e calculada para UCs faturadas (`FATURADA = 'S'`). Para UCs nao faturadas, os indicadores permanecem para conferencia, mas todos os campos `COMP_*` ficam `0`.

## Resumo de compensacao

Os resumos exibem somente os totais calculados da base completa de continuidade individual. Nao ha corte operacional de 24 horas na apuracao previa nem no resumo de ressarcimento.

## Excecao de acessante unico em chave propria

Regra geral: eventos com `UC_ACESSANTE = 'S'` nao compoem a base de compensacao. A coluna `UC_ACESSANTE_COMPENSACAO` fica `S` quando a UC possui evento enquadrado nessa regra.

O caso abaixo e mantido como identificacao complementar de chave particular/acessante unico.

Para fins de compensacao, eventos com as seguintes caracteristicas nao compoem a base compensavel:

| Campo | Regra |
| --- | --- |
| `INDIC_PROPR_CHVP_INTRP` | `P` |
| `UC_ACESSANTE` | `S` |
| Chave do evento | `NUM_OPER_CHV_INTRP`, `NUM_SEQ_INTRP`, `NUM_OCORRENCIA_ADMS` |
| UC do evento | `NUM_UC_UCI` unica dentro da chave do evento |

Nesses casos, os indicadores realizados continuam disponiveis para conferencia (`DIC`, `FIC`, `DMIC`, `DIC_DICRI`, `DIC_ISE`), mas a compensacao usa os campos de base compensavel:

| Indicador realizado | Base usada para compensacao |
| --- | --- |
| `DIC` | `DIC_BASE_COMPENSACAO` |
| `FIC` | `FIC_BASE_COMPENSACAO` |
| `DMIC` | `DMIC_BASE_COMPENSACAO` |
| `DIC_DICRI` | `DICRI_BASE_COMPENSACAO` |
| `DIC_ISE` | `DISE_BASE_COMPENSACAO` |

Se a UC possuir apenas esse tipo de evento, os valores de compensacao ficam `0`.

A coluna `CHAVE_PARTICULAR` fica `S` quando a UC possui evento enquadrado nessa regra.

## Excecoes por componente 52 e causa 71

Eventos com componente `52` ou causa `71` nao compoem `DIC`, `FIC`, `DMIC` nem a base financeira de compensacao.

| Campo | Valor |
| --- | --- |
| `COD_COMP_INTRP` | `52` |
| `COD_CAUSA_INTRP` | `71` |

Os campos devem ser tratados como texto/string, usando comparacao normalizada:

```sql
TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) = '52'
```

```sql
TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)) = '71'
```

Os eventos continuam rastreaveis nas bases analiticas e exportacoes de conferencia, mas nao entram nos indicadores realizados de continuidade individual nem nas bases de compensacao.

Colunas de controle:

| Coluna | Regra |
| --- | --- |
| `COMP52` | `S` quando a UC possui evento com `COD_COMP_INTRP = 52` |
| `CAUSA71` | `S` quando a UC possui evento com `COD_CAUSA_INTRP = 71` |
| `COMP52_CAUSA71` | marcador complementar historico para `COD_COMP_INTRP = 52` ou `COD_CAUSA_INTRP = 71` |

`COMP52_CAUSA71` e apenas marcador complementar historico; as regras principais sao `COMP52` e `CAUSA71`.

## Excecao por posto particular

Eventos com `INDIC_PROPR_POSTO_INTRP = 'P'` tambem nao compoem a base de compensacao. A coluna `POSTO_PARTICULAR` fica `S` quando a UC possui evento enquadrado nessa regra.

```sql
CASE
    WHEN DIC_BASE_COMPENSACAO > META_DIC
    THEN VRC * (DIC_BASE_COMPENSACAO / 730) * KEI
    ELSE 0
END AS COMP_DIC
```

```sql
CASE
    WHEN FIC_BASE_COMPENSACAO > META_FIC
    THEN VRC * (FIC_BASE_COMPENSACAO / 730) * KEI
    ELSE 0
END AS COMP_FIC
```

```sql
CASE
    WHEN DMIC_BASE_COMPENSACAO > META_DMIC
    THEN VRC * (DMIC_BASE_COMPENSACAO / 730) * KEI
    ELSE 0
END AS COMP_DMIC
```

```sql
GREATEST(COMP_DIC, COMP_FIC, COMP_DMIC) AS COMP_GERAL
```

## Formula FIC PRODIST

Para calculo financeiro oficial, usar a formula implementada em `gold_ressarcimento_prodist`:

```sql
COMP_FIC_BRUTA_PRODIST =
    (FIC_BASE_COMPENSACAO / META_FIC) * META_DIC * VRC / 730 * KEI1_CONTINUIDADE
```

Depois aplicar piso e teto:

```sql
COMP_FIC_PRODIST =
    LEAST(18 * VRC, GREATEST(0.01, COMP_FIC_BRUTA_PRODIST))
```

Quando nao houver violacao de `META_FIC`, a compensacao fica `0`.

## Indicadores de DICRI e DISE

Foram incluidos os campos `COMP_DICRI` e `COMP_DISE` para conferencia previa.

A tabela `gold_continuidade_uc` tambem possui:

| Indicador | Meta |
| --- | --- |
| `DIC_DICRI` | `META_DICRI` |
| `DIC_ISE` | `META_DISE` |

Na tabela `gold_ressarcimento_prodist`, `DICRI` e `DISE` usam coeficientes proprios:

| Indicador | Coeficiente |
| --- | --- |
| `DICRI` | `KEI2_DICRI` |
| `DISE` | `KEI3_DISE` |

`COMP_GERAL_CONTINUIDADE_PRODIST` considera o maior valor entre `DIC`, `FIC` e `DMIC`.

`COMP_TOTAL_PRODIST` soma:

```text
COMP_GERAL_CONTINUIDADE_PRODIST + COMP_DICRI_PRODIST + COMP_DISE_PRODIST
```

Observacao: `DICRI` e `DISE` ainda permanecem com status parcial quando agregados por UC, conforme documentado em `docs/10_prodist_modulo8.md`.

## SQL conceitual legado

O bloco abaixo registra a primeira proposta conceitual de cálculo em `gold_continuidade_uc`.

Para cálculo financeiro PRODIST, usar a tabela atual:

```text
gold_ressarcimento_prodist
```

com os campos `*_PRODIST`, piso `R$ 0,01`, teto `18 * VRC`, fórmula FIC PRODIST e coeficientes `KEI1`, `KEI2` e `KEI3`.

```sql
SELECT
    c.*,
    COALESCE(v.COD_GRUPO_NIVEL_TENSAO_UC, m.COD_GRUPO_NTFN) AS COD_GRUPO_NIVEL_TENSAO_UC,
    COALESCE(v.COD_NIVEL_TENSAO_UC, m.COD_NTFN) AS COD_NIVEL_TENSAO_UC,
    COALESCE(v.VRC, 0) AS VRC,

    CASE
        WHEN COALESCE(v.COD_GRUPO_NIVEL_TENSAO_UC, m.COD_GRUPO_NTFN) = 'A'
         AND COALESCE(v.COD_NIVEL_TENSAO_UC, m.COD_NTFN) IN ('1','2','3')
        THEN 108
        WHEN COALESCE(v.COD_GRUPO_NIVEL_TENSAO_UC, m.COD_GRUPO_NTFN) = 'A'
         AND COALESCE(v.COD_NIVEL_TENSAO_UC, m.COD_NTFN) IN ('3a','4','S')
        THEN 40
        WHEN COALESCE(v.COD_GRUPO_NIVEL_TENSAO_UC, m.COD_GRUPO_NTFN) = 'B'
        THEN 34
        ELSE 0
    END AS KEI,

    CASE
        WHEN c.DIC > c.META_DIC
        THEN COALESCE(v.VRC, 0) * (c.DIC / 730) * KEI
        ELSE 0
    END AS COMP_DIC,

    CASE
        WHEN c.FIC > c.META_FIC
        THEN COALESCE(v.VRC, 0) * (c.FIC / 730) * KEI
        ELSE 0
    END AS COMP_FIC,

    CASE
        WHEN c.DMIC > c.META_DMIC
        THEN COALESCE(v.VRC, 0) * (c.DMIC / 730) * KEI
        ELSE 0
    END AS COMP_DMIC,

    GREATEST(COMP_DIC, COMP_FIC, COMP_DMIC) AS COMP_GERAL
FROM gold_continuidade_uc c
LEFT JOIN gold_vrc v
  ON CAST(v.ISN_UC AS VARCHAR) = c.UC
LEFT JOIN gold_metas_uc m
  ON CAST(m.ISN_UC AS VARCHAR) = c.UC
```

## Pendencias remanescentes

Itens ainda recomendados para evolucao e auditoria:

1. Validar a matriz completa de equivalencia entre codigos IQS e itens do PRODIST.
2. Confirmar se o `VRC` extraido representa o valor vigente correto para o mes de apuracao.
3. Evoluir `DICRI` e `DISE` para granularidade por evento, quando necessario.
4. Validar regras de arredondamento e apresentacao financeira final.
5. Controlar efetivacao em fatura fora do escopo atual do MIDWAY.
