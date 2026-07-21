from __future__ import annotations

import os
import tempfile
from pathlib import Path

from django.conf import settings


def preview_path(feed_id: int, root: Path | None = None) -> Path:
    preview_root = Path(root or settings.YOLO_PREVIEW_ROOT)
    return preview_root / f"feed-{int(feed_id)}.jpg"


class PreviewPublisher:
    """Render and atomically publish a bounded JPEG from a YOLO result."""

    def __init__(
        self,
        root: Path | None = None,
        width: int | None = None,
        jpeg_quality: int | None = None,
    ):
        self.root = Path(root or settings.YOLO_PREVIEW_ROOT)
        self.width = width or settings.YOLO_PREVIEW_WIDTH
        self.jpeg_quality = jpeg_quality or settings.YOLO_PREVIEW_JPEG_QUALITY
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, feed_id: int, result) -> Path:
        import cv2

        image = result.plot(boxes=True, labels=True, conf=True)
        height, width = image.shape[:2]
        if width > self.width:
            scale = self.width / width
            image = cv2.resize(
                image,
                (self.width, max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )

        encoded, jpeg = cv2.imencode(
            ".jpg",
            image,
            [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
        )
        if not encoded:
            raise RuntimeError("OpenCV could not encode the dashboard preview.")

        destination = preview_path(feed_id, self.root)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self.root,
            prefix=f".feed-{feed_id}-",
            suffix=".jpg",
        )
        try:
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                temporary_file.write(jpeg.tobytes())
                temporary_file.flush()
            os.chmod(temporary_name, 0o640)
            os.replace(temporary_name, destination)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return destination

    def remove(self, feed_id: int) -> None:
        preview_path(feed_id, self.root).unlink(missing_ok=True)

    def prune(self, valid_feed_ids: set[int]) -> None:
        valid_names = {f"feed-{feed_id}.jpg" for feed_id in valid_feed_ids}
        for existing in self.root.glob("feed-*.jpg"):
            if existing.name not in valid_names:
                existing.unlink(missing_ok=True)
