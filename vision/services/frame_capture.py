from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock, Thread
from typing import Any


class LatestFrameCapture:
    """Continuously drain one source while retaining only its newest frame."""

    def __init__(
        self,
        feed_id: int,
        source: str,
        capture_factory: Callable[[str], Any] | None = None,
    ):
        self.feed_id = feed_id
        self.source = source
        self.capture_factory = capture_factory or open_rtsp_capture
        self._stop_event = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._capture = None
        self._latest_frame = None
        self._sequence = 0
        self._connected = False

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(
            target=self._capture_loop,
            name=f"feed-capture-{self.feed_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 6.0) -> None:
        self._stop_event.set()
        with self._lock:
            capture = self._capture
        if capture is not None:
            capture.release()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def latest(self) -> tuple[int, Any | None]:
        with self._lock:
            return self._sequence, self._latest_frame

    def _capture_loop(self) -> None:
        backoff_seconds = 1.0
        while not self._stop_event.is_set():
            try:
                capture = self.capture_factory(self.source)
            except Exception:
                self._mark_disconnected()
                self._stop_event.wait(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30.0)
                continue
            with self._lock:
                self._capture = capture

            if not capture.isOpened():
                capture.release()
                self._mark_disconnected()
                self._stop_event.wait(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30.0)
                continue

            backoff_seconds = 1.0
            self._set_connected(True)
            while not self._stop_event.is_set():
                try:
                    received, frame = capture.read()
                except Exception:
                    received, frame = False, None
                if not received:
                    break
                with self._lock:
                    self._latest_frame = frame
                    self._sequence += 1

            capture.release()
            self._mark_disconnected()
            if not self._stop_event.is_set():
                self._stop_event.wait(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30.0)

        with self._lock:
            self._capture = None
            self._connected = False

    def _mark_disconnected(self) -> None:
        self._set_connected(False)

    def _set_connected(self, connected: bool) -> None:
        with self._lock:
            self._connected = connected


def open_rtsp_capture(source: str):
    import cv2

    parameters = [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
        5000,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC,
        5000,
    ]
    return cv2.VideoCapture(source, cv2.CAP_FFMPEG, parameters)
