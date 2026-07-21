from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from vision.config import YoloConfig
from vision.models import VideoFeed


class YoloConfigTests(TestCase):
    @override_settings(
        YOLO_SOURCE=None,
        YOLO_MODEL="models/yolo26x.pt",
        YOLO_DEVICE="0",
        YOLO_IMAGE_SIZE=640,
        YOLO_CONFIDENCE=0.25,
        YOLO_FRAME_STRIDE=1,
        YOLO_QUANTIZE="16",
    )
    def test_source_is_required(self):
        with self.assertRaisesMessage(CommandError, "No stream source configured"):
            YoloConfig.from_options({})

    @override_settings(
        YOLO_SOURCE="0",
        YOLO_MODEL="models/yolo26x.pt",
        YOLO_DEVICE="0",
        YOLO_IMAGE_SIZE=640,
        YOLO_CONFIDENCE=0.25,
        YOLO_FRAME_STRIDE=1,
        YOLO_QUANTIZE="16",
    )
    def test_webcam_source_and_fp16_are_normalized(self):
        config = YoloConfig.from_options({})

        self.assertEqual(config.source, 0)
        self.assertEqual(config.quantize, 16)

    @override_settings(
        YOLO_SOURCE=None,
        YOLO_MODEL="models/yolo26x.pt",
        YOLO_DEVICE="0",
        YOLO_IMAGE_SIZE=640,
        YOLO_CONFIDENCE=0.25,
        YOLO_FRAME_STRIDE=1,
        YOLO_QUANTIZE="16",
    )
    def test_saved_feed_is_used_when_no_source_override_exists(self):
        feed = VideoFeed.objects.create(rtsp_url="rtsp://camera.example/live")

        config = YoloConfig.from_options({"feed_id": feed.pk})

        self.assertEqual(config.source, feed.rtsp_url)
        self.assertEqual(config.feed_id, feed.pk)
