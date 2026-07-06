from __future__ import annotations

from midway.web.library.shared import configure_page, render_header, render_sidebar
from midway.web.library.simulacao_ise import show_ise_simulation

configure_page("MIDWAY - Simulação ISE")
render_header("04 Simulação ISE")
_, db_path, sample_limit, _ = render_sidebar()
show_ise_simulation(str(db_path), sample_limit)
