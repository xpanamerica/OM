from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.enums import UserRole, VideoStatus
from app.models.user import User
from app.repositories import (
    direct_message_repository,
    user_block_repository,
    user_follow_repository,
    user_friend_request_repository,
    user_privacy_repository,
    user_repository,
    video_repository,
)
from app.schemas.social import (
    BlockedUserOut,
    DirectConversationOut,
    DirectMessageOut,
    FriendRequestCreate,
    FriendRequestOut,
    FollowUserOut,
    PublicUserProfileOut,
    UserBrief,
    UserPrivacyOut,
    UserPrivacyUpdate,
)
from app.services import notification_service, video_privacy


def _brief(user: User) -> UserBrief:
    return UserBrief.model_validate(user)


def _friend_request_out(row, requester: User, recipient: User) -> FriendRequestOut:
    return FriendRequestOut(
        id=row.id,
        requester=_brief(requester),
        recipient=_brief(recipient),
        status=row.status,
        message=row.message,
        decided_at=row.decided_at,
        created_at=row.created_at,
    )


def _direct_message_preview(body: str) -> str:
    try:
        data = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        return body.strip()[:120] or "新消息"
    if not isinstance(data, dict) or not data.get("__om_dm_v1"):
        return body.strip()[:120] or "新消息"
    text = str(data.get("text") or "").strip()
    if text:
        return text[:120]
    attachments = data.get("attachments")
    if isinstance(attachments, list) and attachments:
        first = attachments[0] if isinstance(attachments[0], dict) else {}
        content_type = str(first.get("content_type") or "")
        if content_type.startswith("image/"):
            return "[图片]"
        return "[附件]"
    return "新消息"


def _privacy_out(user_id: uuid.UUID, db: Session) -> UserPrivacyOut:
    row = user_privacy_repository.get_or_create(db, user_id=user_id)
    return UserPrivacyOut(
        profile_visibility=row.profile_visibility,  # type: ignore[arg-type]
        message_permission=row.message_permission,  # type: ignore[arg-type]
    )


def get_my_privacy(db: Session, user: User) -> UserPrivacyOut:
    return _privacy_out(user.id, db)


def update_my_privacy(db: Session, user: User, payload: UserPrivacyUpdate) -> UserPrivacyOut:
    row = user_privacy_repository.get_or_create(db, user_id=user.id)
    if payload.profile_visibility is not None:
        row.profile_visibility = payload.profile_visibility
    if payload.message_permission is not None:
        row.message_permission = payload.message_permission
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserPrivacyOut(
        profile_visibility=row.profile_visibility,  # type: ignore[arg-type]
        message_permission=row.message_permission,  # type: ignore[arg-type]
    )


def relation_flags(db: Session, *, viewer: User | None, target_id: uuid.UUID) -> tuple[bool, bool, bool]:
    if viewer is None or viewer.id == target_id:
        return False, False, False
    is_following = user_follow_repository.exists(db, follower_id=viewer.id, followee_id=target_id)
    follows_me = user_follow_repository.exists(db, follower_id=target_id, followee_id=viewer.id)
    return is_following, follows_me, is_following and follows_me


def friend_request_status(db: Session, *, viewer: User | None, target_id: uuid.UUID, is_mutual: bool) -> str:
    if viewer is None or viewer.id == target_id:
        return "none"
    if is_mutual:
        return "accepted"
    pending = user_friend_request_repository.find_pending_between(db, user_a=viewer.id, user_b=target_id)
    if pending is None:
        return "none"
    if pending.requester_id == viewer.id:
        return "outgoing_pending"
    return "incoming_pending"


def can_view_profile(db: Session, *, viewer: User | None, target: User) -> bool:
    if viewer is not None and (viewer.id == target.id or viewer.role == UserRole.ADMIN):
        return True
    if viewer is not None and user_block_repository.exists(db, blocker_id=target.id, blocked_id=viewer.id):
        return False
    if viewer is not None and user_block_repository.exists(db, blocker_id=viewer.id, blocked_id=target.id):
        return True
    privacy = user_privacy_repository.get_or_create(db, user_id=target.id)
    mode = privacy.profile_visibility
    if mode == "public":
        return True
    if viewer is None:
        return False
    is_following, follows_me, is_mutual = relation_flags(db, viewer=viewer, target_id=target.id)
    _ = follows_me
    if mode == "followers":
        return is_following
    if mode == "mutual":
        return is_mutual
    return False


def can_send_message(db: Session, *, sender: User, recipient: User) -> bool:
    if sender.id == recipient.id:
        return False
    if user_block_repository.any_between(db, user_a=sender.id, user_b=recipient.id):
        return False
    privacy = user_privacy_repository.get_or_create(db, user_id=recipient.id)
    mode = privacy.message_permission
    if mode == "everyone":
        return True
    is_following, follows_me, is_mutual = relation_flags(db, viewer=sender, target_id=recipient.id)
    _ = is_following
    if mode == "following":
        return follows_me
    if mode == "mutual":
        return is_mutual
    return False


def get_public_profile(db: Session, *, viewer: User | None, user_id: uuid.UUID) -> PublicUserProfileOut:
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        raise AppError("用户不存在", status_code=404)
    if not can_view_profile(db, viewer=viewer, target=target):
        raise AppError("对方设置了个人页访问权限", status_code=403)
    following = user_follow_repository.count_following(db, user_id=target.id)
    followers = user_follow_repository.count_followers(db, user_id=target.id)
    friends = user_follow_repository.count_mutual_friends(db, user_id=target.id)
    likes_recv = video_repository.sum_published_likes_and_favorites_on_author_videos(db, author_id=target.id)
    is_following, follows_me, is_mutual = relation_flags(db, viewer=viewer, target_id=target.id)
    is_blocked = bool(viewer and user_block_repository.exists(db, blocker_id=viewer.id, blocked_id=target.id))
    blocked_me = bool(viewer and user_block_repository.exists(db, blocker_id=target.id, blocked_id=viewer.id))
    raw = video_repository.list_videos(
        db,
        offset=0,
        limit=12,
        only_published=True,
        status=VideoStatus.PUBLISHED,
        category_id=None,
        tag_id=None,
        author_id=target.id,
    )
    return PublicUserProfileOut(
        user=_brief(target),
        following_count=following,
        followers_count=followers,
        friends_count=friends,
        likes_and_favorites_received=likes_recv,
        is_following=is_following,
        follows_me=follows_me,
        is_mutual=is_mutual,
        is_blocked=is_blocked,
        blocked_me=blocked_me,
        can_message=viewer is not None and can_send_message(db, sender=viewer, recipient=target),
        friend_request_status=friend_request_status(db, viewer=viewer, target_id=target.id, is_mutual=is_mutual),
        privacy=_privacy_out(target.id, db),
        recent_videos=[video_privacy.video_list_item_for_viewer(v, viewer, db) for v in raw],
    )


def block_user(db: Session, *, actor: User, target_id: uuid.UUID) -> None:
    if target_id == actor.id:
        raise AppError("不能拉黑自己", status_code=400)
    if user_repository.get_by_id(db, target_id) is None:
        raise AppError("用户不存在", status_code=404)
    if user_block_repository.exists(db, blocker_id=actor.id, blocked_id=target_id):
        raise AppError("已经拉黑", status_code=409)
    user_block_repository.create(db, blocker_id=actor.id, blocked_id=target_id)
    user_follow_repository.delete_pair(db, follower_id=actor.id, followee_id=target_id)
    user_follow_repository.delete_pair(db, follower_id=target_id, followee_id=actor.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("已经拉黑", status_code=409) from None


def unblock_user(db: Session, *, actor: User, target_id: uuid.UUID) -> None:
    n = user_block_repository.delete_pair(db, blocker_id=actor.id, blocked_id=target_id)
    if n == 0:
        raise AppError("尚未拉黑该用户", status_code=404)
    db.commit()


def list_blocked(db: Session, *, actor: User, offset: int, limit: int) -> list[BlockedUserOut]:
    return [
        BlockedUserOut(id=u.id, username=u.username, blocked_at=b.created_at)
        for u, b in user_block_repository.list_blocked(db, blocker_id=actor.id, offset=offset, limit=limit)
    ]


def _follow_out(db: Session, *, viewer: User, user: User, followed_at) -> FollowUserOut:
    is_following, follows_me, is_mutual = relation_flags(db, viewer=viewer, target_id=user.id)
    return FollowUserOut(
        id=user.id,
        username=user.username,
        avatar_url=user.avatar_url,
        followed_at=followed_at,
        is_following=is_following,
        follows_me=follows_me,
        is_mutual=is_mutual,
    )


def list_following(db: Session, *, viewer: User, user_id: uuid.UUID, offset: int, limit: int) -> list[FollowUserOut]:
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        raise AppError("用户不存在", status_code=404)
    if not can_view_profile(db, viewer=viewer, target=target):
        raise AppError("对方设置了个人页访问权限", status_code=403)
    return [_follow_out(db, viewer=viewer, user=u, followed_at=f.created_at) for u, f in user_follow_repository.list_following(db, user_id=user_id, offset=offset, limit=limit)]


def list_followers(db: Session, *, viewer: User, user_id: uuid.UUID, offset: int, limit: int) -> list[FollowUserOut]:
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        raise AppError("用户不存在", status_code=404)
    if not can_view_profile(db, viewer=viewer, target=target):
        raise AppError("对方设置了个人页访问权限", status_code=403)
    return [_follow_out(db, viewer=viewer, user=u, followed_at=f.created_at) for u, f in user_follow_repository.list_followers(db, user_id=user_id, offset=offset, limit=limit)]


def list_my_friends(db: Session, *, current_user: User, offset: int, limit: int) -> list[FollowUserOut]:
    rows = user_follow_repository.list_mutual_friends(db, user_id=current_user.id, offset=offset, limit=limit)
    return [_follow_out(db, viewer=current_user, user=u, followed_at=f.created_at) for u, f in rows]


def send_friend_request(
    db: Session,
    *,
    actor: User,
    target_id: uuid.UUID,
    payload: FriendRequestCreate,
) -> FriendRequestOut:
    if target_id == actor.id:
        raise AppError("不能添加自己为好友", status_code=400)
    target = user_repository.get_by_id(db, target_id)
    if target is None:
        raise AppError("用户不存在", status_code=404)
    if user_block_repository.any_between(db, user_a=actor.id, user_b=target_id):
        raise AppError("无法向该用户发送好友申请", status_code=403)
    _, _, is_mutual = relation_flags(db, viewer=actor, target_id=target_id)
    if is_mutual:
        raise AppError("你们已经是好友", status_code=409)
    pending = user_friend_request_repository.find_pending_between(db, user_a=actor.id, user_b=target_id)
    if pending is not None:
        if pending.requester_id == actor.id:
            raise AppError("好友申请已发送，请等待对方处理", status_code=409)
        raise AppError("对方已向你发送好友申请，请在消息中处理", status_code=409)
    row = user_friend_request_repository.create(
        db,
        requester_id=actor.id,
        recipient_id=target_id,
        message=(payload.message or "").strip() or None,
    )
    notification_service.create_event(
        db,
        user_id=target_id,
        title=f"{actor.username} 请求添加你为好友",
        body=row.message or "对方希望与你成为好友，通过后会进入好友列表并可继续私信交流。",
        kind="friend_request",
        action_url=f"/me/messages?friend_request_id={row.id}",
    )
    db.commit()
    db.refresh(row)
    return _friend_request_out(row, actor, target)


def list_friend_requests(
    db: Session,
    *,
    current_user: User,
    box: str,
    status: str,
    offset: int,
    limit: int,
) -> list[FriendRequestOut]:
    if box == "outgoing":
        rows = user_friend_request_repository.list_outgoing(
            db,
            requester_id=current_user.id,
            status=status,
            offset=offset,
            limit=limit,
        )
        return [_friend_request_out(r, current_user, peer) for r, peer in rows]
    rows = user_friend_request_repository.list_incoming(
        db,
        recipient_id=current_user.id,
        status=status,
        offset=offset,
        limit=limit,
    )
    return [_friend_request_out(r, peer, current_user) for r, peer in rows]


def decide_friend_request(
    db: Session,
    *,
    current_user: User,
    request_id: uuid.UUID,
    accept: bool,
) -> FriendRequestOut:
    row = user_friend_request_repository.get_by_id(db, request_id)
    if row is None or row.recipient_id != current_user.id:
        raise AppError("好友申请不存在或无权处理", status_code=404)
    if row.status != "pending":
        raise AppError("该好友申请已处理", status_code=409)
    requester = user_repository.get_by_id(db, row.requester_id)
    if requester is None:
        raise AppError("申请人不存在", status_code=404)
    row.status = "accepted" if accept else "rejected"
    row.decided_at = datetime.now(tz=UTC)
    db.add(row)
    if accept:
        if not user_follow_repository.exists(db, follower_id=row.requester_id, followee_id=row.recipient_id):
            user_follow_repository.create(db, follower_id=row.requester_id, followee_id=row.recipient_id)
        if not user_follow_repository.exists(db, follower_id=row.recipient_id, followee_id=row.requester_id):
            user_follow_repository.create(db, follower_id=row.recipient_id, followee_id=row.requester_id)
        notification_service.create_event(
            db,
            user_id=row.requester_id,
            title=f"{current_user.username} 已通过你的好友申请",
            body="你们已经成为好友，可以继续浏览主页并发起私信。",
            kind="friend_request_accepted",
            action_url=f"/users/{current_user.id}",
        )
    else:
        notification_service.create_event(
            db,
            user_id=row.requester_id,
            title=f"{current_user.username} 暂未通过你的好友申请",
            body="你仍可以继续关注对方公开内容。",
            kind="friend_request_rejected",
            action_url=f"/users/{current_user.id}",
        )
    db.commit()
    db.refresh(row)
    return _friend_request_out(row, requester, current_user)


def send_direct_message(db: Session, *, sender: User, recipient_id: uuid.UUID, body: str) -> DirectMessageOut:
    recipient = user_repository.get_by_id(db, recipient_id)
    if recipient is None:
        raise AppError("用户不存在", status_code=404)
    if sender.id == recipient.id:
        raise AppError("不能给自己发送私信", status_code=400)
    if not can_send_message(db, sender=sender, recipient=recipient):
        raise AppError("对方设置了私信权限", status_code=403)
    conv = direct_message_repository.get_or_create_conversation(db, user_a=sender.id, user_b=recipient.id)
    msg = direct_message_repository.add_message(
        db,
        conversation_id=conv.id,
        sender_id=sender.id,
        recipient_id=recipient.id,
        body=body.strip(),
    )
    notification_service.create_event(
        db,
        user_id=recipient.id,
        title=f"{sender.username} 发来一条私信",
        body=_direct_message_preview(body),
        kind="direct_message",
        action_url=f"/me/direct-messages/{sender.id}",
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("会话创建失败，请重试", status_code=409) from None
    db.refresh(msg)
    return DirectMessageOut.model_validate(msg)


def list_messages_with_peer(
    db: Session, *, current_user: User, peer_id: uuid.UUID, offset: int, limit: int
) -> list[DirectMessageOut]:
    peer = user_repository.get_by_id(db, peer_id)
    if peer is None:
        raise AppError("用户不存在", status_code=404)
    conv = direct_message_repository.get_conversation_between(db, user_a=current_user.id, user_b=peer_id)
    if conv is None:
        return []
    items = direct_message_repository.list_messages(db, conversation_id=conv.id, offset=offset, limit=limit)
    direct_message_repository.mark_read_from_peer(db, conversation_id=conv.id, recipient_id=current_user.id)
    db.commit()
    return [DirectMessageOut.model_validate(x) for x in items]


def list_conversations(db: Session, *, current_user: User, offset: int, limit: int) -> list[DirectConversationOut]:
    rows = direct_message_repository.list_conversations_for_user(
        db, user_id=current_user.id, offset=offset, limit=limit
    )
    out: list[DirectConversationOut] = []
    for conv, peer in rows:
        last = direct_message_repository.last_message(db, conversation_id=conv.id)
        out.append(
            DirectConversationOut(
                id=conv.id,
                peer=_brief(peer),
                last_message=DirectMessageOut.model_validate(last) if last is not None else None,
                last_message_preview=_direct_message_preview(last.body) if last is not None else None,
                unread_count=direct_message_repository.unread_count(
                    db, conversation_id=conv.id, user_id=current_user.id
                ),
                updated_at=conv.last_message_at,
            )
        )
    return out
