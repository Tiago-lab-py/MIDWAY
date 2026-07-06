import os
from datetime import date, datetime, time, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from midway.ise.simulacao_janela_v2 import (
    CAUSAS_ISE,
    JanelaISE,
    calcular_simulacao_ise_por_janela,
    regionais_disponiveis,
    resumo_causas,
    resumo_simulacao,
)


def db_path(anomes: str) -> Path:
    return Path("data") / "processed" / f"iqs_adms_processed_{anomes}.duckdb"


def csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = StringIO()
    df.to_csv(buffer, sep="|", index=False)
    return buffer.getvalue().encode("utf-8")


def chave_janelas(anomes: str) -> str:
    return f"ise_janelas_v2_{anomes}"


def janela_linha(nome: str, regional: str, inicio: datetime, fim: datetime) -> dict:
    return {
        "Selecionar": True,
        "Regional": regional,
        "Nome": nome,
        "Inicio": inicio,
        "Fim": fim,
    }


def adicionar_janela(anomes: str, regional: str, inicio: datetime, fim: datetime) -> None:
    chave = chave_janelas(anomes)
    atual = st.session_state.get(chave)
    if atual is None:
        atual = pd.DataFrame(columns=["Selecionar", "Regional", "Nome", "Inicio", "Fim"])

    proximo = len(atual) + 1
    nova = pd.DataFrame([janela_linha(f"Janela {proximo}", regional, inicio, fim)])
    st.session_state[chave] = pd.concat([atual, nova], ignore_index=True)


def preparar_janelas(df: pd.DataFrame) -> list[JanelaISE]:
    if df.empty:
        return []

    selecionadas = df[df["Selecionar"]]
    janelas = []
    for indice, row in selecionadas.iterrows():
        inicio = pd.to_datetime(row.get("Inicio"), errors="coerce")
        fim = pd.to_datetime(row.get("Fim"), errors="coerce")
        if pd.isna(inicio) or pd.isna(fim):
            continue

        nome = str(row.get("Nome") or f"Janela {indice + 1}").strip()
        regional = str(row.get("Regional") or "Todas").strip()
        janelas.append(
            JanelaISE(
                nome=nome,
                regional=regional,
                inicio=inicio.to_pydatetime(),
                fim=fim.to_pydatetime(),
            )
        )

    return janelas


def salvar_resultados(
    anomes: str,
    df_uc: pd.DataFrame,
    df_ocorrencia: pd.DataFrame,
    df_causas: pd.DataFrame,
) -> tuple[Path, Path, Path, Path]:
    marts_dir = Path("data") / "marts"
    marts_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    csv_uc = marts_dir / f"Simulacao_ISE_Janela_UC_{anomes}_{timestamp}.CSV"
    csv_ocorrencia = marts_dir / f"Simulacao_ISE_Janela_Ocorrencia_{anomes}_{timestamp}.CSV"
    csv_causas = marts_dir / f"Simulacao_ISE_Janela_Causas_{anomes}_{timestamp}.CSV"
    resumo_path = marts_dir / f"Simulacao_ISE_Janela_{anomes}_{timestamp}_RESUMO.TXT"

    df_uc.to_csv(csv_uc, sep="|", index=False, encoding="utf-8")
    df_ocorrencia.to_csv(csv_ocorrencia, sep="|", index=False, encoding="utf-8")
    df_causas.to_csv(csv_causas, sep="|", index=False, encoding="utf-8")

    resumo = resumo_simulacao(df_uc)
    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("SIMULACAO ISE POR JANELA\n")
        arquivo.write(f"ANOMES: {anomes}\n")
        arquivo.write(f"CSV UC: {csv_uc}\n")
        arquivo.write(f"CSV OCORRENCIA: {csv_ocorrencia}\n")
        arquivo.write(f"CSV CAUSAS: {csv_causas}\n")
        arquivo.write("Regra: bruto verifica potencial ISE; liquido mede reclassificacao.\n")
        arquivo.write(f"Causas ISE: {', '.join(CAUSAS_ISE)}\n\n")
        arquivo.write(f"UCs avaliadas: {resumo['ucs']:.0f}\n")
        arquivo.write(f"UCs com potencial ISE bruto: {resumo['ucs_potencial']:.0f}\n")
        arquivo.write(f"UCs com ISE liquido reclassificavel: {resumo['ucs_reclassificavel']:.0f}\n")
        arquivo.write(f"CI bruto referencia: {resumo['ci_bruto']}\n")
        arquivo.write(f"CI liquido reclassificavel: {resumo['ci_liquido']}\n")
        arquivo.write(f"CHI bruto referencia: {resumo['chi_bruto']}\n")
        arquivo.write(f"CHI liquido reclassificavel: {resumo['chi_liquido']}\n")

    return csv_uc, csv_ocorrencia, csv_causas, resumo_path


def mostrar_simulacao_ise_por_janela() -> None:
    st.divider()
    aba_janela, aba_regra = st.tabs(["Simulação ISE por Janela", "Regra das Janelas"])

    with aba_janela:
        st.subheader("Simulação ISE por Janela")
        st.caption("Bruto verifica potencial ISE; líquido mede quanto poderá ser reclassificado.")

        anomes_padrao = os.getenv("ANOMES", "202606")
        col_anomes, col_regional = st.columns([1, 2])
        with col_anomes:
            anomes = st.text_input("ANOMES da simulação", value=anomes_padrao, key="ise_janela_v2_anomes")

        caminho_db = db_path(anomes)
        if not caminho_db.exists():
            st.error(f"DuckDB processado não encontrado: {caminho_db}")
            return

        try:
            regionais = regionais_disponiveis(caminho_db)
        except Exception as exc:
            st.error(f"Erro ao carregar regionais: {exc}")
            return

        opcoes_regionais = ["Todas"] + regionais
        with col_regional:
            regional_padrao = st.selectbox("Regional", opcoes_regionais, key="ise_janela_v2_regional_padrao")

        ano = int(anomes[:4]) if len(anomes) >= 4 and anomes[:4].isdigit() else date.today().year
        mes = int(anomes[4:6]) if len(anomes) >= 6 and anomes[4:6].isdigit() else date.today().month
        data_inicio_padrao = date(ano, mes, 1)
        data_fim_padrao = (
            date(ano + 1, 1, 1) - timedelta(days=1)
            if mes == 12
            else date(ano, mes + 1, 1) - timedelta(days=1)
        )

        col_inicio, col_fim = st.columns(2)
        with col_inicio:
            periodo_inicio_data = st.date_input(
                "Início do período",
                value=data_inicio_padrao,
                key="ise_janela_v2_periodo_inicio",
            )
        with col_fim:
            periodo_fim_data = st.date_input(
                "Fim do período",
                value=data_fim_padrao,
                key="ise_janela_v2_periodo_fim",
            )

        periodo_inicio = datetime.combine(periodo_inicio_data, time(0, 0))
        periodo_fim = datetime.combine(periodo_fim_data, time(23, 59, 59))

        col_incluir, col_limpar = st.columns([1, 1])
        with col_incluir:
            if st.button("Incluir janela", type="secondary", use_container_width=True):
                adicionar_janela(anomes, regional_padrao, periodo_inicio, periodo_fim)
        with col_limpar:
            if st.button("Limpar janelas", use_container_width=True):
                st.session_state[chave_janelas(anomes)] = pd.DataFrame(
                    columns=["Selecionar", "Regional", "Nome", "Inicio", "Fim"]
                )

        st.info(
            "Clique em Incluir janela para popular a tabela. Depois ajuste regional, data e horário diretamente na grade."
        )

        chave = chave_janelas(anomes)
        if chave not in st.session_state:
            st.session_state[chave] = pd.DataFrame(
                columns=["Selecionar", "Regional", "Nome", "Inicio", "Fim"]
            )

        janelas_df = st.data_editor(
            st.session_state[chave],
            num_rows="dynamic",
            use_container_width=True,
            key="ise_janela_v2_editor",
            column_config={
                "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=True),
                "Regional": st.column_config.SelectboxColumn("Regional", options=opcoes_regionais),
                "Nome": st.column_config.TextColumn("Nome"),
                "Inicio": st.column_config.DatetimeColumn("Início", format="DD/MM/YYYY HH:mm"),
                "Fim": st.column_config.DatetimeColumn("Fim", format="DD/MM/YYYY HH:mm"),
            },
        )
        st.session_state[chave] = janelas_df

        col_calcular, col_causas = st.columns([1, 3])
        with col_calcular:
            calcular = st.button("Calcular ISE por Janela", type="primary", use_container_width=True)
        with col_causas:
            st.caption(f"Causas elegíveis: {', '.join(CAUSAS_ISE)}")

        if calcular:
            try:
                janelas = preparar_janelas(janelas_df)
                fora_periodo = [
                    janela.nome
                    for janela in janelas
                    if janela.inicio >= periodo_fim or janela.fim <= periodo_inicio
                ]
                if fora_periodo:
                    st.warning("Janelas fora do período selecionado: " + ", ".join(fora_periodo))

                with st.spinner("Calculando ISE por janela..."):
                    df_uc, df_ocorrencia = calcular_simulacao_ise_por_janela(
                        caminho_db,
                        janelas=janelas,
                        periodo_inicio=periodo_inicio,
                        periodo_fim=periodo_fim,
                    )
                st.session_state["ise_janela_v2_uc"] = df_uc
                st.session_state["ise_janela_v2_ocorrencia"] = df_ocorrencia
                st.session_state["ise_janela_v2_causas"] = resumo_causas(df_ocorrencia)
            except Exception as exc:
                st.error(f"Não foi possível calcular a Simulação ISE por Janela: {exc}")

        df_uc = st.session_state.get("ise_janela_v2_uc")
        df_ocorrencia = st.session_state.get("ise_janela_v2_ocorrencia")
        df_causas = st.session_state.get("ise_janela_v2_causas")

        if df_uc is not None and df_ocorrencia is not None and df_causas is not None:
            resumo = resumo_simulacao(df_uc)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("UCs", f"{resumo['ucs']:.0f}")
            c2.metric("UCs potencial ISE", f"{resumo['ucs_potencial']:.0f}")
            c3.metric("CHI bruto", f"{resumo['chi_bruto']:,.2f}")
            c4.metric("CHI líquido reclassificável", f"{resumo['chi_liquido']:,.2f}")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("UCs reclassificáveis", f"{resumo['ucs_reclassificavel']:.0f}")
            c6.metric("CI bruto", f"{resumo['ci_bruto']:,.0f}")
            c7.metric("CI líquido", f"{resumo['ci_liquido']:,.0f}")
            c8.metric("Ocorrências", f"{len(df_ocorrencia):,.0f}")

            st.subheader("Resumo por causas")
            st.dataframe(df_causas, use_container_width=True, hide_index=True)

            st.subheader("Ocorrências e interrupções da simulação")
            st.caption("Tabela demonstrativa sem detalhe de UC.")
            st.dataframe(df_ocorrencia, use_container_width=True, hide_index=True)

            st.subheader("Resultado por UC e Janela")
            st.dataframe(df_uc, use_container_width=True, hide_index=True)

            col_down1, col_down2, col_down3 = st.columns(3)
            with col_down1:
                st.download_button(
                    "Baixar CSV por causas",
                    data=csv_bytes(df_causas),
                    file_name=f"Simulacao_ISE_Janela_Causas_{anomes}.CSV",
                    mime="text/csv",
                )
            with col_down2:
                st.download_button(
                    "Baixar CSV ocorrências",
                    data=csv_bytes(df_ocorrencia),
                    file_name=f"Simulacao_ISE_Janela_Ocorrencia_{anomes}.CSV",
                    mime="text/csv",
                )
            with col_down3:
                st.download_button(
                    "Baixar CSV por UC",
                    data=csv_bytes(df_uc),
                    file_name=f"Simulacao_ISE_Janela_UC_{anomes}.CSV",
                    mime="text/csv",
                )

            if st.button("Salvar resultados em data\\marts", key="ise_janela_v2_salvar"):
                csv_uc, csv_ocorrencia, csv_causas, resumo_path = salvar_resultados(
                    anomes,
                    df_uc,
                    df_ocorrencia,
                    df_causas,
                )
                st.success(
                    f"Arquivos salvos: {csv_causas} | {csv_ocorrencia} | {csv_uc} | {resumo_path}"
                )

    with aba_regra:
        st.markdown(
            """
            ### Regra operacional

            - Clique em **Incluir janela** para popular a grade com o período e regional selecionados.
            - Depois ajuste data, horário e regional diretamente na tabela.
            - O cálculo ocorre somente nas janelas selecionadas.
            - O `CHI bruto` verifica se houve potencial ISE.
            - O `CHI líquido` mede quanto poderá ser reclassificado.
            - A duração é limitada à interseção entre evento e janela.

            **Causas elegíveis para ISE:** `2, 4, 5, 6, 7, 8, 9, 13, 15, 23, 24, 28, 39, 40, 41, 52, 54, 69, 82`.

            `COD_CAUSA_INTRP = 52` é elegível para ISE.  
            `COD_COMP_INTRP = 52` continua sendo regra separada de compensação/ressarcimento.
            """
        )
