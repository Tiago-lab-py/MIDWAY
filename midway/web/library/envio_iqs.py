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


def _first_list_value(value) -> str:
    text = ajuste._clean_value(value)
    if not text:
        return ""
    return next((part.strip() for part in text.split(",") if part.strip()), "")


def _row_value(row: pd.Series | dict, candidates: list[str]) -> str:
    for column in candidates:
        if column in row:
            value = ajuste._clean_value(row.get(column))
            if value:
                return value
    return ""


def _where_occurrence(columns: list[str], occurrence: str, interruption: str, uc: str = "") -> str | None:
    conditions = []
    occurrence_col = _first_existing(columns, ["NUM_OCORRENCIA_ADMS"])
    interruption_col = _first_existing(columns, ["NUM_SEQ_INTRP", "NUM_INTRP_UCI", "INTERRUPCAO"])
    uc_col = _first_existing(columns, ["NUM_UC_UCI", "UC"])

    if occurrence and occurrence_col:
        conditions.append(
            f'TRIM(CAST("{occurrence_col}" AS VARCHAR)) = {sql_literal_for_streamlit(occurrence)}'
        )
    if interruption and interruption_col:
        conditions.append(
            f'TRIM(CAST("{interruption_col}" AS VARCHAR)) = {sql_literal_for_streamlit(interruption)}'
        )
    if uc and uc_col:
        conditions.append(f'TRIM(CAST("{uc_col}" AS VARCHAR)) = {sql_literal_for_streamlit(uc)}')

    if not conditions:
        return None
    return " AND ".join(conditions)


def _filtered_table_df(
    con,
    table_name: str,
    occurrence: str,
    interruption: str,
    uc: str,
    limit: int,
) -> pd.DataFrame:
    columns = _table_columns(con, table_name)
    where_clause = _where_occurrence(columns, occurrence, interruption, uc)
    if not where_clause:
        return pd.DataFrame()

    order_col = _first_existing(
        columns,
        [
            "DATA_HORA_INIC_INTRP",
            "DTHR_INICIO_INTRP_UC",
            "INICIO_INTERRUPCAO_UC",
            "DTHR_RECLAMACAO",
            "DATA_RECLAMACAO",
        ],
    )
    order_clause = f'ORDER BY "{order_col}"' if order_col else ""

    return con.execute(
        f"""
        SELECT
            {sql_literal_for_streamlit(table_name)} AS FONTE_OCORRENCIA,
            *
        FROM {table_name}
        WHERE {where_clause}
        {order_clause}
        LIMIT {int(limit)}
        """
    ).fetchdf()


def _fallback_ocorrencia_df(db_path: str, occurrence: str, interruption: str, uc: str, limit: int) -> pd.DataFrame:
    table_order = [
        "gold_interrupcao_tratada",
        "gold_apuracao_uc",
        "gold_reclamacao_uc_vinculada",
        "silver_dbguo_reclamacoes_candidatas",
        "silver_dbguo_reclamacoes",
    ]

    with duckdb.connect(db_path, read_only=True) as con:
        for table_name in table_order:
            if not table_exists(db_path, table_name):
                continue
            df = _filtered_table_df(con, table_name, occurrence, interruption, uc, limit)
            if not df.empty:
                return df

    return pd.DataFrame()


def _candidate_defaults(row: pd.Series | dict) -> dict[str, str]:
    causa_servico = _first_list_value(row.get("CAUSAS_SERVICO"))
    componente_servico = _first_list_value(row.get("COMPONENTES_SERVICO"))
    justificativa_partes = [
        _row_value(row, ["CLASSIFICACAO_QUALIDADE"]),
        f"score={_row_value(row, ['SCORE_QUALIDADE'])}" if _row_value(row, ["SCORE_QUALIDADE"]) else "",
        _row_value(row, ["TIPOS_RECLAMACAO_PROVAVEIS"]),
        _row_value(row, ["PREVIAS_CAUSA_RECLAMACAO", "CAUSAS_PROVAVEIS_RECLAMACAO"]),
    ]
    return {
        "NUM_OCORRENCIA_ADMS": _row_value(row, ["NUM_OCORRENCIA_ADMS"]),
        "NUM_SEQ_INTRP": _row_value(row, ["NUM_SEQ_INTRP"]),
        "NUM_UC_UCI": _row_value(row, ["NUM_UC_UCI", "UC"]),
        "SIGLA_REGIONAL": _row_value(row, ["REGIONAL", "SIGLA_REGIONAL"]),
        "COD_CAUSA_ATUAL": _row_value(row, ["COD_CAUSA_INTRP"]),
        "COD_COMP_ATUAL": _row_value(row, ["COD_COMP_INTRP"]),
        "NOVO_COD_CAUSA_INTRP": causa_servico,
        "NOVO_COD_COMP_INTRP": componente_servico,
        "JUSTIFICATIVA": " | ".join(part for part in justificativa_partes if part),
        "CLASSIFICACAO_QUALIDADE": _row_value(row, ["CLASSIFICACAO_QUALIDADE"]),
        "SCORE_QUALIDADE": _row_value(row, ["SCORE_QUALIDADE"]),
        "SUGESTAO_ORIGEM": "Candidatos de qualidade",
    }


def _defaults_from_candidates(
    candidates: pd.DataFrame,
    occurrence: str,
    interruption: str,
    uc: str,
) -> dict[str, str]:
    if candidates.empty:
        return {}

    filtered = candidates.copy()
    if occurrence and "NUM_OCORRENCIA_ADMS" in filtered.columns:
        filtered = filtered[filtered["NUM_OCORRENCIA_ADMS"].astype(str).str.strip() == str(occurrence).strip()]
    if interruption and "NUM_SEQ_INTRP" in filtered.columns:
        filtered = filtered[filtered["NUM_SEQ_INTRP"].astype(str).str.strip() == str(interruption).strip()]
    if uc:
        uc_column = "NUM_UC_UCI" if "NUM_UC_UCI" in filtered.columns else "UC" if "UC" in filtered.columns else None
        if uc_column:
            filtered = filtered[filtered[uc_column].astype(str).str.strip() == str(uc).strip()]

    if filtered.empty:
        return {}

    return _candidate_defaults(filtered.iloc[0])


def _defaults_from_gold(db_path: str, occurrence: str, interruption: str, uc: str) -> dict[str, str]:
    tables = [
        "gold_reclamacao_uc_vinculada",
        "gold_interrupcao_tratada",
        "gold_apuracao_uc",
        "silver_dbguo_reclamacoes_candidatas",
        "silver_dbguo_reclamacoes",
    ]

    with duckdb.connect(db_path, read_only=True) as con:
        for table_name in tables:
            if not table_exists(db_path, table_name):
                continue
            df = _filtered_table_df(con, table_name, occurrence, interruption, uc, 1)
            if df.empty:
                continue

            row = df.iloc[0]
            causa_sugerida = _first_list_value(_row_value(row, ["CAUSAS_SERVICO"]))
            comp_sugerido = _first_list_value(_row_value(row, ["COMPONENTES_SERVICO"]))
            justificativa = _row_value(row, ["PREVIA_CAUSA_RECLAMACAO", "CAUSA_PROVAVEL_RECLAMACAO"])
            classificacao = _row_value(row, ["CLASSIFICACACAO_QUALIDADE", "CLASSIFICACAO_VINCULO_RECLAMACAO"])
            return {
                "NUM_OCORRENCIA_ADMS": _row_value(row, ["NUM_OCORRENCIA_ADMS"]),
                "NUM_SEQ_INTRP": _row_value(row, ["NUM_SEQ_INTRP", "INTERRUPCAO"]),
                "NUM_UC_UCI": _row_value(row, ["NUM_UC_UCI", "UC"]),
                "SIGLA_REGIONAL": _row_value(row, ["SIGLA_REGIONAL", "REGIONAL"]),
                "COD_CAUSA_ATUAL": _row_value(row, ["COD_CAUSA_INTRP"]),
                "COD_COMP_ATUAL": _row_value(row, ["COD_COMP_INTRP"]),
                "NOVO_COD_CAUSA_INTRP": causa_sugerida,
                "NOVO_COD_COMP_INTRP": comp_sugerido,
                "NOVO_VALID_POS_OPERACAO": "S",
                "NOVA_DATA_HORA_INIC_INTRP": _row_value(row, ["DATA_HORA_INIC_INTRP", "INICIO_INTERRUPCAO_UC"]),
                "NOVA_DATA_HORA_FIM_INTRP": _row_value(row, ["DATA_HORA_FIM_INTRP", "FIM_INTERRUPCAO"]),
                "NOVA_DTHR_INICIO_INTRP_UC": _row_value(row, ["DTHR_INICIO_INTRP_UC", "INICIO_INTERRUPCAO_UC"]),
                "JUSTIFICATIVA": " | ".join(part for part in [classificacao, justificativa, table_name] if part),
                "SUGESTAO_ORIGEM": table_name,
            }

    return {}


def _merge_defaults(*sources: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for source in sources:
        for key, value in source.items():
            clean = ajuste._clean_value(value)
            if clean and not ajuste._clean_value(merged.get(key, "")):
                merged[key] = clean
    return merged


def _render_sugestoes(defaults: dict[str, str]) -> None:
    fields = [
        "SUGESTAO_ORIGEM",
        "NUM_OCORRENCIA_ADMS",
        "NUM_SEQ_INTRP",
        "NUM_UC_UCI",
        "SIGLA_REGIONAL",
        "COD_CAUSA_ATUAL",
        "NOVO_COD_CAUSA_INTRP",
        "COD_COMP_ATUAL",
        "NOVO_COD_COMP_INTRP",
        "JUSTIFICATIVA",
    ]
    rows = [{"Campo": field, "Valor": defaults.get(field, "")} for field in fields if ajuste._clean_value(defaults.get(field, ""))]
    if rows:
        st.markdown("### Dados da ocorrência e sugestões")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _widget_key(prefix: str, defaults: dict[str, str]) -> str:
    occurrence = ajuste._clean_value(defaults.get("NUM_OCORRENCIA_ADMS", "manual")) or "manual"
    interruption = ajuste._clean_value(defaults.get("NUM_SEQ_INTRP", ""))
    uc = ajuste._clean_value(defaults.get("NUM_UC_UCI", ""))
    return f"{prefix}_{occurrence}_{interruption}_{uc}"


def _render_evidencias_envio(defaults: dict[str, str], db_path: str, raw_path, sample_limit: int) -> None:
    occurrence = ajuste._clean_value(defaults.get("NUM_OCORRENCIA_ADMS", ""))
    interruption = ajuste._clean_value(defaults.get("NUM_SEQ_INTRP", ""))
    uc = ajuste._clean_value(defaults.get("NUM_UC_UCI", ""))
    if not occurrence and not interruption and not uc:
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
            uc,
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
            st.info(
                "Sem dados da ocorrência encontrados nas tabelas de evidência. "
                "Confira se o número da ocorrência está no mesmo ANOMES processado."
            )
        else:
            st.caption("A fonte usada aparece na coluna `FONTE_OCORRENCIA` quando a busca cai no fallback gold/silver.")
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
            st.caption("Digite a ocorrência, interrupção ou UC abaixo para buscar evidências e preencher sugestões automaticamente.")
            st.dataframe(
                candidates[[column for column in columns if column in candidates.columns]].head(sample_limit),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("### Identificação da ocorrência")
        col_scope, col_input, col_btn = st.columns([1, 2, 1])
        with col_scope:
            escopo = st.selectbox("Escopo", ["OCORRENCIA", "INTERRUPCAO", "UC"])

        with col_input:
            if escopo == "OCORRENCIA":
                ocorrencia = st.text_input(
                    "NUM_OCORRENCIA_ADMS",
                    value="",
                    key="envio_iqs_ocorrencia_manual",
                )
                interrupcao = ""
                uc = ""
            elif escopo == "INTERRUPCAO":
                interrupcao = st.text_input(
                    "NUM_SEQ_INTRP",
                    value="",
                    key="envio_iqs_interrupcao_manual",
                )
                ocorrencia = ""
                uc = ""
            else:
                uc = st.text_input(
                    "NUM_UC_UCI",
                    value="",
                    key="envio_iqs_uc_manual",
                )
                ocorrencia = ""
                interrupcao = ""

        with col_btn:
            st.write("")
            st.write("")
            buscar = st.button("Buscar evidências")

        typed_defaults = {
            "NUM_OCORRENCIA_ADMS": ocorrencia,
            "NUM_SEQ_INTRP": interrupcao,
            "NUM_UC_UCI": uc,
        }
        matched_candidate_defaults = _defaults_from_candidates(candidates, ocorrencia, interrupcao, uc)
        gold_defaults = _defaults_from_gold(db_path, ocorrencia, interrupcao, uc) if buscar or ocorrencia or interrupcao or uc else {}
        defaults = _merge_defaults(typed_defaults, matched_candidate_defaults, gold_defaults)

        _render_sugestoes(defaults)

        if buscar or defaults.get("NUM_OCORRENCIA_ADMS") or defaults.get("NUM_SEQ_INTRP") or defaults.get("NUM_UC_UCI"):
            st.markdown("### Evidências para decisão")
            _render_evidencias_envio(defaults, db_path, raw_path, sample_limit)

        with st.form("form_novo_ajuste_iqs"):
            col_resp, col_aprov = st.columns([2, 1])
            with col_resp:
                responsavel = st.text_input("Responsável", value="")
            with col_aprov:
                aprovado = st.checkbox("Aprovado para exportar", value=True)

            st.markdown("#### Campos IQS a alterar")
            col_causa, col_comp, col_clima, col_tipo = st.columns(4)
            with col_causa:
                novo_causa = st.text_input(
                    "COD_CAUSA_INTRP",
                    value=defaults.get("NOVO_COD_CAUSA_INTRP", ""),
                    key=_widget_key("novo_causa", defaults),
                )
            with col_comp:
                novo_comp = st.text_input(
                    "COD_COMP_INTRP",
                    value=defaults.get("NOVO_COD_COMP_INTRP", ""),
                    key=_widget_key("novo_comp", defaults),
                )
            with col_clima:
                novo_clima = st.text_input("COD_COND_CLIMA_INTRP", value="", key=_widget_key("novo_clima", defaults))
            with col_tipo:
                novo_tipo = st.text_input("COD_TIPO_INTRP", value="", key=_widget_key("novo_tipo", defaults))

            col_motivo, col_tipo_uci, col_prot_uci = st.columns(3)
            with col_motivo:
                novo_motivo = st.text_input("NUM_MOTIVO_TRAT_DIF_UCI", value="", key=_widget_key("novo_motivo", defaults))
            with col_tipo_uci:
                novo_tipo_prot_uci = st.text_input("TIPO_PROTOC_JUSTIF_UCI", value="", key=_widget_key("novo_tipo_uci", defaults))
            with col_prot_uci:
                novo_prot_uci = st.text_input("NUM_PROTOC_JUSTIF_RESP_UCI", value="", key=_widget_key("novo_prot_uci", defaults))

            col_tipo_intrp, col_prot_intrp, col_valid, col_estado = st.columns(4)
            with col_tipo_intrp:
                novo_tipo_prot_intrp = st.text_input("TIPO_PROTOC_JUSTIF_INTRP", value="", key=_widget_key("novo_tipo_intrp", defaults))
            with col_prot_intrp:
                novo_prot_intrp = st.text_input("NUM_PROTOC_JUSTIF_RESP_INTRP", value="", key=_widget_key("novo_prot_intrp", defaults))
            with col_valid:
                novo_valid = st.text_input(
                    "VALID_POS_OPERACAO",
                    value=defaults.get("NOVO_VALID_POS_OPERACAO", "S"),
                    key=_widget_key("novo_valid", defaults),
                )
            with col_estado:
                novo_estado = st.text_input("ESTADO_INTRP", value="", key=_widget_key("novo_estado", defaults))

            st.markdown("#### Data/hora da ocorrência")
            col_ini, col_fim, col_ini_uc = st.columns(3)
            with col_ini:
                nova_data_ini = st.text_input(
                    "DATA_HORA_INIC_INTRP",
                    value=defaults.get("NOVA_DATA_HORA_INIC_INTRP", ""),
                    help="Opcional. Use dd/mm/aaaa hh:mm:ss.",
                    key=_widget_key("nova_data_ini", defaults),
                )
            with col_fim:
                nova_data_fim = st.text_input(
                    "DATA_HORA_FIM_INTRP",
                    value=defaults.get("NOVA_DATA_HORA_FIM_INTRP", ""),
                    help="Opcional. Use dd/mm/aaaa hh:mm:ss.",
                    key=_widget_key("nova_data_fim", defaults),
                )
            with col_ini_uc:
                nova_data_ini_uc = st.text_input(
                    "DTHR_INICIO_INTRP_UC",
                    value=defaults.get("NOVA_DTHR_INICIO_INTRP_UC", ""),
                    help="Opcional. Use dd/mm/aaaa hh:mm:ss.",
                    key=_widget_key("nova_data_ini_uc", defaults),
                )

            justificativa = st.text_area(
                "Justificativa/evidência",
                value=defaults.get("JUSTIFICATIVA", ""),
                height=100,
                key=_widget_key("justificativa", defaults),
            )
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
