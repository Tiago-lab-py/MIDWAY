-- MIDWAY 7.0.0
-- Views de acompanhamento da tratativa RA 92/82 no schema ddcq.

SET search_path TO ddcq, public;

CREATE OR REPLACE VIEW vw_midway_9282_painel AS
WITH meses AS (
    SELECT anomes
    FROM midway_autorizacao_executiva
    WHERE tipo_autorizacao = 'RA_9282_AUTO'

    UNION

    SELECT anomes
    FROM midway_ajuste_iqs
    WHERE origem_ajuste = 'AUTO_EXECUTIVO_9282'

    UNION

    SELECT anomes
    FROM midway_fila_tecnica
    WHERE tipo_fila = 'RA_9282'
),
autorizacoes AS (
    SELECT
        anomes,
        COUNT(*) AS qtd_autorizacoes,
        SUM(qtd_candidatos) AS qtd_candidatos_autorizacao,
        SUM(qtd_autorizados) AS qtd_autorizados_autorizacao,
        SUM(qtd_rejeitados) AS qtd_rejeitados_autorizacao,
        MAX(autorizado_em) AS ultima_autorizacao_em
    FROM midway_autorizacao_executiva
    WHERE tipo_autorizacao = 'RA_9282_AUTO'
    GROUP BY anomes
),
ajustes AS (
    SELECT
        anomes,
        COUNT(*) AS ajustes_auto_9282,
        COUNT(*) FILTER (WHERE aprovado) AS ajustes_auto_aprovados,
        MAX(criado_em) AS ultimo_ajuste_em
    FROM midway_ajuste_iqs
    WHERE origem_ajuste = 'AUTO_EXECUTIVO_9282'
    GROUP BY anomes
),
fila AS (
    SELECT
        anomes,
        COUNT(*) AS fila_tecnica_total,
        COUNT(*) FILTER (WHERE status_fila = 'ABERTA') AS fila_aberta,
        COUNT(*) FILTER (WHERE status_fila = 'EM_ANALISE') AS fila_em_analise,
        COUNT(*) FILTER (WHERE status_fila = 'TRATADA') AS fila_tratada,
        COUNT(*) FILTER (WHERE status_fila = 'DESCARTADA') AS fila_descartada,
        COUNT(*) FILTER (WHERE status_fila = 'CANCELADA') AS fila_cancelada,
        COUNT(*) FILTER (WHERE nivel_evidencia = 'ROBUSTA_COM_CONFLITO') AS fila_servico_conflito,
        COUNT(*) FILTER (WHERE fonte_sugestao = 'RECLAMACAO') AS fila_reclamacao,
        MAX(criado_em) AS ultima_fila_em
    FROM midway_fila_tecnica
    WHERE tipo_fila = 'RA_9282'
    GROUP BY anomes
)
SELECT
    m.anomes,
    COALESCE(a.qtd_autorizacoes, 0) AS qtd_autorizacoes,
    COALESCE(a.qtd_candidatos_autorizacao, 0) AS qtd_candidatos_autorizacao,
    COALESCE(a.qtd_autorizados_autorizacao, 0) AS qtd_autorizados_autorizacao,
    COALESCE(a.qtd_rejeitados_autorizacao, 0) AS qtd_rejeitados_autorizacao,
    COALESCE(j.ajustes_auto_9282, 0) AS ajustes_auto_9282,
    COALESCE(j.ajustes_auto_aprovados, 0) AS ajustes_auto_aprovados,
    COALESCE(f.fila_tecnica_total, 0) AS fila_tecnica_total,
    COALESCE(f.fila_aberta, 0) AS fila_aberta,
    COALESCE(f.fila_em_analise, 0) AS fila_em_analise,
    COALESCE(f.fila_tratada, 0) AS fila_tratada,
    COALESCE(f.fila_descartada, 0) AS fila_descartada,
    COALESCE(f.fila_cancelada, 0) AS fila_cancelada,
    COALESCE(f.fila_servico_conflito, 0) AS fila_servico_conflito,
    COALESCE(f.fila_reclamacao, 0) AS fila_reclamacao,
    a.ultima_autorizacao_em,
    j.ultimo_ajuste_em,
    f.ultima_fila_em
FROM meses m
LEFT JOIN autorizacoes a ON a.anomes = m.anomes
LEFT JOIN ajustes j ON j.anomes = m.anomes
LEFT JOIN fila f ON f.anomes = m.anomes;

COMMENT ON VIEW vw_midway_9282_painel IS
    'Painel consolidado da tratativa RA 92/82: autorização executiva, ajustes automáticos e fila técnica.';

CREATE OR REPLACE VIEW vw_midway_9282_ajustes_auto AS
SELECT
    a.anomes,
    a.id_ajuste,
    a.id_autorizacao,
    a.aprovado,
    a.num_ocorrencia_adms,
    a.num_seq_intrp,
    a.sigla_regional,
    a.cod_comp_intrp_original,
    a.cod_causa_intrp_original,
    a.novo_cod_comp_intrp,
    a.novo_cod_causa_intrp,
    a.novo_valid_pos_operacao,
    a.justificativa,
    a.criado_por,
    a.criado_em,
    au.autorizado_por,
    au.autorizado_em
FROM midway_ajuste_iqs a
LEFT JOIN midway_autorizacao_executiva au
    ON au.id_autorizacao = a.id_autorizacao
WHERE a.origem_ajuste = 'AUTO_EXECUTIVO_9282';

COMMENT ON VIEW vw_midway_9282_ajustes_auto IS
    'Detalhe dos ajustes automáticos RA 92/82 autorizados pelo Executivo.';

CREATE OR REPLACE VIEW vw_midway_9282_fila_tecnica AS
SELECT
    anomes,
    id_fila,
    prioridade,
    status_fila,
    num_ocorrencia_adms,
    num_seq_intrp,
    cod_comp_atual,
    cod_causa_atual,
    cod_comp_sugerido,
    cod_causa_sugerida,
    fonte_sugestao,
    nivel_evidencia,
    score_sugestao,
    evidencia_resumo,
    responsavel,
    criado_em,
    atualizado_em
FROM midway_fila_tecnica
WHERE tipo_fila = 'RA_9282';

COMMENT ON VIEW vw_midway_9282_fila_tecnica IS
    'Detalhe da fila técnica RA 92/82 para tratamento manual.';

CREATE OR REPLACE VIEW vw_midway_9282_auditoria AS
SELECT
    anomes,
    id_evento,
    tipo_evento,
    entidade,
    id_entidade,
    usuario,
    detalhe,
    criado_em
FROM midway_auditoria_evento
WHERE tipo_evento = 'AUTORIZACAO_9282';

COMMENT ON VIEW vw_midway_9282_auditoria IS
    'Auditoria das autorizações executivas RA 92/82.';
