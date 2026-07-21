from django.core.management.base import BaseCommand

from vision.config import YoloConfig
from vision.services.yolo_runner import YoloRunner


class Command(BaseCommand):
    help = "Run the persistent Ultralytics YOLO detection worker."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            help="Stream URL, video/image path, or webcam index (overrides YOLO_SOURCE).",
        )
        parser.add_argument(
            "--model",
            help="YOLO weights path (defaults to YOLO_MODEL).",
        )
        parser.add_argument(
            "--device",
            help="Inference device such as 0, cuda:0, or cpu.",
        )
        parser.add_argument(
            "--image-size",
            type=int,
            help="Inference image size in pixels.",
        )
        parser.add_argument(
            "--confidence",
            type=float,
            help="Minimum detection confidence from 0 to 1.",
        )
        parser.add_argument(
            "--frame-stride",
            type=int,
            help="Process every Nth frame.",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process one frame and exit (useful for smoke tests).",
        )

    def handle(self, *args, **options):
        config = YoloConfig.from_options(options)
        runner = YoloRunner(config, self.stdout.write)

        try:
            frame_count = runner.run(once=options["once"])
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Detection stopped by operator."))
            return

        self.stdout.write(
            self.style.SUCCESS(f"Detection finished after {frame_count} frame(s).")
        )
