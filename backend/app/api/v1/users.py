from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies.auth import CurrentUser, OptionalUser
from app.api.deps import DbSession
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.schemas.algorithm_reset import (
    AiAgentPanelOut,
    AlgorithmResetResponse,
    AlgorithmStateResponse,
    AlgorithmStateUpdate,
    AttentionIndexResponse,
    GovernancePowerOut,
)
from app.schemas.profile_hub import ProfileHubOut
from app.schemas.social import (
    BlockedUserOut,
    FollowUserOut,
    FriendRequestCreate,
    FriendRequestOut,
    PublicUserProfileOut,
    UserPrivacyOut,
    UserPrivacyUpdate,
)
from app.schemas.user import UserPublic
from app.schemas.video import VideoListItem
from app.services import algorithm_reset_service, social_service, user_avatar_service, user_profile_service, video_interaction_service

router = APIRouter()


@router.get("/me", response_model=UserPublic)
def read_me(current_user: CurrentUser, response: Response) -> UserPublic:
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return UserPublic.model_validate(current_user)


@router.post(
    "/me/avatar",
    response_model=UserPublic,
    summary="上传我的头像",
    dependencies=[Depends(set_mutation_cache_control)],
)
async def upload_my_avatar(
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="JPG/PNG/WebP 头像图片")],
) -> UserPublic:
    return await user_avatar_service.save_avatar(db, actor=current_user, upload=file)


@router.get("/{user_id}/avatar", response_class=FileResponse, summary="读取用户头像")
def read_user_avatar(user_id: UUID, db: DbSession) -> FileResponse:
    path, media_type = user_avatar_service.avatar_file_path(db, user_id=user_id)
    return FileResponse(
        path=str(path),
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/me/profile-hub",
    response_model=ProfileHubOut,
    summary="个人中心聚合数据",
    description="须登录；关注数、粉丝数、已发布稿件累计获赞+收藏、未读互动消息数、最近稿件（含草稿等，作者视角）。",
)
def read_my_profile_hub(
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
) -> ProfileHubOut:
    out = user_profile_service.build_profile_hub(db, current_user)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return out


@router.get("/me/privacy", response_model=UserPrivacyOut, summary="我的隐私设置")
def read_my_privacy(db: DbSession, current_user: CurrentUser, response: Response) -> UserPrivacyOut:
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return social_service.get_my_privacy(db, current_user)


@router.patch(
    "/me/privacy",
    response_model=UserPrivacyOut,
    summary="更新我的隐私设置",
    dependencies=[Depends(set_mutation_cache_control)],
)
def update_my_privacy(
    payload: UserPrivacyUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> UserPrivacyOut:
    return social_service.update_my_privacy(db, current_user, payload)


@router.post(
    "/me/algorithm-reset",
    response_model=AlgorithmResetResponse,
    summary="一键归源",
    description="重置当前用户的推荐画像与推荐缓存状态，让推荐回到随机、均衡、非画像化的初始探索模式。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def reset_my_algorithm(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> AlgorithmResetResponse:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else None
    if not ip and request.client is not None:
        ip = request.client.host
    user_agent = request.headers.get("user-agent")
    return algorithm_reset_service.reset_to_origin(
        db,
        user=current_user,
        ip_address=ip,
        user_agent=user_agent,
    )


@router.get(
    "/me/algorithm-state",
    response_model=AlgorithmStateResponse,
    summary="读取我的算法模式",
)
def read_my_algorithm_state(db: DbSession, current_user: CurrentUser) -> AlgorithmStateResponse:
    return algorithm_reset_service.get_or_create_algorithm_state(db, user=current_user)


@router.patch(
    "/me/algorithm-state",
    response_model=AlgorithmStateResponse,
    summary="切换我的算法模式",
    dependencies=[Depends(set_mutation_cache_control)],
)
def update_my_algorithm_state(
    payload: AlgorithmStateUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AlgorithmStateResponse:
    return algorithm_reset_service.update_algorithm_state(db, user=current_user, payload=payload)


@router.get("/me/attention-index", response_model=AttentionIndexResponse, summary="我的关注指数")
def read_my_attention_index(db: DbSession, current_user: CurrentUser) -> AttentionIndexResponse:
    return algorithm_reset_service.get_attention_index(db, user=current_user)


@router.get("/me/ai-agent-panel", response_model=AiAgentPanelOut, summary="我的 AI Agent 面板")
def read_my_ai_agent_panel(db: DbSession, current_user: CurrentUser) -> AiAgentPanelOut:
    return algorithm_reset_service.get_ai_agent_panel(db, user=current_user)


@router.get("/me/governance-power", response_model=GovernancePowerOut, summary="我的算法治理投票权重")
def read_my_governance_power(db: DbSession, current_user: CurrentUser) -> GovernancePowerOut:
    return algorithm_reset_service.get_governance_power(db, user=current_user)


@router.get("/me/blocked-users", response_model=list[BlockedUserOut], summary="我拉黑的用户")
def list_my_blocked_users(
    db: DbSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[BlockedUserOut]:
    return social_service.list_blocked(db, actor=current_user, offset=offset, limit=limit)


@router.get("/me/friends", response_model=list[FollowUserOut], summary="我的好友列表")
def list_my_friends(
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[FollowUserOut]:
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return social_service.list_my_friends(db, current_user=current_user, offset=offset, limit=limit)


@router.get("/me/friend-requests", response_model=list[FriendRequestOut], summary="我的好友申请")
def list_my_friend_requests(
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
    box: Annotated[str, Query(pattern="^(incoming|outgoing)$")] = "incoming",
    status: Annotated[str, Query(pattern="^(pending|accepted|rejected|cancelled)$")] = "pending",
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[FriendRequestOut]:
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return social_service.list_friend_requests(
        db,
        current_user=current_user,
        box=box,
        status=status,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/me/friend-requests/{request_id}/accept",
    response_model=FriendRequestOut,
    summary="通过好友申请",
    dependencies=[Depends(set_mutation_cache_control)],
)
def accept_friend_request(
    request_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> FriendRequestOut:
    return social_service.decide_friend_request(db, current_user=current_user, request_id=request_id, accept=True)


@router.post(
    "/me/friend-requests/{request_id}/reject",
    response_model=FriendRequestOut,
    summary="拒绝好友申请",
    dependencies=[Depends(set_mutation_cache_control)],
)
def reject_friend_request(
    request_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> FriendRequestOut:
    return social_service.decide_friend_request(db, current_user=current_user, request_id=request_id, accept=False)


@router.get(
    "/{user_id}/profile",
    response_model=PublicUserProfileOut,
    summary="查看用户公开主页",
    description="按对方隐私设置控制访问；返回关注关系、互关状态、私信可用性与最近已发布作品。",
)
def read_user_profile(
    user_id: UUID,
    db: DbSession,
    current_user: OptionalUser,
    response: Response,
) -> PublicUserProfileOut:
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return social_service.get_public_profile(db, viewer=current_user, user_id=user_id)


@router.post(
    "/{user_id}/friend-requests",
    response_model=FriendRequestOut,
    summary="发送好友申请",
    dependencies=[Depends(set_mutation_cache_control)],
)
def send_friend_request(
    user_id: UUID,
    payload: FriendRequestCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> FriendRequestOut:
    return social_service.send_friend_request(db, actor=current_user, target_id=user_id, payload=payload)


@router.post(
    "/{user_id}/follow",
    status_code=204,
    summary="关注用户",
    dependencies=[Depends(set_mutation_cache_control)],
)
def follow_user(
    user_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    user_profile_service.follow_user(db, current_user, user_id)
    return Response(status_code=204)


@router.delete(
    "/{user_id}/follow",
    status_code=204,
    summary="取消关注",
    dependencies=[Depends(set_mutation_cache_control)],
)
def unfollow_user(
    user_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    user_profile_service.unfollow_user(db, current_user, user_id)
    return Response(status_code=204)


@router.post(
    "/{user_id}/block",
    status_code=204,
    summary="拉黑用户",
    dependencies=[Depends(set_mutation_cache_control)],
)
def block_user(
    user_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    social_service.block_user(db, actor=current_user, target_id=user_id)
    return Response(status_code=204)


@router.delete(
    "/{user_id}/block",
    status_code=204,
    summary="解除拉黑",
    dependencies=[Depends(set_mutation_cache_control)],
)
def unblock_user(
    user_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    social_service.unblock_user(db, actor=current_user, target_id=user_id)
    return Response(status_code=204)


@router.get(
    "/{user_id}/following",
    response_model=list[FollowUserOut],
    summary="用户关注列表",
)
def list_user_following(
    user_id: UUID,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[FollowUserOut]:
    rows = social_service.list_following(db, viewer=current_user, user_id=user_id, offset=offset, limit=limit)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return rows


@router.get(
    "/{user_id}/followers",
    response_model=list[FollowUserOut],
    summary="用户粉丝列表",
)
def list_user_followers(
    user_id: UUID,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[FollowUserOut]:
    rows = social_service.list_followers(db, viewer=current_user, user_id=user_id, offset=offset, limit=limit)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return rows


@router.get(
    "/me/favorite-videos",
    response_model=list[VideoListItem],
    summary="我收藏的视频",
    description="须登录；仅含当前仍为 ``published`` 的收藏；偏移分页，响应头 ``X-Total-Count``。",
)
def list_my_favorite_videos(
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[VideoListItem]:
    items, total = video_interaction_service.list_my_favorite_videos(db, current_user, offset=offset, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return items
