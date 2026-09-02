from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select

from config.db import get_session
from models.users import UserModel
from schemas.users import (
    TokenSchema,
    UserLoginSchema,
    UserRegistrationSchema,
    UserResponseSchema,
)
from utils.auths import auth
from utils.encryptions import hash_pwd, verify_pwd

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/register", response_model=UserResponseSchema)
async def register_user(
    payload: UserRegistrationSchema, db: AsyncSession = Depends(get_session)
):
    query = select(UserModel).where(
        (UserModel.username == payload.username) | (UserModel.email == payload.email)
    )
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(400, "username already exists")
    hashed_pwd = hash_pwd(payload.password)
    new_user = UserModel(
        username=payload.username, hashed_password=hashed_pwd, email=payload.email
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/login", response_model=TokenSchema)
async def login_user(
    response: Response,
    payload: UserLoginSchema,
    db: AsyncSession = Depends(get_session),
):
    query = select(UserModel).where(UserModel.username == payload.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user or not verify_pwd(payload.password, user.hashed_password):
        raise HTTPException(400, "incorrect username or password")
    token = auth.create_access_token(uid=str(user.id))
    response.set_cookie("access_token", token)
    return {"access_token": token}

@router.post("/logout")
async def logout_user(response: Response):
    response.delete_cookie("access_token")
    return {'msg': 'logout success'}