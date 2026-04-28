from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.video import VideoListItem

ProfileVisibility = Literal["public", "followers", "mutual", "private"]
MessagePermission = Literal["everyone", "following", "mutual", "none"]
FriendRequestStatus = Literal["none", "incoming_pending", "outgoing_pending", "accepted", "rejected"]


class UserBrief(BaseModel):
    id: uuid.UUID
    username: str = Field(min_length=2, max_length=64)
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class UserPrivacyOut(BaseModel):
    profile_visibility: ProfileVisibility
    message_permission: MessagePermission


class UserPrivacyUpdate(BaseModel):
    profile_visibility: ProfileVisibility | None = None
    message_permission: MessagePermission | None = None


class PublicUserProfileOut(BaseModel):
    user: UserBrief
    following_count: int = Field(ge=0)
    followers_count: int = Field(ge=0)
    friends_count: int = Field(ge=0)
    likes_and_favorites_received: int = Field(ge=0)
    is_following: bool
    follows_me: bool
    is_mutual: bool
    is_blocked: bool
    blocked_me: bool
    can_message: bool
    friend_request_status: FriendRequestStatus = "none"
    privacy: UserPrivacyOut
    recent_videos: list[VideoListItem]


class FollowUserOut(UserBrief):
    followed_at: datetime
    is_following: bool
    follows_me: bool
    is_mutual: bool


class BlockedUserOut(UserBrief):
    blocked_at: datetime


class FriendRequestCreate(BaseModel):
    message: str | None = Field(default=None, max_length=200)


class FriendRequestOut(BaseModel):
    id: uuid.UUID
    requester: UserBrief
    recipient: UserBrief
    status: Literal["pending", "accepted", "rejected", "cancelled"]
    message: str | None = None
    decided_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DirectMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class DirectMessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    recipient_id: uuid.UUID
    body: str
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DirectConversationOut(BaseModel):
    id: uuid.UUID
    peer: UserBrief
    last_message: DirectMessageOut | None
    last_message_preview: str | None = None
    unread_count: int = Field(ge=0)
    updated_at: datetime | None


class DirectMessageAttachmentOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str | None
    size_bytes: int = Field(ge=0)
    url: str
    created_at: datetime
