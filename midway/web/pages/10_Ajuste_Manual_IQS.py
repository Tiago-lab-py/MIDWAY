from __future__ import annotations

from midway.web.library.envio_iqs import show_envio_iqs
from midway.web.library.shared import configure_page, render_header, render_sidebar


configure_page("MIDWAY - Envio IQS")
render_header("10 Envio IQS")
anomes, db_path, sample_limit, _ = render_sidebar()
show_envio_iqs(anomes, str(db_path), sample_limit)
