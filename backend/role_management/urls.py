from django.urls import path
from role_management import views

app_name = 'role_management'

urlpatterns = [
    path('', views.role_management_view, name='role_management'),
]
