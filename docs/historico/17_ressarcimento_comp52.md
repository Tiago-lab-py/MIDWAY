# 17 - Ressarcimento: Exceções por Componente 52 e Causa 71

## Objetivo

Registrar as regras de exceção para eventos com `COD_COMP_INTRP = 52` e `COD_CAUSA_INTRP = 71` na apuração de continuidade e ressarcimento.

Essas regras definem quais eventos devem ser removidos da **base de compensação** e quando também devem sair do cálculo realizado de continuidade.

## Regra de Negócio - Componente 52

Eventos com o componente abaixo não compõem o cálculo de `DIC`, `FIC` e `DMIC` realizado, nem a base financeira de compensação, independentemente da causa:

| Campo | Valor |
| --- | --- |
| `COD_COMP_INTRP` | `52` |

O campo `COD_COMP_INTRP` deve ser tratado como texto/string, usando comparação normalizada:

```sql
TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) = '52'
```

Os eventos continuam rastreáveis nas bases analíticas e exportações de conferência, mas não entram nos indicadores realizados `DIC`, `FIC` e `DMIC`, nem nas bases financeiras de compensação.

## Regra de Negócio - Causa 71

Eventos com a causa abaixo não compõem o cálculo de `DIC`, `FIC` e `DMIC` realizado, nem a base financeira de compensação:

| Campo | Valor |
| --- | --- |
| `COD_CAUSA_INTRP` | `71` |

O campo `COD_CAUSA_INTRP` deve ser tratado como texto/string, usando comparação normalizada:

```sql
TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)) = '71'
```

## Impacto na Apuração

Para `COD_COMP_INTRP = 52`:

- o evento não entra em `DIC`, `FIC` e `DMIC`;
- o evento não entra nas bases de compensação;
- o evento permanece rastreável nas bases analíticas e exportações de conferência.

Para `COD_CAUSA_INTRP = 71`:

- o evento não entra em `DIC`, `FIC` e `DMIC`;
- o evento não entra nas bases de compensação;
- o evento permanece rastreável nas bases analíticas e exportações de conferência.

## Colunas de Controle

| Coluna | Regra | Uso |
| --- | --- | --- |
| `COMP52` | `S` quando a UC possui evento com `COD_COMP_INTRP = 52` | Marcador principal da exceção por componente |
| `CAUSA71` | `S` quando a UC possui evento com `COD_CAUSA_INTRP = 71` | Marcador principal da exceção por causa |
| `COMP52_CAUSA71` | `S` quando a UC possui `COD_COMP_INTRP = 52` ou `COD_CAUSA_INTRP = 71` | Rastreabilidade histórica complementar |

## Interpretação

`COMP52` é a coluna principal para identificar a exceção financeira por componente.

`CAUSA71` é a coluna principal para identificar a exceção por causa que retira o evento de `DIC`, `FIC`, `DMIC` e da compensação.

`COMP52_CAUSA71` não substitui `COMP52` nem `CAUSA71`. Ela permanece como marcador complementar para análises históricas que combinavam:

```text
COD_COMP_INTRP = 52
```

ou:

```text
COD_CAUSA_INTRP = 71
```

## Uso no Painel Streamlit

Na aba de ressarcimento, a explicação do filtro e dos rankings deve deixar claro que:

- `COD_COMP_INTRP = 52` exclui o evento do DIC/FIC/DMIC e da base financeira;
- `COD_CAUSA_INTRP = 71` exclui o evento do DIC/FIC/DMIC e da base financeira;
- as comparações devem ser textuais com `TRIM(CAST(... AS VARCHAR))`;
- `COMP52` identifica a UC com evento enquadrado nessa regra;
- `CAUSA71` identifica a UC com evento enquadrado na causa 71;
- `COMP52_CAUSA71` é apenas marcador complementar histórico.

## Observação

Essa regra não elimina registros da base e não altera a rastreabilidade operacional.

Ela apenas separa:

```text
indicador realizado para conferência
```

de:

```text
base financeira de compensação
```
