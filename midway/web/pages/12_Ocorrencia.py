from __future__ import annotations

import streamlit as st

from midway.web.library.ocorrencia import show_outlier_anomalia
from midway.web.library.shared import configure_page, render_header, render_sidebar


configure_page("MIDWAY - Ocorrência")
render_header("12 Ocorrência")
_, db_path, sample_limit, _ = render_sidebar()

tabs = st.tabs(["Outlier"])
with tabs[0]:
    show_outlier_anomalia(sample_limit)
