import os
import hashlib
from typing import Optional
from fastapi import HTTPException, Header
import asyncpg
from loguru import logger


async def verify_api_key_from_db(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    require_auth = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
    
    if not require_auth:
        return "no_auth_required"
    
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Please provide X-API-Key header."
        )
    
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    
    database_url = os.getenv("DATABASE_URL")
    if database_url and "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")
    
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=500, detail="Authentication service unavailable")
    
    try:
        result = await conn.fetchrow(
            """
            SELECT client_name, rate_limit, is_active
            FROM api_keys 
            WHERE key_hash = $1 AND is_active = true
            """,
            key_hash
        )
        
        if not result:
            logger.warning(f"Invalid API key attempt")
            raise HTTPException(
                status_code=403,
                detail="Invalid or revoked API key"
            )
        
        usage = await conn.fetchval(
            "SELECT COUNT(*) FROM executions WHERE client_name = $1",
            result['client_name']
        )
        
        if usage >= result['rate_limit']:
            logger.warning(f"Rate limit exceeded for client: {result['client_name']}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Limit: {result['rate_limit']}, Used: {usage}. Contact support to increase your limit."
            )
        
        await conn.execute(
            "UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE key_hash = $1",
            key_hash
        )
        
        logger.info(f"API request from client: {result['client_name']} (Usage: {usage}/{result['rate_limit']})")
        return result['client_name']
        
    finally:
        await conn.close()
