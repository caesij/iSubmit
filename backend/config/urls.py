from django.contrib import admin
from django.urls import path, include
from accounts.views import redirect_user_by_role
from django.shortcuts import redirect

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)
    return redirect('accounts:login')

urlpatterns = [
    path('django-admin/', admin.site.urls),

    # Root Routing
    path('', root_redirect, name='root'),

    # Custom App Endpoints
    path('auth/', include('accounts.urls')),
    path('admin-portal/', include('admin_staff_portal.urls')),
    path('faculty-portal/', include('faculty_portal.urls')),
]