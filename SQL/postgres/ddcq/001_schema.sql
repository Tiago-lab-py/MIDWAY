-- MIDWAY 7.0.0
-- PostgreSQL operational schema for local development and dBGUO/company deployment.
-- Target schema: ddcq
-- Execute as database owner/admin, for example postgres, ddcq_owner, or the TI provisioning user.
-- Do not execute this file as the restricted application user if it cannot create schemas/grants.

CREATE SCHEMA IF NOT EXISTS ddcq AUTHORIZATION midway_app;

COMMENT ON SCHEMA ddcq IS
    'MIDWAY operational schema: ajustes, autorizacoes, fila tecnica, auditoria e exportacoes.';

-- Recommended local/app role grants.
-- In the company environment, TI may replace midway_app with the official application user.
GRANT USAGE ON SCHEMA ddcq TO midway_app;
GRANT CREATE ON SCHEMA ddcq TO midway_app;

ALTER ROLE midway_app IN DATABASE midway SET search_path TO ddcq, public;
