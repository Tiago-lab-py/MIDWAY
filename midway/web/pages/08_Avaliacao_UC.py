from __future__ import annotations

import streamlit as st

from midway.web.library.avaliacao_uc import show_consulta_uc, show_outlier_uc
from midway.web.library.reclamacoes_uc import show_reclamacoes_uc
from midway.web.library.shared import configure_page, render_header, render_sidebar


configure_page("MIDWAY - Avaliação de UC")
render_header("08 Avaliação de UC")
_, db_path, sample_limit, _ = render_sidebar()

tabs = st.tabs(["Outlier UC", "Consulta UC", "Reclamações UC"])
with tabs[0]:
    show_outlier_uc(str(db_path), sample_limit)
with tabs[1]:
    show_consulta_uc(str(db_path), sample_limit)
with tabs[2]:
    show_reclamacoes_uc(str(db_path), sample_limit)
