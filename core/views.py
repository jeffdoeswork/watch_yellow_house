from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from vision.services.detection_payloads import dashboard_payload


@login_required
def dashboard(request):
    return render(request, "core/dashboard.html", dashboard_payload())


@never_cache
@login_required
def dashboard_detections(request):
    return JsonResponse(dashboard_payload())
