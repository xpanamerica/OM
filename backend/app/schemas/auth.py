from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(
        min_length=8,
        max_length=128,
        description="至少 8 字符；UTF-8 总长度不超过 72 字节（bcrypt 限制）。",
    )

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("password")
    @classmethod
    def password_within_bcrypt_byte_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("密码过长：UTF-8 编码长度不得超过 72 字节（bcrypt 限制）")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
