import os
from pathlib import Path
from datetime import datetime

import csv
import duckdb
import pandas as pd

_PANDAS_TO_CSV_ORIGINAL = pd.DataFrame.to_csv


def _to_csv_com_linha_unix(self, *args, **kwargs):
    kwargs.setdefault("lineterminator", "\n")
    return _PANDAS_TO_CSV_ORIGINAL(self, *args, **kwargs)


pd.DataFrame.to_csv = _to_csv_com_linha_unix
from dotenv import load_dotenv

from midway.controle_execucao import (
    agora_iso,
    carregar_done,
    configurar_logger,
    gravar_done,
    lock_execucao,
    validar_done_sucesso,
    valor_verdadeiro,
)
from midway.export.iqs_csv import exportar_dataframe_iqs, preparar_dataframe_iqs


# ============================================================
# .ENV
# ============================================================

load_dotenv()

ANOMES = os.getenv("ANOMES", "202605")
REPROCESSAR = valor_verdadeiro("REPROCESSAR")
DUCKDB_THREADS = int(os.getenv("DUCKDB_THREADS", "4"))
DUCKDB_MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "10GB")
DUCKDB_MAX_TEMP_DIRECTORY_SIZE = os.getenv("DUCKDB_MAX_TEMP_DIRECTORY_SIZE", "80GB")

OUTLIER_DURACAO_HORAS = float(os.getenv("OUTLIER_DURACAO_HORAS", "24"))
OUTLIER_QTD_UCS = int(os.getenv("OUTLIER_QTD_UCS", "10000"))
OUTLIER_QTD_INTRP_CONTIDAS = int(os.getenv("OUTLIER_QTD_INTRP_CONTIDAS", "100"))
OUTLIER_QTD_UCS_AFETADAS = int(os.getenv("OUTLIER_QTD_UCS_AFETADAS", "50000"))

DATA_DIR = Path("data")
SAMPLE_CSV_PATH = DATA_DIR / "amostra" / "amostra.csv"
INPUT_DIR = DATA_DIR / "input"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORT_DIR = DATA_DIR / "export"
MARTS_DIR = DATA_DIR / "marts"
TEMP_DIR = Path(os.getenv("DUCKDB_TEMP_DIR", str(DATA_DIR / "temp")))

for diretorio in (INPUT_DIR, RAW_DIR, PROCESSED_DIR, EXPORT_DIR, MARTS_DIR, TEMP_DIR):
    diretorio.mkdir(parents=True, exist_ok=True)

RAW_DUCKDB_PATH = RAW_DIR / f"iqs_adms_raw_{ANOMES}.duckdb"
PROCESSED_DUCKDB_PATH = PROCESSED_DIR / f"iqs_adms_processed_{ANOMES}.duckdb"
ESTADO_7_ACEITAS_PATH = INPUT_DIR / "estado_7_aceitas.csv"
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")
ULTIMO_MAPEAMENTO_EXPORTACAO = []
LAYOUT_IQS_COLUNAS = [
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


def sql_literal(valor):
    return "'" + str(valor).replace("\\", "/").replace("'", "''") + "'"


def detectar_quebra_linha_amostra():
    if not SAMPLE_CSV_PATH.exists():
        return "\n"

    conteudo = SAMPLE_CSV_PATH.read_bytes()[:8192]

    if b"\r\n" in conteudo:
        return "\r\n"

    if b"\r" in conteudo:
        return "\r"

    return "\n"


def detectar_encoding_amostra():
    if not SAMPLE_CSV_PATH.exists():
        return "utf-8"

    conteudo = SAMPLE_CSV_PATH.read_bytes()

    if conteudo.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"

    try:
        conteudo.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def detectar_delimitador_amostra():
    if not SAMPLE_CSV_PATH.exists():
        return "|"

    encoding = detectar_encoding_amostra()
    primeira_linha = SAMPLE_CSV_PATH.read_text(encoding=encoding, errors="ignore").splitlines()[0]
    delimitadores = ("|", ";", ",", "\t")

    return max(delimitadores, key=primeira_linha.count)


def carregar_amostra_formatos(delimitador):
    if not SAMPLE_CSV_PATH.exists():
        return {}

    amostra = pd.read_csv(
        SAMPLE_CSV_PATH,
        sep=delimitador,
        encoding=detectar_encoding_amostra(),
        dtype=str,
        nrows=100,
        keep_default_na=False,
    )

    return {
        coluna: [valor for valor in amostra[coluna].dropna().astype(str) if valor.strip()]
        for coluna in amostra.columns
    }


def detectar_formato_data(valores):
    formatos = (
        ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"),
        ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M"),
        ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"),
        ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M"),
        ("%d/%m/%Y", "%d/%m/%Y"),
        ("%Y-%m-%d", "%Y-%m-%d"),
    )

    for valor in valores:
        for formato_entrada, formato_saida in formatos:
            try:
                datetime.strptime(valor, formato_entrada)
                return formato_saida
            except ValueError:
                continue

    return None


def aplicar_formatos_amostra(df):
    delimitador = detectar_delimitador_amostra()
    formatos_amostra = carregar_amostra_formatos(delimitador)
    colunas_data_hora = {
        "DATA_HORA_INIC_INTRP",
        "DATA_HORA_FIM_INTRP",
        "DTHR_INICIO_INTRP_UC",
    }

    for coluna in df.columns:
        formato_data = detectar_formato_data(formatos_amostra.get(coluna, []))

        if not formato_data and coluna in colunas_data_hora:
            formato_data = "%d/%m/%Y %H:%M:%S"

        if formato_data and pd.api.types.is_datetime64_any_dtype(df[coluna]):
            df[coluna] = df[coluna].dt.strftime(formato_data)

    return df


def exportar_csv_formatado(df, caminho_csv):
    delimitador = detectar_delimitador_amostra()
    encoding = detectar_encoding_amostra()
    quebra_linha = detectar_quebra_linha_amostra()
    df = aplicar_formatos_amostra(df)
    df = df.astype("object").where(pd.notna(df), "")

    df.to_csv(
        caminho_csv,
        sep=delimitador,
        index=False,
        na_rep="",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator=quebra_linha,
        encoding=encoding,
    )


def validar_layout_iqs(df):
    colunas = list(df.columns)

    if colunas != LAYOUT_IQS_COLUNAS:
        faltantes = [coluna for coluna in LAYOUT_IQS_COLUNAS if coluna not in colunas]
        extras = [coluna for coluna in colunas if coluna not in LAYOUT_IQS_COLUNAS]
        fora_ordem = [
            f"{posicao + 1}: esperado={esperado}, encontrado={encontrado}"
            for posicao, (esperado, encontrado) in enumerate(zip(LAYOUT_IQS_COLUNAS, colunas))
            if esperado != encontrado
        ]
        detalhes = []

        if faltantes:
            detalhes.append("faltantes=" + ", ".join(faltantes))
        if extras:
            detalhes.append("extras=" + ", ".join(extras))
        if fora_ordem:
            detalhes.append("fora_ordem=" + "; ".join(fora_ordem[:10]))

        raise RuntimeError("Layout IQS invalido: " + " | ".join(detalhes))


def aplicar_formato_oficial_iqs(df):
    colunas_data_hora = {
        "DATA_HORA_INIC_INTRP",
        "DATA_HORA_FIM_INTRP",
        "DTHR_INICIO_INTRP_UC",
    }
    colunas_inteiras = {
        "NUM_INTRP_INIC_MANOBRA_UCI",
        "NUM_GEO_CHV_INTRP",
    }

    df = df.copy()

    for coluna in colunas_data_hora:
        if coluna not in df.columns:
            continue

        if pd.api.types.is_datetime64_any_dtype(df[coluna]):
            df[coluna] = df[coluna].dt.strftime("%d/%m/%Y %H:%M:%S")
            continue

        valores = df[coluna].astype("string")
        datas = pd.to_datetime(valores, errors="coerce", dayfirst=True)
        formatadas = datas.dt.strftime("%d/%m/%Y %H:%M:%S")
        df[coluna] = formatadas.fillna(valores)

    for coluna in colunas_inteiras:
        if coluna not in df.columns:
            continue

        original = df[coluna].astype("string").fillna("").str.strip()
        sem_vazio = original.replace("", pd.NA)
        numerico = pd.to_numeric(sem_vazio, errors="coerce")
        inteiro = numerico.round()
        mascara_inteiro = numerico.notna() & ((numerico - inteiro).abs() < 0.000000001)
        resultado = original.copy()
        resultado.loc[mascara_inteiro] = inteiro.loc[mascara_inteiro].astype("Int64").astype("string")
        df[coluna] = resultado

    return preparar_dataframe_iqs(df)


def exportar_csv_iqs_oficial(df, caminho_csv):
    validar_layout_iqs(df)
    df = aplicar_formato_oficial_iqs(df)

    exportar_dataframe_iqs(df, caminho_csv)


def exportar_resumo_auditoria(caminho_txt, titulo, total, alertas, arquivo_completo, arquivo_anomalias):
    status = "OK" if alertas == 0 else "NAO OK"
    conteudo = [
        titulo,
        "=" * len(titulo),
        "",
        f"Status: {status}",
        f"Total auditado: {total:,}",
        f"Total de anomalias: {alertas:,}",
        f"Arquivo completo: {arquivo_completo}",
        f"Arquivo de anomalias: {arquivo_anomalias}",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "",
    ]

    if alertas == 0:
        conteudo.append("Resultado: auditoria sem anomalias.")
    else:
        conteudo.append("Resultado: existem anomalias que precisam de revisao.")

    caminho_txt.write_text("\n".join(conteudo) + "\n", encoding="utf-8")


def normalizar_chave_texto(valor):
    if pd.isna(valor):
        return ""

    return str(valor).strip()


def carregar_aceites_estado_7(logger):
    colunas_esperadas = {
        "NUM_SEQ_INTRP_REGISTRO_7",
        "NUM_SEQ_INTRP_REGISTRO_MANTIDO",
    }

    if not ESTADO_7_ACEITAS_PATH.exists():
        logger.info("Arquivo de aceite ESTADO 7 nao encontrado: %s", ESTADO_7_ACEITAS_PATH)
        return pd.DataFrame(columns=list(colunas_esperadas))

    df_aceites = pd.read_csv(
        ESTADO_7_ACEITAS_PATH,
        sep="|",
        dtype=str,
        keep_default_na=False,
        encoding=detectar_encoding_arquivo(ESTADO_7_ACEITAS_PATH),
    )
    df_aceites.columns = [coluna.strip() for coluna in df_aceites.columns]
    faltantes = colunas_esperadas - set(df_aceites.columns)

    if faltantes:
        raise RuntimeError(
            "Arquivo de aceite ESTADO 7 sem colunas obrigatorias: "
            + ", ".join(sorted(faltantes))
        )

    df_aceites["NUM_SEQ_INTRP_REGISTRO_7"] = (
        df_aceites["NUM_SEQ_INTRP_REGISTRO_7"].map(normalizar_chave_texto)
    )
    df_aceites["NUM_SEQ_INTRP_REGISTRO_MANTIDO"] = (
        df_aceites["NUM_SEQ_INTRP_REGISTRO_MANTIDO"].map(normalizar_chave_texto)
    )

    logger.info("Aceites ESTADO 7 carregados: %s", f"{len(df_aceites):,}")
    return df_aceites.drop_duplicates(
        subset=["NUM_SEQ_INTRP_REGISTRO_7", "NUM_SEQ_INTRP_REGISTRO_MANTIDO"]
    )


def detectar_encoding_arquivo(caminho):
    conteudo = caminho.read_bytes()

    if conteudo.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"

    try:
        conteudo.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def exportar_resumo_iqs(arquivos_exportados, total_registros):
    caminho_resumo = EXPORT_DIR / f"Exportacao_IQS_{TIMESTAMP_ARQ}_RESUMO.TXT"
    conteudo = [
        "Exportacao IQS",
        "==============",
        "",
        "Status: OK",
        f"Total de registros alterados: {total_registros:,}",
        f"Total de arquivos gerados: {len(arquivos_exportados):,}",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        "Arquivos:",
    ]

    for caminho in arquivos_exportados:
        conteudo.append(f"- {caminho}")

    caminho_resumo.write_text("\n".join(conteudo) + "\n", encoding="utf-8")
    return caminho_resumo.as_posix()


def coluna_raw_expr(colunas_raw, candidatos, fallback="' '"):
    coluna = coluna_existente_flexivel(colunas_raw, candidatos)

    if not coluna:
        return fallback

    return f"CAST(r.{coluna} AS VARCHAR)"


def origem_expressao_exportacao(expressao):
    if expressao.startswith("CAST(r."):
        return "RAW"

    if expressao.startswith("t."):
        return "TRATAMENTO"

    if expressao.startswith("CONCAT("):
        return "CALCULADO"

    if expressao == "' '":
        return "SEM_ORIGEM"

    return "EXPRESSAO"


def detalhe_expressao_exportacao(expressao):
    if expressao.startswith("CAST(r."):
        return expressao.removeprefix("CAST(r.").removesuffix(" AS VARCHAR)")

    return expressao


def _obsoleto_montar_select_exportacao_iqs_v1(con, regional):
    global ULTIMO_MAPEAMENTO_EXPORTACAO

    colunas_raw = [
        linha[0]
        for linha in con.execute("DESCRIBE raw_db.hiadms_raw").fetchall()
    ]

    campos = {
        "PID_INTRP_CONJTO_PIN": coluna_raw_expr(
            colunas_raw,
            ("PID_INTRP_CONJTO_PIN", "PID_INTRP_CONJTO_PIN_HIADMS", "NUM_SEQ_INTRP_CHVP_HIADMS"),
            "t.NUM_SEQ_INTRP",
        ),
        "PID_POSTO_PIN": coluna_raw_expr(
            colunas_raw,
            (
                "PID_POSTO_PIN_PRIM_HIADMS",
                "PID_POSTO_PIN_ULT_HIADMS",
                "PID_POSTO_PIN_HIADMS",
                "PID_POSTO_PIN",
                "PID_POSTO_PIN_PRIM",
                "PID_POSTO_PIN_ULT",
            ),
            "t.NUM_POSTO_UCI",
        ),
        "INDIC_AREA_REDE_POSTO_PIN": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_AREA_REDE_POSTO_PIN_PRIM_HIADMS",
                "INDIC_AREA_REDE_POSTO_PIN_ULT_HIADMS",
                "INDIC_AREA_REDE_POSTO_PIN_HIADMS",
                "INDIC_AREA_REDE_POSTO_PIN",
            ),
        ),
        "ALIM_INTRP_PIN": coluna_raw_expr(
            colunas_raw,
            (
                "NUM_ALIM_INTRP_PRIM_HIADMS",
                "NUM_ALIM_INTRP_PIN_PRIM_HIADMS",
                "ALIM_INTRP_PIN_PRIM_HIADMS",
                "ALIM_INTRP_PIN_HIADMS",
                "ALIM_INTRP_PIN",
            ),
        ),
        "ESTADO_INTRP": "t.ESTADO_INTRP",
        "ALIM_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "ALIM_INTRP_PRIM_HIADMS",
                "ALIM_INTRP_ULT_HIADMS",
                "ALIM_INTRP_HIADMS",
                "ALIM_INTRP",
                "NUM_ALIM_INTRP_ULT_HIADMS",
                "NUM_ALIM_INTRP_PRIM_HIADMS",
            ),
        ),
        "CAR_SE": coluna_raw_expr(
            colunas_raw,
            (
                "CAR_SE_INTRP_PRIM_HIADMS",
                "CAR_SE_INTRP_ULT_HIADMS",
                "CAR_SE_INTRP_HIADMS",
                "CAR_SE_HIADMS",
                "CAR_SE",
            ),
        ),
        "INDIC_INTRP_SE_ALIM": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_INTRP_SE_ALIM_INTRP_ULT_HIADMS",
                "INDIC_INTRP_SE_ALIM_INTRP_PRIM_HIADMS",
                "INDIC_INTRP_SE_ALIM_ULT_HIADMS",
                "INDIC_INTRP_SE_ALIM_PRIM_HIADMS",
                "INDIC_INTRP_SE_ALIM_HIADMS",
                "INDIC_INTRP_SE_ALIM",
            ),
        ),
        "NUM_OCORRENCIA_ADMS": "t.NUM_OCORRENCIA_ADMS",
        "INDIC_INTRP_AT": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_INTRP_AT_INTRP_ULT_HIADMS",
                "INDIC_INTRP_AT_INTRP_PRIM_HIADMS",
                "INDIC_INTRP_AT_ULT_HIADMS",
                "INDIC_INTRP_AT_PRIM_HIADMS",
                "INDIC_INTRP_AT_HIADMS",
                "INDIC_INTRP_AT",
            ),
        ),
        "CONS_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "CONS_INTRP_PRIM_HIADMS",
                "CONS_INTRP_ULT_HIADMS",
                "QTD_CONS_INTRP_ULT_HIADMS",
                "QTD_CONS_INTRP_PRIM_HIADMS",
                "CONS_INTRP_HIADMS",
                "CONS_INTRP",
            ),
        ),
        "KVA_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "KVA_INTRP_PRIM_HIADMS",
                "KVA_INTRP_ULT_HIADMS",
                "KVA_INTRP_HIADMS",
                "KVA_INTRP",
            ),
        ),
        "NUM_OPER_CHV_INTRP": "t.NUM_OPER_CHV_INTRP",
        "NUM_FUNCAO_ELET_HCAI": coluna_raw_expr(
            colunas_raw,
            (
                "NUM_FUNCAO_ELET_INTRP_PRIM_HIADMS",
                "NUM_FUNCAO_ELET_INTRP_ULT_HIADMS",
                "NUM_FUNCAO_ELET_HCAI",
                "NUM_FUNCAO_ELET_HCAI_HIADMS",
                "NUM_FUNC_ELET_HCAI",
                "NUM_FUNC_ELET_HCAI_HIADMS",
                "DESC_FUNCAO_ELET_HCAI",
            ),
        ),
        "DESC_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "DESC_INTRP_ULT_HIADMS",
                "DESC_INTRP_PRIM_HIADMS",
                "DESC_INTRP_HIADMS",
                "DESC_INTRP",
            ),
        ),
        "VALID_POS_OPERACAO": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_VALID_POS_OPER_INTRP_ULT_HIADMS",
                "INDIC_VALID_POS_OPER_INTRP_PRIM_HIADMS",
                "VALID_POS_OPERACAO_ULT_HIADMS",
                "VALID_POS_OPERACAO_PRIM_HIADMS",
                "VALID_POS_OPERACAO_HIADMS",
                "VALID_POS_OPERACAO",
            ),
            "t.VALID_POS_OPERACAO",
        ),
        "DATA_HORA_INIC_INTRP": "t.DATA_HORA_INIC_INTRP",
        "DATA_HORA_FIM_INTRP": "t.DATA_HORA_FIM_INTRP",
        "TIPO_EQP_INTRP": "t.TIPO_EQP_INTRP",
        "COORD_X_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "COORD_X_INTRP_ULT_HIADMS",
                "COORD_X_INTRP_PRIM_HIADMS",
                "COORD_X_INTRP_HIADMS",
                "COORD_X_INTRP",
                "COORD_X_CHV_INTRP_ULT_HIADMS",
            ),
        ),
        "COORD_Y_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "COORD_Y_INTRP_ULT_HIADMS",
                "COORD_Y_INTRP_PRIM_HIADMS",
                "COORD_Y_INTRP_HIADMS",
                "COORD_Y_INTRP",
                "COORD_Y_CHV_INTRP_ULT_HIADMS",
            ),
        ),
        "NUM_SEQ_INTRP": "t.NUM_SEQ_INTRP",
        "COD_CAUSA_INTRP": "t.COD_CAUSA_INTRP",
        "COD_COMP_INTRP": "t.COD_COMP_INTRP",
        "COD_AREA_ELET_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "COD_AREA_ELET_INTRP_ULT_HIADMS",
                "COD_AREA_ELET_INTRP_PRIM_HIADMS",
                "COD_AREA_ELET_INTRP_HIADMS",
                "COD_AREA_ELET_INTRP",
            ),
        ),
        "COD_GRUPO_COMP_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "COD_GRUPO_COMP_INTRP_ULT_HIADMS",
                "COD_GRUPO_COMP_INTRP_PRIM_HIADMS",
                "COD_GRUPO_COMP_INTRP_HIADMS",
                "COD_GRUPO_COMP_INTRP",
            ),
        ),
        "COD_COND_CLIMA_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "COD_COND_CLIMA_INTRP_ULT_HIADMS",
                "COD_COND_CLIMA_INTRP_PRIM_HIADMS",
                "COD_COND_CLIMA_INTRP_HIADMS",
                "COD_COND_CLIMA_INTRP",
            ),
        ),
        "COD_TIPO_INTRP": coluna_raw_expr(colunas_raw, ("COD_TIPO_INTRP_ULT_HIADMS", "COD_TIPO_INTRP_PRIM_HIADMS", "COD_TIPO_INTRP_HIADMS", "COD_TIPO_INTRP")),
        "INDIC_JUMP_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_JUMP_INTRP_ULT_HIADMS",
                "INDIC_JUMP_INTRP_PRIM_HIADMS",
                "INDIC_JUMP_INTRP_HIADMS",
                "INDIC_JUMP_INTRP",
            ),
        ),
        "NUM_PROTOC_JUSTIF_RESP_INTRP": coluna_raw_expr(colunas_raw, ("NUM_PROTOC_JUSTIF_RESP_INTRP_ULT_HIADMS", "NUM_PROTOC_JUSTIF_RESP_INTRP_PRIM_HIADMS", "NUM_PROTOC_JUSTIF_RESP_INTRP_HIADMS", "NUM_PROTOC_JUSTIF_RESP_INTRP")),
        "TIPO_PROTOC_JUSTIF_INTRP": coluna_raw_expr(colunas_raw, ("TIPO_PROTOC_JUSTIF_INTRP_ULT_HIADMS", "TIPO_PROTOC_JUSTIF_INTRP_PRIM_HIADMS", "TIPO_PROTOC_JUSTIF_INTRP_HIADMS", "TIPO_PROTOC_JUSTIF_INTRP")),
        "COD_CONJTO_ELET_ANEEL_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "COD_CONJTO_ELET_ANEEL_INTRP_ULT_HIADMS",
                "COD_CONJTO_ELET_ANEEL_INTRP_PRIM_HIADMS",
                "COD_CONJTO_ELET_ANEEL_INTRP_HIADMS",
                "COD_CONJTO_ELET_ANEEL_INTRP",
                "COD_CONJ_ELET_ANEEL_INTRP_ULT_HIADMS",
            ),
        ),
        "INDIC_CALC_DMIC_INTRP": coluna_raw_expr(colunas_raw, ("INDIC_CALC_DMIC_INTRP_ULT_HIADMS", "INDIC_CALC_DMIC_INTRP_HIADMS", "INDIC_CALC_DMIC_INTRP")),
        "INDIC_PONTO_CONEX_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_PONTO_CONEX_INTRP_PRIM_HIADMS",
                "INDIC_PONTO_CONEX_INTRP_ULT_HIADMS",
                "INDIC_PONTO_CONEX_INTRP_HIADMS",
                "INDIC_PONTO_CONEX_INTRP",
            ),
        ),
        "NUM_GEO_CHV_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "NUM_GEO_CHV_INTRP_ULT_HIADMS",
                "NUM_GEO_CHV_INTRP_PRIM_HIADMS",
                "NUM_GEO_CHV_INTRP_HIADMS",
                "NUM_GEO_CHV_INTRP",
            ),
        ),
        "TIPO_REDE_CHV_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "TIPO_REDE_CHV_INTRP_ULT_HIADMS",
                "TIPO_REDE_CHV_INTRP_PRIM_HIADMS",
                "TIPO_REDE_CHV_INTRP_HIADMS",
                "TIPO_REDE_CHV_INTRP",
            ),
        ),
        "TIPO_CHV_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "TIPO_CHV_INTRP_ULT_HIADMS",
                "TIPO_CHV_INTRP_PRIM_HIADMS",
                "TIPO_CHV_INTRP_HIADMS",
                "TIPO_CHV_INTRP",
            ),
        ),
        "INDIC_PROPR_POSTO_INTRP": coluna_raw_expr(colunas_raw, ("INDIC_PROPR_POSTO_INTRP_PRIM_HIADMS", "INDIC_PROPR_POSTO_INTRP_HIADMS", "INDIC_PROPR_POSTO_INTRP")),
        "TENSAO_OPER_ALIM_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "TENSAO_OPER_ALIM_INTRP_ULT_HIADMS",
                "TENSAO_OPER_ALIM_INTRP_PRIM_HIADMS",
                "TENSAO_OPER_ALIM_INTRP_HIADMS",
                "TENSAO_OPER_ALIM_INTRP",
            ),
        ),
        "INDIC_DESLIG_ENT_SERV_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_DESLIG_ENT_SERV_INTRP_ULT_HIADMS",
                "INDIC_DESLIG_ENT_SERV_INTRP_PRIM_HIADMS",
                "INDIC_DESLIG_ENT_SERV_INTRP_HIADMS",
                "INDIC_DESLIG_ENT_SERV_INTRP",
            ),
        ),
        "INDIC_PROPR_CHVP_INTRP": coluna_raw_expr(colunas_raw, ("INDIC_PROPR_CHVP_INTRP_PRIM_HIADMS", "INDIC_PROPR_CHVP_INTRP_HIADMS", "INDIC_PROPR_CHVP_INTRP")),
        "INDIC_CHVP_INIC_ALIM_INTRP": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_CHVP_INIC_ALIM_INTRP_PRIM_HIADMS",
                "INDIC_CHVP_INIC_ALIM_INTRP_ULT_HIADMS",
                "INDIC_CHVP_INIC_ALIM_INTRP_HIADMS",
                "INDIC_CHVP_INIC_ALIM_INTRP",
            ),
        ),
        "PID": coluna_raw_expr(colunas_raw, ("PID", "PID_HIADMS", "NUM_SEQ_INTRP_CHVP_HIADMS"), "t.NUM_SEQ_INTRP"),
        "PID_INTRP_UCI": coluna_raw_expr(colunas_raw, ("PID_INTRP_UCI", "PID_INTRP_UCI_HIADMS", "NUM_SEQ_INTRP_CHVP_HIADMS"), "t.NUM_SEQ_INTRP"),
        "NUM_INTRP_UCI": "t.NUM_INTRP_UCI",
        "NUM_POSTO_UCI": "t.NUM_POSTO_UCI",
        "NUM_UC_UCI": "t.NUM_UC_UCI",
        "TIPO_SIT_UC_UCI": coluna_raw_expr(
            colunas_raw,
            (
                "TIPO_SIT_UC_UCI_ULT_HIADMS",
                "TIPO_SIT_UC_UCI_HIADMS",
                "TIPO_SIT_UC_UCI",
            ),
        ),
        "DTHR_INICIO_INTRP_UC": "t.DTHR_INICIO_INTRP_UC",
        "NUM_INTRP_INIC_MANOBRA_UCI": "t.NUM_INTRP_INIC_MANOBRA_UCI",
        "NUM_MOTIVO_TRAT_DIF_UCI": "t.NUM_MOTIVO_TRAT_DIF_UCI",
        "UC_ACESSANTE": coluna_raw_expr(
            colunas_raw,
            (
                "INDIC_UC_ACESS_UCI_PRIM_HIADMS",
                "INDIC_UC_ACESS_UCI_ULT_HIADMS",
                "UC_ACESSANTE_ULT_HIADMS",
                "UC_ACESSANTE_HIADMS",
                "UC_ACESSANTE",
                "INDIC_UC_ACESSANTE_ULT_HIADMS",
            ),
        ),
        "SIGLA_REGIONAL": "t.SIGLA_REGIONAL_ORIG",
        "NUM_PROTOC_JUSTIF_RESP_UCI": coluna_raw_expr(colunas_raw, ("NUM_PROTOC_JUSTIF_RESP_UCI_ULT_HIADMS", "NUM_PROTOC_JUSTIF_RESP_UCI_HIADMS", "NUM_PROTOC_JUSTIF_RESP_UCI")),
        "TIPO_PROTOC_JUSTIF_UCI": "t.TIPO_PROTOC_JUSTIF_UCI",
        "PID_PIN": coluna_raw_expr(
            colunas_raw,
            (
                "PID_PIN",
                "PID_PIN_HIADMS",
                "PID_PIN_PRIM_HIADMS",
                "PID_PIN_ULT_HIADMS",
            ),
            "CONCAT(t.NUM_SEQ_INTRP, t.NUM_POSTO_UCI)",
        ),
        "INDIC_PROCES_IND_PIN": coluna_raw_expr(colunas_raw, ("INDIC_PROCES_IND_PIN_ULT_HIADMS", "INDIC_PROCES_IND_PIN_HIADMS", "INDIC_PROCES_IND_PIN")),
        "INDIC_SIT_PROCES_INDIC_UCI": "t.INDIC_SIT_PROCES_INDIC_UCI",
    }

    select_campos = ",\n            ".join(
        f"{expressao} AS {nome}"
        for nome, expressao in campos.items()
    )
    ULTIMO_MAPEAMENTO_EXPORTACAO = [
        {
            "CAMPO_LAYOUT": nome,
            "ORIGEM": origem_expressao_exportacao(expressao),
            "DETALHE_ORIGEM": detalhe_expressao_exportacao(expressao),
        }
        for nome, expressao in campos.items()
    ]

    return f"""
        SELECT
            {select_campos}
        FROM adms_iqs_alterados t
        LEFT JOIN raw_db.hiadms_raw r
          ON CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) = t.NUM_SEQ_INTRP
         AND CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) = t.NUM_UC_UCI
        WHERE t.REGIONAL = {sql_literal(regional)}
    """


def _obsoleto_consultar_exportacao_iqs_regional_v1(con, regional):
    return con.execute(_obsoleto_montar_select_exportacao_iqs_v1(con, regional)).fetchdf()


def montar_select_exportacao_iqs(con, regional):
    global ULTIMO_MAPEAMENTO_EXPORTACAO

    campos = [
        ("PID_INTRP_CONJTO_PIN", "CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR)"),
        ("PID_POSTO_PIN", "CAST(r.PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR)"),
        ("INDIC_AREA_REDE_POSTO_PIN", "CAST(r.INDIC_AREA_REDE_POSTO_PIN_PRIM_HIADMS AS VARCHAR)"),
        ("ALIM_INTRP_PIN", "CAST(r.NUM_ALIM_INTRP_PIN_PRIM_HIADMS AS VARCHAR)"),
        ("ESTADO_INTRP", "t.ESTADO_INTRP"),
        ("ALIM_INTRP", "CAST(r.ALIM_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("CAR_SE", "CAST(r.CAR_SE_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("INDIC_INTRP_SE_ALIM", "CAST(r.INDIC_INTRP_SE_ALIM_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("NUM_OCORRENCIA_ADMS", "CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("INDIC_INTRP_AT", "CAST(r.INDIC_INTRP_AT_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("CONS_INTRP", "CAST(r.CONS_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("KVA_INTRP", "REPLACE(CAST(r.KVA_INTRP_PRIM_HIADMS AS VARCHAR), '.', ',')"),
        ("NUM_OPER_CHV_INTRP", "CAST(r.NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("NUM_FUNCAO_ELET_HCAI", "CAST(r.NUM_FUNCAO_ELET_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("DESC_INTRP", "CAST(r.NUM_FUNCAO_ELET_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("VALID_POS_OPERACAO", "CAST(r.INDIC_VALID_POS_OPER_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("DATA_HORA_INIC_INTRP", "CAST(r.DATA_HORA_INIC_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("DATA_HORA_FIM_INTRP", "CAST(r.DATA_HORA_FIM_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("TIPO_EQP_INTRP", "CAST(r.TIPO_EQP_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("COORD_X_INTRP", "CAST(r.COORD_X_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("COORD_Y_INTRP", "CAST(r.COORD_Y_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("NUM_SEQ_INTRP", "CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR)"),
        ("COD_CAUSA_INTRP", "CAST(r.COD_CAUSA_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("COD_COMP_INTRP", "CAST(r.COD_COMP_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("COD_AREA_ELET_INTRP", "CAST(r.COD_AREA_ELET_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("COD_GRUPO_COMP_INTRP", "CAST(r.COD_GRUPO_COMP_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("COD_COND_CLIMA_INTRP", "CAST(r.COD_COND_CLIMA_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("COD_TIPO_INTRP", "CAST(r.COD_TIPO_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("INDIC_JUMP_INTRP", "CAST(r.INDIC_JUMP_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("NUM_PROTOC_JUSTIF_RESP_INTRP", "CAST(r.NUM_PROTOC_JUSTIF_RESP_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("TIPO_PROTOC_JUSTIF_INTRP", "CAST(r.TIPO_PROTOC_JUSTIF_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("COD_CONJTO_ELET_ANEEL_INTRP", "CAST(r.COD_CONJTO_ELET_ANEEL_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("INDIC_CALC_DMIC_INTRP", "CAST(r.INDIC_CALC_DMIC_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("INDIC_PONTO_CONEX_INTRP", "CAST(r.INDIC_PONTO_CONEX_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("NUM_GEO_CHV_INTRP", "CAST(r.NUM_GEO_CHV_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("TIPO_REDE_CHV_INTRP", "CAST(r.TIPO_REDE_CHV_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("TIPO_CHV_INTRP", "CAST(r.TIPO_CHV_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("INDIC_PROPR_POSTO_INTRP", "CAST(r.INDIC_PROPR_POSTO_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("TENSAO_OPER_ALIM_INTRP", "CAST(r.TENSAO_OPER_ALIM_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("INDIC_DESLIG_ENT_SERV_INTRP", "CAST(r.INDIC_DESLIG_ENT_SERV_INTRP_ULT_HIADMS AS VARCHAR)"),
        ("INDIC_PROPR_CHVP_INTRP", "CAST(r.INDIC_PROPR_CHVP_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("INDIC_CHVP_INIC_ALIM_INTRP", "CAST(r.INDIC_CHVP_INIC_ALIM_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("PID", "CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR)"),
        ("PID_INTRP_UCI", "CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR)"),
        ("NUM_INTRP_UCI", "CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR)"),
        ("NUM_POSTO_UCI", "CAST(r.PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR)"),
        ("NUM_UC_UCI", "CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR)"),
        ("TIPO_SIT_UC_UCI", "CAST(r.TIPO_SIT_UC_UCI_PRIM_HIADMS AS VARCHAR)"),
        ("DTHR_INICIO_INTRP_UC", "t.DTHR_INICIO_INTRP_UC"),
        ("NUM_INTRP_INIC_MANOBRA_UCI", "t.NUM_INTRP_INIC_MANOBRA_UCI"),
        ("NUM_MOTIVO_TRAT_DIF_UCI", "t.NUM_MOTIVO_TRAT_DIF_UCI"),
        ("UC_ACESSANTE", "CAST(r.INDIC_UC_ACESS_UCI_PRIM_HIADMS AS VARCHAR)"),
        ("SIGLA_REGIONAL", "CAST(r.SIGLA_REGIONAL_INTRP_PRIM_HIADMS AS VARCHAR)"),
        ("NUM_PROTOC_JUSTIF_RESP_UCI", "CAST(r.NUM_PROTOC_JUSTIF_RESP_UCI_ULT_HIADMS AS VARCHAR)"),
        ("TIPO_PROTOC_JUSTIF_UCI", "CAST(r.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR)"),
        ("PID_PIN", "CAST(r.PID_PIN_PRIM_HIADMS AS VARCHAR)"),
        ("INDIC_PROCES_IND_PIN", "CAST(r.INDIC_PROCES_IND_PIN_ULT_HIADMS AS VARCHAR)"),
        ("INDIC_SIT_PROCES_INDIC_UCI", "t.INDIC_SIT_PROCES_INDIC_UCI"),
    ]

    select_campos = ",\n            ".join(
        f"{expressao} AS {nome}"
        for nome, expressao in campos
    )
    ULTIMO_MAPEAMENTO_EXPORTACAO = [
        {
            "CAMPO_LAYOUT": nome,
            "ORIGEM": origem_expressao_exportacao(expressao),
            "DETALHE_ORIGEM": detalhe_expressao_exportacao(expressao),
        }
        for nome, expressao in campos
    ]

    return f"""
        SELECT
            {select_campos}
        FROM adms_iqs_alterados t
        JOIN raw_db.hiadms_raw r
          ON CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) = t.NUM_SEQ_INTRP
         AND CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) = t.NUM_UC_UCI
         AND CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) = t.NUM_OCORRENCIA_ADMS
        WHERE t.REGIONAL = {sql_literal(regional)}
    """


def exportar_previa_iqs_bloqueada(con, regionais, total_registros, auditoria_estado_7, logger):
    arquivos_previa = exportar_arquivos_iqs(
        con,
        regionais,
        MARTS_DIR,
        "PRE_EXPORT_",
        logger,
    )
    mapeamento_exportado = exportar_mapeamento_layout_iqs(logger)

    caminho_resumo = MARTS_DIR / f"PRE_EXPORT_Interrupcoes_IQS_{TIMESTAMP_ARQ}_RESUMO.TXT"
    conteudo = [
        "Pre-export IQS bloqueado",
        "========================",
        "",
        "Status: NAO LIBERADO PARA IQS",
        "Motivo: auditoria ESTADO_INTRP 7 encontrou anomalias.",
        f"Total de registros alterados: {total_registros:,}",
        f"Total de arquivos de previa: {len(arquivos_previa):,}",
        f"Arquivo de anomalias pendentes: {auditoria_estado_7['pending_anomalies_path']}",
        f"Arquivo de anomalias aceitas: {auditoria_estado_7['accepted_anomalies_path']}",
        f"Resumo da auditoria: {auditoria_estado_7['summary_path']}",
        f"Mapeamento do layout: {mapeamento_exportado or 'nao gerado'}",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        "Arquivos de previa:",
    ]

    for caminho in arquivos_previa:
        conteudo.append(f"- {caminho}")

    caminho_resumo.write_text("\n".join(conteudo) + "\n", encoding="utf-8")
    logger.info("Resumo da previa bloqueada gerado: %s", caminho_resumo)

    return {
        "files": arquivos_previa,
        "summary_path": caminho_resumo.as_posix(),
    }


def exportar_mapeamento_layout_iqs(logger):
    if not ULTIMO_MAPEAMENTO_EXPORTACAO:
        return None

    caminho_csv = MARTS_DIR / f"Mapeamento_Layout_IQS_{TIMESTAMP_ARQ}.CSV"
    df_mapeamento = pd.DataFrame(ULTIMO_MAPEAMENTO_EXPORTACAO)
    exportar_csv_formatado(df_mapeamento, caminho_csv)
    logger.info("Mapeamento do layout IQS exportado: %s", caminho_csv)
    return caminho_csv.as_posix()


def auditar_join_raw_export(con, logger):
    total_sem_raw = con.execute("""
        SELECT COUNT(*)
        FROM adms_iqs_alterados t
        LEFT JOIN raw_db.hiadms_raw r
          ON CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) = t.NUM_SEQ_INTRP
         AND CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) = t.NUM_UC_UCI
         AND CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) = t.NUM_OCORRENCIA_ADMS
        WHERE r.NUM_SEQ_INTRP_CHVP_HIADMS IS NULL
    """).fetchone()[0]

    caminho_csv = MARTS_DIR / f"Auditoria_Join_RAW_Export_{TIMESTAMP_ARQ}.CSV"

    if total_sem_raw > 0:
        df_sem_raw = con.execute("""
            SELECT
                t.NUM_OCORRENCIA_ADMS,
                t.NUM_SEQ_INTRP,
                t.NUM_UC_UCI,
                t.REGIONAL,
                t.ESTADO_INTRP,
                t.ACAO_SOBREPOSICAO_INTERRUPCAO,
                t.ACAO_SOBREPOSICAO_TOTAL_UC,
                t.ACAO_AJUSTE_PARCIAL
            FROM adms_iqs_alterados t
            LEFT JOIN raw_db.hiadms_raw r
              ON CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) = t.NUM_SEQ_INTRP
             AND CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) = t.NUM_UC_UCI
             AND CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) = t.NUM_OCORRENCIA_ADMS
            WHERE r.NUM_SEQ_INTRP_CHVP_HIADMS IS NULL
            ORDER BY
                t.REGIONAL,
                t.NUM_SEQ_INTRP,
                t.NUM_UC_UCI
        """).fetchdf()
        exportar_csv_formatado(df_sem_raw, caminho_csv)
        logger.info("Auditoria join RAW export encontrou falhas: %s", caminho_csv)
    else:
        pd.DataFrame(
            [{"STATUS": "OK", "TOTAL_SEM_RAW": 0}]
        ).to_csv(caminho_csv, sep="|", index=False)
        logger.info("Auditoria join RAW export OK: %s", caminho_csv)

    return {
        "path": caminho_csv.as_posix(),
        "rows_without_raw": total_sem_raw,
    }


def criar_tabela_exportacao_iqs(con, logger):
    global ULTIMO_MAPEAMENTO_EXPORTACAO

    logger.info("Criando tabela materializada de exportacao IQS a partir do RAW...")
    con.execute("""
        DROP TABLE IF EXISTS adms_iqs_export;

CREATE TABLE adms_iqs_export AS
SELECT DISTINCT
            CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS PID_INTRP_CONJTO_PIN,
            CAST(r.PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR) AS PID_POSTO_PIN,
            CAST(r.INDIC_AREA_REDE_POSTO_PIN_PRIM_HIADMS AS VARCHAR) AS INDIC_AREA_REDE_POSTO_PIN,
            CAST(r.NUM_ALIM_INTRP_PIN_PRIM_HIADMS AS VARCHAR) AS ALIM_INTRP_PIN,
            t.ESTADO_INTRP AS ESTADO_INTRP,
            CAST(r.ALIM_INTRP_PRIM_HIADMS AS VARCHAR) AS ALIM_INTRP,
            CAST(r.CAR_SE_INTRP_PRIM_HIADMS AS VARCHAR) AS CAR_SE,
            CAST(r.INDIC_INTRP_SE_ALIM_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_INTRP_SE_ALIM,
            CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
            CAST(r.INDIC_INTRP_AT_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_INTRP_AT,
            CAST(r.CONS_INTRP_PRIM_HIADMS AS VARCHAR) AS CONS_INTRP,
            REPLACE(CAST(r.KVA_INTRP_PRIM_HIADMS AS VARCHAR), '.', ',') AS KVA_INTRP,
            CAST(r.NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OPER_CHV_INTRP,
            CAST(r.NUM_FUNCAO_ELET_INTRP_PRIM_HIADMS AS VARCHAR) AS NUM_FUNCAO_ELET_HCAI,
            CAST(r.NUM_FUNCAO_ELET_INTRP_PRIM_HIADMS AS VARCHAR) AS DESC_INTRP,
            CAST(r.INDIC_VALID_POS_OPER_INTRP_ULT_HIADMS AS VARCHAR) AS VALID_POS_OPERACAO,
            r.DATA_HORA_INIC_INTRP_ULT_HIADMS AS DATA_HORA_INIC_INTRP,
            r.DATA_HORA_FIM_INTRP_ULT_HIADMS AS DATA_HORA_FIM_INTRP,
            CAST(r.TIPO_EQP_INTRP_PRIM_HIADMS AS VARCHAR) AS TIPO_EQP_INTRP,
            CAST(r.COORD_X_INTRP_PRIM_HIADMS AS VARCHAR) AS COORD_X_INTRP,
            CAST(r.COORD_Y_INTRP_PRIM_HIADMS AS VARCHAR) AS COORD_Y_INTRP,
            CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
            CAST(r.COD_CAUSA_INTRP_ULT_HIADMS AS VARCHAR) AS COD_CAUSA_INTRP,
            CAST(r.COD_COMP_INTRP_ULT_HIADMS AS VARCHAR) AS COD_COMP_INTRP,
            CAST(r.COD_AREA_ELET_INTRP_ULT_HIADMS AS VARCHAR) AS COD_AREA_ELET_INTRP,
            CAST(r.COD_GRUPO_COMP_INTRP_ULT_HIADMS AS VARCHAR) AS COD_GRUPO_COMP_INTRP,
            CAST(r.COD_COND_CLIMA_INTRP_ULT_HIADMS AS VARCHAR) AS COD_COND_CLIMA_INTRP,
            CAST(r.COD_TIPO_INTRP_ULT_HIADMS AS VARCHAR) AS COD_TIPO_INTRP,
            CAST(r.INDIC_JUMP_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_JUMP_INTRP,
            CAST(r.NUM_PROTOC_JUSTIF_RESP_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_PROTOC_JUSTIF_RESP_INTRP,
            CAST(r.TIPO_PROTOC_JUSTIF_INTRP_ULT_HIADMS AS VARCHAR) AS TIPO_PROTOC_JUSTIF_INTRP,
            CAST(r.COD_CONJTO_ELET_ANEEL_INTRP_PRIM_HIADMS AS VARCHAR) AS COD_CONJTO_ELET_ANEEL_INTRP,
            CAST(r.INDIC_CALC_DMIC_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_CALC_DMIC_INTRP,
            CAST(r.INDIC_PONTO_CONEX_INTRP_PRIM_HIADMS AS VARCHAR) AS INDIC_PONTO_CONEX_INTRP,
            CAST(r.NUM_GEO_CHV_INTRP_PRIM_HIADMS AS VARCHAR) AS NUM_GEO_CHV_INTRP,
            CAST(r.TIPO_REDE_CHV_INTRP_PRIM_HIADMS AS VARCHAR) AS TIPO_REDE_CHV_INTRP,
            CAST(r.TIPO_CHV_INTRP_PRIM_HIADMS AS VARCHAR) AS TIPO_CHV_INTRP,
            CAST(r.INDIC_PROPR_POSTO_INTRP_PRIM_HIADMS AS VARCHAR) AS INDIC_PROPR_POSTO_INTRP,
            CAST(r.TENSAO_OPER_ALIM_INTRP_PRIM_HIADMS AS VARCHAR) AS TENSAO_OPER_ALIM_INTRP,
            CAST(r.INDIC_DESLIG_ENT_SERV_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_DESLIG_ENT_SERV_INTRP,
            CAST(r.INDIC_PROPR_CHVP_INTRP_PRIM_HIADMS AS VARCHAR) AS INDIC_PROPR_CHVP_INTRP,
            CAST(r.INDIC_CHVP_INIC_ALIM_INTRP_PRIM_HIADMS AS VARCHAR) AS INDIC_CHVP_INIC_ALIM_INTRP,
            CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS PID,
            CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS PID_INTRP_UCI,
            CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_INTRP_UCI,
            CAST(r.PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR) AS NUM_POSTO_UCI,
            CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS NUM_UC_UCI,
            CAST(r.TIPO_SIT_UC_UCI_PRIM_HIADMS AS VARCHAR) AS TIPO_SIT_UC_UCI,
            COALESCE(t.DTHR_INICIO_INTRP_UC, r.DATA_HORA_INIC_INTRP_ULT_HIADMS) AS DTHR_INICIO_INTRP_UC,
            COALESCE(
                NULLIF(TRIM(t.NUM_INTRP_INIC_MANOBRA_UCI), ''),
                CAST(r.NUM_INTRP_INIC_MANOBRA_UCI_ULT_HIADMS AS VARCHAR)
            ) AS NUM_INTRP_INIC_MANOBRA_UCI,
            COALESCE(
                NULLIF(TRIM(t.NUM_MOTIVO_TRAT_DIF_UCI), ''),
                CAST(r.NUM_MOTIVO_TRAT_DIF_UCI_ULT_HIADMS AS VARCHAR)
            ) AS NUM_MOTIVO_TRAT_DIF_UCI,
            CAST(r.INDIC_UC_ACESS_UCI_PRIM_HIADMS AS VARCHAR) AS UC_ACESSANTE,
            CAST(r.SIGLA_REGIONAL_INTRP_PRIM_HIADMS AS VARCHAR) AS SIGLA_REGIONAL,
            CAST(r.NUM_PROTOC_JUSTIF_RESP_UCI_ULT_HIADMS AS VARCHAR) AS NUM_PROTOC_JUSTIF_RESP_UCI,
            CAST(r.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR) AS TIPO_PROTOC_JUSTIF_UCI,
            CAST(r.PID_PIN_PRIM_HIADMS AS VARCHAR) AS PID_PIN,
            CAST(r.INDIC_PROCES_IND_PIN_ULT_HIADMS AS VARCHAR) AS INDIC_PROCES_IND_PIN,
            COALESCE(
                NULLIF(TRIM(t.INDIC_SIT_PROCES_INDIC_UCI), ''),
                CAST(r.INDIC_SIT_PROCES_INDIC_UCI_ULT_HIADMS AS VARCHAR)
            ) AS INDIC_SIT_PROCES_INDIC_UCI,
            t.REGIONAL AS REGIONAL_EXPORT
        FROM adms_iqs_alterados t
        JOIN raw_db.hiadms_raw r
          ON CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) = t.NUM_SEQ_INTRP
         AND CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) = t.NUM_UC_UCI
         AND CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) = t.NUM_OCORRENCIA_ADMS
    """)

    ULTIMO_MAPEAMENTO_EXPORTACAO = []
    campos_tratamento = {
        "ESTADO_INTRP",
        "DTHR_INICIO_INTRP_UC",
        "NUM_INTRP_INIC_MANOBRA_UCI",
        "NUM_MOTIVO_TRAT_DIF_UCI",
        "INDIC_SIT_PROCES_INDIC_UCI",
    }

    for coluna in LAYOUT_IQS_COLUNAS:
        ULTIMO_MAPEAMENTO_EXPORTACAO.append(
            {
                "CAMPO_LAYOUT": coluna,
                "ORIGEM": "TRATAMENTO" if coluna in campos_tratamento else "RAW",
                "DETALHE_ORIGEM": "adms_iqs_alterados" if coluna in campos_tratamento else "hiadms_raw",
            }
        )

    con.execute("""
        UPDATE adms_iqs_export
        SET NUM_INTRP_INIC_MANOBRA_UCI = NULL
        WHERE NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
           OR TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) IN ('0', '0.0')
           OR TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) = TRIM(CAST(NUM_INTRP_UCI AS VARCHAR))
           OR TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) = TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
    """)

    manobra_nulos, manobra_preenchidos = con.execute("""
        SELECT
            SUM(CASE WHEN NUM_INTRP_INIC_MANOBRA_UCI IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN NUM_INTRP_INIC_MANOBRA_UCI IS NOT NULL THEN 1 ELSE 0 END)
        FROM adms_iqs_export
    """).fetchone()
    logger.info(
        "NUM_INTRP_INIC_MANOBRA_UCI apos normalizacao: nulos=%s, preenchidos=%s",
        f"{manobra_nulos:,}",
        f"{manobra_preenchidos:,}",
    )

    total_export = con.execute("SELECT COUNT(*) FROM adms_iqs_export").fetchone()[0]
    logger.info("Tabela adms_iqs_export criada. Registros: %s", f"{total_export:,}")
    return total_export


def consultar_exportacao_iqs_regional(con, regional):
    colunas = ", ".join(LAYOUT_IQS_COLUNAS)

    return con.execute(f"""
        SELECT {colunas}
        FROM adms_iqs_export
        WHERE REGIONAL_EXPORT = {sql_literal(regional)}
    """).fetchdf()


def exportar_arquivos_iqs(con, regionais, diretorio_destino, prefixo, logger):
    arquivos_exportados = []

    for (regional,) in regionais:
        nome_arquivo = f"{prefixo}Interrupcoes_IQS_{TIMESTAMP_ARQ}_{regional}.CSV"
        caminho_csv = diretorio_destino / nome_arquivo

        logger.info("Exportando %s: %s", regional, caminho_csv)
        df_export = consultar_exportacao_iqs_regional(con, regional)
        exportar_csv_iqs_oficial(df_export, caminho_csv)
        arquivos_exportados.append(caminho_csv.as_posix())

    return arquivos_exportados


def exportar_auditoria_outliers_bruto(con, logger):
    logger.info("Gerando auditoria preventiva de outliers do bruto...")
    con.execute(montar_sql_auditoria_outliers_bruto(con, logger=logger))

    total = con.execute("SELECT COUNT(*) FROM auditoria_outliers_bruto").fetchone()[0]
    caminho_csv = MARTS_DIR / f"Auditoria_Outliers_Bruto_IQS_{TIMESTAMP_ARQ}.CSV"
    caminho_resumo = MARTS_DIR / f"Auditoria_Outliers_Bruto_IQS_{TIMESTAMP_ARQ}_RESUMO.TXT"

    df_outliers = con.execute("""
        SELECT
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            DATA_HORA_INIC_INTRP,
            DATA_HORA_FIM_INTRP,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_TIPO_INTRP,
            TIPO_PROTOC_JUSTIF_UCI,
            NUM_PROTOC_JUSTIF_RESP_UCI
        FROM auditoria_outliers_bruto
        ORDER BY
            DATA_HORA_INIC_INTRP,
            NUM_SEQ_INTRP
    """).fetchdf()

    exportar_csv_formatado(df_outliers, caminho_csv)
    exportar_resumo_auditoria(
        caminho_resumo,
        "Auditoria Outliers Bruto",
        total,
        total,
        caminho_csv.as_posix(),
        caminho_csv.as_posix(),
    )

    with caminho_resumo.open("a", encoding="utf-8") as resumo:
        resumo.write("\nLimiar duracao horas: " + str(OUTLIER_DURACAO_HORAS) + "\n")
        resumo.write("Limiar quantidade UCs: " + str(OUTLIER_QTD_UCS) + "\n")
        resumo.write("Limiar interrupcoes contidas: " + str(OUTLIER_QTD_INTRP_CONTIDAS) + "\n")
        resumo.write("Limiar UCs afetadas: " + str(OUTLIER_QTD_UCS_AFETADAS) + "\n")
        resumo.write("Observacao: auditoria preventiva nao bloqueia o tratamento.\n")

    logger.info("Auditoria outliers bruto exportada: %s", caminho_csv)
    logger.info("Resumo outliers bruto exportado: %s", caminho_resumo)
    logger.info("Outliers brutos encontrados: %s", f"{total:,}")

    return {
        "path": caminho_csv.as_posix(),
        "summary_path": caminho_resumo.as_posix(),
        "rows": total,
        "thresholds": {
            "duracao_horas": OUTLIER_DURACAO_HORAS,
            "qtd_ucs": OUTLIER_QTD_UCS,
            "qtd_intrp_contidas": OUTLIER_QTD_INTRP_CONTIDAS,
            "qtd_ucs_afetadas": OUTLIER_QTD_UCS_AFETADAS,
        },
    }


def exportar_auditoria_manobra_hcai(con, logger):
    logger.info("Gerando auditoria de interrupcoes de manobra UCI...")
    con.execute(montar_sql_auditoria_manobra_hcai(con, logger=logger))

    total = con.execute("SELECT COUNT(*) FROM auditoria_manobra_hcai").fetchone()[0]
    alertas = con.execute("""
        SELECT COUNT(*)
        FROM auditoria_manobra_hcai
        WHERE RESULTADO_AUDITORIA LIKE 'ALERTA:%'
    """).fetchone()[0]

    caminho_csv = MARTS_DIR / f"Auditoria_Manobra_UCI_IQS_{TIMESTAMP_ARQ}.CSV"
    caminho_anomalias = MARTS_DIR / f"Auditoria_Manobra_UCI_IQS_{TIMESTAMP_ARQ}_ANOMALIAS.CSV"
    caminho_resumo = MARTS_DIR / f"Auditoria_Manobra_UCI_IQS_{TIMESTAMP_ARQ}_RESUMO.TXT"

    df_auditoria = con.execute("""
        SELECT *
        FROM auditoria_manobra_hcai
        ORDER BY
            DATA_HORA_INIC_INTRP,
            NUM_SEQ_INTRP
    """).fetchdf()

    df_anomalias = con.execute("""
        SELECT *
        FROM auditoria_manobra_hcai
        WHERE RESULTADO_AUDITORIA LIKE 'ALERTA:%'
        ORDER BY
            RESULTADO_AUDITORIA,
            DATA_HORA_INIC_INTRP,
            NUM_SEQ_INTRP
    """).fetchdf()

    exportar_csv_formatado(df_auditoria, caminho_csv)
    exportar_csv_formatado(df_anomalias, caminho_anomalias)
    exportar_resumo_auditoria(
        caminho_resumo,
        "Auditoria Manobra HCAI",
        total,
        alertas,
        caminho_csv.as_posix(),
        caminho_anomalias.as_posix(),
    )

    logger.info("Auditoria manobra HCAI exportada: %s", caminho_csv)
    logger.info("Anomalias manobra HCAI exportadas: %s", caminho_anomalias)
    logger.info("Resumo manobra HCAI exportado: %s", caminho_resumo)
    logger.info("Manobras HCAI auditadas: %s", f"{total:,}")
    logger.info("Alertas manobra HCAI: %s", f"{alertas:,}")

    return {
        "path": caminho_csv.as_posix(),
        "anomalies_path": caminho_anomalias.as_posix(),
        "summary_path": caminho_resumo.as_posix(),
        "rows": total,
        "alerts": alertas,
    }


def exportar_auditoria_estado_7(con, logger):
    logger.info("Gerando auditoria dos registros ESTADO_INTRP=7...")
    con.execute(montar_sql_auditoria_estado_7(con, logger=logger))

    total = con.execute("SELECT COUNT(*) FROM auditoria_estado_7").fetchone()[0]
    total_anomalias = con.execute("""
        SELECT COUNT(*)
        FROM auditoria_estado_7
        WHERE RESULTADO_AUDITORIA LIKE 'ALERTA:%'
    """).fetchone()[0]

    nome_arquivo = f"Auditoria_ESTADO_7_IQS_{TIMESTAMP_ARQ}.CSV"
    caminho_csv = MARTS_DIR / nome_arquivo
    caminho_anomalias = MARTS_DIR / f"Auditoria_ESTADO_7_IQS_{TIMESTAMP_ARQ}_ANOMALIAS.CSV"
    caminho_anomalias_pendentes = MARTS_DIR / f"Auditoria_ESTADO_7_IQS_{TIMESTAMP_ARQ}_ANOMALIAS_PENDENTES.CSV"
    caminho_anomalias_aceitas = MARTS_DIR / f"Auditoria_ESTADO_7_IQS_{TIMESTAMP_ARQ}_ANOMALIAS_ACEITAS.CSV"
    caminho_resumo = MARTS_DIR / f"Auditoria_ESTADO_7_IQS_{TIMESTAMP_ARQ}_RESUMO.TXT"

    df_auditoria = con.execute("""
        SELECT *
        FROM auditoria_estado_7
        ORDER BY
            REGIONAL,
            NUM_OPER_CHV_INTRP,
            DATA_HORA_INIC_REGISTRO_7,
            NUM_SEQ_INTRP_REGISTRO_7
    """).fetchdf()

    exportar_csv_formatado(df_auditoria, caminho_csv)

    df_anomalias = con.execute("""
        SELECT *
        FROM auditoria_estado_7
        WHERE RESULTADO_AUDITORIA LIKE 'ALERTA:%'
        ORDER BY
            RESULTADO_AUDITORIA,
            REGIONAL,
            NUM_OPER_CHV_INTRP,
            DATA_HORA_INIC_REGISTRO_7,
            NUM_SEQ_INTRP_REGISTRO_7
    """).fetchdf()

    df_aceites = carregar_aceites_estado_7(logger)

    if df_anomalias.empty:
        df_anomalias["ANOMALIA_ACEITA"] = []
        df_anomalias_pendentes = df_anomalias.copy()
        df_anomalias_aceitas = df_anomalias.copy()
    else:
        df_anomalias["NUM_SEQ_INTRP_REGISTRO_7"] = (
            df_anomalias["NUM_SEQ_INTRP_REGISTRO_7"].map(normalizar_chave_texto)
        )
        df_anomalias["NUM_SEQ_INTRP_REGISTRO_MANTIDO"] = (
            df_anomalias["NUM_SEQ_INTRP_REGISTRO_MANTIDO"].map(normalizar_chave_texto)
        )

        colunas_chave = ["NUM_SEQ_INTRP_REGISTRO_7", "NUM_SEQ_INTRP_REGISTRO_MANTIDO"]
        df_aceites_merge = df_aceites.copy()
        colunas_renomear = {
            coluna: f"ACEITE_{coluna}"
            for coluna in df_aceites_merge.columns
            if coluna not in colunas_chave
        }
        df_aceites_merge = df_aceites_merge.rename(columns=colunas_renomear)
        df_aceites_merge["ANOMALIA_ACEITA"] = "SIM"

        df_anomalias = df_anomalias.merge(
            df_aceites_merge,
            how="left",
            on=colunas_chave,
        )
        df_anomalias["ANOMALIA_ACEITA"] = df_anomalias["ANOMALIA_ACEITA"].fillna("NAO")
        df_anomalias_pendentes = df_anomalias[df_anomalias["ANOMALIA_ACEITA"] != "SIM"].copy()
        df_anomalias_aceitas = df_anomalias[df_anomalias["ANOMALIA_ACEITA"] == "SIM"].copy()

    alertas_pendentes = len(df_anomalias_pendentes)
    alertas_aceitos = len(df_anomalias_aceitas)

    exportar_csv_formatado(df_anomalias, caminho_anomalias)
    exportar_csv_formatado(df_anomalias_pendentes, caminho_anomalias_pendentes)
    exportar_csv_formatado(df_anomalias_aceitas, caminho_anomalias_aceitas)
    exportar_resumo_auditoria(
        caminho_resumo,
        "Auditoria ESTADO_INTRP 7",
        total,
        alertas_pendentes,
        caminho_csv.as_posix(),
        caminho_anomalias_pendentes.as_posix(),
    )

    with caminho_resumo.open("a", encoding="utf-8") as resumo:
        resumo.write("\nAnomalias totais: " + f"{total_anomalias:,}" + "\n")
        resumo.write("Anomalias aceitas: " + f"{alertas_aceitos:,}" + "\n")
        resumo.write("Anomalias pendentes: " + f"{alertas_pendentes:,}" + "\n")
        resumo.write("Arquivo de aceite usado: " + ESTADO_7_ACEITAS_PATH.as_posix() + "\n")
        resumo.write("Arquivo com todas as anomalias: " + caminho_anomalias.as_posix() + "\n")
        resumo.write("Arquivo de anomalias aceitas: " + caminho_anomalias_aceitas.as_posix() + "\n")

    logger.info("Auditoria ESTADO 7 exportada: %s", caminho_csv)
    logger.info("Anomalias ESTADO 7 exportadas: %s", caminho_anomalias)
    logger.info("Anomalias pendentes ESTADO 7 exportadas: %s", caminho_anomalias_pendentes)
    logger.info("Anomalias aceitas ESTADO 7 exportadas: %s", caminho_anomalias_aceitas)
    logger.info("Resumo ESTADO 7 exportado: %s", caminho_resumo)
    logger.info("Pares auditados ESTADO 7: %s", f"{total:,}")
    logger.info("Anomalias ESTADO 7 totais: %s", f"{total_anomalias:,}")
    logger.info("Anomalias ESTADO 7 aceitas: %s", f"{alertas_aceitos:,}")
    logger.info("Anomalias ESTADO 7 pendentes: %s", f"{alertas_pendentes:,}")

    return {
        "path": caminho_csv.as_posix(),
        "anomalies_path": caminho_anomalias.as_posix(),
        "pending_anomalies_path": caminho_anomalias_pendentes.as_posix(),
        "accepted_anomalies_path": caminho_anomalias_aceitas.as_posix(),
        "summary_path": caminho_resumo.as_posix(),
        "rows": total,
        "total_anomalies": total_anomalias,
        "accepted_anomalies": alertas_aceitos,
        "alerts": alertas_pendentes,
        "acceptance_input_path": ESTADO_7_ACEITAS_PATH.as_posix(),
    }


def exportar_auditoria_uc_91_d(con, logger):
    logger.info("Gerando auditoria das UCs 91/D...")
    con.execute(SQL_AUDITORIA_UC_91_D)

    total = con.execute("SELECT COUNT(*) FROM auditoria_uc_91_d").fetchone()[0]
    alertas = con.execute("""
        SELECT COUNT(*)
        FROM auditoria_uc_91_d
        WHERE RESULTADO_AUDITORIA LIKE 'ALERTA:%'
    """).fetchone()[0]

    nome_arquivo = f"Auditoria_UC_91_D_IQS_{TIMESTAMP_ARQ}.CSV"
    caminho_csv = MARTS_DIR / nome_arquivo
    caminho_anomalias = MARTS_DIR / f"Auditoria_UC_91_D_IQS_{TIMESTAMP_ARQ}_ANOMALIAS.CSV"
    caminho_resumo = MARTS_DIR / f"Auditoria_UC_91_D_IQS_{TIMESTAMP_ARQ}_RESUMO.TXT"

    df_auditoria = con.execute("""
        SELECT *
        FROM auditoria_uc_91_d
        ORDER BY
            REGIONAL,
            NUM_UC_UCI,
            DTHR_INICIO_UC_91_D,
            NUM_SEQ_INTRP_UC_91_D
    """).fetchdf()

    exportar_csv_formatado(df_auditoria, caminho_csv)

    df_anomalias = con.execute("""
        SELECT *
        FROM auditoria_uc_91_d
        WHERE RESULTADO_AUDITORIA LIKE 'ALERTA:%'
        ORDER BY
            RESULTADO_AUDITORIA,
            REGIONAL,
            NUM_UC_UCI,
            DTHR_INICIO_UC_91_D,
            NUM_SEQ_INTRP_UC_91_D
    """).fetchdf()

    exportar_csv_formatado(df_anomalias, caminho_anomalias)
    exportar_resumo_auditoria(
        caminho_resumo,
        "Auditoria UC 91/D",
        total,
        alertas,
        caminho_csv.as_posix(),
        caminho_anomalias.as_posix(),
    )

    logger.info("Auditoria UC 91/D exportada: %s", caminho_csv)
    logger.info("Anomalias UC 91/D exportadas: %s", caminho_anomalias)
    logger.info("Resumo UC 91/D exportado: %s", caminho_resumo)
    logger.info("UCs auditadas 91/D: %s", f"{total:,}")
    logger.info("Alertas UC 91/D: %s", f"{alertas:,}")

    return {
        "path": caminho_csv.as_posix(),
        "anomalies_path": caminho_anomalias.as_posix(),
        "summary_path": caminho_resumo.as_posix(),
        "rows": total,
        "alerts": alertas,
    }


# ============================================================
# TRATAMENTO DUCKDB
# ============================================================

SQL_TRATAMENTO = """
DROP TABLE IF EXISTS adms_iqs_alterados;

CREATE TABLE adms_iqs_alterados AS
WITH base AS (
    SELECT
        CAST(PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) AS RAW_PID_OCOR_INTRP,
        CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS RAW_NUM_SEQ_INTRP,
        CAST(NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS RAW_NUM_UC_UCI,

        CAST(PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
        CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
        CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_INTRP_UCI,
        CAST(NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS NUM_UC_UCI,
        CAST(PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR) AS NUM_POSTO_UCI,

        'S' AS VALID_POS_OPERACAO,

        CAST(ESTADO_INTRP_ULT_HIADMS AS VARCHAR) AS ESTADO_INTRP_ORIG,
        CAST(ESTADO_INTRP_ULT_HIADMS AS VARCHAR) AS ESTADO_INTRP,

        CAST(TIPO_EQP_INTRP_PRIM_HIADMS AS VARCHAR) AS TIPO_EQP_INTRP,
        CAST(NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OPER_CHV_INTRP,

        DATA_HORA_INIC_INTRP_ULT_HIADMS AS DATA_HORA_INIC_INTRP,
        DATA_HORA_FIM_INTRP_ULT_HIADMS AS DATA_HORA_FIM_INTRP,
        DATA_HORA_INIC_INTRP_ULT_HIADMS AS DTHR_INICIO_INTRP_UC,

        CAST(COD_CAUSA_INTRP_ULT_HIADMS AS VARCHAR) AS COD_CAUSA_INTRP,
        CAST(COD_COMP_INTRP_ULT_HIADMS AS VARCHAR) AS COD_COMP_INTRP,
        CAST(COD_TIPO_INTRP_ULT_HIADMS AS VARCHAR) AS COD_TIPO_INTRP,

        CAST(NUM_MOTIVO_TRAT_DIF_UCI_ULT_HIADMS AS VARCHAR) AS NUM_MOTIVO_TRAT_DIF_UCI_ORIG,
        CAST(INDIC_SIT_PROCES_INDIC_UCI_ULT_HIADMS AS VARCHAR) AS INDIC_SIT_PROCES_INDIC_UCI_ORIG,
        CAST(NUM_INTRP_INIC_MANOBRA_UCI_ULT_HIADMS AS VARCHAR) AS NUM_INTRP_INIC_MANOBRA_UCI_ORIG,
        __NUM_INTRP_INIC_MANOBRA_HCAI_EXPR__ AS NUM_INTRP_INIC_MANOBRA_HCAI,

        CAST(TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR) AS TIPO_PROTOC_JUSTIF_UCI,

        __REGIONAL_EXPR__ AS REGIONAL,

        __SIGLA_REGIONAL_ORIG_EXPR__ AS SIGLA_REGIONAL_ORIG,

        DTHR_INC_REGIS_HIADMS,
        NOME_ARQ_ADMS_HIADMS,

        DATE_DIFF(
            'second',
            DATA_HORA_INIC_INTRP_ULT_HIADMS,
            DATA_HORA_FIM_INTRP_ULT_HIADMS
        ) / 60.0 AS DURACAO_MINUTOS_ORIG

    FROM raw_db.hiadms_raw
    WHERE DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS >= DATA_HORA_INIC_INTRP_ULT_HIADMS
      AND NULLIF(TRIM(CAST(COD_CAUSA_INTRP_ULT_HIADMS AS VARCHAR)), '') IS NOT NULL
      AND NULLIF(TRIM(CAST(COD_COMP_INTRP_ULT_HIADMS AS VARCHAR)), '') IS NOT NULL
),

/* ============================================================
   1. SOBREPOSIÇÃO TOTAL POR INTERRUPÇÃO / EQUIPAMENTO
   Popula:
     ESTADO_INTRP = 7
     NUM_MOTIVO_TRAT_DIF_UCI = 91
     INDIC_SIT_PROCES_INDIC_UCI = R
   ============================================================ */

interrupcoes_equipamento AS (
    SELECT DISTINCT
        NUM_SEQ_INTRP,
        NUM_INTRP_UCI,
        ESTADO_INTRP,
        TIPO_EQP_INTRP,
        NUM_OPER_CHV_INTRP,
        NUM_INTRP_INIC_MANOBRA_HCAI,
        DATA_HORA_INIC_INTRP,
        DATA_HORA_FIM_INTRP
    FROM base
    WHERE TRIM(ESTADO_INTRP) = '4'
      AND TRIM(TIPO_EQP_INTRP) = 'C'
      AND NULLIF(TRIM(NUM_OPER_CHV_INTRP), '') IS NOT NULL
),

sobreposicao_total_interrupcao AS (
    SELECT DISTINCT
        a.NUM_SEQ_INTRP
    FROM interrupcoes_equipamento a
    WHERE 1 = 0
      AND TRIM(a.ESTADO_INTRP) = '4'
      AND TRIM(a.TIPO_EQP_INTRP) = 'C'
      AND NULLIF(TRIM(a.NUM_OPER_CHV_INTRP), '') IS NOT NULL
      AND NULLIF(TRIM(a.NUM_INTRP_INIC_MANOBRA_HCAI), '') IS NULL
      AND EXISTS (
        SELECT 1
        FROM interrupcoes_equipamento b
        WHERE b.NUM_OPER_CHV_INTRP = a.NUM_OPER_CHV_INTRP
          AND b.NUM_SEQ_INTRP <> a.NUM_SEQ_INTRP
          AND b.DATA_HORA_INIC_INTRP <= a.DATA_HORA_INIC_INTRP
          AND b.DATA_HORA_FIM_INTRP  >= a.DATA_HORA_FIM_INTRP
          AND (
                b.DATA_HORA_INIC_INTRP < a.DATA_HORA_INIC_INTRP
             OR b.DATA_HORA_FIM_INTRP  > a.DATA_HORA_FIM_INTRP
             OR TRY_CAST(REGEXP_REPLACE(b.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
              < TRY_CAST(REGEXP_REPLACE(a.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
          )
      )
),

mapa_interrupcao_pai AS (
    SELECT
        CAST(NULL AS VARCHAR) AS NUM_SEQ_INTRP_FILHA_7,
        CAST(NULL AS VARCHAR) AS NUM_INTRP_UCI_FILHA_7,
        CAST(NULL AS VARCHAR) AS NUM_SEQ_INTRP_PAI,
        CAST(NULL AS VARCHAR) AS NUM_INTRP_UCI_PAI
    WHERE 1 = 0
),

apos_int AS (
    SELECT
        b.*,

        b.ESTADO_INTRP AS ESTADO_INTRP_TRAT,

        b.NUM_MOTIVO_TRAT_DIF_UCI_ORIG AS NUM_MOTIVO_TRAT_DIF_UCI_TRAT,

        b.INDIC_SIT_PROCES_INDIC_UCI_ORIG AS INDIC_SIT_PROCES_INDIC_UCI_TRAT,

        NULL AS ACAO_SOBREPOSICAO_INTERRUPCAO

    FROM base b
),

/* ============================================================
   2. SOBREPOSIÇÃO TOTAL POR UC
   Popula:
     NUM_MOTIVO_TRAT_DIF_UCI = 91
     INDIC_SIT_PROCES_INDIC_UCI = D
   ============================================================ */

uc_total AS (
    SELECT DISTINCT
        a.NUM_SEQ_INTRP,
        a.NUM_UC_UCI
    FROM apos_int a
    WHERE TRIM(a.ESTADO_INTRP_TRAT) = '4'
      AND NULLIF(TRIM(a.NUM_UC_UCI), '') IS NOT NULL
      AND NULLIF(TRIM(a.NUM_MOTIVO_TRAT_DIF_UCI_TRAT), '') IS NULL
      AND EXISTS (
        SELECT 1
        FROM apos_int b
        WHERE b.NUM_UC_UCI = a.NUM_UC_UCI
          AND TRIM(CAST(b.COD_TIPO_INTRP AS VARCHAR)) =
              TRIM(CAST(a.COD_TIPO_INTRP AS VARCHAR))
          AND TRIM(b.ESTADO_INTRP_TRAT) = '4'
          AND NULLIF(TRIM(b.NUM_MOTIVO_TRAT_DIF_UCI_TRAT), '') IS NULL
          AND COALESCE(TRIM(b.TIPO_PROTOC_JUSTIF_UCI), '#') =
              COALESCE(TRIM(a.TIPO_PROTOC_JUSTIF_UCI), '#')
          AND b.NUM_SEQ_INTRP <> a.NUM_SEQ_INTRP
          AND b.DTHR_INICIO_INTRP_UC <= a.DTHR_INICIO_INTRP_UC
          AND b.DATA_HORA_FIM_INTRP >= a.DATA_HORA_FIM_INTRP
          AND (
                b.DTHR_INICIO_INTRP_UC < a.DTHR_INICIO_INTRP_UC
             OR b.DATA_HORA_FIM_INTRP > a.DATA_HORA_FIM_INTRP
             OR TRY_CAST(REGEXP_REPLACE(b.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
              < TRY_CAST(REGEXP_REPLACE(a.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
          )
      )
),

apos_uc_total AS (
    SELECT
        b.*,

        CASE
            WHEN u.NUM_SEQ_INTRP IS NOT NULL THEN '91'
            ELSE b.NUM_MOTIVO_TRAT_DIF_UCI_TRAT
        END AS NUM_MOTIVO_TRAT_DIF_UCI_FINAL_TOTAL,

        CASE
            WHEN u.NUM_SEQ_INTRP IS NOT NULL THEN 'D'
            ELSE b.INDIC_SIT_PROCES_INDIC_UCI_TRAT
        END AS INDIC_SIT_PROCES_INDIC_UCI_FINAL_TOTAL,

        CASE
            WHEN u.NUM_SEQ_INTRP IS NOT NULL
            THEN 'CLASSIFICAR_91_UC_CONTIDA'
        END AS ACAO_SOBREPOSICAO_TOTAL_UC

    FROM apos_int b
    LEFT JOIN uc_total u
      ON u.NUM_SEQ_INTRP = b.NUM_SEQ_INTRP
     AND u.NUM_UC_UCI = b.NUM_UC_UCI
),

/* ============================================================
   3. SOBREPOSIÇÃO PARCIAL POR UC
   Segundo registro:
     DTHR_INICIO_INTRP_UC = fim da anterior
     NUM_INTRP_INIC_MANOBRA_UCI = NUM_INTRP_UCI
   ============================================================ */

uc_parcial AS (
    SELECT
        a.NUM_SEQ_INTRP,
        a.NUM_INTRP_UCI,
        a.NUM_UC_UCI,
        MAX(b.DATA_HORA_FIM_INTRP) AS DTHR_INICIO_INTRP_UC_AJUSTADO,
        ARG_MAX(b.NUM_INTRP_UCI, b.DATA_HORA_FIM_INTRP) AS NUM_INTRP_INIC_MANOBRA_UCI_AJUSTADO
    FROM apos_uc_total a
    JOIN apos_uc_total b
      ON b.NUM_UC_UCI = a.NUM_UC_UCI
     AND TRIM(CAST(b.COD_TIPO_INTRP AS VARCHAR)) =
         TRIM(CAST(a.COD_TIPO_INTRP AS VARCHAR))
     AND TRIM(b.ESTADO_INTRP_TRAT) = '4'
     AND NULLIF(TRIM(b.NUM_MOTIVO_TRAT_DIF_UCI_FINAL_TOTAL), '') IS NULL
     AND COALESCE(TRIM(b.TIPO_PROTOC_JUSTIF_UCI), '#') =
         COALESCE(TRIM(a.TIPO_PROTOC_JUSTIF_UCI), '#')
     AND b.NUM_SEQ_INTRP <> a.NUM_SEQ_INTRP
     AND b.DTHR_INICIO_INTRP_UC < a.DTHR_INICIO_INTRP_UC
     AND b.DATA_HORA_FIM_INTRP > a.DTHR_INICIO_INTRP_UC
     AND b.DATA_HORA_FIM_INTRP < a.DATA_HORA_FIM_INTRP
    WHERE TRIM(a.ESTADO_INTRP_TRAT) = '4'
      AND NULLIF(TRIM(a.NUM_MOTIVO_TRAT_DIF_UCI_FINAL_TOTAL), '') IS NULL
    GROUP BY
        a.NUM_SEQ_INTRP,
        a.NUM_INTRP_UCI,
        a.NUM_UC_UCI
),

tratado AS (
    SELECT
        b.RAW_PID_OCOR_INTRP,
        b.RAW_NUM_SEQ_INTRP,
        b.RAW_NUM_UC_UCI,

        b.NUM_OCORRENCIA_ADMS,
        b.NUM_SEQ_INTRP,
        b.NUM_INTRP_UCI,
        b.NUM_UC_UCI,
        b.NUM_POSTO_UCI,

        b.VALID_POS_OPERACAO,

        b.ESTADO_INTRP_ORIG,
        b.ESTADO_INTRP_TRAT AS ESTADO_INTRP,

        b.TIPO_EQP_INTRP,
        b.NUM_OPER_CHV_INTRP,

        b.DATA_HORA_INIC_INTRP,
        b.DATA_HORA_FIM_INTRP,

        b.DTHR_INICIO_INTRP_UC AS DTHR_INICIO_INTRP_UC_ORIG,

        COALESCE(
            p.DTHR_INICIO_INTRP_UC_AJUSTADO,
            b.DTHR_INICIO_INTRP_UC
        ) AS DTHR_INICIO_INTRP_UC,

        b.COD_CAUSA_INTRP,
        b.COD_COMP_INTRP,

        b.NUM_MOTIVO_TRAT_DIF_UCI_ORIG,
        b.NUM_MOTIVO_TRAT_DIF_UCI_FINAL_TOTAL AS NUM_MOTIVO_TRAT_DIF_UCI,

        b.INDIC_SIT_PROCES_INDIC_UCI_ORIG,
        b.INDIC_SIT_PROCES_INDIC_UCI_FINAL_TOTAL AS INDIC_SIT_PROCES_INDIC_UCI,

        b.NUM_INTRP_INIC_MANOBRA_UCI_ORIG,
        b.NUM_INTRP_INIC_MANOBRA_HCAI,

        COALESCE(
            p.NUM_INTRP_INIC_MANOBRA_UCI_AJUSTADO,
            NULLIF(TRIM(b.NUM_INTRP_INIC_MANOBRA_HCAI), ''),
            b.NUM_INTRP_INIC_MANOBRA_UCI_ORIG
        ) AS NUM_INTRP_INIC_MANOBRA_UCI,

        b.TIPO_PROTOC_JUSTIF_UCI,
        b.REGIONAL,
        b.SIGLA_REGIONAL_ORIG,

        b.DURACAO_MINUTOS_ORIG,

        CASE
            WHEN p.DTHR_INICIO_INTRP_UC_AJUSTADO IS NOT NULL
            THEN DATE_DIFF(
                'second',
                p.DTHR_INICIO_INTRP_UC_AJUSTADO,
                b.DATA_HORA_FIM_INTRP
            ) / 60.0
        END AS DURACAO_MINUTOS_AJUSTADA,

        p.DTHR_INICIO_INTRP_UC_AJUSTADO,
        p.NUM_INTRP_INIC_MANOBRA_UCI_AJUSTADO,

        b.ACAO_SOBREPOSICAO_INTERRUPCAO,
        b.ACAO_SOBREPOSICAO_TOTAL_UC,

        CASE
            WHEN p.NUM_SEQ_INTRP IS NOT NULL
            THEN 'AJUSTAR_SOBREPOSICAO_PARCIAL_UC'
        END AS ACAO_AJUSTE_PARCIAL,

        b.DTHR_INC_REGIS_HIADMS,
        b.NOME_ARQ_ADMS_HIADMS

    FROM apos_uc_total b
    LEFT JOIN uc_parcial p
      ON p.NUM_SEQ_INTRP = b.NUM_SEQ_INTRP
     AND p.NUM_UC_UCI = b.NUM_UC_UCI
),

tratado_redirecionado AS (
    SELECT
        t.* REPLACE (
            CASE
                WHEN m_manobra.NUM_INTRP_UCI_PAI IS NOT NULL
                THEN m_manobra.NUM_INTRP_UCI_PAI
                WHEN NULLIF(TRIM(CAST(t.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                THEN NULL
                WHEN TRIM(CAST(t.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) IN ('0', '0.0')
                THEN NULL
                WHEN TRIM(CAST(t.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) = TRIM(CAST(t.NUM_INTRP_UCI AS VARCHAR))
                THEN NULL
                WHEN TRIM(CAST(t.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) = TRIM(CAST(t.NUM_SEQ_INTRP AS VARCHAR))
                THEN NULL
                ELSE t.NUM_INTRP_INIC_MANOBRA_UCI
            END AS NUM_INTRP_INIC_MANOBRA_UCI
        ),

        t.NUM_INTRP_INIC_MANOBRA_UCI AS NUM_INTRP_INIC_MANOBRA_UCI_ANTES_REDIREC,
        m_manobra.NUM_INTRP_UCI_FILHA_7 AS NUM_INTRP_MANOBRA_FILHA_7_REDIREC,
        m_manobra.NUM_INTRP_UCI_PAI AS NUM_INTRP_MANOBRA_PAI_REDIREC,

        CASE
            WHEN m_manobra.NUM_INTRP_UCI_FILHA_7 IS NOT NULL
            THEN 'REDIRECIONAR_MANOBRA_ESTADO_7'
        END AS ACAO_REDIREC_MANOBRA_ESTADO_7

    FROM tratado t
    LEFT JOIN mapa_interrupcao_pai m_manobra
      ON NULLIF(TRIM(CAST(m_manobra.NUM_INTRP_UCI_FILHA_7 AS VARCHAR)), '') =
         NULLIF(TRIM(CAST(t.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '')
)

SELECT *
FROM tratado_redirecionado
WHERE ACAO_SOBREPOSICAO_INTERRUPCAO IS NOT NULL
   OR ACAO_SOBREPOSICAO_TOTAL_UC IS NOT NULL
   OR ACAO_AJUSTE_PARCIAL IS NOT NULL
   OR ACAO_REDIREC_MANOBRA_ESTADO_7 IS NOT NULL
;
"""


SQL_AUDITORIA_ESTADO_7 = """
DROP TABLE IF EXISTS auditoria_estado_7;

CREATE TABLE auditoria_estado_7 AS
WITH base_interrupcao AS (
    SELECT
        CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
        ANY_VALUE(CAST(PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
        ANY_VALUE(CAST(NUM_UC_UCI_CHVP_HIADMS AS VARCHAR)) AS NUM_UC_UCI_EXEMPLO,
        ANY_VALUE(CAST(PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR)) AS NUM_POSTO_UCI,
        ANY_VALUE(CAST(ESTADO_INTRP_ULT_HIADMS AS VARCHAR)) AS ESTADO_INTRP_ORIG,
        ANY_VALUE(CAST(TIPO_EQP_INTRP_PRIM_HIADMS AS VARCHAR)) AS TIPO_EQP_INTRP,
        CAST(NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OPER_CHV_INTRP,
        MIN(DATA_HORA_INIC_INTRP_ULT_HIADMS) AS DATA_HORA_INIC_INTRP,
        MAX(DATA_HORA_FIM_INTRP_ULT_HIADMS) AS DATA_HORA_FIM_INTRP,
        ANY_VALUE(__REGIONAL_EXPR__) AS REGIONAL,
        ANY_VALUE(__SIGLA_REGIONAL_ORIG_EXPR__) AS SIGLA_REGIONAL_ORIG,
        COUNT(*) AS QTD_UCS_INTERRUPCAO
    FROM raw_db.hiadms_raw
    WHERE DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS >= DATA_HORA_INIC_INTRP_ULT_HIADMS
      AND NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR)), '') IS NOT NULL
    GROUP BY
        CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR),
        CAST(NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR)
),

alterados_seq AS (
    SELECT
        NUM_SEQ_INTRP,
        COUNT(*) AS QTD_REGISTROS_EXPORTADOS_COM_ACAO,
        MAX(CASE WHEN ESTADO_INTRP = '7' THEN 1 ELSE 0 END) AS TEM_ESTADO_7
    FROM adms_iqs_alterados
    GROUP BY NUM_SEQ_INTRP
),

registros_7 AS (
    SELECT
        NUM_SEQ_INTRP,
        ANY_VALUE(REGIONAL) AS REGIONAL,
        ANY_VALUE(SIGLA_REGIONAL_ORIG) AS SIGLA_REGIONAL_ORIG,
        ANY_VALUE(NUM_OPER_CHV_INTRP) AS NUM_OPER_CHV_INTRP,
        ANY_VALUE(NUM_OCORRENCIA_ADMS) AS NUM_OCORRENCIA_ADMS,
        ANY_VALUE(NUM_UC_UCI) AS NUM_UC_UCI_EXEMPLO,
        ANY_VALUE(NUM_POSTO_UCI) AS NUM_POSTO_UCI,
        ANY_VALUE(ESTADO_INTRP_ORIG) AS ESTADO_INTRP_ORIG,
        ANY_VALUE(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
        ANY_VALUE(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
        COUNT(*) AS QTD_UCS_EXPORTADAS
    FROM adms_iqs_alterados
    WHERE ESTADO_INTRP = '7'
       OR ACAO_SOBREPOSICAO_INTERRUPCAO IS NOT NULL
    GROUP BY NUM_SEQ_INTRP
),

candidatos AS (
    SELECT
        a.REGIONAL,
        a.SIGLA_REGIONAL_ORIG,
        a.NUM_OPER_CHV_INTRP,

        a.NUM_OCORRENCIA_ADMS AS NUM_OCORRENCIA_ADMS_REGISTRO_7,
        a.NUM_SEQ_INTRP AS NUM_SEQ_INTRP_REGISTRO_7,
        a.NUM_UC_UCI_EXEMPLO AS NUM_UC_UCI_EXEMPLO_REGISTRO_7,
        a.NUM_POSTO_UCI AS NUM_POSTO_UCI_REGISTRO_7,
        a.ESTADO_INTRP_ORIG AS ESTADO_INTRP_ORIG_REGISTRO_7,
        '7' AS ESTADO_INTRP_TRAT_REGISTRO_7,
        a.DATA_HORA_INIC_INTRP AS DATA_HORA_INIC_REGISTRO_7,
        a.DATA_HORA_FIM_INTRP AS DATA_HORA_FIM_REGISTRO_7,
        a.QTD_UCS_EXPORTADAS AS QTD_UCS_EXPORTADAS_REGISTRO_7,

        b.NUM_OCORRENCIA_ADMS AS NUM_OCORRENCIA_ADMS_REGISTRO_MANTIDO,
        b.NUM_SEQ_INTRP AS NUM_SEQ_INTRP_REGISTRO_MANTIDO,
        b.NUM_UC_UCI_EXEMPLO AS NUM_UC_UCI_EXEMPLO_REGISTRO_MANTIDO,
        b.NUM_POSTO_UCI AS NUM_POSTO_UCI_REGISTRO_MANTIDO,
        b.ESTADO_INTRP_ORIG AS ESTADO_INTRP_ORIG_REGISTRO_MANTIDO,
        b.DATA_HORA_INIC_INTRP AS DATA_HORA_INIC_REGISTRO_MANTIDO,
        b.DATA_HORA_FIM_INTRP AS DATA_HORA_FIM_REGISTRO_MANTIDO,
        b.QTD_UCS_INTERRUPCAO AS QTD_UCS_RAW_REGISTRO_MANTIDO,

        CASE
            WHEN t.NUM_SEQ_INTRP IS NOT NULL THEN 'SIM'
            ELSE 'NAO'
        END AS REGISTRO_MANTIDO_TAMBEM_EXPORTADO_COM_ACAO,

        CASE
            WHEN t.TEM_ESTADO_7 = 1 THEN 'SIM'
            ELSE 'NAO'
        END AS REGISTRO_MANTIDO_TAMBEM_ESTADO_7,

        DATE_DIFF('second', a.DATA_HORA_INIC_INTRP, a.DATA_HORA_FIM_INTRP) / 60.0 AS DURACAO_MIN_REGISTRO_7,
        DATE_DIFF('second', b.DATA_HORA_INIC_INTRP, b.DATA_HORA_FIM_INTRP) / 60.0 AS DURACAO_MIN_REGISTRO_MANTIDO,

        ROW_NUMBER() OVER (
            PARTITION BY a.NUM_SEQ_INTRP
            ORDER BY
                DATE_DIFF('second', b.DATA_HORA_INIC_INTRP, b.DATA_HORA_FIM_INTRP) DESC,
                TRY_CAST(REGEXP_REPLACE(b.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT),
                b.NUM_SEQ_INTRP
        ) AS RN_JUSTIFICATIVA
    FROM registros_7 a
    LEFT JOIN base_interrupcao b
      ON b.NUM_OPER_CHV_INTRP = a.NUM_OPER_CHV_INTRP
     AND b.NUM_SEQ_INTRP <> a.NUM_SEQ_INTRP
     AND b.DATA_HORA_INIC_INTRP <= a.DATA_HORA_INIC_INTRP
     AND b.DATA_HORA_FIM_INTRP >= a.DATA_HORA_FIM_INTRP
     AND (
            b.DATA_HORA_INIC_INTRP < a.DATA_HORA_INIC_INTRP
         OR b.DATA_HORA_FIM_INTRP > a.DATA_HORA_FIM_INTRP
         OR TRY_CAST(REGEXP_REPLACE(b.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
          < TRY_CAST(REGEXP_REPLACE(a.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
      )
    LEFT JOIN alterados_seq t
      ON t.NUM_SEQ_INTRP = b.NUM_SEQ_INTRP
)

SELECT
    REGIONAL,
    SIGLA_REGIONAL_ORIG,
    NUM_OPER_CHV_INTRP,
    NUM_OCORRENCIA_ADMS_REGISTRO_7,
    NUM_SEQ_INTRP_REGISTRO_7,
    NUM_UC_UCI_EXEMPLO_REGISTRO_7,
    NUM_POSTO_UCI_REGISTRO_7,
    ESTADO_INTRP_ORIG_REGISTRO_7,
    ESTADO_INTRP_TRAT_REGISTRO_7,
    DATA_HORA_INIC_REGISTRO_7,
    DATA_HORA_FIM_REGISTRO_7,
    DURACAO_MIN_REGISTRO_7,
    QTD_UCS_EXPORTADAS_REGISTRO_7,
    NUM_OCORRENCIA_ADMS_REGISTRO_MANTIDO,
    NUM_SEQ_INTRP_REGISTRO_MANTIDO,
    NUM_UC_UCI_EXEMPLO_REGISTRO_MANTIDO,
    NUM_POSTO_UCI_REGISTRO_MANTIDO,
    ESTADO_INTRP_ORIG_REGISTRO_MANTIDO,
    DATA_HORA_INIC_REGISTRO_MANTIDO,
    DATA_HORA_FIM_REGISTRO_MANTIDO,
    DURACAO_MIN_REGISTRO_MANTIDO,
    QTD_UCS_RAW_REGISTRO_MANTIDO,
    REGISTRO_MANTIDO_TAMBEM_EXPORTADO_COM_ACAO,
    REGISTRO_MANTIDO_TAMBEM_ESTADO_7,
    CASE
        WHEN NUM_SEQ_INTRP_REGISTRO_MANTIDO IS NULL
        THEN 'ALERTA: REGISTRO 7 SEM INTERRUPCAO 4 MANTIDA COBRINDO O PERIODO'
        WHEN ESTADO_INTRP_ORIG_REGISTRO_MANTIDO <> '4'
        THEN 'ALERTA: REGISTRO MANTIDO NAO ESTA COM ESTADO 4'
        WHEN REGISTRO_MANTIDO_TAMBEM_ESTADO_7 = 'SIM'
        THEN 'ALERTA: REGISTRO MANTIDO TAMBEM FOI MARCADO COMO 7'
        ELSE 'OK: SOMENTE O REGISTRO CONTIDO FOI MARCADO COMO 7'
    END AS RESULTADO_AUDITORIA
FROM candidatos
WHERE RN_JUSTIFICATIVA = 1
;
"""


SQL_AUDITORIA_UC_91_D = """
DROP TABLE IF EXISTS auditoria_uc_91_d;

CREATE TABLE auditoria_uc_91_d AS
WITH candidatos_91d AS (
    SELECT
        NUM_SEQ_INTRP,
        NUM_INTRP_UCI,
        NUM_UC_UCI,
        TIPO_PROTOC_JUSTIF_UCI,
        NUM_OCORRENCIA_ADMS,
        NUM_POSTO_UCI,
        ESTADO_INTRP,
        NUM_MOTIVO_TRAT_DIF_UCI,
        INDIC_SIT_PROCES_INDIC_UCI,
        DATA_HORA_INIC_INTRP,
        DATA_HORA_FIM_INTRP,
        DTHR_INICIO_INTRP_UC,
        REGIONAL,
        SIGLA_REGIONAL_ORIG
    FROM adms_iqs_alterados
    WHERE (
            NUM_MOTIVO_TRAT_DIF_UCI = '91'
        AND INDIC_SIT_PROCES_INDIC_UCI = 'D'
    )
       OR ACAO_SOBREPOSICAO_TOTAL_UC IS NOT NULL
),

ucs_candidatas AS (
    SELECT DISTINCT
        NUM_UC_UCI,
        COALESCE(TRIM(TIPO_PROTOC_JUSTIF_UCI), '#') AS TIPO_PROTOC_JUSTIF_UCI_NORMALIZADO
    FROM candidatos_91d
),

base_uc AS (
    SELECT
        CAST(h.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
        CAST(h.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS NUM_UC_UCI,
        COALESCE(TRIM(CAST(h.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR)), '#') AS TIPO_PROTOC_JUSTIF_UCI_NORMALIZADO,
        ANY_VALUE(CAST(h.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
        ANY_VALUE(CAST(h.PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR)) AS NUM_POSTO_UCI,
        ANY_VALUE(CAST(h.ESTADO_INTRP_ULT_HIADMS AS VARCHAR)) AS ESTADO_INTRP_ORIG,
        ANY_VALUE(CAST(h.TIPO_EQP_INTRP_PRIM_HIADMS AS VARCHAR)) AS TIPO_EQP_INTRP,
        ANY_VALUE(CAST(h.NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR)) AS NUM_OPER_CHV_INTRP,
        MIN(h.DATA_HORA_INIC_INTRP_ULT_HIADMS) AS DTHR_INICIO_INTRP_UC,
        MAX(h.DATA_HORA_FIM_INTRP_ULT_HIADMS) AS DATA_HORA_FIM_INTRP
    FROM raw_db.hiadms_raw h
    JOIN ucs_candidatas c
      ON c.NUM_UC_UCI = CAST(h.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR)
     AND c.TIPO_PROTOC_JUSTIF_UCI_NORMALIZADO =
         COALESCE(TRIM(CAST(h.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR)), '#')
    WHERE h.DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
      AND h.DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
      AND h.DATA_HORA_FIM_INTRP_ULT_HIADMS >= h.DATA_HORA_INIC_INTRP_ULT_HIADMS
    GROUP BY
        CAST(h.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR),
        CAST(h.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR),
        COALESCE(TRIM(CAST(h.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR)), '#')
),

alterados_seq AS (
    SELECT
        NUM_SEQ_INTRP,
        MAX(CASE WHEN ESTADO_INTRP = '7' THEN 1 ELSE 0 END) AS TEM_ESTADO_7
    FROM adms_iqs_alterados
    GROUP BY NUM_SEQ_INTRP
),

alterados_uc AS (
    SELECT
        NUM_SEQ_INTRP,
        NUM_UC_UCI,
        MAX(
            CASE
                WHEN NUM_MOTIVO_TRAT_DIF_UCI = '91'
                 AND INDIC_SIT_PROCES_INDIC_UCI = 'D'
                THEN 1
                ELSE 0
            END
        ) AS TEM_91_D
    FROM adms_iqs_alterados
    GROUP BY
        NUM_SEQ_INTRP,
        NUM_UC_UCI
),

pares AS (
    SELECT
        a.REGIONAL,
        a.SIGLA_REGIONAL_ORIG,
        a.NUM_UC_UCI,
        a.TIPO_PROTOC_JUSTIF_UCI,

        a.NUM_OCORRENCIA_ADMS AS NUM_OCORRENCIA_ADMS_UC_91_D,
        a.NUM_SEQ_INTRP AS NUM_SEQ_INTRP_UC_91_D,
        a.NUM_INTRP_UCI AS NUM_INTRP_UCI_91_D,
        a.NUM_POSTO_UCI AS NUM_POSTO_UCI_91_D,
        a.ESTADO_INTRP AS ESTADO_INTRP_UC_91_D,
        a.NUM_MOTIVO_TRAT_DIF_UCI,
        a.INDIC_SIT_PROCES_INDIC_UCI,
        a.DTHR_INICIO_INTRP_UC AS DTHR_INICIO_UC_91_D,
        a.DATA_HORA_FIM_INTRP AS DATA_HORA_FIM_UC_91_D,

        b.NUM_OCORRENCIA_ADMS AS NUM_OCORRENCIA_ADMS_UC_MANTIDA,
        b.NUM_SEQ_INTRP AS NUM_SEQ_INTRP_UC_MANTIDA,
        b.NUM_POSTO_UCI AS NUM_POSTO_UCI_MANTIDA,
        b.ESTADO_INTRP_ORIG AS ESTADO_INTRP_ORIG_UC_MANTIDA,
        b.TIPO_EQP_INTRP AS TIPO_EQP_UC_MANTIDA,
        b.NUM_OPER_CHV_INTRP AS NUM_OPER_CHV_UC_MANTIDA,
        b.DTHR_INICIO_INTRP_UC AS DTHR_INICIO_UC_MANTIDA,
        b.DATA_HORA_FIM_INTRP AS DATA_HORA_FIM_UC_MANTIDA,

        CASE WHEN seq.TEM_ESTADO_7 = 1 THEN 'SIM' ELSE 'NAO' END AS UC_MANTIDA_INTERRUPCAO_ESTADO_7,
        CASE WHEN uc.TEM_91_D = 1 THEN 'SIM' ELSE 'NAO' END AS UC_MANTIDA_TAMBEM_91_D,

        ROW_NUMBER() OVER (
            PARTITION BY a.NUM_SEQ_INTRP, a.NUM_UC_UCI
            ORDER BY
                CASE
                    WHEN b.NUM_SEQ_INTRP IS NOT NULL
                     AND COALESCE(seq.TEM_ESTADO_7, 0) = 0
                     AND COALESCE(uc.TEM_91_D, 0) = 0
                    THEN 0
                    ELSE 1
                END,
                DATE_DIFF('second', b.DTHR_INICIO_INTRP_UC, b.DATA_HORA_FIM_INTRP) DESC NULLS LAST,
                TRY_CAST(REGEXP_REPLACE(b.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT) NULLS LAST,
                b.NUM_SEQ_INTRP NULLS LAST
        ) AS RN_JUSTIFICATIVA
    FROM candidatos_91d a
    LEFT JOIN base_uc b
      ON b.NUM_UC_UCI = a.NUM_UC_UCI
     AND b.TIPO_PROTOC_JUSTIF_UCI_NORMALIZADO =
         COALESCE(TRIM(a.TIPO_PROTOC_JUSTIF_UCI), '#')
     AND b.NUM_SEQ_INTRP <> a.NUM_SEQ_INTRP
     AND b.DTHR_INICIO_INTRP_UC <= a.DTHR_INICIO_INTRP_UC
     AND b.DATA_HORA_FIM_INTRP >= a.DATA_HORA_FIM_INTRP
     AND (
            b.DTHR_INICIO_INTRP_UC < a.DTHR_INICIO_INTRP_UC
         OR b.DATA_HORA_FIM_INTRP > a.DATA_HORA_FIM_INTRP
         OR TRY_CAST(REGEXP_REPLACE(b.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
          < TRY_CAST(REGEXP_REPLACE(a.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
      )
    LEFT JOIN alterados_seq seq
      ON seq.NUM_SEQ_INTRP = b.NUM_SEQ_INTRP
    LEFT JOIN alterados_uc uc
      ON uc.NUM_SEQ_INTRP = b.NUM_SEQ_INTRP
     AND uc.NUM_UC_UCI = b.NUM_UC_UCI
)

SELECT
    *,
    CASE
        WHEN NUM_SEQ_INTRP_UC_MANTIDA IS NULL
        THEN 'ALERTA: UC 91/D SEM REGISTRO MANTIDO'
        WHEN UC_MANTIDA_INTERRUPCAO_ESTADO_7 = 'SIM'
        THEN 'ALERTA: UC MANTIDA ESTA EM INTERRUPCAO ESTADO 7'
        WHEN UC_MANTIDA_TAMBEM_91_D = 'SIM'
        THEN 'ALERTA: UC MANTIDA TAMBEM FOI MARCADA COMO 91/D'
        WHEN ESTADO_INTRP_UC_91_D <> '4'
        THEN 'ALERTA: UC 91/D NAO PERMANECEU COM ESTADO_INTRP 4'
        ELSE 'OK: UC CONTIDA MARCADA COMO 91/D E INTERRUPCAO PERMANECE 4'
    END AS RESULTADO_AUDITORIA
FROM pares
WHERE RN_JUSTIFICATIVA = 1
;
"""


SQL_AUDITORIA_OUTLIERS_BRUTO = """
DROP TABLE IF EXISTS auditoria_outliers_bruto;

CREATE TABLE auditoria_outliers_bruto AS
WITH base_interrupcao AS (
    SELECT
        CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
        ANY_VALUE(CAST(PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
        MIN(DATA_HORA_INIC_INTRP_ULT_HIADMS) AS DATA_HORA_INIC_INTRP,
        MAX(DATA_HORA_FIM_INTRP_ULT_HIADMS) AS DATA_HORA_FIM_INTRP,
        ANY_VALUE(CAST(COD_CAUSA_INTRP_ULT_HIADMS AS VARCHAR)) AS COD_CAUSA_INTRP,
        ANY_VALUE(CAST(COD_COMP_INTRP_ULT_HIADMS AS VARCHAR)) AS COD_COMP_INTRP,
        ANY_VALUE(__COD_TIPO_INTRP_EXPR__) AS COD_TIPO_INTRP,
        ANY_VALUE(__TIPO_PROTOC_JUSTIF_UCI_EXPR__) AS TIPO_PROTOC_JUSTIF_UCI,
        ANY_VALUE(__NUM_PROTOC_JUSTIF_RESP_UCI_EXPR__) AS NUM_PROTOC_JUSTIF_RESP_UCI,
        ANY_VALUE(CAST(NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR)) AS NUM_OPER_CHV_INTRP,
        COUNT(*) AS QTD_UCS,
        DATE_DIFF(
            'second',
            MIN(DATA_HORA_INIC_INTRP_ULT_HIADMS),
            MAX(DATA_HORA_FIM_INTRP_ULT_HIADMS)
        ) / 3600.0 AS DURACAO_HORAS
    FROM raw_db.hiadms_raw
    WHERE DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS >= DATA_HORA_INIC_INTRP_ULT_HIADMS
    GROUP BY CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR)
),

sobreposicoes AS (
    SELECT
        b.NUM_SEQ_INTRP,
        COUNT(a.NUM_SEQ_INTRP) AS QTD_INTRP_CONTIDAS,
        COALESCE(SUM(a.QTD_UCS), 0) AS QTD_UCS_AFETADAS
    FROM base_interrupcao b
    LEFT JOIN base_interrupcao a
      ON a.NUM_OPER_CHV_INTRP = b.NUM_OPER_CHV_INTRP
     AND a.NUM_SEQ_INTRP <> b.NUM_SEQ_INTRP
     AND NULLIF(TRIM(b.NUM_OPER_CHV_INTRP), '') IS NOT NULL
     AND a.DATA_HORA_INIC_INTRP >= b.DATA_HORA_INIC_INTRP
     AND a.DATA_HORA_FIM_INTRP <= b.DATA_HORA_FIM_INTRP
     AND (
            a.DATA_HORA_INIC_INTRP > b.DATA_HORA_INIC_INTRP
         OR a.DATA_HORA_FIM_INTRP < b.DATA_HORA_FIM_INTRP
         OR TRY_CAST(REGEXP_REPLACE(a.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
          > TRY_CAST(REGEXP_REPLACE(b.NUM_SEQ_INTRP, '[^0-9]', '', 'g') AS BIGINT)
      )
    GROUP BY b.NUM_SEQ_INTRP
),

classificados AS (
    SELECT
        b.NUM_OCORRENCIA_ADMS,
        b.NUM_SEQ_INTRP,
        b.DATA_HORA_INIC_INTRP,
        b.DATA_HORA_FIM_INTRP,
        b.COD_CAUSA_INTRP,
        b.COD_COMP_INTRP,
        b.COD_TIPO_INTRP,
        b.TIPO_PROTOC_JUSTIF_UCI,
        b.NUM_PROTOC_JUSTIF_RESP_UCI,
        b.QTD_UCS,
        b.DURACAO_HORAS,
        s.QTD_INTRP_CONTIDAS,
        s.QTD_UCS_AFETADAS
    FROM base_interrupcao b
    JOIN sobreposicoes s
      ON s.NUM_SEQ_INTRP = b.NUM_SEQ_INTRP
    WHERE b.DURACAO_HORAS >= __OUTLIER_DURACAO_HORAS__
       OR b.QTD_UCS >= __OUTLIER_QTD_UCS__
       OR s.QTD_INTRP_CONTIDAS >= __OUTLIER_QTD_INTRP_CONTIDAS__
       OR s.QTD_UCS_AFETADAS >= __OUTLIER_QTD_UCS_AFETADAS__
)

SELECT *
FROM classificados
;
"""


SQL_AUDITORIA_MANOBRA_HCAI = """
DROP TABLE IF EXISTS auditoria_manobra_hcai;

CREATE TABLE auditoria_manobra_hcai AS
WITH base_interrupcao AS (
    SELECT
        CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
        ANY_VALUE(CAST(PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
        ANY_VALUE(__NUM_INTRP_INIC_MANOBRA_HCAI_EXPR__) AS NUM_INTRP_INIC_MANOBRA_HCAI,
        ANY_VALUE(CAST(NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR)) AS NUM_OPER_CHV_INTRP,
        MIN(DATA_HORA_INIC_INTRP_ULT_HIADMS) AS DATA_HORA_INIC_INTRP,
        MAX(DATA_HORA_FIM_INTRP_ULT_HIADMS) AS DATA_HORA_FIM_INTRP,
        ANY_VALUE(CAST(ESTADO_INTRP_ULT_HIADMS AS VARCHAR)) AS ESTADO_INTRP_ORIG,
        COUNT(*) AS QTD_UCS
    FROM raw_db.hiadms_raw
    WHERE DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
      AND DATA_HORA_FIM_INTRP_ULT_HIADMS >= DATA_HORA_INIC_INTRP_ULT_HIADMS
    GROUP BY CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR)
),

manobras AS (
    SELECT *
    FROM base_interrupcao
    WHERE NULLIF(TRIM(NUM_INTRP_INIC_MANOBRA_HCAI), '') IS NOT NULL
),

tratamento_estado_7 AS (
    SELECT DISTINCT NUM_SEQ_INTRP
    FROM adms_iqs_alterados
    WHERE ESTADO_INTRP = '7'
),

pares AS (
    SELECT
        m.NUM_OCORRENCIA_ADMS,
        m.NUM_SEQ_INTRP,
        m.NUM_INTRP_INIC_MANOBRA_HCAI,
        m.NUM_OPER_CHV_INTRP,
        m.DATA_HORA_INIC_INTRP,
        m.DATA_HORA_FIM_INTRP,
        m.ESTADO_INTRP_ORIG,
        m.QTD_UCS,

        p.NUM_SEQ_INTRP AS NUM_SEQ_INTRP_PAI,
        p.NUM_OCORRENCIA_ADMS AS NUM_OCORRENCIA_ADMS_PAI,
        p.DATA_HORA_INIC_INTRP AS DATA_HORA_INIC_INTRP_PAI,
        p.DATA_HORA_FIM_INTRP AS DATA_HORA_FIM_INTRP_PAI,

        CASE WHEN p.NUM_SEQ_INTRP IS NOT NULL THEN 'SIM' ELSE 'NAO' END AS PAI_EXISTE,
        CASE
            WHEN p.NUM_SEQ_INTRP IS NOT NULL
             AND p.DATA_HORA_INIC_INTRP <= m.DATA_HORA_INIC_INTRP
             AND p.DATA_HORA_FIM_INTRP >= m.DATA_HORA_FIM_INTRP
            THEN 'SIM'
            ELSE 'NAO'
        END AS PAI_COBRE_PERIODO,
        CASE WHEN e.NUM_SEQ_INTRP IS NOT NULL THEN 'SIM' ELSE 'NAO' END AS MANOBRA_MARCADA_ESTADO_7
    FROM manobras m
    LEFT JOIN base_interrupcao p
      ON p.NUM_SEQ_INTRP = m.NUM_INTRP_INIC_MANOBRA_HCAI
    LEFT JOIN tratamento_estado_7 e
      ON e.NUM_SEQ_INTRP = m.NUM_SEQ_INTRP
)

SELECT
    *,
    CASE
        WHEN MANOBRA_MARCADA_ESTADO_7 = 'SIM'
        THEN 'ALERTA: MANOBRA FOI MARCADA COMO ESTADO 7'
        WHEN PAI_EXISTE = 'NAO'
        THEN 'ALERTA: MANOBRA SEM INTERRUPCAO PAI NO BRUTO'
        WHEN PAI_COBRE_PERIODO = 'NAO'
        THEN 'ALERTA: INTERRUPCAO PAI NAO COBRE PERIODO DA MANOBRA'
        ELSE 'OK: MANOBRA PRESERVADA COM PAI IDENTIFICADO'
    END AS RESULTADO_AUDITORIA
FROM pares
;
"""


def coluna_existente(colunas, candidatos):
    colunas_por_upper = {coluna.upper(): coluna for coluna in colunas}

    for candidato in candidatos:
        coluna = colunas_por_upper.get(candidato.upper())

        if coluna:
            return coluna

    return None


def normalizar_nome_coluna(nome):
    normalizado = "".join(caractere for caractere in nome.upper() if caractere.isalnum())
    sufixos = (
        "ULTHIADMS",
        "PRIMHIADMS",
        "HIADMS",
        "HCAI",
        "UCI",
        "CHVP",
        "PIN",
    )

    alterado = True
    while alterado:
        alterado = False
        for sufixo in sufixos:
            if normalizado.endswith(sufixo) and len(normalizado) > len(sufixo):
                normalizado = normalizado[: -len(sufixo)]
                alterado = True

    return normalizado


def coluna_existente_flexivel(colunas, candidatos):
    coluna = coluna_existente(colunas, candidatos)

    if coluna:
        return coluna

    colunas_normalizadas = [
        (normalizar_nome_coluna(coluna_raw), coluna_raw)
        for coluna_raw in colunas
    ]

    for candidato in candidatos:
        candidato_normalizado = normalizar_nome_coluna(candidato)

        if len(candidato_normalizado) < 8:
            continue

        for coluna_normalizada, coluna_raw in colunas_normalizadas:
            if coluna_normalizada == candidato_normalizado:
                return coluna_raw

        for coluna_normalizada, coluna_raw in colunas_normalizadas:
            if coluna_normalizada.startswith(candidato_normalizado):
                return coluna_raw

    return None


def expressao_regional(coluna_sigla):
    if not coluna_sigla:
        return "'COPEL'"

    return f"""
        CASE
            WHEN CAST({coluna_sigla} AS VARCHAR) = 'P' THEN 'CSL'
            WHEN CAST({coluna_sigla} AS VARCHAR) = 'L' THEN 'NRT'
            WHEN CAST({coluna_sigla} AS VARCHAR) = 'M' THEN 'NRO'
            WHEN CAST({coluna_sigla} AS VARCHAR) = 'C' THEN 'LES'
            WHEN CAST({coluna_sigla} AS VARCHAR) = 'V' THEN 'OES'
            ELSE 'COPEL'
        END
    """


def montar_sql_tratamento(con, logger=None):
    colunas = [
        linha[0]
        for linha in con.execute("DESCRIBE raw_db.hiadms_raw").fetchall()
    ]
    coluna_sigla_regional = coluna_existente(
        colunas,
        (
            "INDIC_REG_ORIG_INTRP_HCAI",
            "SIGLA_REGIONAL_INTRP_PRIM_HIADMS",
            "SIGLA_REGIONAL_INTRP_ULT_HIADMS",
            "SIGLA_REGIONAL_HIADMS",
            "SIGLA_REGIONAL",
        ),
    )
    coluna_manobra_hcai = coluna_existente(
        colunas,
        (
        "NUM_INTRP_INIC_MANOBRA_UCI_ULT_HIADMS",
            "NUM_INTRP_INIC_MANOBRA_HCAI_ULT_HIADMS",
            "NUM_INTRP_INIC_MANOBRA_HCAI_PRIM_HIADMS",
            "NUM_INTRP_INIC_MANOBRA_ULT_HIADMS",
        ),
    )

    if coluna_sigla_regional:
        if logger:
            logger.info("Usando coluna regional: %s", coluna_sigla_regional)
        sigla_regional_expr = f"CAST({coluna_sigla_regional} AS VARCHAR)"
    else:
        if logger:
            logger.info("Coluna regional nao encontrada; usando COPEL como fallback.")
        sigla_regional_expr = "' '"

    if coluna_manobra_hcai:
        if logger:
            logger.info("Usando coluna manobra HCAI: %s", coluna_manobra_hcai)
        manobra_hcai_expr = f"CAST({coluna_manobra_hcai} AS VARCHAR)"
    else:
        if logger:
            logger.info("Coluna manobra UCI nao encontrada; usando vazio.")
        manobra_hcai_expr = "' '"

    return (
        SQL_TRATAMENTO
        .replace("__REGIONAL_EXPR__", expressao_regional(coluna_sigla_regional))
        .replace("__SIGLA_REGIONAL_ORIG_EXPR__", sigla_regional_expr)
        .replace("__NUM_INTRP_INIC_MANOBRA_HCAI_EXPR__", manobra_hcai_expr)
    )


def montar_sql_auditoria_outliers_bruto(con, logger=None):
    colunas = [
        linha[0]
        for linha in con.execute("DESCRIBE raw_db.hiadms_raw").fetchall()
    ]
    coluna_cod_tipo = coluna_existente(
        colunas,
        (
            "COD_TIPO_INTRP_ULT_HIADMS",
            "COD_TIPO_INTRP_PRIM_HIADMS",
            "COD_TIPO_INTRP_HIADMS",
            "COD_TIPO_INTRP",
        ),
    )
    coluna_tipo_protocolo_uci = coluna_existente(
        colunas,
        (
            "TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS",
            "TIPO_PROTOC_JUSTIF_UCI_PRIM_HIADMS",
            "TIPO_PROTOC_JUSTIF_UCI_HIADMS",
            "TIPO_PROTOC_JUSTIF_UCI",
        ),
    )
    coluna_num_protocolo_uci = coluna_existente(
        colunas,
        (
            "NUM_PROTOC_JUSTIF_RESP_UCI_ULT_HIADMS",
            "NUM_PROTOC_JUSTIF_RESP_UCI_PRIM_HIADMS",
            "NUM_PROTOC_JUSTIF_RESP_UCI_HIADMS",
            "NUM_PROTOC_JUSTIF_RESP_UCI",
        ),
    )

    if coluna_cod_tipo:
        if logger:
            logger.info("Auditoria outliers usando coluna COD_TIPO_INTRP: %s", coluna_cod_tipo)
        cod_tipo_expr = f"CAST({coluna_cod_tipo} AS VARCHAR)"
    else:
        if logger:
            logger.info("Auditoria outliers sem coluna COD_TIPO_INTRP; usando espaco.")
        cod_tipo_expr = "' '"

    if coluna_tipo_protocolo_uci:
        if logger:
            logger.info(
                "Auditoria outliers usando coluna TIPO_PROTOC_JUSTIF_UCI: %s",
                coluna_tipo_protocolo_uci,
            )
        tipo_protocolo_expr = f"CAST({coluna_tipo_protocolo_uci} AS VARCHAR)"
    else:
        if logger:
            logger.info("Auditoria outliers sem coluna TIPO_PROTOC_JUSTIF_UCI; usando espaco.")
        tipo_protocolo_expr = "' '"

    if coluna_num_protocolo_uci:
        if logger:
            logger.info(
                "Auditoria outliers usando coluna NUM_PROTOC_JUSTIF_RESP_UCI: %s",
                coluna_num_protocolo_uci,
            )
        num_protocolo_expr = f"CAST({coluna_num_protocolo_uci} AS VARCHAR)"
    else:
        if logger:
            logger.info("Auditoria outliers sem coluna NUM_PROTOC_JUSTIF_RESP_UCI; usando espaco.")
        num_protocolo_expr = "' '"

    return (
        SQL_AUDITORIA_OUTLIERS_BRUTO
        .replace("__COD_TIPO_INTRP_EXPR__", cod_tipo_expr)
        .replace("__TIPO_PROTOC_JUSTIF_UCI_EXPR__", tipo_protocolo_expr)
        .replace("__NUM_PROTOC_JUSTIF_RESP_UCI_EXPR__", num_protocolo_expr)
        .replace("__OUTLIER_DURACAO_HORAS__", str(OUTLIER_DURACAO_HORAS))
        .replace("__OUTLIER_QTD_UCS__", str(OUTLIER_QTD_UCS))
        .replace("__OUTLIER_QTD_INTRP_CONTIDAS__", str(OUTLIER_QTD_INTRP_CONTIDAS))
        .replace("__OUTLIER_QTD_UCS_AFETADAS__", str(OUTLIER_QTD_UCS_AFETADAS))
    )


def montar_sql_auditoria_manobra_hcai(con, logger=None):
    colunas = [
        linha[0]
        for linha in con.execute("DESCRIBE raw_db.hiadms_raw").fetchall()
    ]
    coluna_manobra_hcai = coluna_existente(
        colunas,
        (
            "NUM_INTRP_INIC_MANOBRA_HCAI",
            "NUM_INTRP_INIC_MANOBRA_HCAI_ULT_HIADMS",
            "NUM_INTRP_INIC_MANOBRA_HCAI_PRIM_HIADMS",
            "NUM_INTRP_INIC_MANOBRA_ULT_HIADMS",
        ),
    )

    if coluna_manobra_hcai:
        if logger:
            logger.info("Auditoria manobra usando coluna HCAI: %s", coluna_manobra_hcai)
        manobra_hcai_expr = f"CAST({coluna_manobra_hcai} AS VARCHAR)"
    else:
        if logger:
            logger.info("Auditoria manobra sem coluna HCAI; usando vazio.")
        manobra_hcai_expr = "' '"

    return SQL_AUDITORIA_MANOBRA_HCAI.replace(
        "__NUM_INTRP_INIC_MANOBRA_HCAI_EXPR__",
        manobra_hcai_expr,
    )


def montar_sql_auditoria_estado_7(con, logger=None):
    colunas = [
        linha[0]
        for linha in con.execute("DESCRIBE raw_db.hiadms_raw").fetchall()
    ]
    coluna_sigla_regional = coluna_existente(
        colunas,
        (
            "INDIC_REG_ORIG_INTRP_HCAI",
            "SIGLA_REGIONAL_INTRP_PRIM_HIADMS",
            "SIGLA_REGIONAL_INTRP_ULT_HIADMS",
            "SIGLA_REGIONAL_HIADMS",
            "SIGLA_REGIONAL",
        ),
    )

    if coluna_sigla_regional:
        if logger:
            logger.info("Auditoria ESTADO 7 usando coluna regional: %s", coluna_sigla_regional)
        sigla_regional_expr = f"CAST({coluna_sigla_regional} AS VARCHAR)"
    else:
        if logger:
            logger.info("Auditoria ESTADO 7 sem coluna regional; usando COPEL como fallback.")
        sigla_regional_expr = "' '"

    return (
        SQL_AUDITORIA_ESTADO_7
        .replace("__REGIONAL_EXPR__", expressao_regional(coluna_sigla_regional))
        .replace("__SIGLA_REGIONAL_ORIG_EXPR__", sigla_regional_expr)
    )


# ============================================================
# EXPORTAÇÃO POR REGIONAL
# Formato:
# Interrupcoes_IQS_20260624231619_CSL.CSV
# ============================================================

def tratar_e_exportar_alterados(logger=None):
    logger = logger or configurar_logger("tratamento", ANOMES)
    done_tratamento = carregar_done("tratamento", ANOMES)

    if done_tratamento and not REPROCESSAR:
        logger.info("Tratamento ja finalizado em %s", done_tratamento.get("finished_at"))
        logger.info("Registros alterados: %s", done_tratamento.get("rows"))
        logger.info("Defina REPROCESSAR=1 para processar novamente.")
        return

    done_extract = validar_done_sucesso("extract", ANOMES)
    duckdb_path_done = Path(done_extract.get("duckdb_path", ""))

    if duckdb_path_done != RAW_DUCKDB_PATH:
        logger.warning(
            "DuckDB bruto do controle (%s) difere do caminho esperado (%s).",
            duckdb_path_done,
            RAW_DUCKDB_PATH,
        )

    if not RAW_DUCKDB_PATH.exists():
        raise FileNotFoundError(f"DuckDB bruto nao encontrado: {RAW_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    temp_dir = Path("data") / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = {sql_literal(TEMP_DIR.as_posix())}")
    con.execute("SET preserve_insertion_order = false")
    con.execute(f"SET threads = {DUCKDB_THREADS}")
    con.execute(f"SET memory_limit = {sql_literal(DUCKDB_MEMORY_LIMIT)}")
    con.execute(f"SET max_temp_directory_size = {sql_literal(DUCKDB_MAX_TEMP_DIRECTORY_SIZE)}")

    with lock_execucao("tratamento", ANOMES) as started_at:
        logger.info("Conectando bancos DuckDB do modelo data/...")
        logger.info(
            "DuckDB configurado: threads=%s, memory_limit=%s, max_temp_directory_size=%s",
            DUCKDB_THREADS,
            DUCKDB_MEMORY_LIMIT,
            DUCKDB_MAX_TEMP_DIRECTORY_SIZE,
        )
        con.execute(f"ATTACH {sql_literal(RAW_DUCKDB_PATH.as_posix())} AS raw_db (READ_ONLY)")

        auditoria_outliers_bruto = exportar_auditoria_outliers_bruto(con, logger)

        logger.info("Executando tratamento no DuckDB...")
        con.execute(montar_sql_tratamento(con, logger=logger))

        con.execute("""
            UPDATE adms_iqs_alterados
            SET NUM_INTRP_INIC_MANOBRA_UCI =
                CASE
                    WHEN NUM_INTRP_MANOBRA_PAI_REDIREC IS NOT NULL
                    THEN NUM_INTRP_MANOBRA_PAI_REDIREC
                    WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                    THEN NULL
                    WHEN TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) IN ('0', '0.0')
                    THEN NULL
                    WHEN TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) = TRIM(CAST(NUM_INTRP_UCI AS VARCHAR))
                    THEN NULL
                    WHEN TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) = TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                    THEN NULL
                    ELSE NUM_INTRP_INIC_MANOBRA_UCI
                END
        """)

        total = con.execute("SELECT COUNT(*) FROM adms_iqs_alterados").fetchone()[0]
        logger.info("Registros alterados: %s", f"{total:,}")

        regionais = con.execute("""
            SELECT DISTINCT REGIONAL
            FROM adms_iqs_alterados
            WHERE REGIONAL IS NOT NULL
            ORDER BY REGIONAL
        """).fetchall()

        arquivos_exportados = []
        auditoria_estado_7 = {
            "total_pares": 0,
            "total_anomalias": 0,
            "total_anomalias_aceitas": 0,
            "total_anomalias_pendentes": 0,
            "alerts": 0,
        }
        auditoria_manobra_hcai = {
            "total_manobras": 0,
            "total_alertas": 0,
        }
        auditoria_uc_91_d = {
            "total_ucs": 0,
            "total_alertas": 0,
        }
        auditoria_join_raw_export = {
            "status": "DESATIVADA",
            "total_alertas": 0,
        }

        if False and auditoria_join_raw_export["rows_without_raw"] > 0:
            con.close()
            raise RuntimeError(
                "Auditoria join RAW/export encontrou linhas tratadas sem RAW correspondente. "
                f"Verifique: {auditoria_join_raw_export['path']}"
            )

        total_export_iqs = criar_tabela_exportacao_iqs(con, logger)

        if auditoria_estado_7["alerts"] > 0:
            exportar_previa_iqs_bloqueada(
                con,
                regionais,
                total_export_iqs,
                auditoria_estado_7,
                logger,
            )
            con.close()
            raise RuntimeError(
                "Auditoria ESTADO_INTRP 7 encontrou anomalias. "
                f"Verifique: {auditoria_estado_7['anomalies_path']}"
            )

        if not regionais:
            logger.info("Nenhum registro alterado para exportar.")
            con.close()
            gravar_done(
                "tratamento",
                ANOMES,
                {
                    "started_at": started_at,
                    "finished_at": agora_iso(),
                    "rows": total,
                    "processed_duckdb_path": PROCESSED_DUCKDB_PATH.as_posix(),
                    "export_files": arquivos_exportados,
                    "auditoria_outliers_bruto": auditoria_outliers_bruto,
                    "auditoria_estado_7": auditoria_estado_7,
                    "auditoria_manobra_hcai": auditoria_manobra_hcai,
                    "auditoria_uc_91_d": auditoria_uc_91_d,
                    "auditoria_join_raw_export": auditoria_join_raw_export,
                },
            )
            return

        arquivos_exportados = exportar_arquivos_iqs(
            con,
            regionais,
            EXPORT_DIR,
            "",
            logger,
        )

        mapeamento_layout_iqs = exportar_mapeamento_layout_iqs(logger)
        resumo_exportacao = exportar_resumo_iqs(arquivos_exportados, total_export_iqs)
        logger.info("Resumo da exportacao IQS gerado: %s", resumo_exportacao)

        con.close()
        gravar_done(
            "tratamento",
            ANOMES,
            {
                "started_at": started_at,
                "finished_at": agora_iso(),
                "rows": total,
                "processed_duckdb_path": PROCESSED_DUCKDB_PATH.as_posix(),
                "export_files": arquivos_exportados,
                "export_summary_path": resumo_exportacao,
                "layout_mapping_path": mapeamento_layout_iqs,
                "auditoria_outliers_bruto": auditoria_outliers_bruto,
                "auditoria_estado_7": auditoria_estado_7,
                "auditoria_manobra_hcai": auditoria_manobra_hcai,
                "auditoria_uc_91_d": auditoria_uc_91_d,
                "auditoria_join_raw_export": auditoria_join_raw_export,
            },
        )
        logger.info("Exportacao concluida.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    logger = configurar_logger("tratamento", ANOMES)
    logger.info("Tratando ANOMES=%s", ANOMES)
    tratar_e_exportar_alterados(logger=logger)
    logger.info("Fim.")
