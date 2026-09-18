from django.shortcuts import render
from django.views.decorators.http import require_http_methods


from accounts.decorators import faculty


@faculty
@require_http_methods(['GET'])
def dashboard_view(request):
    return render(
        request, 
        'faculty_portal/core/dashboard.html'
    )