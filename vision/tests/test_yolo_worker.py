from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from django.test import TestCase, override_settings

from vision.config import YoloRuntimeConfig
from vision.models import VideoFeed
from vision.services.yolo_worker import MultiFeedYoloWorker


def runtime_config():
    return YoloRuntimeConfig(
        model="models/yolo26x.pt",
        device="cpu",
        image_size=640,
        confidence=0.5,
        frame_stride=1,
        quantize=None,
    )


def inference_result():
    boxes = MagicMock()
    boxes.cls.int.return_value.cpu.return_value.tolist.return_value = []
    boxes.xyxy.cpu.return_value.tolist.return_value = []
    boxes.conf.cpu.return_value.tolist.return_value = []
    boxes.__len__.return_value = 0
    return SimpleNamespace(
        boxes=boxes,
        names={},
        orig_shape=(10, 10),
        speed={"inference": 4.2},
    )


class FakeCapture:
    instances = {}

    def __init__(self, feed_id, source):
        self.feed_id = feed_id
        self.source = source
        self.sequence = 1
        self.frame = np.full((10, 10, 3), feed_id, dtype=np.uint8)
        self.started = False
        self.stopped = False
        self.__class__.instances[feed_id] = self

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def latest(self):
        return self.sequence, self.frame

    @property
    def is_connected(self):
        return self.frame is not None


class FakePreviewPublisher:
    def __init__(self):
        self.published = []
        self.removed = []
        self.pruned = []

    def publish(self, feed_id, result):
        self.published.append(feed_id)

    def remove(self, feed_id):
        self.removed.append(feed_id)

    def prune(self, feed_ids):
        self.pruned.append(set(feed_ids))


@override_settings(
    YOLO_INFERENCE_FPS=2,
    YOLO_PREVIEW_FPS=1,
    YOLO_FEED_REFRESH_SECONDS=5,
)
class MultiFeedYoloWorkerTests(TestCase):
    def setUp(self):
        FakeCapture.instances = {}
        VideoFeed.objects.create(pk=1, rtsp_url="rtsp://one.example/live")
        VideoFeed.objects.create(pk=2, rtsp_url="rtsp://two.example/live")
        VideoFeed.objects.create(pk=3, rtsp_url="rtsp://three/live")
        self.model = MagicMock()
        self.model.predict.side_effect = lambda **kwargs: [inference_result()]
        self.model_factory = MagicMock(return_value=self.model)
        self.previews = FakePreviewPublisher()
        self.feed_rows = [
            (1, "rtsp://one.example/live"),
            (2, "rtsp://two.example/live"),
        ]
        self.worker = MultiFeedYoloWorker(
            runtime_config(),
            write=lambda message: None,
            model_factory=self.model_factory,
            capture_factory=FakeCapture,
            preview_publisher=self.previews,
            feed_loader=lambda: list(self.feed_rows),
        )

    def tearDown(self):
        self.worker.stop()

    def test_model_loads_once_and_feeds_run_round_robin(self):
        self.worker._load_model()
        self.worker._load_model()
        self.worker.sync_feeds(now=0)

        first = self.worker._next_ready_session(now=0)
        self.assertEqual(first.feed_id, 1)
        self.assertTrue(self.worker._process_session(first, now=0))
        second = self.worker._next_ready_session(now=0)
        self.assertEqual(second.feed_id, 2)
        self.assertTrue(self.worker._process_session(second, now=0))

        self.model_factory.assert_called_once_with("models/yolo26x.pt")
        self.assertEqual(self.model.predict.call_count, 2)
        first_source = self.model.predict.call_args_list[0].kwargs["source"]
        second_source = self.model.predict.call_args_list[1].kwargs["source"]
        self.assertEqual(int(first_source[0, 0, 0]), 1)
        self.assertEqual(int(second_source[0, 0, 0]), 2)

    def test_sync_adds_and_removes_feeds_without_reloading_model(self):
        self.worker._load_model()
        self.worker.sync_feeds(now=0)
        removed_capture = FakeCapture.instances[1]
        self.feed_rows = [(2, "rtsp://two.example/live"), (3, "rtsp://three/live")]

        self.worker.sync_feeds(now=5)

        self.assertEqual(set(self.worker.sessions), {2, 3})
        self.assertTrue(removed_capture.stopped)
        self.assertIn(1, self.previews.removed)
        self.assertTrue(FakeCapture.instances[3].started)
        self.model_factory.assert_called_once()

    def test_preview_rate_is_lower_than_inference_rate(self):
        self.worker._load_model()
        self.worker.sync_feeds(now=0)
        session = self.worker.sessions[1]

        self.assertTrue(self.worker._process_session(session, now=0))
        session.capture.sequence += 1
        self.assertTrue(self.worker._process_session(session, now=0.5))
        session.capture.sequence += 1
        self.assertTrue(self.worker._process_session(session, now=1.0))

        self.assertEqual(self.model.predict.call_count, 3)
        self.assertEqual(self.previews.published, [1, 1])

    def test_unready_feed_does_not_block_a_ready_feed(self):
        self.worker.sync_feeds(now=0)
        FakeCapture.instances[1].frame = None

        session = self.worker._next_ready_session(now=0)

        self.assertEqual(session.feed_id, 2)


class EnabledFeedSelectionTests(TestCase):
    def test_new_feeds_are_enabled_by_default(self):
        feed = VideoFeed.objects.create(rtsp_url="rtsp://camera.example/live")

        self.assertTrue(feed.is_enabled)
