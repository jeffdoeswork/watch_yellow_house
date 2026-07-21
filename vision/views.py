from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from .models import VideoFeed
from .streaming import iter_mjpeg_frames, open_rtsp_capture


@login_required
def video_feed_list(request):
    return render(
        request,
        "vision/video_feed_list.html",
        {"video_feeds": VideoFeed.objects.all()},
    )


@login_required
def video_feed_detail(request, pk):
    return render(
        request,
        "vision/video_feed_detail.html",
        {"video_feed": get_object_or_404(VideoFeed, pk=pk)},
    )


@never_cache
@login_required
def video_feed_stream(request, pk):
    video_feed = get_object_or_404(VideoFeed, pk=pk)
    capture = open_rtsp_capture(video_feed.rtsp_url)
    if not capture.isOpened():
        capture.release()
        return HttpResponse("Unable to connect to this video feed.", status=502)

    response = StreamingHttpResponse(
        iter_mjpeg_frames(capture),
        content_type="multipart/x-mixed-replace; boundary=frame",
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response["X-Accel-Buffering"] = "no"
    return response
