-- MIDWAY 7.0.0
-- Geração IQS governada por pacote, modelos e justificativa única do gestor.

SET search_path TO ddcq, public;

CREATE TABLE IF NOT EXISTS midway_iqs_geracao (
    id_geracao uuid PRIMARY KEY,
    anomes varchar(6) NOT NULL,
    status_geracao varchar(30) NOT NULL DEFAULT 'APROVADA',
    justificativa text NOT NULL,
    aprovado_por varchar(120) NOT NULL,
    aprovado_em timestamp NOT NULL DEFAULT now(),
    gerado_em timestamp,
    mensagem text,
    CONSTRAINT ck_midway_iqs_geracao_status
        CHECK (status_geracao IN ('SOLICITADA', 'APROVADA', 'GERADA', 'CANCELADA', 'ERRO'))
);

COMMENT ON TABLE midway_iqs_geracao IS
    'Pacote governado de geração IQS aprovado pelo gestor com justificativa única.';

CREATE TABLE IF NOT EXISTS midway_iqs_geracao_modelo (
    id_modelo_geracao uuid PRIMARY KEY,
    id_geracao uuid NOT NULL REFERENCES midway_iqs_geracao(id_geracao),
    codigo_modelo varchar(80) NOT NULL,
    nome_modelo varchar(160) NOT NULL,
    tipo_arquivo varchar(80) NOT NULL,
    status_modelo varchar(30) NOT NULL DEFAULT 'APROVADO',
    caminho_arquivo text,
    qtd_linhas integer NOT NULL DEFAULT 0,
    mensagem text,
    criado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_iqs_geracao_modelo_status
        CHECK (status_modelo IN ('APROVADO', 'GERADO', 'CANCELADO', 'ERRO'))
);

COMMENT ON TABLE midway_iqs_geracao_modelo IS
    'Modelos/arquivos incluídos em um pacote governado de geração IQS.';

CREATE INDEX IF NOT EXISTS idx_midway_iqs_geracao_anomes_status
    ON midway_iqs_geracao(anomes, status_geracao, aprovado_em);

CREATE INDEX IF NOT EXISTS idx_midway_iqs_geracao_modelo_geracao
    ON midway_iqs_geracao_modelo(id_geracao, codigo_modelo);

CREATE OR REPLACE VIEW vw_midway_iqs_geracao AS
SELECT
    g.id_geracao,
    g.anomes,
    g.status_geracao,
    g.justificativa,
    g.aprovado_por,
    g.aprovado_em,
    g.gerado_em,
    COUNT(m.id_modelo_geracao) AS qtd_modelos,
    STRING_AGG(m.codigo_modelo, ', ' ORDER BY m.codigo_modelo) AS modelos,
    COALESCE(SUM(m.qtd_linhas), 0) AS qtd_linhas_total,
    g.mensagem
FROM midway_iqs_geracao g
LEFT JOIN midway_iqs_geracao_modelo m
    ON m.id_geracao = g.id_geracao
GROUP BY
    g.id_geracao,
    g.anomes,
    g.status_geracao,
    g.justificativa,
    g.aprovado_por,
    g.aprovado_em,
    g.gerado_em,
    g.mensagem;

COMMENT ON VIEW vw_midway_iqs_geracao IS
    'Pacotes de geração IQS aprovados com justificativa única e modelos vinculados.';

CREATE OR REPLACE VIEW vw_midway_iqs_geracao_modelo AS
SELECT
    g.anomes,
    g.id_geracao,
    g.status_geracao,
    g.justificativa,
    g.aprovado_por,
    g.aprovado_em,
    m.id_modelo_geracao,
    m.codigo_modelo,
    m.nome_modelo,
    m.tipo_arquivo,
    m.status_modelo,
    m.caminho_arquivo,
    m.qtd_linhas,
    m.mensagem,
    m.criado_em
FROM midway_iqs_geracao g
JOIN midway_iqs_geracao_modelo m
    ON m.id_geracao = g.id_geracao;

COMMENT ON VIEW vw_midway_iqs_geracao_modelo IS
    'Detalhe dos modelos e arquivos por pacote de geração IQS.';
