import os
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202605")

BASE_DIR = Path("data")
MARTS_DIR = BASE_DIR / "marts"
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")


def sql_literal(valor):
    return "'" + str(valor).replace("'", "''") + "'"


def normalizar_linhas_unix(caminho_csv):
    conteudo = caminho_csv.read_bytes()
    normalizado = conteudo.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if normalizado != conteudo:
        caminho_csv.write_bytes(normalizado)


def auditar_ajuste_inicio_manobra():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))

    tabelas = {
        linha[0]
        for linha in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }

    if "adms_iqs_alterados" not in tabelas:
        con.close()
        raise RuntimeError("Tabela adms_iqs_alterados nao encontrada.")

    colunas = {
        linha[0]
        for linha in con.execute("DESCRIBE adms_iqs_alterados").fetchall()
    }

    colunas_obrigatorias = {
        "ACAO_REDIREC_MANOBRA_ESTADO_7",
        "NUM_INTRP_INIC_MANOBRA_UCI_ANTES_REDIREC",
        "NUM_INTRP_MANOBRA_FILHA_7_REDIREC",
        "NUM_INTRP_MANOBRA_PAI_REDIREC",
    }

    faltantes = sorted(colunas_obrigatorias - colunas)
    if faltantes:
        con.close()
        raise RuntimeError(
            "Colunas de auditoria nao encontradas. Execute run.bat reprocessar. "
            f"Faltantes: {', '.join(faltantes)}"
        )

    total = con.execute(
        """
        SELECT COUNT(*)
        FROM adms_iqs_alterados
        WHERE ACAO_REDIREC_MANOBRA_ESTADO_7 IS NOT NULL
        """
    ).fetchone()[0]

    caminho_csv = MARTS_DIR / f"Auditoria_Ajuste_Inicio_Manobra_{TIMESTAMP_ARQ}.CSV"
    caminho_resumo = MARTS_DIR / f"Auditoria_Ajuste_Inicio_Manobra_{TIMESTAMP_ARQ}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT
                REGIONAL,
                SIGLA_REGIONAL_ORIG,
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP,
                NUM_UC_UCI,
                NUM_POSTO_UCI,
                ESTADO_INTRP,
                DATA_HORA_INIC_INTRP,
                DATA_HORA_FIM_INTRP,
                NUM_INTRP_INIC_MANOBRA_UCI_ANTES_REDIREC,
                NUM_INTRP_MANOBRA_FILHA_7_REDIREC,
                NUM_INTRP_MANOBRA_PAI_REDIREC,
                NUM_INTRP_INIC_MANOBRA_UCI,
                ACAO_REDIREC_MANOBRA_ESTADO_7,
                ACAO_SOBREPOSICAO_INTERRUPCAO,
                ACAO_SOBREPOSICAO_TOTAL_UC,
                ACAO_AJUSTE_PARCIAL
            FROM adms_iqs_alterados
            WHERE ACAO_REDIREC_MANOBRA_ESTADO_7 IS NOT NULL
            ORDER BY
                REGIONAL,
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP,
                NUM_UC_UCI
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

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as resumo:
        resumo.write("AUDITORIA AJUSTE INICIO MANOBRA\n")
        resumo.write(f"ANOMES: {ANOMES}\n")
        resumo.write(f"DuckDB processado: {PROCESSED_DUCKDB_PATH}\n")
        resumo.write(f"Registros redirecionados: {total}\n")
        resumo.write("Regra: NUM_INTRP_INIC_MANOBRA_UCI que apontava para ESTADO_INTRP=7 foi substituido pelo pai mantido.\n")
        resumo.write(f"Arquivo: {caminho_csv}\n")
        resumo.write("Terminador de linha: UNIX LF\n")

    con.close()

    print(f"Auditoria exportada: {caminho_csv}")
    print(f"Resumo exportado: {caminho_resumo}")
    print(f"Registros redirecionados: {total:,}")


if __name__ == "__main__":
    auditar_ajuste_inicio_manobra()
