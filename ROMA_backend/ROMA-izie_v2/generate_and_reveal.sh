#!/bin/bash

# Load environment variables from .env
if [ -f .env ]; then
    export $(cat .env | grep -E '^(DATABASE_URL|ENCRYPTION_KEY|FRONTEND_URL)=' | sed 's/+asyncpg//' | xargs)
fi

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <client_name> <client_email>"
    echo ""
    echo "Example:"
    echo "  $0 'Abdul' 'abdul@example.com'"
    echo ""
    echo "This will:"
    echo "  1. Generate API key using manage-api-keys.sh"
    echo "  2. Create reveal token"
    echo "  3. Provide URL to send to user"
    exit 1
fi

CLIENT_NAME="$1"
CLIENT_EMAIL="$2"

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not set"
    exit 1
fi

if [ -z "$ENCRYPTION_KEY" ]; then
    echo "Error: ENCRYPTION_KEY not set"
    echo "Generate one with:"
    echo "  python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    exit 1
fi

MANAGE_KEYS_SCRIPT="./manage-api-keys.sh"
if [ ! -f "$MANAGE_KEYS_SCRIPT" ]; then
    MANAGE_KEYS_SCRIPT="$(dirname "$0")/manage-api-keys.sh"
fi

if [ ! -f "$MANAGE_KEYS_SCRIPT" ]; then
    echo "Error: manage-api-keys.sh not found"
    echo "Looking in: $(pwd)"
    exit 1
fi

echo "Creating API key for: $CLIENT_NAME ($CLIENT_EMAIL)"
echo ""

API_KEY_OUTPUT=$($MANAGE_KEYS_SCRIPT create production_user 2>&1)

API_KEY=$(echo "$API_KEY_OUTPUT" | grep -oP '[a-f0-9]{64}' | head -1)

if [ -z "$API_KEY" ]; then
    echo "Error: Could not extract API key from manage-api-keys.sh output"
    echo "Output was:"
    echo "$API_KEY_OUTPUT"
    exit 1
fi

echo "✅ API key created: ${API_KEY:0:10}...${API_KEY: -4}"
echo ""
echo "Creating reveal token..."

python3 "$(dirname "$0")/create_reveal_token.py" "$API_KEY" "$CLIENT_NAME" "$CLIENT_EMAIL"
