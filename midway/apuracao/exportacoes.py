from __future__ import annotations

from pathlib import Path

from midway.apuracao.duckdb_utils import normalizar_linhas_unix, sql_literal, tabela_local_existe


def exportar_bdo_interrupcao(
    con,
    *,
    export_dir: Path,
    data_arq: str,
    timestamp: str,
):
    export_dir.mkdir(parents=True, exist_ok=True)
    caminho_csv = export_dir / f"BDO_interupcao_{data_arq}.csv"

    if caminho_csv.exists():
        try:
            caminho_csv.unlink()
        except PermissionError:
            caminho_csv = export_dir / f"BDO_interupcao_{data_arq}_{timestamp}.csv"
            print(
                "Arquivo BDO do dia esta bloqueado pelo Windows; "
                f"exportando arquivo alternativo: {caminho_csv}"
            )

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_apuracao_previa
            ORDER BY
                REGIONAL,
                DATA_HORA_INIC_INTRP,
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP
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
    return caminho_csv

def exportar_gold_ressarcimento_prodist(
    con,
    *,
    marts_dir: Path,
    anomes: str,
    timestamp: str,
):
    if not tabela_local_existe(con, "gold_ressarcimento_prodist"):
        raise RuntimeError("Tabela gold_ressarcimento_prodist nao encontrada.")

    marts_dir.mkdir(parents=True, exist_ok=True)
    caminho_csv = marts_dir / f"Gold_Ressarcimento_PRODIST_{anomes}_{timestamp}.CSV"
    caminho_resumo = marts_dir / f"Gold_Ressarcimento_PRODIST_{anomes}_{timestamp}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_ressarcimento_prodist
            ORDER BY UC
        )
        TO '{caminho_csv.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )

    resumo = con.execute(
        """
        SELECT
            COUNT(*) AS REGISTROS,
            SUM(CASE WHEN COMP_TOTAL_PRODIST > 0 THEN 1 ELSE 0 END) AS UCS_COM_COMPENSACAO,
            COALESCE(SUM(COMP_DIC_PRODIST), 0) AS TOTAL_COMP_DIC_PRODIST,
            COALESCE(SUM(COMP_FIC_PRODIST), 0) AS TOTAL_COMP_FIC_PRODIST,
            COALESCE(SUM(COMP_DMIC_PRODIST), 0) AS TOTAL_COMP_DMIC_PRODIST,
            COALESCE(SUM(COMP_GERAL_CONTINUIDADE_PRODIST), 0) AS TOTAL_COMP_GERAL_CONTINUIDADE_PRODIST,
            COALESCE(SUM(COMP_DICRI_PRODIST), 0) AS TOTAL_COMP_DICRI_PRODIST,
            COALESCE(SUM(COMP_DISE_PRODIST), 0) AS TOTAL_COMP_DISE_PRODIST,
            COALESCE(SUM(COMP_TOTAL_PRODIST), 0) AS TOTAL_COMP_TOTAL_PRODIST,
            SUM(CASE WHEN STATUS_CALCULO_PRODIST = 'PARCIAL_AGREGADO_POR_UC' THEN 1 ELSE 0 END) AS UCS_DICRI_DISE_AGREGADO
        FROM gold_ressarcimento_prodist
        """
    ).fetchone()

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("GOLD RESSARCIMENTO PRODIST MODULO 8\n")
        arquivo.write(f"ANOMES: {anomes}\n")
        arquivo.write("Tabela: gold_ressarcimento_prodist\n")
        arquivo.write(f"Registros: {resumo[0]}\n")
        arquivo.write(f"UCs com compensacao: {resumo[1]}\n")
        arquivo.write(f"Total COMP_DIC_PRODIST: {resumo[2]}\n")
        arquivo.write(f"Total COMP_FIC_PRODIST: {resumo[3]}\n")
        arquivo.write(f"Total COMP_DMIC_PRODIST: {resumo[4]}\n")
        arquivo.write(f"Total COMP_GERAL_CONTINUIDADE_PRODIST: {resumo[5]}\n")
        arquivo.write(f"Total COMP_DICRI_PRODIST: {resumo[6]}\n")
        arquivo.write(f"Total COMP_DISE_PRODIST: {resumo[7]}\n")
        arquivo.write(f"Total COMP_TOTAL_PRODIST: {resumo[8]}\n")
        arquivo.write(f"UCs com DICRI/DISE agregado por UC: {resumo[9]}\n")
        arquivo.write("Observacao: DICRI/DISE ainda devem evoluir para calculo por evento.\n")
        arquivo.write(f"CSV: {caminho_csv}\n")

    print(f"gold_ressarcimento_prodist criada. Registros: {resumo[0]:,}")
    print(f"Conferencia ressarcimento PRODIST: {caminho_csv}")
    return caminho_csv

def exportar_gold_continuidade_uc(
    con,
    *,
    marts_dir: Path,
    anomes: str,
    timestamp: str,
):
    marts_dir.mkdir(parents=True, exist_ok=True)
    caminho_csv = marts_dir / f"Gold_Continuidade_UC_{anomes}_{timestamp}.CSV"
    caminho_resumo = marts_dir / f"Gold_Continuidade_UC_{anomes}_{timestamp}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_continuidade_uc
            ORDER BY UC
        )
        TO '{caminho_csv.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )

    total = con.execute("SELECT COUNT(*) FROM gold_continuidade_uc").fetchone()[0]
    faturadas = con.execute(
        "SELECT COUNT(*) FROM gold_continuidade_uc WHERE FATURADA = 'S'"
    ).fetchone()[0]
    ultrapassou_dic = con.execute(
        'SELECT COUNT(*) FROM gold_continuidade_uc WHERE "%_ULTRAPASSOU_META_DIC" > 0'
    ).fetchone()[0]
    ultrapassou_fic = con.execute(
        'SELECT COUNT(*) FROM gold_continuidade_uc WHERE "%_ULTRAPASSOU_META_FIC" > 0'
    ).fetchone()[0]
    ultrapassou_dmic = con.execute(
        'SELECT COUNT(*) FROM gold_continuidade_uc WHERE "%_ULTRAPASSOU_META_DMIC" > 0'
    ).fetchone()[0]
    ultrapassou_dicri = con.execute(
        'SELECT COUNT(*) FROM gold_continuidade_uc WHERE "%_ULTRAPASSOU_META_DICRI" > 0'
    ).fetchone()[0]
    ultrapassou_dise = con.execute(
        'SELECT COUNT(*) FROM gold_continuidade_uc WHERE "%_ULTRAPASSOU_META_DISE" > 0'
    ).fetchone()[0]
    ucs_base_comp_reduzida = con.execute(
        """
        SELECT COUNT(*)
        FROM gold_continuidade_uc
        WHERE COALESCE(DIC, 0) <> COALESCE(DIC_BASE_COMPENSACAO, 0)
           OR COALESCE(FIC, 0) <> COALESCE(FIC_BASE_COMPENSACAO, 0)
           OR COALESCE(DMIC, 0) <> COALESCE(DMIC_BASE_COMPENSACAO, 0)
           OR COALESCE(DIC_DICRI, 0) <> COALESCE(DICRI_BASE_COMPENSACAO, 0)
           OR COALESCE(DIC_ISE, 0) <> COALESCE(DISE_BASE_COMPENSACAO, 0)
        """
    ).fetchone()[0]
    ucs_chave_particular = con.execute(
        "SELECT COUNT(*) FROM gold_continuidade_uc WHERE CHAVE_PARTICULAR = 'S'"
    ).fetchone()[0]
    ucs_acessantes = con.execute(
        "SELECT COUNT(*) FROM gold_continuidade_uc WHERE UC_ACESSANTE_COMPENSACAO = 'S'"
    ).fetchone()[0]
    ucs_comp52 = con.execute(
        "SELECT COUNT(*) FROM gold_continuidade_uc WHERE COMP52 = 'S'"
    ).fetchone()[0]
    ucs_causa71 = con.execute(
        "SELECT COUNT(*) FROM gold_continuidade_uc WHERE CAUSA71 = 'S'"
    ).fetchone()[0]
    ucs_comp52_causa71 = con.execute(
        "SELECT COUNT(*) FROM gold_continuidade_uc WHERE COMP52_CAUSA71 = 'S'"
    ).fetchone()[0]
    ucs_posto_particular = con.execute(
        "SELECT COUNT(*) FROM gold_continuidade_uc WHERE POSTO_PARTICULAR = 'S'"
    ).fetchone()[0]
    ucs_nao_faturadas = con.execute(
        """
        SELECT COUNT(*)
        FROM gold_continuidade_uc
        WHERE FATURADA <> 'S'
          AND (
                COALESCE(DIC, 0) > 0
             OR COALESCE(FIC, 0) > 0
             OR COALESCE(DMIC, 0) > 0
             OR COALESCE(DIC_DICRI, 0) > 0
             OR COALESCE(DIC_ISE, 0) > 0
          )
        """
    ).fetchone()[0]
    soma_comp_dic = con.execute(
        "SELECT COALESCE(SUM(COMP_DIC), 0) FROM gold_continuidade_uc"
    ).fetchone()[0]
    soma_comp_fic = con.execute(
        "SELECT COALESCE(SUM(COMP_FIC), 0) FROM gold_continuidade_uc"
    ).fetchone()[0]
    soma_comp_dmic = con.execute(
        "SELECT COALESCE(SUM(COMP_DMIC), 0) FROM gold_continuidade_uc"
    ).fetchone()[0]
    soma_comp_dicri = con.execute(
        "SELECT COALESCE(SUM(COMP_DICRI), 0) FROM gold_continuidade_uc"
    ).fetchone()[0]
    soma_comp_dise = con.execute(
        "SELECT COALESCE(SUM(COMP_DISE), 0) FROM gold_continuidade_uc"
    ).fetchone()[0]
    soma_comp_geral = con.execute(
        "SELECT COALESCE(SUM(COMP_GERAL), 0) FROM gold_continuidade_uc"
    ).fetchone()[0]

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("GOLD CONTINUIDADE UC\n")
        arquivo.write(f"ANOMES: {anomes}\n")
        arquivo.write("Tabela: gold_continuidade_uc\n")
        arquivo.write(f"Registros: {total}\n")
        arquivo.write(f"UCs faturadas: {faturadas}\n")
        arquivo.write(f"UCs ultrapassou META_DIC: {ultrapassou_dic}\n")
        arquivo.write(f"UCs ultrapassou META_FIC: {ultrapassou_fic}\n")
        arquivo.write(f"UCs ultrapassou META_DMIC: {ultrapassou_dmic}\n")
        arquivo.write(f"UCs ultrapassou META_DICRI: {ultrapassou_dicri}\n")
        arquivo.write(f"UCs ultrapassou META_DISE: {ultrapassou_dise}\n")
        arquivo.write(f"UCs com CHAVE_PARTICULAR='S': {ucs_chave_particular}\n")
        arquivo.write(f"UCs com UC_ACESSANTE='S' e compensacao zerada: {ucs_acessantes}\n")
        arquivo.write(f"UCs com COMP52='S': {ucs_comp52}\n")
        arquivo.write(f"UCs com CAUSA71='S': {ucs_causa71}\n")
        arquivo.write(f"UCs com COMP52_CAUSA71='S': {ucs_comp52_causa71}\n")
        arquivo.write(f"UCs com POSTO_PARTICULAR='S': {ucs_posto_particular}\n")
        arquivo.write(f"UCs nao faturadas com indicadores e compensacao zerada: {ucs_nao_faturadas}\n")
        arquivo.write(f"UCs com base de compensacao reduzida por filtros de compensacao: {ucs_base_comp_reduzida}\n")
        arquivo.write(f"Soma COMP_DIC: {soma_comp_dic}\n")
        arquivo.write(f"Soma COMP_FIC: {soma_comp_fic}\n")
        arquivo.write(f"Soma COMP_DMIC: {soma_comp_dmic}\n")
        arquivo.write(f"Soma COMP_DICRI: {soma_comp_dicri}\n")
        arquivo.write(f"Soma COMP_DISE: {soma_comp_dise}\n")
        arquivo.write(f"Soma COMP_GERAL: {soma_comp_geral}\n")
        arquivo.write(f"CSV: {caminho_csv}\n")

    print(f"gold_continuidade_uc criada. Registros: {total:,}")
    print(f"Conferencia continuidade UC: {caminho_csv}")

    return caminho_csv
