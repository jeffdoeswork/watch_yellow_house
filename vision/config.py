from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError


@dataclass(frozen=True, slots=True)
class YoloConfig:
    model: str
    source: str | int
    device: str
    image_size: int
    confidence: float
    frame_stride: int
    quantize: int | str | None

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> "YoloConfig":
        source = options.get("source") or settings.YOLO_SOURCE
        if source is None:
            source = _database_source(options.get("feed_id"))

        model = options.get("model") or settings.YOLO_MODEL
        return cls(
            model=_resolve_model_path(model),
            source=_normalize_source(source),
            device=options.get("device") or settings.YOLO_DEVICE,
            image_size=options.get("image_size") or settings.YOLO_IMAGE_SIZE,
            confidence=_option_or_setting(
                options.get("confidence"), settings.YOLO_CONFIDENCE
            ),
            frame_stride=options.get("frame_stride") or settings.YOLO_FRAME_STRIDE,
            quantize=_normalize_quantize(settings.YOLO_QUANTIZE),
        )


def _normalize_source(source: str | int) -> str | int:
    if isinstance(source, int):
        return source
    value = str(source).strip()
    return int(value) if value.isdigit() else value


def _database_source(feed_id: int | None) -> str:
    from vision.models import VideoFeed

    feeds = VideoFeed.objects.all()
    if feed_id is not None:
        feeds = feeds.filter(pk=feed_id)
    feed = feeds.first()
    if feed is None:
        if feed_id is not None:
            raise CommandError(f"Video Feed #{feed_id} does not exist.")
        raise CommandError(
            "No stream source configured. Add a Video Feed in admin, pass --source, "
            "or set YOLO_SOURCE."
        )
    return feed.rtsp_url


def _resolve_model_path(model: str | Path) -> str:
    path = Path(model)
    if not path.is_absolute():
        path = settings.BASE_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _normalize_quantize(value: str | int | None) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    normalized = value.strip().lower()
    if normalized in {"", "none", "false", "off"}:
        return None
    return int(normalized) if normalized.isdigit() else normalized


def _option_or_setting(option: Any, setting: Any) -> Any:
    return setting if option is None else option
