from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.global_search import RESULT_LIMIT, search_portal


@login_required
@require_GET
def global_search_suggestions(request):
    results = search_portal(
        request.user,
        request.GET.get('q', ''),
        limit=RESULT_LIMIT
    )
    return JsonResponse(results)


@login_required
@require_GET
def global_search_results(request):
    query = ' '.join(request.GET.get('q', '').split())
    results = search_portal(request.user, query)
    return render(
        request,
        'core/global_search_results.html',
        {'query': query, **results}
    )
