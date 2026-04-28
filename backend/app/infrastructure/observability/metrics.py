"""应用指标：启动时预热模块（评论域为进程内 Counter，见 ``comment_metrics``）。"""


def setup_metrics() -> None:
    """导入各域指标模块，确保 import 侧效应与类型检查器可见。"""
    from app.infrastructure.observability import (  # noqa: F401
        comment_metrics,
        upload_flow_metrics,
        view_record_metrics,
    )

    _ = comment_metrics.render_comment_metrics_prometheus_text
    _ = view_record_metrics.render_view_record_metrics_prometheus_text
    _ = upload_flow_metrics.render_upload_flow_metrics_prometheus_text
