import os
from datetime import datetime
from pathlib import Path


def _colunas_tabela_apuracao(con, tabela):
    return {
        linha[1].upper()
        for linha in con.execute(f"PRAGMA table_info('{tabela}')").fetchall()
    }


def _expr_coluna_existente(colunas, candidatos, padrao="NULL"):
    for coluna in candidatos:
        if coluna.upper() in colunas:
            return coluna
    return padrao


def criar_gold_interrupcao_sem_uc(con):
    print("Criando gold_interrupcao_sem_uc...")

    colunas = _colunas_tabela_apuracao(con, "gold_interrupcao_tratada")
    regional_expr = _expr_coluna_existente(
        colunas,
        ["REGIONAL_EXPORT", "REGIONAL", "SIGLA_REGIONAL"],
        "'COPEL'",
    )

    con.execute(
        f"""
        DROP TABLE IF EXISTS gold_interrupcao_sem_uc;

        CREATE TABLE gold_interrupcao_sem_uc AS
        WITH base AS (
            SELECT
                CAST({regional_expr} AS VARCHAR) AS REGIONAL,
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(NUM_INTRP_UCI AS VARCHAR) AS NUM_INTRP_UCI,
                CAST(NUM_OPER_CHV_INTRP AS VARCHAR) AS NUM_OPER_CHV_INTRP,
                CAST(NUM_POSTO_UCI AS VARCHAR) AS NUM_POSTO_UCI,
                CAST(COD_CAUSA_INTRP AS VARCHAR) AS COD_CAUSA_INTRP,
                CAST(COD_COMP_INTRP AS VARCHAR) AS COD_COMP_INTRP,
                CAST(COD_TIPO_INTRP AS VARCHAR) AS COD_TIPO_INTRP,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                COUNT(*) AS QTD_UCS_TOTAL,
                SUM(
                    CASE
                        WHEN NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
                        THEN 1 ELSE 0
                    END
                ) AS QTD_UCS_COM_NUM_UC,
                SUM(
                    CASE
                        WHEN TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)) = '91'
                         AND TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)) = 'D'
                        THEN 1 ELSE 0
                    END
                ) AS QTD_UCS_DESCARTADAS_91_D,
                SUM(
                    CASE
                        WHEN NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NULL
                        THEN 1 ELSE 0
                    END
                ) AS QTD_UCS_APURAVEIS,
                SUM(
                    CASE
                        WHEN NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NOT NULL
                        THEN 1 ELSE 0
                    END
                ) AS QTD_UCS_COM_TRATAMENTO
            FROM gold_interrupcao_tratada
            WHERE TRIM(CAST(ESTADO_INTRP AS VARCHAR)) = '4'
            GROUP BY
                CAST({regional_expr} AS VARCHAR),
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                CAST(NUM_SEQ_INTRP AS VARCHAR),
                CAST(NUM_INTRP_UCI AS VARCHAR),
                CAST(NUM_OPER_CHV_INTRP AS VARCHAR),
                CAST(NUM_POSTO_UCI AS VARCHAR),
                CAST(COD_CAUSA_INTRP AS VARCHAR),
                CAST(COD_COMP_INTRP AS VARCHAR),
                CAST(COD_TIPO_INTRP AS VARCHAR)
        )
        SELECT
            *,
            CASE
                WHEN QTD_UCS_TOTAL > 0
                 AND QTD_UCS_DESCARTADAS_91_D = QTD_UCS_TOTAL
                 AND QTD_UCS_APURAVEIS = 0
                THEN 'SIM'
                ELSE 'NAO'
            END AS TODAS_UCS_SOBREPOSTAS_91_D,
            CASE
                WHEN QTD_UCS_TOTAL > 0
                 AND QTD_UCS_DESCARTADAS_91_D = QTD_UCS_TOTAL
                 AND QTD_UCS_APURAVEIS = 0
                THEN 'INTERRUPCAO_SEM_UC_APURAVEL_POR_SOBREPOSICAO_TOTAL_UC'
                ELSE 'OK'
            END AS RESULTADO_AUDITORIA
        FROM base
        WHERE QTD_UCS_TOTAL > 0
          AND QTD_UCS_DESCARTADAS_91_D = QTD_UCS_TOTAL
          AND QTD_UCS_APURAVEIS = 0
        """
    )


def criar_gold_ocorrencia_sem_uc(con):
    print("Criando gold_ocorrencia_sem_uc...")

    colunas = _colunas_tabela_apuracao(con, "gold_interrupcao_tratada")
    regional_expr = _expr_coluna_existente(
        colunas,
        ["REGIONAL_EXPORT", "REGIONAL", "SIGLA_REGIONAL"],
        "'COPEL'",
    )

    con.execute(
        f"""
        DROP TABLE IF EXISTS gold_ocorrencia_sem_uc;

        CREATE TABLE gold_ocorrencia_sem_uc AS
        WITH interrupcoes_estado_4 AS (
            SELECT
                COALESCE(REGIONAL, 'COPEL') AS REGIONAL,
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                SUM(QTD_UCS_TOTAL) AS QTD_UCS_TOTAL,
                SUM(QTD_UCS_DESCARTADAS_91_D) AS QTD_UCS_DESCARTADAS_91_D,
                SUM(QTD_UCS_APURAVEIS) AS QTD_UCS_APURAVEIS,
                MAX(
                    CASE
                        WHEN TODAS_UCS_SOBREPOSTAS_91_D = 'SIM'
                        THEN 1 ELSE 0
                    END
                ) AS INTERRUPCAO_SEM_UC_APURAVEL
            FROM gold_interrupcao_sem_uc
            GROUP BY
                COALESCE(REGIONAL, 'COPEL'),
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP
        ),

        todas_interrupcoes_ocorrencia AS (
            SELECT
                COALESCE(CAST({regional_expr} AS VARCHAR), 'COPEL') AS REGIONAL,
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                COUNT(*) AS QTD_LINHAS_UC,
                SUM(
                    CASE
                        WHEN NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NULL
                        THEN 1 ELSE 0
                    END
                ) AS QTD_UCS_APURAVEIS
            FROM gold_interrupcao_tratada
            WHERE TRIM(CAST(ESTADO_INTRP AS VARCHAR)) = '4'
              AND NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY
                COALESCE(CAST({regional_expr} AS VARCHAR), 'COPEL'),
                CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                CAST(NUM_SEQ_INTRP AS VARCHAR)
        ),

        ocorrencias AS (
            SELECT
                t.REGIONAL,
                t.NUM_OCORRENCIA_ADMS,
                MIN(t.DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_OCORRENCIA,
                MAX(t.DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_OCORRENCIA,
                COUNT(*) AS QTD_INTERRUPCOES_ESTADO_4,
                SUM(CASE WHEN t.QTD_UCS_APURAVEIS = 0 THEN 1 ELSE 0 END) AS QTD_INTERRUPCOES_SEM_UC_APURAVEL,
                SUM(COALESCE(i.INTERRUPCAO_SEM_UC_APURAVEL, 0)) AS QTD_INTERRUPCOES_SEM_UC_91_D,
                SUM(t.QTD_LINHAS_UC) AS QTD_LINHAS_UC_TOTAL,
                SUM(t.QTD_UCS_APURAVEIS) AS QTD_UCS_APURAVEIS
            FROM todas_interrupcoes_ocorrencia t
            LEFT JOIN interrupcoes_estado_4 i
              ON i.REGIONAL = t.REGIONAL
             AND i.NUM_OCORRENCIA_ADMS = t.NUM_OCORRENCIA_ADMS
             AND i.NUM_SEQ_INTRP = t.NUM_SEQ_INTRP
            GROUP BY
                t.REGIONAL,
                t.NUM_OCORRENCIA_ADMS
        )

        SELECT
            *,
            CASE
                WHEN QTD_INTERRUPCOES_ESTADO_4 > 0
                 AND QTD_INTERRUPCOES_SEM_UC_APURAVEL = QTD_INTERRUPCOES_ESTADO_4
                 AND QTD_UCS_APURAVEIS = 0
                THEN 'SIM'
                ELSE 'NAO'
            END AS OCORRENCIA_SEM_UC_APURAVEL,
            CASE
                WHEN QTD_INTERRUPCOES_ESTADO_4 > 0
                 AND QTD_INTERRUPCOES_SEM_UC_APURAVEL = QTD_INTERRUPCOES_ESTADO_4
                 AND QTD_UCS_APURAVEIS = 0
                THEN 'AVALIAR_MARCAR_INTERRUPCOES_DA_OCORRENCIA_COMO_ESTADO_7_91_R'
                WHEN QTD_INTERRUPCOES_SEM_UC_APURAVEL > 0
                THEN 'AVALIAR_INTERRUPCOES_SEM_UC_INDIVIDUAIS'
                ELSE 'OK'
            END AS ACAO_SUGERIDA_AUDITORIA
        FROM ocorrencias
        WHERE QTD_INTERRUPCOES_SEM_UC_APURAVEL > 0
        """
    )


def exportar_auditoria_interrupcao_sem_uc(
    con,
    marts_dir=None,
    anomes=None,
    timestamp=None,
):
    print("Exportando auditoria de interrupcoes sem UC apuravel...")

    marts_dir = Path(marts_dir or Path("data") / "marts")
    anomes = anomes or os.getenv("ANOMES", "202606")
    timestamp = timestamp or datetime.now().strftime("%Y%m%d%H%M%S")

    marts_dir.mkdir(parents=True, exist_ok=True)
    caminho_csv = marts_dir / f"Auditoria_Interrupcao_Sem_UC_{anomes}_{timestamp}.CSV"
    caminho_resumo = marts_dir / f"Auditoria_Interrupcao_Sem_UC_{anomes}_{timestamp}_RESUMO.TXT"
    caminho_ocorrencia_csv = marts_dir / f"Auditoria_Ocorrencia_Sem_UC_{anomes}_{timestamp}.CSV"
    caminho_ocorrencia_resumo = marts_dir / f"Auditoria_Ocorrencia_Sem_UC_{anomes}_{timestamp}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_interrupcao_sem_uc
            ORDER BY REGIONAL, DATA_HORA_INIC_INTRP, NUM_OCORRENCIA_ADMS, NUM_SEQ_INTRP
        )
        TO '{caminho_csv.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_ocorrencia_sem_uc
            ORDER BY REGIONAL, DATA_HORA_INIC_OCORRENCIA, NUM_OCORRENCIA_ADMS
        )
        TO '{caminho_ocorrencia_csv.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )

    total = con.execute("SELECT COUNT(*) FROM gold_interrupcao_sem_uc").fetchone()[0]
    total_ocorrencias = con.execute("SELECT COUNT(*) FROM gold_ocorrencia_sem_uc").fetchone()[0]
    total_ocorrencias_completas = con.execute(
        """
        SELECT COUNT(*)
        FROM gold_ocorrencia_sem_uc
        WHERE OCORRENCIA_SEM_UC_APURAVEL = 'SIM'
        """
    ).fetchone()[0]
    resumo = con.execute(
        """
        SELECT
            COALESCE(REGIONAL, 'COPEL') AS REGIONAL,
            COUNT(*) AS QTD_INTERRUPCOES_SEM_UC,
            SUM(QTD_UCS_TOTAL) AS QTD_UCS_TOTAL,
            SUM(QTD_UCS_DESCARTADAS_91_D) AS QTD_UCS_DESCARTADAS_91_D
        FROM gold_interrupcao_sem_uc
        GROUP BY COALESCE(REGIONAL, 'COPEL')
        ORDER BY REGIONAL
        """
    ).fetchall()

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("AUDITORIA INTERRUPCOES SEM UC APURAVEL\n")
        arquivo.write(f"ANOMES: {anomes}\n")
        arquivo.write("Tabela: gold_interrupcao_sem_uc\n")
        arquivo.write(
            "Criterio: interrupcao ESTADO_INTRP=4 em que todas as UCs foram marcadas como 91/D.\n"
        )
        arquivo.write(f"Total de interrupcoes sem UC apuravel: {total}\n")
        arquivo.write(f"Arquivo CSV: {caminho_csv}\n")
        arquivo.write("\nResumo por regional:\n")
        for regional, qtd_interrupcoes, qtd_ucs_total, qtd_ucs_descartadas in resumo:
            arquivo.write(
                f"{regional}|interrupcoes={qtd_interrupcoes}|"
                f"ucs_total={qtd_ucs_total}|ucs_91_d={qtd_ucs_descartadas}\n"
            )

    print(f"Interrupcoes sem UC apuravel: {total}")
    print(f"Auditoria interrupcao sem UC: {caminho_csv}")
    print(f"Resumo interrupcao sem UC: {caminho_resumo}")

    resumo_ocorrencia = con.execute(
        """
        SELECT
            COALESCE(REGIONAL, 'COPEL') AS REGIONAL,
            COUNT(*) AS QTD_OCORRENCIAS_COM_INTERRUPCAO_SEM_UC,
            SUM(CASE WHEN OCORRENCIA_SEM_UC_APURAVEL = 'SIM' THEN 1 ELSE 0 END) AS QTD_OCORRENCIAS_SEM_UC_COMPLETAS,
            SUM(QTD_INTERRUPCOES_ESTADO_4) AS QTD_INTERRUPCOES_ESTADO_4,
            SUM(QTD_INTERRUPCOES_SEM_UC_APURAVEL) AS QTD_INTERRUPCOES_SEM_UC_APURAVEL
        FROM gold_ocorrencia_sem_uc
        GROUP BY COALESCE(REGIONAL, 'COPEL')
        ORDER BY REGIONAL
        """
    ).fetchall()

    with caminho_ocorrencia_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("AUDITORIA OCORRENCIAS SEM UC APURAVEL\n")
        arquivo.write(f"ANOMES: {anomes}\n")
        arquivo.write("Tabela: gold_ocorrencia_sem_uc\n")
        arquivo.write(
            "Criterio: ocorrencia com uma ou mais interrupcoes sem UC apuravel apos sobreposicao total/parcial por UC.\n"
        )
        arquivo.write(
            "Sinalizacao: ocorrencia completa sem UC pode ser avaliada para marcar interrupcoes como ESTADO_INTRP=7 e 91/R.\n"
        )
        arquivo.write(f"Total de ocorrencias com interrupcao sem UC: {total_ocorrencias}\n")
        arquivo.write(f"Total de ocorrencias completas sem UC: {total_ocorrencias_completas}\n")
        arquivo.write(f"Arquivo CSV: {caminho_ocorrencia_csv}\n")
        arquivo.write("\nResumo por regional:\n")
        for regional, qtd_ocorrencias, qtd_completas, qtd_interrupcoes, qtd_interrupcoes_sem_uc in resumo_ocorrencia:
            arquivo.write(
                f"{regional}|ocorrencias={qtd_ocorrencias}|"
                f"ocorrencias_completas_sem_uc={qtd_completas}|"
                f"interrupcoes_estado_4={qtd_interrupcoes}|"
                f"interrupcoes_sem_uc={qtd_interrupcoes_sem_uc}\n"
            )

    print(f"Ocorrencias com interrupcao sem UC apuravel: {total_ocorrencias}")
    print(f"Ocorrencias completas sem UC apuravel: {total_ocorrencias_completas}")
    print(f"Auditoria ocorrencia sem UC: {caminho_ocorrencia_csv}")
    print(f"Resumo ocorrencia sem UC: {caminho_ocorrencia_resumo}")

    return caminho_csv
