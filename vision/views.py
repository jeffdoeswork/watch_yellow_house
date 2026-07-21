from django.contrib.auth.decorators import login_required
from django.http import (
    FileResponse,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from .models import FeedDetectionState, VideoFeed
from .services.detection_payloads import state_payload
from .services.preview_images import preview_path
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
    video_feed = get_object_or_404(VideoFeed, pk=pk)
    state = FeedDetectionState.objects.filter(feed=video_feed).first()
    return render(
        request,
        "vision/video_feed_detail.html",
        {
            "video_feed": video_feed,
            "detection": state_payload(state, is_enabled=video_feed.is_enabled),
        },
    )


@never_cache
@login_required
def video_feed_detections(request, pk):
    video_feed = get_object_or_404(VideoFeed, pk=pk)
    state = FeedDetectionState.objects.filter(feed=video_feed).first()
    return JsonResponse(state_payload(state, is_enabled=video_feed.is_enabled))


@never_cache
@login_required
def video_feed_preview(request, pk):
    video_feed = get_object_or_404(VideoFeed, pk=pk)
    if not video_feed.is_enabled:
        return HttpResponse(status=204)

    image_path = preview_path(video_feed.pk)
    try:
        image_file = image_path.open("rb")
    except FileNotFoundError:
        return HttpResponse(status=204)

    response = FileResponse(image_file, content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    response["Content-Disposition"] = "inline"
    return response


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
