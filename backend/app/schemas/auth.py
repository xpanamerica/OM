from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    turnstile_token: str | None = Field(
        default=None,
        max_length=4096,
        description="Cloudflare Turnstile 前端 widget 返回的短期 token。",
    )
    invite_code: str | None = Field(
        default=None,
        max_length=128,
        description="内测阶段在平台开启校验时必填；完全开放注册时可省略。",
    )
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

    @field_validator("invite_code", mode="before")
    @classmethod
    def strip_invite_code(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("turnstile_token", mode="before")
    @classmethod
    def strip_turnstile_token(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
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


class ForgotPasswordIn(BaseModel):
    model_config = {"extra": "forbid"}

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def strip_email_fp(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class ForgotPasswordOut(BaseModel):
    model_config = {"extra": "forbid"}

    success: bool = True
    message: str = Field(
        default="若该邮箱已注册，您将收到一封包含说明的邮件。",
        description="防邮箱枚举的固定文案。",
    )


class ResetPasswordIn(BaseModel):
    model_config = {"extra": "forbid"}

    token: str = Field(min_length=16, max_length=512, description="忘记密码流程返回的明文令牌（邮件/日志中的链接或 token 字段）。")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="新密码；至少 8 字符；UTF-8 总长度不超过 72 字节（bcrypt 限制）。",
    )

    @field_validator("token", mode="before")
    @classmethod
    def strip_token(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("password")
    @classmethod
    def password_within_bcrypt_byte_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("密码过长：UTF-8 编码长度不得超过 72 字节（bcrypt 限制）")
        return v


class ResetPasswordOut(BaseModel):
    model_config = {"extra": "forbid"}

    success: bool = True
    message: str = Field(default="密码已重置，请使用新密码登录。")
