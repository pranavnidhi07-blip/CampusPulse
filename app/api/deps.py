from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.auth import Organizer, SensorClient
from app.models.base import utc_now
from app.services.auth_service import AuthService

security_bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_organizer(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: AsyncSession = Depends(get_db)
) -> Organizer:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    payload = AuthService.decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    organizer_id = payload.get("sub")
    if not organizer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject"
        )

    stmt = select(Organizer).where(Organizer.id == int(organizer_id))
    result = await db.execute(stmt)
    organizer = result.scalar_one_or_none()

    if not organizer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organizer not found"
        )

    if not organizer.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive organizer account"
        )

    if organizer.role != "organizer" and organizer.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this operation"
        )

    return organizer


async def get_sensor_client(
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: AsyncSession = Depends(get_db)
) -> SensorClient:
    raw_key = api_key
    if not raw_key and credentials and credentials.credentials:
        # Allow passing sensor API key in Bearer format as well
        raw_key = credentials.credentials

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing sensor client credentials (pass via X-API-Key header or Bearer token)"
        )

    key_hash = AuthService.hash_sensor_key(raw_key)
    stmt = select(SensorClient).where(SensorClient.api_key_hash == key_hash)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()

    if not client or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked sensor API key"
        )

    client.last_seen_at = utc_now()
    await db.commit()
    return client
