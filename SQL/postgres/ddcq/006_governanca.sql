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
        CHECK (perfil IN ('ADM', 'GESTOR', 'ANALISTA')),
    CONSTRAINT ck_midway_usuario_status
        CHECK (status_usuario IN ('ATIVO', 'BLOQUEADO', 'INATIVO'))
);

COMMENT ON TABLE midway_usuario IS
    'Usuarios da aplicacao MIDWAY com perfis de governanca ADM, GESTOR e ANALISTA.';

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

CREATE INDEX IF NOT EXISTS idx_midway_usuario_perfil_status
    ON midway_usuario(perfil, status_usuario);

CREATE INDEX IF NOT EXISTS idx_midway_sessao_usuario_expira
    ON midway_sessao(id_usuario, expira_em);

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

CREATE OR REPLACE VIEW vw_midway_governanca_sessoes_ativas AS
SELECT
    s.id_sessao,
    u.login,
    u.nome,
    u.perfil,
    s.ip_origem,
    s.criado_em,
    s.expira_em,
    s.ultimo_uso_em
FROM midway_sessao s
JOIN midway_usuario u
    ON u.id_usuario = s.id_usuario
WHERE s.revogado_em IS NULL
  AND s.expira_em > now();

COMMENT ON VIEW vw_midway_governanca_sessoes_ativas IS
    'Sessoes ativas de usuarios autenticados no MIDWAY.';

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
