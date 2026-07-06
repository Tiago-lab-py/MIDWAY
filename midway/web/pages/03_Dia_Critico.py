from __future__ import annotations

from midway.web.library.dia_critico import show_dia_critico
from midway.web.library.shared import configure_page, render_header, render_sidebar

configure_page("MIDWAY - Dia Crítico")
render_header("03 Dia Crítico")
_, db_path, sample_limit, _ = render_sidebar()
show_dia_critico(str(db_path), sample_limit)
