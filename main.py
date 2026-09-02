import uvicorn
from fastapi import FastAPI

from routers import users

MASTER_PREFIX = '/api/v1'
app = FastAPI()
app.include_router(users.router, prefix=MASTER_PREFIX)


@app.get("/")
def read_root():
    return {"msg": "Hello, Storium!"}


if __name__ == "__main__":
    uvicorn.run("main:app")
