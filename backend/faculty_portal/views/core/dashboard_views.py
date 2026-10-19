from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from accounts.decorators import faculty
from faculty_portal.services.faculty_dashboard import get_dashboard_data

from faculty_portal.helpers.faculty_dashboard import (
    get_overview_queryset,
    serialize_overview_submissions
)


@faculty
@require_http_methods(['GET'])
def dashboard_data_view(request):
    tab = request.GET.get('tab', 'all')

    if request.GET.get('overview_only') == '1':
        return JsonResponse({
            'overview_submissions': serialize_overview_submissions(
                get_overview_queryset(request.user, tab),
                request.user,
            )
        })

    data = get_dashboard_data(request.user)
    data['overview_submissions'] = serialize_overview_submissions(
        get_overview_queryset(request.user, tab),
        request.user,
    )

    return JsonResponse(data)


@faculty
@require_http_methods(['GET'])
def dashboard_view(request):
    tab = request.GET.get('tab', 'all')
    data = get_dashboard_data(request.user)

    context = {
        **data,
        'overview_submissions': get_overview_queryset(request.user, tab)[:5],
        'selected_tab': tab
    }

    return render(
        request,
        'faculty_portal/core/dashboard.html',
        context
    )