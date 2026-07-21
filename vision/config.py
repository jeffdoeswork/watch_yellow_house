from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError


@dataclass(frozen=True, slots=True)
class YoloRuntimeConfig:
    model: str
    device: str
    image_size: int
    confidence: float
    frame_stride: int
    quantize: int | str | None

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> "YoloRuntimeConfig":
        model = options.get("model") or settings.YOLO_MODEL
        return cls(
            model=_resolve_model_path(model),
            device=options.get("device") or settings.YOLO_DEVICE,
            image_size=options.get("image_size") or settings.YOLO_IMAGE_SIZE,
            confidence=_option_or_setting(
                options.get("confidence"), settings.YOLO_CONFIDENCE
            ),
            frame_stride=options.get("frame_stride") or settings.YOLO_FRAME_STRIDE,
            quantize=_normalize_quantize(settings.YOLO_QUANTIZE),
        )


@dataclass(frozen=True, slots=True)
class YoloConfig(YoloRuntimeConfig):
    source: str | int
    feed_id: int | None

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> "YoloConfig":
        source = options.get("source") or settings.YOLO_SOURCE
        feed_id = options.get("feed_id")
        if source is None:
            feed_id, source = _database_source(feed_id)

        runtime = YoloRuntimeConfig.from_options(options)
        return cls(
            model=runtime.model,
            device=runtime.device,
            image_size=runtime.image_size,
            confidence=runtime.confidence,
            frame_stride=runtime.frame_stride,
            quantize=runtime.quantize,
            source=_normalize_source(source),
            feed_id=feed_id,
        )


def _normalize_source(source: str | int) -> str | int:
    if isinstance(source, int):
        return source
    value = str(source).strip()
    return int(value) if value.isdigit() else value


def _database_source(feed_id: int | None) -> tuple[int, str]:
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
    return feed.pk, feed.rtsp_url


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
