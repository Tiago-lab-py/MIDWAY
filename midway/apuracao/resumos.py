from __future__ import annotations

from pathlib import Path


def gerar_resumo(
    con,
    caminho_csv,
    *,
    marts_dir: Path,
    timestamp: str,
    anomes: str,
    processed_duckdb_path: Path,
    tabela_gold_consumidores_existe,
):
    marts_dir.mkdir(parents=True, exist_ok=True)
    caminho_resumo = marts_dir / f"Apuracao_Previa_{timestamp}_RESUMO.TXT"
    fonte_consumidores = (
        "gold_consumidores"
        if tabela_gold_consumidores_existe(con)
        else "TOTAL_CONSUMIDORES do .env"
    )

    qtd_gold = con.execute("SELECT COUNT(*) FROM gold_interrupcao_tratada").fetchone()[0]
    qtd_uc = con.execute("SELECT COUNT(*) FROM gold_apuracao_uc").fetchone()[0]
    qtd_bdo = con.execute("SELECT COUNT(*) FROM gold_apuracao_previa").fetchone()[0]
    diag_gold = con.execute(
        """
        SELECT
            SUM(CASE WHEN INTERRUPCAO_LONGA = 'SIM' THEN 1 ELSE 0 END) AS QTD_LONGA,
            SUM(CASE WHEN INTERRUPCAO_CONTABILIZAVEL = 'SIM' THEN 1 ELSE 0 END) AS QTD_CONTABILIZAVEL,
            SUM(CASE WHEN INTERRUPCAO_LONGA = 'SIM'
                      AND INTERRUPCAO_CONTABILIZAVEL = 'SIM'
                     THEN 1 ELSE 0 END) AS QTD_ENTRA_CI_CHI,
            MIN(DURACAO_HORA) AS MIN_DURACAO_HORA,
            MAX(DURACAO_HORA) AS MAX_DURACAO_HORA
        FROM gold_apuracao_uc
        """
    ).fetchone()
    ci_bruto_total, chi_bruto_total, ci_liquido_total, chi_liquido_total = con.execute(
        """
        SELECT
            COALESCE(SUM(CI_BRUTO), 0) AS CI_BRUTO_TOTAL,
            COALESCE(SUM(CHI_BRUTO), 0) AS CHI_BRUTO_TOTAL,
            COALESCE(SUM(CI_LIQUIDO), 0) AS CI_LIQUIDO_TOTAL,
            COALESCE(SUM(CHI_LIQUIDO), 0) AS CHI_LIQUIDO_TOTAL
        FROM gold_apuracao_previa
        """
    ).fetchone()

    if tabela_gold_consumidores_existe(con):
        total_consumidores_global = con.execute(
            """
            SELECT UC_FATURADA
            FROM gold_consumidores
            WHERE REGIONAL_TOTAL = 'COPEL'
            LIMIT 1
            """
        ).fetchone()
        total_consumidores_global = (
            total_consumidores_global[0] if total_consumidores_global else None
        )
    else:
        total_consumidores_global = con.execute(
            "SELECT MAX(TOTAL_CONSUMIDORES) FROM gold_apuracao_previa"
        ).fetchone()[0]

    if total_consumidores_global:
        dec_bruto_total = chi_bruto_total / total_consumidores_global
        fec_bruto_total = ci_bruto_total / total_consumidores_global
        dec_liquido_total = chi_liquido_total / total_consumidores_global
        fec_liquido_total = ci_liquido_total / total_consumidores_global
    else:
        dec_bruto_total = None
        fec_bruto_total = None
        dec_liquido_total = None
        fec_liquido_total = None

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as resumo:
        resumo.write("APURACAO PREVIA IQS\n")
        resumo.write(f"ANOMES: {anomes}\n")
        resumo.write(f"DuckDB processado: {processed_duckdb_path}\n")
        resumo.write(f"Tabela gold: gold_interrupcao_tratada\n")
        resumo.write(f"Registros gold ESTADO_INTRP=4: {qtd_gold}\n")
        resumo.write(f"Registros UC apuraveis: {qtd_uc}\n")
        resumo.write(f"Registros BDO exportados: {qtd_bdo}\n")
        resumo.write(f"UCs com interrupcao longa: {diag_gold[0]}\n")
        resumo.write(f"UCs contabilizaveis sem manobra: {diag_gold[1]}\n")
        resumo.write(f"UCs que entram em CI/CHI: {diag_gold[2]}\n")
        resumo.write(f"Duracao hora minima: {diag_gold[3]}\n")
        resumo.write(f"Duracao hora maxima: {diag_gold[4]}\n")
        resumo.write(f"CI bruto total: {ci_bruto_total}\n")
        resumo.write(f"CHI bruto total: {chi_bruto_total}\n")
        resumo.write(f"CI liquido total: {ci_liquido_total}\n")
        resumo.write(f"CHI liquido total: {chi_liquido_total}\n")
        resumo.write(f"Fonte total consumidores: {fonte_consumidores}\n")
        resumo.write(f"Total consumidores: {total_consumidores_global}\n")
        resumo.write(f"DEC bruto total: {dec_bruto_total}\n")
        resumo.write(f"FEC bruto total: {fec_bruto_total}\n")
        resumo.write(f"DEC liquido total: {dec_liquido_total}\n")
        resumo.write(f"FEC liquido total: {fec_liquido_total}\n")
        resumo.write(f"Arquivo BDO: {caminho_csv}\n")
        resumo.write("Separador: |\n")
        resumo.write("Terminador de linha: UNIX LF\n")

    return caminho_resumo

def obter_resumo_compensacao(con):
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

    if "gold_continuidade_uc" not in tabelas:
        return {
            "COMP_DIC": 0,
            "COMP_FIC": 0,
            "COMP_DMIC": 0,
            "COMP_DICRI": 0,
            "COMP_DISE": 0,
            "COMP_GERAL": 0,
        }

    linha = con.execute(
        """
        SELECT
            COALESCE(SUM(COMP_DIC), 0) AS COMP_DIC,
            COALESCE(SUM(COMP_FIC), 0) AS COMP_FIC,
            COALESCE(SUM(COMP_DMIC), 0) AS COMP_DMIC,
            COALESCE(SUM(COMP_DICRI), 0) AS COMP_DICRI,
            COALESCE(SUM(COMP_DISE), 0) AS COMP_DISE,
            COALESCE(SUM(COMP_GERAL), 0) AS COMP_GERAL
        FROM gold_continuidade_uc
        """
    ).fetchone()

    return {
        "COMP_DIC": linha[0],
        "COMP_FIC": linha[1],
        "COMP_DMIC": linha[2],
        "COMP_DICRI": linha[3],
        "COMP_DISE": linha[4],
        "COMP_GERAL": linha[5],
    }

def anexar_compensacao_resumo_principal(
    con,
    *,
    export_dir: Path,
    anomes: str,
    obter_resumo_compensacao,
):
    arquivos = sorted(
        export_dir.glob(f"Apuracao_Previa_{anomes}*_RESUMO.TXT"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not arquivos:
        arquivos = sorted(
            export_dir.glob("Apuracao_Previa_*_RESUMO.TXT"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    if not arquivos:
        return None

    caminho_resumo = arquivos[0]
    conteudo = caminho_resumo.read_text(encoding="utf-8")
    if "COMP_GERAL total:" in conteudo:
        return caminho_resumo

    resumo_compensacao = obter_resumo_compensacao(con)
    with caminho_resumo.open("a", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(f"COMP_DIC total: {resumo_compensacao['COMP_DIC']}\n")
        arquivo.write(f"COMP_FIC total: {resumo_compensacao['COMP_FIC']}\n")
        arquivo.write(f"COMP_DMIC total: {resumo_compensacao['COMP_DMIC']}\n")
        arquivo.write(f"COMP_DICRI total: {resumo_compensacao['COMP_DICRI']}\n")
        arquivo.write(f"COMP_DISE total: {resumo_compensacao['COMP_DISE']}\n")
        arquivo.write(f"COMP_GERAL total: {resumo_compensacao['COMP_GERAL']}\n")

    print(f"Resumo principal atualizado com compensacoes: {caminho_resumo}")
    return caminho_resumo
