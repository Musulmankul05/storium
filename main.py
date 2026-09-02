import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"msg": "Hello, Storium!"}


if __name__ == "__main__":
    uvicorn.run("main:app")
