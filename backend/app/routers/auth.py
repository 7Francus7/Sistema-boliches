from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import LoginIn, TokenOut
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "credenciales inválidas")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "usuario inactivo")

    token = create_access_token(
        subject=str(user.id),
        extra={"role": user.role, "venue": str(user.venue_id)},
    )
    return TokenOut(
        access_token=token,
        role=user.role,
        venue_id=user.venue_id,
        user_id=user.id,
    )
