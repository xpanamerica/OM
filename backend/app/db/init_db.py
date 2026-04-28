from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.repositories import user_repository


def init_db(db: Session) -> None:
    """若配置了首个超级用户环境变量，则在首次启动时创建。"""
    if settings.FIRST_SUPERUSER_EMAIL is None or settings.FIRST_SUPERUSER_USERNAME is None:
        return
    email = str(settings.FIRST_SUPERUSER_EMAIL).strip().lower()
    username = settings.FIRST_SUPERUSER_USERNAME.strip()
    pwd = settings.FIRST_SUPERUSER_PASSWORD
    if not email or not username or pwd is None:
        return
    password_plain = pwd.get_secret_value()
    if not password_plain:
        return
    if user_repository.get_by_email(db, email) or user_repository.get_by_username(db, username):
        return
    try:
        user_repository.create_user(
            db,
            email=email,
            username=username,
            hashed_password=get_password_hash(password_plain),
            role=UserRole.ADMIN,
        )
        db.commit()
    except IntegrityError:
        # create_user 内会 flush；多实例竞态下可能在 flush/commit 任一步触发唯一约束冲突
        db.rollback()
