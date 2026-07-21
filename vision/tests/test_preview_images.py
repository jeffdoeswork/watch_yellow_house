from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import cv2
import numpy as np
from django.test import SimpleTestCase

from vision.services.preview_images import PreviewPublisher, preview_path


class PreviewPublisherTests(SimpleTestCase):
    def test_annotated_jpeg_is_resized_and_atomically_published(self):
        source_image = np.full((720, 1280, 3), 180, dtype=np.uint8)
        result = SimpleNamespace(plot=lambda **options: source_image)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = PreviewPublisher(root=root, width=640, jpeg_quality=65)

            destination = publisher.publish(7, result)

            self.assertEqual(destination, preview_path(7, root))
            image = cv2.imread(str(destination))
            self.assertEqual(image.shape[:2], (360, 640))
            self.assertFalse(list(root.glob(".feed-7-*.jpg")))

    def test_prune_removes_only_unselected_feed_previews(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = PreviewPublisher(root=root)
            preview_path(1, root).write_bytes(b"one")
            preview_path(2, root).write_bytes(b"two")

            publisher.prune({2})

            self.assertFalse(preview_path(1, root).exists())
            self.assertTrue(preview_path(2, root).exists())
