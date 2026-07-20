-- MIDWAY 7.0.0
-- PostgreSQL operational schema for local development and dBGUO/company deployment.
-- Target schema: ddcq
-- Execute as database owner/admin, for example postgres, ddcq_owner, or the TI provisioning user.
-- Do not execute this file as the restricted application user if it cannot create schemas/grants.

CREATE SCHEMA IF NOT EXISTS ddcq;

COMMENT ON SCHEMA ddcq IS
    'MIDWAY operational schema: ajustes, autorizacoes, fila tecnica, auditoria e exportacoes.';

-- As permissões e ALTER ROLE específicos para midway_app (ou usuário de aplicação corporativo)
-- devem ser executados manualmente pelo DBA no ambiente da COPEL conforme a governança, caso existam.
