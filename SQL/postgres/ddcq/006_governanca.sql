-- MIDWAY 7.0.0
-- Governanca, login, perfis e trilha de alteracoes.

SET search_path TO ddcq, public;

CREATE TABLE IF NOT EXISTS midway_usuario (
    id_usuario uuid PRIMARY KEY,
    login varchar(80) NOT NULL UNIQUE,
    nome varchar(160) NOT NULL,
    email varchar(180),
    perfil varchar(30) NOT NULL,
    status_usuario varchar(30) NOT NULL DEFAULT 'ATIVO',
    senha_hash text NOT NULL,
    ultimo_login_em timestamp,
    tentativas_invalidas integer NOT NULL DEFAULT 0,
    bloqueado_ate timestamp,
    criado_por varchar(120),
    criado_em timestamp NOT NULL DEFAULT now(),
    atualizado_por varchar(120),
    atualizado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_usuario_perfil
        CHECK (perfil IN ('ADM', 'GESTOR', 'ANALISTA', 'CONSULTA', 'AUDITOR')),
    CONSTRAINT ck_midway_usuario_status
        CHECK (status_usuario IN ('ATIVO', 'BLOQUEADO', 'INATIVO'))
);

COMMENT ON TABLE midway_usuario IS
    'Usuarios da aplicacao MIDWAY com perfis de governanca ADM, GESTOR, ANALISTA, CONSULTA e AUDITOR.';

ALTER TABLE midway_usuario
    DROP CONSTRAINT IF EXISTS ck_midway_usuario_perfil;

ALTER TABLE midway_usuario
    ADD CONSTRAINT ck_midway_usuario_perfil
        CHECK (perfil IN ('ADM', 'GESTOR', 'ANALISTA', 'CONSULTA', 'AUDITOR'));

CREATE TABLE IF NOT EXISTS midway_sessao (
    id_sessao uuid PRIMARY KEY,
    id_usuario uuid NOT NULL REFERENCES midway_usuario(id_usuario),
    token_hash text NOT NULL UNIQUE,
    ip_origem varchar(80),
    user_agent text,
    criado_em timestamp NOT NULL DEFAULT now(),
    expira_em timestamp NOT NULL,
    revogado_em timestamp,
    ultimo_uso_em timestamp
);

COMMENT ON TABLE midway_sessao IS
    'Sessoes autenticadas da API MIDWAY. Tokens sao armazenados apenas como hash.';

CREATE TABLE IF NOT EXISTS midway_reset_senha (
    id_reset uuid PRIMARY KEY,
    id_usuario uuid NOT NULL REFERENCES midway_usuario(id_usuario),
    solicitado_por varchar(120) NOT NULL,
    codigo_hash text NOT NULL,
    status_reset varchar(30) NOT NULL DEFAULT 'PENDENTE',
    tentativas integer NOT NULL DEFAULT 0,
    expira_em timestamp NOT NULL,
    confirmado_por varchar(120),
    confirmado_em timestamp,
    ip_origem varchar(80),
    justificativa text,
    criado_em timestamp NOT NULL DEFAULT now(),
    atualizado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_reset_senha_status
        CHECK (status_reset IN ('PENDENTE', 'CONFIRMADO', 'EXPIRADO', 'CANCELADO'))
);

COMMENT ON TABLE midway_reset_senha IS
    'Controle governado de reset de senha com codigo de confirmacao de 4 digitos.';

CREATE TABLE IF NOT EXISTS midway_perfil_permissao (
    perfil varchar(30) NOT NULL,
    pagina varchar(60) NOT NULL,
    pode_visualizar boolean NOT NULL DEFAULT false,
    pode_editar boolean NOT NULL DEFAULT false,
    atualizado_por varchar(120),
    atualizado_em timestamp NOT NULL DEFAULT now(),
    PRIMARY KEY (perfil, pagina),
    CONSTRAINT ck_midway_perfil_permissao_perfil
        CHECK (perfil IN ('ADM', 'GESTOR', 'ANALISTA', 'CONSULTA', 'AUDITOR')),
    CONSTRAINT ck_midway_perfil_permissao_pagina
        CHECK (pagina IN ('dashboard', 'executivo', 'anomalias', 'analise_tecnica', 'administracao'))
);

COMMENT ON TABLE midway_perfil_permissao IS
    'Matriz de permissoes por perfil e pagina, separando visualizar e editar.';

CREATE TABLE IF NOT EXISTS midway_alteracao_registro (
    id_alteracao uuid PRIMARY KEY,
    anomes varchar(6),
    modulo varchar(80) NOT NULL,
    entidade varchar(120) NOT NULL,
    id_entidade varchar(120),
    tipo_alteracao varchar(40) NOT NULL,
    status_alteracao varchar(30) NOT NULL DEFAULT 'REGISTRADA',
    antes jsonb,
    depois jsonb,
    justificativa text NOT NULL,
    solicitado_por varchar(120) NOT NULL,
    aprovado_por varchar(120),
    criado_em timestamp NOT NULL DEFAULT now(),
    atualizado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_alteracao_tipo
        CHECK (tipo_alteracao IN ('INSERT', 'UPDATE', 'DELETE', 'APROVACAO', 'REJEICAO', 'EXPORTACAO', 'OUTRO')),
    CONSTRAINT ck_midway_alteracao_status
        CHECK (status_alteracao IN ('REGISTRADA', 'PENDENTE', 'APROVADA', 'REJEITADA', 'APLICADA', 'CANCELADA'))
);

COMMENT ON TABLE midway_alteracao_registro IS
    'Registro governado de alteracoes, aprovacoes, exportacoes e acoes sensiveis.';

CREATE INDEX IF NOT EXISTS idx_midway_usuario_login
    ON midway_usuario(login);

CREATE UNIQUE INDEX IF NOT EXISTS idx_midway_usuario_email_unique
    ON midway_usuario(lower(email))
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_midway_usuario_perfil_status
    ON midway_usuario(perfil, status_usuario);

CREATE INDEX IF NOT EXISTS idx_midway_sessao_usuario_expira
    ON midway_sessao(id_usuario, expira_em);

CREATE INDEX IF NOT EXISTS idx_midway_reset_senha_usuario_status
    ON midway_reset_senha(id_usuario, status_reset, criado_em);

CREATE INDEX IF NOT EXISTS idx_midway_reset_senha_solicitante
    ON midway_reset_senha(solicitado_por, criado_em);

CREATE INDEX IF NOT EXISTS idx_midway_perfil_permissao_pagina
    ON midway_perfil_permissao(pagina);

CREATE INDEX IF NOT EXISTS idx_midway_alteracao_modulo_status
    ON midway_alteracao_registro(modulo, status_alteracao, criado_em);

CREATE INDEX IF NOT EXISTS idx_midway_alteracao_entidade
    ON midway_alteracao_registro(entidade, id_entidade);

CREATE OR REPLACE VIEW vw_midway_governanca_usuarios AS
SELECT
    id_usuario,
    login,
    nome,
    email,
    perfil,
    status_usuario,
    ultimo_login_em,
    tentativas_invalidas,
    bloqueado_ate,
    criado_por,
    criado_em,
    atualizado_por,
    atualizado_em
FROM midway_usuario;

COMMENT ON VIEW vw_midway_governanca_usuarios IS
    'Usuarios e perfis de governanca sem exposicao de senha/hash.';

INSERT INTO midway_perfil_permissao (perfil, pagina, pode_visualizar, pode_editar, atualizado_por)
VALUES
    ('ADM', 'dashboard', true, true, 'bootstrap'),
    ('ADM', 'executivo', true, true, 'bootstrap'),
    ('ADM', 'anomalias', true, true, 'bootstrap'),
    ('ADM', 'analise_tecnica', true, true, 'bootstrap'),
    ('ADM', 'administracao', true, true, 'bootstrap'),
    ('GESTOR', 'dashboard', true, false, 'bootstrap'),
    ('GESTOR', 'executivo', true, true, 'bootstrap'),
    ('GESTOR', 'anomalias', true, true, 'bootstrap'),
    ('GESTOR', 'analise_tecnica', true, false, 'bootstrap'),
    ('GESTOR', 'administracao', false, false, 'bootstrap'),
    ('ANALISTA', 'dashboard', true, false, 'bootstrap'),
    ('ANALISTA', 'executivo', false, false, 'bootstrap'),
    ('ANALISTA', 'anomalias', true, true, 'bootstrap'),
    ('ANALISTA', 'analise_tecnica', true, true, 'bootstrap'),
    ('ANALISTA', 'administracao', false, false, 'bootstrap'),
    ('CONSULTA', 'dashboard', true, false, 'bootstrap'),
    ('CONSULTA', 'executivo', false, false, 'bootstrap'),
    ('CONSULTA', 'anomalias', true, false, 'bootstrap'),
    ('CONSULTA', 'analise_tecnica', true, false, 'bootstrap'),
    ('CONSULTA', 'administracao', false, false, 'bootstrap'),
    ('AUDITOR', 'dashboard', true, false, 'bootstrap'),
    ('AUDITOR', 'executivo', false, false, 'bootstrap'),
    ('AUDITOR', 'anomalias', true, false, 'bootstrap'),
    ('AUDITOR', 'analise_tecnica', true, false, 'bootstrap'),
    ('AUDITOR', 'administracao', true, false, 'bootstrap')
ON CONFLICT (perfil, pagina) DO NOTHING;

CREATE OR REPLACE VIEW vw_midway_governanca_permissoes AS
SELECT
    perfil,
    pagina,
    pode_visualizar,
    pode_editar,
    atualizado_por,
    atualizado_em
FROM midway_perfil_permissao
ORDER BY perfil, pagina;

COMMENT ON VIEW vw_midway_governanca_permissoes IS
    'Matriz de permissoes por perfil e pagina para exibicao na Administracao.';

CREATE OR REPLACE VIEW vw_midway_governanca_sessoes_ativas AS
SELECT
    s.id_sessao,
    u.login,
    u.nome,
    u.perfil,
    s.ip_origem,
    s.criado_em,
    s.expira_em,
    s.ultimo_uso_em,
    COALESCE(u.email, u.login) AS email
FROM midway_sessao s
JOIN midway_usuario u
    ON u.id_usuario = s.id_usuario
WHERE s.revogado_em IS NULL
  AND s.expira_em > now();

COMMENT ON VIEW vw_midway_governanca_sessoes_ativas IS
    'Sessoes ativas de usuarios autenticados no MIDWAY.';

CREATE OR REPLACE VIEW vw_midway_governanca_reset_senha AS
SELECT
    r.id_reset,
    r.id_usuario,
    u.login,
    u.nome,
    u.perfil,
    r.solicitado_por,
    r.status_reset,
    r.tentativas,
    r.expira_em,
    r.confirmado_por,
    r.confirmado_em,
    r.ip_origem,
    r.justificativa,
    r.criado_em,
    r.atualizado_em,
    COALESCE(u.email, u.login) AS email
FROM midway_reset_senha r
JOIN midway_usuario u
    ON u.id_usuario = r.id_usuario;

COMMENT ON VIEW vw_midway_governanca_reset_senha IS
    'Monitoramento de resets de senha sem exposicao do codigo/hash.';

CREATE OR REPLACE VIEW vw_midway_governanca_alteracoes AS
SELECT
    id_alteracao,
    anomes,
    modulo,
    entidade,
    id_entidade,
    tipo_alteracao,
    status_alteracao,
    justificativa,
    solicitado_por,
    aprovado_por,
    criado_em,
    atualizado_em
FROM midway_alteracao_registro;

COMMENT ON VIEW vw_midway_governanca_alteracoes IS
    'Trilha governada de alteracoes sem expandir payloads jsonb.';

CREATE OR REPLACE VIEW vw_midway_governanca_auditoria AS
SELECT
    id_evento,
    anomes,
    tipo_evento,
    entidade,
    id_entidade,
    usuario,
    detalhe,
    criado_em
FROM midway_auditoria_evento
ORDER BY criado_em DESC;

COMMENT ON VIEW vw_midway_governanca_auditoria IS
    'Auditoria operacional consolidada do MIDWAY.';
