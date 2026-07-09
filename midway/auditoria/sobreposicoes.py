import os
import time
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
EXPORT_DIR = BASE_DIR / "export"
SOBREPOSICAO_TOTAL_UC_DIR = EXPORT_DIR / "sobreposicao_total_uc"
SOBREPOSICAO_PARCIAL_UC_DIR = EXPORT_DIR / "sobreposicao_UC_parcial"

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

ISO_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
]

SLASH_MONTH_FIRST_FORMATS = [
    "%m/%d/%Y %H:%M:%S.%f",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
]

SLASH_DAY_FIRST_FORMATS = [
    "%d/%m/%Y %H:%M:%S.%f",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
]


def table_exists(con, table_name):
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


def parse_por_formatos(valores, formatos):
    parsed = pd.Series(pd.NaT, index=valores.index, dtype="datetime64[ns]")
    pendentes = valores.notna()

    for formato in formatos:
        if not pendentes.any():
            break

        tentativa = pd.to_datetime(
            valores.where(pendentes),
            format=formato,
            errors="coerce",
        )
        parsed = parsed.fillna(tentativa)
        pendentes = parsed.isna() & valores.notna()

    return parsed


def formatar_coluna_data_iqs(serie):
    original = serie.astype("string").fillna("")
    sem_vazio = original.replace("", pd.NA)

    mascara_iso = sem_vazio.str.contains("-", na=False)
    mascara_barra = sem_vazio.str.contains("/", na=False)

    parsed_iso = parse_por_formatos(
        sem_vazio.where(mascara_iso),
        ISO_DATE_FORMATS,
    )
    parsed_barra_mes_dia = parse_por_formatos(
        sem_vazio.where(mascara_barra),
        SLASH_MONTH_FIRST_FORMATS,
    )
    parsed_barra_dia_mes = parse_por_formatos(
        sem_vazio.where(mascara_barra),
        SLASH_DAY_FIRST_FORMATS,
    )

    parsed = parsed_iso.fillna(parsed_barra_mes_dia).fillna(parsed_barra_dia_mes)
    formatted = parsed.dt.strftime("%d/%m/%Y %H:%M:%S")
    return formatted.fillna(original)


def exportar_csv_iqs(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df = df.copy()

    for column in DATE_COLUMNS:
        if column not in df.columns:
            continue

        df[column] = formatar_coluna_data_iqs(df[column])

    df = df.astype("string").fillna("")
    df.to_csv(
        path,
        sep="|",
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )


def criar_tabela_saida(con, nome_tabela, condicao):
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {nome_tabela} AS
        WITH chaves AS (
            SELECT DISTINCT
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(NUM_INTRP_UCI AS VARCHAR) AS NUM_INTRP_UCI,
                CAST(NUM_UC_UCI AS VARCHAR) AS NUM_UC_UCI
            FROM adms_iqs_alterados
            WHERE {condicao}
        )
        SELECT DISTINCT
            COALESCE(CAST(e.REGIONAL_EXPORT AS VARCHAR), CAST(e.SIGLA_REGIONAL AS VARCHAR), 'COPEL') AS REGIONAL_EXPORT,
            {", ".join(f"e.{column}" for column in IQS_COLUMNS)}
        FROM adms_iqs_export e
        JOIN chaves c
          ON c.NUM_OCORRENCIA_ADMS = CAST(e.NUM_OCORRENCIA_ADMS AS VARCHAR)
         AND c.NUM_SEQ_INTRP = CAST(e.NUM_SEQ_INTRP AS VARCHAR)
         AND c.NUM_INTRP_UCI = CAST(e.NUM_INTRP_UCI AS VARCHAR)
         AND c.NUM_UC_UCI = CAST(e.NUM_UC_UCI AS VARCHAR)
        """
    )


def exportar_tabela_por_regional(con, nome_tabela, pasta, prefixo):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)

    regionais = con.execute(
        f"""
        SELECT DISTINCT COALESCE(REGIONAL_EXPORT, 'COPEL') AS REGIONAL_EXPORT
        FROM {nome_tabela}
        ORDER BY REGIONAL_EXPORT
        """
    ).fetchall()

    arquivos = []
    for (regional,) in regionais:
        df = con.execute(
            f"""
            SELECT {", ".join(IQS_COLUMNS)}
            FROM {nome_tabela}
            WHERE COALESCE(REGIONAL_EXPORT, 'COPEL') = ?
            ORDER BY DATA_HORA_INIC_INTRP, NUM_OCORRENCIA_ADMS, NUM_SEQ_INTRP, NUM_UC_UCI
            """,
            [regional],
        ).fetchdf()

        if df.empty:
            continue

        path = pasta / f"{prefixo}_{timestamp}_{regional}.CSV"
        exportar_csv_iqs(df, path)
        arquivos.append((regional, len(df), path))
        print(f"Exportado {regional}: {path} ({len(df):,} linhas)")

    return arquivos


def exportar_sobreposicoes():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))

    if not table_exists(con, "adms_iqs_alterados"):
        raise RuntimeError("Tabela adms_iqs_alterados nao encontrada. Execute run.bat tratamento.")

    if not table_exists(con, "adms_iqs_export"):
        raise RuntimeError("Tabela adms_iqs_export nao encontrada. Execute run.bat tratamento.")

    print("Gerando exportacao: sobreposicao total por UC...")
    criar_tabela_saida(
        con,
        "export_sobreposicao_total_uc",
        """
        ACAO_SOBREPOSICAO_TOTAL_UC IS NOT NULL
        OR (
            TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)) = '91'
            AND TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)) = 'D'
        )
        """,
    )
    total_uc = exportar_tabela_por_regional(
        con,
        "export_sobreposicao_total_uc",
        SOBREPOSICAO_TOTAL_UC_DIR,
        "Interrupcoes_IQS",
    )

    time.sleep(1)

    print("Gerando exportacao: sobreposicao parcial por UC...")
    criar_tabela_saida(
        con,
        "export_sobreposicao_parcial_uc",
        """
        ACAO_AJUSTE_PARCIAL IS NOT NULL
        OR DTHR_INICIO_INTRP_UC_AJUSTADO IS NOT NULL
        """,
    )
    parcial_uc = exportar_tabela_por_regional(
        con,
        "export_sobreposicao_parcial_uc",
        SOBREPOSICAO_PARCIAL_UC_DIR,
        "Interrupcoes_IQS",
    )

    con.close()

    print("Exportacao de sobreposicoes concluida.")
    print(f"Sobreposicao total UC: {sum(item[1] for item in total_uc):,} linhas")
    print(f"Sobreposicao parcial UC: {sum(item[1] for item in parcial_uc):,} linhas")


if __name__ == "__main__":
    exportar_sobreposicoes()
