from __future__ import annotations

from midway.web.library.page_sql import show_sql
from midway.web.library.shared import configure_page, render_header, render_sidebar

configure_page("MIDWAY - SQL")
render_header("07 SQL")
_, db_path, sample_limit, _ = render_sidebar()
show_sql(str(db_path), sample_limit)
