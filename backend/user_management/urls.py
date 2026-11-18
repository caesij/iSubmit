from django.urls import path
from user_management import views

app_name = 'user_management'

urlpatterns = [
    path('', views.user_list_view, name='user_list'),
    path('users/add/', views.user_form_view,name='user_create'),
    path('users/<uuid:pk>/edit/', views.user_form_view, name='user_edit'),
    path('ajax/assignment-options/', views.assignment_options_view, name='assignment_options'),
    path('users/<uuid:pk>/toggle-status/', views.user_toggle_status_view, name='user_toggle_acc_status'),
    path('users/<uuid:pk>/unlock/', views.user_unlock_view, name='user_unlock'),
]
