from pathlib import Path


MARCADOR_INICIO = "# >>> MIDWAY ISE POR JANELA"
MARCADOR_FIM = "# <<< MIDWAY ISE POR JANELA"


BLOCO = r'''

# >>> MIDWAY ISE POR JANELA
import os as _ise_os
from datetime import date as _ise_date
from datetime import datetime as _ise_datetime
from datetime import time as _ise_time
from datetime import timedelta as _ise_timedelta
from io import StringIO as _ise_StringIO
from pathlib import Path as _ise_Path

import pandas as _ise_pd
import streamlit as _ise_st

from midway.ise.simulacao_janela import (
    CAUSAS_ISE as _ISE_CAUSAS,
    JanelaISE as _JanelaISE,
    calcular_simulacao_ise_por_janela as _calcular_ise_janela,
    regionais_disponiveis as _regionais_ise,
    resumo_simulacao as _resumo_ise,
)


def _ise_db_path(anomes: str) -> _ise_Path:
    return _ise_Path("data") / "processed" / f"iqs_adms_processed_{anomes}.duckdb"


def _ise_janelas_padrao(periodo_inicio: _ise_datetime, periodo_fim: _ise_datetime) -> _ise_pd.DataFrame:
    return _ise_pd.DataFrame(
        [
            {
                "Selecionar": True,
                "Nome": "Janela 1",
                "Inicio": periodo_inicio,
                "Fim": periodo_fim,
            }
        ]
    )


def _ise_preparar_janelas(df: _ise_pd.DataFrame) -> list[_JanelaISE]:
    janelas = []
    for indice, row in df[df["Selecionar"]].iterrows():
        inicio = _ise_pd.to_datetime(row.get("Inicio"), errors="coerce")
        fim = _ise_pd.to_datetime(row.get("Fim"), errors="coerce")
        if _ise_pd.isna(inicio) or _ise_pd.isna(fim):
            continue
        nome = str(row.get("Nome") or f"Janela {indice + 1}").strip()
        janelas.append(_JanelaISE(nome=nome, inicio=inicio.to_pydatetime(), fim=fim.to_pydatetime()))
    return janelas


def _ise_csv_bytes(df: _ise_pd.DataFrame) -> bytes:
    buffer = _ise_StringIO()
    df.to_csv(buffer, sep="|", index=False)
    return buffer.getvalue().encode("utf-8")


def _ise_salvar_resultado(df: _ise_pd.DataFrame, anomes: str) -> tuple[_ise_Path, _ise_Path]:
    marts_dir = _ise_Path("data") / "marts"
    marts_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _ise_datetime.now().strftime("%Y%m%d%H%M%S")
    csv_path = marts_dir / f"Simulacao_ISE_Janela_{anomes}_{timestamp}.CSV"
    resumo_path = marts_dir / f"Simulacao_ISE_Janela_{anomes}_{timestamp}_RESUMO.TXT"

    df.to_csv(csv_path, sep="|", index=False, encoding="utf-8")
    resumo = _resumo_ise(df)

    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("SIMULACAO ISE POR JANELA\n")
        arquivo.write(f"ANOMES: {anomes}\n")
        arquivo.write(f"CSV: {csv_path}\n")
        arquivo.write("Regra: bruto verifica potencial ISE; liquido mede reclassificacao.\n")
        arquivo.write(f"Causas ISE: {', '.join(_ISE_CAUSAS)}\n\n")
        arquivo.write(f"UCs avaliadas: {resumo['ucs']:.0f}\n")
        arquivo.write(f"UCs com potencial ISE bruto: {resumo['ucs_potencial']:.0f}\n")
        arquivo.write(f"UCs com ISE liquido reclassificavel: {resumo['ucs_reclassificavel']:.0f}\n")
        arquivo.write(f"CI bruto referencia: {resumo['ci_bruto']}\n")
        arquivo.write(f"CI liquido reclassificavel: {resumo['ci_liquido']}\n")
        arquivo.write(f"CHI bruto referencia: {resumo['chi_bruto']}\n")
        arquivo.write(f"CHI liquido reclassificavel: {resumo['chi_liquido']}\n")

    return csv_path, resumo_path


def _mostrar_simulacao_ise_por_janela():
    _ise_st.divider()
    aba_janela, aba_regra = _ise_st.tabs(["Simulação ISE por Janela", "Regra das Janelas"])

    with aba_janela:
        _ise_st.subheader("Simulação ISE por Janela")
        _ise_st.caption("Bruto verifica potencial ISE; líquido mede quanto poderá ser reclassificado.")

        anomes_padrao = _ise_os.getenv("ANOMES", "202606")
        col_anomes, col_regional = _ise_st.columns([1, 2])
        with col_anomes:
            anomes = _ise_st.text_input("ANOMES da simulação", value=anomes_padrao, key="ise_janela_anomes")

        caminho_db = _ise_db_path(anomes)
        if not caminho_db.exists():
            _ise_st.error(f"DuckDB processado não encontrado: {caminho_db}")
            return

        try:
            regionais = _regionais_ise(caminho_db)
        except Exception as exc:
            _ise_st.error(f"Erro ao carregar regionais: {exc}")
            return

        with col_regional:
            regional = _ise_st.selectbox(
                "Regional",
                ["Todas"] + regionais,
                key="ise_janela_regional",
            )

        ano = int(anomes[:4]) if len(anomes) >= 4 and anomes[:4].isdigit() else _ise_date.today().year
        mes = int(anomes[4:6]) if len(anomes) >= 6 and anomes[4:6].isdigit() else _ise_date.today().month
        data_inicio_padrao = _ise_date(ano, mes, 1)
        data_fim_padrao = (
            _ise_date(ano + 1, 1, 1) - _ise_timedelta(days=1)
            if mes == 12
            else _ise_date(ano, mes + 1, 1) - _ise_timedelta(days=1)
        )

        col_inicio, col_fim = _ise_st.columns(2)
        with col_inicio:
            periodo_inicio_data = _ise_st.date_input(
                "Início do período",
                value=data_inicio_padrao,
                key="ise_janela_periodo_inicio",
            )
        with col_fim:
            periodo_fim_data = _ise_st.date_input(
                "Fim do período",
                value=data_fim_padrao,
                key="ise_janela_periodo_fim",
            )

        periodo_inicio = _ise_datetime.combine(periodo_inicio_data, _ise_time(0, 0))
        periodo_fim = _ise_datetime.combine(periodo_fim_data, _ise_time(23, 59, 59))

        _ise_st.info(
            "O cálculo só considera eventos que cruzam as janelas selecionadas. "
            "A duração usada no CHI é limitada à interseção entre o evento e a janela."
        )

        chave_janelas = (
            f"ise_janelas_df_{anomes}_{periodo_inicio:%Y%m%d%H%M%S}_{periodo_fim:%Y%m%d%H%M%S}"
        )
        if chave_janelas not in _ise_st.session_state:
            _ise_st.session_state[chave_janelas] = _ise_janelas_padrao(periodo_inicio, periodo_fim)

        janelas_df = _ise_st.data_editor(
            _ise_st.session_state[chave_janelas],
            num_rows="dynamic",
            use_container_width=True,
            key="ise_janela_editor",
            column_config={
                "Selecionar": _ise_st.column_config.CheckboxColumn("Selecionar", default=True),
                "Nome": _ise_st.column_config.TextColumn("Nome"),
                "Inicio": _ise_st.column_config.DatetimeColumn("Início", format="DD/MM/YYYY HH:mm"),
                "Fim": _ise_st.column_config.DatetimeColumn("Fim", format="DD/MM/YYYY HH:mm"),
            },
        )
        _ise_st.session_state[chave_janelas] = janelas_df

        col_botao, col_causas = _ise_st.columns([1, 3])
        with col_botao:
            calcular = _ise_st.button("Calcular ISE por Janela", type="primary", use_container_width=True)
        with col_causas:
            _ise_st.caption(f"Causas elegíveis: {', '.join(_ISE_CAUSAS)}")

        if calcular:
            try:
                janelas = _ise_preparar_janelas(janelas_df)
                fora_periodo = [
                    janela.nome
                    for janela in janelas
                    if janela.inicio >= periodo_fim or janela.fim <= periodo_inicio
                ]
                if fora_periodo:
                    _ise_st.warning(
                        "Janelas fora do período selecionado: " + ", ".join(fora_periodo)
                    )

                with _ise_st.spinner("Calculando ISE por janela..."):
                    resultado = _calcular_ise_janela(
                        caminho_db,
                        janelas=janelas,
                        regional=regional,
                        periodo_inicio=periodo_inicio,
                        periodo_fim=periodo_fim,
                    )
                _ise_st.session_state["ise_janela_resultado"] = resultado
            except Exception as exc:
                _ise_st.error(f"Não foi possível calcular a Simulação ISE por Janela: {exc}")

        resultado = _ise_st.session_state.get("ise_janela_resultado")
        if resultado is not None:
            resumo = _resumo_ise(resultado)
            c1, c2, c3, c4 = _ise_st.columns(4)
            c1.metric("UCs", f"{resumo['ucs']:.0f}")
            c2.metric("UCs potencial ISE", f"{resumo['ucs_potencial']:.0f}")
            c3.metric("CHI bruto", f"{resumo['chi_bruto']:,.2f}")
            c4.metric("CHI líquido reclassificável", f"{resumo['chi_liquido']:,.2f}")

            c5, c6, c7, c8 = _ise_st.columns(4)
            c5.metric("UCs reclassificáveis", f"{resumo['ucs_reclassificavel']:.0f}")
            c6.metric("CI bruto", f"{resumo['ci_bruto']:,.0f}")
            c7.metric("CI líquido", f"{resumo['ci_liquido']:,.0f}")
            c8.metric("Linhas", f"{len(resultado):,.0f}")

            _ise_st.dataframe(resultado, use_container_width=True, hide_index=True)

            _ise_st.download_button(
                "Baixar CSV da Simulação por Janela",
                data=_ise_csv_bytes(resultado),
                file_name=f"Simulacao_ISE_Janela_{anomes}.CSV",
                mime="text/csv",
            )

            if _ise_st.button("Salvar resultado em data\\marts", key="ise_janela_salvar"):
                csv_path, resumo_path = _ise_salvar_resultado(resultado, anomes)
                _ise_st.success(f"Arquivos salvos: {csv_path} | {resumo_path}")

    with aba_regra:
        _ise_st.markdown(
            """
            ### Regra operacional

            - O cálculo ocorre somente nas janelas selecionadas.
            - O `CHI bruto` verifica se houve potencial ISE.
            - O `CHI líquido` mede quanto poderá ser reclassificado.
            - A duração é limitada à interseção entre evento e janela.
            - Janelas sobrepostas não são aceitas para evitar dupla contagem.

            **Causas elegíveis para ISE:** `2, 4, 5, 6, 7, 8, 9, 13, 15, 23, 24, 28, 39, 40, 41, 52, 54, 69, 82`.

            `COD_CAUSA_INTRP = 52` é elegível para ISE.  
            `COD_COMP_INTRP = 52` continua sendo regra separada de compensação/ressarcimento.
            """
        )


_mostrar_simulacao_ise_por_janela()
# <<< MIDWAY ISE POR JANELA
'''


def encontrar_pagina() -> Path:
    candidatos = [
        Path("midway") / "web" / "pages" / "04_Simulacao_ISE.py",
        Path("pages") / "04_Simulacao_ISE.py",
        Path("04_Simulacao_ISE.py"),
    ]
    for candidato in candidatos:
        if candidato.exists():
            return candidato
    raise FileNotFoundError(
        "Nao encontrei 04_Simulacao_ISE.py. "
        "Execute este script na raiz do projeto D:\\MIDWAY_novo."
    )


def main() -> None:
    pagina = encontrar_pagina()
    texto = pagina.read_text(encoding="utf-8")

    if MARCADOR_INICIO in texto:
        print(f"A aba ISE por Janela ja esta instalada em: {pagina}")
        return

    backup = pagina.with_suffix(".py.bak_ise_janela")
    backup.write_text(texto, encoding="utf-8", newline="\n")
    pagina.write_text(texto.rstrip() + BLOCO, encoding="utf-8", newline="\n")

    print(f"Aba ISE por Janela instalada em: {pagina}")
    print(f"Backup criado em: {backup}")


if __name__ == "__main__":
    main()
