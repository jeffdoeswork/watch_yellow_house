from collections.abc import Callable
from urllib.parse import urlsplit

from vision.config import YoloConfig
from vision.services.detection_state import detection_counts


class YoloRunner:
    """Owns a single YOLO model for the lifetime of an inference worker."""

    def __init__(
        self,
        config: YoloConfig,
        write: Callable[[str], None],
        on_result: Callable[[int, object], None] | None = None,
    ):
        self.config = config
        self.write = write
        self.on_result = on_result
        self.model = None

    def run(self, *, once: bool = False) -> int:
        self._load_model()
        self.write(
            f"Detection started: source={safe_source_label(self.config.source)}, "
            f"device={self.config.device}, model={self.config.model}"
        )

        processed_frames = 0
        for result in self.model.predict(
            source=self.config.source,
            stream=True,
            stream_buffer=False,
            device=self.config.device,
            imgsz=self.config.image_size,
            conf=self.config.confidence,
            vid_stride=self.config.frame_stride,
            quantize=self.config.quantize,
            verbose=False,
        ):
            processed_frames += 1
            if self.on_result is not None:
                self.on_result(processed_frames, result)
            self.write(format_result(processed_frames, result))
            if once:
                break

        return processed_frames

    def _load_model(self) -> None:
        from ultralytics import YOLO

        self.write(f"Loading {self.config.model} on device {self.config.device}...")
        self.model = YOLO(self.config.model)
        self.model.to(torch_device_name(self.config.device))
        self.write("Model loaded and resident. Waiting for frames...")


def format_result(frame_number: int, result) -> str:
    detections = len(result.boxes) if result.boxes is not None else 0
    counts = detection_counts(result)

    summary = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    inference_ms = result.speed.get("inference", 0.0)
    suffix = f" ({summary})" if summary else ""
    return (
        f"frame={frame_number} detections={detections} "
        f"inference={inference_ms:.1f}ms{suffix}"
    )


def safe_source_label(source: str | int) -> str:
    """Describe a stream without writing embedded credentials to logs."""
    if isinstance(source, int):
        return f"webcam:{source}"

    parsed = urlsplit(source)
    if parsed.scheme and parsed.hostname:
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{parsed.hostname}{port}{parsed.path}"
    return source


def torch_device_name(device: str) -> str:
    """Convert Ultralytics' short GPU syntax to a PyTorch device string."""
    return f"cuda:{device}" if device.isdigit() else device
