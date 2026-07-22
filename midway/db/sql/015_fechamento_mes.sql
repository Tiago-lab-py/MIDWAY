CREATE TABLE IF NOT EXISTS {schema}.midway_mes_apuracao (
    anomes VARCHAR(6) PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'ABERTO', -- 'ABERTO' or 'FECHADO'
    fechado_em TIMESTAMP,
    fechado_por VARCHAR(100)
);

COMMENT ON TABLE {schema}.midway_mes_apuracao IS 'Tabela de controle de fechamento de meses de apuração do MIDWAY.';
COMMENT ON COLUMN {schema}.midway_mes_apuracao.anomes IS 'Competência (ex: 202606).';
COMMENT ON COLUMN {schema}.midway_mes_apuracao.status IS 'Status do mês (ABERTO ou FECHADO).';
