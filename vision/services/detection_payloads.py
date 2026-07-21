from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from vision.models import FeedDetectionState, VideoFeed


def state_payload(state: FeedDetectionState | None) -> dict:
    if state is None:
        return {
            "has_detection": False,
            "stable_counts": {},
            "current_counts": {},
            "boxes": [],
            "frame_number": 0,
            "inference_ms": 0,
            "updated_at": None,
            "is_active": False,
        }

    is_active = state.updated_at >= timezone.now() - timedelta(
        seconds=settings.YOLO_STATE_STALE_SECONDS
    )
    return {
        "has_detection": True,
        "stable_counts": state.stable_counts,
        "current_counts": state.current_counts,
        "boxes": state.boxes,
        "frame_number": state.frame_number,
        "inference_ms": state.inference_ms,
        "updated_at": state.updated_at.isoformat(),
        "is_active": is_active,
    }


def dashboard_payload() -> dict:
    totals: Counter[str] = Counter()
    feed_summaries = []

    states_by_feed = {
        state.feed_id: state
        for state in FeedDetectionState.objects.select_related("feed").all()
    }
    for feed in VideoFeed.objects.all():
        payload = state_payload(states_by_feed.get(feed.pk))
        if payload["is_active"]:
            totals.update(payload["stable_counts"])
        feed_summaries.append(
            {
                "id": feed.pk,
                "name": str(feed),
                "connection_host": feed.connection_host,
                "detail_url": reverse("vision:video_feed_detail", args=(feed.pk,)),
                **payload,
            }
        )

    return {
        "total_objects": sum(totals.values()),
        "stable_counts": dict(sorted(totals.items())),
        "feeds": feed_summaries,
    }
