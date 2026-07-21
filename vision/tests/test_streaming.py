import subprocess
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from vision.streaming import iter_video_chunks, open_browser_video_stream


class BrowserVideoStreamingTests(SimpleTestCase):
    @patch("vision.streaming.subprocess.Popen")
    def test_ffmpeg_transcodes_video_and_optional_audio_to_mp4(self, popen):
        source = "rtsp://camera-user:secret@camera.example/live"

        open_browser_video_stream(source)

        command = popen.call_args.args[0]
        self.assertEqual(command[0], "ffmpeg")
        self.assertEqual(command[command.index("-i") + 1], source)
        self.assertIn("0:a:0?", command)
        self.assertIn("libx264", command)
        self.assertIn("aac", command)
        self.assertEqual(command[-2:], ["mp4", "pipe:1"])
        self.assertEqual(popen.call_args.kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(popen.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_iterator_stops_ffmpeg_when_browser_disconnects(self):
        process = MagicMock()
        process.stdout.read1.side_effect = [b"chunk", b""]
        process.poll.return_value = None

        self.assertEqual(list(iter_video_chunks(process)), [b"chunk"])

        process.stdout.close.assert_called_once_with()
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=2)
