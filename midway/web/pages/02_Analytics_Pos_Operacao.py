from __future__ import annotations

import streamlit as st

from midway.web.library.analytics_pos_operacao import show_analytics, show_conjunto_diario
from midway.web.library.shared import configure_page, render_header, render_sidebar

configure_page("MIDWAY - Analytics Pós-Operação")
render_header("02 Analytics Pós-Operação")
_, db_path, sample_limit, _ = render_sidebar()

tabs = st.tabs(["Ranking Ocorrências", "Conjunto Diário"])
with tabs[0]:
    show_analytics(str(db_path), sample_limit)
with tabs[1]:
    show_conjunto_diario(str(db_path), sample_limit)
