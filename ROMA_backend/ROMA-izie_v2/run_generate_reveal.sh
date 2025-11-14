#!/bin/bash

if [ $# -lt 2 ]; then
    echo "Usage: $0 <client_name> <client_email>"
    echo ""
    echo "Example:"
    echo "  $0 'Abdul' 'abdul@example.com'"
    exit 1
fi

CLIENT_NAME="$1"
CLIENT_EMAIL="$2"

# Run inside the roma-api container
docker compose exec -T roma-api bash -c "
export DATABASE_URL='postgresql://postgres:6F5CKP4YHcCi60R9B8b1yzgoOF4m9NG8b5ULErQUsC4=@postgres:5432/roma_dspy'
export ENCRYPTION_KEY='o4C2cuReZ8Pb55_ieJr9wcp8nuPnq6a8okM80yfW-kY='
export FRONTEND_URL='https://keys.izieroma.xyz'

cd /app
./generate_and_reveal.sh '$CLIENT_NAME' '$CLIENT_EMAIL'
"
