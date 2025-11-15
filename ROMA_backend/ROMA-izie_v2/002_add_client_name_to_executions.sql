ALTER TABLE executions ADD COLUMN IF NOT EXISTS client_name TEXT;

CREATE INDEX IF NOT EXISTS idx_executions_client_name ON executions(client_name);

COMMENT ON COLUMN executions.client_name IS 'API key client name for rate limiting';
