from __future__ import annotations

from midway.apuracao.duckdb_utils import tabela_local_existe


def criar_gold_continuidade_uc(con):
    print("Criando gold_continuidade_uc...")

    tabelas = {
        linha[0]
        for linha in con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            """
        ).fetchall()
    }

    if "gold_apuracao_uc" not in tabelas:
        raise RuntimeError("Tabela gold_apuracao_uc nao encontrada.")

    if "gold_uc_fatura" not in tabelas:
        raise RuntimeError("Tabela gold_uc_fatura nao encontrada. Execute run.bat uc_fatura.")

    if "gold_metas_uc" not in tabelas:
        raise RuntimeError("Tabela gold_metas_uc nao encontrada. Execute run.bat metas_uc.")

    if "gold_vrc" not in tabelas:
        raise RuntimeError("Tabela gold_vrc nao encontrada. Execute run.bat vrc.")

    colunas_gold_apuracao_uc = {
        linha[0].upper()
        for linha in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = 'gold_apuracao_uc'
            """
        ).fetchall()
    }

    def coluna_ou_default(nome_coluna: str, default_sql: str) -> str:
        if nome_coluna.upper() in colunas_gold_apuracao_uc:
            return f"a.{nome_coluna}"
        return default_sql

    sigla_tiqs_dic_sql = coluna_ou_default("SIGLA_TIQS_DIC", "'DIC_'")
    sigla_reid_dic_sql = coluna_ou_default("SIGLA_REID_DIC", "NULL")
    sigla_tiqs_fic_sql = coluna_ou_default("SIGLA_TIQS_FIC", "'FIC_'")
    sigla_reid_fic_sql = coluna_ou_default("SIGLA_REID_FIC", "NULL")

    con.execute(
        f"""
        CREATE OR REPLACE TABLE gold_continuidade_uc AS
        WITH uc_faturada AS (
            SELECT DISTINCT
                CAST(UC AS VARCHAR) AS UC,
                MAX(CASE WHEN UPPER(TRIM(CAST(FATURADO AS VARCHAR))) = 'S' THEN 'S' ELSE 'N' END) AS FATURADA
            FROM gold_uc_fatura
            GROUP BY CAST(UC AS VARCHAR)
        ),
        metas AS (
            SELECT
                CAST(ISN_UC AS VARCHAR) AS UC,
                MAX(CAST(COD_GRUPO_NTFN AS VARCHAR)) AS COD_GRUPO_NTFN,
                MAX(CAST(COD_NTFN AS VARCHAR)) AS COD_NTFN,
                MAX(CAST(DESC_NTFN AS VARCHAR)) AS DESC_NTFN,
                MAX(TRY_CAST(META_DIC AS DOUBLE)) AS META_DIC,
                MAX(TRY_CAST(META_FIC AS DOUBLE)) AS META_FIC,
                MAX(TRY_CAST(META_DMIC AS DOUBLE)) AS META_DMIC,
                MAX(TRY_CAST(META_DICRI AS DOUBLE)) AS META_DICRI,
                MAX(TRY_CAST(META_DISE AS DOUBLE)) AS META_DISE
            FROM gold_metas_uc
            GROUP BY CAST(ISN_UC AS VARCHAR)
        ),
        vrc AS (
            SELECT
                CAST(ISN_UC AS VARCHAR) AS UC,
                MAX(CAST(COD_GRUPO_NIVEL_TENSAO_UC AS VARCHAR)) AS COD_GRUPO_NIVEL_TENSAO_UC,
                MAX(CAST(COD_NIVEL_TENSAO_UC AS VARCHAR)) AS COD_NIVEL_TENSAO_UC,
                MAX(TRY_CAST(VRC AS DOUBLE)) AS VRC
            FROM gold_vrc
            GROUP BY CAST(ISN_UC AS VARCHAR)
        ),
        uc_unica_acessante AS (
            SELECT
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(NUM_OPER_CHV_INTRP AS VARCHAR) AS NUM_OPER_CHV_INTRP,
                MIN(CAST(NUM_UC_UCI AS VARCHAR)) AS UC
            FROM gold_interrupcao_tratada
            WHERE TRIM(CAST(INDIC_PROPR_CHVP_INTRP AS VARCHAR)) = 'P'
              AND TRIM(CAST(UC_ACESSANTE AS VARCHAR)) = 'S'
              AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            GROUP BY
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                CAST(NUM_SEQ_INTRP AS VARCHAR),
                CAST(NUM_OPER_CHV_INTRP AS VARCHAR)
            HAVING COUNT(DISTINCT CAST(NUM_UC_UCI AS VARCHAR)) = 1
        ),
        uc_acessante AS (
            SELECT DISTINCT
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(NUM_UC_UCI AS VARCHAR) AS UC
            FROM gold_interrupcao_tratada
            WHERE TRIM(CAST(UC_ACESSANTE AS VARCHAR)) = 'S'
              AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
        ),
        eventos_sem_compensacao AS (
            SELECT
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(NUM_INTRP_UCI AS VARCHAR) AS NUM_INTRP_UCI,
                CAST(NUM_POSTO_UCI AS VARCHAR) AS NUM_POSTO_UCI,
                CAST(NUM_UC_UCI AS VARCHAR) AS UC,
                MAX(
                    CASE
                        WHEN TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) = '52'
                        THEN 1 ELSE 0
                    END
                ) AS EXCLUI_COMPENSACAO_COMP52,
                MAX(
                    CASE
                        WHEN TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)) = '71'
                        THEN 1 ELSE 0
                    END
                ) AS EXCLUI_COMPENSACAO_CAUSA71,
                MAX(
                    CASE
                        WHEN TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) = '52'
                          OR TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)) = '71'
                        THEN 1 ELSE 0
                    END
                ) AS EXCLUI_COMPENSACAO_COMP52_CAUSA71,
                MAX(
                    CASE
                        WHEN TRIM(CAST(INDIC_PROPR_POSTO_INTRP AS VARCHAR)) = 'P'
                        THEN 1 ELSE 0
                    END
                ) AS EXCLUI_COMPENSACAO_POSTO_PARTICULAR
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            GROUP BY
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                CAST(NUM_SEQ_INTRP AS VARCHAR),
                CAST(NUM_INTRP_UCI AS VARCHAR),
                CAST(NUM_POSTO_UCI AS VARCHAR),
                CAST(NUM_UC_UCI AS VARCHAR)
        ),
        base AS (
            SELECT
                CAST(a.NUM_UC_UCI AS VARCHAR) AS UC,
                TRIM(CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) AS TIPO_PROTOC_JUSTIF_UCI,
                TRY_CAST(a.DURACAO_HORA AS DOUBLE) AS DURACAO_HORA,
                COALESCE(NULLIF(TRIM(CAST({sigla_tiqs_dic_sql} AS VARCHAR)), ''), 'DIC_') AS SIGLA_TIQS_DIC,
                NULLIF(TRIM(CAST({sigla_reid_dic_sql} AS VARCHAR)), '') AS SIGLA_REID_DIC,
                COALESCE(NULLIF(TRIM(CAST({sigla_tiqs_fic_sql} AS VARCHAR)), ''), 'FIC_') AS SIGLA_TIQS_FIC,
                NULLIF(TRIM(CAST({sigla_reid_fic_sql} AS VARCHAR)), '') AS SIGLA_REID_FIC,
                CASE
                    WHEN u.UC IS NOT NULL
                    THEN 1 ELSE 0
                END AS EXCLUI_COMPENSACAO_ACESSANTE,
                CASE
                    WHEN ua.UC IS NOT NULL
                    THEN 1 ELSE 0
                END AS EXCLUI_COMPENSACAO_UC_ACESSANTE,
                COALESCE(e.EXCLUI_COMPENSACAO_COMP52, 0) AS EXCLUI_COMPENSACAO_COMP52,
                COALESCE(e.EXCLUI_COMPENSACAO_CAUSA71, 0) AS EXCLUI_COMPENSACAO_CAUSA71,
                CASE
                    WHEN TRIM(CAST(a.COD_COMP_INTRP AS VARCHAR)) = '52'
                      OR TRIM(CAST(a.COD_CAUSA_INTRP AS VARCHAR)) = '71'
                    THEN 1 ELSE 0
                END AS EXCLUI_COMPENSACAO_COMP52_CAUSA71,
                COALESCE(e.EXCLUI_COMPENSACAO_POSTO_PARTICULAR, 0) AS EXCLUI_COMPENSACAO_POSTO_PARTICULAR,
                CASE
                    WHEN UPPER(TRIM(CAST(a.INTERRUPCAO_LONGA AS VARCHAR))) IN ('SIM', 'TRUE', '1')
                    THEN 1 ELSE 0
                END AS INTERRUPCAO_LONGA,
                CASE
                    WHEN UPPER(TRIM(CAST(a.INTERRUPCAO_CONTABILIZAVEL AS VARCHAR))) IN ('SIM', 'TRUE', '1')
                    THEN 1 ELSE 0
                END AS INTERRUPCAO_CONTABILIZAVEL
            FROM gold_apuracao_uc a
            LEFT JOIN uc_unica_acessante u
              ON u.NUM_OCORRENCIA_ADMS = CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)
             AND u.NUM_SEQ_INTRP = CAST(a.NUM_SEQ_INTRP AS VARCHAR)
             AND u.UC = CAST(a.NUM_UC_UCI AS VARCHAR)
            LEFT JOIN uc_acessante ua
              ON ua.NUM_OCORRENCIA_ADMS = CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)
             AND ua.NUM_SEQ_INTRP = CAST(a.NUM_SEQ_INTRP AS VARCHAR)
             AND ua.UC = CAST(a.NUM_UC_UCI AS VARCHAR)
            LEFT JOIN eventos_sem_compensacao e
              ON e.NUM_OCORRENCIA_ADMS = CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)
             AND e.NUM_SEQ_INTRP = CAST(a.NUM_SEQ_INTRP AS VARCHAR)
             AND e.NUM_INTRP_UCI = CAST(a.NUM_INTRP_UCI AS VARCHAR)
             AND e.NUM_POSTO_UCI = CAST(a.NUM_POSTO_UCI AS VARCHAR)
             AND e.UC = CAST(a.NUM_UC_UCI AS VARCHAR)
            WHERE NULLIF(TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
        ),
        agregado AS (
            SELECT
                UC,
                STRING_AGG(DISTINCT COALESCE(SIGLA_TIQS_DIC, 'DIC_'), '; ') AS SIGLAS_TIQS_DIC,
                STRING_AGG(DISTINCT COALESCE(SIGLA_REID_DIC, 'SEM_REGRA'), '; ') AS SIGLAS_REID_DIC,
                STRING_AGG(DISTINCT COALESCE(SIGLA_TIQS_FIC, 'FIC_'), '; ') AS SIGLAS_TIQS_FIC,
                STRING_AGG(DISTINCT COALESCE(SIGLA_REID_FIC, 'SEM_REGRA'), '; ') AS SIGLAS_REID_FIC,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
                         AND SIGLA_REID_DIC IS NULL
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DIC,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_FIC, 'FIC_'), 1, 4) = 'FIC_'
                         AND SIGLA_REID_FIC IS NULL
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                        THEN 1 ELSE 0
                    END
                ) AS FIC,
                MAX(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
                         AND SIGLA_REID_DIC IS NULL
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DMIC,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
                         AND COALESCE(SIGLA_REID_DIC, 'X') NOT IN ('DFC','USU','USI','ACI','FM','ERR','DUP','CHP','DFI','PTP')
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DIC_BRT,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_FIC, 'FIC_'), 1, 4) = 'FIC_'
                         AND COALESCE(SIGLA_REID_FIC, 'X') NOT IN ('DFC','USU','USI','ACI','FM','ERR','DUP','CHP','DFI','PTP','MAN')
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                        THEN 1 ELSE 0
                    END
                ) AS FIC_BRT,
                MAX(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
                         AND COALESCE(SIGLA_REID_DIC, 'X') NOT IN ('DFC','USU','USI','ACI','FM','ERR','DUP','CHP','DFI','PTP')
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DMIC_BRT,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
                         AND SIGLA_REID_DIC IS NULL
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_UC_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                         AND EXCLUI_COMPENSACAO_POSTO_PARTICULAR = 0
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DIC_BASE_COMPENSACAO,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_FIC, 'FIC_'), 1, 4) = 'FIC_'
                         AND SIGLA_REID_FIC IS NULL
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_UC_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                         AND EXCLUI_COMPENSACAO_POSTO_PARTICULAR = 0
                        THEN 1 ELSE 0
                    END
                ) AS FIC_BASE_COMPENSACAO,
                MAX(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '0'
                         AND SUBSTR(COALESCE(SIGLA_TIQS_DIC, 'DIC_'), 1, 4) = 'DIC_'
                         AND SIGLA_REID_DIC IS NULL
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_UC_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                         AND EXCLUI_COMPENSACAO_POSTO_PARTICULAR = 0
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DMIC_BASE_COMPENSACAO,
                MAX(EXCLUI_COMPENSACAO_ACESSANTE) AS TEM_CHAVE_PARTICULAR,
                MAX(EXCLUI_COMPENSACAO_UC_ACESSANTE) AS TEM_UC_ACESSANTE,
                MAX(EXCLUI_COMPENSACAO_COMP52) AS TEM_COMP52,
                MAX(EXCLUI_COMPENSACAO_CAUSA71) AS TEM_CAUSA71,
                MAX(EXCLUI_COMPENSACAO_COMP52_CAUSA71) AS TEM_COMP52_CAUSA71,
                MAX(EXCLUI_COMPENSACAO_POSTO_PARTICULAR) AS TEM_POSTO_PARTICULAR,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '1'
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DIC_DICRI,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '1'
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_UC_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                         AND EXCLUI_COMPENSACAO_POSTO_PARTICULAR = 0
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DICRI_BASE_COMPENSACAO,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI = '1'
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                        THEN 1 ELSE 0
                    END
                ) AS FIC_DICRI,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI IN ('5', '6')
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DIC_ISE,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI IN ('5', '6')
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                         AND EXCLUI_COMPENSACAO_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_UC_ACESSANTE = 0
                         AND EXCLUI_COMPENSACAO_COMP52 = 0
                         AND EXCLUI_COMPENSACAO_CAUSA71 = 0
                         AND EXCLUI_COMPENSACAO_POSTO_PARTICULAR = 0
                        THEN COALESCE(DURACAO_HORA, 0) ELSE 0
                    END
                ) AS DISE_BASE_COMPENSACAO,
                SUM(
                    CASE
                        WHEN TIPO_PROTOC_JUSTIF_UCI IN ('5', '6')
                         AND INTERRUPCAO_LONGA = 1
                         AND INTERRUPCAO_CONTABILIZAVEL = 1
                        THEN 1 ELSE 0
                    END
                ) AS FIC_ISE
            FROM base
            GROUP BY UC
        ),
        enriquecido AS (
        SELECT
            a.UC,
            a.SIGLAS_TIQS_DIC,
            a.SIGLAS_REID_DIC,
            a.SIGLAS_TIQS_FIC,
            a.SIGLAS_REID_FIC,
            a.DIC,
            a.FIC,
            a.DMIC,
            a.DIC_BRT,
            a.FIC_BRT,
            a.DMIC_BRT,
            a.DIC_BASE_COMPENSACAO,
            a.FIC_BASE_COMPENSACAO,
            a.DMIC_BASE_COMPENSACAO,
            CASE
                WHEN COALESCE(a.TEM_CHAVE_PARTICULAR, 0) > 0
                THEN 'S'
                ELSE 'N'
            END AS CHAVE_PARTICULAR,
            CASE
                WHEN COALESCE(a.TEM_UC_ACESSANTE, 0) > 0
                THEN 'S'
                ELSE 'N'
            END AS UC_ACESSANTE_COMPENSACAO,
            CASE
                WHEN COALESCE(a.TEM_COMP52, 0) > 0
                THEN 'S'
                ELSE 'N'
            END AS COMP52,
            CASE
                WHEN COALESCE(a.TEM_CAUSA71, 0) > 0
                THEN 'S'
                ELSE 'N'
            END AS CAUSA71,
            CASE
                WHEN COALESCE(a.TEM_COMP52_CAUSA71, 0) > 0
                THEN 'S'
                ELSE 'N'
            END AS COMP52_CAUSA71,
            CASE
                WHEN COALESCE(a.TEM_POSTO_PARTICULAR, 0) > 0
                THEN 'S'
                ELSE 'N'
            END AS POSTO_PARTICULAR,
            a.DIC_DICRI,
            a.DICRI_BASE_COMPENSACAO,
            a.FIC_DICRI,
            a.DIC_ISE,
            a.DISE_BASE_COMPENSACAO,
            a.FIC_ISE,
            COALESCE(f.FATURADA, 'N') AS FATURADA,
            COALESCE(v.COD_GRUPO_NIVEL_TENSAO_UC, m.COD_GRUPO_NTFN) AS COD_GRUPO_NIVEL_TENSAO_UC,
            COALESCE(v.COD_NIVEL_TENSAO_UC, m.COD_NTFN) AS COD_NIVEL_TENSAO_UC,
            m.DESC_NTFN AS GRUPO_TENSAO,
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
            m.META_DIC,
            m.META_FIC,
            m.META_DMIC,
            m.META_DICRI,
            m.META_DISE,
            CASE
                WHEN COALESCE(m.META_DIC, 0) > 0 AND a.DIC > m.META_DIC
                THEN ((a.DIC / m.META_DIC) - 1) * 100
                ELSE 0
            END AS "%_ULTRAPASSOU_META_DIC",
            CASE
                WHEN COALESCE(m.META_FIC, 0) > 0 AND a.FIC > m.META_FIC
                THEN ((a.FIC / m.META_FIC) - 1) * 100
                ELSE 0
            END AS "%_ULTRAPASSOU_META_FIC",
            CASE
                WHEN COALESCE(m.META_DMIC, 0) > 0 AND a.DMIC > m.META_DMIC
                THEN ((a.DMIC / m.META_DMIC) - 1) * 100
                ELSE 0
            END AS "%_ULTRAPASSOU_META_DMIC",
            CASE
                WHEN COALESCE(m.META_DICRI, 0) > 0 AND a.DIC_DICRI > m.META_DICRI
                THEN ((a.DIC_DICRI / m.META_DICRI) - 1) * 100
                ELSE 0
            END AS "%_ULTRAPASSOU_META_DICRI",
            CASE
                WHEN COALESCE(m.META_DISE, 0) > 0 AND a.DIC_ISE > m.META_DISE
                THEN ((a.DIC_ISE / m.META_DISE) - 1) * 100
                ELSE 0
            END AS "%_ULTRAPASSOU_META_DISE"
        FROM agregado a
        LEFT JOIN uc_faturada f
          ON f.UC = a.UC
        LEFT JOIN metas m
          ON m.UC = a.UC
        LEFT JOIN vrc v
          ON v.UC = a.UC
        )
        SELECT
            *,
            CASE
                WHEN FATURADA = 'S'
                 AND COALESCE(META_DIC, 0) > 0
                 AND COALESCE(DIC_BASE_COMPENSACAO, 0) > META_DIC
                THEN COALESCE(VRC, 0) * (COALESCE(DIC_BASE_COMPENSACAO, 0) / 730.0) * COALESCE(KEI, 0)
                ELSE 0
            END AS COMP_DIC,
            CASE
                WHEN FATURADA = 'S'
                 AND COALESCE(META_FIC, 0) > 0
                 AND COALESCE(FIC_BASE_COMPENSACAO, 0) > META_FIC
                THEN COALESCE(VRC, 0) * (COALESCE(FIC_BASE_COMPENSACAO, 0) / 730.0) * COALESCE(KEI, 0)
                ELSE 0
            END AS COMP_FIC,
            CASE
                WHEN FATURADA = 'S'
                 AND COALESCE(META_DMIC, 0) > 0
                 AND COALESCE(DMIC_BASE_COMPENSACAO, 0) > META_DMIC
                THEN COALESCE(VRC, 0) * (COALESCE(DMIC_BASE_COMPENSACAO, 0) / 730.0) * COALESCE(KEI, 0)
                ELSE 0
            END AS COMP_DMIC,
            CASE
                WHEN FATURADA = 'S'
                 AND COALESCE(META_DICRI, 0) > 0
                 AND COALESCE(DICRI_BASE_COMPENSACAO, 0) > META_DICRI
                THEN COALESCE(VRC, 0) * (COALESCE(DICRI_BASE_COMPENSACAO, 0) / 730.0) * COALESCE(KEI, 0)
                ELSE 0
            END AS COMP_DICRI,
            CASE
                WHEN FATURADA = 'S'
                 AND COALESCE(META_DISE, 0) > 0
                 AND COALESCE(DISE_BASE_COMPENSACAO, 0) > META_DISE
                THEN COALESCE(VRC, 0) * (COALESCE(DISE_BASE_COMPENSACAO, 0) / 730.0) * COALESCE(KEI, 0)
                ELSE 0
            END AS COMP_DISE,
            GREATEST(
                CASE
                    WHEN FATURADA = 'S'
                     AND COALESCE(META_DIC, 0) > 0
                     AND COALESCE(DIC_BASE_COMPENSACAO, 0) > META_DIC
                    THEN COALESCE(VRC, 0) * (COALESCE(DIC_BASE_COMPENSACAO, 0) / 730.0) * COALESCE(KEI, 0)
                    ELSE 0
                END,
                CASE
                    WHEN FATURADA = 'S'
                     AND COALESCE(META_FIC, 0) > 0
                     AND COALESCE(FIC_BASE_COMPENSACAO, 0) > META_FIC
                    THEN COALESCE(VRC, 0) * (COALESCE(FIC_BASE_COMPENSACAO, 0) / 730.0) * COALESCE(KEI, 0)
                    ELSE 0
                END,
                CASE
                    WHEN FATURADA = 'S'
                     AND COALESCE(META_DMIC, 0) > 0
                     AND COALESCE(DMIC_BASE_COMPENSACAO, 0) > META_DMIC
                    THEN COALESCE(VRC, 0) * (COALESCE(DMIC_BASE_COMPENSACAO, 0) / 730.0) * COALESCE(KEI, 0)
                    ELSE 0
                END
            ) AS COMP_GERAL
        FROM enriquecido
        """
    )
