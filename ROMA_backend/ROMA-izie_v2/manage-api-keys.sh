#!/bin/bash

DB_CONTAINER="roma-dspy-postgres"
DB_NAME="roma_dspy"
DB_USER="postgres"

# Ensure pgcrypto is installed (safe to run repeatedly)
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" >/dev/null 2>&1

case "$1" in
    create)
        if [ -z "$2" ]; then
            echo "Usage: $0 create <client_name>"
            exit 1
        fi

        API_KEY=$(openssl rand -hex 32)
        CLIENT_NAME="$2"

        # Escape single quotes in values to avoid SQL injection / syntax errors
        API_KEY_ESC=${API_KEY//\'/\'\'}
        CLIENT_NAME_ESC=${CLIENT_NAME//\'/\'\'}

        docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME <<EOF
INSERT INTO api_keys (key_hash, client_name)
VALUES (encode(digest('$API_KEY_ESC', 'sha256'), 'hex'), '$CLIENT_NAME_ESC');
EOF

        echo ""
        echo "==========================================="
        echo "API Key created for: $CLIENT_NAME"
        echo "==========================================="
        echo "$API_KEY"
        echo "==========================================="
        echo ""
        echo "IMPORTANT: Save this key securely."
        echo "It cannot be retrieved again."
        ;;

    list)
        docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME <<EOF
SELECT id, client_name, created_at, last_used, is_active, rate_limit
FROM api_keys
ORDER BY created_at DESC;
EOF
        ;;

    revoke)
        if [ -z "$2" ]; then
            echo "Usage: $0 revoke <client_name>"
            exit 1
        fi

        CLIENT_NAME_ESC=${2//\'/\'\'}
        docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME <<EOF
UPDATE api_keys SET is_active = false
WHERE client_name = '$CLIENT_NAME_ESC';
EOF
        echo "API key revoked for: $2"
        ;;

    *)
        echo "Usage: $0 {create|list|revoke} <client_name>"
        echo ""
        echo "Examples:"
        echo "  $0 create john_doe"
        echo "  $0 list"
        echo "  $0 revoke john_doe"
        exit 1
        ;;
esac
