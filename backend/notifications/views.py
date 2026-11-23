from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from accounts.decorators import access_required
from notifications.forms import SystemNotificationForm
from notifications.helpers import get_role_based_notifications
from notifications.models import Notification, NotificationPreference
from notifications.services import notify_role_subscribers

ADMIN_TEMPLATE_DIR = 'admin_staff_portal/notifications'
FACULTY_TEMPLATE_DIR = 'faculty_portal/notifications'
NotificationType = NotificationPreference.NotificationType


@access_required('access_system_notifications', 'create_system_notifications',)
@require_http_methods(['GET', 'POST'])
def create_system_notification_view(request):
    if request.method == 'POST':
        form = SystemNotificationForm(request.POST)

        if form.is_valid():
            recipient_count = notify_role_subscribers(
                notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
                title=form.cleaned_data['title'],
                message=form.cleaned_data['message'],
            )

            messages.success(
                request,
                f'Created system notifications for {recipient_count} '
                f'account{"s" if recipient_count != 1 else ""}.',
            )

            return redirect('notifications:notification_list')

    else:
        form = SystemNotificationForm()

    context = {'form': form}
    
    return render(request, f'{ADMIN_TEMPLATE_DIR}/create_notification.html', context)


@login_required
@require_http_methods(['GET'])
def notification_list_data_view(request):
    context = get_role_based_notifications(request)

    page_obj = Paginator(context.pop('notifications'), 7).get_page(
        request.GET.get('page')
    )
    context.update({
        'notifications': page_obj,
        'page_obj': page_obj,
    })

    template_dir = (
        FACULTY_TEMPLATE_DIR if request.user.is_faculty else ADMIN_TEMPLATE_DIR
    )
    html = render_to_string(
        f'{template_dir}/_notifications_list.html',
        context,
        request=request,
    )

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False,
    ).count()

    return JsonResponse({
        'html': html,
        'unread_count': unread_count,
    })


@login_required
@require_http_methods(['GET'])
def notification_list_view(request):
    context = get_role_based_notifications(request)
    page_obj = Paginator(context.pop('notifications'), 7).get_page(
        request.GET.get('page')
    )
    context.update({
        'notifications': page_obj,
        'page_obj': page_obj,
    })

    template_dir = (
        FACULTY_TEMPLATE_DIR if request.user.is_faculty else ADMIN_TEMPLATE_DIR
    )
    return render(
        request,
        f'{template_dir}/notifications_list.html',
        context,
    )


@login_required
@require_http_methods(['GET'])
def notification_dropdown_view(request):
    notifications = Notification.objects.filter(
        user=request.user,
    ).order_by('-created_at')[:3]

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False,
    ).count()

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    template_dir = (
        FACULTY_TEMPLATE_DIR if request.user.is_faculty else ADMIN_TEMPLATE_DIR
    )
    html = render_to_string(
        f'{template_dir}/notif_dropdown.html',
        context,
        request=request,
    )

    return JsonResponse({
        'html': html,
        'unread_count': unread_count,
    })


@login_required
@require_http_methods(['POST'])
def mark_notification_read_view(request, notification_id):
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user,
    )
    notification.is_read = True
    notification.save(update_fields=['is_read'])

    if notification.link:
        return redirect(notification.link)

    return redirect('notifications:notification_list')


@login_required
@require_http_methods(['POST'])
def mark_all_notifications_read_view(request):
    Notification.objects.filter(
        user=request.user,
        is_read=False,
    ).update(is_read=True)

    return redirect('notifications:notification_list')
