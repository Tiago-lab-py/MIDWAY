-- MIDWAY 7.0.0
-- Initial operational parameters for schema ddcq.

SET search_path TO ddcq, public;

INSERT INTO midway_parametro (chave, valor, descricao, atualizado_por)
VALUES
    (
        'midway.version.target',
        '7.0.0',
        'Versao alvo da arquitetura PostgreSQL operacional.',
        'setup'
    ),
    (
        'midway.schema',
        'ddcq',
        'Schema operacional padrao do MIDWAY.',
        'setup'
    ),
    (
        'midway.env',
        'local',
        'Ambiente corrente. Em producao empresa, alterar para empresa.',
        'setup'
    ),
    (
        'regra.9282.automatico',
        'SERVICO+ROBUSTA',
        'Somente RA 92/82 com evidencia de servico robusta pode gerar ajuste automatico executivo.',
        'setup'
    ),
    (
        'regra.9282.manual',
        'SERVICO_CONFLITO+RECLAMACAO',
        'Conflitos de servico e sugestoes por reclamacao entram na fila tecnica/manual.',
        'setup'
    ),
    (
        'exportacao.iqs.apenas_aprovados',
        'S',
        'Exportacao IQS deve usar somente ajustes aprovados.',
        'setup'
    )
ON CONFLICT (chave) DO UPDATE
SET
    valor = EXCLUDED.valor,
    descricao = EXCLUDED.descricao,
    atualizado_por = EXCLUDED.atualizado_por,
    atualizado_em = now();

