from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def briefing(request):
    return render(
        request,
        "core/placeholder.html",
        {
            "page_eyebrow": "Daily view",
            "page_title": "Briefing",
            "page_description": "A focused overview of the latest developments.",
        },
    )


def timeline(request):
    return render(
        request,
        "core/placeholder.html",
        {
            "page_eyebrow": "Track changes",
            "page_title": "Timeline",
            "page_description": "Events will appear here in chronological order.",
        },
    )


def sources(request):
    return render(
        request,
        "core/placeholder.html",
        {
            "page_eyebrow": "Primary material",
            "page_title": "Sources",
            "page_description": "Keep the reporting transparent and easy to verify.",
        },
    )

