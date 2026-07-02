# 11 - Proposta de testes automatizados e estatisticos

## Objetivo

Criar uma camada de testes automatizados sobre os dados tratados para garantir que a apuracao de `DIC` e `FIC` esteja correta, auditavel e estavel entre competencias.

Os testes devem combinar:

1. regras deterministicas de negocio;
2. reconciliacao entre tabelas;
3. estatisticas de controle;
4. deteccao de anomalias;
5. amostragem orientada por risco para verificacao manual.

## Status da implementacao

Primeira fase implementada em `unittest`, sem dependencia adicional de `pytest`.

Arquivos criados:

```text
tests/
  __init__.py
  utils.py
  test_contratos_tabelas.py
  test_apuracao_dic_fic.py
  test_sobreposicao_uc.py
  test_ressarcimento_prodist.py

tools/
  gerar_metricas_qualidade.py
  exportar_amostras_auditoria.py
```

Comandos disponiveis:

```bat
run.bat testar_dados
run.bat metricas_qualidade
run.bat amostras_auditoria
```

Resultado medido em `2026-07-02` para `ANOMES=202606`:

- 15 testes automatizados executados;
- 15 testes aprovados apos correcao da regra de sobreposicao;
- a primeira execucao encontrou 300 sobreposicoes residuais na base liquida;
- a correcao removeu o filtro indevido por `INDIC_SIT_PROCES_INDIC_UCI` na avaliacao de sobreposicao e removeu a restricao artificial de `COD_TIPO_INTRP IN ('0', '1', '6')`;
- metricas finais exportadas em `data/marts/Metricas_Qualidade_Dados_202606_20260702105212.CSV`;
- resumo final exportado em `data/marts/Metricas_Qualidade_Dados_202606_20260702105212_RESUMO.TXT`;
- resultado final: 0 metricas criticas e 2 alertas;
- metricas exportadas em `data/marts/Metricas_Qualidade_Dados_202606_20260702092155.CSV`;
- resumo exportado em `data/marts/Metricas_Qualidade_Dados_202606_20260702092155_RESUMO.TXT`;
- amostras exportadas em `data/marts/Amostra_*_202606_20260702092203.CSV`.

O teste falho nao foi removido: ele revelou um problema real e passou a proteger a regra corrigida.

## Principio central

A base canonica para `DIC` e `FIC` deve ser:

```text
silver_interrupcao_uc_apuravel
```

Publicada por compatibilidade como:

```text
gold_apuracao_uc
```

Regras minimas da base:

- `NUM_MOTIVO_TRAT_DIF_UCI` nulo;
- UC faturada;
- sem contagem duplicada por manobra;
- sem sobreposicao temporal indevida por UC;
- respeito a `COD_TIPO_INTRP`;
- interrupcoes longas quando entram em `CI/CHI`, `DIC/FIC`;
- `DIC/FIC` fechando com `CHI/CI_LIQUIDO`.

## Estatisticas atuais de referencia - ANOMES 202606

Estatisticas medidas apos o ajuste de `NUM_MOTIVO_TRAT_DIF_UCI` nulo.

| Controle | Valor |
| --- | ---: |
| `gold_interrupcao_tratada` | 13.312.100 |
| `silver_interrupcao_uc_apuravel` / `gold_apuracao_uc` | 9.213.875 |
| `gold_apuracao_previa` | 360.353 |
| `gold_continuidade_uc` | 2.507.190 |
| `gold_ressarcimento_prodist` | 2.507.190 |
| Sobreposicao total UC exportada | 324.940 |
| Sobreposicao parcial UC exportada | 139.688 |
| Interrupcao sem UC apuravel | 39.771 |
| Interrupcao sem UC exportada para auditoria | 259.873 |
| Auditoria `ESTADO_INTRP = 7` | 1.210 |
| Auditoria outliers bruto | 746 |

Fechamento atual:

| Origem | Linhas | FIC/CI | DIC/CHI |
| --- | ---: | ---: | ---: |
| `gold_apuracao_uc` | 9.213.875 | 1.649.805 | 2.931.684,7600 |
| `gold_apuracao_previa` | 360.353 | 1.649.805 | 2.931.684,7600 |
| `gold_continuidade_uc` | 2.507.190 | 1.649.805 | 2.931.684,7600 |

Distribuicao por `COD_TIPO_INTRP` em `gold_apuracao_uc`:

| `COD_TIPO_INTRP` | Linhas | FIC | DIC |
| --- | ---: | ---: | ---: |
| `1` | 8.678.272 | 1.494.611 | 2.631.928,7044 |
| `2` | 323.038 | 106.007 | 206.869,0356 |
| `3` | 212.565 | 49.187 | 92.887,0200 |

Distribuicao por faixa de duracao:

| Faixa | Linhas | CI/FIC | CHI/DIC |
| --- | ---: | ---: | ---: |
| `<3min` | 7.178.938 | 0 | 0 |
| `3min-1h` | 1.176.320 | 916.406 | 221.128,1925 |
| `1h-6h` | 747.961 | 641.972 | 1.547.649,8033 |
| `6h-24h` | 106.106 | 87.781 | 789.603,1353 |
| `>=24h` | 4.550 | 3.646 | 373.303,6289 |

Ressarcimento PRODIST:

| Controle | Valor |
| --- | ---: |
| UCs avaliadas | 2.507.190 |
| UCs com compensacao | 104.156 |
| `COMP_TOTAL_PRODIST` | 7.497.763,7609 |
| UCs com calculo `DIC/FIC/DMIC` aderente | 2.220.385 |
| UCs com `DICRI/DISE` agregado por UC | 286.805 |

## Camadas de testes propostas

### 1. Testes de existencia e contrato de schema

Objetivo: garantir que o pipeline gerou todas as tabelas esperadas.

Tabelas obrigatorias:

```text
silver_iqs_uc_fatura
silver_iqs_vrc
silver_iqs_metas_uc
silver_interrupcao_tratada
silver_interrupcao_uc_apuravel
gold_apuracao_uc
gold_apuracao_previa
gold_continuidade_uc
gold_ressarcimento_prodist
```

Testes:

- tabela existe;
- quantidade de linhas maior que zero;
- campos obrigatorios existem;
- tipos numericos de `DURACAO_HORA`, `DIC`, `FIC`, `VRC`, `COMP_*` sao validos;
- campos de chave `UC`, `NUM_SEQ_INTRP`, `NUM_OCORRENCIA_ADMS` nao ficam vazios quando exigidos.

### 2. Testes deterministas da base apuravel

Objetivo: bloquear erro de regra de negocio.

Regras obrigatorias:

```sql
-- Nenhum registro apuravel pode ter motivo de tratamento diferenciado
SELECT COUNT(*)
FROM gold_apuracao_uc
WHERE NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NOT NULL;
```

Esperado: `0`.

```sql
-- DIC/FIC devem fechar com CI/CHI liquido
SELECT
    (SELECT SUM(CI_LIQUIDO) FROM gold_apuracao_uc) AS CI_UC,
    (SELECT SUM(FIC) FROM gold_continuidade_uc) AS FIC_UC,
    (SELECT SUM(CHI_LIQUIDO) FROM gold_apuracao_uc) AS CHI_UC,
    (SELECT SUM(DIC) FROM gold_continuidade_uc) AS DIC_UC;
```

Esperado:

- `CI_UC = FIC_UC`;
- `CHI_UC` e `DIC_UC` com diferenca menor que tolerancia decimal, por exemplo `0,001`.

```sql
-- Apuracao previa deve fechar com base por UC
SELECT
    (SELECT SUM(CI_LIQUIDO) FROM gold_apuracao_previa) AS CI_PREVIA,
    (SELECT SUM(CI_LIQUIDO) FROM gold_apuracao_uc) AS CI_UC,
    (SELECT SUM(CHI_LIQUIDO) FROM gold_apuracao_previa) AS CHI_PREVIA,
    (SELECT SUM(CHI_LIQUIDO) FROM gold_apuracao_uc) AS CHI_UC;
```

### 3. Testes de sobreposicao temporal por UC

Objetivo: garantir que sobreposicoes trataveis nao seguem para `DIC/FIC`.

Teste principal:

```sql
WITH base AS (
    SELECT
        NUM_UC_UCI AS UC,
        COD_TIPO_INTRP,
        NUM_SEQ_INTRP,
        DTHR_INICIO_INTRP_UC,
        DATA_HORA_FIM_INTRP
    FROM gold_apuracao_uc
    WHERE CI_LIQUIDO = 1
)
SELECT COUNT(*)
FROM base a
JOIN base b
  ON a.UC = b.UC
 AND a.COD_TIPO_INTRP = b.COD_TIPO_INTRP
 AND a.NUM_SEQ_INTRP <> b.NUM_SEQ_INTRP
 AND a.DTHR_INICIO_INTRP_UC < b.DATA_HORA_FIM_INTRP
 AND b.DTHR_INICIO_INTRP_UC < a.DATA_HORA_FIM_INTRP;
```

Esperado: `0` ou lista residual explicada por regra documentada.

Observacao: este teste deve respeitar `COD_TIPO_INTRP`; eventos de tipos diferentes nao devem ser tratados como sobreposicao indevida automaticamente.

### 4. Testes de manobra

Objetivo: impedir dupla contagem.

```sql
SELECT COUNT(*)
FROM gold_apuracao_uc
WHERE NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL;
```

Esperado: `0`.

Tambem testar normalizacao:

- vazio;
- `0`;
- `0.0`;
- valor igual a propria interrupcao;
- valor diferente da propria interrupcao.

### 5. Testes de duracao

Objetivo: detectar duracoes impossiveis ou suspeitas.

Regras obrigatorias:

```sql
SELECT COUNT(*)
FROM gold_apuracao_uc
WHERE DTHR_INICIO_INTRP_UC IS NULL
   OR DATA_HORA_FIM_INTRP IS NULL
   OR DATA_HORA_FIM_INTRP < DTHR_INICIO_INTRP_UC
   OR DURACAO_HORA < 0;
```

Esperado: `0`.

Regras estatisticas:

- monitorar `p50`, `p90`, `p99`, `max`;
- monitorar volume `>=24h`;
- gerar lista de amostra para duracoes extremas.

SQL:

```sql
SELECT
    COUNT(*) AS linhas,
    MIN(DURACAO_HORA) AS min_h,
    QUANTILE_CONT(DURACAO_HORA, 0.50) AS p50_h,
    QUANTILE_CONT(DURACAO_HORA, 0.90) AS p90_h,
    QUANTILE_CONT(DURACAO_HORA, 0.99) AS p99_h,
    MAX(DURACAO_HORA) AS max_h
FROM gold_apuracao_uc
WHERE CI_LIQUIDO = 1;
```

Importante: duracao `>=24h` nao deve ser removida automaticamente. Deve gerar auditoria, nao filtro.

### 6. Testes estatisticos de estabilidade mensal

Objetivo: detectar mudancas bruscas entre competencias.

Criar tabela historica:

```text
controle_metricas_mensais
```

Campos:

```text
ANOMES
N_GOLD_INTERRUPCAO_TRATADA
N_GOLD_APURACAO_UC
N_GOLD_CONTINUIDADE_UC
TOTAL_CI_LIQUIDO
TOTAL_CHI_LIQUIDO
TOTAL_DIC
TOTAL_FIC
QTD_SOBREPOSICAO_TOTAL_UC
QTD_SOBREPOSICAO_PARCIAL_UC
QTD_INTERRUPCAO_SEM_UC
QTD_MOTIVO_90_R
QTD_MOTIVO_91_D
QTD_DURACAO_GE_24H
P50_DURACAO
P90_DURACAO
P99_DURACAO
TOTAL_COMP_PRODIST
DATA_EXECUCAO
```

Alertas sugeridos:

| Metrica | Alerta amarelo | Alerta vermelho |
| --- | ---: | ---: |
| linhas `gold_interrupcao_tratada` | variacao > 15% | variacao > 30% |
| `CI_LIQUIDO` | variacao > 15% | variacao > 30% |
| `CHI_LIQUIDO` | variacao > 20% | variacao > 40% |
| sobreposicao total UC | variacao > 25% | variacao > 50% |
| sobreposicao parcial UC | variacao > 25% | variacao > 50% |
| interrupcao sem UC | variacao > 25% | variacao > 50% |
| duracao `>=24h` | variacao > 30% | variacao > 60% |
| `COMP_TOTAL_PRODIST` | variacao > 25% | variacao > 50% |

Esses limites devem ser calibrados apos 6 a 12 competencias.

### 7. Testes de ressarcimento PRODIST

Objetivo: garantir aderencia financeira minima.

Regras:

```sql
-- A tabela PRODIST deve ter a mesma quantidade de UCs da continuidade
SELECT
    (SELECT COUNT(*) FROM gold_continuidade_uc) AS continuidade,
    (SELECT COUNT(*) FROM gold_ressarcimento_prodist) AS prodist;
```

```sql
-- COMP_GERAL_CONTINUIDADE_PRODIST deve ser maior valor entre DIC, FIC, DMIC
SELECT COUNT(*)
FROM gold_ressarcimento_prodist
WHERE ABS(
    COMP_GERAL_CONTINUIDADE_PRODIST
    - GREATEST(COMP_DIC_PRODIST, COMP_FIC_PRODIST, COMP_DMIC_PRODIST)
) > 0.001;
```

Esperado: `0`.

```sql
-- Teto 18 * VRC
SELECT COUNT(*)
FROM gold_ressarcimento_prodist
WHERE COMP_TOTAL_PRODIST > (18 * VRC * 3);
```

Observacao: o teto e por indicador. O teste acima e apenas sentinela ampla, pois `COMP_TOTAL_PRODIST` soma continuidade + `DICRI` + `DISE`.

```sql
-- Compensacao positiva nao pode ficar abaixo de R$ 0,01
SELECT COUNT(*)
FROM gold_ressarcimento_prodist
WHERE (COMP_DIC_PRODIST > 0 AND COMP_DIC_PRODIST < 0.01)
   OR (COMP_FIC_PRODIST > 0 AND COMP_FIC_PRODIST < 0.01)
   OR (COMP_DMIC_PRODIST > 0 AND COMP_DMIC_PRODIST < 0.01)
   OR (COMP_DICRI_PRODIST > 0 AND COMP_DICRI_PRODIST < 0.01)
   OR (COMP_DISE_PRODIST > 0 AND COMP_DISE_PRODIST < 0.01);
```

Esperado: `0`.

## Acoes provaveis de tratamento por estatistica

As estatisticas devem indicar qual acao de verificacao executar.

| Sinal estatistico | Acao provavel | Saida esperada |
| --- | --- | --- |
| Alta de sobreposicao total UC | revisar regra de contencao temporal por UC e `COD_TIPO_INTRP` | amostra de UCs contidas e interrupcoes dominantes |
| Alta de sobreposicao parcial UC | revisar ajuste de `DTHR_INICIO_INTRP_UC` e manobra | amostra antes/depois do ajuste |
| Alta de `NUM_MOTIVO_TRAT_DIF_UCI` preenchido | revisar codigos de tratamento diferenciado | ranking por motivo/situacao |
| Alta de interrupcao sem UC | revisar joins de UC, `gold_uc_fatura` e UCs nao faturadas | lista de interrupcoes sem UC apuravel |
| Alta de duracao `>=24h` | auditar outliers sem filtrar automaticamente | lista priorizada por duracao e impacto em CHI |
| Aumento de `COD_TIPO_INTRP` incomum | verificar mudanca de origem ADMS/IQS | distribuicao por tipo |
| Divergencia `DIC/FIC` x `CHI/CI` | bloquear fechamento | falha critica |
| Aumento de compensacao PRODIST | identificar UCs, metas e VRC que mais explicam variacao | top UCs por `COMP_TOTAL_PRODIST` |

## Implementacao

### Estrutura de arquivos

```text
tests/
  __init__.py
  utils.py
  test_contratos_tabelas.py
  test_apuracao_dic_fic.py
  test_sobreposicao_uc.py
  test_ressarcimento_prodist.py

tools/
  gerar_metricas_qualidade.py
  exportar_amostras_auditoria.py
```

### Dependencias

Foi usada a biblioteca padrao `unittest`, sem dependencia nova.

Opcional futuro: migrar para `pytest` quando houver necessidade de relatorios HTML, fixtures mais elaboradas ou parametrizacao por competencia.

### Comandos implementados

Adicionados ao `run.bat`:

```bat
run.bat testar_dados
run.bat metricas_qualidade
run.bat amostras_auditoria
```

Fluxo recomendado:

```bat
run.bat apuracao_parcial
run.bat testar_dados
run.bat metricas_qualidade
run.bat amostras_auditoria
```

## Criterios de aprovacao

### Falha critica

Bloqueia fechamento:

- tabela obrigatoria ausente;
- `NUM_MOTIVO_TRAT_DIF_UCI` preenchido em `gold_apuracao_uc`;
- `DIC/FIC` diferente de `CHI/CI_LIQUIDO`;
- duracao negativa;
- sobreposicao residual por mesma UC e mesmo `COD_TIPO_INTRP`;
- `gold_ressarcimento_prodist` com quantidade diferente de `gold_continuidade_uc`;
- `COMP_GERAL_CONTINUIDADE_PRODIST` diferente do maior entre `DIC`, `FIC`, `DMIC`.

### Alerta

Nao bloqueia automaticamente, mas exige revisao:

- variacao estatistica acima do limite amarelo/vermelho;
- duracao extrema;
- alto volume de interrupcao sem UC;
- alta de `DICRI/DISE` ainda agregado por UC;
- `VRC = 0` em UC com violacao de meta.

## Entregaveis da primeira fase

1. [x] Criar `tests/` com testes deterministas.
2. [x] Criar `tools/gerar_metricas_qualidade.py`.
3. [x] Gerar CSV mensal:

```text
data/marts/Metricas_Qualidade_Dados_<ANOMES>_<timestamp>.CSV
```

4. [x] Gerar resumo:

```text
data/marts/Metricas_Qualidade_Dados_<ANOMES>_<timestamp>_RESUMO.TXT
```

5. [x] Gerar amostras:

```text
data/marts/Amostra_Sobreposicao_Residual_<ANOMES>_<timestamp>.CSV
data/marts/Amostra_Duracao_Extrema_<ANOMES>_<timestamp>.CSV
data/marts/Amostra_Ressarcimento_Alto_<ANOMES>_<timestamp>.CSV
data/marts/Amostra_VRC_Zero_Com_Violacao_<ANOMES>_<timestamp>.CSV
```

## Recomendacao de ordem

1. Implementar testes deterministas de fechamento `DIC/FIC`.
2. Implementar teste de `NUM_MOTIVO_TRAT_DIF_UCI` nulo.
3. Implementar teste de sobreposicao residual por UC e `COD_TIPO_INTRP`.
4. Implementar teste de ressarcimento PRODIST.
5. Criar metricas mensais.
6. Criar alertas estatisticos com base historica.
7. Criar amostras de auditoria priorizadas por impacto em `DIC`, `FIC` e `COMP_TOTAL_PRODIST`.
