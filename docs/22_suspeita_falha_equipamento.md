# 22 - Suspeita de Falha de Equipamento

## Objetivo

Identificar, em caráter exploratório, situações em que um equipamento ou ponto operacional pode ter registrado interrupções indevidas por falha de comunicação, automação, medição ou comportamento anômalo do OMS/ADMS.

O caso motivador é o padrão observado em que um equipamento apresentou uma interrupção longa e, no mesmo dia, registrou várias interrupções curtas subsequentes, afetando grande volume de UCs, porém sem volume proporcional de reclamações.

Esse comportamento sugere que parte das interrupções pode não representar uma percepção real do consumidor, mas sim repetição indevida de registros para o mesmo equipamento ou chave.

## Hipótese operacional

Uma ocorrência é suspeita quando existe concentração de interrupções no mesmo dia e no mesmo agrupamento elétrico/equipamento, com as seguintes características:

- uma interrupção longa inicial;
- várias interrupções curtas depois da interrupção longa;
- alto volume de UCs afetadas;
- muitas aberturas ou interrupções no mesmo dia;
- baixo ou nenhum volume de reclamações vinculadas;
- recorrência no mesmo equipamento, chave, posto, alimentador ou conjunto.

## Fontes de dados

### Base IQS/ADMS processada

Tabela principal:

```text
gold_interrupcao_tratada
```

Campos relevantes:

| Campo | Uso |
| --- | --- |
| `NUM_OCORRENCIA_ADMS` | ocorrência OMS/ADMS |
| `NUM_SEQ_INTRP` | interrupção |
| `NUM_UC_UCI` | unidade consumidora afetada |
| `COD_CONJTO_ELET_ANEEL_INTRP` | conjunto elétrico |
| `ALIM_INTRP` | alimentador |
| `NUM_OPER_CHV_INTRP` | chave operacional |
| `NUM_GEO_CHV_INTRP` | chave geográfica/equipamento |
| `PID_POSTO_PIN` | posto/equipamento |
| `DATA_HORA_INIC_INTRP` | início da interrupção |
| `DATA_HORA_FIM_INTRP` | fim da interrupção |
| `COD_CAUSA_INTRP` | causa |
| `COD_COMP_INTRP` | componente |

### Reclamações DBGUO

Tabela materializada:

```text
silver_dbguo_reclamacoes
```

Campos relevantes:

| Campo | Uso |
| --- | --- |
| `UC` | unidade consumidora reclamante |
| `DTHR_RECLAMACAO` | horário da reclamação |
| `NUM_OCORRENCIA_ADMS` | ocorrência provável vinculada |
| `NUM_SEQ_INTRP` | interrupção provável vinculada |
| `SCORE_VINCULO_RECLAMACAO` | força do vínculo reclamação/interrupção |
| `CLASSIFICACAO_VINCULO_RECLAMACAO` | classificação textual do vínculo |

## Agrupamento sugerido

A análise deve agrupar os eventos por:

```text
DATA_EVENTO
COD_CONJTO_ELET_ANEEL_INTRP
ALIM_INTRP
NUM_OPER_CHV_INTRP
NUM_GEO_CHV_INTRP
PID_POSTO_PIN
```

A `REGIONAL` não é obrigatória para esta análise, pois a suspeita está mais ligada ao comportamento do equipamento/chave do que à estrutura administrativa.

## Métricas calculadas

| Métrica | Descrição |
| --- | --- |
| `QTD_INTERRUPCOES_DIA` | quantidade de interrupções no agrupamento/dia |
| `QTD_OCORRENCIAS_DIA` | quantidade de ocorrências distintas no agrupamento/dia |
| `MAX_UCS_EM_INTERRUPCAO` | maior quantidade de UCs em uma interrupção do agrupamento |
| `QTD_LINHAS_UC_AFETADAS` | soma das UCs afetadas por interrupção |
| `QTD_INTERRUPCOES_ATE_6MIN` | interrupções com duração até 6 minutos |
| `QTD_INTERRUPCOES_ATE_15MIN` | interrupções com duração até 15 minutos |
| `QTD_INTERRUPCOES_ATE_30MIN` | interrupções com duração até 30 minutos |
| `QTD_INTERRUPCOES_LONGAS` | interrupções com duração igual ou maior que 1 hora |
| `MAIOR_DURACAO_H` | maior duração no agrupamento |
| `SOMA_DURACAO_H` | soma das durações no agrupamento |
| `PRIMEIRA_INTERRUPCAO` | primeiro início do agrupamento |
| `ULTIMA_INTERRUPCAO` | último fim do agrupamento |
| `QTD_RECLAMACOES` | reclamações vinculadas ao agrupamento |
| `INDICE_RECLAMACAO_UC` | reclamações dividido pelo maior volume de UCs afetadas |

## Score de suspeita

Score inicial sugerido:

| Condição | Pontos |
| --- | ---: |
| `MAX_UCS_EM_INTERRUPCAO >= 4000` | 30 |
| `QTD_INTERRUPCOES_DIA >= 10` | 25 |
| `QTD_INTERRUPCOES_ATE_15MIN >= 5` | 20 |
| `QTD_INTERRUPCOES_LONGAS >= 1` | 15 |
| `MAIOR_DURACAO_H >= 1` | 10 |
| `QTD_RECLAMACOES = 0` | 10 |
| `INDICE_RECLAMACAO_UC <= 0.001` | 10 |

Classificação sugerida:

| Score | Classificação |
| ---: | --- |
| `>= 80` | Crítico |
| `>= 60` | Alto |
| `>= 40` | Médio |
| `< 40` | Baixo |

## SQL exploratório inicial

```sql
WITH eventos AS (
    SELECT
        CAST(DATA_HORA_INIC_INTRP AS DATE) AS DATA_EVENTO,
        COD_CONJTO_ELET_ANEEL_INTRP AS CONJUNTO,
        ALIM_INTRP,
        NUM_OPER_CHV_INTRP,
        NUM_GEO_CHV_INTRP,
        PID_POSTO_PIN,
        NUM_OCORRENCIA_ADMS,
        NUM_SEQ_INTRP,
        COUNT(DISTINCT NUM_UC_UCI) AS QTD_UCS,
        MIN(DATA_HORA_INIC_INTRP) AS INICIO,
        MAX(DATA_HORA_FIM_INTRP) AS FIM,
        DATE_DIFF(
            'minute',
            MIN(DATA_HORA_INIC_INTRP),
            MAX(DATA_HORA_FIM_INTRP)
        ) / 60.0 AS DURACAO_H
    FROM gold_interrupcao_tratada
    WHERE NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
    GROUP BY
        CAST(DATA_HORA_INIC_INTRP AS DATE),
        COD_CONJTO_ELET_ANEEL_INTRP,
        ALIM_INTRP,
        NUM_OPER_CHV_INTRP,
        NUM_GEO_CHV_INTRP,
        PID_POSTO_PIN,
        NUM_OCORRENCIA_ADMS,
        NUM_SEQ_INTRP
),
agrupado AS (
    SELECT
        DATA_EVENTO,
        CONJUNTO,
        ALIM_INTRP,
        NUM_OPER_CHV_INTRP,
        NUM_GEO_CHV_INTRP,
        PID_POSTO_PIN,
        COUNT(*) AS QTD_INTERRUPCOES_DIA,
        COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS_DIA,
        SUM(QTD_UCS) AS QTD_LINHAS_UC_AFETADAS,
        MAX(QTD_UCS) AS MAX_UCS_EM_INTERRUPCAO,
        SUM(CASE WHEN DURACAO_H <= 0.10 THEN 1 ELSE 0 END) AS QTD_INTERRUPCOES_ATE_6MIN,
        SUM(CASE WHEN DURACAO_H <= 0.25 THEN 1 ELSE 0 END) AS QTD_INTERRUPCOES_ATE_15MIN,
        SUM(CASE WHEN DURACAO_H <= 0.50 THEN 1 ELSE 0 END) AS QTD_INTERRUPCOES_ATE_30MIN,
        SUM(CASE WHEN DURACAO_H >= 1 THEN 1 ELSE 0 END) AS QTD_INTERRUPCOES_LONGAS,
        MAX(DURACAO_H) AS MAIOR_DURACAO_H,
        SUM(DURACAO_H) AS SOMA_DURACAO_H,
        MIN(INICIO) AS PRIMEIRA_INTERRUPCAO,
        MAX(FIM) AS ULTIMA_INTERRUPCAO,
        STRING_AGG(
            DISTINCT CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
            ', '
            ORDER BY CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)
        ) AS OCORRENCIAS,
        STRING_AGG(
            DISTINCT CAST(NUM_SEQ_INTRP AS VARCHAR),
            ', '
            ORDER BY CAST(NUM_SEQ_INTRP AS VARCHAR)
        ) AS INTERRUPCOES
    FROM eventos
    GROUP BY
        DATA_EVENTO,
        CONJUNTO,
        ALIM_INTRP,
        NUM_OPER_CHV_INTRP,
        NUM_GEO_CHV_INTRP,
        PID_POSTO_PIN
),
reclamacoes AS (
    SELECT
        CAST(INICIO_INTERRUPCAO_UC AS DATE) AS DATA_EVENTO,
        CONJUNTO,
        ALIM_INTRP,
        NUM_OPER_CHV_INTRP,
        NUM_GEO_CHV_INTRP,
        COUNT(DISTINCT ID_RECLAMACAO) AS QTD_RECLAMACOES
    FROM silver_dbguo_reclamacoes
    WHERE CLASSIFICACAO_VINCULO_RECLAMACAO <> 'SEM_OCORRENCIA_PROVAVEL'
    GROUP BY
        CAST(INICIO_INTERRUPCAO_UC AS DATE),
        CONJUNTO,
        ALIM_INTRP,
        NUM_OPER_CHV_INTRP,
        NUM_GEO_CHV_INTRP
)
SELECT
    a.*,
    COALESCE(r.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
    COALESCE(r.QTD_RECLAMACOES, 0) / NULLIF(a.MAX_UCS_EM_INTERRUPCAO, 0) AS INDICE_RECLAMACAO_UC,
    (
        CASE WHEN a.MAX_UCS_EM_INTERRUPCAO >= 4000 THEN 30 ELSE 0 END
      + CASE WHEN a.QTD_INTERRUPCOES_DIA >= 10 THEN 25 ELSE 0 END
      + CASE WHEN a.QTD_INTERRUPCOES_ATE_15MIN >= 5 THEN 20 ELSE 0 END
      + CASE WHEN a.QTD_INTERRUPCOES_LONGAS >= 1 THEN 15 ELSE 0 END
      + CASE WHEN a.MAIOR_DURACAO_H >= 1 THEN 10 ELSE 0 END
      + CASE WHEN COALESCE(r.QTD_RECLAMACOES, 0) = 0 THEN 10 ELSE 0 END
      + CASE
            WHEN COALESCE(r.QTD_RECLAMACOES, 0) / NULLIF(a.MAX_UCS_EM_INTERRUPCAO, 0) <= 0.001
            THEN 10 ELSE 0
        END
    ) AS SCORE_SUSPEITA_FALHA_EQUIPAMENTO,
    CASE
        WHEN (
            CASE WHEN a.MAX_UCS_EM_INTERRUPCAO >= 4000 THEN 30 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_DIA >= 10 THEN 25 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_ATE_15MIN >= 5 THEN 20 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_LONGAS >= 1 THEN 15 ELSE 0 END
          + CASE WHEN a.MAIOR_DURACAO_H >= 1 THEN 10 ELSE 0 END
          + CASE WHEN COALESCE(r.QTD_RECLAMACOES, 0) = 0 THEN 10 ELSE 0 END
          + CASE
                WHEN COALESCE(r.QTD_RECLAMACOES, 0) / NULLIF(a.MAX_UCS_EM_INTERRUPCAO, 0) <= 0.001
                THEN 10 ELSE 0
            END
        ) >= 80 THEN 'Crítico'
        WHEN (
            CASE WHEN a.MAX_UCS_EM_INTERRUPCAO >= 4000 THEN 30 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_DIA >= 10 THEN 25 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_ATE_15MIN >= 5 THEN 20 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_LONGAS >= 1 THEN 15 ELSE 0 END
          + CASE WHEN a.MAIOR_DURACAO_H >= 1 THEN 10 ELSE 0 END
          + CASE WHEN COALESCE(r.QTD_RECLAMACOES, 0) = 0 THEN 10 ELSE 0 END
          + CASE
                WHEN COALESCE(r.QTD_RECLAMACOES, 0) / NULLIF(a.MAX_UCS_EM_INTERRUPCAO, 0) <= 0.001
                THEN 10 ELSE 0
            END
        ) >= 60 THEN 'Alto'
        WHEN (
            CASE WHEN a.MAX_UCS_EM_INTERRUPCAO >= 4000 THEN 30 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_DIA >= 10 THEN 25 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_ATE_15MIN >= 5 THEN 20 ELSE 0 END
          + CASE WHEN a.QTD_INTERRUPCOES_LONGAS >= 1 THEN 15 ELSE 0 END
          + CASE WHEN a.MAIOR_DURACAO_H >= 1 THEN 10 ELSE 0 END
          + CASE WHEN COALESCE(r.QTD_RECLAMACOES, 0) = 0 THEN 10 ELSE 0 END
          + CASE
                WHEN COALESCE(r.QTD_RECLAMACOES, 0) / NULLIF(a.MAX_UCS_EM_INTERRUPCAO, 0) <= 0.001
                THEN 10 ELSE 0
            END
        ) >= 40 THEN 'Médio'
        ELSE 'Baixo'
    END AS FAIXA_SUSPEITA
FROM agrupado a
LEFT JOIN reclamacoes r
  ON r.DATA_EVENTO = a.DATA_EVENTO
 AND COALESCE(CAST(r.CONJUNTO AS VARCHAR), '') = COALESCE(CAST(a.CONJUNTO AS VARCHAR), '')
 AND COALESCE(CAST(r.ALIM_INTRP AS VARCHAR), '') = COALESCE(CAST(a.ALIM_INTRP AS VARCHAR), '')
 AND COALESCE(CAST(r.NUM_OPER_CHV_INTRP AS VARCHAR), '') = COALESCE(CAST(a.NUM_OPER_CHV_INTRP AS VARCHAR), '')
 AND COALESCE(CAST(r.NUM_GEO_CHV_INTRP AS VARCHAR), '') = COALESCE(CAST(a.NUM_GEO_CHV_INTRP AS VARCHAR), '')
WHERE a.QTD_INTERRUPCOES_DIA >= 5
  AND a.MAX_UCS_EM_INTERRUPCAO >= 1000
ORDER BY
    SCORE_SUSPEITA_FALHA_EQUIPAMENTO DESC,
    a.MAX_UCS_EM_INTERRUPCAO DESC,
    a.QTD_INTERRUPCOES_DIA DESC;
```

## Interpretação

A análise não afirma automaticamente que houve erro. Ela apenas prioriza casos que merecem investigação operacional.

A hipótese de falha fica mais forte quando:

- muitas UCs são afetadas;
- há várias interrupções no mesmo dia;
- a maioria das interrupções é curta;
- existe uma interrupção longa inicial;
- o número de reclamações é muito baixo em relação ao impacto estimado;
- as interrupções se concentram no mesmo equipamento/chave.

## Próxima etapa recomendada

Materializar essa análise como tabela gold:

```text
gold_suspeita_falha_equipamento
```

E exibir no painel em uma aba de Analytics Pós-Operação ou Avaliação de UC.

A tabela deve ser recalculada após:

```bat
run.bat apuracao_parcial
materializar_dbguo_reclamacoes_silver.bat
```

No futuro, a materialização pode ser integrada ao `run.bat apuracao_parcial`, desde que a base DBGUO já esteja disponível.
