"""v1 复用顶层 schema，避免重复定义。"""

from app.schemas.user import UserPublic

__all__ = ["UserPublic"]
