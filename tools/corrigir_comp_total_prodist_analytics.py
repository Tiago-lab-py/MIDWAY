from pathlib import Path


NOVO_BLOCO = r'''

# >>> MIDWAY PATCH COMP_TOTAL_PRODIST ANALYTICS
import duckdb as _midway_analytics_duckdb


def _midway_comp_total_prodist_por_ocorrencia(db_path: str) -> dict[str, float]:
    """Calcula COMP_TOTAL_PRODIST por ocorrencia sem duplicar UC.

    Regra:
    COMP_TOTAL_PRODIST da ocorrencia = soma do COMP_TOTAL_PRODIST das UCs distintas
    vinculadas a NUM_OCORRENCIA_ADMS na gold_apuracao_uc.
    """
    with _midway_analytics_duckdb.connect(db_path, read_only=True) as con:
        rows = con.execute(
            """
            WITH ocorrencia_uc AS (
                SELECT DISTINCT
                    NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') AS NUM_OCORRENCIA_ADMS,
                    NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS UC
                FROM gold_apuracao_uc
                WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
                  AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            ),
            ressarcimento_uc AS (
                SELECT
                    NULLIF(TRIM(CAST(UC AS VARCHAR)), '') AS UC,
                    COALESCE(TRY_CAST(COMP_TOTAL_PRODIST AS DOUBLE), 0) AS COMP_TOTAL_PRODIST
                FROM gold_ressarcimento_prodist
                WHERE NULLIF(TRIM(CAST(UC AS VARCHAR)), '') IS NOT NULL
            )
            SELECT
                o.NUM_OCORRENCIA_ADMS,
                SUM(COALESCE(r.COMP_TOTAL_PRODIST, 0)) AS COMP_TOTAL_PRODIST
            FROM ocorrencia_uc o
            LEFT JOIN ressarcimento_uc r
              ON r.UC = o.UC
            GROUP BY o.NUM_OCORRENCIA_ADMS
            """
        ).fetchall()

    return {str(ocorrencia): float(valor or 0) for ocorrencia, valor in rows}


def _midway_corrigir_comp_total_prodist_df(df, db_path: str):
    if df is None or df.empty:
        return df

    if "NUM_OCORRENCIA_ADMS" not in df.columns:
        return df

    coluna_comp = None
    for candidata in ("COMP_TOTAL_PRODIST", "↓ COMP_TOTAL_PRODIST", "COMP_ESTIMADA"):
        if candidata in df.columns:
            coluna_comp = candidata
            break

    if coluna_comp is None:
        return df

    mapa = _midway_comp_total_prodist_por_ocorrencia(db_path)
    ocorrencias = df["NUM_OCORRENCIA_ADMS"].astype(str)
    df[coluna_comp] = ocorrencias.map(mapa).fillna(0.0)
    return df
# <<< MIDWAY PATCH COMP_TOTAL_PRODIST ANALYTICS
'''


def encontrar_pagina() -> Path:
    candidatos = [
        Path("midway") / "web" / "pages" / "02_Analytics_Pos_Operacao.py",
        Path("midway") / "web" / "pages" / "02_Analytics_Pos_Operacao.py",
        Path("pages") / "02_Analytics_Pos_Operacao.py",
    ]
    for candidato in candidatos:
        if candidato.exists():
            return candidato
    raise FileNotFoundError(
        "Nao encontrei 02_Analytics_Pos_Operacao.py. Execute na raiz do projeto D:\\MIDWAY_novo."
    )


def inserir_bloco(texto: str) -> str:
    inicio = "# >>> MIDWAY PATCH COMP_TOTAL_PRODIST ANALYTICS"
    fim = "# <<< MIDWAY PATCH COMP_TOTAL_PRODIST ANALYTICS"
    if inicio in texto:
        pos_inicio = texto.index(inicio)
        pos_fim = texto.index(fim, pos_inicio) + len(fim)
        return texto[:pos_inicio].rstrip() + NOVO_BLOCO + texto[pos_fim:].lstrip()
    return texto.rstrip() + NOVO_BLOCO


def inserir_chamada_correcao(texto: str) -> str:
    alvo = "ranking_df = analytics_occurrences(db_path, min_score, sample_limit * 5)"
    chamada = (
        "ranking_df = analytics_occurrences(db_path, min_score, sample_limit * 5)\n"
        "    ranking_df = _midway_corrigir_comp_total_prodist_df(ranking_df, db_path)"
    )
    if chamada in texto:
        return texto
    if alvo in texto:
        return texto.replace(alvo, chamada, 1)

    alvo_alt = "ranking_df = analytics_occurrences(str(db_path), min_score, sample_limit * 5)"
    chamada_alt = (
        "ranking_df = analytics_occurrences(str(db_path), min_score, sample_limit * 5)\n"
        "    ranking_df = _midway_corrigir_comp_total_prodist_df(ranking_df, str(db_path))"
    )
    if chamada_alt in texto:
        return texto
    if alvo_alt in texto:
        return texto.replace(alvo_alt, chamada_alt, 1)

    raise RuntimeError(
        "Nao encontrei a linha ranking_df = analytics_occurrences(...). "
        "Ajuste manualmente chamando _midway_corrigir_comp_total_prodist_df apos gerar ranking_df."
    )


def main() -> None:
    pagina = encontrar_pagina()
    texto = pagina.read_text(encoding="utf-8")

    backup = pagina.with_suffix(".py.bak_comp_total_prodist")
    backup.write_text(texto, encoding="utf-8", newline="\n")

    atualizado = inserir_bloco(texto)
    atualizado = inserir_chamada_correcao(atualizado)
    pagina.write_text(atualizado, encoding="utf-8", newline="\n")

    print(f"Analytics atualizado: {pagina}")
    print(f"Backup criado: {backup}")
    print("COMP_TOTAL_PRODIST agora e recalculado por UC distinta da ocorrencia.")


if __name__ == "__main__":
    main()
