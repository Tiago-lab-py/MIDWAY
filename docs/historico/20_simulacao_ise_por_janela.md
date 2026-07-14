# Simulação ISE por Janela

## Objetivo

A Simulação ISE por Janela calcula o potencial ISE apenas dentro de janelas informadas pelo usuário.

O cálculo permite escolher:

- `ANOMES`;
- Regional;
- Período de cálculo;
- uma ou mais janelas específicas;
- execução manual pelo botão **Calcular ISE**.

## Regra de janela

Só entram no cálculo eventos que cruzam uma janela selecionada.

Quando o evento começa antes da janela ou termina depois dela, a duração considerada é apenas a interseção entre:

- início/fim do evento;
- início/fim da janela.

Assim, o CHI da simulação por janela não usa automaticamente a duração total do evento. Ele usa a duração limitada pela janela.

## Bruto e líquido

| Campo | Interpretação |
| --- | --- |
| `ISE_CHI_BRUTO_REFERENCIA` | CHI bruto dentro da janela para verificar se houve potencial ISE |
| `ISE_CHI_LIQUIDO_RECLASSIFICAVEL` | CHI líquido dentro da janela para medir quanto poderá ser reclassificado |
| `ISE_CI_BRUTO_REFERENCIA` | CI bruto dentro da janela |
| `ISE_CI_LIQUIDO_RECLASSIFICAVEL` | CI líquido dentro da janela |

## Causas elegíveis

São elegíveis para ISE:

```text
2, 4, 5, 6, 7, 8, 9, 13, 15, 23, 24, 28,
39, 40, 41, 52, 54, 69, 82
```

## Observação sobre código 52

`COD_CAUSA_INTRP = 52` é elegível para ISE.

`COD_COMP_INTRP = 52` continua sendo regra separada de compensação/ressarcimento e não deve ser confundido com a causa 52.

## Execução

Abrir painel:

```bat
cd /d D:\MIDWAY_novo
painel_ise_janela.bat
```

No painel:

1. informar `ANOMES`;
2. escolher a regional ou `Todas`;
3. escolher o período;
4. preencher e selecionar as janelas;
5. clicar em **Calcular ISE**;
6. baixar CSV ou salvar em `data\marts`.

