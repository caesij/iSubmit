from django.contrib import admin
from django.urls import path, include
from accounts.views import redirect_user_by_role
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)