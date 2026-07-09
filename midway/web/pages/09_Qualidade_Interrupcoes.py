from __future__ import annotations

from midway.web.library.qualidade_interrupcoes import show_qualidade_interrupcoes
from midway.web.library.shared import configure_page, render_header, render_sidebar


configure_page("MIDWAY - Qualidade de Interrupções")
render_header("09 Qualidade de Interrupções")
anomes, db_path, sample_limit, _ = render_sidebar()
show_qualidade_interrupcoes(anomes, str(db_path), sample_limit)
