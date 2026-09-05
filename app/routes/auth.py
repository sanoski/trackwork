from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..auth import authenticate_user, create_access_token, get_current_user
from ..config import settings
from ..limiter import limiter
from ..models import LoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response):
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(user.email)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    return {"message": "Logged in", "name": user.name, "role": user.role}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return UserResponse(
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
    )
