from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text

from midway.db.postgres import create_postgres_engine, get_config


def show_outlier_anomalia(sample_limit: int = 500) -> None:
    st.subheader("Ocorrências - Outliers (midway_anomalia)")

    try:
        config = get_config()
        engine = create_postgres_engine(config)
        schema = config.schema or "ddcq"

        sql = f"""
            SELECT 
                id_anomalia, anomes, registro_id, anomalia_codigo, nome, 
                categoria, severidade, confianca, status_anomalia, origem, 
                regional, conjunto, equipamento, uc, ocorrencia, interrupcao, 
                descricao, explicacao_simples, explicacao_tecnica, regra_violada, 
                impacto_possivel, campos_envolvidos, dados_originais, 
                dados_sugeridos, impacto, linha_tempo, criado_por, criado_em, 
                atualizado_por, atualizado_em
            FROM {schema}.midway_anomalia
            LIMIT :limit
        """

        with engine.connect() as con:
            rows = con.execute(text(sql), {"limit": sample_limit}).mappings().all()

        if not rows:
            st.info("Nenhuma anomalia encontrada.")
            return

        df = pd.DataFrame([dict(row) for row in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Exibindo até {sample_limit} registros da tabela midway_anomalia.")

    except Exception as error:
        st.error(f"Falha ao consultar a tabela midway_anomalia: {error}")
