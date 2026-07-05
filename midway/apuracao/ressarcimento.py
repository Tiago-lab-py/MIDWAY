from __future__ import annotations

from midway.apuracao.duckdb_utils import tabela_local_existe


def criar_gold_ressarcimento_prodist(con):
    print("Criando gold_ressarcimento_prodist...")

    if not tabela_local_existe(con, "gold_continuidade_uc"):
        raise RuntimeError("Tabela gold_continuidade_uc nao encontrada.")

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_ressarcimento_prodist AS
        WITH base AS (
            SELECT
                c.*,
                CASE
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'A'
                     AND COALESCE(c.COD_NIVEL_TENSAO_UC, '') IN ('1','2','3')
                    THEN 'AT'
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'A'
                     AND COALESCE(c.COD_NIVEL_TENSAO_UC, '') IN ('3a','3A','4','S')
                    THEN 'MT'
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'B'
                    THEN 'BT'
                    ELSE 'NAO_CLASSIFICADO'
                END AS CLASSE_TENSAO_PRODIST,
                CASE
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'A'
                     AND COALESCE(c.COD_NIVEL_TENSAO_UC, '') IN ('1','2','3')
                    THEN 108
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'A'
                     AND COALESCE(c.COD_NIVEL_TENSAO_UC, '') IN ('3a','3A','4','S')
                    THEN 40
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'B'
                    THEN 34
                    ELSE 0
                END AS KEI1_CONTINUIDADE,
                CASE
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'A'
                     AND COALESCE(c.COD_NIVEL_TENSAO_UC, '') IN ('3a','3A','4','S')
                    THEN 20
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'B'
                    THEN 14
                    ELSE 0
                END AS KEI2_DICRI,
                CASE
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'A'
                     AND COALESCE(c.COD_NIVEL_TENSAO_UC, '') IN ('3a','3A','4','S')
                    THEN 20
                    WHEN COALESCE(c.COD_GRUPO_NIVEL_TENSAO_UC, '') = 'B'
                    THEN 14
                    ELSE 0
                END AS KEI3_DISE
            FROM gold_continuidade_uc c
        ),
        bruta AS (
            SELECT
                *,
                CASE
                    WHEN FATURADA = 'S'
                     AND COALESCE(COMP52, 'N') <> 'S'
                     AND COALESCE(CAUSA71, 'N') <> 'S'
                     AND COALESCE(VRC, 0) > 0
                     AND COALESCE(META_DIC, 0) > 0
                     AND COALESCE(DIC_BASE_COMPENSACAO, 0) > META_DIC
                    THEN COALESCE(DIC_BASE_COMPENSACAO, 0) * COALESCE(VRC, 0) / 730.0 * COALESCE(KEI1_CONTINUIDADE, 0)
                    ELSE 0
                END AS COMP_DIC_BRUTA_PRODIST,
                CASE
                    WHEN FATURADA = 'S'
                     AND COALESCE(COMP52, 'N') <> 'S'
                     AND COALESCE(CAUSA71, 'N') <> 'S'
                     AND COALESCE(VRC, 0) > 0
                     AND COALESCE(META_FIC, 0) > 0
                     AND COALESCE(META_DIC, 0) > 0
                     AND COALESCE(FIC_BASE_COMPENSACAO, 0) > META_FIC
                    THEN (COALESCE(FIC_BASE_COMPENSACAO, 0) / META_FIC) * META_DIC * COALESCE(VRC, 0) / 730.0 * COALESCE(KEI1_CONTINUIDADE, 0)
                    ELSE 0
                END AS COMP_FIC_BRUTA_PRODIST,
                CASE
                    WHEN FATURADA = 'S'
                     AND COALESCE(COMP52, 'N') <> 'S'
                     AND COALESCE(CAUSA71, 'N') <> 'S'
                     AND COALESCE(VRC, 0) > 0
                     AND COALESCE(META_DMIC, 0) > 0
                     AND COALESCE(DMIC_BASE_COMPENSACAO, 0) > META_DMIC
                    THEN COALESCE(DMIC_BASE_COMPENSACAO, 0) * COALESCE(VRC, 0) / 730.0 * COALESCE(KEI1_CONTINUIDADE, 0)
                    ELSE 0
                END AS COMP_DMIC_BRUTA_PRODIST,
                CASE
                    WHEN FATURADA = 'S'
                     AND COALESCE(COMP52, 'N') <> 'S'
                     AND COALESCE(CAUSA71, 'N') <> 'S'
                     AND COALESCE(VRC, 0) > 0
                     AND COALESCE(META_DICRI, 0) > 0
                     AND COALESCE(DICRI_BASE_COMPENSACAO, 0) > META_DICRI
                    THEN COALESCE(DICRI_BASE_COMPENSACAO, 0) * COALESCE(VRC, 0) / 730.0 * COALESCE(KEI2_DICRI, 0)
                    ELSE 0
                END AS COMP_DICRI_BRUTA_PRODIST,
                CASE
                    WHEN FATURADA = 'S'
                     AND COALESCE(COMP52, 'N') <> 'S'
                     AND COALESCE(CAUSA71, 'N') <> 'S'
                     AND COALESCE(VRC, 0) > 0
                     AND COALESCE(META_DISE, 0) > 0
                     AND COALESCE(DISE_BASE_COMPENSACAO, 0) > META_DISE
                    THEN COALESCE(DISE_BASE_COMPENSACAO, 0) * COALESCE(VRC, 0) / 730.0 * COALESCE(KEI3_DISE, 0)
                    ELSE 0
                END AS COMP_DISE_BRUTA_PRODIST
            FROM base
        ),
        ajustada AS (
            SELECT
                *,
                CASE
                    WHEN COMP_DIC_BRUTA_PRODIST > 0
                    THEN LEAST(18.0 * VRC, GREATEST(0.01, COMP_DIC_BRUTA_PRODIST))
                    ELSE 0
                END AS COMP_DIC_PRODIST,
                CASE
                    WHEN COMP_FIC_BRUTA_PRODIST > 0
                    THEN LEAST(18.0 * VRC, GREATEST(0.01, COMP_FIC_BRUTA_PRODIST))
                    ELSE 0
                END AS COMP_FIC_PRODIST,
                CASE
                    WHEN COMP_DMIC_BRUTA_PRODIST > 0
                    THEN LEAST(18.0 * VRC, GREATEST(0.01, COMP_DMIC_BRUTA_PRODIST))
                    ELSE 0
                END AS COMP_DMIC_PRODIST,
                CASE
                    WHEN COMP_DICRI_BRUTA_PRODIST > 0
                    THEN LEAST(18.0 * VRC, GREATEST(0.01, COMP_DICRI_BRUTA_PRODIST))
                    ELSE 0
                END AS COMP_DICRI_PRODIST,
                CASE
                    WHEN COMP_DISE_BRUTA_PRODIST > 0
                    THEN LEAST(18.0 * VRC, GREATEST(0.01, COMP_DISE_BRUTA_PRODIST))
                    ELSE 0
                END AS COMP_DISE_PRODIST
            FROM bruta
        )
        SELECT
            *,
            GREATEST(
                COALESCE(COMP_DIC_PRODIST, 0),
                COALESCE(COMP_FIC_PRODIST, 0),
                COALESCE(COMP_DMIC_PRODIST, 0)
            ) AS COMP_GERAL_CONTINUIDADE_PRODIST,
            GREATEST(
                COALESCE(COMP_DIC_PRODIST, 0),
                COALESCE(COMP_FIC_PRODIST, 0),
                COALESCE(COMP_DMIC_PRODIST, 0)
            )
            + COALESCE(COMP_DICRI_PRODIST, 0)
            + COALESCE(COMP_DISE_PRODIST, 0) AS COMP_TOTAL_PRODIST,
            CASE
                WHEN COALESCE(DICRI_BASE_COMPENSACAO, 0) > 0
                  OR COALESCE(DISE_BASE_COMPENSACAO, 0) > 0
                THEN 'PARCIAL_AGREGADO_POR_UC'
                ELSE 'ADERENTE_DIC_FIC_DMIC'
            END AS STATUS_CALCULO_PRODIST
        FROM ajustada
        """
    )
