import hashlib
import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import and_

from models.objects import BucketModel, ObjectModel


class StorageService:
    """
    **This class contains async methods to work with buckets and objects.**

    # **Args**:
        db: Takes ORM session dependency
        storage_dir: Main storage for buckets/objects. "./static/storage" by default

    # **Methods**:
        create_bucket: Creates bucket. Excepts when caused race-condition by unique name
        del_bucket: Deletes bucket if its empty. Used for DELETE HTTP-Method
        get_user_buckets: Gets list of current users buckets
        put_object: Uploads file by dividing to chunks first, then save combined hashed file
        get_object: Gets object by key and bucket name
        del_object: Deletes object bt key and bucket name

    # **Example:**
    ```python
        ...
        storage = StorageService(db)
        try:
            return await storage.create_bucket(payload.name, user_id=current_user.id)
        except ValueError as e:
            raise HTTPException(409, str(e))
    ```
    """

    def __init__(self, db: AsyncSession, storage_dir: str = "./static/storage"):
        self.db = db
        self.storage_dir = storage_dir

    async def __file_iterator(self, file_path: str, chunk_size: int = 65536):
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    async def create_bucket(self, name, user_id):
        new_bucket = BucketModel(name=name, owner_id=user_id)
        try:
            self.db.add(new_bucket)
            await self.db.commit()
            await self.db.refresh(new_bucket)
            return new_bucket
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("bucket with this name already exists")

    async def del_bucket(self, bucket_name, user_id):
        res = await self.db.execute(
            select(BucketModel).where(
                and_(BucketModel.name == bucket_name, BucketModel.owner_id == user_id)
            )
        )
        bucket = res.scalar_one_or_none()
        if bucket is None:
            raise ValueError("bucket not found")
        obj_res = await self.db.execute(
            select(ObjectModel).where(ObjectModel.bucket_id == bucket.id).limit(1)
        )
        obj = obj_res.scalar_one_or_none()
        if obj:
            raise FileExistsError("bucket is not empty")
        await self.db.delete(bucket)
        await self.db.commit()

    async def get_user_buckets(self, user_id):
        res = await self.db.execute(
            select(BucketModel).where(BucketModel.owner_id == user_id)
        )
        return res.scalars().all()

    async def put_object(self, bucket_name, key, stream, content_type, user_id: int):
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
        temp_path = os.path.join(self.storage_dir, f"temp_{bucket.id}_{abs(hash(key))}")

        os.makedirs(self.storage_dir, exist_ok=True)
        with open(temp_path, "wb") as f:
            async for chunk in stream:
                hasher.update(chunk)
                size += len(chunk)
                f.write(chunk)

        etag = hasher.hexdigest()
        final_path = os.path.join(self.storage_dir, etag)
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
        file_path = os.path.join(self.storage_dir, obj.etag)
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
            file_path = os.path.join(self.storage_dir, target_etag)
            if os.path.exists(file_path):
                os.remove(file_path)
