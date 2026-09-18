from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

from accounts.decorators import faculty
from accounts.forms import PreferencesForm
from accounts.models import NotificationPreference
from accounts.utils import get_or_create_preferences


@faculty
@require_http_methods(['GET', 'POST'])
def preferences_view(request):
    if request.method == 'POST':
        form = PreferencesForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferences updated successfully.')
            return redirect('faculty_portal:preferences')
        else:
            messages.error(request, 'Invalid.')
    else:
        form = PreferencesForm(instance=request.user)

    context = {'form': form}
    
    return render(
        request,
        'faculty_portal/settings/preferences.html',
        context
    )

@faculty
@require_http_methods(['GET', 'POST'])
def notification_settings_view(request):
    preferences = get_or_create_preferences(request.user)

    if request.method == 'POST':
        for pref in preferences:
            pref.enabled = pref.notification_type in request.POST
        NotificationPreference.objects.bulk_update(preferences, ['enabled'])
        messages.success(request, 'Notification settings updated.')
        return redirect('faculty_portal:notification_settings')

    context = {'preferences': preferences}
    
    return render(
        request,
        'faculty_portal/settings/notification_settings.html',
        context
    )

@faculty
@require_http_methods(['GET', 'POST'])
def notification_channel_view(request):
    preferences = get_or_create_preferences(request.user)

    if request.method == 'POST':
        for pref in preferences:
            pref.email_enabled = f'email_{pref.notification_type}' in request.POST
            pref.system_enabled = f'system_{pref.notification_type}' in request.POST
        NotificationPreference.objects.bulk_update(preferences, ['email_enabled', 'system_enabled'])
        messages.success(request, 'Notification channels updated.')
        return redirect('faculty_portal:notification_channel')

    context = {'preferences': preferences}
    
    return render(
        request,
        'faculty_portal/settings/notification_channel.html',
        context
    )

@faculty
@require_http_methods(['GET', 'POST'])
def account_and_security_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('faculty_portal:account_and_security')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
        
    context = {'form': form}

    return render(
        request,
        'faculty_portal/settings/account_security.html',
        context
    )