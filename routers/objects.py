from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_session
from models import UserModel
from schemas.objects import (
    BucketNameSchema,
    BucketSchema,
    ObjectResponseSchema,
)
from services.depends import get_current_user
from services.storage import StorageService

router = APIRouter(tags=["Storage"])


@router.post("/buckets", status_code=201, response_model=BucketSchema)
async def create_bucket(
    payload: BucketNameSchema,
    db: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
):
    storage = StorageService(db)
    try:
        return await storage.create_bucket(payload.name, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/buckets", response_model=list[BucketSchema,])
async def get_buckets(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    storage = StorageService(db)
    return await storage.get_user_buckets(current_user.id)


@router.delete("/buckets/{bucket_name}")
async def delete_bucket(
    bucket_name: str,
    db: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
):
    storage = StorageService(db)
    try:
        await storage.del_bucket(bucket_name, current_user.id)
    except ValueError:
        raise HTTPException(404, "bucket not found")
    except FileExistsError:
        raise HTTPException(409, "bucket is not empty")
    return {"msg": f"bucket {bucket_name} delete success"}


@router.put("/buckets/{bucket_name}/objects/{key:path}", status_code=201)
async def put_object(
    bucket_name: str,
    key: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
):
    storage = StorageService(db)
    content_type = request.headers.get("content-type")
    try:
        await storage.put_object(
            bucket_name=bucket_name,
            key=key,
            stream=request.stream(),
            content_type=content_type,
            user_id=current_user.id,
        )
    except ValueError:
        raise HTTPException(404, "bucket not found")
    return {"msg": "object created", "key": key}


@router.get("/buckets/{bucket_name}/objects/{key:path}")
async def get_object(
    bucket_name: str,
    key: str,
    db: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
):
    storage = StorageService(db)
    try:
        obj, file_stream = await storage.get_object(bucket_name, key, current_user.id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "object or bucket not found")
    return StreamingResponse(
        file_stream,
        media_type=obj.content_type,
        headers={"Content-Length": str(obj.size), "ETag": obj.etag},
    )


@router.delete("/buckets/{bucket_name}/objects/{key:path}", status_code=204)
async def delete_object(
    bucket_name: str,
    key: str,
    db: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
):
    storage = StorageService(db)
    try:
        await storage.del_object(bucket_name, key, current_user.id)
    except ValueError:
        raise HTTPException(404, "object not found")


@router.get("/buckets/{bucket_name}/objects", response_model=list[ObjectResponseSchema,])
async def get_objects_list(
    bucket_name: str,
    prefix: str | None = None,
    limit: int = Query(default=20, ge=1, le=40),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    storage = StorageService(db)
    try:
        objects = await storage.get_bucket_objects(bucket_name, current_user.id, limit, offset, prefix)
    except ValueError:
        raise HTTPException(404, 'bucket not found')
    return objects
        
