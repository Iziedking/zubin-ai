CREATE TABLE IF NOT EXISTS api_key_reveals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reveal_token VARCHAR(64) UNIQUE NOT NULL,
    key_hash VARCHAR(64) NOT NULL REFERENCES api_keys(key_hash),
    api_key_encrypted TEXT NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    client_email VARCHAR(255) NOT NULL,
    is_revealed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revealed_at TIMESTAMP,
    CONSTRAINT fk_api_key FOREIGN KEY (key_hash) REFERENCES api_keys(key_hash) ON DELETE CASCADE
);

CREATE INDEX idx_reveal_token ON api_key_reveals(reveal_token);
CREATE INDEX idx_reveal_key_hash ON api_key_reveals(key_hash);
CREATE INDEX idx_reveal_status ON api_key_reveals(is_revealed);

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS reveal_id UUID REFERENCES api_key_reveals(id);
