from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from time import monotonic, sleep
from typing import Any

from django.conf import settings
from django.db import DatabaseError, close_old_connections

from vision.config import YoloRuntimeConfig
from vision.models import FeedDetectionState, VideoFeed
from vision.services.detection_state import DetectionStateRecorder
from vision.services.frame_capture import LatestFrameCapture
from vision.services.preview_images import PreviewPublisher
from vision.services.yolo_runner import safe_source_label, torch_device_name


@dataclass
class FeedSession:
    feed_id: int
    source: str
    capture: LatestFrameCapture
    recorder: DetectionStateRecorder
    frame_number: int = 0
    last_sequence: int = 0
    next_inference_at: float = 0.0
    next_preview_at: float = 0.0


class MultiFeedYoloWorker:
    """Schedule enabled feeds through one resident model, one frame at a time."""

    def __init__(
        self,
        config: YoloRuntimeConfig,
        write,
        *,
        model_factory=None,
        capture_factory=LatestFrameCapture,
        preview_publisher: PreviewPublisher | None = None,
        feed_loader=None,
        clock=monotonic,
        wait=sleep,
    ):
        self.config = config
        self.write = write
        self.model_factory = model_factory or _ultralytics_model
        self.capture_factory = capture_factory
        self.preview_publisher = preview_publisher or PreviewPublisher()
        self.feed_loader = feed_loader or _enabled_feeds
        self.clock = clock
        self.wait = wait
        self.model = None
        self.sessions: dict[int, FeedSession] = {}
        self._cursor = 0
        self._next_feed_sync_at = 0.0
        self._reported_waiting = False

    def run(self, *, once: bool = False, stop_event: Event | None = None) -> int:
        stop_event = stop_event or Event()
        self._load_model()
        processed_frames = 0

        try:
            while not stop_event.is_set():
                now = self.clock()
                if now >= self._next_feed_sync_at:
                    self.sync_feeds(now)

                session = self._next_ready_session(now)
                if session is None:
                    if not self.sessions and not self._reported_waiting:
                        self.write("No enabled video feeds. Model resident; waiting...")
                        self._reported_waiting = True
                    self.wait(0.05)
                    continue

                if self._process_session(session, now):
                    processed_frames += 1
                    if once:
                        break
        finally:
            self.stop()

        return processed_frames

    def sync_feeds(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        close_old_connections()
        enabled_feeds = {feed_id: source for feed_id, source in self.feed_loader()}

        for feed_id, session in list(self.sessions.items()):
            if enabled_feeds.get(feed_id) == session.source:
                continue
            session.capture.stop()
            self.preview_publisher.remove(feed_id)
            del self.sessions[feed_id]

        for feed_id, source in enabled_feeds.items():
            if feed_id in self.sessions:
                continue
            capture = self.capture_factory(feed_id, source)
            capture.start()
            self.sessions[feed_id] = FeedSession(
                feed_id=feed_id,
                source=source,
                capture=capture,
                recorder=DetectionStateRecorder(feed_id),
                next_inference_at=now,
                next_preview_at=now,
            )
            self.write(f"Feed #{feed_id} scheduled: {safe_source_label(source)}")

        self.preview_publisher.prune(set(enabled_feeds))
        self._publish_capture_statuses()
        self._next_feed_sync_at = now + settings.YOLO_FEED_REFRESH_SECONDS
        self._reported_waiting = False

    def stop(self) -> None:
        for session in self.sessions.values():
            session.capture.stop()
        self.sessions.clear()

    def _publish_capture_statuses(self) -> None:
        for feed_id, session in self.sessions.items():
            worker_status = (
                FeedDetectionState.WorkerStatus.CONNECTED
                if session.capture.is_connected
                else FeedDetectionState.WorkerStatus.RECONNECTING
            )
            updated = FeedDetectionState.objects.filter(feed_id=feed_id).update(
                worker_status=worker_status
            )
            if not updated:
                FeedDetectionState.objects.create(
                    feed_id=feed_id,
                    worker_status=worker_status,
                )

    def _next_ready_session(self, now: float) -> FeedSession | None:
        feed_ids = sorted(self.sessions)
        if not feed_ids:
            return None

        for offset in range(len(feed_ids)):
            index = (self._cursor + offset) % len(feed_ids)
            session = self.sessions[feed_ids[index]]
            if now < session.next_inference_at:
                continue
            sequence, frame = session.capture.latest()
            if frame is None or sequence == session.last_sequence:
                continue
            self._cursor = (index + 1) % len(feed_ids)
            return session
        return None

    def _process_session(self, session: FeedSession, now: float) -> bool:
        sequence, frame = session.capture.latest()
        session.next_inference_at = now + (1.0 / settings.YOLO_INFERENCE_FPS)
        if frame is None or sequence == session.last_sequence:
            return False

        try:
            result = self.model.predict(
                source=frame,
                stream=False,
                device=self.config.device,
                imgsz=self.config.image_size,
                conf=self.config.confidence,
                quantize=self.config.quantize,
                verbose=False,
            )[0]
        except Exception as error:
            # An unhealthy feed must not prevent inference for the others.
            self.write(f"Feed #{session.feed_id} inference failed: {error}")
            session.last_sequence = sequence
            return False

        session.last_sequence = sequence
        session.frame_number += 1
        try:
            session.recorder.record(session.frame_number, result)
        except DatabaseError as error:
            self.write(f"Feed #{session.feed_id} state update failed: {error}")

        if now >= session.next_preview_at:
            try:
                self.preview_publisher.publish(session.feed_id, result)
            except Exception as error:
                # A failed preview must not discard an otherwise valid result.
                self.write(f"Feed #{session.feed_id} preview failed: {error}")
            session.next_preview_at = now + (1.0 / settings.YOLO_PREVIEW_FPS)

        return True

    def _load_model(self) -> None:
        if self.model is not None:
            return
        self.write(f"Loading {self.config.model} on device {self.config.device}...")
        self.model = self.model_factory(self.config.model)
        self.model.to(torch_device_name(self.config.device))
        self.write("Model loaded and resident. Scheduling enabled feeds...")


def _enabled_feeds() -> list[tuple[int, str]]:
    return list(
        VideoFeed.objects.filter(is_enabled=True)
        .order_by("id")
        .values_list("id", "rtsp_url")
    )


def _ultralytics_model(model_path: str) -> Any:
    from ultralytics import YOLO

    return YOLO(model_path)
