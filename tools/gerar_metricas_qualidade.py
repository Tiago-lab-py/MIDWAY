import csv
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


def escalar(con, sql):
    return con.execute(sql).fetchone()[0]


def valor_float(valor):
    if valor is None:
        return 0.0
    return float(valor)


def adicionar_metricas_tabela(con, metricas):
    tabelas = [
        "gold_interrupcao_tratada",
        "silver_interrupcao_uc_apuravel",
        "gold_apuracao_uc",
        "gold_apuracao_previa",
        "gold_continuidade_uc",
        "gold_ressarcimento_prodist",
        "export_sobreposicao_total_uc",
        "export_sobreposicao_parcial_uc",
        "gold_interrupcao_sem_uc",
        "gold_ocorrencia_sem_uc",
        "adms_iqs_interrupcao_sem_uc_export",
        "Auditoria_ESTADO_7",
        "auditoria_outliers_bruto",
    ]
    for tabela in tabelas:
        existe = escalar(
            con,
            f"""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = '{tabela}'
            """,
        )
        valor = escalar(con, f"SELECT COUNT(*) FROM {tabela}") if existe else None
        metricas.append(
            {
                "metrica": f"linhas_{tabela}",
                "valor": valor,
                "nivel": "OK" if existe else "CRITICO",
                "detalhe": "Tabela existe" if existe else "Tabela ausente",
            }
        )


def adicionar_metricas_fechamento(con, metricas):
    ci_uc, chi_uc = con.execute(
        "SELECT SUM(CI_LIQUIDO), SUM(CHI_LIQUIDO) FROM gold_apuracao_uc"
    ).fetchone()
    ci_previa, chi_previa = con.execute(
        "SELECT SUM(CI_LIQUIDO), SUM(CHI_LIQUIDO) FROM gold_apuracao_previa"
    ).fetchone()
    fic, dic = con.execute("SELECT SUM(FIC), SUM(DIC) FROM gold_continuidade_uc").fetchone()

    diff_ci_fic = abs(valor_float(ci_uc) - valor_float(fic))
    diff_chi_dic = abs(valor_float(chi_uc) - valor_float(dic))
    diff_ci_previa = abs(valor_float(ci_uc) - valor_float(ci_previa))
    diff_chi_previa = abs(valor_float(chi_uc) - valor_float(chi_previa))

    metricas.extend(
        [
            {"metrica": "total_ci_liquido", "valor": ci_uc, "nivel": "INFO", "detalhe": "gold_apuracao_uc"},
            {"metrica": "total_chi_liquido", "valor": chi_uc, "nivel": "INFO", "detalhe": "gold_apuracao_uc"},
            {"metrica": "total_fic", "valor": fic, "nivel": "INFO", "detalhe": "gold_continuidade_uc"},
            {"metrica": "total_dic", "valor": dic, "nivel": "INFO", "detalhe": "gold_continuidade_uc"},
            {
                "metrica": "diff_ci_fic",
                "valor": diff_ci_fic,
                "nivel": "OK" if diff_ci_fic == 0 else "CRITICO",
                "detalhe": "CI liquido deve fechar com FIC",
            },
            {
                "metrica": "diff_chi_dic",
                "valor": diff_chi_dic,
                "nivel": "OK" if diff_chi_dic <= 0.001 else "CRITICO",
                "detalhe": "CHI liquido deve fechar com DIC",
            },
            {
                "metrica": "diff_ci_previa_uc",
                "valor": diff_ci_previa,
                "nivel": "OK" if diff_ci_previa == 0 else "CRITICO",
                "detalhe": "gold_apuracao_previa deve fechar com gold_apuracao_uc",
            },
            {
                "metrica": "diff_chi_previa_uc",
                "valor": diff_chi_previa,
                "nivel": "OK" if diff_chi_previa <= 0.001 else "CRITICO",
                "detalhe": "gold_apuracao_previa deve fechar com gold_apuracao_uc",
            },
        ]
    )


def adicionar_metricas_regras(con, metricas):
    motivo_preenchido = escalar(
        con,
        """
        SELECT COUNT(*)
        FROM gold_apuracao_uc
        WHERE NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NOT NULL
        """,
    )
    manobra_preenchida = escalar(
        con,
        """
        SELECT COUNT(*)
        FROM gold_apuracao_uc
        WHERE NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL
        """,
    )
    duracao_invalida = escalar(
        con,
        """
        SELECT COUNT(*)
        FROM gold_apuracao_uc
        WHERE DTHR_INICIO_INTRP_UC IS NULL
           OR DATA_HORA_FIM_INTRP IS NULL
           OR DATA_HORA_FIM_INTRP < DTHR_INICIO_INTRP_UC
           OR DURACAO_HORA < 0
        """,
    )
    duracao_ge_24h = escalar(
        con,
        """
        SELECT COUNT(*)
        FROM gold_apuracao_uc
        WHERE CI_LIQUIDO = 1
          AND DURACAO_HORA >= 24
        """,
    )
    sobreposicao_residual = escalar(
        con,
        """
        WITH base AS (
            SELECT
                TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS UC,
                TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) AS COD_TIPO_INTRP,
                TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) AS TIPO_PROTOC_JUSTIF_UCI,
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                DTHR_INICIO_INTRP_UC,
                DATA_HORA_FIM_INTRP,
                LAG(DATA_HORA_FIM_INTRP) OVER (
                    PARTITION BY
                        TRIM(CAST(NUM_UC_UCI AS VARCHAR)),
                        TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)),
                        TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR))
                    ORDER BY
                        DTHR_INICIO_INTRP_UC,
                        DATA_HORA_FIM_INTRP,
                        TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                ) AS FIM_ANTERIOR
            FROM gold_apuracao_uc
            WHERE CI_LIQUIDO = 1
              AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
        )
        SELECT COUNT(*)
        FROM base
        WHERE FIM_ANTERIOR > DTHR_INICIO_INTRP_UC
        """,
    )
    ocorrencias_sem_uc_completas = escalar(
        con,
        """
        SELECT COUNT(*)
        FROM gold_ocorrencia_sem_uc
        WHERE OCORRENCIA_SEM_UC_APURAVEL = 'SIM'
        """,
    )

    metricas.extend(
        [
            {
                "metrica": "motivo_preenchido_em_gold_apuracao_uc",
                "valor": motivo_preenchido,
                "nivel": "OK" if motivo_preenchido == 0 else "CRITICO",
                "detalhe": "NUM_MOTIVO_TRAT_DIF_UCI deve ser nulo na base apuravel",
            },
            {
                "metrica": "manobra_preenchida_em_gold_apuracao_uc",
                "valor": manobra_preenchida,
                "nivel": "OK" if manobra_preenchida == 0 else "CRITICO",
                "detalhe": "Manobras nao devem entrar novamente em DIC/FIC",
            },
            {
                "metrica": "duracao_invalida_em_gold_apuracao_uc",
                "valor": duracao_invalida,
                "nivel": "OK" if duracao_invalida == 0 else "CRITICO",
                "detalhe": "Datas e duracao devem ser validas",
            },
            {
                "metrica": "duracao_liquida_ge_24h",
                "valor": duracao_ge_24h,
                "nivel": "ALERTA" if duracao_ge_24h > 0 else "OK",
                "detalhe": "Auditar sem filtrar automaticamente",
            },
            {
                "metrica": "sobreposicao_residual_uc_tipo_base_liquida",
                "valor": sobreposicao_residual,
                "nivel": "OK" if sobreposicao_residual == 0 else "CRITICO",
                "detalhe": "Sobreposicao residual por mesma UC, COD_TIPO_INTRP e TIPO_PROTOC_JUSTIF_UCI",
            },
            {
                "metrica": "ocorrencias_completas_sem_uc_apuravel",
                "valor": ocorrencias_sem_uc_completas,
                "nivel": "ALERTA" if ocorrencias_sem_uc_completas > 0 else "OK",
                "detalhe": "Avaliar possibilidade de ESTADO_INTRP=7 e 91/R por ocorrencia completa",
            },
        ]
    )


def adicionar_metricas_percentis(con, metricas):
    row = con.execute(
        """
        SELECT
            MIN(DURACAO_HORA),
            QUANTILE_CONT(DURACAO_HORA, 0.50),
            QUANTILE_CONT(DURACAO_HORA, 0.90),
            QUANTILE_CONT(DURACAO_HORA, 0.99),
            MAX(DURACAO_HORA)
        FROM gold_apuracao_uc
        WHERE CI_LIQUIDO = 1
        """
    ).fetchone()
    nomes = ["duracao_min_h", "duracao_p50_h", "duracao_p90_h", "duracao_p99_h", "duracao_max_h"]
    for nome, valor in zip(nomes, row):
        metricas.append(
            {
                "metrica": nome,
                "valor": valor,
                "nivel": "INFO",
                "detalhe": "Distribuicao de duracao da base liquida",
            }
        )


def adicionar_metricas_ressarcimento(con, metricas):
    row = con.execute(
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN COMP_TOTAL_PRODIST > 0 THEN 1 ELSE 0 END),
            COALESCE(SUM(COMP_TOTAL_PRODIST), 0),
            SUM(CASE WHEN STATUS_CALCULO_PRODIST = 'PARCIAL_AGREGADO_POR_UC' THEN 1 ELSE 0 END)
        FROM gold_ressarcimento_prodist
        """
    ).fetchone()
    metricas.extend(
        [
            {"metrica": "ressarcimento_prodist_ucs", "valor": row[0], "nivel": "INFO", "detalhe": "UCs avaliadas"},
            {"metrica": "ressarcimento_prodist_ucs_com_compensacao", "valor": row[1], "nivel": "INFO", "detalhe": "UCs com valor positivo"},
            {"metrica": "ressarcimento_prodist_total", "valor": row[2], "nivel": "INFO", "detalhe": "COMP_TOTAL_PRODIST"},
            {
                "metrica": "ressarcimento_dicri_dise_agregado_uc",
                "valor": row[3],
                "nivel": "ALERTA" if row[3] else "OK",
                "detalhe": "DICRI/DISE ainda requerem evolucao por evento",
            },
        ]
    )


def escrever_saida(metricas):
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = MARTS_DIR / f"Metricas_Qualidade_Dados_{ANOMES}_{TIMESTAMP}.CSV"
    resumo_path = MARTS_DIR / f"Metricas_Qualidade_Dados_{ANOMES}_{TIMESTAMP}_RESUMO.TXT"

    with csv_path.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=["metrica", "valor", "nivel", "detalhe"], delimiter="|")
        writer.writeheader()
        writer.writerows(metricas)

    criticos = [m for m in metricas if m["nivel"] == "CRITICO"]
    alertas = [m for m in metricas if m["nivel"] == "ALERTA"]

    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("METRICAS DE QUALIDADE DE DADOS\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write(f"CSV: {csv_path}\n")
        arquivo.write(f"Total metricas: {len(metricas)}\n")
        arquivo.write(f"Criticos: {len(criticos)}\n")
        arquivo.write(f"Alertas: {len(alertas)}\n")
        arquivo.write("\nCRITICOS\n")
        for metrica in criticos:
            arquivo.write(f"- {metrica['metrica']}: {metrica['valor']} ({metrica['detalhe']})\n")
        arquivo.write("\nALERTAS\n")
        for metrica in alertas:
            arquivo.write(f"- {metrica['metrica']}: {metrica['valor']} ({metrica['detalhe']})\n")

    print(f"Metricas exportadas: {csv_path}")
    print(f"Resumo exportado: {resumo_path}")
    if criticos:
        raise SystemExit(1)


def main():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    metricas = []
    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH), read_only=True)
    try:
        adicionar_metricas_tabela(con, metricas)
        adicionar_metricas_fechamento(con, metricas)
        adicionar_metricas_regras(con, metricas)
        adicionar_metricas_percentis(con, metricas)
        adicionar_metricas_ressarcimento(con, metricas)
    finally:
        con.close()

    escrever_saida(metricas)


if __name__ == "__main__":
    main()
