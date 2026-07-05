# 20 - Verificacao de Dia Critico por Conjunto

## Objetivo

Criar uma analise diaria por conjunto eletrico para identificar dias com volume elevado de ocorrencias que provavelmente exigiram atendimento de equipes.

Esta analise e uma triagem operacional. Ela nao substitui a classificacao oficial de dia critico, pois o conjunto de dados atual nao possui as ocorrencias de servicos/equipes nem a meta real de dia critico por conjunto.

## Premissas

Como nao ha dados de servicos executados por equipes, a ferramenta usa uma aproximacao:

```text
ocorrencia provavel com atendimento de equipe =
ocorrencia com duracao maxima maior ou igual ao limite configurado no painel
```

O limite padrao no Streamlit e:

```text
1 hora
```

No painel, esse valor e ajustavel por slider.

## Tabela de Meta Sintetica

A apuracao parcial cria a tabela:

```text
gold_meta_dia_critico_conjunto
```

Ela contem uma referencia provisoria por conjunto:

| Campo | Descricao |
|---|---|
| `COD_CONJUNTO_ANEEL` | conjunto eletrico |
| `QTD_UCS_URBANAS` | quantidade de UCs urbanas no conjunto |
| `META_DICRI_UC_URBANA_REFERENCIA` | maior `META_DICRI` das UCs urbanas do conjunto |
| `FATOR_META_DIA_CRITICO_SINTETICA` | fator aplicado, fixado em `1.5` |
| `META_DIA_CRITICO_SINTETICA` | meta sintetica calculada |
| `META_DIA_CRITICO_REAL` | meta real futura, inicialmente nula |
| `TIPO_META_DIA_CRITICO` | regra usada para gerar a meta |
| `PENDENCIA_META_REAL` | indica que a meta real ainda precisa ser informada |

## Formula da Meta Sintetica

Enquanto a meta real por conjunto nao existir, a referencia usada e:

```text
META_DIA_CRITICO_SINTETICA =
1.5 * MAX(META_DICRI) das UCs urbanas do conjunto
```

Filtro de UCs urbanas:

```text
URB_RUR = 'U'
```

Quando a meta real for disponibilizada, a coluna `META_DIA_CRITICO_REAL` deve ser preenchida e o painel passa a usar a meta real como referencia.

## Indicador do Painel

Para cada dia e conjunto, o painel calcula:

```text
QTD_OCORRENCIAS_PROVAVEL_EQUIPE =
count(distinct NUM_OCORRENCIA_ADMS)
onde MAX_DURACAO_H >= limite selecionado
```

Comparacao contra a referencia:

```text
PCT_META_DIA_CRITICO =
QTD_OCORRENCIAS_PROVAVEL_EQUIPE / META_DIA_CRITICO_USADA * 100
```

Onde:

```text
META_DIA_CRITICO_USADA =
META_DIA_CRITICO_REAL, se existir
senao META_DIA_CRITICO_SINTETICA
```

## Status

| Status | Regra |
|---|---|
| `ACIMA_REFERENCIA` | percentual maior ou igual a 100% |
| `ATENCAO` | percentual entre 80% e 100% |
| `MONITORAR` | percentual abaixo de 80% |

## Painel Streamlit

A tela fica em:

```text
Analytics Pos-Operacao > Dia Critico
```

Recursos:

- filtro por dia;
- filtro por conjunto;
- slider de duracao minima provavel atendimento;
- cards de resumo;
- comparativo por dia/conjunto contra meta sintetica ou real;
- lista das ocorrencias consideradas no criterio;
- download do comparativo.

## Pendencias de Desenvolvimento

- Obter a meta real de dia critico por conjunto.
- Definir a origem oficial da meta real e a rotina de carga.
- Substituir a aproximacao por duracao quando houver base de servicos/equipes.
- Validar com a pos-operacao se o limite padrao de 1 hora representa bem o atendimento por equipes.
