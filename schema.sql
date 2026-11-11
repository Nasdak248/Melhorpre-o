BEGIN;
CREATE TABLE IF NOT EXISTS rotas_monitoradas (
 id BIGSERIAL PRIMARY KEY,
 apelido VARCHAR(100) NOT NULL,
 origem CHAR(3) NOT NULL CHECK (origem ~ '^[A-Z]{3}$'),
 destino CHAR(3) NOT NULL CHECK (destino ~ '^[A-Z]{3}$'),
 max_preco_alerta NUMERIC(12,2) NOT NULL CHECK (max_preco_alerta > 0),
 ativo BOOLEAN NOT NULL DEFAULT TRUE,
 data_inicio DATE NOT NULL,
 data_fim DATE NOT NULL,
 CHECK (origem <> destino),
 CHECK (data_fim >= data_inicio AND data_fim - data_inicio <= 30)
);
CREATE TABLE IF NOT EXISTS historico_precos (
 id BIGSERIAL PRIMARY KEY,
 rota_id BIGINT NOT NULL REFERENCES rotas_monitoradas(id) ON DELETE CASCADE,
 origem CHAR(3) NOT NULL,
 destino CHAR(3) NOT NULL,
 data_voo DATE NOT NULL,
 preco NUMERIC(12,2) NOT NULL CHECK (preco > 0),
 data_consulta TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 alerta_enviado_em TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS historico_rota_consulta ON historico_precos (rota_id, data_consulta DESC);
COMMIT;
