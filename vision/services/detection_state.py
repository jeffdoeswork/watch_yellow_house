from collections import Counter, deque
from collections.abc import Iterable, Mapping
from typing import Any

from django.conf import settings

from vision.models import FeedDetectionState


def detection_counts(result) -> dict[str, int]:
    """Return integral per-class counts from one Ultralytics result."""
    counts: dict[str, int] = {}
    if result.boxes is None:
        return counts

    for class_id in result.boxes.cls.int().cpu().tolist():
        class_name = str(result.names[class_id])
        counts[class_name] = counts.get(class_name, 0) + 1
    return counts


def stabilized_counts(
    history: Iterable[Mapping[str, int]],
    previous_counts: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """Take each class's mode and keep the prior value while it remains tied."""
    frames = list(history)
    previous_counts = previous_counts or {}
    class_names = sorted({name for frame in frames for name in frame})
    stable: dict[str, int] = {}

    for class_name in class_names:
        values = [int(frame.get(class_name, 0)) for frame in frames]
        frequencies = Counter(values)
        highest_frequency = max(frequencies.values())
        tied_values = {
            value
            for value, frequency in frequencies.items()
            if frequency == highest_frequency
        }
        previous = previous_counts.get(class_name)
        selected = (
            previous
            if previous in tied_values
            else next(value for value in reversed(values) if value in tied_values)
        )
        if selected > 0:
            stable[class_name] = selected

    return stable


def detection_boxes(result) -> list[dict[str, Any]]:
    """Normalize the latest boxes so any browser-sized player can draw them."""
    if result.boxes is None:
        return []

    height, width = result.orig_shape[:2]
    if not height or not width:
        return []

    coordinates = result.boxes.xyxy.cpu().tolist()
    class_ids = result.boxes.cls.int().cpu().tolist()
    confidences = result.boxes.conf.cpu().tolist()
    boxes = []

    for xyxy, class_id, confidence in zip(
        coordinates, class_ids, confidences, strict=True
    ):
        x1, y1, x2, y2 = xyxy
        boxes.append(
            {
                "class_name": str(result.names[class_id]),
                "confidence": round(float(confidence), 4),
                "x1": _unit_value(x1 / width),
                "y1": _unit_value(y1 / height),
                "x2": _unit_value(x2 / width),
                "y2": _unit_value(y2 / height),
            }
        )
    return boxes


class DetectionStateRecorder:
    """Maintain a short in-memory window and publish one state row per feed."""

    def __init__(self, feed_id: int, window_size: int | None = None):
        self.feed_id = feed_id
        self.window_size = window_size or settings.YOLO_COUNT_WINDOW
        previous_state = (
            FeedDetectionState.objects.filter(feed_id=feed_id)
            .values("count_history", "stable_counts")
            .first()
            or {}
        )
        previous_history = previous_state.get("count_history", [])
        self.stable_counts = previous_state.get("stable_counts", {})
        self.history = deque(
            previous_history[-self.window_size :], maxlen=self.window_size
        )

    def record(self, frame_number: int, result) -> None:
        current_counts = detection_counts(result)
        self.history.append(current_counts)
        self.stable_counts = stabilized_counts(self.history, self.stable_counts)
        FeedDetectionState.objects.update_or_create(
            feed_id=self.feed_id,
            defaults={
                "count_history": list(self.history),
                "stable_counts": self.stable_counts,
                "current_counts": current_counts,
                "boxes": detection_boxes(result),
                "frame_number": frame_number,
                "inference_ms": round(float(result.speed.get("inference", 0.0)), 2),
                "worker_status": FeedDetectionState.WorkerStatus.DETECTING,
            },
        )


def _unit_value(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 6)
