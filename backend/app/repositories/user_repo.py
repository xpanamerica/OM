"""兼容旧导入路径 `app.repositories.user_repo`，请优先使用 `user_repository`。"""

from app.repositories.user_repository import (  # noqa: F401
    create_user,
    get_by_email,
    get_by_id,
    get_by_login_identifier,
    get_by_username,
)
