# 05 - Ajuste de inicio de manobra apontando para interrupcao descartada

## Contexto

Na primeira etapa do tratamento, a sobreposicao total por equipamento marca interrupcoes contidas como:

- `ESTADO_INTRP = 7`;
- `NUM_MOTIVO_TRAT_DIF_UCI = 91`;
- `INDIC_SIT_PROCES_INDIC_UCI = R`.

Essas interrupcoes deixam de ser consideradas interrupcoes validas no IQS.

## Problema

Pode existir uma terceira interrupcao que aponta para a interrupcao descartada no campo:

`NUM_INTRP_INIC_MANOBRA_UCI`

Exemplo:

| Registro | Situacao |
| --- | --- |
| A | interrupcao contida |
| B | interrupcao pai, mantida como valida |
| C | interrupcao que possui `NUM_INTRP_INIC_MANOBRA_UCI = A` |

Como A sera marcada como `ESTADO_INTRP = 7`, o registro C nao deve continuar apontando para A.

## Regra implementada

Quando uma interrupcao A for marcada como `ESTADO_INTRP = 7` por sobreposicao total de equipamento, o tratamento cria um mapa:

`interrupcao filha 7 -> interrupcao pai mantida`

Depois, qualquer registro que tenha:

`NUM_INTRP_INIC_MANOBRA_UCI = interrupcao filha 7`

passa a receber:

`NUM_INTRP_INIC_MANOBRA_UCI = interrupcao pai mantida`

Se `NUM_INTRP_INIC_MANOBRA_UCI` esta nulo, vazio, `0`, `0.0` ou igual a propria interrupcao (`NUM_INTRP_UCI`/`NUM_SEQ_INTRP`), o valor permanece nulo na tabela de exportacao tratada.

O tratamento nao deve preencher `NUM_INTRP_INIC_MANOBRA_UCI` com a propria interrupcao. Esse campo so deve permanecer preenchido quando aponta para outra interrupcao real.

## Campos tecnicos gerados

O tratamento passa a registrar os campos auxiliares abaixo em `adms_iqs_alterados`:

| Campo | Descricao |
| --- | --- |
| `NUM_INTRP_INIC_MANOBRA_UCI_ANTES_REDIREC` | valor original antes do redirecionamento |
| `NUM_INTRP_MANOBRA_FILHA_7_REDIREC` | interrupcao descartada que era referenciada |
| `NUM_INTRP_MANOBRA_PAI_REDIREC` | interrupcao pai usada como substituta |
| `ACAO_REDIREC_MANOBRA_ESTADO_7` | acao `REDIRECIONAR_MANOBRA_ESTADO_7` |

Esses campos sao apenas de controle/auditoria e nao entram no layout final do IQS.

## Ordem do tratamento

A regra entra depois das tres etapas principais:

1. sobreposicao total por equipamento;
2. sobreposicao total por UC;
3. sobreposicao parcial por UC.

Ela e aplicada no resultado final tratado, antes da exportacao.

## Exportacao

Os registros redirecionados entram no pacote:

`data/export/sobreposicao_eqp_uc`

Motivo: o redirecionamento nasce da primeira etapa, porque a referencia original apontava para uma interrupcao descartada por sobreposicao de equipamento.

## Auditoria

Para gerar a auditoria:

```bat
python -m midway.auditoria.ajuste_inicio_manobra
```

Arquivos gerados:

- `data/marts/Auditoria_Ajuste_Inicio_Manobra_<timestamp>.CSV`
- `data/marts/Auditoria_Ajuste_Inicio_Manobra_<timestamp>_RESUMO.TXT`

O CSV lista:

- registro alterado;
- valor anterior;
- interrupcao filha descartada;
- interrupcao pai usada como substituta;
- valor final de `NUM_INTRP_INIC_MANOBRA_UCI`.

## Observacao

Depois de alterar essa regra, e necessario reprocessar:

```bat
run.bat reprocessar
```

Depois, para gerar os pacotes separados:

```bat
run.bat exportacao_sobreposicao
```
