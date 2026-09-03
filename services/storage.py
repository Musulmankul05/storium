import hashlib
import os
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import and_

from models.objects import BucketModel, ObjectModel


class StorageService:
    def __init__(self, db: AsyncSession, storage_dirs):
        self.db = db
        self.storage_dirs = storage_dirs

    async def __file_iterator(self, file_path: str, chunk_size: int = 65536):
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    async def put_object(self, bucket_name, key, stream, content_type, user_id):
        res = await self.db.execute(
            select(BucketModel).where(
                and_(BucketModel.name == bucket_name, BucketModel.owner_id == user_id)
            )
        )
        bucket = res.scalar_one_or_none()
        if not bucket:
            raise ValueError("bucket not found")

        hasher = hashlib.md5()
        size = 0
        temp_path = os.path.join(
            self.storage_dirs, f"temp_{bucket.id}_{abs(hash(key))}"
        )

        os.makedirs(self.storage_dirs, exist_ok=True)
        with open(temp_path, "wb") as f:
            async for chunk in stream:
                hasher.update(chunk)
                size += len(chunk)
                f.write(chunk)

        etag = hasher.hexdigest()
        final_path = os.path.join(self.storage_dirs, etag)
        os.rename(temp_path, final_path)
        existing_obj_res = await self.db.execute(
            select(ObjectModel).where(
                and_(ObjectModel.bucket_id == bucket.id), ObjectModel.key == key
            )
        )
        existing_obj = existing_obj_res.scalar_one_or_none()

        if existing_obj:
            existing_obj.etag = etag
            existing_obj.size = size
            existing_obj.content_type = content_type
        else:
            new_obj = ObjectModel(
                key=key,
                etag=etag,
                size=size,
                content_type=content_type,
                bucket_id=bucket.id,
            )
            self.db.add(new_obj)
            await self.db.commit()

    async def get_object(self, bucket_name, key, user_id):
        obj_res = await self.db.execute(
            select(ObjectModel)
            .join(BucketModel, ObjectModel.bucket_id == BucketModel.id)
            .where(
                and_(
                    BucketModel.name == bucket_name,
                    BucketModel.owner_id == user_id,
                    ObjectModel.key == key,
                )
            )
        )
        obj = obj_res.scalar_one_or_none()
        if obj is None:
            raise ValueError("object not found")
        file_path = os.path.join(self.storage_dirs, obj.etag)
        if not os.path.exists(file_path):
            raise FileNotFoundError("file data is missing on disk")
        return obj, self.__file_iterator(file_path)

    async def del_object(self, bucket_name, key, user_id):
        obj_res = await self.db.execute(
            select(ObjectModel)
            .join(BucketModel, ObjectModel.bucket_id == BucketModel.id)
            .where(
                and_(
                    BucketModel.name == bucket_name,
                    BucketModel.owner_id == user_id,
                    ObjectModel.key == key,
                )
            )
        )
        obj = obj_res.scalar_one_or_none()
        if obj is None:
            raise ValueError("object not found")

        target_etag = obj.etag
        await self.db.delete(obj)
        await self.db.commit()

        check_ref = await self.db.execute(
            select(ObjectModel.id).where(ObjectModel.etag == target_etag).limit(1)
        )
        has_other_refs = check_ref.scalar_one_or_none() is not None

        if not has_other_refs:
            file_path = os.path.join(self.storage_dirs, target_etag)
            if os.path.exists(file_path):
                os.remove(file_path)
