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


CAUSA_DESCRICOES = {
    "00": "SEM CAUSA INFORMADA",
    "01": "ANIMAIS/INSETOS/PASSAROS",
    "02": "GALHOS TOCANDO A RD (PODA)",
    "03": "CORROSAO/OXIDACAO/POLUICAO",
    "04": "DESCARGA ATMOSFERICA",
    "05": "EROSAO",
    "06": "GEADA/NEVE/BAIXA TEMP./GRANIZO",
    "07": "ARVORE CAIU SOBRE A REDE",
    "08": "CASCAS/GALHOS LANCADOS NA RD",
    "09": "INUNDACAO/ALAGAMENTO/BANHADO",
    "10": "TERCEIROS DERRUBADA ARVORE RD",
    "13": "VENTO/VENDAVAL",
    "15": "FATORES IMPREV.CALAMID.PUBLICA",
    "18": "ABALROAMENTO",
    "19": "ACIDENTE DE TERCEIROS",
    "20": "FALTA DE ACESSO",
    "21": "NECESSARIO VEICULO COM CESTO",
    "22": "ATENDIDO POR OUTRA OCORRENCIA",
    "23": "OBJETOS ESTRANHOS NA REDE",
    "24": "DESLIGAMENTO POR SEGURANCA",
    "26": "VANDALISMO/FURTOS",
    "28": "QUEIMADAS/INCENDIO",
    "33": "FALHA HUMANA DA EMPRESA",
    "34": "FALHA HUMANA CONTRATADA",
    "38": "DESEQUILIBRIO DE CARGA/TENSAO",
    "39": "MANOBRAS",
    "40": "ABERTURA OPERACAO OUTRA CHAVE",
    "41": "MANUTENCAO CORRETIVA",
    "42": "MANUTENCAO PREVENTIVA",
    "43": "MELHORIAS E/OU AMPLIACOES",
    "44": "REPOR COMPONENTE FURTADO DA RD",
    "45": "REVISAO OBRA",
    "47": "FALHA SISTEMA GERACAO/TRANSM",
    "48": "FALHA ALIMENTACAO CA/CC",
    "50": "OSCILACAO DE TENSAO/FREQUENCIA",
    "51": "RACIONAMENTO DE ENERGIA",
    "52": "TRANSF. CARGA/RETORNO CONFIG.",
    "54": "COMPONENTE AVARIADO/DESRREGUL",
    "60": "FALHA OU DEFEITO DE FABRICACAO",
    "68": "PONTO QUENTE",
    "69": "FALHA DE OUTRO RA/DISJUNTOR",
    "71": "DEFEITO INSTALACAO INTERNA",
    "74": "LIGAR/DESLIGAR/RELIGAR",
    "75": "REARMAR DISJUNTOR",
    "76": "NIVEL TENSAO ENVIAR P/ MEDICAO",
    "77": "NIVEL TENSAO NADA ENCONTRADO",
    "78": "SUBSTIT./RETIRADA/INSTALACAO",
    "82": "NAO IDENTIFICADA",
    "83": "ATENDIMENTO NAO EFETUADO",
    "85": "IMPROCEDENTE",
    "86": "BALANCEAMENTO CIRC/REMANEJAM.",
    "87": "COORDENACAO DA PROTECAO",
    "88": "SOLICITACAO DE TERCEIROS",
    "89": "ACOMP. VEICULO CARGA ALTA",
    "90": "AUXILIAR OUTRA EQUIPE",
    "91": "INSP./MANUT. EQUIPE DE EMERG.",
    "93": "MEDICOES/LEITURA EM SE OU RD",
    "95": "SERVICO EQUIPE DE MANUTENCAO",
    "96": "OUTRAS NECESSIDADES DA EMPRESA",
    "98": "FESTIVIDADES/COMICIOS/EVENTOS",
    "E1": "MANOBRA INDEVIDA TRANSMISSAO",
    "E2": "MANOBRA INDEVIDA EM SE 34,5 KV",
    "E3": "INTERF. ACIDENT. EQUIPE MANUT.",
    "E4": "CORTE DE CARGA",
    "E5": "RECOMPOSICAO",
    "H1": "FALHA COMPONENTE PROTECAO",
    "H2": "FALHA DE COMPONENTE DE MEDICAO",
    "H3": "FALHA SUPERVISAO(COE/COD/COS)",
    "K1": "MANOBRA INDEVIDA SISTEMA INTER",
    "K2": "INTER. ACID. MANUT SIST INTERL",
    "K3": "RACIONAMENTO SIST. INTERLIGADO",
    "K4": "RECOMPOSICAO SIST. INTERLIGADO",
    "K5": "FALHA COMP. PROT. SIST. INTERL",
    "K6": "FALHA COMP. MEDICAO SIST. INT.",
    "K7": "FALHA SUPERVISAO SIST. INTERL.",
    "K8": "FALHA GERACAO/TRANSM. SIST.INT",
    "K9": "FALHA ALIMENTACAO CA/CC SIST.",
    "P1": "OSCILACAO DE TENSAO/FREQ. SIST",
}


COMPONENTE_DESCRICOES = {
    "22": "COMPONENTE 22",
    "35": "COMPONENTE 35",
    "47": "COMPONENTE 47",
    "52": "CHAVE_PROTECAO",
    "92": "NAO_IDENTIFICADA",
}


REFERENCIA_COMPONENTE_CAUSA_TABLES = [
    "gold_iqs_referencia_componente_causa",
    "silver_iqs_referencia_componente_causa",
    "gold_referencia_iqs_componente_causa",
    "silver_referencia_iqs_componente_causa",
    "gold_iqs_componente_causa",
    "silver_iqs_componente_causa",
]


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


def _normalizar_codigo(codigo: str, descricoes: dict[str, str] | None = None) -> str:
    valor = ajuste._clean_value(codigo).upper()
    if not valor:
        return ""
    if descricoes and valor in descricoes:
        return valor
    if descricoes and valor.isdigit() and len(valor) == 1 and f"0{valor}" in descricoes:
        return f"0{valor}"
    return valor


def _descricao_codigo(codigo: str, descricoes: dict[str, str]) -> str:
    codigo_normalizado = _normalizar_codigo(codigo, descricoes)
    if not codigo_normalizado:
        return ""
    return descricoes.get(codigo_normalizado, "Descrição não cadastrada")


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


def _ref_label(codigo: str, descricao: str = "") -> str:
    codigo = ajuste._clean_value(codigo)
    descricao = ajuste._clean_value(descricao)
    if not codigo:
        return ""
    return f"{codigo} - {descricao}" if descricao else codigo


def _codigo_from_label(label: str) -> str:
    if not label:
        return ""
    return label.split(" - ", 1)[0].strip()


def _fallback_referencia_componentes_causas() -> pd.DataFrame:
    rows = []
    for cod_comp, desc_comp in COMPONENTE_DESCRICOES.items():
        for cod_causa, desc_causa in CAUSA_DESCRICOES.items():
            rows.append(
                {
                    "COD_GRUPO_GCR": "",
                    "DESC_GRUPO_GCR": "Todos os grupos",
                    "COD_COMP": cod_comp,
                    "DESC_COMP": desc_comp,
                    "COD_CAUSA": cod_causa,
                    "DESC_CAUSA": desc_causa,
                }
            )
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def _referencia_componentes_causas(db_path: str) -> pd.DataFrame:
    for table_name in REFERENCIA_COMPONENTE_CAUSA_TABLES:
        if not table_exists(db_path, table_name):
            continue
        with duckdb.connect(db_path, read_only=True) as con:
            columns = _table_columns(con, table_name)
            cod_grupo = _first_existing(columns, ["COD_GRUPO_GCR", "COD_GRUPO", "GRUPO"])
            desc_grupo = _first_existing(columns, ["DESC_GRUPO_GCR", "DESC_GRUPO", "GRUPO_DESCRICAO"])
            cod_comp = _first_existing(columns, ["COD_COMP", "COD_COMP_INTRP", "COMPONENTE"])
            desc_comp = _first_existing(columns, ["DESC_COMP", "DESC_COMPONENTE", "COMPONENTE_DESCRICAO"])
            cod_causa = _first_existing(columns, ["COD_CAUSA", "COD_CAUSA_INTRP", "CAUSA"])
            desc_causa = _first_existing(columns, ["DESC_CAUSA", "DESC_CAUSA_INTRP", "CAUSA_DESCRICAO"])
            if not cod_comp or not cod_causa:
                continue

            select_parts = [
                f"NULLIF(TRIM(CAST({cod_grupo} AS VARCHAR)), '') AS COD_GRUPO_GCR" if cod_grupo else "'' AS COD_GRUPO_GCR",
                f"NULLIF(TRIM(CAST({desc_grupo} AS VARCHAR)), '') AS DESC_GRUPO_GCR" if desc_grupo else "'Todos os grupos' AS DESC_GRUPO_GCR",
                f"NULLIF(TRIM(CAST({cod_comp} AS VARCHAR)), '') AS COD_COMP",
                f"NULLIF(TRIM(CAST({desc_comp} AS VARCHAR)), '') AS DESC_COMP" if desc_comp else "'' AS DESC_COMP",
                f"NULLIF(TRIM(CAST({cod_causa} AS VARCHAR)), '') AS COD_CAUSA",
                f"NULLIF(TRIM(CAST({desc_causa} AS VARCHAR)), '') AS DESC_CAUSA" if desc_causa else "'' AS DESC_CAUSA",
            ]
            df = con.execute(
                f"""
                SELECT DISTINCT
                    {", ".join(select_parts)}
                FROM {table_name}
                WHERE NULLIF(TRIM(CAST({cod_comp} AS VARCHAR)), '') IS NOT NULL
                  AND NULLIF(TRIM(CAST({cod_causa} AS VARCHAR)), '') IS NOT NULL
                ORDER BY DESC_GRUPO_GCR, DESC_COMP, DESC_CAUSA
                """
            ).fetchdf()
            if not df.empty:
                return df.fillna("").astype(str)

    return _fallback_referencia_componentes_causas()


def _referencia_options(df: pd.DataFrame, code_col: str, desc_col: str, default_code: str = "") -> list[str]:
    labels = [""]
    default_code = _normalizar_codigo(default_code)
    if default_code and default_code not in set(df.get(code_col, pd.Series(dtype=str)).astype(str)):
        labels.append(_ref_label(default_code, "Descrição não cadastrada"))

    if df.empty or code_col not in df.columns:
        return labels

    work = df[[code_col, desc_col]].drop_duplicates() if desc_col in df.columns else df[[code_col]].drop_duplicates()
    if desc_col not in work.columns:
        work[desc_col] = ""
    work = work.sort_values([desc_col, code_col])
    for _, row in work.iterrows():
        codigo = ajuste._clean_value(row.get(code_col))
        if not codigo:
            continue
        label = _ref_label(codigo, row.get(desc_col, ""))
        if label not in labels:
            labels.append(label)
    return labels


def _referencia_selectbox(
    label: str,
    df: pd.DataFrame,
    code_col: str,
    desc_col: str,
    default_code: str,
    key: str,
) -> str:
    options = _referencia_options(df, code_col, desc_col, default_code)
    default_code = _normalizar_codigo(default_code)
    default_label = next((option for option in options if _codigo_from_label(option) == default_code), "")
    index = options.index(default_label) if default_label in options else 0
    selected = st.selectbox(label, options, index=index, key=key)
    return _codigo_from_label(selected)


def _referencia_descricao(df: pd.DataFrame, code_col: str, desc_col: str, codigo: str, fallback: dict[str, str]) -> str:
    codigo = _normalizar_codigo(codigo, fallback)
    if not codigo:
        return ""
    if not df.empty and code_col in df.columns and desc_col in df.columns:
        matches = df[df[code_col].astype(str).str.strip() == codigo]
        if not matches.empty:
            descricao = ajuste._clean_value(matches.iloc[0].get(desc_col, ""))
            if descricao:
                return descricao
    return fallback.get(codigo, "Descrição não cadastrada")


def _grupo_default_por_componente(referencia_df: pd.DataFrame, cod_comp: str) -> str:
    cod_comp = _normalizar_codigo(cod_comp)
    if not cod_comp or referencia_df.empty:
        return ""
    matches = referencia_df[referencia_df["COD_COMP"].astype(str).str.strip() == cod_comp]
    if matches.empty:
        return ""
    return ajuste._clean_value(matches.iloc[0].get("COD_GRUPO_GCR", ""))


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
    causa_sugerida = _first_list_value(row.get("SUGESTAO_COD_CAUSA_INTRP")) or _first_list_value(row.get("CAUSAS_SERVICO"))
    componente_sugerido = _first_list_value(row.get("SUGESTAO_COD_COMP_INTRP")) or _first_list_value(row.get("COMPONENTES_SERVICO"))
    pares_inconsistentes = _row_value(row, ["PARES_COMP_CAUSA_INCONSISTENTES"])
    sugestao_pares = _row_value(row, ["SUGESTAO_PARES_COMP_CAUSA"])
    justificativa_partes = [
        _row_value(row, ["CLASSIFICACAO_QUALIDADE"]),
        f"score={_row_value(row, ['SCORE_QUALIDADE'])}" if _row_value(row, ["SCORE_QUALIDADE"]) else "",
        f"pares inconsistentes={pares_inconsistentes}" if pares_inconsistentes else "",
        f"sugestao componente/causa={sugestao_pares}" if sugestao_pares else "",
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
        "NOVO_COD_CAUSA_INTRP": causa_sugerida,
        "NOVO_COD_COMP_INTRP": componente_sugerido,
        "PARES_COMP_CAUSA_INCONSISTENTES": pares_inconsistentes,
        "SUGESTAO_PARES_COMP_CAUSA": sugestao_pares,
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
            causa_sugerida = _first_list_value(_row_value(row, ["SUGESTAO_COD_CAUSA_INTRP", "CAUSAS_SERVICO"]))
            comp_sugerido = _first_list_value(_row_value(row, ["SUGESTAO_COD_COMP_INTRP", "COMPONENTES_SERVICO"]))
            justificativa = _row_value(row, ["SUGESTAO_PARES_COMP_CAUSA", "PREVIA_CAUSA_RECLAMACAO", "CAUSA_PROVAVEL_RECLAMACAO"])
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
        "PARES_COMP_CAUSA_INCONSISTENTES",
        "SUGESTAO_PARES_COMP_CAUSA",
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
                "INCONSISTENCIA_COMPONENTE_CAUSA",
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
                "QTD_INCONSISTENCIA_COMP_CAUSA",
                "PARES_COMP_CAUSA_INCONSISTENTES",
                "SUGESTAO_PARES_COMP_CAUSA",
                "SUGESTAO_COD_CAUSA_INTRP",
                "SUGESTAO_COD_COMP_INTRP",
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

            referencia_iqs = _referencia_componentes_causas(db_path)
            default_comp = defaults.get("NOVO_COD_COMP_INTRP", "")
            default_causa = defaults.get("NOVO_COD_CAUSA_INTRP", "")
            default_grupo = _grupo_default_por_componente(referencia_iqs, default_comp)

            st.markdown("#### Campos IQS a alterar")
            col_grupo, col_comp, col_desc_comp = st.columns([1, 1, 2])
            with col_grupo:
                cod_grupo = _referencia_selectbox(
                    "GRUPO_COMPONENTE_REDE",
                    referencia_iqs,
                    "COD_GRUPO_GCR",
                    "DESC_GRUPO_GCR",
                    default_grupo,
                    _widget_key("grupo_comp", defaults),
                )

            componentes_df = referencia_iqs
            if cod_grupo:
                componentes_df = componentes_df[componentes_df["COD_GRUPO_GCR"].astype(str).str.strip() == cod_grupo]
            if componentes_df.empty:
                componentes_df = referencia_iqs

            with col_comp:
                novo_comp = _referencia_selectbox(
                    "COD_COMP_INTRP",
                    componentes_df,
                    "COD_COMP",
                    "DESC_COMP",
                    default_comp,
                    _widget_key("novo_comp", {**defaults, "COD_GRUPO_GCR": cod_grupo}),
                )
            with col_desc_comp:
                st.text_input(
                    "DESC_COMP_INTRP",
                    value=_referencia_descricao(componentes_df, "COD_COMP", "DESC_COMP", novo_comp, COMPONENTE_DESCRICOES),
                    disabled=True,
                    key=_widget_key("desc_comp", {**defaults, "NOVO_COD_COMP_INTRP": novo_comp, "COD_GRUPO_GCR": cod_grupo}),
                )

            causas_df = componentes_df
            if novo_comp:
                causas_df = componentes_df[componentes_df["COD_COMP"].astype(str).str.strip() == novo_comp]
            if causas_df.empty:
                causas_df = _fallback_referencia_componentes_causas()
                if novo_comp:
                    causas_df = causas_df[causas_df["COD_COMP"].astype(str).str.strip() == novo_comp]
                if causas_df.empty:
                    causas_df = _fallback_referencia_componentes_causas()

            col_causa, col_desc_causa = st.columns([1, 3])
            with col_causa:
                novo_causa = _referencia_selectbox(
                    "COD_CAUSA_INTRP",
                    causas_df,
                    "COD_CAUSA",
                    "DESC_CAUSA",
                    default_causa,
                    _widget_key("novo_causa", {**defaults, "NOVO_COD_COMP_INTRP": novo_comp}),
                )
            with col_desc_causa:
                st.text_input(
                    "DESC_CAUSA_INTRP",
                    value=_referencia_descricao(causas_df, "COD_CAUSA", "DESC_CAUSA", novo_causa, CAUSA_DESCRICOES),
                    disabled=True,
                    key=_widget_key("desc_causa", {**defaults, "NOVO_COD_CAUSA_INTRP": novo_causa, "NOVO_COD_COMP_INTRP": novo_comp}),
                )

            col_clima, col_tipo = st.columns(2)
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
