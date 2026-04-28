from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """用户角色（仅存枚举值，禁止任意字符串写入数据库）。"""

    USER = "user"
    ADMIN = "admin"


class VideoStatus(str, Enum):
    """视频生命周期状态（含审核与上下架；合法迁移见 `app.domain.video_workflow_rules`）。"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    OFFLINE = "offline"


class VodUploadStatus(str, Enum):
    """阿里云 VOD 侧上传进度（业务粗粒度；回调接入后可细化）。"""

    NOT_STARTED = "not_started"
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"


class VodTranscodeStatus(str, Enum):
    """阿里云 VOD 转码状态（粗粒度）。"""

    NONE = "none"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AiJobType(str, Enum):
    """AI 内容任务类型（阶段 15 框架；执行器可后续替换为真实模型）。"""

    TRANSCRIPT = "transcript"
    SUMMARY = "summary"
    CONCEPT_EXTRACT = "concept_extract"
    CHAPTER_EXTRACT = "chapter_extract"


class AiJobStatus(str, Enum):
    """AI 任务状态。"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
