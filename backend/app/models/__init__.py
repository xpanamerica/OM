"""ORM 模型聚合导入，供 Alembic `target_metadata` 与业务层使用。"""

from app.models.category import Category
from app.models.comment import Comment
from app.models.concept import Concept, VideoConcept
from app.models.direct_message import DirectConversation, DirectMessage, DirectMessageAttachment
from app.models.ai_job import AiJob
from app.models.algorithm_reset import AlgorithmResetLog, AttentionValueSnapshot, UserAlgorithmPreset, UserAlgorithmState
from app.models.app_setting import AppSetting
from app.models.invite_code import InviteCode
from app.models.enums import AiJobStatus, AiJobType, UserRole, VideoStatus
from app.models.learning_path import LearningPath, LearningPathItem
from app.models.tag import Tag
from app.models.upload_intent import UploadIntent
from app.models.registration_attempt import RegistrationAttempt
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.security_event import SecurityEvent
from app.models.user import User
from app.models.user_auth_state import UserAuthState
from app.models.user_block import UserBlock
from app.models.user_follow import UserFollow
from app.models.user_friend_request import UserFriendRequest
from app.models.user_mfa_setting import UserMfaSetting
from app.models.user_notification import UserNotification
from app.models.user_privacy import UserPrivacySetting
from app.models.video import Video, video_tags
from app.models.video_attachment import VideoAttachment
from app.models.video_favorite import VideoFavorite
from app.models.video_like import VideoLike
from app.models.video_workflow_event import VideoWorkflowEvent
from app.models.view_record import ViewRecord

__all__ = [
    "AiJob",
    "AiJobStatus",
    "AiJobType",
    "AlgorithmResetLog",
    "AttentionValueSnapshot",
    "UserAlgorithmPreset",
    "AppSetting",
    "Category",
    "Comment",
    "Concept",
    "DirectConversation",
    "DirectMessage",
    "DirectMessageAttachment",
    "InviteCode",
    "PasswordResetToken",
    "LearningPath",
    "LearningPathItem",
    "Tag",
    "RegistrationAttempt",
    "RefreshToken",
    "SecurityEvent",
    "UploadIntent",
    "User",
    "UserAuthState",
    "UserAlgorithmState",
    "UserBlock",
    "UserFollow",
    "UserFriendRequest",
    "UserMfaSetting",
    "UserNotification",
    "UserPrivacySetting",
    "UserRole",
    "Video",
    "VideoAttachment",
    "VideoConcept",
    "VideoFavorite",
    "VideoLike",
    "VideoStatus",
    "ViewRecord",
    "VideoWorkflowEvent",
    "video_tags",
]
