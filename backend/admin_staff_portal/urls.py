from django.urls import path
from . import views

app_name = 'admin_staff_portal'

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/add/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<uuid:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<uuid:pk>/toggle-acc-status/', views.UserToggleAccStatusView.as_view(), name='user_toggle_acc_status'),
]