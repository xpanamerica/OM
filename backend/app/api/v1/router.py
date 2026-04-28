from fastapi import APIRouter

from app.api.v1 import (
    admin_management,
    ai_jobs,
    auth,
    categories,
    concepts,
    direct_messages,
    learning_paths,
    search,
    tags,
    user_notifications,
    users,
    video_comments,
    video_covers,
    video_interactions,
    video_workflow,
    video_attachments,
    videos,
    view_records,
    video_ai_jobs,
    video_concepts,
    vod_uploads,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_management.router, prefix="/admin", tags=["admin"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(user_notifications.router, prefix="/users", tags=["notifications"])
api_router.include_router(direct_messages.router, prefix="/direct-messages", tags=["direct-messages"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(concepts.router, prefix="/concepts", tags=["knowledge"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(video_covers.router, tags=["covers"])
api_router.include_router(video_workflow.router, prefix="/videos", tags=["videos"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(video_attachments.router, prefix="/videos", tags=["videos", "attachments"])
api_router.include_router(video_ai_jobs.router, prefix="/videos", tags=["ai-jobs"])
api_router.include_router(video_concepts.router, prefix="/videos", tags=["knowledge"])
api_router.include_router(learning_paths.router, prefix="/learning-paths", tags=["knowledge"])
api_router.include_router(video_interactions.router, prefix="/videos", tags=["video-interactions"])
api_router.include_router(view_records.videos_router, prefix="/videos", tags=["view-records"])
api_router.include_router(view_records.users_router, prefix="/users", tags=["view-records"])
api_router.include_router(video_comments.router, prefix="/videos", tags=["comments"])
api_router.include_router(video_comments.comments_root_router, prefix="/comments", tags=["comments"])
api_router.include_router(vod_uploads.router, prefix="/uploads", tags=["uploads", "vod"])
api_router.include_router(ai_jobs.router, prefix="/ai-jobs", tags=["ai-jobs"])
