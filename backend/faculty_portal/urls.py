from django.urls import path
from . import views

app_name = 'faculty_portal'

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
]