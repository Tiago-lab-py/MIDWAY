from __future__ import annotations

from midway.web.library.executivo import show_executivo
from midway.web.library.shared import configure_page, render_header, render_sidebar

configure_page("MIDWAY - Executivo")
render_header("06 Executivo")
_, db_path, sample_limit, _ = render_sidebar()
show_executivo(str(db_path), sample_limit)
