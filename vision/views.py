from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from .models import VideoFeed
from .streaming import iter_video_chunks, open_browser_video_stream


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
    try:
        process = open_browser_video_stream(video_feed.rtsp_url)
    except OSError:
        return HttpResponse("Video streaming is unavailable.", status=503)

    response = StreamingHttpResponse(
        iter_video_chunks(process),
        content_type="video/mp4",
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response["X-Accel-Buffering"] = "no"
    response["Content-Disposition"] = "inline"
    return response
