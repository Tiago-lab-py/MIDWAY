import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

from midway.export.iqs_csv import exportar_dataframe_iqs


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
EXPORT_DIR = BASE_DIR / "export" / "interrupcao_sem_uc"
MARTS_DIR = BASE_DIR / "marts"
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")

IQS_COLUMNS = [
    "PID_INTRP_CONJTO_PIN",
    "PID_POSTO_PIN",
    "INDIC_AREA_REDE_POSTO_PIN",
    "ALIM_INTRP_PIN",
    "ESTADO_INTRP",
    "ALIM_INTRP",
    "CAR_SE",
    "INDIC_INTRP_SE_ALIM",
    "NUM_OCORRENCIA_ADMS",
    "INDIC_INTRP_AT",
    "CONS_INTRP",
    "KVA_INTRP",
    "NUM_OPER_CHV_INTRP",
    "NUM_FUNCAO_ELET_HCAI",
    "DESC_INTRP",
    "VALID_POS_OPERACAO",
    "DATA_HORA_INIC_INTRP",
    "DATA_HORA_FIM_INTRP",
    "TIPO_EQP_INTRP",
    "COORD_X_INTRP",
    "COORD_Y_INTRP",
    "NUM_SEQ_INTRP",
    "COD_CAUSA_INTRP",
    "COD_COMP_INTRP",
    "COD_AREA_ELET_INTRP",
    "COD_GRUPO_COMP_INTRP",
    "COD_COND_CLIMA_INTRP",
    "COD_TIPO_INTRP",
    "INDIC_JUMP_INTRP",
    "NUM_PROTOC_JUSTIF_RESP_INTRP",
    "TIPO_PROTOC_JUSTIF_INTRP",
    "COD_CONJTO_ELET_ANEEL_INTRP",
    "INDIC_CALC_DMIC_INTRP",
    "INDIC_PONTO_CONEX_INTRP",
    "NUM_GEO_CHV_INTRP",
    "TIPO_REDE_CHV_INTRP",
    "TIPO_CHV_INTRP",
    "INDIC_PROPR_POSTO_INTRP",
    "TENSAO_OPER_ALIM_INTRP",
    "INDIC_DESLIG_ENT_SERV_INTRP",
    "INDIC_PROPR_CHVP_INTRP",
    "INDIC_CHVP_INIC_ALIM_INTRP",
    "PID",
    "PID_INTRP_UCI",
    "NUM_INTRP_UCI",
    "NUM_POSTO_UCI",
    "NUM_UC_UCI",
    "TIPO_SIT_UC_UCI",
    "DTHR_INICIO_INTRP_UC",
    "NUM_INTRP_INIC_MANOBRA_UCI",
    "NUM_MOTIVO_TRAT_DIF_UCI",
    "UC_ACESSANTE",
    "SIGLA_REGIONAL",
    "NUM_PROTOC_JUSTIF_RESP_UCI",
    "TIPO_PROTOC_JUSTIF_UCI",
    "PID_PIN",
    "INDIC_PROCES_IND_PIN",
    "INDIC_SIT_PROCES_INDIC_UCI",
]

DATE_COLUMNS = [
    "DATA_HORA_INIC_INTRP",
    "DATA_HORA_FIM_INTRP",
    "DTHR_INICIO_INTRP_UC",
]

INTEGER_COLUMNS = [
    "NUM_INTRP_INIC_MANOBRA_UCI",
    "NUM_GEO_CHV_INTRP",
]


def table_columns(con, table_name):
    return {
        row[1].upper()
        for row in con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    }


def column_expr(columns, column_name, table_alias=None):
    if column_name.upper() in columns:
        prefix = f"{table_alias}." if table_alias else ""
        return f"CAST({prefix}{column_name} AS VARCHAR) AS {column_name}"
    return f"'' AS {column_name}"


def exportar_csv_iqs(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df = df.copy()

    for column in DATE_COLUMNS:
        if column not in df.columns:
            continue

        original = df[column].astype("string").fillna("")
        parsed = pd.to_datetime(original, errors="coerce", dayfirst=True)
        formatted = parsed.dt.strftime("%d/%m/%Y %H:%M:%S")
        df[column] = formatted.fillna(original)

    for column in INTEGER_COLUMNS:
        if column not in df.columns:
            continue

        original = df[column].astype("string").fillna("").str.strip()
        sem_vazio = original.replace("", pd.NA)
        numerico = pd.to_numeric(sem_vazio, errors="coerce")
        inteiro = numerico.round()
        mascara_inteiro = numerico.notna() & ((numerico - inteiro).abs() < 0.000000001)
        resultado = original.copy()
        resultado.loc[mascara_inteiro] = inteiro.loc[mascara_inteiro].astype("Int64").astype("string")
        df[column] = resultado

    exportar_dataframe_iqs(df, path)


def exportar_interrupcao_sem_uc():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    MARTS_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    tables = {
        row[0]
        for row in con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            """
        ).fetchall()
    }

    if "adms_iqs_export" not in tables:
        raise RuntimeError(
            "Tabela adms_iqs_export nao encontrada. Execute run.bat tratamento antes."
        )

    columns = table_columns(con, "adms_iqs_export")
    regional_expr = (
        "REGIONAL_EXPORT"
        if "REGIONAL_EXPORT" in columns
        else "SIGLA_REGIONAL"
        if "SIGLA_REGIONAL" in columns
        else "'COPEL'"
    )

    select_columns = []
    for column in IQS_COLUMNS:
        if column == "ESTADO_INTRP":
            select_columns.append("'7' AS ESTADO_INTRP")
        elif column == "NUM_MOTIVO_TRAT_DIF_UCI":
            select_columns.append("'90' AS NUM_MOTIVO_TRAT_DIF_UCI")
        elif column == "INDIC_SIT_PROCES_INDIC_UCI":
            select_columns.append("'R' AS INDIC_SIT_PROCES_INDIC_UCI")
        elif column == "KVA_INTRP":
            select_columns.append(f"REPLACE(CAST(e.{column} AS VARCHAR), '.', ',') AS {column}")
        else:
            select_columns.append(column_expr(columns, column, "e"))

    con.execute(
        f"""
        CREATE OR REPLACE TABLE Auditoria_ESTADO_7 AS
        WITH interrupcoes AS (
            SELECT
                CAST({regional_expr} AS VARCHAR) AS REGIONAL_EXPORT,
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(NUM_INTRP_UCI AS VARCHAR) AS NUM_INTRP_UCI,
                MIN(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)) AS NUM_OPER_CHV_INTRP,
                MIN(CAST(COD_TIPO_INTRP AS VARCHAR)) AS COD_TIPO_INTRP,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                COUNT(*) AS QTD_UCS_TOTAL,
                SUM(
                    CASE
                        WHEN TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)) = '90'
                         AND TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)) = 'D'
                        THEN 1 ELSE 0
                    END
                ) AS QTD_UCS_90_D,
                SUM(
                    CASE
                        WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL
                         AND TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) NOT IN ('0', '0.0')
                        THEN 1 ELSE 0
                    END
                ) AS QTD_UCS_COM_MANOBRA
            FROM adms_iqs_export
            WHERE TRIM(CAST(ESTADO_INTRP AS VARCHAR)) = '4'
            GROUP BY
                CAST({regional_expr} AS VARCHAR),
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                CAST(NUM_SEQ_INTRP AS VARCHAR),
                CAST(NUM_INTRP_UCI AS VARCHAR)
        ),
        referencias_manobra AS (
            SELECT
                p.NUM_OCORRENCIA_ADMS,
                p.NUM_SEQ_INTRP,
                p.NUM_INTRP_UCI,
                COUNT(DISTINCT CAST(f.NUM_SEQ_INTRP AS VARCHAR)) AS QTD_INTERRUPCOES_FILHAS_REFERENCIANDO,
                COUNT(*) AS QTD_UCS_FILHAS_REFERENCIANDO,
                STRING_AGG(
                    DISTINCT CAST(f.NUM_SEQ_INTRP AS VARCHAR),
                    ', '
                    ORDER BY CAST(f.NUM_SEQ_INTRP AS VARCHAR)
                ) AS NUM_SEQ_INTRP_FILHAS_REFERENCIANDO
            FROM interrupcoes p
            JOIN adms_iqs_export f
              ON CAST(f.NUM_SEQ_INTRP AS VARCHAR) <> p.NUM_SEQ_INTRP
             AND NULLIF(TRIM(CAST(f.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL
             AND TRIM(CAST(f.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) NOT IN ('0', '0.0')
             AND TRIM(CAST(f.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) IN (
                    TRIM(p.NUM_INTRP_UCI),
                    TRIM(p.NUM_SEQ_INTRP)
                 )
             AND TRIM(CAST(f.ESTADO_INTRP AS VARCHAR)) = '4'
             AND NULLIF(TRIM(CAST(f.NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NULL
             AND NULLIF(TRIM(CAST(f.INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)), '') IS NULL
            GROUP BY
                p.NUM_OCORRENCIA_ADMS,
                p.NUM_SEQ_INTRP,
                p.NUM_INTRP_UCI
        )
        SELECT
            i.*,
            COALESCE(r.QTD_INTERRUPCOES_FILHAS_REFERENCIANDO, 0) AS QTD_INTERRUPCOES_FILHAS_REFERENCIANDO,
            COALESCE(r.QTD_UCS_FILHAS_REFERENCIANDO, 0) AS QTD_UCS_FILHAS_REFERENCIANDO,
            COALESCE(r.NUM_SEQ_INTRP_FILHAS_REFERENCIANDO, '') AS NUM_SEQ_INTRP_FILHAS_REFERENCIANDO,
            CASE
                WHEN i.QTD_UCS_TOTAL > 0
                 AND i.QTD_UCS_90_D = i.QTD_UCS_TOTAL
                 AND i.QTD_UCS_COM_MANOBRA = 0
                 AND COALESCE(r.QTD_INTERRUPCOES_FILHAS_REFERENCIANDO, 0) = 0
                THEN 'EXPORTAR_ESTADO_7_INTERRUPCAO_SEM_UC'
                WHEN i.QTD_UCS_TOTAL > 0
                 AND i.QTD_UCS_90_D = i.QTD_UCS_TOTAL
                 AND COALESCE(r.QTD_INTERRUPCOES_FILHAS_REFERENCIANDO, 0) > 0
                THEN 'NAO_EXPORTAR_REFERENCIADA_COMO_MANOBRA'
                WHEN i.QTD_UCS_TOTAL > 0
                 AND i.QTD_UCS_90_D = i.QTD_UCS_TOTAL
                 AND i.QTD_UCS_COM_MANOBRA > 0
                THEN 'NAO_EXPORTAR_MANOBRA_COM_REFERENCIA'
                ELSE 'OK'
            END AS RESULTADO_AUDITORIA
        FROM interrupcoes i
        LEFT JOIN referencias_manobra r
          ON r.NUM_OCORRENCIA_ADMS = i.NUM_OCORRENCIA_ADMS
         AND r.NUM_SEQ_INTRP = i.NUM_SEQ_INTRP
         AND r.NUM_INTRP_UCI = i.NUM_INTRP_UCI
        WHERE i.QTD_UCS_TOTAL > 0
          AND i.QTD_UCS_90_D = i.QTD_UCS_TOTAL
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE adms_iqs_interrupcao_sem_uc_export AS
        WITH chaves AS (
            SELECT
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP,
                NUM_INTRP_UCI
            FROM Auditoria_ESTADO_7
            WHERE RESULTADO_AUDITORIA = 'EXPORTAR_ESTADO_7_INTERRUPCAO_SEM_UC'
        )
        SELECT
            CAST({regional_expr} AS VARCHAR) AS REGIONAL_EXPORT,
            {", ".join(select_columns)}
        FROM adms_iqs_export e
        JOIN chaves c
          ON c.NUM_OCORRENCIA_ADMS = CAST(e.NUM_OCORRENCIA_ADMS AS VARCHAR)
         AND c.NUM_SEQ_INTRP = CAST(e.NUM_SEQ_INTRP AS VARCHAR)
         AND c.NUM_INTRP_UCI = CAST(e.NUM_INTRP_UCI AS VARCHAR)
        """
    )

    auditoria_path = MARTS_DIR / f"Auditoria_ESTADO_7_Interrupcao_Sem_UC_{ANOMES}_{TIMESTAMP_ARQ}.CSV"
    resumo_path = MARTS_DIR / f"Auditoria_ESTADO_7_Interrupcao_Sem_UC_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO.TXT"

    auditoria_df = con.execute(
        """
        SELECT *
        FROM Auditoria_ESTADO_7
        ORDER BY REGIONAL_EXPORT, DATA_HORA_INIC_INTRP, NUM_OCORRENCIA_ADMS, NUM_SEQ_INTRP
        """
    ).fetchdf()
    exportar_csv_iqs(auditoria_df, auditoria_path)

    regionais = con.execute(
        """
        SELECT DISTINCT REGIONAL_EXPORT
        FROM adms_iqs_interrupcao_sem_uc_export
        ORDER BY REGIONAL_EXPORT
        """
    ).fetchall()

    arquivos_exportados = []
    for (regional,) in regionais:
        if regional is None or str(regional).strip() == "":
            regional = "COPEL"

        df = con.execute(
            f"""
            SELECT {", ".join(IQS_COLUMNS)}
            FROM adms_iqs_interrupcao_sem_uc_export
            WHERE COALESCE(REGIONAL_EXPORT, 'COPEL') = ?
            ORDER BY DATA_HORA_INIC_INTRP, NUM_OCORRENCIA_ADMS, NUM_SEQ_INTRP, NUM_UC_UCI
            """,
            [regional],
        ).fetchdf()

        if df.empty:
            continue

        path = EXPORT_DIR / f"Interrupcoes_IQS_{TIMESTAMP_ARQ}_{regional}.CSV"
        exportar_csv_iqs(df, path)
        arquivos_exportados.append((regional, len(df), path))

    total_auditoria = con.execute("SELECT COUNT(*) FROM Auditoria_ESTADO_7").fetchone()[0]
    total_export = con.execute(
        "SELECT COUNT(*) FROM adms_iqs_interrupcao_sem_uc_export"
    ).fetchone()[0]
    total_interrupcoes_export = con.execute(
        """
        SELECT COUNT(*)
        FROM Auditoria_ESTADO_7
        WHERE RESULTADO_AUDITORIA = 'EXPORTAR_ESTADO_7_INTERRUPCAO_SEM_UC'
        """
    ).fetchone()[0]
    total_manobra = con.execute(
        """
        SELECT COUNT(*)
        FROM Auditoria_ESTADO_7
        WHERE RESULTADO_AUDITORIA = 'NAO_EXPORTAR_MANOBRA_COM_REFERENCIA'
        """
    ).fetchone()[0]
    total_referenciada = con.execute(
        """
        SELECT COUNT(*)
        FROM Auditoria_ESTADO_7
        WHERE RESULTADO_AUDITORIA = 'NAO_EXPORTAR_REFERENCIADA_COMO_MANOBRA'
        """
    ).fetchone()[0]

    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("AUDITORIA ESTADO 7 - INTERRUPCAO SEM UC\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write("Origem: adms_iqs_export\n")
        arquivo.write("Tabela auditoria: Auditoria_ESTADO_7\n")
        arquivo.write("Tabela exportacao: adms_iqs_interrupcao_sem_uc_export\n")
        arquivo.write(
            "Criterio: interrupcao em ESTADO 4 onde todas as UCs ficaram 91/D apos sobreposicao total por UC.\n"
        )
        arquivo.write(
            "Excecao: interrupcoes com NUM_INTRP_INIC_MANOBRA_UCI preenchido nao sao exportadas como ESTADO 7.\n"
        )
        arquivo.write(f"Interrupcoes auditadas: {total_auditoria}\n")
        arquivo.write(f"Interrupcoes exportadas: {total_interrupcoes_export}\n")
        arquivo.write(f"Interrupcoes bloqueadas por manobra: {total_manobra}\n")
        arquivo.write(f"Interrupcoes bloqueadas por serem origem de manobra: {total_referenciada}\n")
        arquivo.write(f"Linhas exportadas IQS: {total_export}\n")
        arquivo.write(f"Auditoria CSV: {auditoria_path}\n")
        arquivo.write("\nArquivos exportados:\n")
        for regional, qtd_linhas, path in arquivos_exportados:
            arquivo.write(f"{regional}|linhas={qtd_linhas}|arquivo={path}\n")

    con.close()

    print(f"Auditoria ESTADO 7 populada: {auditoria_path}")
    print(f"Exportacao interrupcao sem UC: {EXPORT_DIR}")
    print(f"Interrupcoes exportadas: {total_interrupcoes_export}")
    print(f"Linhas exportadas: {total_export}")
    print(f"Resumo: {resumo_path}")


if __name__ == "__main__":
    exportar_interrupcao_sem_uc()
