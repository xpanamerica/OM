"""领域规则：工作流 POST 边与 PATCH 状态约束（无 DB）。"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.core.video_codes import (
    VIDEO_APPROVE_INVALID_STATE,
    VIDEO_OFFLINE_INVALID_STATE,
    VIDEO_PATCH_ADMIN_OFFLINE_USE_ENDPOINT,
    VIDEO_PATCH_STATUS_USE_DEDICATED_ENDPOINT,
    VIDEO_REJECT_INVALID_STATE,
    VIDEO_STATUS_TRANSITION_INVALID,
    VIDEO_SUBMIT_INVALID_STATE,
)
from app.domain.video_workflow_rules import (
    WorkflowPostKind,
    assert_patch_status_change_allowed,
    assert_workflow_post_source_status,
    workflow_post_target,
)
from app.models.enums import UserRole, VideoStatus


@pytest.mark.parametrize(
    ("kind", "current", "expect_code"),
    [
        (WorkflowPostKind.SUBMIT_REVIEW, VideoStatus.PENDING_REVIEW, VIDEO_SUBMIT_INVALID_STATE),
        (WorkflowPostKind.APPROVE, VideoStatus.DRAFT, VIDEO_APPROVE_INVALID_STATE),
        (WorkflowPostKind.REJECT, VideoStatus.PUBLISHED, VIDEO_REJECT_INVALID_STATE),
        (WorkflowPostKind.OFFLINE_ADMIN, VideoStatus.DRAFT, VIDEO_OFFLINE_INVALID_STATE),
    ],
)
def test_workflow_post_rejects_wrong_source(kind: WorkflowPostKind, current: VideoStatus, expect_code: str):
    with pytest.raises(AppError) as ei:
        assert_workflow_post_source_status(kind, current)
    assert ei.value.status_code == 400
    assert ei.value.code == expect_code


def test_workflow_post_accepts_valid_sources():
    assert_workflow_post_source_status(WorkflowPostKind.SUBMIT_REVIEW, VideoStatus.DRAFT)
    assert_workflow_post_source_status(WorkflowPostKind.APPROVE, VideoStatus.PENDING_REVIEW)
    assert_workflow_post_source_status(WorkflowPostKind.REJECT, VideoStatus.PENDING_REVIEW)
    assert_workflow_post_source_status(WorkflowPostKind.OFFLINE_ADMIN, VideoStatus.PUBLISHED)


def test_workflow_post_targets_match_phase82():
    assert workflow_post_target(WorkflowPostKind.SUBMIT_REVIEW) == VideoStatus.PENDING_REVIEW
    assert workflow_post_target(WorkflowPostKind.APPROVE) == VideoStatus.PUBLISHED
    assert workflow_post_target(WorkflowPostKind.REJECT) == VideoStatus.REJECTED
    assert workflow_post_target(WorkflowPostKind.OFFLINE_ADMIN) == VideoStatus.OFFLINE


def test_patch_noop_same_status():
    assert_patch_status_change_allowed(VideoStatus.DRAFT, VideoStatus.DRAFT, UserRole.ADMIN) is None


def test_patch_admin_rejected_to_draft_ok():
    assert_patch_status_change_allowed(VideoStatus.REJECTED, VideoStatus.DRAFT, UserRole.ADMIN) is None


def test_patch_author_published_to_offline_ok():
    assert_patch_status_change_allowed(VideoStatus.PUBLISHED, VideoStatus.OFFLINE, UserRole.USER) is None


def test_patch_dedicated_edges_use_post():
    with pytest.raises(AppError) as ei:
        assert_patch_status_change_allowed(VideoStatus.DRAFT, VideoStatus.PENDING_REVIEW, UserRole.USER)
    assert ei.value.code == VIDEO_PATCH_STATUS_USE_DEDICATED_ENDPOINT


def test_patch_admin_platform_offline_must_use_post():
    with pytest.raises(AppError) as ei:
        assert_patch_status_change_allowed(VideoStatus.PUBLISHED, VideoStatus.OFFLINE, UserRole.ADMIN)
    assert ei.value.code == VIDEO_PATCH_ADMIN_OFFLINE_USE_ENDPOINT


def test_patch_author_illegal_transition():
    with pytest.raises(AppError) as ei:
        assert_patch_status_change_allowed(VideoStatus.DRAFT, VideoStatus.PUBLISHED, UserRole.USER)
    assert ei.value.code == VIDEO_STATUS_TRANSITION_INVALID
