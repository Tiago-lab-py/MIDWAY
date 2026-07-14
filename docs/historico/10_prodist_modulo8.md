# 10 - Validacao do ressarcimento contra PRODIST Modulo 8

## Fonte normativa consultada

Consulta realizada em 2026-07-02.

Fonte oficial:

- Pagina ANEEL Prodist: https://www.gov.br/aneel/pt-br/centrais-de-conteudos/procedimentos-regulatorios/prodist
- Modulo 8 vigente indicado pela pagina oficial: `aren20251137_Prodist_modulo_8_v14.pdf`
- URL do PDF vigente consultado: https://git.aneel.gov.br/publico/centralconteudo/-/raw/main/procreg/prodist/modulo08/aren20251137_Prodist_modulo_8_v14.pdf

Escopo deste documento: compensacao por violacao dos limites dos indicadores de continuidade individuais `DIC`, `FIC`, `DMIC`, `DICRI` e `DISE`.

Nao confundir com o Modulo 9 do PRODIST, que trata de ressarcimento de danos eletricos.

## Mapeamento operacional IQS/ADMS

No MIDWAY, o campo `TIPO_PROTOC_JUSTIF_UCI` direciona a familia de indicadores:

| `TIPO_PROTOC_JUSTIF_UCI` | Interpretacao | Indicadores |
| --- | --- | --- |
| `0` | Base liquida regular | `DIC`, `FIC`, `DMIC` |
| `1` | Dia Critico | `DICRI` |
| `5` | ISE | `DISE` |
| `6` | ISE | `DISE` |

O campo `COD_TIPO_INTRP` classifica a natureza da interrupcao:

| `COD_TIPO_INTRP` | Interpretacao |
| --- | --- |
| `1` | Acidental |
| `2` | Programado |
| `3` | Voluntario |

As sobreposicoes temporais devem ser tratadas dentro da mesma UC e do mesmo `COD_TIPO_INTRP`, sem misturar naturezas diferentes de interrupcao.

## Regras PRODIST Modulo 8 relevantes

### Base de apuracao

O item 177 determina que os indicadores de continuidade individuais e coletivos considerem apenas interrupcoes de longa duracao, ou seja, duracao maior ou igual a 3 minutos.

O item 178 lista situacoes que nao devem ser consideradas na apuracao de `DIC` e `FIC`, incluindo, entre outras:

- falha nas instalacoes da unidade consumidora ou central geradora sem interrupcao em terceiros;
- obra de interesse exclusivo do consumidor ou central geradora;
- Interrupcao em Situacao de Emergencia - `ISE`;
- suspensoes por inadimplemento ou deficiencia tecnica/seguranca;
- racionamento instituido pela Uniao;
- Dia Critico;
- `ERAC`;
- interrupcao de origem externa ao sistema de distribuicao.

O item 179 acrescenta regra especifica para `DMIC`: alem das exclusoes do item 178, tambem nao devem ser consideradas interrupcoes programadas quando os consumidores forem avisados e inicio/fim estiverem dentro do intervalo programado.

Os itens 180 e 180-A tratam das excecoes especificas de `DICRI` e `DISE`.

### Compensacao

O item 219 determina compensacao quando houver violacao dos limites individuais de `DIC`, `FIC`, `DMIC`, `DICRI` e `DISE`.

O item 225 define as formulas:

| Indicador | Formula normativa |
| --- | --- |
| `DIC` | `CompDIC = DICv * VRC / 730 * Kei1` |
| `DMIC` | `CompDMIC = DMICv * VRC / 730 * Kei1` |
| `FIC` | `CompFIC = (FICv / FICp) * DICp * VRC / 730 * Kei1` |
| `DICRI` | `CompDICRI = DICRIv * VRC / 730 * Kei2` |
| `DISE` | `CompDISE = DISEv * VRC / 730 * Kei3` |

Onde:

- `DICv`, `DMICv`, `FICv`, `DICRIv` e `DISEv` sao os valores verificados;
- `DICp` e `FICp` sao os limites do periodo;
- `VRC` e o valor monetario base da compensacao;
- `730` e o numero medio de horas no mes;
- `Kei1`, `Kei2` e `Kei3` sao coeficientes de majoracao.

Coeficientes:

| Coeficiente | Baixa tensao | Media tensao | Alta tensao |
| --- | ---: | ---: | ---: |
| `Kei1` | 34 | 40 | 108 |
| `Kei2` | 14 | 20 | nao se aplica |
| `Kei3` | 14 | 20 | nao se aplica |

O item 225.1 estabelece regra especifica de calculo do `VRC` para unidade consumidora residencial baixa renda.

O item 227 estabelece regras adicionais:

- compensacao minima de `R$ 0,01`;
- compensacao limitada a `18 * VRC`;
- se houver violacao de mais de um indicador entre `DIC`, `FIC` e `DMIC`, deve ser considerado o maior valor monetario;
- `DICRI` e `DISE` sao compensacoes adicionais, sem prejuizo de `DIC`, `FIC` e `DMIC`, e podem somar mais de uma violacao no mesmo mes.

## Comparacao com a implementacao atual

Arquivo principal: `midway.apuracao.previa`.

Tabela de saida: `gold_continuidade_uc`.

### Pontos aderentes ou parcialmente aderentes

| Tema | Status | Observacao |
| --- | --- | --- |
| Interrupcao longa | Aderente | `gold_apuracao_uc` considera duracao maior ou igual a 3 minutos. |
| Base unica DEC/FEC x DIC/FIC | Aderente com regra IQS | `DIC/FIC/DMIC` usam siglas IQS de indicador e regra de expurgo quando disponíveis. |
| Motivo de tratamento diferenciado | Aderente a regra operacional definida | `NUM_MOTIVO_TRAT_DIF_UCI` deve estar nulo para entrar na base apuravel. |
| Manobra | Aderente ao objetivo operacional | Registros com `NUM_INTRP_INIC_MANOBRA_UCI` preenchido nao entram novamente na contagem. |
| `DIC` e `DMIC` | Parcial | A formula base usa `valor_verificado * VRC / 730 * KEI`, mas ainda falta aplicar minimo, teto e validar `VRC`. |
| `COMP_GERAL` | Parcial | Usa o maior valor entre `COMP_DIC`, `COMP_FIC` e `COMP_DMIC`, conforme ideia do item 227. |

### Pontos nao aderentes ou pendentes

| Tema | Status | Problema |
| --- | --- | --- |
| `FIC` | Nao aderente | O codigo usa `FIC_BASE_COMPENSACAO * VRC / 730 * KEI`. O PRODIST usa `(FICv / FICp) * DICp * VRC / 730 * Kei1`. |
| `DICRI` | Nao aderente | O codigo usa o mesmo `KEI` de `DIC/FIC/DMIC`; o PRODIST usa `Kei2`. Tambem deve tratar compensacoes por interrupcao em Dia Critico. |
| `DISE` | Nao aderente | O codigo usa o mesmo `KEI`; o PRODIST usa `Kei3`. Tambem deve tratar compensacoes por interrupcao em Situacao de Emergencia. |
| Teto `18 * VRC` | Pendente | Nao ha limite superior aplicado nos campos `COMP_*`. |
| Minimo `R$ 0,01` | Pendente | Nao ha piso explicito para compensacoes positivas. |
| Baixa renda | Pendente | Nao foi validado se o `VRC` extraido ja segue a regra do item 225.1. |
| Exclusoes do item 178 | Parcial evoluido | O sistema aplica siglas IQS (`SIGLA_TIQS_*`, `SIGLA_REID_*`) quando disponíveis e mantém pendente a matriz formal de equivalência entre códigos IQS e alíneas do PRODIST. |
| Interrupcao programada em `DMIC` | Pendente | Falta validar se a exclusao especifica do item 179 esta refletida nos codigos de justificativa/tratamento. |
| Credito em fatura ate 2 meses | Fora do escopo atual | O MIDWAY calcula previa, mas nao controla efetivacao financeira/faturamento. |

## Diagnostico

O MIDWAY esta adequado como middleware de tratamento e previa de indicadores, especialmente apos:

- remover sobreposicao temporal por UC;
- respeitar `COD_TIPO_INTRP` nas sobreposicoes;
- exigir `NUM_MOTIVO_TRAT_DIF_UCI` nulo na base apuravel;
- manter `DIC/FIC` fechando com `DEC/FEC` liquido.

Porem, os campos `COMP_*` ainda nao devem ser tratados como compensacao oficial PRODIST Modulo 8.

Motivo: a formula de `FIC`, os coeficientes de `DICRI/DISE`, teto, piso e regras especificas de eventos criticos/emergenciais ainda precisam ser ajustados.

## Implementacao tecnica

### 1. Separar indicadores de formulas financeiras

Manter `gold_continuidade_uc` como tabela de indicadores realizados:

- `DIC`;
- `FIC`;
- `DMIC`;
- `DIC_DICRI`;
- `DIC_ISE`;
- metas;
- VRC;
- grupo/nivel de tensao;
- flags de exclusao.

Foi criada uma nova tabela:

```text
gold_ressarcimento_prodist
```

Essa tabela deve conter apenas a regra financeira do PRODIST Modulo 8.

### 2. Criar coeficientes separados

Adicionar campos:

```text
KEI1_CONTINUIDADE
KEI2_DICRI
KEI3_DISE
```

Regras:

| Grupo | `KEI1` | `KEI2` | `KEI3` |
| --- | ---: | ---: | ---: |
| BT | 34 | 14 | 14 |
| MT | 40 | 20 | 20 |
| AT | 108 | 0 | 0 |

### 3. Corrigir formulas

Formulas propostas:

```sql
COMP_DIC_BRUTA =
    DIC_BASE_COMPENSACAO * VRC / 730 * KEI1_CONTINUIDADE
```

```sql
COMP_DMIC_BRUTA =
    DMIC_BASE_COMPENSACAO * VRC / 730 * KEI1_CONTINUIDADE
```

```sql
COMP_FIC_BRUTA =
    (FIC_BASE_COMPENSACAO / META_FIC) * META_DIC * VRC / 730 * KEI1_CONTINUIDADE
```

```sql
COMP_DICRI_BRUTA =
    DICRI_BASE_COMPENSACAO * VRC / 730 * KEI2_DICRI
```

```sql
COMP_DISE_BRUTA =
    DISE_BASE_COMPENSACAO * VRC / 730 * KEI3_DISE
```

Aplicar somente quando houver violacao do respectivo limite.

### 4. Aplicar piso e teto

Para cada compensacao positiva:

```sql
COMP_AJUSTADA = LEAST(18 * VRC, GREATEST(0.01, COMP_BRUTA))
```

Para compensacao sem violacao:

```sql
COMP_AJUSTADA = 0
```

### 5. Calcular geral conforme item 227

```sql
COMP_GERAL_CONTINUIDADE =
    GREATEST(COMP_DIC, COMP_FIC, COMP_DMIC)
```

`DICRI` e `DISE` devem ficar separados e somar adicionalmente:

```sql
COMP_TOTAL_PRODIST =
    COMP_GERAL_CONTINUIDADE
  + COMP_DICRI
  + COMP_DISE
```

### 6. Validar matriz de codigos IQS

Criar uma tabela/documento de equivalencia entre:

- `TIPO_PROTOC_JUSTIF_UCI`;
- `NUM_MOTIVO_TRAT_DIF_UCI`;
- `COD_CAUSA_INTRP`;
- `COD_COMP_INTRP`;
- regras do item 178 do PRODIST.

Sem essa matriz, a previa pode estar correta operacionalmente, mas nao fica plenamente auditavel contra o texto normativo.

### 7. Filtros IQS para DIC, FIC e DMIC

O MIDWAY aplica, quando os campos existem na base apurável, as siglas do IQS para determinar elegibilidade de `DIC`, `FIC` e `DMIC`.

Campos usados:

```text
SIGLA_TIQS_DIC
SIGLA_REID_DIC
SIGLA_TIQS_FIC
SIGLA_REID_FIC
```

Regras líquidas:

```sql
SUBSTR(COALESCE(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
AND SIGLA_REID_DIC IS NULL
```

```sql
SUBSTR(COALESCE(SIGLA_TIQS_FIC, 'FIC_'), 1, 4) = 'FIC_'
AND SIGLA_REID_FIC IS NULL
```

`DMIC` segue a mesma elegibilidade do `DIC`, considerando a maior duração individual elegível.

Regras brutas:

```sql
COALESCE(SIGLA_REID_DIC, 'X') NOT IN ('DFC','USU','USI','ACI','FM','ERR','DUP','CHP','DFI','PTP')
```

```sql
COALESCE(SIGLA_REID_FIC, 'X') NOT IN ('DFC','USU','USI','ACI','FM','ERR','DUP','CHP','DFI','PTP','MAN')
```

Além disso, eventos com `COD_COMP_INTRP = 52` ou `COD_CAUSA_INTRP = 71` não compõem `DIC`, `FIC`, `DMIC` nem a base de compensação.

## Status apos implementacao

A tabela `gold_ressarcimento_prodist` foi implementada em `midway.apuracao.previa` e passa a ser gerada no fluxo:

```bat
run.bat apuracao_parcial
```

Saidas:

```text
data/marts/Gold_Ressarcimento_PRODIST_<ANOMES>_<timestamp>.CSV
data/marts/Gold_Ressarcimento_PRODIST_<ANOMES>_<timestamp>_RESUMO.TXT
```

Campos principais:

| Campo | Descricao |
| --- | --- |
| `KEI1_CONTINUIDADE` | coeficiente para `DIC`, `FIC` e `DMIC` |
| `KEI2_DICRI` | coeficiente para `DICRI` |
| `KEI3_DISE` | coeficiente para `DISE` |
| `COMP_DIC_PRODIST` | compensacao DIC com piso e teto |
| `COMP_FIC_PRODIST` | compensacao FIC conforme formula `(FICv / FICp) * DICp * VRC / 730 * Kei1` |
| `COMP_DMIC_PRODIST` | compensacao DMIC com piso e teto |
| `COMP_GERAL_CONTINUIDADE_PRODIST` | maior valor entre `DIC`, `FIC` e `DMIC` |
| `COMP_DICRI_PRODIST` | compensacao DICRI com `Kei2` |
| `COMP_DISE_PRODIST` | compensacao DISE com `Kei3` |
| `COMP_TOTAL_PRODIST` | continuidade geral + `DICRI` + `DISE` |
| `STATUS_CALCULO_PRODIST` | marca limitacao conhecida para `DICRI/DISE` agregados por UC |

## Conclusao

Status atual:

```text
[x] Indicadores DIC/FIC coerentes com DEC/FEC liquido
[x] Sobreposicao temporal por UC tratada antes do calculo individual
[x] NUM_MOTIVO_TRAT_DIF_UCI preenchido fora da base apuravel
[x] Formula DIC/DMIC com piso/teto na tabela gold_ressarcimento_prodist
[x] Maior valor entre DIC/FIC/DMIC considerado em COMP_GERAL
[x] Formula FIC conforme PRODIST na tabela gold_ressarcimento_prodist
[x] Kei2/Kei3 para DICRI/DISE na tabela gold_ressarcimento_prodist
[x] Piso R$ 0,01
[x] Teto 18 * VRC
[x] Filtros IQS por `SIGLA_TIQS_DIC`, `SIGLA_REID_DIC`, `SIGLA_TIQS_FIC` e `SIGLA_REID_FIC`
[x] Exclusao de `COD_COMP_INTRP = 52` e `COD_CAUSA_INTRP = 71` de `DIC/FIC/DMIC` e compensacao
[~] Tratamento de DICRI/DISE ainda agregado por UC
[~] Matriz de equivalencia dos codigos IQS x item 178 parcialmente coberta pelas siglas IQS
```

Recomendacao: usar `gold_ressarcimento_prodist` como base financeira PRODIST para `DIC`, `FIC` e `DMIC`; manter `DICRI/DISE` como parcial ate evoluir o calculo para granularidade por evento.
