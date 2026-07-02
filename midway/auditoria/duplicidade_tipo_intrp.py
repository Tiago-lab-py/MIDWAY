import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
MARTS_DIR = BASE_DIR / "marts"
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")

TIPOS_AUDITADOS = ("1", "2", "3")


def escrever_csv(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df = df.astype("string").fillna("")
    df.to_csv(
        caminho,
        sep="|",
        index=False,
        lineterminator="\n",
        encoding="utf-8",
    )


def tabela_fonte(con: duckdb.DuckDBPyConnection) -> str:
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

    if "gold_interrupcao_tratada" in tabelas:
        return "gold_interrupcao_tratada"

    if "adms_iqs_export" in tabelas:
        return "adms_iqs_export"

    if "adms_iqs_alterados" in tabelas:
        return "adms_iqs_alterados"

    raise RuntimeError(
        "Nenhuma tabela fonte encontrada. Esperado: gold_interrupcao_tratada, "
        "adms_iqs_export ou adms_iqs_alterados."
    )


def auditar_duplicidade_tipo_intrp() -> None:
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH), read_only=True)
    fonte = tabela_fonte(con)

    con.execute(
        f"""
        CREATE TEMP TABLE interrupcao_tipo_base AS
        SELECT DISTINCT
            REGIONAL_EXPORT AS REGIONAL,
            CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
            CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
            CAST(NUM_OPER_CHV_INTRP AS VARCHAR) AS NUM_OPER_CHV_INTRP,
            CAST(NUM_POSTO_UCI AS VARCHAR) AS NUM_POSTO_UCI,
            CAST(COD_CAUSA_INTRP AS VARCHAR) AS COD_CAUSA_INTRP,
            CAST(COD_COMP_INTRP AS VARCHAR) AS COD_COMP_INTRP,
            CAST(COD_TIPO_INTRP AS VARCHAR) AS COD_TIPO_INTRP,
            DATA_HORA_INIC_INTRP,
            DATA_HORA_FIM_INTRP,
            CAST(ESTADO_INTRP AS VARCHAR) AS ESTADO_INTRP,
            CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR) AS NUM_MOTIVO_TRAT_DIF_UCI,
            CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR) AS INDIC_SIT_PROCES_INDIC_UCI
        FROM {fonte}
        WHERE TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) IN ('1', '2', '3')
        """
    )

    resumo_por_tipo = con.execute(
        """
        SELECT
            COD_TIPO_INTRP,
            COUNT(*) AS QTD_INTERRUPCOES,
            COUNT(DISTINCT NUM_SEQ_INTRP) AS QTD_NUM_SEQ_INTRP,
            COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS,
            COUNT(DISTINCT NUM_OPER_CHV_INTRP) AS QTD_EQUIPAMENTOS
        FROM interrupcao_tipo_base
        GROUP BY COD_TIPO_INTRP
        ORDER BY COD_TIPO_INTRP
        """
    ).fetchdf()

    duplicidade_exata = con.execute(
        """
        WITH grupos AS (
            SELECT
                COD_TIPO_INTRP,
                NUM_OPER_CHV_INTRP,
                DATA_HORA_INIC_INTRP,
                DATA_HORA_FIM_INTRP,
                COD_CAUSA_INTRP,
                COD_COMP_INTRP,
                COUNT(*) AS QTD_INTERRUPCOES,
                COUNT(DISTINCT NUM_SEQ_INTRP) AS QTD_NUM_SEQ_INTRP,
                STRING_AGG(DISTINCT NUM_OCORRENCIA_ADMS, ', ' ORDER BY NUM_OCORRENCIA_ADMS) AS OCORRENCIAS,
                STRING_AGG(DISTINCT NUM_SEQ_INTRP, ', ' ORDER BY NUM_SEQ_INTRP) AS NUM_SEQ_INTRP_LISTA
            FROM interrupcao_tipo_base
            GROUP BY
                COD_TIPO_INTRP,
                NUM_OPER_CHV_INTRP,
                DATA_HORA_INIC_INTRP,
                DATA_HORA_FIM_INTRP,
                COD_CAUSA_INTRP,
                COD_COMP_INTRP
            HAVING COUNT(DISTINCT NUM_SEQ_INTRP) > 1
        )
        SELECT *
        FROM grupos
        ORDER BY QTD_NUM_SEQ_INTRP DESC, COD_TIPO_INTRP, NUM_OPER_CHV_INTRP
        """
    ).fetchdf()

    duplicidade_periodo = con.execute(
        """
        WITH pares AS (
            SELECT
                a.COD_TIPO_INTRP,
                a.NUM_OPER_CHV_INTRP,
                a.NUM_OCORRENCIA_ADMS AS NUM_OCORRENCIA_A,
                a.NUM_SEQ_INTRP AS NUM_SEQ_INTRP_A,
                a.DATA_HORA_INIC_INTRP AS DATA_HORA_INIC_A,
                a.DATA_HORA_FIM_INTRP AS DATA_HORA_FIM_A,
                b.NUM_OCORRENCIA_ADMS AS NUM_OCORRENCIA_B,
                b.NUM_SEQ_INTRP AS NUM_SEQ_INTRP_B,
                b.DATA_HORA_INIC_INTRP AS DATA_HORA_INIC_B,
                b.DATA_HORA_FIM_INTRP AS DATA_HORA_FIM_B,
                CASE
                    WHEN a.DATA_HORA_INIC_INTRP = b.DATA_HORA_INIC_INTRP
                     AND a.DATA_HORA_FIM_INTRP = b.DATA_HORA_FIM_INTRP
                    THEN 'MESMO_PERIODO'
                    ELSE 'PERIODO_SOBREPOSTO'
                END AS TIPO_DUPLICIDADE
            FROM interrupcao_tipo_base a
            JOIN interrupcao_tipo_base b
              ON b.COD_TIPO_INTRP = a.COD_TIPO_INTRP
             AND COALESCE(NULLIF(TRIM(b.NUM_OPER_CHV_INTRP), ''), '#') =
                 COALESCE(NULLIF(TRIM(a.NUM_OPER_CHV_INTRP), ''), '#')
             AND b.NUM_SEQ_INTRP > a.NUM_SEQ_INTRP
             AND b.DATA_HORA_INIC_INTRP <= a.DATA_HORA_FIM_INTRP
             AND b.DATA_HORA_FIM_INTRP >= a.DATA_HORA_INIC_INTRP
        )
        SELECT *
        FROM pares
        ORDER BY COD_TIPO_INTRP, NUM_OPER_CHV_INTRP, DATA_HORA_INIC_A
        """
    ).fetchdf()

    detalhe_exata = con.execute(
        """
        WITH grupos AS (
            SELECT
                COD_TIPO_INTRP,
                NUM_OPER_CHV_INTRP,
                DATA_HORA_INIC_INTRP,
                DATA_HORA_FIM_INTRP,
                COD_CAUSA_INTRP,
                COD_COMP_INTRP
            FROM interrupcao_tipo_base
            GROUP BY
                COD_TIPO_INTRP,
                NUM_OPER_CHV_INTRP,
                DATA_HORA_INIC_INTRP,
                DATA_HORA_FIM_INTRP,
                COD_CAUSA_INTRP,
                COD_COMP_INTRP
            HAVING COUNT(DISTINCT NUM_SEQ_INTRP) > 1
        )
        SELECT b.*
        FROM interrupcao_tipo_base b
        JOIN grupos g
          ON g.COD_TIPO_INTRP = b.COD_TIPO_INTRP
         AND COALESCE(g.NUM_OPER_CHV_INTRP, '') = COALESCE(b.NUM_OPER_CHV_INTRP, '')
         AND g.DATA_HORA_INIC_INTRP = b.DATA_HORA_INIC_INTRP
         AND g.DATA_HORA_FIM_INTRP = b.DATA_HORA_FIM_INTRP
         AND COALESCE(g.COD_CAUSA_INTRP, '') = COALESCE(b.COD_CAUSA_INTRP, '')
         AND COALESCE(g.COD_COMP_INTRP, '') = COALESCE(b.COD_COMP_INTRP, '')
        ORDER BY b.COD_TIPO_INTRP, b.NUM_OPER_CHV_INTRP, b.DATA_HORA_INIC_INTRP, b.NUM_SEQ_INTRP
        """
    ).fetchdf()

    caminho_resumo_tipo = MARTS_DIR / f"Auditoria_Duplicidade_Tipo_INTRP_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO_TIPO.CSV"
    caminho_dup_exata = MARTS_DIR / f"Auditoria_Duplicidade_Tipo_INTRP_{ANOMES}_{TIMESTAMP_ARQ}_DUP_EXATA.CSV"
    caminho_dup_periodo = MARTS_DIR / f"Auditoria_Duplicidade_Tipo_INTRP_{ANOMES}_{TIMESTAMP_ARQ}_SOBREPOSICAO_PERIODO.CSV"
    caminho_detalhe = MARTS_DIR / f"Auditoria_Duplicidade_Tipo_INTRP_{ANOMES}_{TIMESTAMP_ARQ}_DETALHE.CSV"
    caminho_txt = MARTS_DIR / f"Auditoria_Duplicidade_Tipo_INTRP_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO.TXT"

    escrever_csv(resumo_por_tipo, caminho_resumo_tipo)
    escrever_csv(duplicidade_exata, caminho_dup_exata)
    escrever_csv(duplicidade_periodo, caminho_dup_periodo)
    escrever_csv(detalhe_exata, caminho_detalhe)

    with caminho_txt.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("AUDITORIA DUPLICIDADE DE INTERRUPCAO POR COD_TIPO_INTRP\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write(f"DuckDB processado: {PROCESSED_DUCKDB_PATH}\n")
        arquivo.write(f"Tabela fonte: {fonte}\n")
        arquivo.write("Tipos auditados: 1, 2, 3\n")
        arquivo.write(f"Resumo por tipo: {caminho_resumo_tipo}\n")
        arquivo.write(f"Duplicidade exata: {caminho_dup_exata}\n")
        arquivo.write(f"Sobreposicao por periodo/equipamento: {caminho_dup_periodo}\n")
        arquivo.write(f"Detalhe duplicidade exata: {caminho_detalhe}\n")
        arquivo.write(f"Grupos com duplicidade exata: {len(duplicidade_exata)}\n")
        arquivo.write(f"Pares com periodo sobreposto: {len(duplicidade_periodo)}\n")

    con.close()

    print(f"Auditoria concluida para ANOMES={ANOMES}")
    print(f"Resumo: {caminho_txt}")
    print(f"Duplicidade exata: {caminho_dup_exata}")
    print(f"Sobreposicao periodo: {caminho_dup_periodo}")


if __name__ == "__main__":
    auditar_duplicidade_tipo_intrp()
