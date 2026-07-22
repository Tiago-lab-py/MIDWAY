CREATE TABLE IF NOT EXISTS ddcq.midway_propostas_tratamento (
    id SERIAL PRIMARY KEY,
    codigo_modulo VARCHAR(100) NOT NULL,
    chave_negocio VARCHAR(255) NOT NULL,
    
    -- Campos flexíveis de Evidência baseados em JSON para acomodar as diferenças entre módulos
    evidencias JSONB NOT NULL,
    
    -- Campos exigidos pelo contrato
    impacto TEXT NOT NULL,
    acao_sugerida TEXT NOT NULL,
    campos_iqs_afetados TEXT[],
    exportacao_iqs VARCHAR(255),
    
    -- Governança de Workflow
    status_governanca VARCHAR(50) DEFAULT 'pendente',
    usuario_aprovador VARCHAR(255),
    data_decisao TIMESTAMP,
    justificativa_decisao TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices essenciais para o Frontend e deduplicação
CREATE INDEX IF NOT EXISTS idx_propostas_modulo ON ddcq.midway_propostas_tratamento(codigo_modulo);
CREATE INDEX IF NOT EXISTS idx_propostas_status ON ddcq.midway_propostas_tratamento(status_governanca);
CREATE INDEX IF NOT EXISTS idx_propostas_chave ON ddcq.midway_propostas_tratamento(chave_negocio);
-- Índice GIN para busca rápida dentro das evidências JSON
CREATE INDEX IF NOT EXISTS idx_propostas_evidencias ON ddcq.midway_propostas_tratamento USING GIN (evidencias);
