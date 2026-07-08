/*
Extracao de reclamacoes - dbguo
Fonte: dop_extracao_demandas_eventos.reclamacoes
*/
SELECT
    ss,
    data_reclamacao,
    reclamacao,
    informacao_retorno,
    CASE
        WHEN trim(CAST(uc AS TEXT)) ~ '^[0-9]+(\.0+)?$'
            THEN CAST(CAST(trim(CAST(uc AS TEXT)) AS NUMERIC) AS BIGINT)::VARCHAR
        ELSE NULLIF(trim(CAST(uc AS TEXT)), '')
    END AS uc
FROM dop_extracao_demandas_eventos.reclamacoes
WHERE NULLIF(trim(CAST(uc AS TEXT)), '') IS NOT NULL;
