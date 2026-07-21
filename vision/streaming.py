import subprocess
from collections.abc import Iterator


def open_browser_video_stream(rtsp_url: str) -> subprocess.Popen[bytes]:
    """Transcode an RTSP feed to a browser-compatible fragmented MP4 stream."""
    return subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-rtsp_transport",
            "tcp",
            "-i",
            rtsp_url,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "30",
            "-keyint_min",
            "30",
            "-sc_threshold",
            "0",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+frag_keyframe+empty_moov+default_base_moof",
            "-frag_duration",
            "1000000",
            "-f",
            "mp4",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def iter_video_chunks(
    process: subprocess.Popen[bytes], chunk_size: int = 64 * 1024
) -> Iterator[bytes]:
    """Yield FFmpeg output and stop the child process when the client leaves."""
    if process.stdout is None:
        raise RuntimeError("FFmpeg was started without a stdout pipe.")

    try:
        while chunk := process.stdout.read1(chunk_size):
            yield chunk
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
