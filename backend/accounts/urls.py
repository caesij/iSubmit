from django.urls import path
from django.contrib.auth import views as auth_views
from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('reset_password/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/pass_reset/password_reset_form.html',
            email_template_name='accounts/pass_reset/password_reset_email.txt',
            html_email_template_name='accounts/pass_reset/password_reset_email.html',
            success_url='/auth/reset_password_sent/',
        ), 
        name='reset_password',
    ),
    path('reset_password_sent/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/pass_reset/password_reset_done.html'
        ), 
        name='password_reset_done',
    ),
    path('reset_/<uidb64>/<token>',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/pass_reset/password_reset_confirm.html',
            success_url='/auth/reset_password_complete/',
        ), 
        name='password_reset_confirm',
    ),
    path('reset_password_complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/pass_reset/password_reset_complete.html'
        ), 
        name='password_reset_complete',
    ),
]