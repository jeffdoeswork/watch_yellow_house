from time import monotonic, sleep
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from vision.services.frame_capture import LatestFrameCapture


class LatestFrameCaptureTests(SimpleTestCase):
    def test_capture_discards_old_frames_and_releases_connection(self):
        capture = MagicMock()
        capture.isOpened.return_value = True
        capture.read.side_effect = [
            (True, "old-frame"),
            (True, "new-frame"),
            (False, None),
        ]
        feed_capture = LatestFrameCapture(
            4,
            "rtsp://user:secret@camera.example/live",
            capture_factory=lambda source: capture,
        )

        feed_capture.start()
        deadline = monotonic() + 1
        while feed_capture.latest()[0] < 2 and monotonic() < deadline:
            sleep(0.01)
        feed_capture.stop()

        sequence, frame = feed_capture.latest()
        self.assertGreaterEqual(sequence, 2)
        self.assertEqual(frame, "new-frame")
        capture.release.assert_called()
