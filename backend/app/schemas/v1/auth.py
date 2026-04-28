"""v1 复用顶层 schema，避免重复定义。"""

from app.schemas.auth import Token, UserRegister

__all__ = ["Token", "UserRegister"]
