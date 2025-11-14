import os
import secrets
import hashlib
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncpg
from cryptography.fernet import Fernet
from loguru import logger

router = APIRouter(prefix="/api/v1/keys", tags=["API Key Management"])

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY environment variable must be set")

cipher = Fernet(ENCRYPTION_KEY.encode())


class RevealTokenInfo(BaseModel):
    valid: bool
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    is_revealed: Optional[bool] = None
    created_at: Optional[datetime] = None
    reason: Optional[str] = None


class RevealKeyRequest(BaseModel):
    reveal_token: str


class RevealKeyResponse(BaseModel):
    api_key: str
    client_name: str
    rate_limit: int
    warning: str


class MaskedKeyResponse(BaseModel):
    masked_key: str
    client_name: str
    rate_limit: int
    created_at: datetime
    last_used: Optional[datetime]
    is_active: bool


@router.get("/reveal/{reveal_token}/info", response_model=RevealTokenInfo)
async def get_reveal_info(reveal_token: str):
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        record = await conn.fetchrow(
            """
            SELECT client_name, client_email, is_revealed, created_at
            FROM api_key_reveals
            WHERE reveal_token = $1
            """,
            reveal_token
        )
        
        if not record:
            return RevealTokenInfo(valid=False, reason="Invalid reveal token")
        
        return RevealTokenInfo(
            valid=True,
            client_name=record['client_name'],
            client_email=record['client_email'],
            is_revealed=record['is_revealed'],
            created_at=record['created_at']
        )
    
    finally:
        await conn.close()


@router.post("/reveal", response_model=RevealKeyResponse)
async def reveal_api_key(request: RevealKeyRequest):
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        record = await conn.fetchrow(
            """
            SELECT 
                akr.id,
                akr.api_key_encrypted,
                akr.client_name,
                akr.is_revealed,
                akr.key_hash,
                ak.rate_limit
            FROM api_key_reveals akr
            JOIN api_keys ak ON akr.key_hash = ak.key_hash
            WHERE akr.reveal_token = $1
            """,
            request.reveal_token
        )
        
        if not record:
            raise HTTPException(status_code=404, detail="Invalid reveal token")
        
        if record['is_revealed']:
            raise HTTPException(
                status_code=400,
                detail="This API key has already been revealed. You can only view it once."
            )
        
        decrypted_key = cipher.decrypt(record['api_key_encrypted'].encode()).decode()
        
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE api_key_reveals
                SET is_revealed = TRUE, revealed_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                record['id']
            )
        
        logger.info(f"API key revealed for {record['client_name']}")
        
        return RevealKeyResponse(
            api_key=decrypted_key,
            client_name=record['client_name'],
            rate_limit=record['rate_limit'],
            warning="This is the only time you'll see this key. Copy it now and store it securely."
        )
    
    finally:
        await conn.close()


@router.get("/reveal/{reveal_token}/masked", response_model=MaskedKeyResponse)
async def get_masked_key(reveal_token: str):
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        record = await conn.fetchrow(
            """
            SELECT 
                akr.api_key_encrypted,
                akr.client_name,
                akr.is_revealed,
                ak.rate_limit,
                ak.created_at,
                ak.last_used,
                ak.is_active
            FROM api_key_reveals akr
            JOIN api_keys ak ON akr.key_hash = ak.key_hash
            WHERE akr.reveal_token = $1
            """,
            reveal_token
        )
        
        if not record:
            raise HTTPException(status_code=404, detail="Invalid reveal token")
        
        if not record['is_revealed']:
            raise HTTPException(
                status_code=400,
                detail="Key has not been revealed yet. Click 'Reveal Key' first."
            )
        
        decrypted_key = cipher.decrypt(record['api_key_encrypted'].encode()).decode()
        
        if len(decrypted_key) > 8:
            masked = f"{decrypted_key[:4]}{'*' * (len(decrypted_key) - 8)}{decrypted_key[-4:]}"
        else:
            masked = "*" * len(decrypted_key)
        
        return MaskedKeyResponse(
            masked_key=masked,
            client_name=record['client_name'],
            rate_limit=record['rate_limit'],
            created_at=record['created_at'],
            last_used=record['last_used'],
            is_active=record['is_active']
        )
    
    finally:
        await conn.close()
