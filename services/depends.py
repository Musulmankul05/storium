import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select

from config.db import get_session
from models import UserModel
from services.auths import config


async def get_current_user(request: Request, db: AsyncSession = Depends(get_session)):
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(401, "auth token not found")
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
        user_id = int(payload.get("sub"))
        if user_id is None:
            raise HTTPException(401, "invalid token")
    except jwt.PyJWTError:
        raise HTTPException(401, "token is not valid or expired")

    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "user not found")
    return user
