from __future__ import annotations

from midway.web.library.shared import configure_page, render_header, render_sidebar
from midway.web.library.validacao_pos_operacao import show_validacao_pos_operacao

configure_page("MIDWAY - Validação Pós-Operação")
render_header("05 Validação Pós-Operação")
_, db_path, sample_limit, _ = render_sidebar()
show_validacao_pos_operacao(str(db_path), sample_limit)
