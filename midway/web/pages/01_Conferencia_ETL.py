from __future__ import annotations

import streamlit as st

from midway.web.library.conferencia_etl import show_dic_fic, show_marts, show_overlaps, show_prodist, show_quality_metrics
from midway.web.library.shared import configure_page, render_header, render_sidebar

configure_page("MIDWAY - Conferência ETL")
render_header("01 Conferência ETL")
anomes, db_path, sample_limit, preview_rows = render_sidebar(include_preview_rows=True)

tabs = st.tabs(["Qualidade", "Sobreposição", "DIC/FIC", "Ressarcimento", "Arquivos"])
with tabs[0]:
    show_quality_metrics(anomes)
with tabs[1]:
    show_overlaps(str(db_path), sample_limit)
with tabs[2]:
    show_dic_fic(str(db_path))
with tabs[3]:
    show_prodist(str(db_path), sample_limit)
with tabs[4]:
    show_marts(anomes, preview_rows)
