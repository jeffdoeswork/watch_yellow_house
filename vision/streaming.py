from collections.abc import Iterator


def open_rtsp_capture(rtsp_url: str):
    import cv2

    return cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)


def iter_mjpeg_frames(capture) -> Iterator[bytes]:
    import cv2

    try:
        while capture.isOpened():
            success, frame = capture.read()
            if not success:
                break

            encoded, jpeg = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 82],
            )
            if not encoded:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + jpeg.tobytes()
                + b"\r\n"
            )
    finally:
        capture.release()
