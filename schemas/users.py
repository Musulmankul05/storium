from pydantic import BaseModel


class UserResponseSchema(BaseModel):
    id: int
    username: str
    email: str

class UserRegistrationSchema(BaseModel):
    username: str
    password: str
    email: str

class UserLoginSchema(BaseModel):
    username: str
    password: str

class TokenSchema(BaseModel):
    access_token: str
    token_type: str = 'bearer'