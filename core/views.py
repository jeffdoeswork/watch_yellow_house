from django.shortcuts import render


def dashboard(request):
    return render(request, "core/dashboard.html")


def video_feeds(request):
    return render(request, "core/video_feeds.html")
