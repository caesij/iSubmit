from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.global_search import RESULT_LIMIT, search_portal

DASHBOARD_URLS = {
    'ADMIN': 'admin_staff_portal:admin_dashboard',
    'STAFF': 'admin_staff_portal:staff_dashboard',
    'FACULTY': 'faculty_portal:dashboard'
}


@login_required
@require_GET
def global_search_suggestions(request):
    query = ' '.join(request.GET.get('q', '').split())
    faculty_name = ' '.join(request.GET.get('faculty_name', '').split())
    document_title = ' '.join(request.GET.get('document_title', '').split())

    results = search_portal(
        request.user,
        query,
        limit=RESULT_LIMIT,
        faculty_name=faculty_name,
        document_title=document_title
    )

    return JsonResponse(results)


@login_required
@require_GET
def global_search_results(request):
    query = ' '.join(request.GET.get('q', '').split())
    faculty_name = ' '.join(request.GET.get('faculty_name', '').split())
    document_title = ' '.join(request.GET.get('document_title', '').split())

    results = search_portal(
        request.user,
        query,
        faculty_name=faculty_name,
        document_title=document_title,
    )
    
    context = {
        'query': query,
        'faculty_name': faculty_name,
        'document_title': document_title,
        'has_search': any((
            query,
            faculty_name,
            document_title
        )),
        'dashboard_url': DASHBOARD_URLS.get(request.user.role),
        **results
    }

    return render(
        request,
        'core/global_search_results.html',
        context
    )