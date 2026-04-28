"""已迁移至 `app.api.v1.users`，保留此导入以兼容旧路径。"""

from app.api.v1.users import router

__all__ = ["router"]
