import os
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202605")

BASE_DIR = Path("data")
EXPORT_DIR = BASE_DIR / "export" / "Teste_motivo"
MARTS_DIR = BASE_DIR / "marts"
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"

TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")

COLUNAS_EXPORTACAO_IQS = [
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
    "STRFTIME(CAST(DATA_HORA_INIC_INTRP AS TIMESTAMP), '%d/%m/%Y %H:%M:%S') AS DATA_HORA_INIC_INTRP",
    "STRFTIME(CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP), '%d/%m/%Y %H:%M:%S') AS DATA_HORA_FIM_INTRP",
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
    "STRFTIME(CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), '%d/%m/%Y %H:%M:%S') AS DTHR_INICIO_INTRP_UC",
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


def sql_literal(valor):
    return "'" + str(valor).replace("'", "''") + "'"


def normalizar_linhas_unix(caminho_csv):
    conteudo = caminho_csv.read_bytes()
    normalizado = conteudo.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if normalizado != conteudo:
        caminho_csv.write_bytes(normalizado)


def condicao_motivo_preenchido():
    return "NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NOT NULL"


def expressao_regional():
    return """
        CASE
            WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'P' THEN 'CSL'
            WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'L' THEN 'NRT'
            WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'M' THEN 'NRO'
            WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'C' THEN 'LES'
            WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'V' THEN 'OES'
            WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) IN ('CSL', 'NRT', 'NRO', 'LES', 'OES')
                THEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR))
            ELSE 'COPEL'
        END
    """


def exportar_motivo_nao_nulo():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    MARTS_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    con.execute("SET preserve_insertion_order=false")
    colunas_exportacao = ",\n                    ".join(COLUNAS_EXPORTACAO_IQS)

    tabelas = {
        linha[0]
        for linha in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }

    if "adms_iqs_export" not in tabelas:
        con.close()
        raise RuntimeError(
            "Tabela adms_iqs_export nao encontrada. Execute run.bat tratamento "
            "ou run.bat exportar antes desta exportacao de teste."
        )

    total = con.execute(
        f"""
        SELECT COUNT(*)
        FROM adms_iqs_export
        WHERE {condicao_motivo_preenchido()}
        """
    ).fetchone()[0]

    print(f"Registros com NUM_MOTIVO_TRAT_DIF_UCI preenchido: {total:,}")

    if total == 0:
        con.close()
        print("Nenhum registro encontrado para exportar.")
        return

    regionais = con.execute(
        f"""
        SELECT DISTINCT {expressao_regional()} AS REGIONAL_EXPORT
        FROM adms_iqs_export
        WHERE {condicao_motivo_preenchido()}
        ORDER BY 1
        """
    ).fetchall()

    arquivos = []

    for (regional,) in regionais:
        nome_arquivo = f"Interrupcoes_IQS_{TIMESTAMP_ARQ}_{regional}.CSV"
        caminho_csv = EXPORT_DIR / nome_arquivo

        print(f"Exportando {regional}: {caminho_csv}")

        con.execute(
            f"""
            COPY (
                SELECT DISTINCT
                    {colunas_exportacao}
                FROM adms_iqs_export
                WHERE {condicao_motivo_preenchido()}
                  AND {expressao_regional()} = {sql_literal(regional)}
            )
            TO {sql_literal(caminho_csv.as_posix())}
            WITH (
                HEADER TRUE,
                DELIMITER '|',
                NULL ''
            )
            """
        )

        normalizar_linhas_unix(caminho_csv)
        print(f"Terminador de linha UNIX aplicado: {caminho_csv}")
        arquivos.append(caminho_csv)

    caminho_resumo = MARTS_DIR / f"Exportacao_Teste_Motivo_IQS_{TIMESTAMP_ARQ}_RESUMO.TXT"
    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as resumo:
        resumo.write("EXPORTACAO TESTE IQS - NUM_MOTIVO_TRAT_DIF_UCI PREENCHIDO\n")
        resumo.write(f"ANOMES: {ANOMES}\n")
        resumo.write(f"DuckDB processado: {PROCESSED_DUCKDB_PATH}\n")
        resumo.write(f"Registros exportados: {total}\n")
        resumo.write("Filtro: NUM_MOTIVO_TRAT_DIF_UCI nao nulo e nao vazio\n")
        resumo.write("Terminador de linha: UNIX LF\n")
        resumo.write("Arquivos:\n")
        for caminho_csv in arquivos:
            resumo.write(f"- {caminho_csv}\n")

    con.close()

    print(f"Resumo exportado: {caminho_resumo}")
    print("Exportacao teste concluida.")


if __name__ == "__main__":
    exportar_motivo_nao_nulo()
