import os
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
MARTS_DIR = BASE_DIR / "marts"
TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")
LIMITE_AMOSTRA = int(os.getenv("LIMITE_AMOSTRA_AUDITORIA", "1000"))


def exportar(con, nome, sql):
    caminho = MARTS_DIR / f"{nome}_{ANOMES}_{TIMESTAMP}.CSV"
    con.execute(
        f"""
        COPY (
            {sql}
        )
        TO '{caminho.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )
    print(f"Amostra exportada: {caminho}")
    return caminho


def main():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH), read_only=True)
    try:
        exportar(
            con,
            "Amostra_Sobreposicao_Residual",
            f"""
            WITH base AS (
                SELECT
                    TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS UC,
                    TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) AS COD_TIPO_INTRP,
                    TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) AS TIPO_PROTOC_JUSTIF_UCI,
                    TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                    DTHR_INICIO_INTRP_UC,
                    DATA_HORA_FIM_INTRP,
                    DURACAO_HORA,
                    CHI_LIQUIDO,
                    LAG(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))) OVER (
                        PARTITION BY
                            TRIM(CAST(NUM_UC_UCI AS VARCHAR)),
                            TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)),
                            TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR))
                        ORDER BY DTHR_INICIO_INTRP_UC, DATA_HORA_FIM_INTRP, TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                    ) AS NUM_SEQ_INTRP_ANTERIOR,
                    LAG(DATA_HORA_FIM_INTRP) OVER (
                        PARTITION BY
                            TRIM(CAST(NUM_UC_UCI AS VARCHAR)),
                            TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)),
                            TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR))
                        ORDER BY DTHR_INICIO_INTRP_UC, DATA_HORA_FIM_INTRP, TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                    ) AS FIM_ANTERIOR
                FROM gold_apuracao_uc
                WHERE CI_LIQUIDO = 1
            )
            SELECT *
            FROM base
            WHERE FIM_ANTERIOR > DTHR_INICIO_INTRP_UC
            ORDER BY CHI_LIQUIDO DESC
            LIMIT {LIMITE_AMOSTRA}
            """,
        )
        exportar(
            con,
            "Amostra_Duracao_Extrema",
            f"""
            SELECT
                NUM_UC_UCI,
                COD_TIPO_INTRP,
                TIPO_PROTOC_JUSTIF_UCI,
                NUM_SEQ_INTRP,
                NUM_OCORRENCIA_ADMS,
                DTHR_INICIO_INTRP_UC,
                DATA_HORA_FIM_INTRP,
                DURACAO_HORA,
                CI_LIQUIDO,
                CHI_LIQUIDO
            FROM gold_apuracao_uc
            WHERE CI_LIQUIDO = 1
              AND DURACAO_HORA >= 24
            ORDER BY DURACAO_HORA DESC
            LIMIT {LIMITE_AMOSTRA}
            """,
        )
        exportar(
            con,
            "Amostra_Ressarcimento_Alto",
            f"""
            SELECT
                UC,
                DIC,
                FIC,
                DMIC,
                META_DIC,
                META_FIC,
                META_DMIC,
                VRC,
                COMP_DIC_PRODIST,
                COMP_FIC_PRODIST,
                COMP_DMIC_PRODIST,
                COMP_GERAL_CONTINUIDADE_PRODIST,
                COMP_TOTAL_PRODIST,
                STATUS_CALCULO_PRODIST
            FROM gold_ressarcimento_prodist
            WHERE COMP_TOTAL_PRODIST > 0
            ORDER BY COMP_TOTAL_PRODIST DESC
            LIMIT {LIMITE_AMOSTRA}
            """,
        )
        exportar(
            con,
            "Amostra_VRC_Zero_Com_Violacao",
            f"""
            SELECT
                UC,
                DIC,
                FIC,
                DMIC,
                META_DIC,
                META_FIC,
                META_DMIC,
                VRC,
                FATURADA,
                CLASSE_TENSAO_PRODIST
            FROM gold_ressarcimento_prodist
            WHERE FATURADA = 'S'
              AND COALESCE(VRC, 0) = 0
              AND (
                    COALESCE(DIC_BASE_COMPENSACAO, 0) > COALESCE(META_DIC, 0)
                 OR COALESCE(FIC_BASE_COMPENSACAO, 0) > COALESCE(META_FIC, 0)
                 OR COALESCE(DMIC_BASE_COMPENSACAO, 0) > COALESCE(META_DMIC, 0)
              )
            ORDER BY DIC DESC
            LIMIT {LIMITE_AMOSTRA}
            """,
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()
