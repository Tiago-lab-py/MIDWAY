# Simulação ISE

## Objetivo

A Simulação ISE identifica interrupções com causa elegível para ISE e separa duas visões:

- **Bruto**: verifica se houve potencial ISE.
- **Líquido**: mede quanto pode ser reclassificado.

## Regra de CHI

| Medida | Uso |
| --- | --- |
| `CHI_BRUTO` / `DIC_BRT` | Verificar se houve ISE |
| `CHI_LIQUIDO` / `DIC` | Quantidade que poderá ser reclassificada |

O bruto é referência de elegibilidade. O líquido é referência de impacto apurável.

## Causas elegíveis

São elegíveis para ISE os códigos de causa:

```text
2, 4, 5, 6, 7, 8, 9, 13, 15, 23, 24, 28,
39, 40, 41, 52, 54, 69, 82
```

## Observação importante

`COD_CAUSA_INTRP = 52` é elegível para ISE.

Isto é diferente de `COD_COMP_INTRP = 52`, que continua sendo exceção de compensação/ressarcimento.

