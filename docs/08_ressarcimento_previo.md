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
| `DIC` | somatorio de todas as duracoes da UC, incluindo a maior interrupcao |
| `FIC` | quantidade de interrupcoes da UC |
| `DMIC` | maior duracao individual de interrupcao da UC |

`DIC`, `FIC` e `DMIC` usam a mesma base liquida de `DEC_LIQUIDO` e `FEC_LIQUIDO`: interrupcoes longas, contabilizaveis, de UCs validas/faturadas e com `TIPO_PROTOC_JUSTIF_UCI = '0'`.

Exemplo:

```text
Interrupcoes da UC: 10h, 2h, 4h, 1h, 8h
DIC  = 25h
FIC  = 5
DMIC = 10h
```

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

## Excecao por componente 52

Eventos com o componente abaixo nao compoem a base de compensacao, independentemente da causa:

| Campo | Valor |
| --- | --- |
| `COD_COMP_INTRP` | `52` |

O campo `COD_COMP_INTRP` deve ser tratado como texto/string, usando comparacao com `TRIM(CAST(campo AS VARCHAR))`.

Os indicadores realizados continuam disponiveis para conferencia, mas as bases de compensacao desconsideram esses eventos.

A coluna `COMP52` fica `S` quando a UC possui evento enquadrado nessa regra. A coluna `COMP52_CAUSA71` permanece como marcador complementar para a combinacao historica `COD_COMP_INTRP = 52` e `COD_CAUSA_INTRP = 71`.

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

## Observacao sobre FIC

Foi informado o esboco:

```sql
VRC * (realizado_fic 730) * KEI
```

Para implementacao, a formula foi interpretada como:

```sql
VRC * (realizado_fic / 730) * KEI
```

Essa interpretacao precisa ser confirmada contra o PRODIST Modulo 8 vigente antes de fechamento oficial.

## Indicadores de DICRI e DISE

Foram incluidos os campos `COMP_DICRI` e `COMP_DISE` para conferencia previa.

A tabela `gold_continuidade_uc` tambem possui:

| Indicador | Meta |
| --- | --- |
| `DIC_DICRI` | `META_DICRI` |
| `DIC_ISE` | `META_DISE` |

Ponto pendente: confirmar no PRODIST Modulo 8 se DICRI e DISE devem gerar compensacao financeira com formula propria, fator proprio ou se entram apenas como informacao/controle. Ate essa validacao, a proposta de `COMP_GERAL` deve considerar somente `DIC`, `FIC` e `DMIC`.

## SQL conceitual

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

## Informacoes pendentes para implementar com seguranca

Antes de codificar como regra oficial, validar:

1. Formula vigente exata de compensacao no PRODIST Modulo 8.
2. Se o divisor `730` e fixo para todos os meses ou se deve variar por horas do periodo de apuracao.
3. Se `FIC` usa a mesma estrutura `realizado / 730`.
4. Se a compensacao deve considerar somente o excedente `(realizado - meta)` ou o valor realizado total.
5. Se `DICRI` e `DISE` geram compensacao financeira ou apenas controle.
6. Se existe teto, minimo, arredondamento, tributacao ou regra de acumulo por indicador.
7. Se deve usar `VRC` vigente no mes de apuracao ou valor atual de cadastro.
