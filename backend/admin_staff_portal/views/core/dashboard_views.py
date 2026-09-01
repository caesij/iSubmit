from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.decorators import role_required

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def dashboard_view(request):
    context = {}
    return render(
        request, 
        'admin_staff_portal/core/dashboard.html', 
        context
    )