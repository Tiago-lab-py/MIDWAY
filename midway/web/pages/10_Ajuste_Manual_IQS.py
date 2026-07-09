from __future__ import annotations

from midway.web.library.ajuste_manual_iqs import show_ajuste_manual_iqs
from midway.web.library.shared import configure_page, render_header, render_sidebar


configure_page("MIDWAY - Ajuste Manual IQS")
render_header("10 Ajuste Manual IQS")
anomes, db_path, sample_limit, _ = render_sidebar()
show_ajuste_manual_iqs(anomes, str(db_path), sample_limit)
