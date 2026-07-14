# 21 - Simulacao de ISE por Janela

## Objetivo

Criar uma verificacao operacional para simular Interrupcao em Situacao de Emergencia - ISE em janelas de tempestade por regional.

A simulacao permite informar:

- regional afetada;
- data/hora de inicio da janela;
- data/hora final da janela;
- tipo ISE a aplicar na simulacao (`TIPO_PROTOC_JUSTIF_UCI = 5` ou `6`).

## Importante

Esta tela nao altera o DuckDB processado e nao gera arquivo oficial para o IQS.

Ela serve para estimar:

- quais UCs seriam afetadas pela janela ISE;
- quanto DIC/FIC normal poderia ser expurgado;
- quanto DISE/FISE seria adicionado;
- quais ocorrencias e registros UC deveriam ser verificados pela pos-operacao antes de aplicar o ISE.

## Fonte

A simulacao usa:

```text
gold_apuracao_uc
gold_continuidade_uc
```

## Criterio Temporal

Um registro UC entra na simulacao quando ha sobreposicao entre a interrupcao e a janela ISE:

```text
DATA_HORA_INIC_INTRP < FIM_ISE
DATA_HORA_FIM_INTRP  > INICIO_ISE
```

O painel tambem permite definir uma sobreposicao minima em minutos para evitar considerar registros que encostam na janela por poucos segundos.

## Cenario 1 - Expurgo pela Janela

Calcula apenas o trecho da interrupcao que ficou dentro da janela:

```text
INICIO_SOBREPOSTO = max(DATA_HORA_INIC_INTRP, INICIO_ISE)
FIM_SOBREPOSTO    = min(DATA_HORA_FIM_INTRP, FIM_ISE)
HORAS_SOBREPOSTAS = FIM_SOBREPOSTO - INICIO_SOBREPOSTO
```

Indicadores:

```text
DIC_EXPURGO_JANELA = min(CHI_LIQUIDO, HORAS_SOBREPOSTAS)
FIC_EXPURGO_JANELA = CI_LIQUIDO quando houver sobreposicao
DISE_SIM_JANELA    = DIC_ISE atual + DIC_EXPURGO_JANELA
```

Esse cenario e util para estimar o efeito estritamente limitado a janela informada.

## Cenario 2 - Expurgo do Registro Inteiro

Calcula o efeito se o registro UC atingido pela janela for marcado integralmente como ISE:

```text
DIC_EXPURGO_REGISTRO = CHI_LIQUIDO
FIC_EXPURGO_REGISTRO = CI_LIQUIDO
DISE_SIM_REGISTRO    = DIC_ISE atual + DIC_EXPURGO_REGISTRO
```

Esse cenario e util para avaliar o impacto da aplicacao pratica do `TIPO_PROTOC_JUSTIF_UCI = 5` ou `6` no registro.

## Filtro Padrao

Por padrao, o painel simula apenas registros atualmente liquidos:

```text
TIPO_PROTOC_JUSTIF_UCI = 0
```

Esse filtro evita misturar registros ja classificados como Dia Critico ou ISE.

O usuario pode desmarcar o filtro para investigar outros cenarios.

## Saidas do Painel

A aba fica em:

```text
Analytics Pos-Operacao > Simulacao ISE
```

Saidas exibidas:

- resumo por regional;
- total de ocorrencias atingidas;
- total de UCs afetadas;
- DISE/FISE simulado pelo trecho da janela;
- DISE/FISE simulado pelo registro inteiro;
- impacto por UC com comparacao contra `META_DISE`;
- detalhe dos registros UC atingidos pela janela;
- downloads em CSV para conferencia.

## Uso Operacional

Fluxo recomendado:

1. informar regional e janela de tempestade;
2. manter o filtro `Somente DIC/FIC liquido` ligado;
3. avaliar o resumo por regional;
4. verificar as UCs com maior `DISE_SIM_REGISTRO` e maior `% META_DISE`;
5. conferir as ocorrencias atingidas;
6. somente depois decidir se o ISE deve ser aplicado oficialmente no arquivo IQS.

## Pendencias

- Criar cadastro persistente de janelas ISE por evento.
- Definir se a aplicacao oficial deve usar trecho da janela ou registro inteiro.
- Gerar arquivo de aplicacao IQS com `TIPO_PROTOC_JUSTIF_UCI = 5/6` e protocolo justificante.
- Validar a regra com a pos-operacao e regulatorio antes de transformar simulacao em tratamento oficial.
