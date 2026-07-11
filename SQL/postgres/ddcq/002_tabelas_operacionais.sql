-- MIDWAY 7.0.0
-- Operational tables for schema ddcq.

SET search_path TO ddcq, public;

CREATE TABLE IF NOT EXISTS midway_execucao_lote (
    id_lote uuid PRIMARY KEY,
    anomes varchar(6) NOT NULL,
    tipo_lote varchar(60) NOT NULL,
    status_lote varchar(30) NOT NULL,
    origem varchar(120),
    parametros jsonb,
    iniciado_em timestamp NOT NULL DEFAULT now(),
    finalizado_em timestamp,
    criado_por varchar(120),
    mensagem text,
    CONSTRAINT ck_midway_execucao_lote_status
        CHECK (status_lote IN ('ABERTO', 'PROCESSANDO', 'CONCLUIDO', 'ERRO', 'CANCELADO'))
);

COMMENT ON TABLE midway_execucao_lote IS
    'Controle de execucoes, processamentos, cargas e exportacoes do MIDWAY.';

CREATE TABLE IF NOT EXISTS midway_autorizacao_executiva (
    id_autorizacao uuid PRIMARY KEY,
    anomes varchar(6) NOT NULL,
    tipo_autorizacao varchar(80) NOT NULL,
    regra varchar(120) NOT NULL,
    status_autorizacao varchar(30) NOT NULL,
    qtd_candidatos integer NOT NULL DEFAULT 0,
    qtd_autorizados integer NOT NULL DEFAULT 0,
    qtd_rejeitados integer NOT NULL DEFAULT 0,
    justificativa text,
    autorizado_por varchar(120),
    autorizado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_autorizacao_status
        CHECK (status_autorizacao IN ('PENDENTE', 'AUTORIZADA', 'REJEITADA', 'CANCELADA')),
    CONSTRAINT ck_midway_autorizacao_quantidades
        CHECK (qtd_candidatos >= 0 AND qtd_autorizados >= 0 AND qtd_rejeitados >= 0)
);

COMMENT ON TABLE midway_autorizacao_executiva IS
    'Registro de autorizacoes executivas para tratativas em massa, como RA 92/82 automatico.';

CREATE TABLE IF NOT EXISTS midway_ajuste_iqs (
    id_ajuste uuid PRIMARY KEY,
    anomes varchar(6) NOT NULL,
    aprovado boolean NOT NULL DEFAULT false,
    origem_ajuste varchar(80) NOT NULL,
    escopo varchar(30) NOT NULL,
    num_ocorrencia_adms varchar(80),
    num_seq_intrp varchar(80),
    num_uc_uci varchar(80),
    sigla_regional varchar(20),
    cod_causa_intrp_original varchar(20),
    cod_comp_intrp_original varchar(20),
    novo_cod_causa_intrp varchar(20),
    novo_cod_comp_intrp varchar(20),
    novo_cod_cond_clima_intrp varchar(20),
    novo_cod_tipo_intrp varchar(20),
    novo_num_motivo_trat_dif_uci varchar(20),
    novo_tipo_protoc_justif_uci varchar(20),
    novo_num_protoc_justif_resp_uci varchar(80),
    novo_tipo_protoc_justif_intrp varchar(20),
    novo_num_protoc_justif_resp_intrp varchar(80),
    novo_valid_pos_operacao varchar(10),
    novo_estado_intrp varchar(20),
    nova_data_hora_inic_intrp timestamp,
    nova_data_hora_fim_intrp timestamp,
    nova_dthr_inicio_intrp_uci timestamp,
    justificativa text,
    id_autorizacao uuid REFERENCES midway_autorizacao_executiva(id_autorizacao),
    criado_por varchar(120),
    criado_em timestamp NOT NULL DEFAULT now(),
    atualizado_por varchar(120),
    atualizado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_ajuste_escopo
        CHECK (escopo IN ('OCORRENCIA', 'INTERRUPCAO', 'UC')),
    CONSTRAINT ck_midway_ajuste_origem
        CHECK (origem_ajuste IN ('MANUAL_TECNICO', 'AUTO_EXECUTIVO_9282', 'IMPORTACAO', 'OUTRO'))
);

COMMENT ON TABLE midway_ajuste_iqs IS
    'Ajustes IQS aprovados ou pendentes, manuais ou autorizados pelo Executivo.';

CREATE TABLE IF NOT EXISTS midway_fila_tecnica (
    id_fila uuid PRIMARY KEY,
    anomes varchar(6) NOT NULL,
    tipo_fila varchar(80) NOT NULL,
    prioridade integer NOT NULL DEFAULT 0,
    status_fila varchar(30) NOT NULL DEFAULT 'ABERTA',
    num_ocorrencia_adms varchar(80),
    num_seq_intrp varchar(80),
    cod_causa_atual varchar(20),
    cod_comp_atual varchar(20),
    cod_causa_sugerida varchar(20),
    cod_comp_sugerido varchar(20),
    fonte_sugestao varchar(80),
    nivel_evidencia varchar(80),
    score_sugestao numeric(10, 2),
    evidencia_resumo text,
    responsavel varchar(120),
    criado_em timestamp NOT NULL DEFAULT now(),
    atualizado_em timestamp NOT NULL DEFAULT now(),
    CONSTRAINT ck_midway_fila_status
        CHECK (status_fila IN ('ABERTA', 'EM_ANALISE', 'TRATADA', 'DESCARTADA', 'CANCELADA'))
);

COMMENT ON TABLE midway_fila_tecnica IS
    'Fila de itens problematicos para tratamento tecnico, incluindo conflitos e sugestoes por reclamacao.';

CREATE TABLE IF NOT EXISTS midway_auditoria_evento (
    id_evento uuid PRIMARY KEY,
    anomes varchar(6),
    tipo_evento varchar(80) NOT NULL,
    entidade varchar(80),
    id_entidade varchar(120),
    usuario varchar(120),
    detalhe jsonb,
    criado_em timestamp NOT NULL DEFAULT now()
);

COMMENT ON TABLE midway_auditoria_evento IS
    'Auditoria de eventos operacionais: autorizacoes, ajustes, exportacoes, alteracoes e cargas.';

CREATE TABLE IF NOT EXISTS midway_exportacao_iqs (
    id_exportacao uuid PRIMARY KEY,
    anomes varchar(6) NOT NULL,
    tipo_exportacao varchar(80) NOT NULL,
    status_exportacao varchar(30) NOT NULL,
    caminho_arquivo text,
    qtd_linhas integer NOT NULL DEFAULT 0,
    gerado_por varchar(120),
    gerado_em timestamp NOT NULL DEFAULT now(),
    id_lote uuid REFERENCES midway_execucao_lote(id_lote),
    CONSTRAINT ck_midway_exportacao_status
        CHECK (status_exportacao IN ('GERADA', 'VALIDADA', 'ENVIADA', 'ERRO', 'CANCELADA')),
    CONSTRAINT ck_midway_exportacao_qtd_linhas
        CHECK (qtd_linhas >= 0)
);

COMMENT ON TABLE midway_exportacao_iqs IS
    'Controle de arquivos IQS gerados pelo MIDWAY e respectivos lotes.';

CREATE TABLE IF NOT EXISTS midway_parametro (
    chave varchar(120) PRIMARY KEY,
    valor text,
    descricao text,
    atualizado_por varchar(120),
    atualizado_em timestamp NOT NULL DEFAULT now()
);

COMMENT ON TABLE midway_parametro IS
    'Parametros operacionais do MIDWAY por ambiente.';

