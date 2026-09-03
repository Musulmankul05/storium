import os
from datetime import timedelta

from authx import AuthX, AuthXConfig
from dotenv import load_dotenv

load_dotenv()

config = AuthXConfig(
    JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY"),
    JWT_ALGORITHM="HS256",
    JWT_TOKEN_LOCATION=["cookies"],
    JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=30),
    JWT_ACCESS_COOKIE_NAME="auth_access_token",
)

auth = AuthX(config)
