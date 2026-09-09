import os

import httpx
import pytest
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.db import Base, get_session
from main import app
from models import BucketModel, ObjectModel, UserModel
from services.depends import get_current_user
from services.encryptions import hash_pwd

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("TEST_DB", "test_db")
DB_ADMIN = os.getenv("DB_ADMIN")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DB_URL = f"postgresql+asyncpg://{DB_ADMIN}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
test_engine = create_async_engine(DB_URL)


@pytest.fixture(scope='session', autouse=True)
async def db_engine():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()


@pytest.fixture(scope='function')
async def db_session():
    async_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_factory() as session:
        yield session


@pytest.fixture(scope='function')
async def test_user(db_session):
    user = UserModel(
        username="testman",
        hashed_password=hash_pwd("test123"),
        email="testman@test.com",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    await db_session.delete(user)
    await db_session.commit()


@pytest.fixture(scope='function')
async def client(db_session: AsyncSession, test_user):
    async def _override_get_db():
        yield db_session

    async def _override_get_user():
        return test_user

    app.dependency_overrides[get_session] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
