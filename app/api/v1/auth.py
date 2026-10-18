from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.auth import Organizer, SensorClient
from app.schemas.auth import (
    OrganizerCreate,
    OrganizerLogin,
    OrganizerOut,
    TokenResponse,
    SensorClientCreate,
    SensorClientOut
)
from app.services.auth_service import AuthService
from app.api.deps import get_current_organizer
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=OrganizerOut, status_code=status.HTTP_201_CREATED)
async def register_organizer(
    data: OrganizerCreate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Organizer).where(Organizer.email == data.email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organizer with this email already exists"
        )

    password_hash = AuthService.hash_password(data.password)
    organizer = Organizer(
        email=data.email,
        password_hash=password_hash,
        role=data.role,
        is_active=True
    )
    db.add(organizer)
    await db.commit()
    await db.refresh(organizer)
    return organizer


@router.post("/login", response_model=TokenResponse)
async def login_organizer(
    data: OrganizerLogin,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Organizer).where(Organizer.email == data.email)
    res = await db.execute(stmt)
    organizer = res.scalar_one_or_none()

    if not organizer or not AuthService.verify_password(data.password, organizer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not organizer.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive organizer account"
        )

    token = AuthService.create_access_token(
        data={"sub": str(organizer.id), "email": organizer.email, "role": organizer.role}
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/sensor-clients", response_model=SensorClientOut, status_code=status.HTTP_201_CREATED)
async def create_sensor_client(
    data: SensorClientCreate,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    raw_key, hashed_key = AuthService.generate_sensor_api_key()
    client = SensorClient(
        name=data.name,
        api_key_hash=hashed_key,
        is_active=True
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    out = SensorClientOut.model_validate(client)
    out.api_key = raw_key  # Plaintext key only returned on creation
    return out


@router.get("/sensor-clients", response_model=list[SensorClientOut])
async def list_sensor_clients(
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SensorClient).order_by(SensorClient.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()
