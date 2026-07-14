from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd


ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DIR = BASE_DIR / "processed"
EXPORT_DIR = BASE_DIR / "export" / "suspeita_falha_RA"


def processed_path(anomes: str = ANOMES) -> Path:
    return PROCESSED_DIR / f"iqs_adms_processed_{anomes}.duckdb"


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE lower(table_name) = lower(?)
            """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


def _required_tables(con: duckdb.DuckDBPyConnection) -> None:
    required = [
        "gold_interrupcao_tratada",
        "gold_apuracao_uc",
        "gold_ressarcimento_prodist",
        "gold_reclamacao_ocorrencia_resumo",
    ]
    missing = [table for table in required if not _table_exists(con, table)]
    if missing:
        raise RuntimeError("Tabelas obrigatórias ausentes no processado: " + ", ".join(missing))


def _query_base() -> str:
    return """
        WITH interrupcoes_ra AS (
            SELECT
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                MAX(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), '')) AS REGIONAL,
                MAX(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '')) AS CONJUNTO,
                MAX(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')) AS ALIM_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS NUM_OPER_CHV_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_GEO_CHV_INTRP AS VARCHAR)), '')) AS NUM_GEO_CHV_INTRP,
                MAX(NULLIF(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR)), '')) AS TIPO_CHV_INTRP,
                MAX(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), '')) AS COD_COMP_INTRP,
                MAX(LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_CAUSA_INTRP,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                DATE(MIN(DATA_HORA_INIC_INTRP)) AS DIA_OPERACAO,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_INTERRUPCAO
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
              AND UPPER(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR))) = 'RA'
              AND NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '') IS NOT NULL
              AND DATA_HORA_INIC_INTRP IS NOT NULL
            GROUP BY 1
        ),
        apuracao_seq AS (
            SELECT
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_APURAVEIS,
                SUM(COALESCE(TRY_CAST(CI_LIQUIDO AS DOUBLE), 0)) AS CI_LIQUIDO,
                SUM(COALESCE(TRY_CAST(CHI_LIQUIDO AS DOUBLE), 0)) AS CHI_LIQUIDO,
                MAX(COALESCE(TRY_CAST(DURACAO_HORA AS DOUBLE), 0)) AS DURACAO_MAX_HORA
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1
        ),
        reclamacoes AS (
            SELECT
                TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                SUM(COALESCE(QTD_RECLAMACOES, 0)) AS QTD_RECLAMACOES,
                SUM(COALESCE(QTD_UCS_RECLAMANTES, 0)) AS QTD_UCS_RECLAMANTES
            FROM gold_reclamacao_ocorrencia_resumo
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1
        ),
        uc_ocorrencia AS (
            SELECT DISTINCT
                TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS NUM_UC_UCI
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
        ),
        uc_peso AS (
            SELECT
                NUM_UC_UCI,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS_UC
            FROM uc_ocorrencia
            GROUP BY 1
        ),
        ressarcimento_seq AS (
            SELECT
                u.NUM_SEQ_INTRP,
                SUM(COALESCE(r.COMP_FIC_PRODIST, 0) / NULLIF(COALESCE(p.QTD_OCORRENCIAS_UC, 1), 0)) AS COMP_FIC_ESTIMADA,
                SUM(COALESCE(r.COMP_TOTAL_PRODIST, 0) / NULLIF(COALESCE(p.QTD_OCORRENCIAS_UC, 1), 0)) AS COMP_TOTAL_ESTIMADA,
                COUNT(DISTINCT CASE WHEN COALESCE(r.COMP_FIC_PRODIST, 0) > 0 THEN u.NUM_UC_UCI END) AS UCS_COM_COMP_FIC,
                COUNT(DISTINCT CASE WHEN COALESCE(r.COMP_TOTAL_PRODIST, 0) > 0 THEN u.NUM_UC_UCI END) AS UCS_COM_COMP_TOTAL
            FROM uc_ocorrencia u
            LEFT JOIN gold_ressarcimento_prodist r
              ON u.NUM_UC_UCI = TRIM(CAST(r.UC AS VARCHAR))
            LEFT JOIN uc_peso p
              ON u.NUM_UC_UCI = p.NUM_UC_UCI
            GROUP BY 1
        )
        SELECT
            i.*,
            COALESCE(a.UCS_APURAVEIS, i.UCS_INTERRUPCAO) AS UCS_APURAVEIS,
            COALESCE(a.CI_LIQUIDO, 0) AS CI_LIQUIDO,
            COALESCE(a.CHI_LIQUIDO, 0) AS CHI_LIQUIDO,
            COALESCE(a.DURACAO_MAX_HORA, 0) AS DURACAO_MAX_HORA,
            COALESCE(r.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
            COALESCE(r.QTD_UCS_RECLAMANTES, 0) AS QTD_UCS_RECLAMANTES,
            COALESCE(rs.COMP_FIC_ESTIMADA, 0) AS COMP_FIC_ESTIMADA,
            COALESCE(rs.COMP_TOTAL_ESTIMADA, 0) AS COMP_TOTAL_ESTIMADA,
            COALESCE(rs.UCS_COM_COMP_FIC, 0) AS UCS_COM_COMP_FIC,
            COALESCE(rs.UCS_COM_COMP_TOTAL, 0) AS UCS_COM_COMP_TOTAL
        FROM interrupcoes_ra i
        LEFT JOIN apuracao_seq a
          ON i.NUM_SEQ_INTRP = a.NUM_SEQ_INTRP
        LEFT JOIN reclamacoes r
          ON i.NUM_OCORRENCIA_ADMS = r.NUM_OCORRENCIA_ADMS
        LEFT JOIN ressarcimento_seq rs
          ON i.NUM_SEQ_INTRP = rs.NUM_SEQ_INTRP
    """


def _query_alimentador_dia(min_fic_consumidor_dia: int) -> str:
    min_fic = max(int(min_fic_consumidor_dia), 1)
    return f"""
        WITH interrupcoes_ra AS (
            SELECT
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                MAX(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), '')) AS REGIONAL,
                MAX(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '')) AS CONJUNTO,
                MAX(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')) AS ALIM_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS NUM_OPER_CHV_INTRP,
                DATE(MIN(DATA_HORA_INIC_INTRP)) AS DIA_OPERACAO
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
              AND UPPER(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR))) = 'RA'
              AND NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '') IS NOT NULL
              AND DATA_HORA_INIC_INTRP IS NOT NULL
            GROUP BY 1
        ),
        reclamacoes AS (
            SELECT
                TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                SUM(COALESCE(QTD_RECLAMACOES, 0)) AS QTD_RECLAMACOES,
                SUM(COALESCE(QTD_UCS_RECLAMANTES, 0)) AS QTD_UCS_RECLAMANTES
            FROM gold_reclamacao_ocorrencia_resumo
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1
        ),
        ra_alimentador AS (
            SELECT
                REGIONAL,
                CONJUNTO,
                ALIM_INTRP,
                DIA_OPERACAO,
                COUNT(DISTINCT NUM_SEQ_INTRP) AS QTD_RA_ALIM_DIA,
                COUNT(DISTINCT NUM_OPER_CHV_INTRP) AS QTD_EQUIPAMENTOS_RA_ALIM_DIA
            FROM interrupcoes_ra
            GROUP BY 1, 2, 3, 4
        ),
        ocorrencias_alimentador AS (
            SELECT DISTINCT
                REGIONAL,
                CONJUNTO,
                ALIM_INTRP,
                DIA_OPERACAO,
                NUM_OCORRENCIA_ADMS
            FROM interrupcoes_ra
            WHERE NUM_OCORRENCIA_ADMS IS NOT NULL
        ),
        reclamacoes_alimentador AS (
            SELECT
                o.REGIONAL,
                o.CONJUNTO,
                o.ALIM_INTRP,
                o.DIA_OPERACAO,
                SUM(COALESCE(r.QTD_RECLAMACOES, 0)) AS QTD_RECLAMACOES_ALIM_DIA,
                SUM(COALESCE(r.QTD_UCS_RECLAMANTES, 0)) AS QTD_UCS_RECLAMANTES_ALIM_DIA
            FROM ocorrencias_alimentador o
            LEFT JOIN reclamacoes r
              ON o.NUM_OCORRENCIA_ADMS = r.NUM_OCORRENCIA_ADMS
            GROUP BY 1, 2, 3, 4
        ),
        fic_uc_alimentador AS (
            SELECT
                i.REGIONAL,
                i.CONJUNTO,
                i.ALIM_INTRP,
                i.DIA_OPERACAO,
                TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)) AS NUM_UC_UCI,
                COUNT(DISTINCT i.NUM_SEQ_INTRP) AS FIC_UC_ALIM_DIA
            FROM gold_apuracao_uc a
            JOIN interrupcoes_ra i
              ON TRIM(CAST(a.NUM_SEQ_INTRP AS VARCHAR)) = i.NUM_SEQ_INTRP
            WHERE NULLIF(TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5
        ),
        fic_recorrente AS (
            SELECT
                REGIONAL,
                CONJUNTO,
                ALIM_INTRP,
                DIA_OPERACAO,
                COUNT(DISTINCT NUM_UC_UCI) AS UCS_FIC_RECORRENTE_ALIM_DIA
            FROM fic_uc_alimentador
            WHERE FIC_UC_ALIM_DIA >= {min_fic}
            GROUP BY 1, 2, 3, 4
        )
        SELECT
            r.REGIONAL,
            r.CONJUNTO,
            r.ALIM_INTRP,
            r.DIA_OPERACAO,
            r.QTD_RA_ALIM_DIA,
            r.QTD_EQUIPAMENTOS_RA_ALIM_DIA,
            COALESCE(f.UCS_FIC_RECORRENTE_ALIM_DIA, 0) AS UCS_FIC_RECORRENTE_ALIM_DIA,
            COALESCE(c.QTD_RECLAMACOES_ALIM_DIA, 0) AS QTD_RECLAMACOES_ALIM_DIA,
            COALESCE(c.QTD_UCS_RECLAMANTES_ALIM_DIA, 0) AS QTD_UCS_RECLAMANTES_ALIM_DIA
        FROM ra_alimentador r
        LEFT JOIN fic_recorrente f
          ON r.REGIONAL = f.REGIONAL
         AND r.CONJUNTO = f.CONJUNTO
         AND r.ALIM_INTRP = f.ALIM_INTRP
         AND r.DIA_OPERACAO = f.DIA_OPERACAO
        LEFT JOIN reclamacoes_alimentador c
          ON r.REGIONAL = c.REGIONAL
         AND r.CONJUNTO = c.CONJUNTO
         AND r.ALIM_INTRP = c.ALIM_INTRP
         AND r.DIA_OPERACAO = c.DIA_OPERACAO
    """


def analisar_suspeita_falha_ra(
    anomes: str = ANOMES,
    db_path: str | Path | None = None,
    min_ocorrencias_dia: int = 2,
    min_ci_liquido: float = 10,
    min_comp_fic: float = 1,
    min_fic_consumidor_dia: int = 3,
    consumidores_por_reclamacao: int = 250,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    db_path = Path(db_path) if db_path else processed_path(anomes)
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB processado nao encontrado: {db_path}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        _required_tables(con)
        ocorrencias = con.execute(
            f"""
            SELECT *
            FROM ({_query_base()})
            """
        ).fetchdf()
        contexto_alimentador = con.execute(_query_alimentador_dia(min_fic_consumidor_dia)).fetchdf()

    if ocorrencias.empty:
        return ocorrencias, pd.DataFrame()

    grouped = (
        ocorrencias.groupby(
            ["REGIONAL", "CONJUNTO", "ALIM_INTRP", "NUM_OPER_CHV_INTRP", "DIA_OPERACAO"],
            dropna=False,
            as_index=False,
        )
        .agg(
            QTD_OCORRENCIAS_RA=("NUM_SEQ_INTRP", "nunique"),
            PRIMEIRA_INTERRUPCAO=("DATA_HORA_INIC_INTRP", "min"),
            ULTIMA_INTERRUPCAO=("DATA_HORA_INIC_INTRP", "max"),
            NUM_OCORRENCIAS_ADMS=("NUM_OCORRENCIA_ADMS", lambda values: ", ".join(sorted({str(value) for value in values if value}))),
            NUM_SEQ_INTRP=("NUM_SEQ_INTRP", lambda values: ", ".join(sorted({str(value) for value in values if value}))),
            COD_COMP_INTRP=("COD_COMP_INTRP", lambda values: ", ".join(sorted({str(value) for value in values if value}))),
            COD_CAUSA_INTRP=("COD_CAUSA_INTRP", lambda values: ", ".join(sorted({str(value) for value in values if value}))),
            UCS_APURAVEIS=("UCS_APURAVEIS", "sum"),
            CI_LIQUIDO_TOTAL=("CI_LIQUIDO", "sum"),
            CHI_LIQUIDO_TOTAL=("CHI_LIQUIDO", "sum"),
            DURACAO_MAX_HORA=("DURACAO_MAX_HORA", "max"),
            QTD_RECLAMACOES_TOTAL=("QTD_RECLAMACOES", "sum"),
            QTD_UCS_RECLAMANTES_TOTAL=("QTD_UCS_RECLAMANTES", "sum"),
            QTD_OCORRENCIAS_COM_RECLAMACAO=("QTD_RECLAMACOES", lambda values: int((values > 0).sum())),
            COMP_FIC_ESTIMADA=("COMP_FIC_ESTIMADA", "sum"),
            COMP_TOTAL_ESTIMADA=("COMP_TOTAL_ESTIMADA", "sum"),
            UCS_COM_COMP_FIC=("UCS_COM_COMP_FIC", "sum"),
            UCS_COM_COMP_TOTAL=("UCS_COM_COMP_TOTAL", "sum"),
        )
    )
    grouped = grouped.merge(
        contexto_alimentador,
        on=["REGIONAL", "CONJUNTO", "ALIM_INTRP", "DIA_OPERACAO"],
        how="left",
    )
    colunas_contexto = [
        "QTD_RA_ALIM_DIA",
        "QTD_EQUIPAMENTOS_RA_ALIM_DIA",
        "UCS_FIC_RECORRENTE_ALIM_DIA",
        "QTD_RECLAMACOES_ALIM_DIA",
        "QTD_UCS_RECLAMANTES_ALIM_DIA",
    ]
    grouped[colunas_contexto] = grouped[colunas_contexto].fillna(0)
    divisor_reclamacao = max(int(consumidores_por_reclamacao), 1)
    grouped["RECLAMACOES_MINIMAS_ALIM_DIA"] = grouped["UCS_FIC_RECORRENTE_ALIM_DIA"].apply(
        lambda value: int((int(value) + divisor_reclamacao - 1) // divisor_reclamacao)
        if int(value) >= divisor_reclamacao
        else 0
    )
    grouped["RELACAO_UCS_FIC_RECORRENTE_POR_RECLAMACAO"] = grouped.apply(
        lambda row: row["UCS_FIC_RECORRENTE_ALIM_DIA"] / max(float(row["QTD_RECLAMACOES_ALIM_DIA"]), 1.0),
        axis=1,
    )
    grouped["SINAL_ZERO_RECLAMACAO_EQUIPAMENTO"] = (
        grouped["QTD_OCORRENCIAS_COM_RECLAMACAO"].eq(0) & grouped["COMP_FIC_ESTIMADA"].ge(float(min_comp_fic))
    )
    grouped["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"] = (
        grouped["RECLAMACOES_MINIMAS_ALIM_DIA"].gt(0)
        & grouped["QTD_RECLAMACOES_ALIM_DIA"].lt(grouped["RECLAMACOES_MINIMAS_ALIM_DIA"])
    )
    grouped["JANELA_MINUTOS"] = (
        pd.to_datetime(grouped["ULTIMA_INTERRUPCAO"]) - pd.to_datetime(grouped["PRIMEIRA_INTERRUPCAO"])
    ).dt.total_seconds().fillna(0) / 60
    grouped["SCORE_SUSPEITA_RA"] = (
        (grouped["QTD_OCORRENCIAS_RA"] * 20)
        + grouped["CI_LIQUIDO_TOTAL"].clip(upper=100)
        + (grouped["COMP_FIC_ESTIMADA"] / 1000).clip(upper=40)
        + grouped["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"].astype(int) * 20
        + (grouped["JANELA_MINUTOS"].le(24 * 60).astype(int) * 10)
    ).clip(upper=100)
    grouped["CLASSIFICACAO"] = grouped.apply(
        lambda row: "CRITICA_BAIXA_RECLAMACAO_ALIM_CONJUNTO"
        if row["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"]
        else (
            "SUSPEITA_FORTE_FALHA_COMUNICACAO_RA"
            if row["QTD_OCORRENCIAS_RA"] >= 3 or row["COMP_FIC_ESTIMADA"] >= 1000
            else "SUSPEITA_FALHA_COMUNICACAO_RA"
        ),
        axis=1,
    )

    resumo = grouped[
        (grouped["QTD_OCORRENCIAS_RA"] >= int(min_ocorrencias_dia))
        & (grouped["CI_LIQUIDO_TOTAL"] >= float(min_ci_liquido))
        & (grouped["SINAL_ZERO_RECLAMACAO_EQUIPAMENTO"] | grouped["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"])
    ].sort_values(
        ["SCORE_SUSPEITA_RA", "COMP_FIC_ESTIMADA", "CI_LIQUIDO_TOTAL", "QTD_OCORRENCIAS_RA"],
        ascending=[False, False, False, False],
    )

    detalhe = ocorrencias.merge(
        resumo[
            [
                "REGIONAL",
                "CONJUNTO",
                "ALIM_INTRP",
                "NUM_OPER_CHV_INTRP",
                "DIA_OPERACAO",
                "CLASSIFICACAO",
                "SCORE_SUSPEITA_RA",
                "QTD_OCORRENCIAS_RA",
                "SINAL_ZERO_RECLAMACAO_EQUIPAMENTO",
                "SINAL_BAIXA_RECLAMACAO_ALIM_DIA",
                "UCS_FIC_RECORRENTE_ALIM_DIA",
                "QTD_RECLAMACOES_ALIM_DIA",
                "RECLAMACOES_MINIMAS_ALIM_DIA",
            ]
        ],
        on=["REGIONAL", "CONJUNTO", "ALIM_INTRP", "NUM_OPER_CHV_INTRP", "DIA_OPERACAO"],
        how="inner",
    ).sort_values(["SCORE_SUSPEITA_RA", "NUM_OPER_CHV_INTRP", "DATA_HORA_INIC_INTRP"], ascending=[False, True, True])

    return detalhe, resumo


def gerar_exportacao_suspeita_falha_ra(
    anomes: str = ANOMES,
    db_path: str | Path | None = None,
    min_ocorrencias_dia: int = 2,
    min_ci_liquido: float = 10,
    min_comp_fic: float = 1,
    min_fic_consumidor_dia: int = 3,
    consumidores_por_reclamacao: int = 250,
) -> dict[str, object]:
    detalhe, resumo = analisar_suspeita_falha_ra(
        anomes=anomes,
        db_path=db_path,
        min_ocorrencias_dia=min_ocorrencias_dia,
        min_ci_liquido=min_ci_liquido,
        min_comp_fic=min_comp_fic,
        min_fic_consumidor_dia=min_fic_consumidor_dia,
        consumidores_por_reclamacao=consumidores_por_reclamacao,
    )

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    detalhe_path = EXPORT_DIR / f"Suspeita_Falha_RA_{anomes}_{timestamp}_DETALHE.CSV"
    resumo_path = EXPORT_DIR / f"Suspeita_Falha_RA_{anomes}_{timestamp}_EQUIPAMENTO_DIA.CSV"
    nota_path = EXPORT_DIR / f"Suspeita_Falha_RA_{anomes}_{timestamp}_NOTA.TXT"

    detalhe.to_csv(detalhe_path, sep=";", index=False, encoding="utf-8-sig")
    resumo.to_csv(resumo_path, sep=";", index=False, encoding="utf-8-sig")

    with nota_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("AGENTE SUSPEITA FALHA RA\n")
        file.write(f"ANOMES: {anomes}\n")
        file.write(f"Mínimo ocorrências por equipamento/dia: {min_ocorrencias_dia}\n")
        file.write(f"Mínimo CI/FIC líquido agregado: {min_ci_liquido}\n")
        file.write(f"Mínimo compensação FIC estimada: {min_comp_fic}\n")
        file.write(f"FIC recorrente por consumidor no alimentador/dia: >= {min_fic_consumidor_dia}\n")
        file.write(f"Regra proporcional reclamações: 1 a cada {consumidores_por_reclamacao} consumidores recorrentes\n")
        file.write(f"Equipamentos/dia suspeitos: {len(resumo)}\n")
        file.write(f"Ocorrências detalhadas: {len(detalhe)}\n")
        file.write(f"Resumo equipamento/dia: {resumo_path}\n")
        file.write(f"Detalhe ocorrências: {detalhe_path}\n")
        file.write(
            "Regra: religador automático com ocorrências sucessivas no mesmo equipamento e dia. "
            "Sinal alto quando não há reclamações vinculadas ao equipamento/dia e há compensação FIC; "
            "sinal crítico quando o alimentador/conjunto/dia tem consumidores com FIC recorrente "
            "e reclamações abaixo da proporção mínima esperada.\n"
        )

    return {
        "detalhe": detalhe_path,
        "resumo": resumo_path,
        "nota": nota_path,
        "linhas_detalhe": len(detalhe),
        "linhas_resumo": len(resumo),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agente de suspeita de falha de comunicação em religador automático.")
    parser.add_argument("anomes", nargs="?", default=ANOMES)
    parser.add_argument("--min-ocorrencias-dia", type=int, default=int(os.getenv("SUSPEITA_RA_MIN_OCORRENCIAS_DIA", "2")))
    parser.add_argument("--min-ci", type=float, default=float(os.getenv("SUSPEITA_RA_MIN_CI", "10")))
    parser.add_argument("--min-comp-fic", type=float, default=float(os.getenv("SUSPEITA_RA_MIN_COMP_FIC", "1")))
    parser.add_argument("--min-fic-consumidor-dia", type=int, default=int(os.getenv("SUSPEITA_RA_MIN_FIC_CONSUMIDOR_DIA", "3")))
    parser.add_argument("--consumidores-por-reclamacao", type=int, default=int(os.getenv("SUSPEITA_RA_CONSUMIDORES_POR_RECLAMACAO", "250")))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = gerar_exportacao_suspeita_falha_ra(
        anomes=args.anomes,
        min_ocorrencias_dia=args.min_ocorrencias_dia,
        min_ci_liquido=args.min_ci,
        min_comp_fic=args.min_comp_fic,
        min_fic_consumidor_dia=args.min_fic_consumidor_dia,
        consumidores_por_reclamacao=args.consumidores_por_reclamacao,
    )
    print("AGENTE SUSPEITA FALHA RA")
    print(f"Equipamentos/dia suspeitos: {result['linhas_resumo']}")
    print(f"Ocorrências detalhadas: {result['linhas_detalhe']}")
    print(f"Resumo: {result['resumo']}")
    print(f"Detalhe: {result['detalhe']}")
    print(f"Nota: {result['nota']}")


if __name__ == "__main__":
    main()
