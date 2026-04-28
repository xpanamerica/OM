"""站内消息：``GET/PATCH/POST /users/me/notifications…``。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.deps import DbSession
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL
from app.core.exceptions import AppError
from app.schemas.user_notification import UserNotificationOut, UserNotificationUnreadCount
from app.services import notification_service

router = APIRouter()


@router.get(
    "/me/notifications/unread-count",
    response_model=UserNotificationUnreadCount,
    summary="未读消息数（个人中心角标）",
)
def get_my_notifications_unread_count(
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
) -> UserNotificationUnreadCount:
    n = notification_service.unread_count_for_hub(db, user_id=current_user.id)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return UserNotificationUnreadCount(unread_count=n)


@router.get(
    "/me/notifications",
    response_model=list[UserNotificationOut],
    summary="我的站内消息列表",
)
def list_my_notifications(
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[UserNotificationOut]:
    items, total, unread = notification_service.list_my_notifications(
        db, user_id=current_user.id, offset=offset, limit=limit
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Unread-Count"] = str(unread)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return [UserNotificationOut.model_validate(x) for x in items]


@router.patch("/me/notifications/{notification_id}/read", response_model=UserNotificationOut)
def mark_notification_read(
    notification_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> UserNotificationOut:
    row = notification_service.mark_read(db, user_id=current_user.id, notification_id=notification_id)
    if row is None:
        raise AppError("消息不存在或无权访问", status_code=404)
    return UserNotificationOut.model_validate(row)


@router.post("/me/notifications/read-all")
def mark_all_notifications_read(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, int]:
    n = notification_service.mark_all_read(db, user_id=current_user.id)
    return {"marked": n}
