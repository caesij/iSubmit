from django.urls import path

from notifications import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list_view, name='notification_list'),
    path('create/', views.create_system_notification_view, name='create_system_notification'),
    path('data/', views.notification_list_data_view, name='list_data'),
    path('dropdown/', views.notification_dropdown_view, name='dropdown'),
    path('<int:notification_id>/read/', views.mark_notification_read_view, name='mark_read'),
    path('mark-all-read/', views.mark_all_notifications_read_view, name='mark_all_read')
]