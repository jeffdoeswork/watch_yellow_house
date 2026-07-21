from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from vision.services.yolo_runner import (
    format_result,
    safe_source_label,
    torch_device_name,
)


class ResultFormattingTests(SimpleTestCase):
    def test_stream_credentials_are_not_logged(self):
        source = "rtsp://camera-user:secret@example.com:8554/live"

        self.assertEqual(safe_source_label(source), "rtsp://example.com:8554/live")

    def test_detection_summary_includes_class_counts(self):
        boxes = MagicMock()
        boxes.cls = SimpleNamespace(
            int=lambda: SimpleNamespace(
                cpu=lambda: SimpleNamespace(tolist=lambda: [0, 0, 2])
            )
        )
        boxes.__len__.return_value = 3
        result = SimpleNamespace(
            boxes=boxes,
            names={0: "person", 2: "car"},
            speed={"inference": 12.34},
        )

        summary = format_result(7, result)

        self.assertIn("frame=7", summary)
        self.assertIn("car=1", summary)
        self.assertIn("person=2", summary)

    def test_short_gpu_device_is_valid_for_torch(self):
        self.assertEqual(torch_device_name("0"), "cuda:0")
        self.assertEqual(torch_device_name("cpu"), "cpu")
