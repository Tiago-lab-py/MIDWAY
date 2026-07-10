from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

import midway.web.library.ajuste_manual_iqs as ajuste
from midway.web.library.shared import (
    format_number,
    show_metric_cards,
    sql_literal_for_streamlit,
    table_exists,
)


def _table_columns(con, table_name: str) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = ?
            ORDER BY ordinal_position
            """,
            [table_name],
        ).fetchall()
    ]


def _first_existing(columns: list[str], candidates: list[str]) -> str | None:
    mapping = {column.upper(): column for column in columns}
    for candidate in candidates:
        if candidate.upper() in mapping:
            return mapping[candidate.upper()]
    return None


def _text_expr(columns: list[str], candidates: list[str]) -> str:
    column = _first_existing(columns, candidates)
    if not column:
        return "CAST(NULL AS VARCHAR)"
    return f'NULLIF(TRIM(CAST("{column}" AS VARCHAR)), \'\')'


def _timestamp_expr(columns: list[str], candidates: list[str]) -> str:
    column = _first_existing(columns, candidates)
    if not column:
        return "CAST(NULL AS TIMESTAMP)"
    return f'TRY_CAST("{column}" AS TIMESTAMP)'


def _number_expr(columns: list[str], candidates: list[str]) -> str:
    column = _first_existing(columns, candidates)
    if not column:
        return "CAST(0 AS DOUBLE)"
    return f'COALESCE(TRY_CAST("{column}" AS DOUBLE), 0)'


def _where_occurrence(columns: list[str], occurrence: str, interruption: str) -> str | None:
    conditions = []
    occurrence_col = _first_existing(columns, ["NUM_OCORRENCIA_ADMS"])
    interruption_col = _first_existing(columns, ["NUM_SEQ_INTRP", "NUM_INTRP_UCI", "INTERRUPCAO"])

    if occurrence and occurrence_col:
        conditions.append(
            f'TRIM(CAST("{occurrence_col}" AS VARCHAR)) = {sql_literal_for_streamlit(occurrence)}'
        )
    if interruption and interruption_col:
        conditions.append(
            f'TRIM(CAST("{interruption_col}" AS VARCHAR)) = {sql_literal_for_streamlit(interruption)}'
        )

    if not conditions:
        return None
    return " AND ".join(conditions)


def _fallback_ocorrencia_df(db_path: str, occurrence: str, interruption: str, limit: int) -> pd.DataFrame:
    sources = [
        (
            "gold_interrupcao_tratada",
            "gold_interrupcao_tratada",
            ["REGIONAL", "SIGLA_REGIONAL", "SIGLA_REGIONAL_INTRP_PRIM_HIADMS"],
            ["DATA_HORA_INIC_INTRP", "DTHR_INICIO_INTRP_UC"],
            ["DATA_HORA_FIM_INTRP"],
        ),
        (
            "gold_apuracao_uc",
            "gold_apuracao_uc",
            ["REGIONAL", "SIGLA_REGIONAL", "SIGLA_REGIONAL_INTRP_PRIM_HIADMS"],
            ["DATA_HORA_INIC_INTRP", "DTHR_INICIO_INTRP_UC"],
            ["DATA_HORA_FIM_INTRP"],
        ),
        (
            "gold_reclamacao_uc_vinculada",
            "gold_reclamacao_uc_vinculada",
            ["REGIONAL", "SIGLA_REGIONAL"],
            ["INICIO_INTERRUPCAO_UC"],
            ["FIM_INTERRUPCAO"],
        ),
    ]

    with duckdb.connect(db_path, read_only=True) as con:
        for table_name, source_label, regional_candidates, start_candidates, end_candidates in sources:
            if not table_exists(db_path, table_name):
                continue

            columns = _table_columns(con, table_name)
            where_clause = _where_occurrence(columns, occurrence, interruption)
            if not where_clause:
                continue

            occurrence_expr = _text_expr(columns, ["NUM_OCORRENCIA_ADMS"])
            interruption_expr = _text_expr(columns, ["NUM_SEQ_INTRP", "INTERRUPCAO"])
            regional_expr = _text_expr(columns, regional_candidates)
            conjunto_expr = _text_expr(columns, ["COD_CONJTO_ELET_ANEEL_INTRP", "CONJUNTO"])
            alim_expr = _text_expr(columns, ["ALIM_INTRP"])
            oper_expr = _text_expr(columns, ["NUM_OPER_CHV_INTRP"])
            geo_expr = _text_expr(columns, ["NUM_GEO_CHV_INTRP"])
            estado_expr = _text_expr(columns, ["ESTADO_INTRP"])
            valid_expr = _text_expr(columns, ["VALID_POS_OPERACAO"])
            causa_expr = _text_expr(columns, ["COD_CAUSA_INTRP"])
            comp_expr = _text_expr(columns, ["COD_COMP_INTRP"])
            clima_expr = _text_expr(columns, ["COD_COND_CLIMA_INTRP"])
            tipo_expr = _text_expr(columns, ["COD_TIPO_INTRP"])
            uc_expr = _text_expr(columns, ["NUM_UC_UCI", "UC"])
            start_expr = _timestamp_expr(columns, start_candidates)
            end_expr = _timestamp_expr(columns, end_candidates)
            duracao_expr = _number_expr(columns, ["DURACAO_HORA"])

            df = con.execute(
                f"""
                SELECT
                    {occurrence_expr} AS NUM_OCORRENCIA_ADMS,
                    {interruption_expr} AS NUM_SEQ_INTRP,
                    {regional_expr} AS SIGLA_REGIONAL,
                    {conjunto_expr} AS CONJUNTO,
                    {alim_expr} AS ALIM_INTRP,
                    {oper_expr} AS NUM_OPER_CHV_INTRP,
                    {geo_expr} AS NUM_GEO_CHV_INTRP,
                    MIN({start_expr}) AS DATA_HORA_INIC_INTRP,
                    MAX({end_expr}) AS DATA_HORA_FIM_INTRP,
                    {estado_expr} AS ESTADO_INTRP,
                    {valid_expr} AS VALID_POS_OPERACAO,
                    {causa_expr} AS COD_CAUSA_INTRP,
                    {comp_expr} AS COD_COMP_INTRP,
                    {clima_expr} AS COD_COND_CLIMA_INTRP,
                    {tipo_expr} AS COD_TIPO_INTRP,
                    COUNT(*) AS LINHAS_IQS,
                    COUNT(DISTINCT {uc_expr}) AS UCS,
                    SUM({duracao_expr}) AS DURACAO_TOTAL_HORA,
                    {sql_literal_for_streamlit(source_label)} AS FONTE_OCORRENCIA
                FROM {table_name}
                WHERE {where_clause}
                GROUP BY
                    {occurrence_expr},
                    {interruption_expr},
                    {regional_expr},
                    {conjunto_expr},
                    {alim_expr},
                    {oper_expr},
                    {geo_expr},
                    {estado_expr},
                    {valid_expr},
                    {causa_expr},
                    {comp_expr},
                    {clima_expr},
                    {tipo_expr}
                ORDER BY DATA_HORA_INIC_INTRP, NUM_SEQ_INTRP
                LIMIT {int(limit)}
                """
            ).fetchdf()

            if not df.empty:
                return df

    return pd.DataFrame()


def _render_evidencias_envio(defaults: dict[str, str], db_path: str, raw_path, sample_limit: int) -> None:
    occurrence = defaults.get("NUM_OCORRENCIA_ADMS", "")
    interruption = defaults.get("NUM_SEQ_INTRP", "")
    if not occurrence and not interruption:
        st.info("Selecione uma ocorrência para carregar evidências.")
        return

    detalhes = ajuste.detalhe_ajuste_ocorrencia(
        db_path,
        str(raw_path),
        occurrence,
        interruption,
        min(sample_limit, 200),
    )
    if detalhes["interrupcao"].empty:
        detalhes["interrupcao"] = _fallback_ocorrencia_df(
            db_path,
            occurrence,
            interruption,
            min(sample_limit, 200),
        )

    st.markdown(
        """
        **Legenda visual:** sem cor = valor atual da ocorrência; verde = sugestão do algoritmo e informação pré-tratada/evidência; amarelo = ajuste manual registrado.
        """
    )
    preview = ajuste._preview_comparacao(defaults, detalhes)
    st.dataframe(preview.style.apply(ajuste._comparison_style, axis=None), use_container_width=True, hide_index=True)

    evidence_tabs = st.tabs(["Ocorrência", "Serviço ADMS", "Reclamações"])
    with evidence_tabs[0]:
        ocorrencia_df = detalhes["interrupcao"]
        if ocorrencia_df.empty:
            st.info("Sem dados da ocorrência encontrados para o filtro nas tabelas `adms_iqs_export`, `gold_interrupcao_tratada`, `gold_apuracao_uc` e `gold_reclamacao_uc_vinculada`.")
        else:
            st.dataframe(ocorrencia_df, use_container_width=True, hide_index=True)

    with evidence_tabs[1]:
        servicos = detalhes["servicos"]
        if servicos.empty:
            st.info("Sem serviços ADMS vinculados às interrupções selecionadas.")
        else:
            servicos_display = servicos.drop(columns=["NUM_SEQ_INTRP"], errors="ignore")
            st.caption("Visão resumida do serviço ADMS; os dados da ocorrência ficam na aba Ocorrência.")
            st.dataframe(servicos_display, use_container_width=True, hide_index=True)

    with evidence_tabs[2]:
        resumo = detalhes["reclamacao_resumo"]
        reclamacoes = detalhes["reclamacoes"]
        if resumo.empty and reclamacoes.empty:
            st.info("Sem reclamações vinculadas à ocorrência.")
        if not resumo.empty:
            st.markdown("#### Resumo")
            st.dataframe(resumo, use_container_width=True, hide_index=True)
        if not reclamacoes.empty:
            st.markdown("#### Detalhe")
            st.dataframe(reclamacoes, use_container_width=True, hide_index=True)


def show_envio_iqs(anomes: str, db_path: str, sample_limit: int) -> None:
    st.subheader("Envio IQS")
    st.caption(
        "Prepara o envio ao IQS com decisões manuais da pós-operação, aplicando alterações sobre `adms_iqs_export` "
        "e gerando CSV no layout IQS para carga controlada."
    )

    if not table_exists(db_path, "adms_iqs_export"):
        st.info("Tabela `adms_iqs_export` não encontrada. Execute `run.bat exportar` ou `run.bat tratamento` antes.")
        return

    ajustes_path = ajuste.ajustes_db_path(anomes)
    st.caption(f"Base local de ajustes: `{ajustes_path}`")

    raw_path = ajuste.adms_servicos_raw_path(anomes)

    col_filtro_class, col_filtro_val = st.columns(2)
    with col_filtro_class:
        filtro_classificacao = st.selectbox(
            "Classificação Qualidade",
            [
                "Todos",
                "SUSPEITA_IMPROCEDENTE",
                "SUSPEITA_ATENDIDO_OUTRA_OCORRENCIA",
                "RECLAMACAO_FORTE_SEM_SERVICO",
                "RECLAMACAO_FORTE_REVISAR_CAUSA",
                "MULTIPLOS_SERVICOS_REVISAR",
                "CAUSA_COMPONENTE_COM_EVIDENCIA",
                "SERVICO_SEM_RECLAMACAO",
                "RECLAMACAO_SEM_SERVICO",
                "SEM_EVIDENCIA_COMPLEMENTAR",
            ],
        )
    with col_filtro_val:
        filtro_validacao = st.selectbox(
            "Validação Pós-Operação (Filtro Candidatos)",
            ["Todos", "Somente validados (S)", "Somente pendentes (N)"],
            index=2,
        )

    candidates = pd.DataFrame()
    if raw_path.exists():
        try:
            candidates = ajuste.qualidade_ranking(
                db_path,
                str(raw_path),
                filtro_classificacao,
                True,
                "",
                20,
                min(sample_limit, 500),
                filtro_validacao,
            )
        except Exception as error:
            st.warning(f"Não foi possível carregar candidatos da qualidade: {error}")

    ajustes = ajuste.listar_ajustes(anomes)
    aprovados = ajustes[ajustes["APROVADO"].map(ajuste._bool_value)] if not ajustes.empty else ajustes
    show_metric_cards(
        [
            ("Ajustes registrados", format_number(len(ajustes), 0), None),
            ("Ajustes aprovados", format_number(len(aprovados), 0), None),
            ("Candidatos qualidade", format_number(len(candidates), 0), None),
        ]
    )

    tabs = st.tabs(["Ajuste manual", "Ajustes registrados", "Envio IQS"])

    with tabs[0]:
        st.markdown("### Candidatos de qualidade")
        if candidates.empty:
            st.info("Sem candidatos carregados. Você ainda pode preencher o ajuste manualmente.")
        else:
            columns = [
                "CLASSIFICACAO_QUALIDADE",
                "SCORE_QUALIDADE",
                "NUM_OCORRENCIA_ADMS",
                "NUM_SEQ_INTRP",
                "CONJUNTO",
                "REGIONAL",
                "COD_CAUSA_INTRP",
                "COD_COMP_INTRP",
                "CAUSAS_SERVICO",
                "COMPONENTES_SERVICO",
                "QTD_RECLAMACOES",
                "FIC_OCORRENCIA",
                "DIC_OCORRENCIA",
            ]
            st.dataframe(
                candidates[[column for column in columns if column in candidates.columns]].head(sample_limit),
                use_container_width=True,
                hide_index=True,
            )

        defaults = {}

        st.markdown("### Identificação da ocorrência")
        col_scope, col_input, col_btn = st.columns([1, 2, 1])
        with col_scope:
            escopo = st.selectbox("Escopo", ["OCORRENCIA", "INTERRUPCAO", "UC"])

        ocorrencia = defaults.get("NUM_OCORRENCIA_ADMS", "")
        interrupcao = defaults.get("NUM_SEQ_INTRP", "")
        uc = ""

        with col_input:
            if escopo == "OCORRENCIA":
                ocorrencia = st.text_input("NUM_OCORRENCIA_ADMS", value=ocorrencia)
            elif escopo == "INTERRUPCAO":
                interrupcao = st.text_input("NUM_SEQ_INTRP", value=interrupcao)
            elif escopo == "UC":
                uc = st.text_input("NUM_UC_UCI", value="")

        with col_btn:
            st.write("")
            st.write("")
            buscar = st.button("Buscar evidências")

        evidence_defaults = defaults.copy()
        if ocorrencia or interrupcao or uc:
            evidence_defaults["NUM_OCORRENCIA_ADMS"] = ocorrencia
            evidence_defaults["NUM_SEQ_INTRP"] = interrupcao
            evidence_defaults["NUM_UC_UCI"] = uc

        if buscar or evidence_defaults.get("NUM_OCORRENCIA_ADMS") or evidence_defaults.get("NUM_SEQ_INTRP"):
            st.markdown("### Evidências para decisão")
            _render_evidencias_envio(evidence_defaults, db_path, raw_path, sample_limit)

        with st.form("form_novo_ajuste_iqs"):
            col_resp, col_aprov = st.columns([2, 1])
            with col_resp:
                responsavel = st.text_input("Responsável", value="")
            with col_aprov:
                aprovado = st.checkbox("Aprovado para exportar", value=True)

            st.markdown("#### Campos IQS a alterar")
            col_causa, col_comp, col_clima, col_tipo = st.columns(4)
            with col_causa:
                novo_causa = st.text_input("COD_CAUSA_INTRP", value=defaults.get("NOVO_COD_CAUSA_INTRP", ""))
            with col_comp:
                novo_comp = st.text_input("COD_COMP_INTRP", value=defaults.get("NOVO_COD_COMP_INTRP", ""))
            with col_clima:
                novo_clima = st.text_input("COD_COND_CLIMA_INTRP", value="")
            with col_tipo:
                novo_tipo = st.text_input("COD_TIPO_INTRP", value="")

            col_motivo, col_tipo_uci, col_prot_uci = st.columns(3)
            with col_motivo:
                novo_motivo = st.text_input("NUM_MOTIVO_TRAT_DIF_UCI", value="")
            with col_tipo_uci:
                novo_tipo_prot_uci = st.text_input("TIPO_PROTOC_JUSTIF_UCI", value="")
            with col_prot_uci:
                novo_prot_uci = st.text_input("NUM_PROTOC_JUSTIF_RESP_UCI", value="")

            col_tipo_intrp, col_prot_intrp, col_valid, col_estado = st.columns(4)
            with col_tipo_intrp:
                novo_tipo_prot_intrp = st.text_input("TIPO_PROTOC_JUSTIF_INTRP", value="")
            with col_prot_intrp:
                novo_prot_intrp = st.text_input("NUM_PROTOC_JUSTIF_RESP_INTRP", value="")
            with col_valid:
                novo_valid = st.text_input("VALID_POS_OPERACAO", value="S")
            with col_estado:
                novo_estado = st.text_input("ESTADO_INTRP", value="")

            st.markdown("#### Data/hora da ocorrência")
            col_ini, col_fim, col_ini_uc = st.columns(3)
            with col_ini:
                nova_data_ini = st.text_input("DATA_HORA_INIC_INTRP", value="", help="Opcional. Use dd/mm/aaaa hh:mm:ss.")
            with col_fim:
                nova_data_fim = st.text_input("DATA_HORA_FIM_INTRP", value="", help="Opcional. Use dd/mm/aaaa hh:mm:ss.")
            with col_ini_uc:
                nova_data_ini_uc = st.text_input("DTHR_INICIO_INTRP_UC", value="", help="Opcional. Use dd/mm/aaaa hh:mm:ss.")

            justificativa = st.text_area("Justificativa/evidência", value=defaults.get("JUSTIFICATIVA", ""), height=100)
            submitted = st.form_submit_button("Adicionar ajuste")

        if submitted:
            try:
                ajuste_id = ajuste.adicionar_ajuste(
                    anomes,
                    {
                        "APROVADO": aprovado,
                        "ESCOPO": escopo,
                        "NUM_OCORRENCIA_ADMS": ocorrencia,
                        "NUM_SEQ_INTRP": interrupcao,
                        "NUM_UC_UCI": uc,
                        "SIGLA_REGIONAL": defaults.get("SIGLA_REGIONAL", ""),
                        "NOVO_COD_CAUSA_INTRP": novo_causa,
                        "NOVO_COD_COMP_INTRP": novo_comp,
                        "NOVO_COD_COND_CLIMA_INTRP": novo_clima,
                        "NOVO_COD_TIPO_INTRP": novo_tipo,
                        "NOVO_NUM_MOTIVO_TRAT_DIF_UCI": novo_motivo,
                        "NOVO_TIPO_PROTOC_JUSTIF_UCI": novo_tipo_prot_uci,
                        "NOVO_NUM_PROTOC_JUSTIF_RESP_UCI": novo_prot_uci,
                        "NOVO_TIPO_PROTOC_JUSTIF_INTRP": novo_tipo_prot_intrp,
                        "NOVO_NUM_PROTOC_JUSTIF_RESP_INTRP": novo_prot_intrp,
                        "NOVO_VALID_POS_OPERACAO": novo_valid,
                        "NOVO_ESTADO_INTRP": novo_estado,
                        "NOVA_DATA_HORA_INIC_INTRP": nova_data_ini,
                        "NOVA_DATA_HORA_FIM_INTRP": nova_data_fim,
                        "NOVA_DTHR_INICIO_INTRP_UC": nova_data_ini_uc,
                        "JUSTIFICATIVA": justificativa,
                        "RESPONSAVEL": responsavel,
                    },
                )
                st.success(f"Ajuste registrado: `{ajuste_id}`")
                st.cache_data.clear()
            except Exception as error:
                st.error(f"Falha ao registrar ajuste: {error}")

    with tabs[1]:
        st.markdown("### Grade de ajustes")
        ajustes = ajuste.listar_ajustes(anomes)
        if not ajustes.empty:
            visual_columns = [
                "APROVADO",
                "ESCOPO",
                "NUM_OCORRENCIA_ADMS",
                "NUM_SEQ_INTRP",
                "NUM_UC_UCI",
                "SIGLA_REGIONAL",
                "NOVO_COD_CAUSA_INTRP",
                "NOVO_COD_COMP_INTRP",
                "NOVA_DATA_HORA_INIC_INTRP",
                "NOVA_DATA_HORA_FIM_INTRP",
                "NOVA_DTHR_INICIO_INTRP_UC",
                "JUSTIFICATIVA",
            ]
            visual = ajustes[[column for column in visual_columns if column in ajustes.columns]].head(sample_limit)
            st.markdown("#### Prévia visual")
            st.caption("Amarelo indica campo alterado manualmente; verde indica ajuste aprovado.")
            st.dataframe(visual.style.apply(ajuste._manual_adjustment_style, axis=None), use_container_width=True, hide_index=True)
        edited = st.data_editor(
            ajustes,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            disabled=["ID_AJUSTE", "ANOMES", "DTHR_CRIACAO", "DTHR_ATUALIZACAO"],
            column_config={
                "APROVADO": st.column_config.CheckboxColumn("Aprovado"),
                "JUSTIFICATIVA": st.column_config.TextColumn("Justificativa", width="large"),
            },
        )
        if st.button("Salvar alterações da grade"):
            try:
                ajuste.salvar_grade_ajustes(anomes, edited)
                st.success("Grade de ajustes salva.")
                st.cache_data.clear()
            except Exception as error:
                st.error(f"Falha ao salvar grade: {error}")

    with tabs[2]:
        st.markdown("### Envio IQS")
        st.warning(
            "A exportação usa somente ajustes aprovados e gera linhas encontradas em `adms_iqs_export`. "
            "Conferir auditoria antes da carga no IQS."
        )
        if st.button("Gerar arquivo para Envio IQS", type="primary"):
            try:
                resultado = ajuste.gerar_exportacao_ajustes(anomes, db_path)
                st.success(
                    f"Exportação gerada: {resultado['linhas_exportadas']} linhas em "
                    f"{len(resultado['arquivos'])} arquivo(s)."
                )
                for path in resultado["arquivos"]:
                    st.write(f"Arquivo IQS: `{path}`")
                    st.download_button(
                        f"Baixar {path.name}",
                        data=path.read_bytes(),
                        file_name=path.name,
                        mime="text/csv",
                    )
                st.write(f"Auditoria: `{resultado['auditoria']}`")
                st.write(f"Resumo: `{resultado['resumo']}`")
            except Exception as error:
                st.error(f"Falha ao gerar exportação: {error}")
