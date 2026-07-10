/*
Referencia IQS para classificacao encadeada no Envio IQS.

Fluxo:
  1. Grupo de componente de rede
  2. Componente do grupo
  3. Causa permitida para o componente
*/

SELECT DISTINCT
    gcr.COD_GRUPO_GCR,
    gcr.DESC_GRUPO_GCR,
    comp.COD_COMP,
    comp.DESC_COMP,
    ca.COD_CAUSA,
    ca.DESC_CAUSA
FROM sod.GRUPO_COMPONENTE_REDE gcr
LEFT JOIN sod.COMPONENTE comp
    ON gcr.PID = comp.PID_GCR_COMP
LEFT JOIN sod.C_CAUSA cc
    ON comp.PIDC_CAUSA_COMP = cc.PID
LEFT JOIN sod.CAUSA ca
    ON cc.PID_REF = ca.PID
WHERE comp.COD_COMP IS NOT NULL
  AND ca.COD_CAUSA IS NOT NULL
ORDER BY
    gcr.COD_GRUPO_GCR,
    gcr.DESC_GRUPO_GCR,
    comp.COD_COMP,
    comp.DESC_COMP,
    ca.COD_CAUSA,
    ca.DESC_CAUSA
