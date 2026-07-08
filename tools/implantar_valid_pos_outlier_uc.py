from pathlib import Path
import re


CAMINHO = Path("midway") / "web" / "library" / "avaliacao_uc.py"

NOVO_BLOCO = r'''
@st.cache_data(show_spinner=False)
def outlier_uc_ranking(db_path: str, sample_limit: int):
    valid_pos_expr = (
        "UPPER(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR)))"
        if _has_column(db_path, "gold_apuracao_uc", "VALID_POS_OPERACAO")
        else "'N'"
    )

    return query_df(
        db_path,
        f"""
        WITH eventos_uc AS (
            SELECT
                TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS UC,
                ANY_VALUE(REGIONAL) AS REGIONAL,
                ANY_VALUE(COD_CONJTO_ELET_ANEEL_INTRP) AS CONJUNTO,
                COUNT(*) AS QTD_INTERRUPCOES,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS,
                COUNT(DISTINCT CASE WHEN {valid_pos_expr} = 'S' THEN NUM_OCORRENCIA_ADMS END) AS QTD_OCORRENCIAS_VALIDADAS_POS,
                COUNT(DISTINCT CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN NUM_OCORRENCIA_ADMS END) AS QTD_OCORRENCIAS_PENDENTES_POS,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS FIC,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS DIC,
                MAX(COALESCE(CHI_LIQUIDO, 0)) AS DMIC,
                SUM(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN COALESCE(CI_LIQUIDO, 0) ELSE 0 END) AS FIC_PENDENTE_POS,
                SUM(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS DIC_PENDENTE_POS,
                MAX(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS DMIC_PENDENTE_POS,
                SUM(CASE WHEN COALESCE(DURACAO_HORA, 0) >= 24 THEN 1 ELSE 0 END) AS QTD_DURACAO_GE_24H,
                SUM(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' AND COALESCE(DURACAO_HORA, 0) >= 24 THEN 1 ELSE 0 END) AS QTD_DURACAO_GE_24H_PENDENTE_POS,
                SUM(CASE WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL THEN 1 ELSE 0 END) AS QTD_MANOBRA,
                COUNT(DISTINCT TIPO_PROTOC_JUSTIF_UCI) AS QTD_TIPOS_PROTOCOLO,
                COUNT(DISTINCT CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN TIPO_PROTOC_JUSTIF_UCI END) AS QTD_TIPOS_PROTOCOLO_PENDENTE_POS,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS CHI_TIPO_0,
                SUM(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS CHI_TIPO_0_PENDENTE_POS,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) <> '0' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS CHI_TIPO_NAO_0
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            GROUP BY TRIM(CAST(NUM_UC_UCI AS VARCHAR))
        ),
        continuidade AS (
            SELECT
                TRIM(CAST(UC AS VARCHAR)) AS UC,
                COALESCE(META_DIC, 0) AS META_DIC,
                COALESCE(META_FIC, 0) AS META_FIC,
                COALESCE(META_DMIC, 0) AS META_DMIC,
                COALESCE(COMP_TOTAL_PRODIST, 0) AS COMP_TOTAL_PRODIST
            FROM gold_ressarcimento_prodist
        ),
        score AS (
            SELECT
                e.*,
                c.META_DIC,
                c.META_FIC,
                c.META_DMIC,
                c.COMP_TOTAL_PRODIST,
                CASE
                    WHEN e.QTD_OCORRENCIAS_PENDENTES_POS > 0 THEN COALESCE(c.COMP_TOTAL_PRODIST, 0)
                    ELSE 0
                END AS COMP_TOTAL_PRODIST_PENDENTE_POS,
                CASE
                    WHEN e.QTD_OCORRENCIAS = e.QTD_OCORRENCIAS_VALIDADAS_POS AND e.QTD_OCORRENCIAS > 0 THEN 'Validado pós'
                    WHEN e.QTD_OCORRENCIAS_VALIDADAS_POS > 0 THEN 'Parcialmente validado'
                    ELSE 'Pendente pós'
                END AS STATUS_POS_OPERACAO,
                CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC / c.META_DIC * 100 ELSE 0 END AS PCT_META_DIC,
                CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC / c.META_FIC * 100 ELSE 0 END AS PCT_META_FIC,
                CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC / c.META_DMIC * 100 ELSE 0 END AS PCT_META_DMIC,
                CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC_PENDENTE_POS / c.META_DIC * 100 ELSE 0 END AS PCT_META_DIC_PENDENTE_POS,
                CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC_PENDENTE_POS / c.META_FIC * 100 ELSE 0 END AS PCT_META_FIC_PENDENTE_POS,
                CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC_PENDENTE_POS / c.META_DMIC * 100 ELSE 0 END AS PCT_META_DMIC_PENDENTE_POS,
                (
                    LEAST(CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC / c.META_DIC * 30 ELSE 0 END, 30)
                  + LEAST(CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC / c.META_FIC * 20 ELSE 0 END, 20)
                  + LEAST(CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC / c.META_DMIC * 20 ELSE 0 END, 20)
                  + LEAST(e.QTD_DURACAO_GE_24H * 10, 10)
                  + LEAST(e.QTD_TIPOS_PROTOCOLO * 5, 10)
                  + LEAST(COALESCE(c.COMP_TOTAL_PRODIST, 0) / 10000.0, 10)
                ) AS SCORE_OUTLIER_UC,
                (
                    LEAST(CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC_PENDENTE_POS / c.META_DIC * 30 ELSE 0 END, 30)
                  + LEAST(CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC_PENDENTE_POS / c.META_FIC * 20 ELSE 0 END, 20)
                  + LEAST(CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC_PENDENTE_POS / c.META_DMIC * 20 ELSE 0 END, 20)
                  + LEAST(e.QTD_DURACAO_GE_24H_PENDENTE_POS * 10, 10)
                  + LEAST(e.QTD_TIPOS_PROTOCOLO_PENDENTE_POS * 5, 10)
                  + LEAST(
                        CASE WHEN e.QTD_OCORRENCIAS_PENDENTES_POS > 0 THEN COALESCE(c.COMP_TOTAL_PRODIST, 0) ELSE 0 END / 10000.0,
                        10
                    )
                ) AS SCORE_OUTLIER_UC_PENDENTE
            FROM eventos_uc e
            LEFT JOIN continuidade c
              ON c.UC = e.UC
        )
        SELECT
            *,
            CASE
                WHEN SCORE_OUTLIER_UC >= 80 THEN 'Crítico'
                WHEN SCORE_OUTLIER_UC >= 60 THEN 'Alto'
                WHEN SCORE_OUTLIER_UC >= 40 THEN 'Médio'
                ELSE 'Baixo'
            END AS FAIXA_OUTLIER,
            CASE
                WHEN SCORE_OUTLIER_UC_PENDENTE >= 80 THEN 'Crítico'
                WHEN SCORE_OUTLIER_UC_PENDENTE >= 60 THEN 'Alto'
                WHEN SCORE_OUTLIER_UC_PENDENTE >= 40 THEN 'Médio'
                ELSE 'Baixo'
            END AS FAIXA_OUTLIER_PENDENTE
        FROM score
        ORDER BY
            SCORE_OUTLIER_UC_PENDENTE DESC,
            COMP_TOTAL_PRODIST_PENDENTE_POS DESC,
            DIC_PENDENTE_POS DESC,
            FIC_PENDENTE_POS DESC
        LIMIT {int(sample_limit)}
        """,
    )


def show_outlier_uc(db_path: str, sample_limit: int) -> None:
    st.subheader("Outlier UC")
    st.caption(
        "Ranking exploratório para localizar UCs com comportamento atípico em continuidade, "
        "protocolo, duração e compensação. Ocorrências com VALID_POS_OPERACAO = S deixam de pesar como pendência."
    )

    required_tables = ["gold_apuracao_uc", "gold_ressarcimento_prodist"]
    if not all(require_table(db_path, table_name) for table_name in required_tables):
        return

    col_score, col_faixa, col_pos = st.columns([1, 1, 1])
    with col_score:
        min_score = st.slider("Score mínimo pendente", 0, 100, 0, step=5)
    with col_faixa:
        faixa = st.selectbox("Faixa pendente", ["Todas", "Baixo", "Médio", "Alto", "Crítico"])
    with col_pos:
        filtro_pos = st.selectbox(
            "Validação Pós-Operação",
            ["Pendentes", "Todos", "Somente validados", "Parcialmente validados"],
        )

    ranking_df = outlier_uc_ranking(db_path, sample_limit * 5)
    if ranking_df.empty:
        st.success("Nenhum outlier UC encontrado.")
        return

    ranking_df = ranking_df[ranking_df["SCORE_OUTLIER_UC_PENDENTE"] >= min_score]
    if faixa != "Todas":
        ranking_df = ranking_df[ranking_df["FAIXA_OUTLIER_PENDENTE"] == faixa]

    if filtro_pos == "Pendentes":
        ranking_df = ranking_df[ranking_df["QTD_OCORRENCIAS_PENDENTES_POS"] > 0]
    elif filtro_pos == "Somente validados":
        ranking_df = ranking_df[ranking_df["QTD_OCORRENCIAS_PENDENTES_POS"] == 0]
    elif filtro_pos == "Parcialmente validados":
        ranking_df = ranking_df[ranking_df["STATUS_POS_OPERACAO"] == "Parcialmente validado"]

    ranking_df = ranking_df.head(sample_limit)

    if ranking_df.empty:
        st.success("Nenhum outlier UC encontrado para os filtros informados.")
        return

    show_metric_cards(
        [
            ("UCs exibidas", len(ranking_df), "Após filtros"),
            ("Pendências pós", ranking_df["QTD_OCORRENCIAS_PENDENTES_POS"].sum(), "Ocorrências não validadas"),
            ("Validadas pós", ranking_df["QTD_OCORRENCIAS_VALIDADAS_POS"].sum(), "Ocorrências já aceitas"),
            ("Comp. pendente", ranking_df["COMP_TOTAL_PRODIST_PENDENTE_POS"].sum(), "Estimativa do ranking"),
        ]
    )

    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SCORE_OUTLIER_UC_PENDENTE": st.column_config.ProgressColumn(
                "Score pendente",
                min_value=0,
                max_value=100,
            ),
            "SCORE_OUTLIER_UC": st.column_config.ProgressColumn(
                "Score total",
                min_value=0,
                max_value=100,
            ),
            "STATUS_POS_OPERACAO": st.column_config.TextColumn("Status pós"),
            "QTD_OCORRENCIAS_PENDENTES_POS": st.column_config.NumberColumn("Pendentes pós", format="%d"),
            "QTD_OCORRENCIAS_VALIDADAS_POS": st.column_config.NumberColumn("Validadas pós", format="%d"),
            "PCT_META_DIC_PENDENTE_POS": st.column_config.NumberColumn("% META DIC pend.", format="%.2f%%"),
            "PCT_META_FIC_PENDENTE_POS": st.column_config.NumberColumn("% META FIC pend.", format="%.2f%%"),
            "PCT_META_DMIC_PENDENTE_POS": st.column_config.NumberColumn("% META DMIC pend.", format="%.2f%%"),
            "COMP_TOTAL_PRODIST_PENDENTE_POS": st.column_config.NumberColumn("COMP pendente", format="%.2f"),
            "COMP_TOTAL_PRODIST": st.column_config.NumberColumn("COMP total", format="%.2f"),
            "DIC_PENDENTE_POS": st.column_config.NumberColumn("DIC pend.", format="%.3f"),
            "FIC_PENDENTE_POS": st.column_config.NumberColumn("FIC pend.", format="%.0f"),
            "DMIC_PENDENTE_POS": st.column_config.NumberColumn("DMIC pend.", format="%.3f"),
        },
    )

    st.download_button(
        "Baixar Outlier UC",
        ranking_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="outlier_uc.csv",
        mime="text/csv",
    )
'''


def substituir_bloco_funcoes(texto: str) -> str:
    padrao = re.compile(
        r"@st\.cache_data\(show_spinner=False\)\s*\ndef outlier_uc_ranking\(.*?\n(?=def show_avaliacao_uc\()",
        re.DOTALL,
    )
    if padrao.search(texto):
        return padrao.sub(NOVO_BLOCO + "\n\n", texto, count=1)

    marcador = "\ndef show_avaliacao_uc("
    if marcador in texto:
        return texto.replace(marcador, "\n" + NOVO_BLOCO + "\n" + marcador.lstrip(), 1)

    return texto.rstrip() + "\n\n" + NOVO_BLOCO


def main() -> None:
    caminho = Path("midway") / "web" / "library" / "avaliacao_uc.py"
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    texto = caminho.read_text(encoding="utf-8")
    backup = caminho.with_suffix(".py.bak_valid_pos_outlier")
    backup.write_text(texto, encoding="utf-8", newline="\n")

    atualizado = substituir_bloco_funcoes(texto)
    caminho.write_text(atualizado, encoding="utf-8", newline="\n")

    print(f"Atualizado: {caminho}")
    print(f"Backup: {backup}")
    print("Outlier UC agora separa ocorrencias validadas e pendentes pela pos-operacao.")


if __name__ == "__main__":
    main()
