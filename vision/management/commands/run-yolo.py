from time import sleep

from django.core.management.base import BaseCommand, CommandError

from vision.config import YoloConfig
from vision.services.detection_state import DetectionStateRecorder
from vision.services.yolo_runner import YoloRunner


class Command(BaseCommand):
    help = "Run the persistent Ultralytics YOLO detection worker."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            help="Stream URL, video/image path, or webcam index (overrides YOLO_SOURCE).",
        )
        parser.add_argument(
            "--feed-id",
            type=int,
            help="Use a saved Video Feed by database ID.",
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
        parser.add_argument(
            "--watch",
            action="store_true",
            help="Wait for a saved feed and reconnect after stream interruptions.",
        )

    def handle(self, *args, **options):
        try:
            self._run(options)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Detection stopped by operator."))

    def _run(self, options):
        while True:
            try:
                config = YoloConfig.from_options(options)
            except CommandError as error:
                if not options["watch"]:
                    raise
                self.stdout.write(self.style.WARNING(f"{error} Retrying in 10s."))
                sleep(10)
                continue

            recorder = (
                DetectionStateRecorder(config.feed_id) if config.feed_id is not None else None
            )
            runner = YoloRunner(
                config,
                self.stdout.write,
                on_result=recorder.record if recorder is not None else None,
            )
            frame_count = runner.run(once=options["once"])
            if options["once"] or not options["watch"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Detection finished after {frame_count} frame(s)."
                    )
                )
                return

            self.stdout.write(
                self.style.WARNING(
                    f"Stream ended after {frame_count} frame(s). Reconnecting in 5s."
                )
            )
            sleep(5)
