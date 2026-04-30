import json
import re
from typing import Any, Self

from pydantic import EmailStr, Field, SecretStr, ValidationInfo, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。

    `SECRET_KEY` 与 `FIRST_SUPERUSER_PASSWORD` 使用 `SecretStr`，避免 `repr` / 日志无意泄露；
    取值请用 `.get_secret_value()`。
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = Field(default="video-knowledge-api", min_length=1, max_length=128)

    @field_validator("APP_NAME", mode="before")
    @classmethod
    def strip_app_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("LOG_FILE_DIR", mode="before")
    @classmethod
    def normalize_log_file_dir(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v

    ENVIRONMENT: str = Field(
        default="local",
        description="运行环境：local/development 为开发态；production|prod|staging 启用更严的 CORS/SECRET/文档策略。",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="根日志级别（DEBUG/INFO/WARNING/ERROR），由 ``setup_logging`` 应用。",
    )
    LOG_FILE_DIR: str | None = Field(
        default=None,
        description=(
            "可选。若为非空字符串，则在该目录下追加写入 ``app.log``（UTF-8）；"
            "目录不存在时会尝试创建。生产可挂载可写卷到该路径。"
        ),
    )
    EXPOSE_INTERNAL_ERROR_DETAILS: bool = Field(
        default=False,
        description=(
            "未捕获异常时是否在 JSON ``detail`` 中附带异常类型与消息；默认 **False**（任何环境均只返回泛化文案，"
            "避免泄露实现细节）。本地深度排障可临时设为 **True**（生产类环境仍仅返回泛化文案）。"
        ),
    )
    EXPOSE_OPENAPI_DOCS: bool | None = Field(
        default=None,
        description=(
            "是否暴露 /docs、/redoc、/openapi.json：None 时按 ENVIRONMENT（production/prod/staging 关闭）；"
            "显式 True/False 可覆盖（例如受信内网 staging 临时开文档）。"
        ),
    )
    SECURITY_HSTS_MAX_AGE: int = Field(
        default=0,
        ge=0,
        le=365 * 24 * 3600,
        description=(
            "在「关闭 OpenAPI 文档」的响应上追加 ``Strict-Transport-Security: max-age=…``（秒）。"
            "默认 0 不发送；仅当客户端 **始终经 HTTPS** 访问本 API 时设为正值（如 31536000）。"
        ),
    )
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["*"],
        description="浏览器 Access-Control-Allow-Origin；逗号分隔字符串或 JSON 数组；生产类环境禁止仅 *",
    )

    SECRET_KEY: SecretStr = Field(description="JWT HMAC 密钥，UTF-8 至少 32 字节")
    JWT_CURRENT_KID: str = Field(default="default", min_length=1, max_length=64)
    JWT_SIGNING_KEYS: str | None = Field(
        default=None,
        description=(
            "可选 JWT 多密钥配置。兼容 kid:secret,kid2:secret；推荐 JSON："
            '{"current":"k2","keys":[{"kid":"k1","secret":"...","not_after":1893456000},{"kid":"k2","secret":"..."}]}。'
        ),
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=60 * 24 * 30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=30,
        ge=7,
        le=30,
        description="Refresh token 有效期（天），合规范围 7-30 天。",
    )
    REFRESH_TOKEN_COOKIE_NAME: str = Field(
        default="om_refresh_token",
        min_length=1,
        max_length=128,
        description="HttpOnly refresh token Cookie 名称。",
    )
    REFRESH_TOKEN_COOKIE_PATH: str = Field(
        default="/api/v1/auth",
        min_length=1,
        max_length=256,
        description="Refresh token Cookie 路径，仅认证端点携带。",
    )
    REFRESH_TOKEN_COOKIE_SECURE: bool = Field(
        default=False,
        description="是否给 refresh token Cookie 设置 Secure；HTTPS/生产建议开启。",
    )
    REFRESH_TOKEN_COOKIE_SAMESITE: str = Field(
        default="lax",
        description="Refresh token Cookie SameSite 策略：lax/strict/none。",
    )
    CSRF_COOKIE_NAME: str = Field(
        default="om_csrf_token",
        min_length=1,
        max_length=128,
        description="双提交 CSRF token Cookie 名称（非 HttpOnly，供前端读取）。",
    )
    CSRF_HEADER_NAME: str = Field(
        default="X-CSRF-Token",
        min_length=1,
        max_length=128,
        description="双提交 CSRF token 请求头名称。",
    )

    DATABASE_URL: str = Field(min_length=1)
    REDIS_URL: str = "redis://localhost:6379/0"
    IDEMPOTENCY_ALLOW_MEMORY_FALLBACK: bool = Field(
        default=True,
        description=(
            "为 True 时 Redis 不可用时 Idempotency-Key 回退到进程内字典（单测/单机）。"
            "生产多实例请设为 False：须可用 Redis，否则进程启动失败；带 Key 的请求在 Redis 故障时返回 503。"
        ),
    )

    AUTH_RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description=(
            "启用认证端点生产级限流（注册/登录/忘记密码）；"
            "单测与 CI 通常通过环境变量设为 false。"
        ),
    )
    AUTH_RATE_LIMIT_USE_REDIS: bool = Field(
        default=True,
        description="为 True 且 Redis 可达时，认证限流计数存 Redis（多 worker 一致）。",
    )
    AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY: bool = Field(
        default=True,
        description="Redis 限流调用失败时是否回退进程内滑动窗口；生产若要求严格一致可关（将抛错）。",
    )
    AUTH_RATE_LIMIT_REDIS_STALE_REPROBE_SECONDS: int = Field(
        default=30,
        ge=0,
        le=3600,
        description=(
            "当进程内曾判定 Redis 不可达时，认证限流每隔多少秒对 Redis 再探测一次；"
            "0 表示不重探测（与其它子系统共用首次 ping 缓存）。"
        ),
    )
    AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE: int = Field(
        default=3,
        ge=1,
        le=10_000,
        description="注册：每 IP 滑动 60 秒内最多请求次数。",
    )
    AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR: int = Field(
        default=10,
        ge=1,
        le=100_000,
        description="注册：每 IP 滑动 3600 秒内最多请求次数。",
    )
    AUTH_RATE_LIMIT_LOGIN_PER_IP_PER_MINUTE: int = Field(
        default=5,
        ge=1,
        le=10_000,
        description="登录：每 IP 滑动 60 秒内最多请求次数。",
    )
    AUTH_RATE_LIMIT_LOGIN_FAIL_WINDOW_SECONDS: int = Field(
        default=900,
        ge=60,
        le=86_400,
        description="登录失败计数滑动窗口（秒），默认 15 分钟。",
    )
    AUTH_RATE_LIMIT_LOGIN_FAIL_MAX_PER_ACCOUNT: int = Field(
        default=5,
        ge=1,
        le=10_000,
        description="同一登录标识在上述窗口内允许的最大失败次数，达到后拒绝登录直至窗口滑动。",
    )
    AUTH_RATE_LIMIT_MFA_MAX_ATTEMPTS: int = Field(
        default=5,
        ge=1,
        le=100,
        description="MFA challenge 在窗口内允许的最大失败/验证尝试次数。",
    )
    AUTH_RATE_LIMIT_MFA_WINDOW_SECONDS: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="MFA challenge 尝试次数滑动窗口（秒），默认等于挑战有效期 5 分钟。",
    )
    AUTH_RATE_LIMIT_FORGOT_PER_IP_PER_HOUR: int = Field(
        default=3,
        ge=1,
        le=10_000,
        description="忘记密码：每 IP 滑动 3600 秒内最多请求次数。",
    )
    AUTH_RATE_LIMIT_FORGOT_PER_EMAIL_PER_HOUR: int = Field(
        default=2,
        ge=1,
        le=10_000,
        description="忘记密码：同一规范化邮箱滑动 3600 秒内最多请求次数。",
    )
    AUTH_RATE_LIMIT_REGISTER_MINUTE_WINDOW_SECONDS: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="注册「每分钟」维度的滑动窗口长度（秒）。",
    )
    AUTH_RATE_LIMIT_REGISTER_HOUR_WINDOW_SECONDS: int = Field(
        default=3600,
        ge=120,
        le=604_800,
        description="注册「每小时」维度的滑动窗口长度（秒）。",
    )
    AUTH_RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="登录：每 IP 滑动窗口长度（秒）。",
    )
    AUTH_RATE_LIMIT_FORGOT_WINDOW_SECONDS: int = Field(
        default=3600,
        ge=120,
        le=604_800,
        description="忘记密码：每 IP / 每邮箱共用的时间窗口长度（秒）。",
    )
    AUTH_REGISTER_MAX_ATTEMPTS_PER_MINUTE: int = Field(
        default=0,
        ge=0,
        le=10_000,
        description=(
            "注册：每 IP 在「每分钟」滑动窗口内的**有效上限**；**0** 表示不启用本项，"
            "沿用 ``AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE``。"
            "设为正值时**覆盖**该分钟维度配额（小时维度仍用 ``AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR``），"
            "便于生产单独设为 20–60 等运营值而不改通用限流默认值。"
        ),
    )
    TURNSTILE_SECRET: SecretStr | None = Field(
        default=None,
        description="Cloudflare Turnstile 服务端 secret，仅后端读取；勿下发前端。",
    )
    TURNSTILE_BYPASS: bool = Field(
        default=False,
        description="测试环境绕过 Turnstile 校验；仅允许 NODE_ENV=test。",
    )
    NODE_ENV: str = Field(
        default="",
        description="前后端测试约定环境名；TURNSTILE_BYPASS=true 时必须为 test。",
    )
    TURNSTILE_LOGIN_FAILURE_THRESHOLD: int = Field(
        default=3,
        ge=1,
        le=100,
        description="同一登录标识连续失败达到该次数后，登录必须提交 Turnstile token。",
    )
    TURNSTILE_ALLOWED_HOSTNAMES: list[str] = Field(
        default_factory=list,
        description="可选。Siteverify 返回 hostname 时必须命中该白名单；为空则不校验 hostname。",
    )
    AUTH_TRUST_X_FORWARDED_FOR: bool = Field(
        default=False,
        description="为 True 时用 X-Forwarded-For 最左侧作为客户端 IP（仅置于受信反代之后开启）",
    )
    AUTH_REGISTRATION_REQUIRES_APPROVAL: bool = Field(
        default=True,
        description="为 True 时，公开注册用户默认未启用，需后台管理员审核启用后才能登录。",
    )
    AUTH_PASSWORD_RESET_TOKEN_TTL_SECONDS: int = Field(
        default=3600,
        ge=300,
        le=604_800,
        description="忘记密码邮件中重置令牌有效时长（秒），默认 1 小时。",
    )
    AUTH_PASSWORD_RESET_EMAIL_BACKEND: str = Field(
        default="noop",
        description="noop=仅落库不发信；log=INFO 记录含链接（仅开发/排障）；smtp=经 SMTP 发信（须同时配置 SMTP_* 与模板）。",
    )
    AUTH_PASSWORD_RESET_EMAIL_FROM: str | None = Field(
        default=None,
        description="SMTP 发信时的 From 地址；``AUTH_PASSWORD_RESET_EMAIL_BACKEND=smtp`` 时必填。",
    )
    AUTH_PASSWORD_RESET_PUBLIC_LINK_TEMPLATE: str = Field(
        default="",
        max_length=512,
        description="邮件正文中的重置链接模板，**必须**包含字面量 ``{token}``（例如前端页 `https://app.example/reset?token={token}`）。",
    )
    SMTP_HOST: str | None = Field(default=None, description="SMTP 主机；仅 ``AUTH_PASSWORD_RESET_EMAIL_BACKEND=smtp`` 时使用。")
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_USER: str | None = Field(default=None, description="SMTP 认证用户名；可留空表示无认证。")
    SMTP_PASSWORD: SecretStr | None = Field(default=None, description="SMTP 认证密码。")
    SMTP_USE_TLS: bool = Field(default=True, description="SMTP 是否使用 STARTTLS。")
    COMMENT_POST_MAX_PER_VIDEO_PER_MINUTE: int = Field(
        default=12,
        ge=0,
        le=10_000,
        description=(
            "同一用户对同一视频在滑动 60 秒内最多发表评论次数；0 关闭。"
            "若 ``COMMENT_RATE_LIMIT_USE_REDIS`` 且 Redis 可达，则多实例/多 worker 共享计数；"
            "否则回退进程内滑动窗口。"
        ),
    )
    COMMENT_RATE_LIMIT_USE_REDIS: bool = Field(
        default=True,
        description="为 True 且 Redis 可达时，评论发帖限流使用 Redis ZSET 滑动窗口（键前缀 rl:comment:post:v1:）。",
    )
    COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY: bool = Field(
        default=True,
        description="Redis 限流调用异常时是否回退进程内计数；生产若要求严格一致可关（将抛错，由上层处理）。",
    )

    EXPOSE_PROMETHEUS_METRICS: bool = Field(
        default=False,
        description="为 True 时挂载 ``GET /metrics``（Prometheus textformat）；仅受信网络或 sidecar 抓取时开启。",
    )
    METRICS_INSTANCE_ID: str | None = Field(
        default=None,
        max_length=256,
        description=(
            "可选；非空时写入评论指标 ``worker`` 标签，便于多副本/多进程抓取区分。"
            "为空时默认 ``pid_<进程号>``；Uvicorn 多 worker 时建议设为 ``HOSTNAME`` 或 K8s pod 名。"
        ),
    )

    @field_validator("METRICS_INSTANCE_ID", mode="before")
    @classmethod
    def empty_metrics_instance_id_none(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip() if isinstance(v, str) else v

    ALIYUN_ACCESS_KEY_ID: str | None = Field(
        default=None,
        description="阿里云 RAM 用户 AccessKey Id；仅服务端使用，勿下发前端。未设置则 VOD 上传凭证接口不可用。",
    )
    ALIYUN_ACCESS_KEY_SECRET: SecretStr | None = Field(
        default=None,
        description="阿里云 AccessKey Secret；使用 SecretStr，勿记录到日志。",
    )
    ALIYUN_VOD_REGION: str | None = Field(
        default=None,
        description="VOD 区域 id，如 cn-shanghai；用于拼接 endpoint ``vod.{region}.aliyuncs.com``。",
    )
    ALIYUN_VOD_TEMPLATE_GROUP_ID: str | None = Field(
        default=None,
        description="可选；CreateUploadVideo 的 TemplateGroupId。",
    )
    ALIYUN_VOD_WORKFLOW_ID: str | None = Field(
        default=None,
        description="可选；CreateUploadVideo 的 WorkflowId。",
    )
    ALIYUN_VOD_PLAY_AUTH_TIMEOUT_SECONDS: int | None = Field(
        default=3_000,
        ge=60,
        le=2_592_000,
        description=(
            "可选；GetVideoPlayAuth 的 AuthInfoTimeout（秒），即 PlayAuth 有效时长上限。"
            "为空则不传该参数，由阿里云使用默认 TTL。"
        ),
    )
    ALIYUN_VOD_CALLBACK_SECRET: SecretStr | None = Field(
        default=None,
        description=(
            "VOD HTTP 回调鉴权：请求头 ``X-VOD-Callback-Secret`` 须与本密钥一致；"
            "未配置则回调接口返回 503。后续可叠加 HMAC 签名（见 vod_callback_service）。"
        ),
    )

    MAX_VIDEO_SIZE_MB: int = Field(
        default=2048,
        ge=1,
        le=50_000,
        description="上传前校验：客户端声明的媒资文件大小不得超过该值（MB）。",
    )
    LOCAL_VIDEO_STORAGE_DIR: str = Field(
        default="data/local_videos",
        description="本站直接存储的成片目录（相对进程工作目录或绝对路径）；须仅服务端可写。",
    )
    LOCAL_VIDEO_PLAY_TOKEN_SECONDS: int = Field(
        default=7200,
        ge=300,
        le=86400 * 7,
        description="本机流式播放 URL 中 query token 的有效期（秒）；到期后需重新请求 GET …/play。",
    )
    VIDEO_COVER_STORAGE_DIR: str = Field(
        default="data/video_covers",
        min_length=1,
        max_length=1024,
        description="稿件封面 JPEG 落盘目录；相对路径相对进程工作目录。",
    )
    VIDEO_COVER_MAX_UPLOAD_MB: int = Field(
        default=8,
        ge=1,
        le=50,
        description="单张封面上传上限（MB）；须为 JPEG。",
    )
    API_PUBLIC_BASE_URL: str | None = Field(
        default=None,
        max_length=2048,
        description=(
            "可选。生成本机播放绝对 URL 时使用（须含 ``/api/v1`` 前缀且无尾部斜杠），"
            "例如 ``https://api.example.com/api/v1``；浏览器页与 API 不同源且无法依赖反向代理路径时配置。"
        ),
    )
    ALLOWED_VIDEO_EXTENSIONS: str = Field(
        default="mp4,mov,mkv,webm",
        description="逗号分隔扩展名（可带或不带 ``.``），用于视频文件名 / 源文件名白名单。",
    )
    ALLOWED_COVER_EXTENSIONS: str = Field(
        default="jpg,jpeg,png,webp",
        description="逗号分隔；用于从封面 URL 路径解析出的扩展名白名单。",
    )
    MAX_VIDEO_TITLE_LENGTH: int = Field(
        default=255,
        ge=1,
        le=512,
        description="创建/更新视频与 VOD 上传凭证请求中标题的最大字符数。",
    )
    MAX_VIDEO_DESCRIPTION_LENGTH: int = Field(
        default=10_000,
        ge=0,
        le=200_000,
        description="描述最大字符数；0 表示仅允许省略或空描述。",
    )
    VIDEO_UPLOAD_MAX_PER_USER_PER_DAY: int = Field(
        default=0,
        ge=0,
        le=10_000,
        description="普通用户每 UTC 自然日最多成功占位获取 VOD 上传凭证的次数；0 关闭。管理员不受限。",
    )
    VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS: bool = Field(
        default=True,
        description="为 True 且 Redis 可达时，日上传计数使用 Redis INCR（键前缀 rl:upload:vod:day:v1:）。",
    )
    VIDEO_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY: bool = Field(
        default=True,
        description="Redis 计数失败时是否回退进程内按日计数；生产若要求强一致可关（将返回 503）。",
    )
    VOD_REFRESH_UPLOAD_MAX_PER_USER_PER_MINUTE: int = Field(
        default=60,
        ge=0,
        le=10_000,
        description=(
            "同一用户每 60 秒滑动窗口内最多调用几次 ``POST …/refresh-upload-video``；"
            "**0** 关闭。管理员不受此限。"
            " 若 ``VOD_REFRESH_UPLOAD_RATE_LIMIT_USE_REDIS`` 且 Redis 可达则多实例共享计数（键前缀 rl:vod:refresh:v1:）。"
        ),
    )
    VOD_REFRESH_UPLOAD_RATE_LIMIT_USE_REDIS: bool = Field(
        default=True,
        description="为 True 且 Redis 可达时，VOD 刷新上传凭证限流使用 Redis ZSET 滑动窗口。",
    )
    VOD_REFRESH_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY: bool = Field(
        default=True,
        description="Redis 限流失败时是否回退进程内计数；生产若要求严格一致可关（将返回 503）。",
    )

    ATTACHMENT_STORAGE_DIR: str = Field(
        default="data/attachments",
        min_length=1,
        max_length=1024,
        description="稿件附属文件（图片/PDF/Office 等）落盘目录；相对路径相对进程工作目录。",
    )
    MAX_ATTACHMENT_SIZE_MB: int = Field(
        default=50,
        ge=1,
        le=500,
        description="单附件最大字节数上限（MB）。",
    )
    MAX_ATTACHMENTS_PER_VIDEO: int = Field(
        default=20,
        ge=1,
        le=200,
        description="单条稿件最多附属文件条数。",
    )
    ALLOWED_ATTACHMENT_EXTENSIONS: str = Field(
        default="jpg,jpeg,png,webp,gif,bmp,pdf,doc,docx,xls,xlsx,ppt,pptx,txt,zip",
        description="逗号分隔扩展名；用于 ``POST /videos/{id}/attachments`` 白名单。",
    )
    ATTACHMENT_VERIFY_FILE_MAGIC: bool = Field(
        default=True,
        description=(
            "为 True 时，附件落盘后按文件头魔数与扩展名交叉校验（``UPLOAD_ATTACHMENT_MAGIC_MISMATCH``）；"
            "排查兼容问题时可临时关闭。"
        ),
    )
    ATTACHMENT_MIN_RESERVED_DISK_MB: int = Field(
        default=256,
        ge=0,
        le=1_000_000,
        description=(
            "附件落盘前检查存储卷：剩余空间须 ≥ 本值（MB）+ 单附件上限字节；**0** 关闭。"
            "避免写满系统盘导致 API 与健康检查一并失败。"
        ),
    )
    ATTACHMENT_POST_MAX_PER_USER_PER_MINUTE: int = Field(
        default=60,
        ge=0,
        le=10_000,
        description=(
            "同一用户每 60 秒滑动窗口内最多发起几次附件上传；**0** 关闭。"
            " 若 ``ATTACHMENT_POST_RATE_LIMIT_USE_REDIS`` 且 Redis 可达则多实例共享计数（键前缀 rl:attachment:post:v1:）。"
        ),
    )
    ATTACHMENT_POST_RATE_LIMIT_USE_REDIS: bool = Field(
        default=True,
        description="为 True 且 Redis 可达时，附件上传限流使用 Redis ZSET 滑动窗口。",
    )
    ATTACHMENT_POST_RATE_LIMIT_REDIS_FALLBACK_MEMORY: bool = Field(
        default=True,
        description="Redis 限流失败时是否回退进程内计数；生产若要求严格一致可关（将返回 503）。",
    )

    VIDEO_SEARCH_KEYWORD_MAX_LENGTH: int = Field(
        default=200,
        ge=8,
        le=512,
        description=(
            "``GET /search/videos`` 关键词（trim 后）最大字符数；超长由接口返回 400。"
            "过大 ILIKE 易拖慢库，运营侧建议 80–200。"
        ),
    )
    VIDEO_TRENDING_WEIGHT_VIEWS: int = Field(
        default=1,
        ge=0,
        le=50_000,
        description="热门榜线性热度分：``views_count`` 系数（三项权重之和须 >0）。",
    )
    VIDEO_TRENDING_WEIGHT_LIKES: int = Field(
        default=4,
        ge=0,
        le=50_000,
        description="热门榜：``likes_count`` 系数。",
    )
    VIDEO_TRENDING_WEIGHT_FAVORITES: int = Field(
        default=6,
        ge=0,
        le=50_000,
        description="热门榜：``favorites_count`` 系数。",
    )
    VIDEO_TRENDING_RECENCY_HALF_LIFE_DAYS: float = Field(
        default=0.0,
        ge=0.0,
        le=3650.0,
        description=(
            "热门榜时间衰减：按 ``coalesce(published_at, created_at)`` 起算「距今天数」；"
            "有效分 = 线性热度 × ``1 / (1 + age_days / half_life)``。**0** 关闭（仅按热度权重排序）。"
        ),
    )
    VIDEO_SEARCH_MAX_REQUESTS_PER_MINUTE: int = Field(
        default=0,
        ge=0,
        le=10_000,
        description=(
            "``GET /search/videos`` 每客户端 IP 每 60 秒滑动窗口最大请求数；**0** 关闭。"
            "进程内计数（多 worker 不共享）；高流量可后续换 Redis。"
        ),
    )

    @model_validator(mode="after")
    def trending_score_weights_sum_positive(self) -> Self:
        t = (
            int(self.VIDEO_TRENDING_WEIGHT_VIEWS)
            + int(self.VIDEO_TRENDING_WEIGHT_LIKES)
            + int(self.VIDEO_TRENDING_WEIGHT_FAVORITES)
        )
        if t <= 0:
            raise ValueError(
                "VIDEO_TRENDING_WEIGHT_VIEWS + VIDEO_TRENDING_WEIGHT_LIKES + VIDEO_TRENDING_WEIGHT_FAVORITES 须大于 0"
            )
        return self

    @model_validator(mode="after")
    def auth_rate_limit_register_windows_coherent(self) -> Self:
        if self.AUTH_RATE_LIMIT_REGISTER_HOUR_WINDOW_SECONDS < self.AUTH_RATE_LIMIT_REGISTER_MINUTE_WINDOW_SECONDS:
            raise ValueError(
                "AUTH_RATE_LIMIT_REGISTER_HOUR_WINDOW_SECONDS 须大于等于 AUTH_RATE_LIMIT_REGISTER_MINUTE_WINDOW_SECONDS"
            )
        return self

    @model_validator(mode="after")
    def turnstile_bypass_only_in_node_test(self) -> Self:
        if self.TURNSTILE_BYPASS and (self.NODE_ENV or "").strip().lower() != "test":
            raise ValueError("TURNSTILE_BYPASS=true 仅允许在 NODE_ENV=test 时使用")
        return self

    @field_validator("REFRESH_TOKEN_COOKIE_SAMESITE", mode="before")
    @classmethod
    def normalize_refresh_cookie_samesite(cls, v: Any) -> Any:
        s = "lax" if v is None else str(v).strip().lower()
        if s not in {"lax", "strict", "none"}:
            raise ValueError("REFRESH_TOKEN_COOKIE_SAMESITE 须为 lax、strict 或 none")
        return s

    @model_validator(mode="after")
    def secure_refresh_cookie_in_production_like(self) -> Self:
        e = self.ENVIRONMENT.strip().lower()
        if e in ("production", "prod", "staging") and not self.REFRESH_TOKEN_COOKIE_SECURE:
            raise ValueError("生产类环境必须设置 REFRESH_TOKEN_COOKIE_SECURE=true")
        if self.REFRESH_TOKEN_COOKIE_SAMESITE == "none" and not self.REFRESH_TOKEN_COOKIE_SECURE:
            raise ValueError("SameSite=None 必须配合 REFRESH_TOKEN_COOKIE_SECURE=true")
        return self

    @field_validator("TURNSTILE_SECRET", mode="before")
    @classmethod
    def empty_turnstile_secret_none(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("NODE_ENV", mode="before")
    @classmethod
    def normalize_node_env(cls, v: Any) -> Any:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip().lower()
        return str(v).strip().lower()

    @field_validator("TURNSTILE_ALLOWED_HOSTNAMES", mode="before")
    @classmethod
    def parse_turnstile_allowed_hostnames(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            return [p.strip().lower() for p in s.split(",") if p.strip()]
        if isinstance(v, (list, tuple)):
            return [str(x).strip().lower() for x in v if str(x).strip()]
        raise ValueError("TURNSTILE_ALLOWED_HOSTNAMES 须为逗号分隔字符串或字符串列表")

    @model_validator(mode="after")
    def password_reset_smtp_requires_host_from_and_template(self) -> Self:
        b = (self.AUTH_PASSWORD_RESET_EMAIL_BACKEND or "noop").strip().lower()
        if b == "smtp":
            if not (self.SMTP_HOST or "").strip():
                raise ValueError("AUTH_PASSWORD_RESET_EMAIL_BACKEND=smtp 时必须配置 SMTP_HOST")
            if not (self.AUTH_PASSWORD_RESET_EMAIL_FROM or "").strip():
                raise ValueError("AUTH_PASSWORD_RESET_EMAIL_BACKEND=smtp 时必须配置 AUTH_PASSWORD_RESET_EMAIL_FROM")
            tpl = (self.AUTH_PASSWORD_RESET_PUBLIC_LINK_TEMPLATE or "").strip()
            if "{token}" not in tpl:
                raise ValueError("smtp 发信时 AUTH_PASSWORD_RESET_PUBLIC_LINK_TEMPLATE 必须包含字面量 {token}")
        return self

    @field_validator("AUTH_PASSWORD_RESET_EMAIL_BACKEND", mode="before")
    @classmethod
    def normalize_password_reset_email_backend(cls, v: Any) -> Any:
        if v is None:
            return "noop"
        if isinstance(v, str):
            s = v.strip().lower()
            return s or "noop"
        return v

    @field_validator("AUTH_PASSWORD_RESET_EMAIL_FROM", mode="before")
    @classmethod
    def empty_password_reset_from_none(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    @field_validator("AUTH_PASSWORD_RESET_PUBLIC_LINK_TEMPLATE", mode="before")
    @classmethod
    def strip_password_reset_link_template(cls, v: Any) -> Any:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("ALIYUN_VOD_TEMPLATE_GROUP_ID", "ALIYUN_VOD_WORKFLOW_ID", mode="before")
    @classmethod
    def strip_optional_vod_template_workflow(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("ALIYUN_ACCESS_KEY_ID", "ALIYUN_VOD_REGION", mode="before")
    @classmethod
    def strip_optional_aliyun_str(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("ALLOWED_VIDEO_EXTENSIONS", "ALLOWED_COVER_EXTENSIONS", mode="before")
    @classmethod
    def strip_allowed_ext_lists_nonempty(cls, v: Any) -> Any:
        if v is None or not isinstance(v, str):
            return v
        s = v.strip()
        if not s:
            raise ValueError("扩展名白名单不能为空")
        return s

    FIRST_SUPERUSER_EMAIL: EmailStr | None = None
    FIRST_SUPERUSER_USERNAME: str | None = None
    FIRST_SUPERUSER_PASSWORD: SecretStr | None = Field(
        default=None,
        description="首个管理员明文密码；仅启动 init_db 使用，勿记录到日志",
    )

    @field_validator("FIRST_SUPERUSER_EMAIL", mode="before")
    @classmethod
    def empty_email_none(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip().lower()

    @field_validator("FIRST_SUPERUSER_USERNAME", mode="before")
    @classmethod
    def empty_username_none(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    @field_validator("FIRST_SUPERUSER_PASSWORD", mode="before")
    @classmethod
    def superuser_password(cls, v: Any, info: ValidationInfo) -> str | None:
        if v is None:
            return None
        if isinstance(v, SecretStr):
            plain = v.get_secret_value()
        else:
            plain = str(v)
        plain = plain.strip()
        if not plain:
            return None
        if len(plain) < 8:
            raise ValueError("FIRST_SUPERUSER_PASSWORD 若设置，长度至少 8（与注册用户密码策略一致）")
        if len(plain.encode("utf-8")) > 72:
            raise ValueError(
                "FIRST_SUPERUSER_PASSWORD UTF-8 长度不得超过 72 字节（bcrypt 与注册用户策略一致）。"
            )
        env = (info.data.get("ENVIRONMENT") or "local")
        if isinstance(env, str):
            env = env.strip().lower()
        else:
            env = str(env).strip().lower()
        if env in ("production", "prod", "staging"):
            weak = frozenset(
                {
                    "changeme",
                    "password",
                    "admin",
                    "12345678",
                    "qwerty123",
                }
            )
            if plain.lower() in weak:
                raise ValueError(
                    "生产类环境下 FIRST_SUPERUSER_PASSWORD 过于简单，请使用强密码。"
                )
        return plain

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def secret_key_entropy(cls, v: Any, info: ValidationInfo) -> str:
        if isinstance(v, SecretStr):
            plain = v.get_secret_value()
        elif isinstance(v, (bytes, bytearray)):
            plain = v.decode("utf-8")
        else:
            plain = str(v)
        plain = plain.strip()
        raw = plain.encode("utf-8")
        if len(raw) < 32:
            raise ValueError(
                "SECRET_KEY 过短：UTF-8 编码须至少 32 字节（HS256 常见下限）。"
                "生成示例：openssl rand -hex 32"
            )
        s = plain.lower()
        insecure_exact = frozenset(
            {
                "changeme",
                "secret",
                "password",
                "test",
                "your-secret-key",
                "your-secret-key-here",
                # 历史 compose 内联弱默认（已移除）；任何环境禁止再使用
                "dev-insecure-change-me-use-openssl-rand-hex-32-in-prod-env!!",
            }
        )
        if s in insecure_exact:
            raise ValueError("SECRET_KEY 过于常见或为已废弃的弱默认，请使用高熵随机串（如 openssl rand -hex 32）。")
        env = (info.data.get("ENVIRONMENT") or "local")
        if isinstance(env, str):
            env = env.strip().lower()
        else:
            env = str(env).strip().lower()
        if env in ("production", "prod", "staging") and len(raw) < 48:
            raise ValueError(
                "当前 ENVIRONMENT 为生产类环境：建议 SECRET_KEY UTF-8 长度至少 48 字节。"
            )
        _banned_in_deploy = frozenset(
            {
                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "unit-test-environment-default-secret-48b-min-ok!!",
            }
        )
        if env in ("production", "prod", "staging") and plain in _banned_in_deploy:
            raise ValueError(
                "生产类环境禁止使用文档/单测中的示例或默认 SECRET_KEY；请使用独立高熵密钥（如 openssl rand -hex 32）。"
            )
        return plain

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Any:
        if v is None:
            return ["*"]
        if isinstance(v, str):
            s = v.strip()
            if not s or s == "*":
                return ["*"]
            return [p.strip() for p in s.split(",") if p.strip()]
        if isinstance(v, (list, tuple)):
            out = [str(x).strip() for x in v if str(x).strip()]
            return out if out else ["*"]
        raise ValueError("CORS_ORIGINS 须为逗号分隔字符串或字符串列表")

    @field_validator("JWT_SIGNING_KEYS", mode="before")
    @classmethod
    def validate_jwt_signing_keys_shape(cls, v: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("JWT_SIGNING_KEYS 须为字符串")
        s = v.strip()
        if not s:
            return None
        if s.startswith("{"):
            try:
                data = json.loads(s)
            except json.JSONDecodeError as e:
                raise ValueError("JWT_SIGNING_KEYS JSON 格式无效") from e
            keys = data.get("keys")
            if not isinstance(keys, list) or not keys:
                raise ValueError("JWT_SIGNING_KEYS JSON 须包含非空 keys 数组")
            for item in keys:
                if not isinstance(item, dict) or not item.get("kid") or not item.get("secret"):
                    raise ValueError("JWT_SIGNING_KEYS 每个 key 须包含 kid 与 secret")
                if len(str(item["secret"]).encode("utf-8")) < 32:
                    raise ValueError("JWT_SIGNING_KEYS 中每个 secret UTF-8 编码须至少 32 字节")
            return s
        for part in s.split(","):
            if ":" not in part:
                raise ValueError("JWT_SIGNING_KEYS 兼容格式须为 kid:secret,kid2:secret")
            kid, secret = part.split(":", 1)
            if not kid.strip() or len(secret.strip().encode("utf-8")) < 32:
                raise ValueError("JWT_SIGNING_KEYS 兼容格式中 kid 不能为空，secret 至少 32 字节")
        return s

    @model_validator(mode="after")
    def cors_tighten_in_production_like(self) -> Self:
        e = self.ENVIRONMENT.strip().lower()
        if e not in ("production", "prod", "staging"):
            return self
        if not self.CORS_ORIGINS:
            raise ValueError("生产类环境下 CORS_ORIGINS 不能为空，请列出允许的前端 Origin。")
        if any(o == "*" for o in self.CORS_ORIGINS):
            raise ValueError(
                "生产类环境禁止使用 CORS_ORIGINS='*'：请显式列出前端来源（逗号分隔多个 Origin）。"
            )
        return self

    @model_validator(mode="after")
    def reject_default_postgres_password_in_production_like(self) -> Self:
        """生产类环境禁止数据库用户 postgres 仍使用口令 postgres（常见弱默认）。"""
        e = self.ENVIRONMENT.strip().lower()
        if e not in ("production", "prod", "staging"):
            return self
        url = self.DATABASE_URL
        if re.search(r"postgresql(\+psycopg)?://postgres:postgres@", url):
            raise ValueError(
                "生产类环境禁止使用默认数据库口令 postgres（请为数据库用户使用独立强口令并同步更新 DATABASE_URL）。"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expose_openapi_docs(self) -> bool:
        """是否挂载 Swagger/ReDoc/OpenAPI JSON。

        默认在生产类环境关闭以降低信息泄露；可通过 EXPOSE_OPENAPI_DOCS 强制开关。
        """
        if self.EXPOSE_OPENAPI_DOCS is not None:
            return self.EXPOSE_OPENAPI_DOCS
        e = self.ENVIRONMENT.strip().lower()
        return e not in ("production", "prod", "staging")


settings = Settings()
