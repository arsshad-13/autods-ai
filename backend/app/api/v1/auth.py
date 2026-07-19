from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from app.core.dependencies import get_current_active_user
from app.core.security import decode_token, create_access_token
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import authenticate_user, register_user, get_user_by_uuid

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.
    """
    return await register_user(db, user_in)


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user and return a JWT access and refresh token.
    """
    return await authenticate_user(db, login_data)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_active_user)):
    """
    Get current logged in user profile.
    """
    return current_user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Get a new access token using a refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(refresh_data.refresh_token)
        uuid_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        if uuid_str is None or token_type != "refresh":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    import uuid
    try:
        user_uuid = uuid.UUID(uuid_str)
    except ValueError:
        raise credentials_exception

    user = await get_user_by_uuid(db, user_uuid=user_uuid)
    if user is None or not user.is_active:
        raise credentials_exception

    subject = str(user.uuid)
    
    # We could also issue a new refresh token here or just the access token.
    # The requirement is to validate refresh token and issue new access token.
    # Typically both are re-issued or just access. I'll re-issue both as standard.
    from app.core.security import create_refresh_token
    return TokenResponse(
        access_token=create_access_token(subject=subject),
        refresh_token=create_refresh_token(subject=subject),
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """
    Logout the current user. For now, it simply returns success. 
    Future milestones can implement token blacklisting.
    """
    return {"detail": "Successfully logged out"}
