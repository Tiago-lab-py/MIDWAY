from __future__ import annotations

from midway.web.library.avaliacao_uc import show_avaliacao_uc
from midway.web.library.shared import configure_page, render_header, render_sidebar


configure_page("MIDWAY - Avaliação de UC")
render_header("08 Avaliação de UC")
_, db_path, sample_limit, _ = render_sidebar()

show_avaliacao_uc(str(db_path), sample_limit)
