#!/usr/bin/env python3

import os
import sys
import secrets
import hashlib
import asyncio
import asyncpg
from cryptography.fernet import Fernet

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("@postgres:", "@localhost:")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://keys.izieroma.xyz")

if not DATABASE_URL:
    print("Error: DATABASE_URL not set")
    sys.exit(1)

if not ENCRYPTION_KEY:
    print("Error: ENCRYPTION_KEY not set")
    print("Generate one with: python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
    sys.exit(1)


async def create_reveal_token(api_key: str, client_name: str, client_email: str):
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    reveal_token = secrets.token_urlsafe(32)
    
    cipher = Fernet(ENCRYPTION_KEY.encode())
    encrypted_key = cipher.encrypt(api_key.encode()).decode()
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        existing = await conn.fetchrow(
            "SELECT key_hash FROM api_keys WHERE key_hash = $1",
            key_hash
        )
        
        if not existing:
            print(f"Error: API key not found in database")
            print(f"Make sure the key was created with manage-api-keys.sh first")
            sys.exit(1)
        
        await conn.execute(
            """
            INSERT INTO api_key_reveals 
            (reveal_token, key_hash, api_key_encrypted, client_name, client_email)
            VALUES ($1, $2, $3, $4, $5)
            """,
            reveal_token, key_hash, encrypted_key, client_name, client_email
        )
        
        reveal_url = f"{FRONTEND_URL}?reveal={reveal_token}"
        
        print("\n" + "=" * 80)
        print("✅ Reveal Token Created Successfully")
        print("=" * 80)
        print(f"\nClient: {client_name}")
        print(f"Email: {client_email}")
        print(f"\nReveal URL:\n{reveal_url}")
        print("\n" + "=" * 80)
        print("📧 Send this email to the user:")
        print("=" * 80)
        print(f"""
Hi {client_name},

Your ROMA API key is ready!

Click this link to reveal your API key:
{reveal_url}

⚠️ IMPORTANT:
- You can only view the full key ONCE
- After that, it will be masked for security
- Copy and save it immediately when revealed

Documentation: https://b-fame.gitbook.io/roma-api-integration

Questions? Reply to this email.

Best regards,
ROMA Team
""")
        print("=" * 80 + "\n")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 create_reveal_token.py <api_key> <client_name> <client_email>")
        print("\nExample:")
        print("  python3 create_reveal_token.py 'roma_abc123...' 'John Doe' 'john@example.com'")
        sys.exit(1)
    
    api_key = sys.argv[1]
    client_name = sys.argv[2]
    client_email = sys.argv[3]
    
    asyncio.run(create_reveal_token(api_key, client_name, client_email))
