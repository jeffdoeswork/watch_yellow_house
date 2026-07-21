from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import TestCase

from vision.models import FeedDetectionState, VideoFeed
from vision.services.detection_state import (
    DetectionStateRecorder,
    detection_boxes,
    stabilized_counts,
)


def make_result(class_ids=(0, 0, 2)):
    boxes = MagicMock()
    boxes.cls.int.return_value.cpu.return_value.tolist.return_value = list(class_ids)
    boxes.xyxy.cpu.return_value.tolist.return_value = [
        [20, 10, 100, 90],
        [0, 0, 50, 50],
        [120, 40, 200, 100],
    ][: len(class_ids)]
    boxes.conf.cpu.return_value.tolist.return_value = [0.91, 0.82, 0.74][
        : len(class_ids)
    ]
    return SimpleNamespace(
        boxes=boxes,
        names={0: "person", 2: "car"},
        orig_shape=(100, 200),
        speed={"inference": 12.345},
    )


class StabilizedCountTests(TestCase):
    def test_per_class_mode_remains_integral(self):
        history = [
            {"person": 2, "car": 1},
            {"person": 2, "car": 1},
            {"person": 3, "car": 1},
            {"person": 2},
        ]

        self.assertEqual(stabilized_counts(history), {"car": 1, "person": 2})

    def test_frequency_tie_prefers_the_most_recent_count(self):
        self.assertEqual(
            stabilized_counts([{"person": 2}, {"person": 3}]),
            {"person": 3},
        )

    def test_frequency_tie_keeps_the_previous_displayed_count(self):
        self.assertEqual(
            stabilized_counts(
                [{"person": 2}, {"person": 3}],
                previous_counts={"person": 2},
            ),
            {"person": 2},
        )

    def test_missing_classes_are_counted_as_zero(self):
        history = [{"person": 1}] * 4 + [{}] * 6

        self.assertEqual(stabilized_counts(history), {})

    def test_boxes_are_normalized_to_the_source_frame(self):
        boxes = detection_boxes(make_result(class_ids=(0,)))

        self.assertEqual(
            boxes,
            [
                {
                    "class_name": "person",
                    "confidence": 0.91,
                    "x1": 0.1,
                    "y1": 0.1,
                    "x2": 0.5,
                    "y2": 0.9,
                }
            ],
        )


class DetectionStateRecorderTests(TestCase):
    def test_recorder_keeps_only_the_configured_window(self):
        feed = VideoFeed.objects.create(rtsp_url="rtsp://camera.example/live")
        recorder = DetectionStateRecorder(feed.pk, window_size=2)

        recorder.record(1, make_result(class_ids=(0,)))
        recorder.record(2, make_result(class_ids=(0, 0)))
        recorder.record(3, make_result(class_ids=(0, 0)))

        state = FeedDetectionState.objects.get(feed=feed)
        self.assertEqual(state.count_history, [{"person": 2}, {"person": 2}])
        self.assertEqual(state.stable_counts, {"person": 2})
        self.assertEqual(state.frame_number, 3)
        self.assertEqual(state.inference_ms, 12.35)
