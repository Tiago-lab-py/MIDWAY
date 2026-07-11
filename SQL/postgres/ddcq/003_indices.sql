-- MIDWAY 7.0.0
-- Indexes and idempotency constraints for schema ddcq.

SET search_path TO ddcq, public;

CREATE INDEX IF NOT EXISTS idx_midway_execucao_lote_anomes_tipo
    ON midway_execucao_lote(anomes, tipo_lote);

CREATE INDEX IF NOT EXISTS idx_midway_execucao_lote_status
    ON midway_execucao_lote(status_lote, iniciado_em);

CREATE INDEX IF NOT EXISTS idx_midway_autorizacao_anomes_tipo
    ON midway_autorizacao_executiva(anomes, tipo_autorizacao);

CREATE INDEX IF NOT EXISTS idx_midway_autorizacao_status
    ON midway_autorizacao_executiva(status_autorizacao, autorizado_em);

CREATE INDEX IF NOT EXISTS idx_midway_ajuste_iqs_anomes
    ON midway_ajuste_iqs(anomes);

CREATE INDEX IF NOT EXISTS idx_midway_ajuste_iqs_ocorrencia
    ON midway_ajuste_iqs(num_ocorrencia_adms);

CREATE INDEX IF NOT EXISTS idx_midway_ajuste_iqs_intrp
    ON midway_ajuste_iqs(num_seq_intrp);

CREATE INDEX IF NOT EXISTS idx_midway_ajuste_iqs_uc
    ON midway_ajuste_iqs(num_uc_uci);

CREATE INDEX IF NOT EXISTS idx_midway_ajuste_iqs_aprovado
    ON midway_ajuste_iqs(anomes, aprovado, origem_ajuste);

CREATE INDEX IF NOT EXISTS idx_midway_fila_tecnica_anomes_status
    ON midway_fila_tecnica(anomes, status_fila);

CREATE INDEX IF NOT EXISTS idx_midway_fila_tecnica_prioridade
    ON midway_fila_tecnica(status_fila, prioridade DESC, criado_em);

CREATE INDEX IF NOT EXISTS idx_midway_auditoria_evento_tipo_data
    ON midway_auditoria_evento(tipo_evento, criado_em);

CREATE INDEX IF NOT EXISTS idx_midway_auditoria_evento_entidade
    ON midway_auditoria_evento(entidade, id_entidade);

CREATE INDEX IF NOT EXISTS idx_midway_exportacao_iqs_anomes
    ON midway_exportacao_iqs(anomes, tipo_exportacao);

CREATE INDEX IF NOT EXISTS idx_midway_exportacao_iqs_status
    ON midway_exportacao_iqs(status_exportacao, gerado_em);

-- Idempotency for automatic executive treatment of RA 92/82.
-- Prevents creating the same automatic adjustment more than once for the same interruption.
CREATE UNIQUE INDEX IF NOT EXISTS uq_midway_ajuste_auto_9282
    ON midway_ajuste_iqs (
        anomes,
        num_seq_intrp,
        novo_cod_comp_intrp,
        novo_cod_causa_intrp,
        origem_ajuste
    )
    WHERE origem_ajuste = 'AUTO_EXECUTIVO_9282';

-- Avoid duplicated open technical queue items for the same rule/interruption/source.
CREATE UNIQUE INDEX IF NOT EXISTS uq_midway_fila_tecnica_aberta
    ON midway_fila_tecnica (
        anomes,
        tipo_fila,
        COALESCE(num_seq_intrp, ''),
        COALESCE(fonte_sugestao, ''),
        COALESCE(nivel_evidencia, '')
    )
    WHERE status_fila IN ('ABERTA', 'EM_ANALISE');

