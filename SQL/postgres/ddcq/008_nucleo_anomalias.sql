-- MIDWAY 7.0.0
-- Nucleo V7: anomalias, evidencias, sugestoes e decisoes humanas.

SET search_path TO ddcq, public;

CREATE TABLE IF NOT EXISTS midway_anomalia (
    id_anomalia uuid PRIMARY KEY,
    anomes varchar(6) NOT NULL,
    registro_id varchar(120) NOT NULL,
    anomalia_codigo varchar(80) NOT NULL,
    nome varchar(160) NOT NULL,
    categoria varchar(60) NOT NULL,
    severidade varchar(30) NOT NULL,
    confianca numeric(6, 4) NOT NULL,
    status_anomalia varchar(30) NOT NULL DEFAULT 'PENDENTE',
    origem varchar(80),
    regional varchar(40),
    conjunto varchar(80),
    equipamento varchar(120),
    uc varchar(120),
    ocorrencia varchar(120),
    interrupcao varchar(120),
    descricao text NOT NULL,
    explicacao_simples text NOT NULL,
    explicacao_tecnica text,
    regra_violada text,
    impacto_possivel text,
    campos_envolvidos jsonb NOT NULL DEFAULT '[]'::jsonb,
    dados_originais jsonb NOT NULL DEFAULT '{}'::jsonb,
    dados_sugeridos jsonb NOT NULL DEFAULT '{}'::jsonb,
    impacto jsonb NOT NULL DEFAULT '{}'::jsonb,
    linha_tempo jsonb NOT NULL DEFAULT '[]'::jsonb,
    criado_por varchar(120) NOT NULL DEFAULT 'setup',
    criado_em timestamp NOT NULL DEFAULT now(),
    atualizado_por varchar(120),
    atualizado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_anomalia_severidade
        CHECK (severidade IN ('baixa', 'média', 'alta', 'crítica')),
    CONSTRAINT ck_midway_anomalia_status
        CHECK (status_anomalia IN ('PENDENTE', 'EM_ANALISE', 'APROVADA', 'REJEITADA', 'APLICADA', 'CANCELADA')),
    CONSTRAINT ck_midway_anomalia_confianca
        CHECK (confianca >= 0 AND confianca <= 1)
);

COMMENT ON TABLE midway_anomalia IS
    'Anomalias detectadas pelo motor MIDWAY V7, preservando explicacao, impacto e dados antes/depois sugeridos.';

CREATE TABLE IF NOT EXISTS midway_evidencia (
    id_evidencia uuid PRIMARY KEY,
    id_anomalia uuid NOT NULL REFERENCES midway_anomalia(id_anomalia) ON DELETE CASCADE,
    campo varchar(120) NOT NULL,
    valor text,
    origem varchar(80),
    detalhe jsonb NOT NULL DEFAULT '{}'::jsonb,
    criado_em timestamp NOT NULL DEFAULT now()
);

COMMENT ON TABLE midway_evidencia IS
    'Evidencias objetivas associadas a cada anomalia V7.';

CREATE TABLE IF NOT EXISTS midway_sugestao (
    id_sugestao uuid PRIMARY KEY,
    id_anomalia uuid NOT NULL REFERENCES midway_anomalia(id_anomalia) ON DELETE CASCADE,
    acao varchar(120) NOT NULL,
    valor_original text,
    valor_sugerido text,
    justificativa text NOT NULL,
    nivel_confianca varchar(30) NOT NULL,
    risco_regulatorio varchar(30),
    risco_operacional varchar(30),
    risco_juridico varchar(30),
    requer_aprovacao boolean NOT NULL DEFAULT true,
    criado_por varchar(120) NOT NULL DEFAULT 'setup',
    criado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_sugestao_confianca
        CHECK (nivel_confianca IN ('muito alta', 'alta', 'média', 'baixa', 'inconclusiva'))
);

COMMENT ON TABLE midway_sugestao IS
    'Sugestoes de tratamento separadas da deteccao e dependentes de aprovacao humana quando aplicavel.';

CREATE TABLE IF NOT EXISTS midway_decisao (
    id_decisao uuid PRIMARY KEY,
    id_anomalia uuid NOT NULL REFERENCES midway_anomalia(id_anomalia),
    id_sugestao uuid REFERENCES midway_sugestao(id_sugestao),
    decisao varchar(30) NOT NULL,
    justificativa text NOT NULL,
    valor_final jsonb,
    decidido_por varchar(120) NOT NULL,
    decidido_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_decisao
        CHECK (decisao IN ('APROVAR', 'REJEITAR', 'EDITAR', 'SOLICITAR_ANALISE'))
);

COMMENT ON TABLE midway_decisao IS
    'Decisoes humanas sobre sugestoes V7. Nenhuma decisao deve apagar o dado original.';

CREATE INDEX IF NOT EXISTS idx_midway_anomalia_status
    ON midway_anomalia(anomes, status_anomalia, severidade);

CREATE INDEX IF NOT EXISTS idx_midway_anomalia_busca
    ON midway_anomalia(anomes, ocorrencia, interrupcao, uc);

CREATE INDEX IF NOT EXISTS idx_midway_evidencia_anomalia
    ON midway_evidencia(id_anomalia);

CREATE INDEX IF NOT EXISTS idx_midway_sugestao_anomalia
    ON midway_sugestao(id_anomalia);

CREATE INDEX IF NOT EXISTS idx_midway_decisao_anomalia
    ON midway_decisao(id_anomalia, decidido_em);

INSERT INTO midway_parametro (chave, valor, descricao, atualizado_por)
VALUES
    (
        'midway.v7.anomalias.fonte',
        'postgres_raw_silver_gold',
        'Fonte preferencial da Central de Anomalias V7.',
        'setup'
    )
ON CONFLICT (chave) DO UPDATE
SET
    valor = EXCLUDED.valor,
    descricao = EXCLUDED.descricao,
    atualizado_por = EXCLUDED.atualizado_por,
    atualizado_em = now();
